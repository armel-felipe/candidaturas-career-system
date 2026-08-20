from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from career.services.database import Database
from career.services.harness_supervisor import (
    HarnessSupervisor,
    SpecialistContract,
    SpecialistResult,
)
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.artifact_repository import ArtifactRepository
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.paths import CAREER_STATE
from career.utils import sha256_file, sha256_text


class SupervisorContractTests(unittest.TestCase):
    """Real SQLite contract checks for specialist completion.

    Each test names a failure that the former "an allowed file changed" rule
    could not observe.  No test reads or writes compatibility state JSON.
    """

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.db = Database(self.root / "control-plane" / "career.db")
        self.addCleanup(self.db.close)
        self.applications = ApplicationRepository(self.db)
        self.analysis = AnalysisRepository(self.db)
        self.gates = GateRepository(self.db)
        self.artifacts = ArtifactRepository(self.db)
        self.supervisor = HarnessSupervisor(self.root)
        self.primary = self._application("notion_578", "fp-conexa", "Conexa")
        self.secondary = self._application("notion_579", "fp-people", "People Meet")
        self.cv_contract = SpecialistContract(
            step="cv",
            required_artifacts=("cv",),
            required_gates=("cv_review_passed",),
        )

    def test_docx_without_review_is_blocked_and_audited(self) -> None:
        revision_id = self._validated_revision(self.primary)
        self._register_cv(self.primary, revision_id, label="unreviewed")

        result = self.supervisor.execute_specialist(
            self.primary.application_id,
            self.cv_contract,
            run_id="run-contract-unreviewed",
        )

        self.assertIsInstance(result, SpecialistResult)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.blocker_reason, "unapproved_review")
        self._assert_blocker_event(result, missing_artifact="cv")

    def test_foreign_feras_cannot_satisfy_current_application_contract(self) -> None:
        secondary_revision = self._validated_revision(self.secondary)
        self.artifacts.register(
            self.secondary.application_id,
            "feras",
            None,
            "FERAS da People Meet",
            secondary_revision,
            "run-feras-secondary",
        )
        primary_revision = self._validated_revision(self.primary)
        contract = SpecialistContract(
            step="feras",
            required_artifacts=("feras",),
            required_gates=("fit_map_validated",),
        )

        result = self.supervisor.execute_specialist(
            self.primary.application_id,
            contract,
            run_id="run-contract-foreign-feras",
        )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.blocker_reason, "missing_required_artifact")
        self.assertEqual(result.missing_artifacts, ("feras",))
        self.assertEqual(primary_revision, result.source_revision_id)
        self._assert_blocker_event(result, missing_artifact="feras")

    def test_mutated_registered_docx_cannot_satisfy_contract(self) -> None:
        revision_id = self._validated_revision(self.primary)
        approved = self._approve_cv(
            self.primary,
            self._register_cv(self.primary, revision_id, label="mutated"),
            revision_id,
        )
        Path(str(approved.path)).write_bytes(b"different-bytes-after-review")

        result = self.supervisor.execute_specialist(
            self.primary.application_id,
            self.cv_contract,
            run_id="run-contract-mutated",
        )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.blocker_reason, "content_hash_mismatch")
        self._assert_blocker_event(result, missing_artifact="cv")

    def test_missing_required_gate_blocks_without_partial_success(self) -> None:
        revision_id = self._validated_revision(self.primary)
        self._approve_cv(
            self.primary,
            self._register_cv(self.primary, revision_id, label="missing-gate"),
            revision_id,
        )
        contract = SpecialistContract(
            step="cv",
            required_artifacts=("cv",),
            required_gates=("cv_review_passed", "delivery_verified"),
        )

        result = self.supervisor.execute_specialist(
            self.primary.application_id,
            contract,
            run_id="run-contract-missing-gate",
        )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.blocker_reason, "missing_required_gate")
        self.assertEqual(result.missing_gates, ("delivery_verified",))
        self._assert_blocker_event(result, missing_gate="delivery_verified")

    def test_scoped_provenance_and_receipts_return_success_without_stage_change(self) -> None:
        revision_id = self._validated_revision(self.primary)
        self._approve_cv(
            self.primary,
            self._register_cv(self.primary, revision_id, label="approved"),
            revision_id,
        )
        before = self.db.fetch_one(
            "SELECT stage, funil_stage FROM applications WHERE id = ?",
            (self.primary.application_id,),
        )

        result = self.supervisor.execute_specialist(
            self.primary.application_id,
            self.cv_contract,
            run_id="run-contract-success",
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.application_id, self.primary.application_id)
        self.assertEqual(result.source_revision_id, revision_id)
        self.assertEqual(result.missing_artifacts, ())
        self.assertEqual(result.missing_gates, ())
        self.assertEqual(
            self.db.fetch_one(
                "SELECT stage, funil_stage FROM applications WHERE id = ?",
                (self.primary.application_id,),
            ),
            before,
        )

    def test_unscoped_and_unknown_calls_fail_closed(self) -> None:
        unscoped = self.supervisor.execute_specialist(
            "", self.cv_contract, run_id="run-contract-unscoped"
        )
        unknown = self.supervisor.execute_specialist(
            "notion_unknown", self.cv_contract, run_id="run-contract-unknown"
        )

        self.assertEqual(unscoped.status, "blocked")
        self.assertEqual(unscoped.blocker_reason, "explicit_application_scope_required")
        self.assertEqual(unknown.status, "blocked")
        self.assertEqual(unknown.blocker_reason, "unknown_application")

        malformed = self.supervisor.execute_specialist(
            "../foreign", self.cv_contract, run_id="run-contract-malformed"
        )
        self.assertEqual(malformed.status, "blocked")
        self.assertEqual(malformed.blocker_reason, "unknown_application")

    def test_legacy_explicit_pipeline_signature_remains_scope_blocked(self) -> None:
        result = self.supervisor.execute_specialist("fit-map", extras={})

        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocker_reason"], "explicit_application_scope_required")

    def test_scoped_fit_map_menu_uses_sqlite_snapshot_not_contaminated_root_json(self) -> None:
        self._seed_menu_snapshot(self.primary)
        root_fit_map = CAREER_STATE / "fit_map.json"
        original = root_fit_map.read_bytes() if root_fit_map.exists() else None
        self.addCleanup(self._restore_root_fit_map, root_fit_map, original)
        root_fit_map.parent.mkdir(parents=True, exist_ok=True)
        root_fit_map.write_text(
            json.dumps(
                {
                    "cargo": "Customer Success Manager",
                    "empresa": "Instaleap",
                    "nota_aderencia": {"final": 1.0},
                    "gaps_sem_cobertura": ["gap global"],
                    "objecoes": ["objecao global"],
                }
            ),
            encoding="utf-8",
        )

        scoped_pipeline_result = self.supervisor._pipeline_result(
            intake={"application_id": self.primary.application_id},
            specialist={
                "status": "completed",
                "step": "fit-map",
                "application_id": self.primary.application_id,
            },
        )
        decorated = self.supervisor._decorate_result_payload(scoped_pipeline_result)

        serialized = json.dumps(decorated, ensure_ascii=False)
        self.assertIn("Conexa", serialized)
        self.assertIn("Diretor", serialized)
        self.assertIn("8.7/10", serialized)
        self.assertIn("Gaps mapeados: 1 | Objecoes mapeadas: 1", serialized)
        self.assertNotIn("Instaleap", serialized)
        self.assertNotIn("Customer Success Manager", serialized)
        self.assertNotIn("1.0/10", serialized)
        self.assertNotIn("gap global", serialized)
        self.assertNotIn("objecao global", serialized)

    def test_completed_fit_map_menu_without_scope_is_blocked(self) -> None:
        decorated = self.supervisor._decorate_result_payload(
            {"status": "completed", "step": "fit-map"}
        )

        self.assertEqual(decorated["status"], "blocked")
        self.assertEqual(
            decorated["blocker_reason"], "explicit_application_scope_required"
        )

    def _application(self, application_id: str, fingerprint: str, company: str):
        return self.applications.create_application(
            ApplicationIdentity(
                application_id=application_id,
                company=company,
                role="Diretor",
                fingerprint=fingerprint,
            )
        )

    def _seed_menu_snapshot(self, application) -> str:
        description_id = f"description-{application.application_id}"
        application_revision_id = f"application-revision-{application.application_id}"
        description = "Descricao canonica da vaga de Diretor na Conexa"
        with self.db.transaction(immediate=True) as conn:
            conn.execute(
                """INSERT INTO job_descriptions
                   (description_id, application_id, source_id, language, content,
                    content_hash, created_at)
                   VALUES (?, ?, NULL, ?, ?, ?, ?)""",
                (
                    description_id,
                    application.application_id,
                    "pt",
                    description,
                    sha256_text(description),
                    "2026-08-20T00:00:00+00:00",
                ),
            )
            conn.execute(
                """INSERT INTO application_revisions
                   (revision_id, application_id, revision_kind, fingerprint,
                    source_hash, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    application_revision_id,
                    application.application_id,
                    "job_description",
                    application.fingerprint,
                    sha256_text(description),
                    json.dumps({"job_description_id": description_id}),
                    "2099-01-01T00:00:00+00:00",
                ),
            )
        return self.analysis.create_revision(
            application.application_id,
            {
                "metadata": {"job_fingerprint": application.fingerprint},
                "scores": {"final": 8.7},
                "dimensions": {
                    "estrategia": {
                        "score": 8.7,
                        "gap_summary": "Aprofundar contexto clinico",
                    }
                },
                "objections": [
                    {
                        "objection_key": "healthcare",
                        "objection_text": "Experiencia setorial",
                    }
                ],
            },
            source_hash=sha256_text(f"menu-fit-map-{application.application_id}"),
        )

    @staticmethod
    def _restore_root_fit_map(path: Path, original: bytes | None) -> None:
        if original is None:
            path.unlink(missing_ok=True)
            return
        path.write_bytes(original)

    def _validated_revision(self, application) -> str:
        run_id = f"run-fit-{application.application_id}"
        self.gates.record(
            GateReceipt(
                application_id=application.application_id,
                application_fingerprint=application.fingerprint or "",
                run_id=run_id,
                gate="fit_map_draft_valid",
                validator="fit_map.validate_draft",
                input_hash=sha256_text(f"draft-input-{application.application_id}"),
                output_hash=sha256_text(f"draft-output-{application.application_id}"),
            )
        )
        revision_id = self.analysis.create_revision(
            application.application_id,
            {"fingerprint": application.fingerprint, "keywords": [], "stories": []},
            source_hash=sha256_text(f"fit-map-{application.application_id}"),
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
                    run_id=run_id,
                    gate=gate,
                    validator=validator,
                    input_hash=sha256_text(f"{gate}-input-{application.application_id}"),
                    output_hash=sha256_text(f"{gate}-output-{application.application_id}"),
                    revision_id=revision_id,
                )
            )
        return revision_id

    def _register_cv(self, application, revision_id: str, *, label: str):
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

    def _approve_cv(self, application, artifact, revision_id: str):
        report = self.root / f"{application.application_id}-{artifact.artifact_id}-review.json"
        report.write_text(
            json.dumps(
                {
                    "kind": "cv",
                    "artifact": artifact.path,
                    "company": application.company,
                    "role": application.role,
                    "artifact_sha256": sha256_file(Path(str(artifact.path))),
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
                run_id=str(artifact.run_id),
                gate="cv_review_passed",
                validator="cv.review",
                input_hash=sha256_file(Path(str(artifact.path))),
                output_hash=sha256_file(report),
                revision_id=revision_id,
            )
        )
        return self.artifacts.mark_review_passed(
            artifact.artifact_id,
            receipt_id=receipt_id,
            report_path=report,
        )

    def _assert_blocker_event(
        self,
        result: SpecialistResult,
        *,
        missing_artifact: str | None = None,
        missing_gate: str | None = None,
    ) -> None:
        event = self.db.fetch_one(
            """SELECT event, metadata FROM workflow_events
                 WHERE application_id = ? AND event = 'specialist_contract_blocked'
                 ORDER BY id DESC LIMIT 1""",
            (result.application_id,),
        )
        self.assertIsNotNone(event)
        metadata = json.loads(str(event["metadata"]))
        self.assertEqual(metadata["application_id"], result.application_id)
        self.assertEqual(metadata["run_id"], result.run_id)
        self.assertEqual(metadata["validator"], "harness_supervisor.contract")
        self.assertEqual(metadata["reason"], result.blocker_reason)
        if missing_artifact:
            self.assertIn(missing_artifact, metadata["missing_artifacts"])
        if missing_gate:
            self.assertIn(missing_gate, metadata["missing_gates"])
        receipt = self.db.fetch_one(
            """SELECT application_id, run_id, validator, gate, result, details_json
                 FROM validation_receipts
                WHERE run_id = ? AND gate = 'specialist_contract'
                ORDER BY created_at DESC, receipt_id DESC LIMIT 1""",
            (result.run_id,),
        )
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["application_id"], result.application_id)
        self.assertEqual(receipt["validator"], "harness_supervisor.contract")
        self.assertEqual(receipt["result"], "blocked")
        receipt_details = json.loads(str(receipt["details_json"]))
        self.assertEqual(receipt_details["reason"], result.blocker_reason)


if __name__ == "__main__":
    unittest.main()
