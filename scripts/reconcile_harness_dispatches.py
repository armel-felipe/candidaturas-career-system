#!/usr/bin/env python3
"""Reconcile stale asynchronous Harness dispatch mirrors safely.

The SQLite command store remains authoritative.  This utility only closes old
JSON dispatch envelopes that no longer have a live lease and preserves their
directories and historical payloads.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.utils import read_json, utc_now_iso, write_json
from career.services.application_context import canonical_database
from career.services.harness_command_store import HarnessCommandStore


def _timestamp(value: Any, fallback: datetime) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return fallback


def _lease_is_live(path: Path, *, now: datetime) -> bool:
    if not path.is_file():
        return False
    try:
        lease = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    expires_at = lease.get("expires_at") if isinstance(lease, dict) else None
    if not expires_at:
        return False
    return _timestamp(expires_at, now - timedelta(seconds=1)) > now


def reconcile_dispatches(
    dispatch_root: Path,
    *,
    older_than_seconds: int = 300,
    dry_run: bool = True,
    now: datetime | None = None,
    command_status: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """Reconcile stale ``running`` status mirrors below ``dispatch_root``."""
    if older_than_seconds <= 0:
        raise ValueError("older_than_seconds must be positive")
    current_time = now or datetime.now(UTC)
    cutoff = current_time - timedelta(seconds=older_than_seconds)
    report: dict[str, Any] = {
        "dispatch_root": str(dispatch_root),
        "dry_run": dry_run,
        "older_than_seconds": older_than_seconds,
        "candidates": [],
        "reconciled": 0,
        "skipped_live": 0,
        "skipped_active": 0,
        "skipped_recent": 0,
    }
    if not dispatch_root.exists():
        return report

    for status_path in sorted(dispatch_root.glob("*/status.json")):
        dispatch_dir = status_path.parent
        try:
            status = read_json(status_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(status, dict) or status.get("status") != "running":
            continue
        request_path = dispatch_dir / "request.json"
        try:
            request = read_json(request_path) if request_path.is_file() else {}
        except (OSError, ValueError, json.JSONDecodeError):
            request = {}
        started_at = _timestamp(
            status.get("started_at") or request.get("created_at"),
            datetime.fromtimestamp(status_path.stat().st_mtime, UTC),
        )
        if started_at > cutoff:
            report["skipped_recent"] += 1
            continue
        if _lease_is_live(dispatch_dir / "lease.json", now=current_time):
            report["skipped_live"] += 1
            continue
        command_id = str(request.get("command_id") or "").strip()
        current_command_status = command_status(command_id) if command_id and command_status else None
        if current_command_status in {"queued", "running"}:
            report["skipped_active"] += 1
            continue

        scope = status.get("scope") if isinstance(status.get("scope"), dict) else {}
        candidate = {
            "dispatch_id": dispatch_dir.name,
            "age_seconds": max(0, int((current_time - started_at).total_seconds())),
            "profile_id": scope.get("profile_id"),
            "application_id": scope.get("application_id"),
            "command_id": command_id or None,
            "command_status": current_command_status,
            "action": "mark_blocked_dispatch_orphaned",
        }
        report["candidates"].append(candidate)
        if dry_run:
            continue
        finished = {
            **status,
            "status": "blocked",
            "next_state": "blocked",
            "blocker_reason": "dispatch_orphaned",
            "completed_at": utc_now_iso(),
            "reconciled_at": utc_now_iso(),
        }
        result_path = dispatch_dir / "result.json"
        if not result_path.exists():
            write_json(result_path, finished)
        write_json(status_path, finished)
        report["reconciled"] += 1
    return report


def _profile_dispatch_root(profile: str) -> Path:
    return ROOT / "workspaces" / profile / "state" / "harness" / "dispatches"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("vagas_bot_01", "vagas_bot_02"), required=True)
    parser.add_argument("--older-than-seconds", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    database = canonical_database(root=ROOT)
    try:
        command_store = HarnessCommandStore(database)

        def command_status(command_id: str) -> str | None:
            row = command_store.get(command_id)
            return str(row.get("status")) if row else None

        report = reconcile_dispatches(
            _profile_dispatch_root(args.profile),
            older_than_seconds=args.older_than_seconds,
            dry_run=args.dry_run,
            command_status=command_status,
        )
    finally:
        database.close()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
