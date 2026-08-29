#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career.services.cellular_persistence import reconcile_standard_cv  # noqa: E402
from career.services.database import Database  # noqa: E402


def open_database(db_path: Path | None) -> Database:
    """Use the runtime-selected authority unless an explicit DB is supplied."""
    return Database(db_path=db_path) if db_path is not None else Database()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import a completed cellular standard-CV run into SQLite."
    )
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--fit-map", required=True, type=Path)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--cv", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--cv-run-id", required=True)
    parser.add_argument("--delivery-report", required=True, type=Path)
    parser.add_argument("--notion-receipt", required=True, type=Path)
    parser.add_argument("--notion-run-id", required=True)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    database = open_database(args.db)
    try:
        result = reconcile_standard_cv(
            database=database,
            application_id=args.application_id,
            fit_map_path=args.fit_map,
            draft_path=args.draft,
            cv_path=args.cv,
            registry_path=args.registry,
            cv_run_id=args.cv_run_id,
            delivery_report_path=args.delivery_report,
            notion_receipt_path=args.notion_receipt,
            notion_run_id=args.notion_run_id,
            state_root=args.state_root,
        )
    finally:
        database.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
