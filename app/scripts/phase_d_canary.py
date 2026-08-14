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
    persist_gate_evidence,
    probe_runner,
    resolve_target_from_compose,
    rollback_dry_run,
    route_smoke,
    stage_hook,
    run_preflight,
)
from career.services.application_context import paths_for
from career.utils import read_json


def _assert_target_state_root(target: Any) -> None:
    control_db_path = Path(getattr(target, "control_db_path")).resolve()
    authority_ledger_path = Path(getattr(target, "authority_ledger_path")).resolve()
    if control_db_path.name != "career.db" or authority_ledger_path.name != "authority.json":
        raise ValueError(
            "canonical canary authority paths must end with career.db and authority.json"
        )
    if control_db_path.parent != authority_ledger_path.parent:
        raise ValueError(
            "workspace requires control_db_path and authority_ledger_path under one canary state root"
        )


def run_controlled_canary(
    target: Any, application_id: str, workspace: Path
) -> dict[str, Any]:
    from run_phase_c_pilot import run_pilot

    assert_canary_target(target)
    app_name = str(application_id or "").strip()
    if not app_name:
        raise ValueError("application_id is required for controlled canary")
    workspace_root = Path(workspace).resolve()
    if workspace_root != Path(target.workspace_root).resolve():
        raise ValueError("workspace must match the canary target workspace_root")
    _assert_target_state_root(target)
    applications_root = Path(target.control_db_path).resolve().parent / "applications_v2"
    existing_paths = paths_for(app_name, root=applications_root)
    if existing_paths.app_dir.exists():
        raise ValueError(f"application_id already exists for controlled canary: {existing_paths.application_id}")
    result = run_pilot(
        workspace_root,
        application_id=app_name,
        control_db_path=Path(target.control_db_path),
        authority_ledger_path=Path(target.authority_ledger_path),
    )
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
        "node_id": str(request.get("node_id") or ""),
        "attempt": int(request.get("attempt") or 0),
        "request_md": str(Path(result["request_json"]).with_suffix(".md")),
        "read_allowlist": list(request.get("read_allowlist") or []),
        "write_allowlist": list(request.get("write_allowlist") or []),
    }


def _blocked_target_payload(bot_name: str, *, reason: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "target": bot_name,
        "checks": [{"name": "target", "status": "blocked", "reason": reason}],
        "mutations": [],
    }


def _blocked_runner_payload(bot_name: str, *, reason: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "target": bot_name,
        "command": [],
        "type": "unknown",
        "available": False,
        "returncode": None,
        "blocker": reason,
    }


def _reject_non_canary_bot(bot_name: str, *, runner: bool = False) -> dict[str, Any] | None:
    if str(bot_name).strip() == "vagas_bot_01":
        return None
    reason = "phase D canary target must be vagas_bot_01"
    return _blocked_runner_payload(bot_name, reason=reason) if runner else _blocked_target_payload(bot_name, reason=reason)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase D canary controls")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="Run read-only canary preflight")
    preflight.add_argument("--compose", required=True, type=Path)
    preflight.add_argument("--bot", required=True)
    preflight.add_argument("--json", action="store_true", dest="as_json")

    record_preflight = subparsers.add_parser(
        "record-preflight", help="Run D0 and explicitly persist ready evidence"
    )
    record_preflight.add_argument("--compose", required=True, type=Path)
    record_preflight.add_argument("--bot", required=True)
    record_preflight.add_argument("--json", action="store_true", dest="as_json")

    rollback = subparsers.add_parser("rollback-dry-run", help="Inspect rollback without writing")
    rollback.add_argument("--compose", required=True, type=Path)
    rollback.add_argument("--bot", required=True)
    rollback.add_argument("--json", action="store_true", dest="as_json")

    stage = subparsers.add_parser("stage-hook", help="Produce D1 hook-stage evidence without running the gateway")
    stage.add_argument("--compose", required=True, type=Path)
    stage.add_argument("--bot", required=True)
    stage.add_argument("--apply", action="store_true")
    stage.add_argument("--json", action="store_true", dest="as_json")

    controlled = subparsers.add_parser("controlled-run", help="Run the D2 controlled canary and persist compact gate evidence")
    controlled.add_argument("--compose", required=True, type=Path)
    controlled.add_argument("--bot", required=True)
    controlled.add_argument("--application-id", required=True)
    controlled.add_argument("--workspace", type=Path)
    controlled.add_argument("--json", action="store_true", dest="as_json")

    runner_probe = subparsers.add_parser("runner-probe", help="Probe the real runner gate without fallback")
    runner_probe.add_argument(
        "--compose",
        type=Path,
        default=Path(__file__).parents[1] / "deploy" / "hermes" / "compose.yaml",
    )
    runner_probe.add_argument("--bot", required=True)
    runner_probe.add_argument("--gate-manifest", type=Path)
    runner_probe.add_argument("--json", action="store_true", dest="as_json")

    smoke = subparsers.add_parser("route-smoke", help="Exercise deterministic routing smoke locally")
    smoke.add_argument("--root", type=Path)
    smoke.add_argument("--message-id", required=True)
    smoke.add_argument("--message", required=True)
    smoke.add_argument("--route-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "preflight":
        blocked = _reject_non_canary_bot(args.bot)
        if blocked is not None:
            result = blocked
        else:
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
    if args.command == "record-preflight":
        blocked = _reject_non_canary_bot(args.bot)
        if blocked is not None:
            result = blocked
        else:
            try:
                target = resolve_target_from_compose(compose_path=args.compose, bot_name=args.bot)
                result = run_preflight(target, args.compose)
                if result.get("status") == "ready":
                    result = {
                        **result,
                        "evidence": persist_gate_evidence(target, "d0", result),
                    }
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
        blocked = _reject_non_canary_bot(args.bot)
        if blocked is not None:
            result = blocked
        else:
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
    if args.command == "stage-hook":
        blocked = _reject_non_canary_bot(args.bot)
        if blocked is not None:
            result = blocked
        else:
            try:
                target = resolve_target_from_compose(compose_path=args.compose, bot_name=args.bot)
                result = stage_hook(target, apply=bool(args.apply))
                persist_gate_evidence(target, "d1", result)
            except Exception as exc:
                result = {
                    "status": "blocked",
                    "target": args.bot,
                    "checks": [{"name": "stage_hook", "status": "blocked", "reason": str(exc)}],
                    "mutations": [],
                }
        if args.as_json:
            json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True)
            sys.stdout.write("\n")
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if result["status"] in {"dry_run_ok", "installed"} else 1
    if args.command == "controlled-run":
        blocked = _reject_non_canary_bot(args.bot)
        if blocked is not None:
            result = blocked
        else:
            try:
                target = resolve_target_from_compose(compose_path=args.compose, bot_name=args.bot)
                workspace = args.workspace or target.workspace_root
                result = run_controlled_canary(target, args.application_id, workspace)
                persist_gate_evidence(target, "d2", result)
            except Exception as exc:
                result = {
                    "status": "blocked",
                    "target": args.bot,
                    "checks": [{"name": "controlled_run", "status": "blocked", "reason": str(exc)}],
                    "mutations": [],
                }
        if args.as_json:
            json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True)
            sys.stdout.write("\n")
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if result["status"] == "completed" else 1
    if args.command == "runner-probe":
        from career.services import applications_v2

        blocked = _reject_non_canary_bot(args.bot, runner=True)
        if blocked is not None:
            result = blocked
        else:
            try:
                target = resolve_target_from_compose(compose_path=args.compose, bot_name=args.bot)
                result = probe_runner(
                    target,
                    dict(applications_v2.DEFAULT_CONFIG["analysis_runner"]),
                    gate_manifest_path=args.gate_manifest,
                )
            except Exception as exc:
                result = {
                    "status": "blocked",
                    "target": args.bot,
                    "command": [],
                    "type": "unknown",
                    "available": False,
                    "returncode": None,
                    "blocker": str(exc),
                }
        if args.as_json:
            json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True)
            sys.stdout.write("\n")
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if result["status"] == "completed" else 1
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
