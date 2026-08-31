from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from career.services import application_context
from career.services.database import Database
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.tasks import registry
from career.utils import sha256_text


class IntakeGateReceiptTests(unittest.TestCase):
    def test_revision_bound_gate_resolves_current_fit_map_revision_when_cli_omits_it(self) -> None:
        class Store:
            application_id = "app-1"
            database = object()

        fake_analysis = type("Analysis", (), {"get_current": lambda self, app_id: type("Revision", (), {"revision_id": "fit_current"})()})()
        with patch.object(registry, "AnalysisRepository", return_value=fake_analysis):
            revision_id = registry._revision_id_for_gate(
                Store(), "cv_review_passed", {}
            )
        self.assertEqual(revision_id, "fit_current")

    def test_persist_intake_records_job_description_saved_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = Database(db_path=root / "control-plane" / "career.db")
            text = "# Diretor de Growth\n" + ("Descrição persistida. " * 40)
            fingerprint = sha256_text(text)
            with patch.object(application_context, "ROOT", root), patch.object(
                application_context, "APPLICATIONS_DIR", root / ".career-state" / "applications_v2"
            ):
                application_context.persist_intake(
                    source_type="notion_record",
                    source_id="578",
                    company="Conexa",
                    role="Diretor de Growth",
                    source_text=text,
                    fingerprint=fingerprint,
                    record_id=578,
                    database=database,
                )

            receipt = database.fetch_one(
                """SELECT gate, validator, application_id, application_fingerprint,
                          input_hash, output_hash
                     FROM validation_receipts
                    WHERE application_id = 'notion_578'
                      AND gate = 'job_description_saved'"""
            )
            self.assertIsNotNone(receipt)
            self.assertEqual(receipt["validator"], "project.save_job_description")
            self.assertEqual(receipt["application_fingerprint"], fingerprint)
            self.assertEqual(receipt["input_hash"], fingerprint)
            self.assertEqual(receipt["output_hash"], fingerprint)
            database.close()

    def test_reintake_reactivates_historical_fingerprint_after_newer_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = Database(db_path=root / "control-plane" / "career.db")
            self.addCleanup(database.close)
            text = "# Diretor de Growth\n" + ("Descrição atual. " * 40)
            fingerprint = sha256_text(text)
            newer_fingerprint = "b" * 64
            applications = ApplicationRepository(database)
            applications.create_application(
                ApplicationIdentity(
                    application_id="notion_578",
                    company="Conexa",
                    role="Diretor de Growth",
                )
            )
            with database.transaction(immediate=True) as conn:
                conn.execute(
                    """INSERT INTO job_descriptions
                       (description_id, application_id, source_id, language, content,
                        content_hash, created_at)
                       VALUES (?, ?, NULL, 'pt', ?, ?, ?)""",
                    ("job-old", "notion_578", text, fingerprint, "2026-08-30T00:00:00+00:00"),
                )
                conn.execute(
                    """INSERT INTO application_revisions
                       (revision_id, application_id, revision_kind, fingerprint,
                        source_hash, payload_json, created_at)
                       VALUES (?, ?, 'job_description', ?, ?, ?, ?)""",
                    (
                        "rev-old",
                        "notion_578",
                        fingerprint,
                        fingerprint,
                        json.dumps({"job_description_id": "job-old"}),
                        "2026-08-30T00:00:00+00:00",
                    ),
                )
                conn.execute(
                    """INSERT INTO application_revisions
                       (revision_id, application_id, revision_kind, fingerprint,
                        source_hash, payload_json, created_at)
                       VALUES (?, ?, 'job_description', ?, ?, ?, ?)""",
                    (
                        "rev-newer",
                        "notion_578",
                        newer_fingerprint,
                        newer_fingerprint,
                        "{}",
                        "2026-08-31T00:00:00+00:00",
                    ),
                )

            with patch.object(application_context, "ROOT", root), patch.object(
                application_context,
                "APPLICATIONS_DIR",
                root / ".career-state" / "applications_v2",
            ):
                application_context.persist_intake(
                    source_type="notion_record",
                    source_id="578",
                    company="Conexa",
                    role="Diretor de Growth",
                    source_text=text,
                    fingerprint=fingerprint,
                    record_id=578,
                    database=database,
                )

            current = applications.resolve(application_id="notion_578")
            self.assertEqual(current.fingerprint, fingerprint)
            current_revision_id = applications.get_current_revision_id("notion_578")
            self.assertIsNotNone(current_revision_id)
            current_description = applications.get_job_description_for_application_revision(
                "notion_578", str(current_revision_id)
            )
            self.assertEqual(current_description.content_hash, fingerprint)


if __name__ == "__main__":
    unittest.main()
