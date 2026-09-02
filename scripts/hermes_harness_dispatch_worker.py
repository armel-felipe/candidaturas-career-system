#!/usr/bin/env python3
"""Durable worker entrypoint for asynchronous HarnessSupervisor dispatch."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.utils import read_json, utc_now_iso, write_json
from telegram_harness_adapter import _dispatch_lock, _lease_alive, process_message


_TERMINAL_WORKER_STATUSES = frozenset({"completed", "blocked", "awaiting_input"})


def run_worker(dispatch_dir: Path) -> dict:
    with _dispatch_lock(dispatch_dir):
        return _run_worker_locked(dispatch_dir)


def _run_worker_locked(dispatch_dir: Path) -> dict:
    request_path = dispatch_dir / "request.json"
    status_path = dispatch_dir / "status.json"
    result_path = dispatch_dir / "result.json"
    lease_path = dispatch_dir / "lease.json"
    if not request_path.is_file() or not status_path.is_file():
        return _blocked(
            dispatch_dir,
            "dispatch_request_missing",
            request_path=str(request_path),
        )
    request = read_json(request_path)
    status = read_json(status_path)
    if str(status.get("status") or "") in _TERMINAL_WORKER_STATUSES:
        return read_json(result_path) if result_path.is_file() else status
    if str(status.get("status") or "") == "running":
        return _blocked(dispatch_dir, "dispatch_reentrancy")
    if not lease_path.is_file():
        return _blocked(dispatch_dir, "dispatch_lease_missing")
    lease = read_json(lease_path)
    try:
        lease_pid = int(lease.get("pid") or 0)
    except (TypeError, ValueError):
        lease_pid = 0
    if lease_pid != os.getpid():
        return _blocked(
            dispatch_dir,
            "dispatch_lease_owner_mismatch",
            lease_pid=lease_pid,
            worker_pid=os.getpid(),
        )
    if not _lease_alive(lease):
        return _blocked(dispatch_dir, "dispatch_lease_expired")
    lease = {
        **lease,
        "owner": f"harness-worker-{os.getpid()}",
        "pid": os.getpid(),
        "state": "running",
        "claimed_at": utc_now_iso(),
    }
    write_json(lease_path, lease)
    running = {
        "status": "running",
        "request_id": request.get("message_id"),
        "message_id": request.get("message_id"),
        "started_at": utc_now_iso(),
        "decision": request.get("decision") or "block",
        "dispatch_action": request.get("dispatch_action") or "awaiting_agent",
        "next_state": "running",
        "scope": request.get("scope") or {},
    }
    write_json(status_path, running)
    try:
        worker_root = dispatch_dir.parent
        for parent in dispatch_dir.parents:
            if parent.name == ".career-state":
                worker_root = parent.parent
                break
        _load_project_dotenv(worker_root)
        result = process_message(
            str(request.get("message") or ""),
            message_id=str(request.get("message_id") or ""),
            execute=True,
            runtime_context=request.get("runtime_context")
            if isinstance(request.get("runtime_context"), dict)
            else None,
            root=worker_root,
        )
        payload = (
            result.get("result")
            if isinstance(result, dict) and isinstance(result.get("result"), dict)
            else {}
        )
        reported_status = payload.get("status") or (
            result.get("status") if isinstance(result, dict) else None
        )
        if not isinstance(reported_status, str) or not reported_status.strip():
            return _blocked(
                dispatch_dir,
                "dispatch_worker_invalid_status",
                observed_status=reported_status,
            )
        final_status = reported_status.strip()
        if final_status == "awaiting_agent" or final_status not in _TERMINAL_WORKER_STATUSES:
            return _blocked(
                dispatch_dir,
                "dispatch_worker_invalid_status",
                observed_status=final_status,
            )
        reply_text = result.get("reply_text") if isinstance(result, dict) else None
        delivery = {"status": "not_required"}
        if isinstance(reply_text, str) and reply_text.strip():
            try:
                delivery = _deliver_reply(reply_text.strip())
            except Exception as exc:
                delivery = {
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                }
        persisted = {
            "status": final_status,
            "request_id": request.get("message_id"),
            "message_id": request.get("message_id"),
            "completed_at": utc_now_iso(),
            "result": result,
            "decision": request.get("decision") or "block",
            "dispatch_action": request.get("dispatch_action") or "awaiting_agent",
            "next_state": final_status,
            "scope": request.get("scope") or {},
            "reply_text": reply_text.strip() if isinstance(reply_text, str) and reply_text.strip() else None,
            "delivery": delivery,
        }
        write_json(result_path, persisted)
        write_json(status_path, {key: value for key, value in persisted.items() if key != "result"})
        lease_path.unlink(missing_ok=True)
        return persisted
    except SystemExit as exc:
        return _blocked(
            dispatch_dir,
            "dispatch_worker_failed",
            deliver_reply=True,
            error_type=type(exc).__name__,
            error=str(exc)[:500] or f"worker exited with code {exc.code!r}",
        )
    except Exception as exc:
        return _blocked(
            dispatch_dir,
            "dispatch_worker_failed",
            deliver_reply=True,
            error_type=type(exc).__name__,
            error=f"{type(exc).__name__}: {exc}"[:500],
        )


def _deliver_reply(reply_text: str) -> dict:
    """Send a completed harness reply through the current Hermes profile."""
    if not reply_text or not reply_text.strip():
        return {"status": "not_required"}
    hermes_bin = Path(sys.executable).with_name("hermes")
    if hermes_bin.is_file():
        command = [str(hermes_bin)]
    else:
        hermes_on_path = shutil.which("hermes")
        command = [hermes_on_path] if hermes_on_path else [sys.executable, "-m", "hermes_cli.main"]
    command.extend(["send", "--to", "telegram", "--file", "-", "--quiet"])
    delivery_env = dict(os.environ)
    profile_name = str(delivery_env.get("CAREER_HERMES_PROFILE_NAME") or "").strip()
    hermes_home = Path(delivery_env.get("HERMES_HOME") or Path.home() / ".hermes")
    if profile_name and not (hermes_home.parent.name == "profiles" and hermes_home.name == profile_name):
        delivery_env["HERMES_HOME"] = str(hermes_home / "profiles" / profile_name)
    completed = subprocess.run(
        command,
        input=reply_text,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
        env=delivery_env,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown delivery error").strip()
        raise RuntimeError(f"Hermes Telegram delivery failed: {detail[:400]}")
    return {"status": "sent"}


def _load_project_dotenv(root: Path) -> None:
    """Load project credentials when the worker cwd is outside the workspace."""
    env_path = root / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def _blocked(dispatch_dir: Path, reason: str, *, deliver_reply: bool = False, **extra) -> dict:
    request = {}
    try:
        request = read_json(dispatch_dir / "request.json")
    except Exception:
        pass
    payload = {
        "status": "blocked",
        "request_id": request.get("message_id") or dispatch_dir.name,
        "message_id": request.get("message_id") or dispatch_dir.name,
        "blocker_reason": reason,
        "completed_at": utc_now_iso(),
        "decision": request.get("decision") or "block",
        "dispatch_action": request.get("dispatch_action") or "awaiting_agent",
        "next_state": "blocked",
        "scope": request.get("scope") or {},
        **extra,
    }
    if deliver_reply:
        error = str(payload.get("error") or "erro não especificado").strip()
        reply_text = (
            "Não foi possível concluir o processamento desta mensagem. "
            f"O worker foi bloqueado ({reason}): {error}"
        )
        payload["reply_text"] = reply_text
        try:
            payload["delivery"] = _deliver_reply(reply_text)
        except Exception as exc:
            payload["delivery"] = {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}"[:500],
            }
    write_json(dispatch_dir / "result.json", payload)
    write_json(dispatch_dir / "status.json", payload)
    (dispatch_dir / "lease.json").unlink(missing_ok=True)
    return payload


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatch-dir", required=True)
    args = parser.parse_args()
    result = run_worker(Path(args.dispatch_dir))
    raise SystemExit(0 if result.get("status") in {"completed", "awaiting_input", "awaiting_agent"} else 1)
