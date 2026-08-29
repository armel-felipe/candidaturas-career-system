from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from career.services.database import Database
from career.services.persistence.application_repository import ApplicationRepository
from career.services.reconciliation import MigrationImporter


class JsonMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.db = Database(db_path=self.root / "control-plane" / "career.db")
        self.addCleanup(self.db.close)
        self.app_dir = self._write_application(
            bot_id="vagas_bot_01",
            application_id="people_meet",
            notion_id="328",
            company="People Meet",
            role="Diretor de Operações",
            fingerprint="fp-people-meet",
        )

    def test_dry_run_classifies_without_touching_sources_and_apply_is_idempotent(self) -> None:
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.app_dir.rglob("*")
            if path.is_file()
        }
        importer = MigrationImporter(self.db, self.root)

        report = importer.dry_run()

        self.assertEqual(report.status, "dry_run")
        self.assertGreaterEqual(len(report.sources), 6)
        self.assertIn("identity", {item.kind for item in report.sources})
        self.assertIn("fit_map", {item.kind for item in report.sources})
        self.assertTrue(
            self.db.fetch_one(
                "SELECT 1 FROM migration_runs WHERE run_id = ? AND status = 'dry_run'",
                (report.report_id,),
            )
        )
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.app_dir.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)

        applied = importer.apply(report.report_id)
        self.assertEqual(applied.status, "applied")
        self.assertEqual(
            self.db.fetch_one(
                "SELECT COUNT(*) AS count FROM applications WHERE id = ?",
                ("people_meet",),
            )["count"],
            1,
        )
        self.assertEqual(
            self.db.fetch_one(
                "SELECT COUNT(*) AS count FROM fit_map_revisions WHERE application_id = ?",
                ("people_meet",),
            )["count"],
            1,
        )
        self.assertEqual(
            self.db.fetch_one(
                "SELECT COUNT(*) AS count FROM validation_receipts WHERE application_id = ?",
                ("people_meet",),
            )["count"],
            0,
            "migration must not invent validation gates",
        )

        applied_again = importer.apply(report.report_id)
        self.assertEqual(applied_again.status, "applied")
        self.assertEqual(
            self.db.fetch_one(
                "SELECT COUNT(*) AS count FROM fit_map_revisions WHERE application_id = ?",
                ("people_meet",),
            )["count"],
            1,
        )

    def test_conflicting_fit_map_fingerprint_is_blocked(self) -> None:
        fit_map = self.app_dir / "fit_map.json"
        payload = json.loads(fit_map.read_text(encoding="utf-8"))
        payload["metadata"]["job_fingerprint"] = "foreign-fingerprint"
        fit_map.write_text(json.dumps(payload), encoding="utf-8")

        report = MigrationImporter(self.db, self.root).dry_run()

        self.assertTrue(any(item.kind == "fit_map" for item in report.sources))
        self.assertTrue(
            any("fingerprint" in conflict.reason for conflict in report.conflicts)
        )

    def test_missing_identity_blocks_apply_instead_of_raising(self) -> None:
        (self.app_dir / "identity.json").unlink()

        importer = MigrationImporter(self.db, self.root)
        report = importer.dry_run()

        self.assertTrue(any(conflict.reason == "missing_identity" for conflict in report.conflicts))
        applied = importer.apply(report.report_id)
        self.assertEqual(applied.status, "applied_with_conflicts")
        self.assertIn("people_meet", applied.blocked_application_ids)
        self.assertEqual(applied.applied_application_ids, ())

    def _write_application(
        self,
        *,
        bot_id: str,
        application_id: str,
        notion_id: str,
        company: str,
        role: str,
        fingerprint: str,
    ) -> Path:
        app_dir = self.root / "workspaces" / bot_id / "state" / "applications_v2" / application_id
        (app_dir / "derived").mkdir(parents=True)
        (app_dir / "requests").mkdir()
        description = f"# {role} — {company}\n\nDescrição histórica sanitizada.\n"
        fingerprint = hashlib.sha256(description.encode("utf-8")).hexdigest()
        (app_dir / "identity.json").write_text(
            json.dumps(
                {
                    "application_id": application_id,
                    "notion_id": notion_id,
                    "company": company,
                    "role": role,
                    "fingerprint": fingerprint,
                }
            ),
            encoding="utf-8",
        )
        (app_dir / "job_description.md").write_text(description, encoding="utf-8")
        (app_dir / "fit_map.json").write_text(
            json.dumps(
                {
                    "cargo": role,
                    "empresa": company,
                    "metadata": {"job_fingerprint": fingerprint},
                    "scores": {"final": 7.4},
                    "stories": [],
                }
            ),
            encoding="utf-8",
        )
        (app_dir / "state.json").write_text(json.dumps({"stage": "created"}), encoding="utf-8")
        (app_dir / "workflow_state.json").write_text(
            json.dumps({"stage": "created", "completed_states": []}),
            encoding="utf-8",
        )
        (app_dir / "derived" / "manifest.json").write_text(
            json.dumps({"application_id": application_id, "fingerprint": fingerprint}),
            encoding="utf-8",
        )
        (app_dir / "requests" / "request.json").write_text(
            json.dumps({"application_id": application_id, "kind": "fit-map"}),
            encoding="utf-8",
        )
        return app_dir


if __name__ == "__main__":
    unittest.main()
