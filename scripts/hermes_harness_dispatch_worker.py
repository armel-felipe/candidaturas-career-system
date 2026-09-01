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
from telegram_harness_adapter import process_message


def run_worker(dispatch_dir: Path) -> dict:
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
    lease = read_json(lease_path) if lease_path.is_file() else {}
    if str(status.get("status") or "") == "running":
        return _blocked(dispatch_dir, "dispatch_reentrancy")
    running = {
        "status": "running",
        "request_id": request.get("message_id"),
        "message_id": request.get("message_id"),
        "started_at": utc_now_iso(),
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
    payload = {
        "status": "blocked",
        "blocker_reason": reason,
        "completed_at": utc_now_iso(),
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
