#!/usr/bin/env python3
"""Run the read-only Phase 7 runtime-unification verifier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap


ROOT = bootstrap()

from career.services.runtime_verifier import verify_runtime, write_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--db")
    parser.add_argument("--report")
    args = parser.parse_args()

    report = verify_runtime(
        Path(args.root),
        strict=args.strict,
        database_path=Path(args.db) if args.db else None,
    )
    if args.report:
        write_report(report, Path(args.report))
    print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True))
    return 2 if args.strict and report.blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
