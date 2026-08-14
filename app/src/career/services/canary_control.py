from __future__ import annotations

import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

import yaml

from career.services.agent_runner import AgentRunRequest, SubprocessAgentRunner
from career.services.harness_supervisor import HarnessSupervisor


CANARY_BOT_NAME = "vagas_bot_01"
RUNNER_GATE_MANIFEST_RELATIVE_PATH = Path(".career-state/phase_d_runner_gate.json")
REQUIRED_WORKSPACE_MOUNTS = (
    "/workspace/candidaturas/.career-state",
    "/workspace/candidaturas/inbox",
    "/workspace/candidaturas/outputs",
)


@dataclass(frozen=True)
class CanaryTarget:
    bot_name: str
    compose_service: str
    hermes_config: Path
    adapter_script: Path
    control_db_path: Path
    authority_ledger_path: Path
    workspace_root: Path
    compose_path: Path


def assert_canary_target(target: CanaryTarget) -> None:
    if str(target.bot_name).strip() != CANARY_BOT_NAME:
        raise ValueError(f"phase D canary target must be {CANARY_BOT_NAME}")
    if str(target.compose_service).strip() != CANARY_BOT_NAME:
        raise ValueError(f"phase D compose service must be {CANARY_BOT_NAME}")


def resolve_target_from_compose(
    *, compose_path: str | Path, bot_name: str, env: dict[str, str] | None = None
) -> CanaryTarget:
    env_map = dict(os.environ)
    if env:
        env_map.update(env)
    compose_file = Path(compose_path).resolve()
    compose = _load_compose(compose_file)
    service = _service_from_compose(compose, bot_name)
    volumes = service.get("volumes") or []
    workspace_root = _find_volume_source(volumes, "/workspace/candidaturas")
    if workspace_root is None:
        workspace_root = compose_file.parent
    workspace_root = workspace_root.resolve()
    state_root = _find_volume_source(volumes, "/workspace/candidaturas/.career-state")
    if state_root is None:
        state_root = workspace_root / ".career-state"
    state_root = state_root.resolve()
    control_db_path = Path(
        str(
            (service.get("environment") or {}).get("CAREER_CONTROL_DB_PATH")
            or env_map.get("CAREER_CONTROL_DB_PATH")
            or state_root / "career.db"
        )
    ).resolve()
    authority_ledger_path = Path(
        str(
            (service.get("environment") or {}).get("CAREER_AUTHORITY_LEDGER_PATH")
            or env_map.get("CAREER_AUTHORITY_LEDGER_PATH")
            or state_root / "authority.json"
        )
    ).resolve()
    adapter_script = (workspace_root / "scripts" / "telegram_harness_adapter.py").resolve()
    profile_mount = _find_profile_mount(volumes, bot_name)
    hermes_config = (
        profile_mount / "hermes.config.json" if profile_mount is not None else workspace_root / "missing.json"
    ).resolve()
    return CanaryTarget(
        bot_name=bot_name,
        compose_service=bot_name,
        hermes_config=hermes_config,
        adapter_script=adapter_script,
        control_db_path=control_db_path,
        authority_ledger_path=authority_ledger_path,
        workspace_root=workspace_root,
        compose_path=compose_file,
    )


def run_preflight(
    target: CanaryTarget, compose_path: str | Path, env: dict[str, str] | None = None
) -> dict[str, Any]:
    assert_canary_target(target)
    env_map = dict(os.environ)
    if env:
        env_map.update(env)
    compose_file = Path(compose_path).resolve()
    report: dict[str, Any] = {
        "status": "ready",
        "target": target.bot_name,
        "checks": [],
        "mutations": [],
    }
    blocked = False
    compose = _load_compose(compose_file)
    services = compose.get("services") or {}
    service = services.get(target.compose_service)
    if service is None:
        _append_check(report, "compose_service", "blocked", reason=f"service {target.compose_service} not found")
        report["status"] = "blocked"
        return report
    _append_check(report, "compose_service", "ok")

    hermes_home = str((service.get("environment") or {}).get("HERMES_HOME") or "").strip()
    if hermes_home:
        _append_check(report, "hermes_home", "ok", path=hermes_home)
    else:
        blocked = True
        _append_check(report, "hermes_home", "blocked", reason="HERMES_HOME is missing")

    volumes = service.get("volumes") or []
    missing_mounts = [mount for mount in REQUIRED_WORKSPACE_MOUNTS if _find_volume_source(volumes, mount) is None]
    if missing_mounts:
        blocked = True
        _append_check(report, "workspace_mounts", "blocked", reason="missing required workspace mounts", mounts=missing_mounts)
    else:
        _append_check(report, "workspace_mounts", "ok")

    blocked = _check_path(report, "adapter_script", target.adapter_script, blocked)
    blocked = _check_path(report, "hermes_config", target.hermes_config, blocked)
    blocked = _check_path(report, "control_plane_sqlite", target.control_db_path, blocked)
    blocked = _check_path(report, "authority_ledger", target.authority_ledger_path, blocked)

    runner_bin = str(env_map.get("PHASE_D_RUNNER_BIN") or env_map.get("PYTHON_BIN") or "python3")
    if shutil.which(runner_bin):
        _append_check(report, "runner_bin", "ok", runner=runner_bin)
    else:
        blocked = True
        _append_check(report, "runner_bin", "blocked", reason=f"runner not available: {runner_bin}")

    if target.control_db_path.is_file():
        db_check = _inspect_control_db(target.control_db_path)
        report["control_db"] = db_check
        if db_check["status"] != "ok":
            blocked = True
            _append_check(report, "control_plane_sqlite", "blocked", reason=db_check["reason"])
        else:
            _replace_check(report, "control_plane_sqlite", {"name": "control_plane_sqlite", "status": "ok"})
            expected_control_db_id = str(env_map.get("CAREER_CONTROL_DB_ID") or "").strip()
            if not expected_control_db_id:
                blocked = True
                _append_check(
                    report,
                    "control_db_identity",
                    "blocked",
                    reason="CAREER_CONTROL_DB_ID is required for D0 preflight",
                )
            elif expected_control_db_id != db_check["control_db_id"]:
                blocked = True
                _append_check(report, "control_db_identity", "blocked", reason="CAREER_CONTROL_DB_ID does not match authoritative database")
            else:
                _append_check(report, "control_db_identity", "ok")
            ledger_check = _inspect_ledger(target.authority_ledger_path, db_check)
            if ledger_check["status"] != "ok":
                blocked = True
                _replace_check(
                    report,
                    "authority_ledger",
                    {"name": "authority_ledger", "status": "blocked", "reason": ledger_check["reason"]},
                )
            else:
                report["control_db"]["ledger_id"] = ledger_check["ledger_id"]
                report["control_db"]["authority_epoch"] = ledger_check["authority_epoch"]
                _replace_check(report, "authority_ledger", {"name": "authority_ledger", "status": "ok"})

    report["status"] = "blocked" if blocked else "ready"
    return report


def stage_hook(target: CanaryTarget, apply: bool) -> dict[str, Any]:
    _assert_canary_hook_target(target)
    import install_hermes_harness_hook

    result = install_hermes_harness_hook.install(target.hermes_config, apply=apply)
    staged = {
        **result,
        "target": target.bot_name,
        "apply": apply,
        "mutations": _hook_mutations(target, result),
    }
    return staged


def rollback_dry_run(target: CanaryTarget) -> dict[str, Any]:
    _assert_canary_hook_target(target)
    backup = target.hermes_config.with_suffix(target.hermes_config.suffix + ".bak.harness")
    return {
        "status": "dry_run_ok",
        "target": target.bot_name,
        "apply": False,
        "config": str(target.hermes_config),
        "backup": str(backup),
        "revertible": backup.exists(),
        "mutations": [],
    }


def route_smoke(
    root: Path,
    messages: list[dict[str, Any]],
    *,
    execute: bool = False,
    supervisor: Any | None = None,
) -> list[dict[str, Any]]:
    import telegram_harness_adapter

    smoke_root = Path(root).resolve()
    smoke_root.mkdir(parents=True, exist_ok=True)
    smoke_supervisor = supervisor or _RouteSmokeSupervisor()
    results: list[dict[str, Any]] = []
    for entry in messages:
        results.append(
            telegram_harness_adapter.process_message(
                str(entry["message"]),
                message_id=str(entry["message_id"]),
                execute=execute,
                supervisor=smoke_supervisor,
                root=smoke_root,
            )
        )
    return results


def probe_runner(
    runner_config: dict[str, Any],
    root: Path,
    gate_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    config = dict(runner_config or {})
    runner = SubprocessAgentRunner(root_path)
    gate_context = _load_runner_gate_context(root_path, gate_manifest_path=gate_manifest_path)
    request_context = gate_context.get("request_context") if gate_context.get("status") == "ok" else None
    request_md = (
        request_context["request_md"]
        if request_context is not None
        else (root_path / ".career-state" / "runner_probe" / "request.md")
    )
    command = runner.build_command(
        AgentRunRequest(
            stage="analyze",
            record_key=(
                str(request_context["application_id"])
                if request_context is not None
                else CANARY_BOT_NAME
            ),
            request_path=request_md,
            instruction="Runner probe only; do not resume prior sessions.",
            runner_config=config,
        )
    )
    runner_type = str(config.get("kind") or config.get("command") or Path(command[0]).name).casefold()
    resolved = shutil.which(str(config.get("command") or command[0]))
    if not resolved:
        return {
            "status": "blocked",
            "command": command,
            "type": runner_type,
            "available": False,
            "returncode": 127,
            "blocker": "runner_unavailable",
        }
    command = [resolved, *command[1:]]
    if gate_context.get("status") != "ok":
        return {
            "status": "blocked",
            "command": command,
            "type": runner_type,
            "available": True,
            "returncode": None,
            "blocker": str(gate_context.get("blocker") or "d3_gate_manifest_missing"),
        }
    payload = HarnessSupervisor(root_path).run_application_stage(
        stage="analyze",
        record_key=str(request_context["application_id"]),
        application_dir=Path(request_context["application_dir"]),
        request_json=Path(request_context["request_json"]),
        request_md=Path(request_context["request_md"]),
        runner_config=config,
        workspace_owner=str(os.environ.get("CAREER_WORKSPACE_OWNER") or ""),
        control_db_id=str(os.environ.get("CAREER_CONTROL_DB_ID") or ""),
    )
    blocker = None
    status = "completed"
    returncode = int(payload.get("returncode", 0))
    if returncode != 0:
        status = "blocked"
        blocker = str(payload.get("blocker_reason") or "runner_failed")
    elif (payload.get("isolation") or {}).get("status") != "ok":
        status = "blocked"
        blocker = "runner_isolation_blocked"
    return {
        "status": status,
        "command": list(payload.get("command") or command),
        "type": runner_type,
        "available": True,
        "returncode": returncode,
        "blocker": blocker,
    }


def _append_check(report: dict[str, Any], name: str, status: str, **extra: Any) -> None:
    report["checks"].append({"name": name, "status": status, **extra})


def _replace_check(report: dict[str, Any], name: str, replacement: dict[str, Any]) -> None:
    for index, check in enumerate(report["checks"]):
        if check["name"] == name:
            report["checks"][index] = replacement
            return
    report["checks"].append(replacement)


def _check_path(report: dict[str, Any], name: str, path: Path, blocked: bool) -> bool:
    if path.is_file():
        _append_check(report, name, "ok", path=str(path))
        return blocked
    _append_check(report, name, "blocked", reason=f"missing file: {path}")
    return True


def _load_runner_gate_context(
    root: Path,
    *,
    gate_manifest_path: str | Path | None,
) -> dict[str, Any]:
    manifest_path = (
        _resolve_under_root(root, gate_manifest_path)
        if gate_manifest_path is not None
        else (root / RUNNER_GATE_MANIFEST_RELATIVE_PATH).resolve()
    )
    if not manifest_path.is_file():
        return {"status": "blocked", "blocker": "d3_gate_manifest_missing"}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "blocked", "blocker": "d3_gate_manifest_invalid"}
    if not isinstance(payload, dict):
        return {"status": "blocked", "blocker": "d3_gate_manifest_invalid"}
    if str(payload.get("target") or "").strip() != CANARY_BOT_NAME:
        return {"status": "blocked", "blocker": "d3_gate_target_mismatch"}
    approvals = payload.get("approvals")
    if not isinstance(approvals, dict):
        return {"status": "blocked", "blocker": "d3_approvals_missing"}
    for stage_name in ("d0", "d1", "d2"):
        stage_payload = approvals.get(stage_name)
        if not isinstance(stage_payload, dict) or stage_payload.get("approved") is not True:
            return {"status": "blocked", "blocker": "d3_approvals_missing"}
    request_context = _validate_runner_gate_request(root, approvals["d2"])
    if request_context.get("status") != "ok":
        return request_context
    return {"status": "ok", "request_context": request_context["request_context"]}


def _validate_runner_gate_request(root: Path, d2_payload: dict[str, Any]) -> dict[str, Any]:
    required_text_fields = (
        "application_id",
        "run_id",
        "node_id",
        "request_json",
        "request_md",
        "request_hash",
    )
    if any(not str(d2_payload.get(field) or "").strip() for field in required_text_fields):
        return {"status": "blocked", "blocker": "d2_request_incomplete"}
    if not isinstance(d2_payload.get("attempt"), int) or int(d2_payload["attempt"]) <= 0:
        return {"status": "blocked", "blocker": "d2_request_incomplete"}
    read_allowlist = d2_payload.get("read_allowlist")
    write_allowlist = d2_payload.get("write_allowlist")
    if not isinstance(read_allowlist, list) or not read_allowlist:
        return {"status": "blocked", "blocker": "d2_request_incomplete"}
    if not isinstance(write_allowlist, list) or not write_allowlist:
        return {"status": "blocked", "blocker": "d2_request_incomplete"}
    request_json = _resolve_under_root(root, str(d2_payload["request_json"]))
    request_md = _resolve_under_root(root, str(d2_payload["request_md"]))
    if not request_json.is_file() or not request_md.is_file():
        return {"status": "blocked", "blocker": "d2_request_missing"}
    try:
        payload = json.loads(request_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "blocked", "blocker": "d2_request_missing"}
    if payload.get("cellular") is not True:
        return {"status": "blocked", "blocker": "d2_request_mismatch"}
    expected_application = str(d2_payload["application_id"])
    expected_dir = (root / ".career-state" / "applications_v2" / expected_application).resolve()
    if request_json.parents[5] != expected_dir:
        return {"status": "blocked", "blocker": "d2_request_mismatch"}
    if request_md != request_json.with_suffix(".md"):
        return {"status": "blocked", "blocker": "d2_request_mismatch"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    expected_read = [str(item).strip() for item in read_allowlist]
    expected_write = [str(item).strip() for item in write_allowlist]
    if any(not item for item in (*expected_read, *expected_write)):
        return {"status": "blocked", "blocker": "d2_request_incomplete"}
    checks = {
        "application_id": expected_application,
        "run_id": str(d2_payload["run_id"]),
        "node_id": str(d2_payload["node_id"]),
        "attempt": int(d2_payload["attempt"]),
        "read_allowlist": expected_read,
        "write_allowlist": expected_write,
    }
    for key, expected in checks.items():
        if payload.get(key) != expected:
            return {"status": "blocked", "blocker": "d2_request_mismatch"}
    if request_hash != str(d2_payload["request_hash"]):
        return {"status": "blocked", "blocker": "d2_request_mismatch"}
    return {
        "status": "ok",
        "request_context": {
            "application_id": expected_application,
            "request_json": request_json,
            "request_md": request_md,
            "application_dir": expected_dir,
            "request_hash": request_hash,
            "read_allowlist": expected_read,
            "write_allowlist": expected_write,
        },
    }


def _resolve_under_root(root: Path, raw_path: str | Path) -> Path:
    candidate = Path(raw_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("runner gate path escapes workspace root")
    return resolved


def _load_compose(compose_path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("compose file must deserialize to a mapping")
    return payload


def _service_from_compose(compose: dict[str, Any], service_name: str) -> dict[str, Any]:
    services = compose.get("services") or {}
    service = services.get(service_name)
    if not isinstance(service, dict):
        raise ValueError(f"service {service_name} not found in compose")
    return service


def _find_volume_source(volumes: list[Any], destination: str) -> Path | None:
    for volume in volumes:
        if not isinstance(volume, str):
            continue
        parts = volume.split(":")
        if len(parts) >= 2 and parts[1] == destination:
            return Path(parts[0])
    return None


def _find_profile_mount(volumes: list[Any], bot_name: str) -> Path | None:
    expected_destination = f"/opt/data/profiles/{bot_name}"
    return _find_volume_source(volumes, expected_destination)


def _assert_canary_hook_target(target: CanaryTarget) -> None:
    assert_canary_target(target)
    if target.hermes_config.name != "hermes.config.json":
        raise ValueError("phase D hook staging requires hermes.config.json")
    resolved = resolve_target_from_compose(compose_path=target.compose_path, bot_name=target.bot_name)
    compared_paths = {
        "compose-resolved profile path": (target.hermes_config.resolve(), resolved.hermes_config.resolve()),
        "compose-resolved adapter path": (target.adapter_script.resolve(), resolved.adapter_script.resolve()),
        "compose-resolved workspace root": (target.workspace_root.resolve(), resolved.workspace_root.resolve()),
        "compose-resolved control db path": (target.control_db_path.resolve(), resolved.control_db_path.resolve()),
        "compose-resolved authority ledger path": (
            target.authority_ledger_path.resolve(),
            resolved.authority_ledger_path.resolve(),
        ),
    }
    for label, (actual, expected) in compared_paths.items():
        if actual != expected:
            raise ValueError(f"{label} mismatch for {CANARY_BOT_NAME}: expected {expected}, got {actual}")


def _hook_mutations(target: CanaryTarget, result: dict[str, Any]) -> list[dict[str, str]]:
    if not result.get("apply") or result.get("status") != "installed":
        return []
    backup = target.hermes_config.with_suffix(target.hermes_config.suffix + ".bak.harness")
    return [
        {"kind": "backup_config", "path": str(backup)},
        {"kind": "write_config", "path": str(target.hermes_config)},
        {
            "kind": "install_plugin",
            "path": str(target.hermes_config.parent / "plugins" / "career-harness-output"),
        },
    ]


class _RouteSmokeSupervisor:
    def handle_message(self, message: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "status": "completed",
            "result": {
                "display_text": f"route-only ok: {message}",
                "channel": kwargs.get("channel"),
                "execute": kwargs.get("execute"),
            },
        }


def _inspect_control_db(control_db_path: Path) -> dict[str, Any]:
    try:
        connection = sqlite3.connect(f"file:{control_db_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """SELECT control_db_id, storage_identity, authority_ledger_id, authority_epoch
               FROM workspace_authority WHERE singleton_id = 1"""
        ).fetchone()
    except sqlite3.Error as exc:
        return {"status": "blocked", "reason": f"unable to read authoritative control database: {exc}"}
    finally:
        try:
            connection.close()
        except Exception:
            pass
    if row is None or not row["control_db_id"]:
        return {"status": "blocked", "reason": "workspace authority row is missing"}
    return {
        "status": "ok",
        "control_db_id": str(row["control_db_id"]),
        "storage_identity": str(row["storage_identity"] or ""),
        "authority_ledger_id": str(row["authority_ledger_id"] or ""),
        "authority_epoch": int(row["authority_epoch"] or 0),
        "read_only": True,
    }


def _inspect_ledger(ledger_path: Path, db_check: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "blocked", "reason": f"unable to read authority ledger: {exc}"}
    if not isinstance(payload, dict):
        return {"status": "blocked", "reason": "authority ledger is invalid"}
    if str(payload.get("control_db_id") or "") != str(db_check["control_db_id"]):
        return {"status": "blocked", "reason": "shared authority ledger control database mismatch"}
    ledger_id = str(payload.get("ledger_id") or "")
    if not ledger_id.startswith("ledger_"):
        return {"status": "blocked", "reason": "shared authority ledger provenance is invalid"}
    if str(payload.get("storage_identity") or "") != str(db_check["storage_identity"]):
        return {"status": "blocked", "reason": "shared authority ledger designates another physical control database copy"}
    return {
        "status": "ok",
        "ledger_id": ledger_id,
        "authority_epoch": int(payload.get("authority_epoch") or 0),
    }
