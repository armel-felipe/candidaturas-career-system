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
from career.services.persistence.reference_repository import ReferenceRepository
from career.services.positioning_pack import (
    build_positioning_pack,
    validate_positioning_pack,
)
from career.utils import sha256_text


class PositioningPackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_dir.cleanup)
        root = Path(self.temporary_dir.name)
        self.database = Database(root / "control-plane" / "career.db")
        self.addCleanup(self.database.close)
        self.applications = ApplicationRepository(self.database)
        self.analysis = AnalysisRepository(self.database)
        self.references = ReferenceRepository(self.database)
        self.evidence_reference = self.references.upsert_version(
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
                            "metrics": ["10%"],
                            "capabilities": ["operações"],
                            "allowed_claims": ["Claim A"],
                            "source_refs": [{"path": "autoconhecimento.md", "lines": "1-2"}],
                            "artifact_guidance": {"cv": "Caso A"},
                        },
                        {
                            "story_id": "story_b",
                            "title": "História B",
                            "context": "Contexto B",
                            "actions": ["Ação B"],
                            "results": ["Resultado B"],
                            "metrics": ["20%"],
                            "capabilities": ["planejamento"],
                            "allowed_claims": ["Claim B"],
                            "source_refs": [{"path": "autoconhecimento.md", "lines": "3-4"}],
                            "artifact_guidance": {"cv": "Caso B"},
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            "candidate-evidence-v1",
        )
        self.apps = {
            "app-a": self._create_application("app-a", "Empresa A", "Diretor A"),
            "app-b": self._create_application("app-b", "Empresa B", "Diretor B"),
        }

    def _create_application(self, application_id: str, company: str, role: str) -> str:
        description = f"Descrição da vaga de {company}"
        fingerprint = sha256_text(description)
        self.applications.create_application(
            ApplicationIdentity(
                application_id=application_id,
                company=company,
                role=role,
                fingerprint=fingerprint,
            )
        )
        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                """INSERT INTO job_descriptions
                   (description_id, application_id, source_id, language, content, content_hash, created_at)
                   VALUES (?, ?, NULL, ?, ?, ?, ?)""",
                (f"job-{application_id}", application_id, "pt-BR", description, fingerprint, "2026-08-29T00:00:00+00:00"),
            )
            conn.execute(
                """INSERT INTO application_revisions
                   (revision_id, application_id, revision_kind, fingerprint, source_hash, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (f"app-rev-{application_id}", application_id, "job_description", fingerprint, fingerprint, "{}", "2026-08-29T00:00:00+00:00"),
            )
        fit_map_revision = self.analysis.create_revision(
            application_id,
            {
                "metadata": {"job_fingerprint": fingerprint},
                "keywords": [{"keyword": "operações", "coverage": "covered_exact"}],
                "stories": [{"story_key": "selected", "narrative": "História selecionada."}],
                "reference_versions": [{"reference_id": self.evidence_reference}],
            },
            source_hash=f"fit-source-{application_id}",
        )
        story_id = "story_a" if application_id == "app-a" else "story_b"
        self.analysis.create_positioning_revision(
            application_id,
            fit_map_revision,
            {
                "thesis": f"Tese {application_id}",
                "persona": f"Persona {application_id}",
                "stories": [{"story_key": story_id, "story_id": story_id, "narrative": f"Narrativa {story_id}"}],
                "claims": [f"Claim {'A' if story_id == 'story_a' else 'B'}"],
                "artifact_targets": ["cv", "feras", "cover_letter", "habilidades"],
            },
        )
        return fit_map_revision

    def test_builds_isolated_pack_with_revision_lineage(self) -> None:
        pack_a = build_positioning_pack("app-a", self.database)
        pack_b = build_positioning_pack("app-b", self.database)

        self.assertEqual(pack_a["application_id"], "app-a")
        self.assertEqual(pack_a["fit_map_revision_id"], self.apps["app-a"])
        self.assertEqual(pack_a["candidate_evidence_revision_id"], self.evidence_reference)
        self.assertEqual([story["story_id"] for story in pack_a["stories"]], ["story_a"])
        self.assertEqual([story["story_id"] for story in pack_b["stories"]], ["story_b"])
        self.assertNotEqual(pack_a["positioning_revision_id"], pack_b["positioning_revision_id"])
        self.assertEqual(pack_a["claims"], ["Claim A"])
        self.assertEqual(validate_positioning_pack(pack_a), pack_a)

    def test_rejects_story_without_source_refs(self) -> None:
        payload = {
            "application_id": "app-a",
            "fit_map_revision_id": "fit-a",
            "positioning_revision_id": "pos-a",
            "candidate_evidence_revision_id": "ref-a",
            "thesis": "Tese",
            "persona": "Persona",
            "stories": [{"story_id": "story-a", "allowed_claims": ["Claim"]}],
            "claims": ["Claim"],
            "keywords": [],
            "gaps": [],
            "artifact_targets": ["cv"],
        }

        with self.assertRaisesRegex(ValueError, "source_refs"):
            validate_positioning_pack(payload)


if __name__ == "__main__":
    unittest.main()
