from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from career.schemas.review import CvReviewReportSchema
from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.artifact_repository import ArtifactRepository
from career.services.persistence.reference_repository import ReferenceRepository
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.services.review import record_approved_cv_provenance
from career.utils import sha256_file, sha256_text
from review_output import publish_approved_review_provenance


class ArtifactProvenanceTests(unittest.TestCase):
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
        self.references = ReferenceRepository(self.db)

        self.primary = self.applications.create_application(
            ApplicationIdentity(
                application_id="app-conexa",
                company="Conexa",
                role="Diretor de Growth",
                notion_id="578",
                fingerprint="fp-conexa",
            )
        )
        self.secondary = self.applications.create_application(
            ApplicationIdentity(
                application_id="app-people",
                company="People Meet",
                role="Diretor de Operacoes",
                notion_id="579",
                fingerprint="fp-people",
            )
        )

    def test_register_docx_persists_hash_text_and_revision_dependencies(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        positioning_revision_id = self.analysis.create_positioning_revision(
            self.primary.application_id,
            source_revision_id,
            {
                "headline": "Executivo de growth com disciplina operacional.",
                "stories": [
                    {
                        "story_key": "growth_story",
                        "title": "Escala com governanca",
                        "narrative": "Escalou operacoes mantendo disciplina de margem.",
                    }
                ],
            },
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-conexa-v1",
        )
        extracted_text = "Resumo\nLiderei growth e governanca.\nExperiencia\nEscala operacional."

        record = self.artifacts.register(
            self.primary.application_id,
            "cv",
            artifact_path,
            extracted_text,
            source_revision_id,
            "run-cv-1",
        )

        self.assertEqual(record.application_id, self.primary.application_id)
        self.assertEqual(record.kind, "cv")
        self.assertEqual(record.path, str(artifact_path.resolve()))
        self.assertEqual(record.content_hash, sha256_file(artifact_path))
        self.assertEqual(
            record.mime_type,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual(record.size_bytes, len(b"docx-conexa-v1"))
        self.assertEqual(record.source_revision_id, source_revision_id)
        self.assertEqual(record.positioning_revision_id, positioning_revision_id)
        self.assertEqual(record.status, "draft")

        validation = self.artifacts.validate_path(record.artifact_id)
        self.assertFalse(validation.valid)
        self.assertEqual(validation.reason, "unapproved_review")

        content_row = self.db.fetch_one(
            "SELECT content FROM artifact_contents WHERE version_id = ?",
            (record.artifact_id,),
        )
        self.assertEqual(content_row, {"content": extracted_text})

    def test_register_can_bind_candidate_evidence_and_positioning_claims(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        positioning_revision_id = self.analysis.create_positioning_revision(
            self.primary.application_id,
            source_revision_id,
            {
                "stories": [{"story_key": "story_a", "narrative": "Narrativa A"}],
            },
        )
        evidence_reference_id = self.references.upsert_version(
            "candidate_evidence",
            "candidate",
            json.dumps({"schema_version": 1, "stories": []}),
            "candidate-evidence-v1",
        )

        record = self.artifacts.register(
            self.primary.application_id,
            "feras",
            None,
            "FERAS com estratégia compartilhada",
            source_revision_id,
            "run-feras-positioning",
            positioning_revision_id=positioning_revision_id,
            candidate_evidence_reference_id=evidence_reference_id,
            positioning_story_ids=["story_a"],
            positioning_claim_ids=["Claim A"],
        )

        dependencies = self.db.fetch_all(
            """SELECT dependency_type, dependency_id
               FROM artifact_version_dependencies
              WHERE version_id = ?
              ORDER BY dependency_type, dependency_id""",
            (record.artifact_id,),
        )
        self.assertIn(
            {"dependency_type": "candidate_evidence_reference", "dependency_id": evidence_reference_id},
            dependencies,
        )
        self.assertIn(
            {"dependency_type": "positioning_story", "dependency_id": "story_a"},
            dependencies,
        )
        self.assertIn(
            {"dependency_type": "positioning_claim", "dependency_id": "Claim A"},
            dependencies,
        )

    def test_register_rejects_missing_source_dependency_and_unsupported_kind(self) -> None:
        source_revision_id = self.analysis.create_revision(
            self.primary.application_id,
            self._fit_map_payload(self.primary.fingerprint or "", score=7.4),
            source_hash="fit-source-no-gate",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-conexa-v1",
        )

        with self.assertRaisesRegex(ValueError, "fit_map_validated"):
            self.artifacts.register(
                self.primary.application_id,
                "cv",
                artifact_path,
                "Resumo",
                source_revision_id,
                "run-cv-1",
            )

        validated_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        with self.assertRaisesRegex(ValueError, "unsupported artifact kind"):
            self.artifacts.register(
                self.primary.application_id,
                "spreadsheet",
                artifact_path,
                None,
                validated_revision_id,
                "run-cv-1",
            )

    def test_validate_path_detects_content_mutation_after_registration(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-conexa-v1",
        )

        record = self.artifacts.register(
            self.primary.application_id,
            "cv",
            artifact_path,
            None,
            source_revision_id,
            "run-cv-1",
        )

        artifact_path.write_bytes(b"docx-conexa-v2")

        validation = self.artifacts.validate_path(record.artifact_id)

        self.assertFalse(validation.valid)
        self.assertEqual(validation.reason, "content_hash_mismatch")
        self.assertEqual(validation.stored_hash, sha256_text("docx-conexa-v1"))
        self.assertEqual(validation.current_hash, sha256_file(artifact_path))

    def test_validate_path_rejects_artifact_when_candidate_evidence_revision_changes(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        positioning_revision_id = self.analysis.create_positioning_revision(
            self.primary.application_id,
            source_revision_id,
            {"stories": [{"story_key": "story_a", "narrative": "Narrativa A"}]},
        )
        first_reference_id = self.references.upsert_version(
            "candidate_evidence",
            "candidate",
            json.dumps({"schema_version": 1, "stories": []}),
            "candidate-evidence-v1",
        )
        artifact = self.artifacts.register(
            self.primary.application_id,
            "feras",
            None,
            "FERAS v1",
            source_revision_id,
            "run-feras-v1",
            positioning_revision_id=positioning_revision_id,
            candidate_evidence_reference_id=first_reference_id,
            positioning_story_ids=["story_a"],
        )
        self.references.upsert_version(
            "candidate_evidence",
            "candidate",
            json.dumps({"schema_version": 2, "stories": []}),
            "candidate-evidence-v2",
        )

        validation = self.artifacts.validate_path(artifact.artifact_id)

        self.assertFalse(validation.valid)
        self.assertEqual(validation.reason, "stale_candidate_evidence_reference")

    def test_validate_path_rejects_artifact_missing_a_required_positioning_story(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        evidence_reference_id = self.references.upsert_version(
            "candidate_evidence",
            "candidate",
            json.dumps(
                {
                    "schema_version": 1,
                    "candidate": {"name": "Felipe Armel"},
                    "stories": [
                        {
                            "story_id": "story_a",
                            "title": "História A",
                            "context": "Contexto A",
                            "actions": ["Ação A"],
                            "results": ["Resultado A"],
                            "metrics": [],
                            "capabilities": ["operações"],
                            "allowed_claims": ["claim_a"],
                            "source_refs": [{"path": "autoconhecimento.md", "lines": "1-2"}],
                            "artifact_guidance": {"feras": "Caso A"},
                        },
                        {
                            "story_id": "story_b",
                            "title": "História B",
                            "context": "Contexto B",
                            "actions": ["Ação B"],
                            "results": ["Resultado B"],
                            "metrics": [],
                            "capabilities": ["transformação"],
                            "allowed_claims": ["claim_b"],
                            "source_refs": [{"path": "autoconhecimento.md", "lines": "3-4"}],
                            "artifact_guidance": {"feras": "Caso B"},
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            "candidate-evidence-v1",
        )
        positioning_revision_id = self.analysis.create_positioning_revision(
            self.primary.application_id,
            source_revision_id,
            {
                "reference_versions": [{"reference_id": evidence_reference_id}],
                "stories": [
                    {"story_id": "story_a", "narrative": "Narrativa A"},
                    {"story_id": "story_b", "narrative": "Narrativa B"},
                ],
                "claims": ["claim_a", "claim_b"],
                "artifact_targets": {
                    "feras": {"required_story_ids": ["story_a", "story_b"]}
                },
            },
        )
        artifact = self.artifacts.register(
            self.primary.application_id,
            "feras",
            None,
            "FERAS com apenas a história A",
            source_revision_id,
            "run-feras-incomplete",
            positioning_revision_id=positioning_revision_id,
            candidate_evidence_reference_id=evidence_reference_id,
            positioning_story_ids=["story_a"],
            positioning_claim_ids=["claim_a"],
        )

        validation = self.artifacts.validate_path(artifact.artifact_id)

        self.assertFalse(validation.valid)
        self.assertEqual(validation.reason, "positioning_coverage_incomplete")

    def test_register_is_idempotent_for_equivalent_artifact(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-conexa-v1",
        )

        first = self.artifacts.register(
            self.primary.application_id,
            "cv",
            artifact_path,
            "Resumo",
            source_revision_id,
            "run-cv-1",
        )
        second = self.artifacts.register(
            self.primary.application_id,
            "cv",
            artifact_path,
            "Resumo",
            source_revision_id,
            "run-cv-1",
        )

        self.assertEqual(first.artifact_id, second.artifact_id)
        rows = self.db.fetch_all(
            "SELECT version_id FROM artifact_versions WHERE application_id = ?",
            (self.primary.application_id,),
        )
        self.assertEqual(rows, [{"version_id": first.artifact_id}])

        distinct_run = self.artifacts.register(
            self.primary.application_id,
            "cv",
            artifact_path,
            "Resumo",
            source_revision_id,
            "run-cv-2",
        )
        self.assertNotEqual(distinct_run.artifact_id, first.artifact_id)

    def test_register_is_isolated_per_application(self) -> None:
        primary_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        secondary_revision_id = self._create_validated_fit_map(
            self.secondary.application_id,
            self.secondary.fingerprint or "",
        )
        shared_path = self._write_docx("felipe_armel_cv_shared.docx", b"shared-docx")

        primary_record = self.artifacts.register(
            self.primary.application_id,
            "cv",
            shared_path,
            "Resumo Conexa",
            primary_revision_id,
            "run-cv-primary",
        )
        secondary_record = self.artifacts.register(
            self.secondary.application_id,
            "cv",
            shared_path,
            "Resumo People",
            secondary_revision_id,
            "run-cv-secondary",
        )

        self.assertNotEqual(primary_record.artifact_id, secondary_record.artifact_id)
        self.assertEqual(primary_record.application_id, self.primary.application_id)
        self.assertEqual(secondary_record.application_id, self.secondary.application_id)

    def test_mark_review_passed_requires_ordered_receipt_and_approved_report(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-conexa-v1",
        )
        artifact = self.artifacts.register(
            self.primary.application_id,
            "cv",
            artifact_path,
            "Resumo",
            source_revision_id,
            "run-cv-1",
        )
        report_path = self._write_review_report(artifact_path, approved=True)

        with self.assertRaisesRegex(ValueError, "validation receipt"):
            self.artifacts.mark_review_passed(
                artifact.artifact_id,
                receipt_id="gate_missing",
                report_path=report_path,
            )

        receipt_id = self.gates.record(
            GateReceipt(
                application_id=self.primary.application_id,
                application_fingerprint=self.primary.fingerprint or "",
                run_id="run-cv-1",
                gate="cv_review_passed",
                validator="cv.approve",
                input_hash=sha256_text(source_revision_id),
                output_hash=sha256_file(report_path),
                revision_id=source_revision_id,
            )
        )

        updated = self.artifacts.mark_review_passed(
            artifact.artifact_id,
            receipt_id=receipt_id,
            report_path=report_path,
        )

        self.assertEqual(updated.status, "review_passed")
        dependency_rows = self.db.fetch_all(
            """SELECT dependency_type, dependency_id
                 FROM artifact_version_dependencies
                WHERE version_id = ?
                ORDER BY dependency_type ASC, dependency_id ASC""",
            (artifact.artifact_id,),
        )
        self.assertEqual(
            dependency_rows,
            [
                {
                    "dependency_type": "fit_map_revision",
                    "dependency_id": source_revision_id,
                },
                {
                    "dependency_type": "validation_receipt",
                    "dependency_id": receipt_id,
                },
            ],
        )

    def test_mark_review_passed_rejects_unapproved_report(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-conexa-v1",
        )
        artifact = self.artifacts.register(
            self.primary.application_id,
            "cv",
            artifact_path,
            "Resumo",
            source_revision_id,
            "run-cv-1",
        )
        report_path = self._write_review_report(artifact_path, approved=False)
        receipt_id = self.gates.record(
            GateReceipt(
                application_id=self.primary.application_id,
                application_fingerprint=self.primary.fingerprint or "",
                run_id="run-cv-1",
                gate="cv_review_passed",
                validator="cv.approve",
                input_hash=sha256_text(source_revision_id),
                output_hash=sha256_file(report_path),
                revision_id=source_revision_id,
            )
        )

        with self.assertRaisesRegex(ValueError, "approved review report"):
            self.artifacts.mark_review_passed(
                artifact.artifact_id,
                receipt_id=receipt_id,
                report_path=report_path,
            )

    def test_review_integration_publishes_only_after_an_approved_report(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-conexa-v1",
        )
        blocked_report = self._write_review_report(artifact_path, approved=False)

        with self.assertRaisesRegex(ValueError, "approved review report"):
            record_approved_cv_provenance(
                artifact=artifact_path,
                report_path=blocked_report,
                application_id=self.primary.application_id,
                source_revision_id=source_revision_id,
                run_id="run-cv-approval",
                database=self.db,
            )
        self.assertEqual(
            self.db.fetch_all(
                "SELECT version_id FROM artifact_versions WHERE application_id = ?",
                (self.primary.application_id,),
            ),
            [],
        )

        approved_report = self._write_review_report(artifact_path, approved=True)
        record = record_approved_cv_provenance(
            artifact=artifact_path,
            report_path=approved_report,
            application_id=self.primary.application_id,
            source_revision_id=source_revision_id,
            run_id="run-cv-approval",
            database=self.db,
        )

        self.assertEqual(record.status, "review_passed")
        validation = self.artifacts.validate_path(record.artifact_id)
        self.assertTrue(validation.valid)
        receipt = self.db.fetch_one(
            "SELECT gate, result FROM validation_receipts WHERE receipt_id = ?",
            (record.review_receipt_id,),
        )
        self.assertEqual(receipt, {"gate": "cv_review_passed", "result": "passed"})

    def test_review_publication_rejects_artifact_mutated_after_objective_review(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-reviewed-v1",
        )
        report_path = self._write_review_report(artifact_path, approved=True)

        artifact_path.write_bytes(b"docx-replaced-v2")

        with self.assertRaisesRegex(ValueError, "artifact_sha256"):
            record_approved_cv_provenance(
                artifact=artifact_path,
                report_path=report_path,
                application_id=self.primary.application_id,
                source_revision_id=source_revision_id,
                run_id="run-cv-mutated",
                database=self.db,
            )
        self.assertEqual(
            self.db.fetch_all(
                "SELECT version_id FROM artifact_versions WHERE application_id = ?",
                (self.primary.application_id,),
            ),
            [],
        )

        self.assertEqual(
            self.db.fetch_all(
                "SELECT receipt_id FROM validation_receipts WHERE gate = 'cv_review_passed'"
            ),
            [],
        )

    def test_mark_review_passed_rejects_report_for_other_artifact_bytes(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-reviewed-v1",
        )
        report_path = self._write_review_report(artifact_path, approved=True)

        artifact_path.write_bytes(b"docx-replaced-v2")
        artifact = self.artifacts.register(
            self.primary.application_id,
            "cv",
            artifact_path,
            None,
            source_revision_id,
            "run-cv-mutated",
        )
        receipt_id = self.gates.record(
            GateReceipt(
                application_id=self.primary.application_id,
                application_fingerprint=self.primary.fingerprint or "",
                run_id="run-cv-mutated",
                gate="cv_review_passed",
                validator="cv.review",
                input_hash=sha256_file(artifact_path),
                output_hash=sha256_file(report_path),
                revision_id=source_revision_id,
            )
        )

        with self.assertRaisesRegex(ValueError, "artifact_sha256"):
            self.artifacts.mark_review_passed(
                artifact.artifact_id,
                receipt_id=receipt_id,
                report_path=report_path,
            )
        self.assertEqual(self.artifacts._load_record(artifact.artifact_id).status, "draft")

    def test_legacy_review_report_without_digest_stays_report_only(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-reviewed-v1",
        )
        report_path = self._write_review_report(
            artifact_path,
            approved=True,
            include_artifact_sha256=False,
        )
        legacy_report = json.loads(report_path.read_text(encoding="utf-8"))

        CvReviewReportSchema(legacy_report).validate()
        with self.assertRaisesRegex(ValueError, "artifact_sha256"):
            record_approved_cv_provenance(
                artifact=artifact_path,
                report_path=report_path,
                application_id=self.primary.application_id,
                source_revision_id=source_revision_id,
                run_id="run-cv-legacy-report",
                database=self.db,
            )
        self.assertEqual(
            self.db.fetch_all(
                "SELECT version_id FROM artifact_versions WHERE application_id = ?",
                (self.primary.application_id,),
            ),
            [],
        )

    def test_mark_review_passed_rejects_legacy_report_without_digest(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-reviewed-v1",
        )
        report_path = self._write_review_report(
            artifact_path,
            approved=True,
            include_artifact_sha256=False,
        )
        artifact = self.artifacts.register(
            self.primary.application_id,
            "cv",
            artifact_path,
            None,
            source_revision_id,
            "run-cv-legacy-report",
        )
        receipt_id = self.gates.record(
            GateReceipt(
                application_id=self.primary.application_id,
                application_fingerprint=self.primary.fingerprint or "",
                run_id="run-cv-legacy-report",
                gate="cv_review_passed",
                validator="cv.review",
                input_hash=sha256_file(artifact_path),
                output_hash=sha256_file(report_path),
                revision_id=source_revision_id,
            )
        )

        with self.assertRaisesRegex(ValueError, "artifact_sha256"):
            self.artifacts.mark_review_passed(
                artifact.artifact_id,
                receipt_id=receipt_id,
                report_path=report_path,
            )
        self.assertEqual(self.artifacts._load_record(artifact.artifact_id).status, "draft")

    def test_review_output_publisher_treats_report_without_approval_as_non_receipt(self) -> None:
        source_revision_id = self._create_validated_fit_map(
            self.primary.application_id,
            self.primary.fingerprint or "",
        )
        artifact_path = self._write_docx(
            "felipe_armel_cv_conexa_diretor_growth.docx",
            b"docx-conexa-v1",
        )
        blocked_report = self._write_review_report(artifact_path, approved=False)

        published = publish_approved_review_provenance(
            report=json.loads(blocked_report.read_text(encoding="utf-8")),
            artifact=artifact_path,
            report_path=blocked_report,
            application_id=self.primary.application_id,
            source_revision_id=source_revision_id,
            run_id="run-cv-script",
            control_db_path=self.db.db_path,
        )

        self.assertIsNone(published)
        self.assertEqual(
            self.db.fetch_all(
                "SELECT version_id FROM artifact_versions WHERE application_id = ?",
                (self.primary.application_id,),
            ),
            [],
        )

        approved_report = self._write_review_report(artifact_path, approved=True)
        published = publish_approved_review_provenance(
            report=json.loads(approved_report.read_text(encoding="utf-8")),
            artifact=artifact_path,
            report_path=approved_report,
            application_id=self.primary.application_id,
            source_revision_id=source_revision_id,
            run_id="run-cv-script",
            control_db_path=self.db.db_path,
        )
        self.assertIsNotNone(published)
        self.assertEqual(published.status, "review_passed")

    def _create_validated_fit_map(self, application_id: str, fingerprint: str) -> str:
        source_revision_id = self.analysis.create_revision(
            application_id,
            self._fit_map_payload(fingerprint, score=8.1),
            source_hash=f"fit-source-{application_id}",
        )
        self.gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint=fingerprint,
                run_id=f"run-fit-{application_id}",
                gate="fit_map_draft_valid",
                validator="fit_map.validate_draft",
                input_hash=sha256_text(f"draft:{application_id}"),
                output_hash=sha256_text(f"draft-valid:{application_id}"),
            )
        )
        self.gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint=fingerprint,
                run_id=f"run-fit-{application_id}",
                gate="fit_map_built",
                validator="fit_map.build",
                input_hash=sha256_text(f"build-input:{application_id}"),
                output_hash=sha256_text(f"build-output:{application_id}"),
                revision_id=source_revision_id,
            )
        )
        self.gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint=fingerprint,
                run_id=f"run-fit-{application_id}",
                gate="fit_map_scored",
                validator="fit_map.score",
                input_hash=sha256_text(f"score-input:{application_id}"),
                output_hash=sha256_text(f"score-output:{application_id}"),
                revision_id=source_revision_id,
            )
        )
        self.gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint=fingerprint,
                run_id=f"run-fit-{application_id}",
                gate="fit_map_validated",
                validator="fit_map.validate",
                input_hash=sha256_text(f"validate-input:{application_id}"),
                output_hash=sha256_text(f"validate-output:{application_id}"),
                revision_id=source_revision_id,
            )
        )
        return source_revision_id

    def _fit_map_payload(self, fingerprint: str, *, score: float) -> dict[str, object]:
        return {
            "metadata": {"job_fingerprint": fingerprint},
            "scores": {"final": score},
            "stories": [
                {
                    "story_key": "base_story",
                    "title": "Base",
                    "narrative": "Narrativa base defensavel.",
                }
            ],
        }

    def _write_docx(self, filename: str, content: bytes) -> Path:
        path = self.root / filename
        path.write_bytes(content)
        return path

    def _write_review_report(
        self,
        artifact_path: Path,
        *,
        approved: bool,
        include_artifact_sha256: bool = True,
    ) -> Path:
        report = {
            "kind": "cv",
            "artifact": str(artifact_path.resolve()),
            "company": "Conexa",
            "role": "Diretor de Growth",
            "approved": approved,
            "approved_for_delivery": approved,
            "ats_policy": {"top8": {}, "top15": {}, "weights": {}},
            "blockers": [] if approved else [{"id": "ats_top8_missing"}],
            "warnings": [],
            "totals": {"weight_total_passed": 8, "weight_total_total": 8},
            "weight_total_checks": [],
            "minor_checks": [],
        }
        if include_artifact_sha256:
            report["artifact_sha256"] = sha256_file(artifact_path)
            CvReviewReportSchema(report).validate()
        path = self.root / ("review_approved.json" if approved else "review_blocked.json")
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
