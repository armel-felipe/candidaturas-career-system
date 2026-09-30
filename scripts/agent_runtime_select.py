#!/usr/bin/env python3
"""Select one Telegram gateway runtime for the candidaturas project."""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


PROJECT = Path("/opt/agent-projects/candidaturas")
CONNECTOR_SERVICE = "opencode-telegram-connector.service"
HERMES_CONTAINER = "hermes-vagas-bot-01"
OPENCODE_URL = "http://127.0.0.1:4196"
DATABASE = PROJECT / "control-plane" / "career.db"
STATE_DIR = Path("/var/lib/candidaturas-runtime")
MODE_FILE = STATE_DIR / "mode"
STARTED_FILE = STATE_DIR / "started_at"
LOCK_FILE = Path("/run/lock/candidaturas-runtime.lock")


class RuntimeErrorSafe(RuntimeError):
    pass


def _command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeErrorSafe(f"command_failed:{args[0]}") from exc
    if check and result.returncode:
        raise RuntimeErrorSafe(f"command_failed:{args[0]}:exit={result.returncode}")
    return result


def _unit_active(unit: str) -> bool:
    return _command(["systemctl", "is-active", "--quiet", unit], check=False).returncode == 0


def _hermes_active() -> bool:
    result = _command(["docker", "inspect", "-f", "{{.State.Running}}", HERMES_CONTAINER], check=False)
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _mode() -> str | None:
    try:
        value = MODE_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    if value not in {"hermes", "opencode"}:
        raise RuntimeErrorSafe("runtime_mode_state_invalid")
    return value


def _started_at() -> datetime:
    try:
        return datetime.fromisoformat(STARTED_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        # Without an activation timestamp, every persisted active row is treated
        # as live until an operator establishes a known runtime state.
        return datetime.min.replace(tzinfo=timezone.utc)


def _write_state(mode: str) -> None:
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    for target, value in ((MODE_FILE, mode + "\n"), (STARTED_FILE, now + "\n")):
        fd, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=STATE_DIR)
        tmp = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)


def _active_project_sessions() -> list[str]:
    query = urlencode({"directory": str(PROJECT)})
    try:
        with urlopen(f"{OPENCODE_URL}/session/status?{query}", timeout=4) as response:
            payload = json.loads(response.read(1_000_000))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeErrorSafe("opencode_session_status_unavailable; refusing runtime switch") from exc
    if not isinstance(payload, dict):
        raise RuntimeErrorSafe("opencode_session_status_invalid; refusing runtime switch")
    return [str(session_id) for session_id, status in payload.items()
            if not isinstance(status, dict) or status.get("type") != "idle"]


def _active_cell_runs() -> dict[str, int]:
    if not DATABASE.is_file():
        raise RuntimeErrorSafe(f"control_database_missing:{DATABASE}")
    try:
        db = sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        since = _started_at().astimezone(timezone.utc).isoformat()
        active = {"application_runs": 0, "cell_nodes": 0}
        if "application_runs" in tables:
            active["application_runs"] = db.execute(
                "SELECT count(*) FROM application_runs "
                "WHERE lower(status) IN ('running','reserved') AND updated_at >= ?",
                (since,),
            ).fetchone()[0]
        if "cell_nodes" in tables:
            active["cell_nodes"] = db.execute(
                "SELECT count(*) FROM cell_nodes "
                "WHERE lower(status) IN ('running','reserved') "
                "AND (updated_at >= ? OR (reservation_expires_at IS NOT NULL AND reservation_expires_at > ?))",
                (since, datetime.now(timezone.utc).isoformat()),
            ).fetchone()[0]
        db.close()
        return active
    except sqlite3.Error as exc:
        raise RuntimeErrorSafe("control_database_unreadable; refusing runtime switch") from exc


def _assert_no_active_work(*, current_mode: str | None) -> None:
    runs = _active_cell_runs()
    if any(runs.values()):
        raise RuntimeErrorSafe(f"active_cell_runs:{runs}; refusing runtime switch")
    if current_mode == "opencode" and _unit_active(CONNECTOR_SERVICE):
        sessions = _active_project_sessions()
        if sessions:
            raise RuntimeErrorSafe(f"active_opencode_sessions:{len(sessions)}; refusing runtime switch")
    if current_mode == "hermes" and _hermes_active():
        recent = _command(["docker", "logs", "--since", "2m", HERMES_CONTAINER], check=False)
        if recent.returncode:
            raise RuntimeErrorSafe("hermes_recent_activity_unavailable; refusing runtime switch")
        if recent.stdout or recent.stderr:
            raise RuntimeErrorSafe("recent_hermes_activity; wait until the current turn finishes")


def _opencode_healthy() -> bool:
    try:
        with urlopen(f"{OPENCODE_URL}/global/health", timeout=4) as response:
            payload = json.loads(response.read(64_000))
        return isinstance(payload, dict) and payload.get("healthy") is True
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return False


def _stop_hermes() -> None:
    if not _hermes_active():
        return
    _command(["docker", "update", "--restart=no", HERMES_CONTAINER])
    _command(["docker", "stop", "--time", "30", HERMES_CONTAINER])
    if _hermes_active():
        raise RuntimeErrorSafe("hermes_gateway_did_not_stop")


def _start_hermes() -> None:
    _command(["docker", "update", "--restart=unless-stopped", HERMES_CONTAINER], check=False)
    _command(["docker", "compose", "-f", str(PROJECT / "compose.yaml"), "up", "-d", "vagas_bot_01"])
    if not _hermes_active():
        raise RuntimeErrorSafe("hermes_gateway_did_not_start")


def status() -> int:
    hermes = _hermes_active()
    opencode = _unit_active(CONNECTOR_SERVICE)
    selected = _mode() or "unknown"
    print(f"selected={selected}")
    print(f"vagas_bot_01_hermes={'active' if hermes else 'inactive'}")
    print(f"vagas_bot_02_opencode={'active' if opencode else 'inactive'}")
    if opencode:
        print(f"opencode_server={'healthy' if _opencode_healthy() else 'unhealthy'}")
    if hermes and opencode:
        print("status=conflict: both Telegram gateways are active")
        return 2
    if opencode and not _opencode_healthy():
        print("status=connector_active_but_server_unhealthy")
        return 2
    if selected == "unknown" or (selected == "hermes") != hermes or (selected == "opencode") != opencode:
        print("status=observed_services_do_not_match_saved_mode")
        return 2
    print("status=ok")
    return 0


def select(mode: str, *, restore: bool = False) -> int:
    if mode not in {"hermes", "opencode"}:
        raise RuntimeErrorSafe("usage: candidaturas-runtime select hermes|opencode")
    current = _mode()
    if current == mode and ((_hermes_active() and not _unit_active(CONNECTOR_SERVICE))
                            if mode == "hermes" else (_unit_active(CONNECTOR_SERVICE) and not _hermes_active())):
        print(f"already_selected={mode}")
        return 0
    _assert_no_active_work(current_mode=current)

    if mode == "opencode":
        _stop_hermes()
        try:
            _command(["systemctl", "start", CONNECTOR_SERVICE])
            for _ in range(20):
                if _unit_active(CONNECTOR_SERVICE) and _opencode_healthy():
                    if _hermes_active():
                        raise RuntimeErrorSafe("both_gateways_active_after_opencode_start")
                    _write_state("opencode")
                    print("selected=opencode")
                    return 0
                time.sleep(1)
            raise RuntimeErrorSafe("opencode_connector_or_server_unhealthy")
        except Exception:
            _command(["systemctl", "stop", CONNECTOR_SERVICE], check=False)
            _start_hermes()
            _write_state("hermes")
            raise

    _command(["systemctl", "stop", CONNECTOR_SERVICE], check=False)
    if _unit_active(CONNECTOR_SERVICE):
        raise RuntimeErrorSafe("opencode_connector_did_not_stop; Hermes was not started")
    _start_hermes()
    _write_state("hermes")
    print("selected=hermes")
    return 0


def shutdown() -> int:
    _command(["systemctl", "stop", CONNECTOR_SERVICE], check=False)
    _stop_hermes()
    print("runtime_gateways_stopped")
    return 0


def main(argv: list[str]) -> int:
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    LOCK_FILE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with LOCK_FILE.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if argv == ["status"]:
            return status()
        if argv == ["restore"]:
            restored_mode = _mode() or "hermes"
            # A systemd restore runs after boot, when no pre-reboot agent turn
            # can still be executing. Rebase stale database statuses to this
            # gateway generation before restoring its selected mode.
            _write_state(restored_mode)
            return select(restored_mode, restore=True)
        if argv == ["shutdown"]:
            return shutdown()
        if len(argv) == 2 and argv[0] == "select":
            return select(argv[1])
    raise RuntimeErrorSafe("usage: candidaturas-runtime status|select hermes|select opencode|restore|shutdown")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except RuntimeErrorSafe as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
