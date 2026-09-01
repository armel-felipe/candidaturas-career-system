#!/usr/bin/env python3
"""Durable worker entrypoint for asynchronous HarnessSupervisor dispatch."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.utils import read_json, utc_now_iso, write_json
from telegram_harness_adapter import _dispatch_lock, _lease_alive, process_message


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
    if str(status.get("status") or "") in {"completed", "blocked"}:
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
        result = process_message(
            str(request.get("message") or ""),
            message_id=str(request.get("message_id") or ""),
            execute=True,
            runtime_context=request.get("runtime_context")
            if isinstance(request.get("runtime_context"), dict)
            else None,
            root=worker_root,
        )
        payload = result.get("result") if isinstance(result, dict) else {}
        final_status = str(payload.get("status") or result.get("status") or "completed")
        if final_status not in {"completed", "blocked", "awaiting_agent"}:
            final_status = "completed"
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
        }
        write_json(result_path, persisted)
        write_json(status_path, {key: value for key, value in persisted.items() if key != "result"})
        lease_path.unlink(missing_ok=True)
        return persisted
    except Exception as exc:
        return _blocked(
            dispatch_dir,
            "dispatch_worker_failed",
            error=f"{type(exc).__name__}: {exc}"[:500],
        )


def _blocked(dispatch_dir: Path, reason: str, **extra) -> dict:
    request = {}
    try:
        request = read_json(dispatch_dir / "request.json")
    except Exception:
        pass
    payload = {
        "status": "blocked",
        "blocker_reason": reason,
        "completed_at": utc_now_iso(),
        "decision": request.get("decision") or "block",
        "dispatch_action": request.get("dispatch_action") or "awaiting_agent",
        "next_state": "blocked",
        "scope": request.get("scope") or {},
        **extra,
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
    raise SystemExit(0 if result.get("status") in {"completed", "awaiting_agent"} else 1)
