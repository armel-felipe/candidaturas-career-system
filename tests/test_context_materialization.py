from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from career.services.context_materializer import ContextMaterializer
from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.reference_repository import ReferenceRepository
from career.utils import sha256_file, sha256_text


class ContextMaterializerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_dir.cleanup)
        self.root = Path(self.temporary_dir.name)
        self.database = Database(self.root / "control-plane" / "career.db")
        self.addCleanup(self.database.close)
        self.applications = ApplicationRepository(self.database)
        self.analysis = AnalysisRepository(self.database)
        self.references = ReferenceRepository(self.database)
        self.materializer = ContextMaterializer(self.database)
        self._create_application("notion_578", "Conexa", "Diretor de Growth", "Conexa job text")
        self._create_application("notion_999", "Outra", "Diretor de Produto", "Outra job text")
        self.references.upsert_version(
            "candidate_facts",
            "felipe",
            json.dumps({"facts": ["Escalou operacoes"]}, ensure_ascii=False),
            "candidate-source-v1",
        )
        self.conexa_revision_one = self._create_analysis(
            "notion_578", "fp-conexa-v1", "Growth", "Historia de crescimento v1"
        )
        self.conexa_revision_two = self._create_analysis(
            "notion_578", "fp-conexa-v2", "Growth revisado", "Historia de crescimento v2"
        )
        self._create_analysis("notion_999", "fp-outra", "Produto", "Historia de produto")

    def _create_application(self, application_id: str, company: str, role: str, description: str) -> None:
        self.applications.create_application(
            ApplicationIdentity(
                application_id=application_id,
                company=company,
                role=role,
                fingerprint=f"intake-{application_id}",
            )
        )
        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                """INSERT INTO job_descriptions
                   (description_id, application_id, source_id, language, content, content_hash, created_at)
                   VALUES (?, ?, NULL, ?, ?, ?, ?)""",
                (
                    f"job-{application_id}",
                    application_id,
                    "pt",
                    description,
                    sha256_text(description),
                    "2026-08-20T00:00:00+00:00",
                ),
            )
            conn.execute(
                """INSERT INTO application_revisions
                   (revision_id, application_id, revision_kind, fingerprint, source_hash, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"description-revision-{application_id}",
                    application_id,
                    "job_description",
                    f"intake-{application_id}",
                    f"description-{application_id}",
                    json.dumps({"job_description_id": f"job-{application_id}"}),
                    "2999-01-01T00:00:00+00:00",
                ),
            )

    def _create_analysis(self, application_id: str, fingerprint: str, keyword: str, story: str) -> str:
        revision_id = self.analysis.create_revision(
            application_id,
            {
                "metadata": {"job_fingerprint": fingerprint},
                "scores": {"final": 8.1},
                "keywords": [
                    {
                        "keyword": keyword,
                        "coverage": "covered_exact",
                        "importance": 0.95,
                        "evidence": story,
                    }
                ],
                "stories": [
                    {"story_key": "impact", "title": keyword, "narrative": story}
                ],
            },
            source_hash=f"source-{fingerprint}",
        )
        self.analysis.create_positioning_revision(
            application_id,
            revision_id,
            {
                "headline": f"Executivo de {keyword}",
                "stories": [
                    {"story_key": "pitch", "title": keyword, "narrative": story}
                ],
            },
        )
        return revision_id

    def test_builds_all_context_kinds_from_canonical_records_with_bound_metadata(self) -> None:
        for kind in ("fit_map_seed", "cv_input", "feras_input", "habilidades_input"):
            payload = self.materializer.build("notion_578", kind)

            self.assertEqual(payload["kind"], kind)
            self.assertEqual(payload["application_id"], "notion_578")
            self.assertEqual(payload["source_revision_ids"]["fit_map_revision_id"], self.conexa_revision_two)
            self.assertEqual(payload["context"]["application"]["company"], "Conexa")
            self.assertEqual(payload["context"]["job_description"]["content"], "Conexa job text")
            self.assertEqual(payload["context"]["analysis"]["stories"][0]["narrative"], "Historia de crescimento v2")
            self.assertEqual(payload["context"]["references"][0]["logical_key"], "felipe")
            self.assertEqual(
                payload["canonical_payload_hash"],
                sha256_text(json.dumps(payload["context"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
            )
            self.assertTrue(payload["generated_at"])

    def test_revision_pinning_uses_only_the_requested_application_revision(self) -> None:
        payload = self.materializer.build(
            "notion_578", "cv_input", revision_id=self.conexa_revision_one
        )

        self.assertEqual(payload["source_revision_ids"]["fit_map_revision_id"], self.conexa_revision_one)
        self.assertEqual(payload["context"]["analysis"]["stories"][0]["narrative"], "Historia de crescimento v1")
        with self.assertRaisesRegex(ValueError, "same application|no fit_map revision"):
            self.materializer.build("notion_578", "cv_input", revision_id="missing")

    def test_rejects_unknown_and_cross_application_revision_scope(self) -> None:
        with self.assertRaisesRegex(ValueError, "no application matched"):
            self.materializer.build("notion_missing", "fit_map_seed")
        with self.assertRaisesRegex(ValueError, "same application"):
            self.materializer.build("notion_999", "feras_input", revision_id=self.conexa_revision_two)
        with self.assertRaisesRegex(ValueError, "unsupported context kind"):
            self.materializer.build("notion_578", "not-a-context")

    def test_export_is_scoped_hashable_and_never_used_as_authority(self) -> None:
        scoped_destination = (
            self.root
            / ".career-state"
            / "applications_v2"
            / "notion_578"
            / "derived"
            / "cv_input.json"
        )
        receipt = self.materializer.export_json("notion_578", "cv_input", scoped_destination)

        self.assertEqual(receipt.application_id, "notion_578")
        self.assertEqual(receipt.kind, "cv_input")
        self.assertEqual(receipt.path, scoped_destination)
        self.assertEqual(receipt.content_hash, sha256_file(scoped_destination))
        self.assertTrue(receipt.created_at)
        self.assertTrue(receipt.expires_at)
        exported = json.loads(scoped_destination.read_text(encoding="utf-8"))
        exported["context"]["application"]["company"] = "Contaminada"
        scoped_destination.write_text(json.dumps(exported), encoding="utf-8")

        rebuilt = self.materializer.build("notion_578", "cv_input")
        self.assertEqual(rebuilt["context"]["application"]["company"], "Conexa")
        with self.assertRaisesRegex(ValueError, "application-scoped or temporary"):
            self.materializer.export_json(
                "notion_578", "cv_input", Path.cwd() / "exports" / "cv_input.json"
            )

    def test_same_kind_cannot_cross_application_boundaries(self) -> None:
        conexa = self.materializer.build("notion_578", "habilidades_input")
        outra = self.materializer.build("notion_999", "habilidades_input")

        self.assertNotEqual(conexa["canonical_payload_hash"], outra["canonical_payload_hash"])
        self.assertEqual(conexa["context"]["analysis"]["keywords"][0]["keyword"], "Growth revisado")
        self.assertEqual(outra["context"]["analysis"]["keywords"][0]["keyword"], "Produto")


if __name__ == "__main__":
    unittest.main()
