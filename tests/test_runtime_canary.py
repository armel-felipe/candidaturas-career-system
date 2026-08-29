from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.artifact_repository import ArtifactRepository
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.services.runtime_canary import run_canary
from career.utils import sha256_file, sha256_text, utc_now_iso


class RuntimeCanaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.db_path = self.root / "control-plane" / "career.db"
        self.db = Database(db_path=self.db_path)
        self.applications = ApplicationRepository(self.db)
        self.analysis = AnalysisRepository(self.db)
        self.gates = GateRepository(self.db)
        self.artifacts = ArtifactRepository(self.db)

    def tearDown(self) -> None:
        self.db.close()

    def _application(self, application_id: str):
        application = self.applications.create_application(
            ApplicationIdentity(
                application_id=application_id,
                company="Canary Co",
                role="Director of Operations",
                fingerprint="f" * 64,
            )
        )
        self.gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint="f" * 64,
                run_id=f"run-description-{application_id}",
                gate="job_description_saved",
                validator="project.save_job_description",
                input_hash=sha256_text("description-input"),
                output_hash=sha256_text("description-output"),
            )
        )
        self.gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint="f" * 64,
                run_id=f"run-fit-{application_id}",
                gate="fit_map_draft_valid",
                validator="fit_map.validate_draft",
                input_hash=sha256_text("draft-input"),
                output_hash=sha256_text("draft-output"),
            )
        )
        revision_id = self.analysis.create_revision(
            application_id,
            {"fingerprint": "f" * 64, "keywords": [], "stories": []},
            sha256_text("fit-map"),
        )
        for gate, validator in (
            ("fit_map_built", "fit_map.build"),
            ("fit_map_scored", "fit_map.score"),
            ("fit_map_validated", "fit_map.validate"),
        ):
            self.gates.record(
                GateReceipt(
                    application_id=application_id,
                    application_fingerprint="f" * 64,
                    run_id=f"run-fit-{application_id}",
                    gate=gate,
                    validator=validator,
                    input_hash=sha256_text(gate + "-input"),
                    output_hash=sha256_text(gate + "-output"),
                    revision_id=revision_id,
                )
            )
        return application, revision_id

    def _cv(self, application, revision_id: str):
        path = self.root / f"{application.application_id}.docx"
        path.write_bytes(b"canary cv")
        cv = self.artifacts.register(
            application.application_id,
            "cv",
            path,
            None,
            revision_id,
            f"run-cv-{application.application_id}",
        )
        report_path = self.root / f"{application.application_id}-review.json"
        report_path.write_text(
            json.dumps(
                {
                    "kind": "cv",
                    "artifact": cv.path,
                    "company": application.company,
                    "role": application.role,
                    "artifact_sha256": sha256_file(path),
                    "approved": True,
                    "approved_for_delivery": True,
                    "ats_policy": {},
                    "blockers": [],
                    "warnings": [],
                    "totals": {},
                    "weight_total_checks": [],
                    "minor_checks": [],
                }
            ),
            encoding="utf-8",
        )
        receipt_id = self.gates.record(
            GateReceipt(
                application_id=application.application_id,
                application_fingerprint=application.fingerprint or "",
                run_id=f"run-cv-{application.application_id}",
                gate="cv_review_passed",
                validator="cv.review",
                input_hash=sha256_file(path),
                output_hash=sha256_file(report_path),
                revision_id=revision_id,
            )
        )
        return self.artifacts.mark_review_passed(
            cv.artifact_id, receipt_id=receipt_id, report_path=report_path
        )

    def _unreviewed_cv(self, application, revision_id: str):
        path = self.root / f"{application.application_id}-unreviewed.docx"
        path.write_bytes(b"unreviewed canary cv")
        return self.artifacts.register(
            application.application_id,
            "cv",
            path,
            None,
            revision_id,
            f"run-cv-{application.application_id}-unreviewed",
        )

    def _seal_external_receipts(self, application_id: str, artifact_id: str) -> None:
        artifact = self.artifacts._load_record(artifact_id)
        report_path = self.root / f"{application_id}-delivery.json"
        payload = {
            "application_id": application_id,
            "artifact_version_id": artifact_id,
            "artifact_hash": artifact.content_hash,
            "source_revision_id": artifact.source_revision_id,
            "positioning_revision_id": artifact.positioning_revision_id,
            "run_id": artifact.run_id,
        }
        report_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        self.db.get_connection().execute(
            """INSERT INTO deliveries
               (delivery_id, application_id, artifact_version_id, channel, target,
                status, report_path, report_hash, payload_json, delivered_at)
               VALUES (?, ?, ?, 'onedrive', ?, 'delivered', ?, ?, ?, ?)""",
            (
                f"delivery-{application_id}", application_id, artifact_id,
                "01_armel/Curriculos/personalizados", str(report_path),
                sha256_file(report_path), json.dumps(payload, sort_keys=True), utc_now_iso(),
            ),
        )
        record_id = f"notion-{application_id}"
        receipt_path = self.root / f"{application_id}-notion.json"
        notion_payload = {**payload, "record_id": record_id}
        receipt_path.write_text(json.dumps(notion_payload, sort_keys=True), encoding="utf-8")
        now = utc_now_iso()
        self.db.get_connection().execute(
            """INSERT INTO notion_records
               (record_id, application_id, notion_page_id, notion_database_id,
                notion_unique_id, notion_url, created_at, updated_at)
               VALUES (?, ?, 'page', 'db', NULL, NULL, ?, ?)""",
            (record_id, application_id, now, now),
        )
        sync_payload = {
            **notion_payload,
            "receipt_path": str(receipt_path),
            "receipt_hash": sha256_file(receipt_path),
        }
        self.db.get_connection().execute(
            """INSERT INTO notion_syncs
               (sync_id, application_id, record_id, action, status, payload_json, synced_at)
               VALUES (?, ?, ?, 'update', 'succeeded', ?, ?)""",
            (f"sync-{application_id}", application_id, record_id, json.dumps(sync_payload, sort_keys=True), now),
        )
        self.db.get_connection().commit()

    def test_canary_blocks_candidate_with_cv_not_reviewed(self) -> None:
        application, revision_id = self._application("people-meet-canary")
        self._unreviewed_cv(application, revision_id)

        report = run_canary(
            application.application_id,
            "vagas_bot_01",
            mode="offline",
            root=Path(__file__).resolve().parents[1],
            database_path=self.db_path,
        )

        self.assertEqual(report.status, "blocked")
        self.assertEqual(report.gates["stage"], "cv_review_pending")
        self.assertIn("core_package_not_sealed", report.blockers)

    def test_canary_passes_only_when_core_package_is_sealed(self) -> None:
        application, revision_id = self._application("healthy-canary")
        cv = self._cv(application, revision_id)
        self._seal_external_receipts(application.application_id, cv.artifact_id)

        report = run_canary(
            application.application_id,
            "vagas_bot_02",
            mode="offline",
            root=Path(__file__).resolve().parents[1],
            database_path=self.db_path,
        )

        self.assertEqual(report.status, "passed")
        self.assertEqual(report.gates["stage"], "core_package_sealed")
        self.assertEqual(report.bot_id, "vagas_bot_02")
        self.assertTrue(report.rollback_checkpoint["verified"])


if __name__ == "__main__":
    unittest.main()
