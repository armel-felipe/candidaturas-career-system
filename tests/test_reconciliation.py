from __future__ import annotations

import json
import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from career.services.database import Database
from career.services.reconciliation import MigrationImporter, Reconciler


CELLULAR_RECONCILE_SCRIPT = ROOT / "scripts" / "reconcile_cellular_run.py"


def _load_cellular_reconcile_module():
    spec = importlib.util.spec_from_file_location(
        "reconcile_cellular_run_for_test", CELLULAR_RECONCILE_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReconciliationTests(unittest.TestCase):
    def test_cellular_reconcile_uses_runtime_database_when_db_is_omitted(self) -> None:
        module = _load_cellular_reconcile_module()
        with tempfile.TemporaryDirectory() as tempdir:
            expected = Path(tempdir) / "career.db"
            previous = os.environ.get("CAREER_CONTROL_DB_PATH")
            os.environ["CAREER_CONTROL_DB_PATH"] = str(expected)
            try:
                database = module.open_database(None)
                self.addCleanup(database.close)
                self.assertEqual(database.db_path, expected)
            finally:
                if previous is None:
                    os.environ.pop("CAREER_CONTROL_DB_PATH", None)
                else:
                    os.environ["CAREER_CONTROL_DB_PATH"] = previous

    def test_missing_receipts_preserve_historical_recovery_without_validating_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            app_dir = root / "workspaces" / "vagas_bot_01" / "state" / "applications_v2" / "notion_578"
            (app_dir / "derived").mkdir(parents=True)
            description = "# Diretor de Growth — Conexa\n\nDescrição sanitizada.\n"
            fingerprint = hashlib.sha256(description.encode("utf-8")).hexdigest()
            (app_dir / "identity.json").write_text(
                json.dumps(
                    {
                        "application_id": "notion_578",
                        "notion_id": "578",
                        "company": "Conexa",
                        "role": "Diretor de Growth",
                        "fingerprint": fingerprint,
                    }
                ),
                encoding="utf-8",
            )
            (app_dir / "job_description.md").write_text(description, encoding="utf-8")
            (app_dir / "fit_map.json").write_text(
                json.dumps(
                    {
                        "cargo": "Diretor de Growth",
                        "empresa": "Conexa",
                        "metadata": {"job_fingerprint": fingerprint},
                        "scores": {"final": 8.0},
                        "stories": [],
                    }
                ),
                encoding="utf-8",
            )
            db = Database(db_path=root / "control-plane" / "career.db")
            self.addCleanup(db.close)
            report = MigrationImporter(db, root).dry_run()
            MigrationImporter(db, root).apply(report.report_id)

            reconciliation = Reconciler(db, root).reconcile("notion_578", "dry-run")

            self.assertEqual(reconciliation.status, "historical_unverified")
            self.assertIn("missing_verified_receipts", reconciliation.warnings)
            self.assertEqual(reconciliation.applied_changes, 0)

            applied = Reconciler(db, root).reconcile("notion_578", "apply")
            self.assertEqual(applied.status, "historical_unverified")
            self.assertEqual(applied.applied_changes, 1)
            event = db.fetch_one(
                "SELECT metadata FROM workflow_events WHERE application_id = ? AND event = ?",
                ("notion_578", "legacy_reconciled"),
            )
            self.assertIn("historical_unverified", str(event["metadata"]))


if __name__ == "__main__":
    unittest.main()
