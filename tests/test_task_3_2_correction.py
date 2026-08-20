from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from career.services import application_context, intake, multiagent
from career.services.context_materializer import ContextMaterializer
from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.reference_repository import ReferenceRepository
from career.utils import read_json, sha256_text, write_json


class Task32CorrectionTests(unittest.TestCase):
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

    def _create_revision_history(self) -> tuple[str, str]:
        application_id = "notion_578"
        reference_id = self.references.upsert_version(
            "candidate_facts", "felipe", "REFERENCE HISTORY", "reference-history"
        )
        self.applications.create_application(
            ApplicationIdentity(
                application_id=application_id,
                company="Conexa",
                role="Diretor de Growth",
                fingerprint="fp-bootstrap",
            )
        )
        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                """INSERT INTO job_descriptions
                   (description_id, application_id, source_id, language, content, content_hash, created_at)
                   VALUES (?, ?, NULL, ?, ?, ?, ?)""",
                (
                    "description-v1",
                    application_id,
                    "pt",
                    "DESCRICAO CANONICA V1",
                    sha256_text("DESCRICAO CANONICA V1"),
                    "2099-01-01T00:00:00+00:00",
                ),
            )
            conn.execute(
                """INSERT INTO application_revisions
                   (revision_id, application_id, revision_kind, fingerprint, source_hash, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    "application-v1",
                    application_id,
                    "job_description",
                    "fp-v1",
                    "source-v1",
                    json.dumps({"job_description_id": "description-v1"}),
                    "2099-01-01T00:01:00+00:00",
                ),
            )
        fit_map_v1 = self.analysis.create_revision(
            application_id,
            {
                "metadata": {"job_fingerprint": "fp-v1"},
                "reference_versions": [{"reference_id": reference_id}],
                "stories": [
                    {
                        "story_key": "v1",
                        "narrative": "HISTORIA CANONICA V1",
                    }
                ],
            },
            source_hash="source-v1",
        )
        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                """INSERT INTO job_descriptions
                   (description_id, application_id, source_id, language, content, content_hash, created_at)
                   VALUES (?, ?, NULL, ?, ?, ?, ?)""",
                (
                    "description-v2",
                    application_id,
                    "pt",
                    "DESCRICAO CANONICA V2",
                    sha256_text("DESCRICAO CANONICA V2"),
                    "2100-01-01T00:00:00+00:00",
                ),
            )
            conn.execute(
                """INSERT INTO application_revisions
                   (revision_id, application_id, revision_kind, fingerprint, source_hash, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    "application-v2",
                    application_id,
                    "job_description",
                    "fp-v2",
                    "source-v2",
                    json.dumps({"job_description_id": "description-v2"}),
                    "2100-01-01T00:01:00+00:00",
                ),
            )
        fit_map_v2 = self.analysis.create_revision(
            application_id,
            {
                "metadata": {"job_fingerprint": "fp-v2"},
                "reference_versions": [{"reference_id": reference_id}],
                "stories": [
                    {
                        "story_key": "v2",
                        "narrative": "HISTORIA CANONICA V2",
                    }
                ],
            },
            source_hash="source-v2",
        )
        return fit_map_v1, fit_map_v2

    def test_pinned_revision_uses_its_linked_description_and_fingerprint(self) -> None:
        fit_map_v1, _fit_map_v2 = self._create_revision_history()

        payload = self.materializer.build(
            "notion_578", "feras_input", revision_id=fit_map_v1
        )

        self.assertEqual(
            payload["context"]["job_description"]["content"],
            "DESCRICAO CANONICA V1",
        )
        self.assertEqual(payload["context"]["application"]["fingerprint"], "fp-v1")
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("DESCRICAO CANONICA V2", serialized)
        self.assertNotIn("fp-v2", serialized)

    def test_export_rejects_lookalike_application_tree_and_accepts_declared_temp_root(self) -> None:
        self._create_revision_history()
        lookalike = (
            self.root
            / "lookalike"
            / "applications_v2"
            / "notion_578"
            / "derived"
            / "feras_input.json"
        )

        with self.assertRaisesRegex(ValueError, "application-scoped or temporary"):
            self.materializer.export_json("notion_578", "feras_input", lookalike)

        with tempfile.TemporaryDirectory() as temporary_dir:
            temporary_root = Path(temporary_dir)
            receipt = self.materializer.export_json(
                "notion_578",
                "feras_input",
                temporary_root / "feras_input.json",
                temporary_root=temporary_root,
            )
        self.assertEqual(receipt.application_id, "notion_578")

    @contextmanager
    def _runtime(self):
        career_state = self.root / ".career-state"
        applications_dir = career_state / "applications_v2"
        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", applications_dir
        ), mock.patch.object(
            application_context, "canonical_database", return_value=self.database
        ), mock.patch.object(intake, "ROOT", self.root), mock.patch.object(
            intake, "CAREER_STATE", career_state
        ), mock.patch.object(intake, "INBOX", self.root / "inbox"), mock.patch.object(
            multiagent, "ROOT", self.root
        ):
            yield

    def test_real_request_uses_in_memory_sqlite_context_not_contaminated_json(self) -> None:
        with self._runtime():
            source = intake.JobSource(
                source_type="notion_record",
                source_id="578",
                company="Conexa",
                role="Diretor de Growth",
                text="Descricao Conexa " * 80,
                record_id="578",
                preferred_id="notion_578",
            )
            record = intake.start_intake(source, database=self.database)
            revision_id = self.analysis.create_revision(
                record.application_id,
                {
                    "metadata": {"job_fingerprint": record.fingerprint},
                    "stories": [
                        {
                            "story_key": "canonical",
                            "narrative": "CANONICAL SQLITE STORY",
                        }
                    ],
                },
                source_hash=record.fingerprint,
            )
            paths = application_context.paths_for(record.application_id)
            write_json(
                paths.fit_map,
                {"story": "JSON CONTAMINADO", "revision_id": revision_id},
            )

            result = multiagent.write_request(
                "feras", application_id=record.application_id, database=self.database
            )
            payload = read_json(self.root / result["request_json"])

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertIn("CANONICAL SQLITE STORY", serialized)
        self.assertNotIn("JSON CONTAMINADO", serialized)
        self.assertFalse(
            any(
                item.endswith("fit_map.json") or "/derived/" in item
                for item in payload["allowed_files"]
            )
        )
        self.assertTrue(
            any("in-memory" in rule.lower() or "sqlite" in rule.lower()
                for rule in payload["operational_rules"])
        )


if __name__ == "__main__":
    unittest.main()
