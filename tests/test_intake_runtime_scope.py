from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from career.services import application_context, intake, multiagent
from career.services.database import Database
from career.services.harness_supervisor import HarnessSupervisor
from career.utils import ValidationFailure


class IntakeRuntimeScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_dir.cleanup)
        self.root = Path(self.temporary_dir.name)
        self.career_state = self.root / ".career-state"
        self.applications_dir = self.career_state / "applications_v2"

    def test_public_paste_runs_real_pipeline_with_injected_canonical_database(self):
        canonical = Database(self.root / "control-plane" / "career.db")
        self.addCleanup(canonical.close)

        with self._runtime_context():
            result = intake.from_paste(
                company="Conexa",
                role="Diretor de Growth",
                text="Descricao paste completa " * 80,
                application_id="paste_conexa_pipeline",
                database=canonical,
            )

        self.assertEqual(result["status"], "ready_for_model_analysis")
        self.assertTrue(
            (self.applications_dir / "paste_conexa_pipeline" / "fit_map.draft.json").is_file()
        )
        self.assertEqual(
            canonical.fetch_one(
                "SELECT id FROM applications WHERE id = ?", ("paste_conexa_pipeline",)
            )["id"],
            "paste_conexa_pipeline",
        )
        self.assertFalse((self.career_state / "career.db").exists())

    def test_multiagent_request_requires_explicit_application_scope(self):
        with self.assertRaisesRegex(ValidationFailure, "application_id"):
            multiagent.write_request("fit-map")

    def test_harness_supervisor_uses_root_control_plane_database(self):
        supervisor = HarnessSupervisor(self.root)
        self.addCleanup(supervisor.db.close)

        self.assertEqual(supervisor.db.db_path, self.root / "control-plane" / "career.db")

    @contextmanager
    def _runtime_context(self):
        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ), mock.patch.object(intake, "ROOT", self.root), mock.patch.object(
            intake, "CAREER_STATE", self.career_state
        ), mock.patch.object(intake, "INBOX", self.root / "inbox"):
            yield


if __name__ == "__main__":
    unittest.main()
