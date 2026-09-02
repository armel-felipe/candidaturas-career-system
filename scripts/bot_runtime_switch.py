#!/usr/bin/env python3
"""Switch the cellular agent runner for exactly one Hermes bot.

Hermes remains the Telegram gateway in both modes.  The switch only changes
the per-bot cellular runner configuration used by ``applications:run --run-agent``.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HOST_PROJECT_ROOT = "/opt/agent-projects/candidaturas"
CONTAINER_PROJECT_ROOT = "/workspace/candidaturas"
SUPPORTED_BOTS = ("vagas_bot_01", "vagas_bot_02")
SUPPORTED_MODES = ("hermes", "opencode")
ACTIVE_RUN_STATUSES = {"running", "reserved"}


class RuntimeModeError(RuntimeError):
    """A safe, actionable refusal to change a bot runtime mode."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _paths(project_root: Path, bot: str) -> tuple[Path, Path, Path]:
    bot_root = project_root / "workspaces" / bot / "state"
    return (
        bot_root / "applications_v2" / "config.json",
        bot_root / "runtime_mode.lock.json",
        bot_root / "runtime_mode.mutex",
    )


def _read_json(path: Path, *, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeModeError(f"invalid_json:{path}") from exc


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _runner_config(mode: str, bot: str) -> dict[str, Any]:
    common = {
        "agent": "build",
        "timeout_minutes": 90,
        "profile_name": bot,
        "working_dir": CONTAINER_PROJECT_ROOT,
    }
    if mode == "hermes":
        return {"kind": "hermes", "command": "hermes", **common}
    if mode == "opencode":
        return {
            "kind": "opencode",
            "command": "opencode",
            **common,
            "project_root": CONTAINER_PROJECT_ROOT,
            "host_project_root": HOST_PROJECT_ROOT,
        }
    raise RuntimeModeError(f"unsupported_mode:{mode}")


def _lock_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _active_cells(database_path: Path) -> list[dict[str, str]]:
    if not database_path.exists():
        return []
    try:
        connection = sqlite3.connect(database_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            active: list[dict[str, str]] = []
            if "application_runs" in tables:
                rows = connection.execute(
                    "SELECT run_id, application_id, status FROM application_runs "
                    "WHERE lower(status) IN (?, ?) ORDER BY run_id",
                    tuple(sorted(ACTIVE_RUN_STATUSES)),
                )
                active.extend(
                    {
                        "run_id": str(run_id),
                        "application_id": str(application_id),
                        "status": str(status),
                    }
                    for run_id, application_id, status in rows
                )
            if "cell_nodes" in tables:
                rows = connection.execute(
                    "SELECT run_id, node_id, status FROM cell_nodes "
                    "WHERE lower(status) IN (?, ?) ORDER BY run_id, node_id",
                    tuple(sorted(ACTIVE_RUN_STATUSES)),
                )
                active.extend(
                    {
                        "run_id": str(run_id),
                        "node_id": str(node_id),
                        "status": str(status),
                    }
                    for run_id, node_id, status in rows
                )
            return active
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise RuntimeModeError(f"control_db_unreadable:{database_path}") from exc


def _locked_mode(lock_path: Path) -> str | None:
    payload = _read_json(lock_path, default=None)
    if payload is None:
        return None
    if not isinstance(payload, dict) or payload.get("mode") not in SUPPORTED_MODES:
        raise RuntimeModeError("runtime_lock_invalid")
    return str(payload["mode"])


def status_bot_mode(project_root: Path, bot: str) -> dict[str, Any]:
    if bot not in SUPPORTED_BOTS:
        raise RuntimeModeError(f"unsupported_bot:{bot}")
    config_path, lock_path, _ = _paths(project_root, bot)
    config = _read_json(config_path, default={})
    if not isinstance(config, dict):
        raise RuntimeModeError(f"invalid_config:{config_path}")
    lock = _read_json(lock_path, default=None)
    runner = config.get("analysis_runner") or {}
    mode = str((lock or {}).get("mode") or runner.get("kind") or "unknown")
    return {
        "bot": bot,
        "mode": mode,
        "locked": lock is not None,
        "lock": lock,
        "config": str(config_path),
        "host_project_root": HOST_PROJECT_ROOT,
        "container_project_root": CONTAINER_PROJECT_ROOT,
    }


def unlock_bot_mode(
    project_root: Path,
    bot: str,
    *,
    control_db_path: Path | None = None,
) -> dict[str, Any]:
    if bot not in SUPPORTED_BOTS:
        raise RuntimeModeError(f"unsupported_bot:{bot}")
    config_path, lock_path, mutex_path = _paths(project_root, bot)
    mutex_path.parent.mkdir(parents=True, exist_ok=True)
    with mutex_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        lock = _read_json(lock_path, default=None)
        active = _active_cells(
            Path(control_db_path or project_root / "control-plane" / "career.db")
        )
        if active:
            raise RuntimeModeError(
                "active_cell_run:" + json.dumps(active, ensure_ascii=False, sort_keys=True)
            )
        if lock_path.exists():
            lock_path.unlink()
        config = _read_json(config_path, default={})
        if isinstance(config, dict) and isinstance(config.get("runtime_mode"), dict):
            config["runtime_mode"]["locked"] = False
            _write_json_atomic(config_path, config)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {"status": "unlocked", "bot": bot, "previous_lock": lock}


def switch_bot_mode(
    project_root: Path,
    bot: str,
    mode: str,
    *,
    control_db_path: Path | None = None,
    unlock: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    mode = mode.strip().lower()
    if bot not in SUPPORTED_BOTS:
        raise RuntimeModeError(f"unsupported_bot:{bot}")
    if mode not in SUPPORTED_MODES:
        raise RuntimeModeError(f"unsupported_mode:{mode}")

    config_path, lock_path, mutex_path = _paths(project_root, bot)
    if not config_path.is_file():
        raise RuntimeModeError(f"bot_config_missing:{config_path}")
    config = _read_json(config_path, default={})
    if not isinstance(config, dict):
        raise RuntimeModeError(f"invalid_config:{config_path}")

    mutex_path.parent.mkdir(parents=True, exist_ok=True)
    with mutex_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        current_mode = _locked_mode(lock_path)
        if current_mode == mode:
            result = status_bot_mode(project_root, bot)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return {**result, "status": "already_selected"}
        if current_mode is not None and not unlock:
            raise RuntimeModeError(
                f"runtime_mode_locked:bot={bot}:mode={current_mode}:use_unlock=true"
            )

        database_path = Path(control_db_path or project_root / "control-plane" / "career.db")
        active = _active_cells(database_path)
        if active:
            raise RuntimeModeError(
                "active_cell_run:" + json.dumps(active, ensure_ascii=False, sort_keys=True)
            )

        backup_path = config_path.parent / "runtime_mode.config.backup.json"
        if not backup_path.exists():
            _write_json_atomic(backup_path, config)

        runner = _runner_config(mode, bot)
        config["analysis_runner"] = dict(runner)
        config["generation_runner"] = dict(runner)
        config["runtime_mode"] = {
            "bot": bot,
            "mode": mode,
            "gateway": "hermes",
            "locked": True,
            "host_project_root": HOST_PROJECT_ROOT,
            "container_project_root": CONTAINER_PROJECT_ROOT,
            "env_file": str(project_root / ".env"),
            "changed_at": _now(),
        }
        _write_json_atomic(config_path, config)
        lock_payload = {
            "schema": "bot_runtime_mode_lock_v1",
            "bot": bot,
            "mode": mode,
            "gateway": "hermes",
            "owner": _lock_owner(),
            "locked_at": _now(),
            "host_project_root": HOST_PROJECT_ROOT,
            "container_project_root": CONTAINER_PROJECT_ROOT,
            "config_path": str(config_path),
        }
        _write_json_atomic(lock_path, lock_payload)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {"status": "switched", **lock_payload, "config": str(config_path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bot", choices=SUPPORTED_BOTS, required=True)
    parser.add_argument("--mode", choices=SUPPORTED_MODES)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--unlock", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path(HOST_PROJECT_ROOT))
    parser.add_argument("--control-db", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.status:
            result = status_bot_mode(args.project_root, args.bot)
        elif args.mode:
            result = switch_bot_mode(
                args.project_root,
                args.bot,
                args.mode,
                control_db_path=args.control_db,
                unlock=args.unlock,
            )
        elif args.unlock:
            result = unlock_bot_mode(
                args.project_root,
                args.bot,
                control_db_path=args.control_db,
            )
        else:
            raise RuntimeModeError("missing_action:use_mode_status_or_unlock")
    except RuntimeModeError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
