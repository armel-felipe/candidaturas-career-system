from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.services.post_processing import (
    create_post_artifact,
    list_post_artifacts,
    read_post_artifact,
    revise_positioning,
)
from career.utils import sha256_text


class PostProcessingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.db = Database(db_path=self.root / "runtime.db")
        self.addCleanup(self.db.close)
        self.applications = ApplicationRepository(self.db)
        self.analysis = AnalysisRepository(self.db)
        self.gates = GateRepository(self.db)
        self.application = self.applications.create_application(
            ApplicationIdentity(
                application_id="app-post-processing",
                company="Conexa",
                role="Diretor de Growth",
                notion_id="578",
                fingerprint="fp-post-processing",
            )
        )
        self.application_revision_id = self.applications.get_current_revision_id(
            self.application.application_id
        )
        assert self.application_revision_id
        self.db.migrate()
        self._attach_description(
            self.application.application_id,
            self.application_revision_id,
            "desc-post-processing",
            "fp-post-processing",
        )
        self.fit_map_revision_id = self.analysis.create_revision(
            self.application.application_id,
            {
                "cargo": "Diretor de Growth",
                "empresa": "Conexa",
                "metadata": {"job_fingerprint": "fp-post-processing"},
                "keywords_para_ats": ["Growth", "Operações", "Dados"],
                "keywords_habilidade_ats": ["Growth", "Operações", "Dados"],
                "historias_selecionadas": {
                    "principal": {
                        "resultado": "Escala de receita com eficiência operacional.",
                        "contexto": "Liderei crescimento com dados e execução.",
                    }
                },
                "stories": [
                    {
                        "story_key": "growth",
                        "title": "Escala",
                        "narrative": "Escala defensável com dados.",
                    }
                ],
            },
            source_hash="fp-post-processing",
            application_revision_id=self.application_revision_id,
        )
        self._record_fit_map_gates()

    def _attach_description(
        self,
        application_id: str,
        application_revision_id: str,
        description_id: str,
        fingerprint: str,
    ) -> None:
        self.db.get_connection().execute(
            """
            INSERT INTO job_descriptions
                (description_id, application_id, source_id, language, content,
                 content_hash, created_at)
            VALUES (?, ?, NULL, 'pt-BR', ?, ?, '2026-08-20T00:00:00+00:00')
            """,
            (
                description_id,
                application_id,
                "Descrição da vaga de growth e operações.",
                fingerprint,
            ),
        )
        self.db.get_connection().execute(
            """
            UPDATE application_revisions
               SET payload_json = ?
             WHERE revision_id = ? AND application_id = ?
            """,
            (json.dumps({"job_description_id": description_id}), application_revision_id, application_id),
        )
        self.db.get_connection().commit()

    def test_post_artifacts_use_sqlite_snapshot_without_rerunning_intake(self) -> None:
        revision_count_before = self._application_revision_count()
        stage_before = self._stage()

        feras = create_post_artifact(
            self.application.application_id,
            "feras",
            database=self.db,
        )
        skills = create_post_artifact(
            self.application.application_id,
            "gupy_skills",
            database=self.db,
        )
        letter = create_post_artifact(
            self.application.application_id,
            "cover_letter",
            database=self.db,
        )

        self.assertEqual(feras.application_id, self.application.application_id)
        self.assertEqual(skills.application_id, self.application.application_id)
        self.assertEqual(letter.application_id, self.application.application_id)
        self.assertEqual(feras.source_revision_id, self.fit_map_revision_id)
        self.assertEqual(skills.source_revision_id, self.fit_map_revision_id)
        self.assertEqual(letter.source_revision_id, self.fit_map_revision_id)
        self.assertNotEqual(feras.artifact_id, skills.artifact_id)
        self.assertEqual(self._application_revision_count(), revision_count_before)
        self.assertEqual(self._stage(), stage_before)
        self.assertTrue(
            self.db.fetch_one(
                "SELECT 1 FROM artifact_contents WHERE version_id = ?",
                (feras.artifact_id,),
            )
        )
        self.assertIn(
            "Conexa",
            read_post_artifact(
                self.application.application_id,
                feras.artifact_id,
                database=self.db,
            ),
        )
        self.assertEqual(len(list_post_artifacts(self.application.application_id, database=self.db)), 3)

    def test_revised_positioning_preserves_old_post_artifacts(self) -> None:
        original = create_post_artifact(
            self.application.application_id,
            "feras",
            database=self.db,
        )

        positioning_revision_id = revise_positioning(
            self.application.application_id,
            {"headline": "Growth com governança e escala."},
            database=self.db,
        )
        revised = create_post_artifact(
            self.application.application_id,
            "feras",
            source_positioning_revision=positioning_revision_id,
            database=self.db,
        )

        self.assertNotEqual(original.artifact_id, revised.artifact_id)
        self.assertEqual(revised.positioning_revision_id, positioning_revision_id)
        records = list_post_artifacts(self.application.application_id, database=self.db)
        self.assertEqual([item.artifact_id for item in records], [revised.artifact_id, original.artifact_id])

    def test_foreign_positioning_revision_is_rejected(self) -> None:
        other = self.applications.create_application(
            ApplicationIdentity(
                application_id="app-other-post-processing",
                company="People Meet",
                role="Diretor de Operações",
                fingerprint="fp-other-post-processing",
            )
        )
        other_application_revision_id = self.applications.get_current_revision_id(
            other.application_id
        )
        assert other_application_revision_id
        self._attach_description(
            other.application_id,
            other_application_revision_id,
            "desc-other-post-processing",
            "fp-other-post-processing",
        )
        other_fit_map_revision_id = self.analysis.create_revision(
            other.application_id,
            {
                "cargo": other.role,
                "empresa": other.company,
                "metadata": {"job_fingerprint": "fp-other-post-processing"},
                "stories": [],
            },
            source_hash="fp-other-post-processing",
            application_revision_id=other_application_revision_id,
        )
        other_revision = self.analysis.create_positioning_revision(
            other.application_id,
            other_fit_map_revision_id,
            {"headline": "não pertence à candidatura atual"},
        )
        with self.assertRaisesRegex(ValueError, "same application"):
            create_post_artifact(
                self.application.application_id,
                "feras",
                source_positioning_revision=other_revision,
                database=self.db,
            )

    def _record_fit_map_gates(self) -> None:
        app_id = self.application.application_id
        fingerprint = "fp-post-processing"
        receipts = [
            ("fit_map_draft_valid", "fit_map.validate_draft", None),
            ("fit_map_built", "fit_map.build", self.fit_map_revision_id),
            ("fit_map_scored", "fit_map.score", self.fit_map_revision_id),
            ("fit_map_validated", "fit_map.validate", self.fit_map_revision_id),
        ]
        for gate, validator, revision_id in receipts:
            self.gates.record(
                GateReceipt(
                    application_id=app_id,
                    application_fingerprint=fingerprint,
                    run_id=f"run-{gate}",
                    gate=gate,
                    validator=validator,
                    input_hash=sha256_text(f"input:{gate}"),
                    output_hash=sha256_text(f"output:{gate}"),
                    revision_id=revision_id,
                )
            )

    def _application_revision_count(self) -> int:
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM application_revisions WHERE application_id = ?",
            (self.application.application_id,),
        )
        return int(row["count"])

    def _stage(self) -> str:
        row = self.db.fetch_one(
            "SELECT stage FROM applications WHERE id = ?",
            (self.application.application_id,),
        )
        return str(row["stage"])


if __name__ == "__main__":
    unittest.main()
