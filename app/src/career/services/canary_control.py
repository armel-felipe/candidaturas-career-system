from __future__ import annotations

import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


CANARY_BOT_NAME = "vagas_bot_01"
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
    control_db_path = Path(
        str(
            (service.get("environment") or {}).get("CAREER_CONTROL_DB_PATH")
            or env_map.get("CAREER_CONTROL_DB_PATH")
            or workspace_root / ".career-state" / "career.db"
        )
    ).resolve()
    authority_ledger_path = Path(
        str(
            env_map.get("CAREER_AUTHORITY_LEDGER_PATH")
            or control_db_path.with_name("authority.json")
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
            if expected_control_db_id and expected_control_db_id != db_check["control_db_id"]:
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
