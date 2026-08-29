from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from career.services.application_context import build_application_projection
from career.services.applications_v2 import ApplicationStage, derive_application_stage
from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.artifact_repository import ArtifactRepository
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.utils import sha256_file, sha256_text, utc_now_iso


class ApplicationProjectionTests(unittest.TestCase):
    """SQLite integration coverage for the authoritative application projection.

    Each test would fail if stage derivation consulted legacy ``state.json`` or
    treated a materialized file as an approved receipt.
    """

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.db = Database(db_path=self.root / "runtime.db")
        self.addCleanup(self.db.close)
        self.applications = ApplicationRepository(self.db)
        self.analysis = AnalysisRepository(self.db)
        self.gates = GateRepository(self.db)
        self.artifacts = ArtifactRepository(self.db)
        self.primary = self._create_application("app-conexa", "fp-conexa")
        self.secondary = self._create_application("app-people", "fp-people")

    def test_intake_without_description_receipt_is_pending(self) -> None:
        projection = build_application_projection(self.primary.application_id, self.db)

        self.assertEqual(projection.stage, ApplicationStage.INTAKE_PENDING)
        self.assertEqual(projection.next_required_step, "save_job_description")
        self.assertFalse(projection.base_package_sealed)

    def test_validated_fit_map_advances_to_cv_build(self) -> None:
        self._record_description_saved(self.primary)
        revision_id = self._create_validated_fit_map(self.primary)

        self.assertEqual(
            derive_application_stage(self.primary.application_id, self.db),
            ApplicationStage.FIT_MAP_VALIDATED,
        )
        projection = build_application_projection(self.primary.application_id, self.db)
        self.assertEqual(projection.next_required_step, "build_cv")
        self.assertEqual(projection.fit_map_revision_id, revision_id)

    def test_cv_artifact_without_review_stays_review_pending(self) -> None:
        self._record_description_saved(self.primary)
        revision_id = self._create_validated_fit_map(self.primary)
        self._register_cv(self.primary, revision_id)

        projection = build_application_projection(self.primary.application_id, self.db)

        self.assertEqual(projection.stage, ApplicationStage.CV_REVIEW_PENDING)
        self.assertEqual(projection.next_required_step, "review_cv")

    def test_reviewed_cv_without_onedrive_delivery_stays_delivery_pending(self) -> None:
        self._record_description_saved(self.primary)
        revision_id = self._create_validated_fit_map(self.primary)
        cv = self._register_cv(self.primary, revision_id)
        self._approve_cv(self.primary, cv, revision_id)

        projection = build_application_projection(self.primary.application_id, self.db)

        self.assertEqual(projection.stage, ApplicationStage.ONEDRIVE_PENDING)
        self.assertEqual(projection.next_required_step, "deliver_cv_onedrive")

    def test_delivered_cv_without_notion_sync_stays_notion_pending(self) -> None:
        self._record_description_saved(self.primary)
        revision_id = self._create_validated_fit_map(self.primary)
        cv = self._register_cv(self.primary, revision_id)
        approved = self._approve_cv(self.primary, cv, revision_id)
        self._record_delivery(self.primary.application_id, approved.artifact_id)

        projection = build_application_projection(self.primary.application_id, self.db)

        self.assertEqual(projection.stage, ApplicationStage.NOTION_PENDING)
        self.assertEqual(projection.next_required_step, "sync_notion")

    def test_status_only_delivery_receipt_cannot_seal_package(self) -> None:
        self._record_description_saved(self.primary)
        revision_id = self._create_validated_fit_map(self.primary, label="status-only")
        cv = self._register_cv(self.primary, revision_id, label="status-only")
        approved = self._approve_cv(self.primary, cv, revision_id)
        self._record_status_only_delivery(self.primary.application_id, approved.artifact_id)
        self._record_notion_sync(self.primary.application_id, approved.artifact_id)

        projection = build_application_projection(self.primary.application_id, self.db)

        self.assertEqual(projection.stage, ApplicationStage.ONEDRIVE_PENDING)
        self.assertEqual(projection.next_required_step, "deliver_cv_onedrive")

    def test_sync_receipt_for_previous_artifact_cannot_seal_current_package(self) -> None:
        self._record_description_saved(self.primary)
        first_revision = self._create_validated_fit_map(self.primary, label="v1")
        first_cv = self._register_cv(self.primary, first_revision, label="v1")
        first_approved = self._approve_cv(self.primary, first_cv, first_revision)
        self._record_delivery(self.primary.application_id, first_approved.artifact_id)
        self._record_notion_sync(self.primary.application_id, first_approved.artifact_id)

        current_revision = self._create_validated_fit_map(self.primary, label="v2")
        current_cv = self._register_cv(self.primary, current_revision, label="v2")
        current_approved = self._approve_cv(self.primary, current_cv, current_revision)
        self._record_delivery(self.primary.application_id, current_approved.artifact_id)

        projection = build_application_projection(self.primary.application_id, self.db)

        self.assertEqual(projection.stage, ApplicationStage.NOTION_PENDING)
        self.assertEqual(projection.next_required_step, "sync_notion")

    def test_delivery_receipt_for_previous_artifact_cannot_seal_current_package(self) -> None:
        self._record_description_saved(self.primary)
        first_revision = self._create_validated_fit_map(self.primary, label="delivery-v1")
        first_cv = self._register_cv(self.primary, first_revision, label="delivery-v1")
        first_approved = self._approve_cv(self.primary, first_cv, first_revision)
        self._record_delivery(self.primary.application_id, first_approved.artifact_id)

        current_revision = self._create_validated_fit_map(self.primary, label="delivery-v2")
        current_cv = self._register_cv(self.primary, current_revision, label="delivery-v2")
        current_approved = self._approve_cv(self.primary, current_cv, current_revision)
        self._record_notion_sync(self.primary.application_id, current_approved.artifact_id)

        projection = build_application_projection(self.primary.application_id, self.db)

        self.assertEqual(projection.stage, ApplicationStage.ONEDRIVE_PENDING)
        self.assertEqual(projection.next_required_step, "deliver_cv_onedrive")

    def test_integrity_valid_but_semantically_unrelated_delivery_report_cannot_seal(self) -> None:
        self._record_description_saved(self.primary)
        revision_id = self._create_validated_fit_map(self.primary, label="unrelated-report")
        cv = self._register_cv(self.primary, revision_id, label="unrelated-report")
        approved = self._approve_cv(self.primary, cv, revision_id)
        self._record_delivery(
            self.primary.application_id,
            approved.artifact_id,
            report_payload={"unrelated": True},
        )
        self._record_notion_sync(self.primary.application_id, approved.artifact_id)

        projection = build_application_projection(self.primary.application_id, self.db)

        self.assertEqual(projection.stage, ApplicationStage.ONEDRIVE_PENDING)
        self.assertEqual(projection.next_required_step, "deliver_cv_onedrive")

    def test_delivered_reviewed_cv_and_successful_notion_sync_seal_base_package(self) -> None:
        self._record_description_saved(self.primary)
        revision_id = self._create_validated_fit_map(self.primary)
        cv = self._register_cv(self.primary, revision_id)
        approved = self._approve_cv(self.primary, cv, revision_id)
        self._record_delivery(self.primary.application_id, approved.artifact_id)
        self._record_notion_sync(self.primary.application_id, approved.artifact_id)

        projection = build_application_projection(self.primary.application_id, self.db)

        self.assertEqual(projection.stage, ApplicationStage.CORE_PACKAGE_SEALED)
        self.assertEqual(projection.next_required_step, "post_processing_available")
        self.assertTrue(projection.base_package_sealed)

    def test_gupy_registration_seals_without_cv_or_onedrive(self) -> None:
        application = self.applications.create_application(
            ApplicationIdentity(
                application_id="gupy-registration",
                company="Conexa",
                role="Diretor de Growth",
                fingerprint="g" * 64,
                delivery_profile="gupy_registration",
            )
        )
        self._record_description_saved(application)
        revision_id = self._create_validated_fit_map(application, label="gupy")
        now = utc_now_iso()
        record_id = "notion-gupy-registration"
        self.db.get_connection().execute(
            """INSERT INTO notion_records
               (record_id, application_id, notion_page_id, notion_database_id,
                notion_unique_id, notion_url, created_at, updated_at)
               VALUES (?, ?, 'page-gupy', 'db', '578', NULL, ?, ?)""",
            (record_id, application.application_id, now, now),
        )
        self.db.get_connection().execute(
            """INSERT INTO notion_syncs
               (sync_id, application_id, record_id, action, status, payload_json, synced_at)
               VALUES (?, ?, ?, 'registration_import', 'succeeded', ?, ?)""",
            (
                "sync-gupy-registration",
                application.application_id,
                record_id,
                json.dumps(
                    {
                        "application_id": application.application_id,
                        "record_id": record_id,
                        "registration_status": "Aplicação Feita",
                        "source": "notion_record",
                    },
                    sort_keys=True,
                ),
                now,
            ),
        )
        self.db.get_connection().commit()

        projection = build_application_projection(application.application_id, self.db)

        self.assertEqual(projection.stage, ApplicationStage.CORE_PACKAGE_SEALED)
        self.assertEqual(projection.next_required_step, "post_processing_available")
        self.assertTrue(projection.base_package_sealed)
        self.assertIsNone(projection.cv_artifact_id)

    def test_contradictory_legacy_stage_is_observed_but_never_authoritative(self) -> None:
        self._record_description_saved(self.primary)
        self._create_validated_fit_map(self.primary)
        legacy_state = self.root / "applications_v2" / self.primary.application_id / "state.json"
        legacy_state.parent.mkdir(parents=True)
        legacy_state.write_text(json.dumps({"stage": "done", "next_action": None}), encoding="utf-8")

        projection = build_application_projection(
            self.primary.application_id,
            self.db,
            legacy_state_path=legacy_state,
        )

        self.assertEqual(projection.stage, ApplicationStage.FIT_MAP_VALIDATED)
        self.assertEqual(projection.next_required_step, "build_cv")
        self.assertEqual(projection.compatibility_payload["stage"], "fit_map_validated")
        self.assertEqual(projection.compatibility_payload["next_required_step"], "build_cv")
        self.assertEqual(
            projection.compatibility_payload["active_job"]["application_id"],
            self.primary.application_id,
        )
        observation = self.db.fetch_one(
            """SELECT event, metadata FROM workflow_events
                 WHERE application_id = ?
                 ORDER BY id DESC LIMIT 1""",
            (self.primary.application_id,),
        )
        self.assertEqual(observation["event"], "application_projection_divergence")
        self.assertEqual(json.loads(observation["metadata"])["legacy_stage"], "done")
        self.assertEqual(
            self.db.fetch_one("SELECT stage FROM applications WHERE id = ?", (self.primary.application_id,))["stage"],
            "analyze_pending",
        )

    def test_missing_application_fails_and_receipts_from_another_application_do_not_leak(self) -> None:
        self._record_description_saved(self.secondary)
        self._create_validated_fit_map(self.secondary)

        with self.assertRaisesRegex(ValueError, "unknown application"):
            build_application_projection("app-missing", self.db)

        projection = build_application_projection(self.primary.application_id, self.db)
        self.assertEqual(projection.stage, ApplicationStage.INTAKE_PENDING)
        self.assertEqual(projection.next_required_step, "save_job_description")

    def _create_application(self, application_id: str, fingerprint: str):
        return self.applications.create_application(
            ApplicationIdentity(
                application_id=application_id,
                company=application_id,
                role="Director",
                fingerprint=fingerprint,
            )
        )

    def _record_description_saved(self, application) -> None:
        self.gates.record(
            GateReceipt(
                application_id=application.application_id,
                application_fingerprint=application.fingerprint or "",
                run_id=f"run-description-{application.application_id}",
                gate="job_description_saved",
                validator="project.save_job_description",
                input_hash=sha256_text(f"description-input-{application.application_id}"),
                output_hash=sha256_text(f"description-output-{application.application_id}"),
            )
        )

    def _create_validated_fit_map(self, application, *, label: str = "default") -> str:
        self.gates.record(
            GateReceipt(
                application_id=application.application_id,
                application_fingerprint=application.fingerprint or "",
                run_id=f"run-fit-{application.application_id}-{label}",
                gate="fit_map_draft_valid",
                validator="fit_map.validate_draft",
                input_hash=sha256_text(f"draft-input-{application.application_id}-{label}"),
                output_hash=sha256_text(f"draft-output-{application.application_id}-{label}"),
            )
        )
        revision_id = self.analysis.create_revision(
            application.application_id,
            {"fingerprint": application.fingerprint, "keywords": [], "stories": []},
            sha256_text(f"fit-map-{application.application_id}-{label}"),
        )
        for gate, validator in (
            ("fit_map_built", "fit_map.build"),
            ("fit_map_scored", "fit_map.score"),
            ("fit_map_validated", "fit_map.validate"),
        ):
            self.gates.record(
                GateReceipt(
                    application_id=application.application_id,
                    application_fingerprint=application.fingerprint or "",
                    run_id=f"run-fit-{application.application_id}-{label}",
                    gate=gate,
                    validator=validator,
                    input_hash=sha256_text(f"{gate}-input-{application.application_id}-{label}"),
                    output_hash=sha256_text(f"{gate}-output-{application.application_id}-{label}"),
                    revision_id=revision_id,
                )
            )
        return revision_id

    def _register_cv(self, application, revision_id: str, *, label: str = "default"):
        path = self.root / f"{application.application_id}-{label}.docx"
        path.write_bytes(f"cv-{application.application_id}-{label}".encode("utf-8"))
        return self.artifacts.register(
            application.application_id,
            "cv",
            path,
            None,
            revision_id,
            f"run-cv-{application.application_id}-{label}",
        )

    def _approve_cv(self, application, cv, revision_id: str):
        report = self.root / f"{application.application_id}-review.json"
        report.write_text(
            json.dumps(
                {
                    "kind": "cv",
                    "artifact": cv.path,
                    "company": application.company,
                    "role": application.role,
                    "artifact_sha256": sha256_file(Path(cv.path)),
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
                run_id=f"run-cv-{application.application_id}-{Path(cv.path).stem}",
                gate="cv_review_passed",
                validator="cv.review",
                input_hash=sha256_file(Path(cv.path)),
                output_hash=sha256_file(report),
                revision_id=revision_id,
            )
        )
        return self.artifacts.mark_review_passed(
            cv.artifact_id,
            receipt_id=receipt_id,
            report_path=report,
        )

    def _record_delivery(
        self,
        application_id: str,
        artifact_id: str,
        *,
        report_payload: dict[str, object] | None = None,
    ) -> None:
        self.db.migrate()
        artifact = self.artifacts._load_record(artifact_id)
        report_path = self.root / f"delivery-{application_id}-{artifact_id}.json"
        report = report_payload or {
            "status": "delivered",
            "channel": "onedrive",
            "application_id": application_id,
            "run_id": artifact.run_id,
            "artifact_version_id": artifact_id,
            "artifact_hash": artifact.content_hash,
            "source_revision_id": artifact.source_revision_id,
            "positioning_revision_id": artifact.positioning_revision_id,
        }
        report_path.write_text(
            json.dumps(report, sort_keys=True),
            encoding="utf-8",
        )
        self.db.get_connection().execute(
            """INSERT INTO deliveries
               (delivery_id, application_id, artifact_version_id, channel, target,
                status, report_path, report_hash, payload_json, delivered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"delivery-{application_id}-{artifact_id}",
                application_id,
                artifact_id,
                "onedrive",
                "01_armel/Curriculos/personalizados",
                "delivered",
                str(report_path),
                sha256_file(report_path),
                json.dumps(
                    {
                        "artifact_version_id": artifact_id,
                        "artifact_hash": artifact.content_hash,
                        "source_revision_id": artifact.source_revision_id,
                        "positioning_revision_id": artifact.positioning_revision_id,
                        "application_id": application_id,
                        "run_id": artifact.run_id,
                    },
                    sort_keys=True,
                ),
                utc_now_iso(),
            ),
        )
        self.db.get_connection().commit()

    def _record_status_only_delivery(self, application_id: str, artifact_id: str) -> None:
        self.db.migrate()
        self.db.get_connection().execute(
            """INSERT INTO deliveries
               (delivery_id, application_id, artifact_version_id, channel, target,
                status, report_path, report_hash, payload_json, delivered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"status-only-delivery-{application_id}-{artifact_id}",
                application_id,
                artifact_id,
                "onedrive",
                "01_armel/Curriculos/personalizados",
                "delivered",
                None,
                None,
                "{}",
                utc_now_iso(),
            ),
        )
        self.db.get_connection().commit()

    def _record_notion_sync(self, application_id: str, artifact_id: str) -> None:
        self.db.migrate()
        artifact = self.artifacts._load_record(artifact_id)
        now = utc_now_iso()
        record_id = f"notion-{application_id}"
        receipt_path = self.root / f"notion-{application_id}-{artifact_id}.json"
        receipt_payload = {
            "status": "succeeded",
            "record_id": record_id,
            "application_id": application_id,
            "run_id": artifact.run_id,
            "artifact_version_id": artifact_id,
            "artifact_hash": artifact.content_hash,
            "source_revision_id": artifact.source_revision_id,
            "positioning_revision_id": artifact.positioning_revision_id,
        }
        receipt_path.write_text(json.dumps(receipt_payload, sort_keys=True), encoding="utf-8")
        sync_payload = {**receipt_payload, "receipt_path": str(receipt_path), "receipt_hash": sha256_file(receipt_path)}
        self.db.get_connection().execute(
            """INSERT INTO notion_records
               (record_id, application_id, notion_page_id, notion_database_id,
                notion_unique_id, notion_url, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (record_id, application_id, "page-1", "db-1", None, None, now, now),
        )
        self.db.get_connection().execute(
            """INSERT INTO notion_syncs
               (sync_id, application_id, record_id, action, status, payload_json, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"sync-{application_id}-{artifact_id}", application_id, record_id, "update", "succeeded", json.dumps(sync_payload, sort_keys=True), now),
        )
        self.db.get_connection().commit()


if __name__ == "__main__":
    unittest.main()
