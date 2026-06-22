#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.services.harness_supervisor import HarnessSupervisor
from career.utils import read_json, utc_now_iso, write_json


def process_message(
    message: str,
    *,
    message_id: str | None = None,
    execute: bool = True,
    supervisor: HarnessSupervisor | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    normalized = " ".join(str(message or "").strip().split())
    if not normalized:
        raise ValueError("Telegram message cannot be empty.")
    stable_id = message_id or hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    safe_id = "".join(ch for ch in stable_id if ch.isalnum() or ch in {"-", "_"})[:80]
    cache_path = root / ".career-state" / "telegram" / "messages" / f"{safe_id}.json"
    if cache_path.exists():
        cached = read_json(cache_path)
        if not _should_retry_cached_message(cached):
            cached["deduplicated"] = True
            return cached
    supervisor = supervisor or HarnessSupervisor(root)
    result = supervisor.handle_message(
        normalized,
        channel="telegram",
        execute=execute,
    )
    envelope = {
        "message_id": stable_id,
        "received_at": utc_now_iso(),
        "message": normalized,
        "deduplicated": False,
        "result": result,
    }
    write_json(cache_path, envelope)
    return envelope


def _should_retry_cached_message(cached: dict[str, Any]) -> bool:
    result = cached.get("result") if isinstance(cached.get("result"), dict) else {}
    if not isinstance(result, dict):
        return False
    if result.get("status") != "blocked":
        return False
    return str(result.get("blocker_reason") or "") in {
        "no_deterministic_route",
        "generic_runner_unavailable",
        "generic_runner_failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message")
    parser.add_argument("--message-id")
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--route-only", action="store_true")
    args = parser.parse_args()
    if args.stdin:
        message = sys.stdin.read()
    else:
        message = args.message
    if not message:
        raise SystemExit("Use --message or --stdin.")
    result = process_message(
        message,
        message_id=args.message_id,
        execute=not args.route_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
