#!/usr/bin/env python3
"""Run a safe Phase 7 canary for one explicit application."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap


ROOT = bootstrap()

from career.services.runtime_canary import run_canary, write_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--bot-id", required=True, choices=["vagas_bot_01", "vagas_bot_02"])
    parser.add_argument("--mode", choices=["offline", "live"], default="offline")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--db")
    parser.add_argument("--report")
    args = parser.parse_args()
    report = run_canary(
        args.application_id,
        args.bot_id,
        mode=args.mode,
        root=Path(args.root),
        database_path=Path(args.db) if args.db else None,
    )
    if args.report:
        write_report(report, Path(args.report))
    print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True))
    return 2 if report.blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
