from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career.services import intake
from career.workflow import state_store as state_store_module
from career.workflow.state_store import WorkflowStateStore


class LinkedinIntakeMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)

    def test_saved_job_metadata_hints_resolve_selected_url(self) -> None:
        saved_jobs = self.root / "inbox" / "linkedin_saved_jobs.json"
        saved_jobs.parent.mkdir(parents=True)
        saved_jobs.write_text(
            json.dumps(
                {
                    "extractedAt": "2026-08-14T13:46:50Z",
                    "jobs": [
                        {
                            "jobId": "4453385301",
                            "title": "Gerente de Desenvolvimento de Negócios- Growth",
                            "company": "iFood",
                            "location": "Brasil (Remoto)",
                            "url": "https://www.linkedin.com/jobs/view/4453385301/",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with mock.patch.object(intake, "INBOX", saved_jobs.parent):
            self.assertEqual(
                intake._saved_job_metadata_hints_for_url(
                    "https://www.linkedin.com/jobs/view/4453385301/?trk=public_jobs"
                ),
                {
                    "company": "iFood",
                    "role": "Gerente de Desenvolvimento de Negócios- Growth",
                    "location": "Brasil (Remoto)",
                },
            )

    def test_saved_job_metadata_hints_ignore_unmatched_or_invalid_cache(self) -> None:
        saved_jobs = self.root / "inbox" / "linkedin_saved_jobs.json"
        saved_jobs.parent.mkdir(parents=True)
        saved_jobs.write_text("not-json", encoding="utf-8")

        with mock.patch.object(intake, "INBOX", saved_jobs.parent):
            self.assertEqual(
                intake._saved_job_metadata_hints_for_url(
                    "https://www.linkedin.com/jobs/view/4453385301/"
                ),
                {},
            )

    def test_application_intake_mirrors_pointer_for_global_guard(self) -> None:
        application_store = WorkflowStateStore(
            path=self.root / "application" / "workflow_state.json"
        )
        global_store = WorkflowStateStore(
            path=self.root / "global" / "workflow_state.json"
        )
        application_store.payload = {
            "active_job": {"path": ".career-state/applications_v2/app-a/job_description.md"},
            "active_intake": {
                "application_id": "app-a",
                "job_description_path": ".career-state/applications_v2/app-a/job_description.md",
                "next_required_step": "fill_fit_map_draft",
            },
        }
        application_store.save()

        with mock.patch.object(
            state_store_module, "CAREER_STATE", self.root / ".career-state"
        ):
            intake._sync_global_active_pointer(application_store, global_store)

        mirrored = global_store.load()
        self.assertEqual(mirrored["active_job"], application_store.payload["active_job"])
        self.assertEqual(
            mirrored["active_intake"], application_store.payload["active_intake"]
        )
        self.assertTrue(global_store.path.exists())
        self.assertFalse((self.root / ".career-state" / "active_application.json").exists())


if __name__ == "__main__":
    unittest.main()
