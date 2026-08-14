#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from career.services.canary_control import resolve_target_from_compose, run_preflight


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase D canary controls")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="Run read-only canary preflight")
    preflight.add_argument("--compose", required=True, type=Path)
    preflight.add_argument("--bot", required=True)
    preflight.add_argument("--json", action="store_true", dest="as_json")
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
