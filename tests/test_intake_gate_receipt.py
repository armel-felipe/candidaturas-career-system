from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from career.services import application_context
from career.services.database import Database
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


if __name__ == "__main__":
    unittest.main()
