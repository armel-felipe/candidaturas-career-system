from __future__ import annotations
import os
import platform
import sqlite3
import shutil
import subprocess
from pathlib import Path
from typing import Any

import save_job_description as legacy_save_job_description
import validate_project_structure as legacy_validate_project_structure

from career.paths import CAREER_STATE, ROOT
from career.services import fit_map as fit_map_service
from career.utils import read_json, sha256_file, sha256_text, write_json, write_text


def validate_structure() -> None:
    exit_code = legacy_validate_project_structure.main()
    if exit_code != 0:
        raise SystemExit(exit_code)


def save_job_description(company: str, role: str, text: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{legacy_save_job_description.slugify(company)}_{legacy_save_job_description.slugify(role)}.md"
    write_text(output_path, legacy_save_job_description.normalize_text(text))
    return output_path


def diagnose_runtime() -> dict[str, Any]:
    workflow_state = CAREER_STATE / "workflow_state.json"
    python_wrapper = ROOT / "scripts" / "python.sh"
    keyword_registry = ROOT / ".career-state" / "derived" / "keyword_ats_registry.json"
    translation_candidates = ROOT / ".career-state" / "derived" / "keyword_translation_candidates.json"
    macos_soffice = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    soffice = shutil.which("libreoffice") or shutil.which("soffice") or (str(macos_soffice) if macos_soffice.exists() else None)
    payload = read_json(workflow_state) if workflow_state.exists() else {}
    diagnosis = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "commands": {
            name: shutil.which(name)
            for name in ["git", "node", "npm", "python3", "hermes"]
        },
        "python_runtime": {
            "wrapper": str(python_wrapper.relative_to(ROOT)),
            "wrapper_exists": python_wrapper.exists(),
            "resolved_executable": _command_output([str(python_wrapper), "-c", "import sys; print(sys.executable)"])
            if python_wrapper.exists()
            else None,
            "resolved_version": _command_version([str(python_wrapper), "--version"]) if python_wrapper.exists() else None,
        },
        "libreoffice": {
            "command": soffice,
            "version": _command_version([soffice, "--version"]) if soffice else None,
        },
        "workflow_state": {
            "path": str(workflow_state.relative_to(ROOT)),
            "exists": workflow_state.exists(),
            "bytes": workflow_state.stat().st_size if workflow_state.exists() else 0,
            "completed_states": len(payload.get("completed_states", [])),
            "task_history": len(payload.get("task_history", [])),
        },
        "large_references": [
            {
                "path": str(path.relative_to(ROOT)),
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
            for path in [keyword_registry, translation_candidates]
        ],
    }
    diagnosis["control_plane"] = _control_plane_snapshot()
    diagnosis["runtime_observability"] = _runtime_observability_snapshot(
        diagnosis["control_plane"]
    )
    diagnosis["hermes_profiles"] = [
        {
            "profile_id": path.parent.name,
            "state_db": str(path.resolve()),
            **inspect_hermes_state_db(path),
        }
        for path in _hermes_state_db_paths()
    ]
    return diagnosis


def inspect_hermes_state_db(path: Path) -> dict[str, Any]:
    """Read aggregate Hermes session metrics without loading message bodies."""
    path = Path(path)
    if not path.is_file():
        return {"status": "unavailable", "reason": "missing"}
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        required = {"sessions", "messages"}
        if not required.issubset(tables):
            return {
                "status": "unavailable",
                "reason": "incompatible_schema",
                "tables": sorted(tables),
            }
        session_count = int(connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
        message_count = int(connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0])
        max_session_row = connection.execute(
            """SELECT id AS session_id, message_count, tool_call_count,
                      input_tokens, output_tokens, api_call_count
               FROM sessions
               ORDER BY message_count DESC, started_at DESC
               LIMIT 1"""
        ).fetchone()
        max_session = dict(max_session_row) if max_session_row is not None else None
        usage = {"input_tokens": 0, "output_tokens": 0, "api_call_count": 0}
        if "session_model_usage" in tables:
            usage_row = connection.execute(
                """SELECT COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(api_call_count), 0) AS api_call_count
                   FROM session_model_usage"""
            ).fetchone()
            usage = {key: int(usage_row[key] or 0) for key in usage}
        return {
            "status": "ok",
            "bytes": path.stat().st_size,
            "session_count": session_count,
            "message_count": message_count,
            "max_session": max_session,
            "usage": usage,
        }
    except (OSError, sqlite3.Error) as exc:
        return {"status": "unavailable", "reason": type(exc).__name__}
    finally:
        if connection is not None:
            connection.close()


def _hermes_state_db_paths() -> list[Path]:
    root = Path(os.environ.get("CAREER_HERMES_ROOT") or (ROOT.parent / "hermes"))
    if not root.is_dir():
        return []
    return sorted(
        path for path in root.glob("vagas_bot_*/state.db") if path.is_file()
    )


def _control_plane_snapshot() -> dict[str, Any]:
    configured_path = os.environ.get("CAREER_CONTROL_DB_PATH")
    path = Path(configured_path or (CAREER_STATE / "career.db")).expanduser().resolve()
    snapshot: dict[str, Any] = {
        "path": str(path),
        "configured": bool(configured_path),
        "exists": path.is_file(),
        "status": "missing" if not path.is_file() else "unavailable",
        "control_db_id": None,
        "schema_tables": [],
    }
    if not path.is_file():
        return snapshot
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        tables = sorted(
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        )
        snapshot["schema_tables"] = tables
        if "workspace_authority" not in tables:
            snapshot["status"] = "uninitialized"
            return snapshot
        authority = connection.execute(
            """SELECT control_db_id, storage_identity, authority_epoch
               FROM workspace_authority WHERE singleton_id = 1"""
        ).fetchone()
        if authority is None:
            snapshot["status"] = "invalid"
            return snapshot
        snapshot.update(
            {
                "status": "ready",
                "control_db_id": authority["control_db_id"],
                "storage_identity": authority["storage_identity"],
                "authority_epoch": authority["authority_epoch"],
            }
        )
        return snapshot
    except (OSError, sqlite3.Error) as exc:
        snapshot["reason"] = type(exc).__name__
        return snapshot
    finally:
        if connection is not None:
            connection.close()


def _runtime_observability_snapshot(control_plane: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(control_plane["path"]))
    result = {"worker_count": 0, "run_count": 0, "observation_count": 0}
    if not path.is_file() or control_plane.get("status") != "ready":
        return result
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for table, key in (
            ("runtime_workers", "worker_count"),
            ("runtime_runs", "run_count"),
            ("runtime_observations", "observation_count"),
        ):
            if table in tables:
                result[key] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return result
    except (OSError, sqlite3.Error):
        return result
    finally:
        if connection is not None:
            connection.close()


def local_strict_status() -> dict[str, Any]:
    package_json = ROOT / "package.json"
    scripts = read_json(package_json).get("scripts", {}) if package_json.exists() else {}
    required_scripts = [
        "fit-map:summary",
        "fit-map:draft-summary",
        "validate:fit-map:quality",
        "workflow:summary",
        "registry:summary",
        "derive:all-for-fit-map",
        "context:doctor",
        "context:validate-fit-map-request",
        "context:validate-cv-request",
        "notion:link-record",
        "notion:record-summary",
        "local:strict:status",
        "local:strict:doctor",
        "benchmark:local-agent",
    ]
    missing_scripts = [name for name in required_scripts if name not in scripts]
    return {
        "status": "blocked" if missing_scripts else "ok",
        "mode": "local_strict",
        "required_scripts": required_scripts,
        "missing_scripts": missing_scripts,
        "rules": [
            "use compact npm commands before ad hoc shell inspection",
            "prefer derived context artifacts and request validators before opening long references",
            "do not cat FIT_MAP, draft, Notion cache, ATS registry, or long references",
            "do not run broad grep/rg over inbox/notion, .career-state, outputs, or .agents",
            "answer with paths, counts, status, blockers, and next command",
        ],
    }


def local_strict_doctor() -> dict[str, Any]:
    status = local_strict_status()
    diagnosis = diagnose_runtime()
    large_files = [
        item for item in diagnosis.get("large_references", [])
        if int(item.get("bytes") or 0) > 250_000
    ]
    return {
        "status": status["status"],
        "local_strict": status,
        "runtime": {
            "workflow_state": diagnosis.get("workflow_state"),
            "large_references": large_files,
        },
        "recommended_agent_entrypoints": [
            "npm run agent:evaluate-notion -- <id>",
            "npm run derive:all-for-fit-map",
            "npm run context:validate-fit-map-request",
            "npm run fit-map:summary",
            "npm run validate:fit-map:quality",
            "npm run notion:link-record -- <id>",
        ],
    }


def local_agent_benchmark() -> dict[str, Any]:
    checks = [
        ("local_strict_status", local_strict_status()),
        ("workflow_summary_available", {"status": "ok"}),
        ("fit_map_summary", fit_map_service.payload_summary(CAREER_STATE / "fit_map.json")),
        ("draft_summary", fit_map_service.draft_summary(CAREER_STATE / "fit_map.draft.json")),
        ("fit_map_quality", fit_map_service.quality_report(CAREER_STATE / "fit_map.json")),
        ("registry_summary", fit_map_service.registry_summary()),
    ]
    failed = [
        {"check": name, "status": result.get("status"), "result": result}
        for name, result in checks
        if result.get("status") not in {"ok"}
    ]
    return {
        "status": "blocked" if failed else "ok",
        "checks": [
            {
                "name": name,
                "status": result.get("status"),
                "summary": {
                    key: result.get(key)
                    for key in ("path", "kind", "cargo", "empresa", "nota_final", "registered", "missing_scripts")
                    if key in result
                },
            }
            for name, result in checks
        ],
        "failed": failed,
    }


def hermes_runtime_snapshot() -> dict[str, Any]:
    hermes_home = Path.home() / ".hermes"
    config_path = hermes_home / "config.yaml"
    config = _read_simple_yaml(config_path) if config_path.exists() else {}
    raw_config = read_json(ROOT / ".career-state" / "applications_v2" / "config.json")
    harness = raw_config.get("harness", {}) if isinstance(raw_config.get("harness"), dict) else {}
    harness_fit_map = harness.get("fit_map", {}) if isinstance(harness.get("fit_map"), dict) else {}
    harness_approvals = harness.get("approvals", {}) if isinstance(harness.get("approvals"), dict) else {}
    applications_config = {
        **raw_config,
        "harness": {
            "fit_map": {
                "auto_finalize": bool(harness_fit_map.get("auto_finalize", True)),
            },
            "approvals": {
                "notion_write": str(harness_approvals.get("notion_write") or "explicit_request"),
                "email_draft": str(harness_approvals.get("email_draft") or "manual"),
            },
        },
    }
    main_model = _config_get(config, "model.default")
    main_provider = _config_get(config, "model.provider")
    main_base_url = _config_get(config, "model.base_url")
    toolsets = _config_get(config, "toolsets") or []
    direct_temperature = _find_temperature_value(config)
    project_model = applications_config.get("active_model")
    project_variant = applications_config.get("active_variant")
    temperature_policy = "provider_default"
    if isinstance(project_model, str):
        lowered = project_model.casefold()
        if "kimi" in lowered or "moonshot" in lowered:
            temperature_policy = "server_managed_omitted"
        elif "trinity-large-thinking" in lowered:
            temperature_policy = "fixed_0.5"
    return {
        "status": "ok",
        "hermes_home": str(hermes_home),
        "config_path": str(config_path),
        "project_runtime": {
            "active_model": project_model,
            "active_variant": project_variant,
            "analysis_runner": applications_config.get("analysis_runner"),
            "generation_runner": applications_config.get("generation_runner"),
            "harness": applications_config.get("harness"),
        },
        "hermes_config": {
            "model_default": main_model,
            "model_provider": main_provider,
            "model_base_url": main_base_url,
            "toolsets": toolsets,
            "reasoning_effort": _config_get(config, "agent.reasoning_effort"),
            "max_turns": _config_get(config, "agent.max_turns"),
            "streaming": _config_get(config, "display.streaming"),
            "show_reasoning": _config_get(config, "display.show_reasoning"),
            "temperature": direct_temperature,
            "temperature_source": "explicit_config" if direct_temperature is not None else "not_set_in_config",
            "temperature_policy_for_project_model": temperature_policy,
        },
    }


def _command_version(command: list[str | None]) -> str | None:
    if not command[0]:
        return None
    try:
        result = subprocess.run([str(part) for part in command], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else None


def _command_output(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or result.stderr).strip()
    return output or None


def _read_simple_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _config_get(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _find_temperature_value(payload: Any) -> Any:
    if isinstance(payload, dict):
        if "temperature" in payload:
            return payload["temperature"]
        for value in payload.values():
            found = _find_temperature_value(value)
            if found is not None:
                return found
        return None
    if isinstance(payload, list):
        for item in payload:
            found = _find_temperature_value(item)
            if found is not None:
                return found
    return None


def write_runtime_diagnosis(output_path: Path) -> Path:
    write_json(output_path, diagnose_runtime())
    return output_path


def artifact_fingerprint(path: Path) -> str | None:
    return sha256_file(path) if path.exists() else None


def text_fingerprint(text: str) -> str:
    return sha256_text(text)
