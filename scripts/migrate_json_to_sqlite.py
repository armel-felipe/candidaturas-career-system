#!/usr/bin/env python3
"""Audit and import historical JSON state into the canonical SQLite control plane.

The default operation is a read-only source inventory.  Applying a report is
explicit and refuses reports with conflicts or changed source hashes.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from _bootstrap import bootstrap

bootstrap()

from career.paths import ROOT
from career.services.database import Database
from career.services.reconciliation import MigrationImporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        type=Path,
        default=ROOT,
        help="root to inventory (default: repository root)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=ROOT / "control-plane" / "career.db",
        help="canonical SQLite database path",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="optional JSON output path for the migration report",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="inventory only")
    mode.add_argument("--apply", metavar="REPORT_ID", help="apply a persisted dry-run report")
    return parser


def report_payload(report) -> dict:
    return {
        "report_id": report.report_id,
        "status": report.status,
        "input_root": report.input_root,
        "source_count": len(report.sources),
        "applied_application_count": len(report.applied_application_ids),
        "blocked_application_count": len(report.blocked_application_ids),
        "sources_by_kind": {
            kind: sum(1 for source in report.sources if source.kind == kind)
            for kind in sorted({source.kind for source in report.sources})
        },
        "conflicts": [asdict(conflict) for conflict in report.conflicts],
    }


def main() -> int:
    args = build_parser().parse_args()
    database = Database(db_path=args.db)
    try:
        importer = MigrationImporter(database, args.input_root)
        if args.apply:
            report = importer.apply(args.apply)
        else:
            report = importer.dry_run()
        payload = report_payload(report)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if report.status not in {"blocked"} else 2
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
