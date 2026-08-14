#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from career.services.canary_control import (
    resolve_target_from_compose,
    rollback_dry_run,
    route_smoke,
    run_preflight,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase D canary controls")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="Run read-only canary preflight")
    preflight.add_argument("--compose", required=True, type=Path)
    preflight.add_argument("--bot", required=True)
    preflight.add_argument("--json", action="store_true", dest="as_json")

    rollback = subparsers.add_parser("rollback-dry-run", help="Inspect rollback without writing")
    rollback.add_argument("--compose", required=True, type=Path)
    rollback.add_argument("--bot", required=True)
    rollback.add_argument("--json", action="store_true", dest="as_json")

    smoke = subparsers.add_parser("route-smoke", help="Exercise deterministic routing smoke locally")
    smoke.add_argument("--root", required=True, type=Path)
    smoke.add_argument("--message-id", required=True)
    smoke.add_argument("--message", required=True)
    smoke.add_argument("--route-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "preflight":
        try:
            target = resolve_target_from_compose(compose_path=args.compose, bot_name=args.bot)
            result = run_preflight(target, args.compose)
        except Exception as exc:
            result = {
                "status": "blocked",
                "target": args.bot,
                "checks": [{"name": "compose_service", "status": "blocked", "reason": str(exc)}],
                "mutations": [],
            }
        if args.as_json:
            json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True)
            sys.stdout.write("\n")
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if result["status"] == "ready" else 1
    if args.command == "rollback-dry-run":
        try:
            target = resolve_target_from_compose(compose_path=args.compose, bot_name=args.bot)
            result = rollback_dry_run(target)
        except Exception as exc:
            result = {
                "status": "blocked",
                "target": args.bot,
                "checks": [{"name": "rollback", "status": "blocked", "reason": str(exc)}],
                "mutations": [],
            }
        if args.as_json:
            json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True)
            sys.stdout.write("\n")
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if result["status"] == "dry_run_ok" else 1
    if args.command == "route-smoke":
        messages = [
            {"message_id": args.message_id, "message": args.message},
            {"message_id": args.message_id, "message": args.message},
        ]
        result = route_smoke(args.root, messages, execute=not args.route_only)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
