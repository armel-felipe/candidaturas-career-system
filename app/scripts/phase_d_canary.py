#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from career.services.canary_control import (
    assert_canary_target,
    resolve_target_from_compose,
    rollback_dry_run,
    route_smoke,
    run_preflight,
)
from career.utils import read_json
from scripts.run_phase_c_pilot import run_pilot


def _assert_target_workspace_consistent(target: Any, workspace_root: Path) -> None:
    expected_state_root = (workspace_root / ".career-state").resolve()
    expected_paths = {
        "control_db_path": (expected_state_root / "career.db").resolve(),
        "authority_ledger_path": (expected_state_root / "authority.json").resolve(),
    }
    for field_name, expected_path in expected_paths.items():
        actual = Path(getattr(target, field_name)).resolve()
        if actual != expected_path:
            raise ValueError(
                f"workspace must match the canary target {field_name}: "
                f"expected {expected_path} got {actual}"
            )


def run_controlled_canary(
    target: Any, application_id: str, workspace: Path
) -> dict[str, Any]:
    assert_canary_target(target)
    workspace_root = Path(workspace).resolve()
    if workspace_root != Path(target.workspace_root).resolve():
        raise ValueError("workspace must match the canary target workspace_root")
    _assert_target_workspace_consistent(target, workspace_root)
    result = run_pilot(workspace_root, application_id=application_id)
    request = read_json(Path(result["request_json"]))
    manifest = read_json(Path(result["manifest_path"]))
    expected = {
        "application_id": result["application_id"],
        "run_id": result["run_id"],
        "node_id": "analyze_fit",
        "attempt": 1,
    }
    for key, value in expected.items():
        if request.get(key) != value:
            raise RuntimeError(f"cell request {key} mismatch for controlled canary")
        if manifest.get(key) != value:
            raise RuntimeError(f"manifest {key} mismatch for controlled canary")
    return {
        **result,
        "target": target.bot_name,
    }


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
    smoke.add_argument("--root", type=Path)
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
        smoke_root = args.root or Path(tempfile.mkdtemp(prefix="phase-d-fixture-"))
        messages = [
            {"message_id": args.message_id, "message": args.message},
            {"message_id": args.message_id, "message": args.message},
        ]
        result = route_smoke(smoke_root, messages, execute=not args.route_only)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
