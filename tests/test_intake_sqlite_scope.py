from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from career import cli
from career.services import agent_guard, application_context, intake
from career.services.harness_supervisor import HarnessSupervisor
from career.services.database import Database
from career.utils import ValidationFailure
from career.utils import sha256_text
from career.workflow.state_store import WorkflowStateStore


class IntakeSQLiteScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_dir.cleanup)
        self.root = Path(self.temporary_dir.name)
        self.career_state = self.root / ".career-state"
        self.applications_dir = self.career_state / "applications_v2"
        self.database = Database(db_path=self.career_state / "career.db")
        self.addCleanup(self.database.close)

    def _source(self, *, application_id: str, company: str, role: str, text: str):
        return intake.JobSource(
            source_type="notion_record",
            source_id=application_id.removeprefix("notion_"),
            company=company,
            role=role,
            text=text,
            record_id=application_id.removeprefix("notion_"),
            preferred_id=application_id,
        )

    def _start(self, source):
        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ), mock.patch.object(intake, "ROOT", self.root), mock.patch.object(
            intake, "CAREER_STATE", self.career_state
        ):
            return intake.start_intake(source, database=self.database)

    def test_notion_intake_commits_identity_and_description_before_compatibility_materialization(self):
        source = self._source(
            application_id="notion_578",
            company="Conexa",
            role="Diretor de Growth",
            text="Descricao Conexa " * 80,
        )
        observed = {"description_rows_before_materialization": None}
        original_write_text = intake.write_text

        def observe_materialization(path: Path, text: str) -> None:
            if path.name == "job_description.md":
                observed["description_rows_before_materialization"] = self.database.fetch_one(
                    "SELECT COUNT(*) AS total FROM job_descriptions WHERE application_id = ?",
                    (source.application_id,),
                )["total"]
            original_write_text(path, text)

        with mock.patch.object(intake, "write_text", side_effect=observe_materialization):
            record = self._start(source)

        self.assertEqual(record.application_id, source.preferred_id)
        self.assertEqual(record.fingerprint, sha256_text(source.text))
        self.assertEqual(observed["description_rows_before_materialization"], 1)
        self.assertEqual(
            self.database.fetch_one(
                "SELECT content, content_hash FROM job_descriptions WHERE application_id = ?",
                (source.application_id,),
            ),
            {"content": source.text, "content_hash": sha256_text(source.text)},
        )
        self.assertEqual(
            self.database.fetch_one(
                "SELECT fingerprint FROM job_sources WHERE application_id = ?",
                (source.application_id,),
            )["fingerprint"],
            sha256_text(source.text),
        )

    def test_default_start_intake_persists_to_control_plane_not_legacy_database(self):
        source = self._source(
            application_id="notion_579",
            company="Conexa",
            role="Diretor de Growth",
            text="Descricao Conexa canonica " * 80,
        )

        with self._runtime_context():
            record = intake.start_intake(source)

        canonical_path = self.root / "control-plane" / "career.db"
        canonical = Database(canonical_path)
        self.addCleanup(canonical.close)
        self.assertEqual(record.application_id, source.application_id)
        self.assertEqual(
            canonical.fetch_one(
                "SELECT content FROM job_descriptions WHERE application_id = ?",
                (record.application_id,),
            )["content"],
            source.text,
        )
        self.assertFalse((self.career_state / "career.db").exists())

    def test_public_paste_routes_one_explicit_scope_to_the_ready_pipeline(self):
        saved_path = self.root / "inbox" / "job_descriptions" / "paste.md"

        def save_description(*_args, **_kwargs):
            saved_path.parent.mkdir(parents=True, exist_ok=True)
            saved_path.write_text("Descricao paste " * 80, encoding="utf-8")
            return saved_path

        with self._runtime_context(), mock.patch.object(
            intake.project_service,
            "save_job_description",
            side_effect=save_description,
        ), mock.patch.object(
            intake,
            "_run_ready_pipeline",
            return_value={"status": "ready_for_model_analysis"},
        ) as ready_pipeline:
            result = intake.from_paste(
                company="Conexa",
                role="Diretor de Growth",
                text="Descricao paste " * 80,
                application_id="paste_conexa_579",
            )

        self.assertEqual(result["status"], "ready_for_model_analysis")
        state_store = ready_pipeline.call_args.args[0]
        self.assertEqual(state_store.application_id, "paste_conexa_579")
        canonical = Database(self.root / "control-plane" / "career.db")
        self.addCleanup(canonical.close)
        self.assertEqual(
            canonical.fetch_one(
                "SELECT id FROM applications WHERE id = ?", ("paste_conexa_579",)
            )["id"],
            "paste_conexa_579",
        )

    def test_resume_without_application_scope_fails_closed(self):
        global_store = WorkflowStateStore(path=self.career_state / "workflow_state.json")
        global_store.payload = {
            "active_intake": {"application_id": "notion_578", "job_description_path": "other.md"}
        }
        global_store.save()

        result = intake.resume(state_store=global_store)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "explicit_application_scope_required")

    def test_request_bundle_without_application_scope_does_not_write_file(self):
        output_path = self.root / "intake_request.json"

        with self.assertRaisesRegex(ValueError, "application_id"):
            intake.write_request_bundle(output_path)

        self.assertFalse(output_path.exists())

    def test_guard_rejects_active_intake_from_a_different_application_even_when_fingerprint_matches(self):
        text = "Descricao compartilhada " * 80
        first = self._start(
            self._source(
                application_id="notion_578",
                company="Conexa",
                role="Diretor de Growth",
                text=text,
            )
        )
        second = self._start(
            self._source(
                application_id="notion_900",
                company="People Meet",
                role="Diretor de Operacoes",
                text=text,
            )
        )
        state_store = WorkflowStateStore.for_application(
            first.application_id,
            database=self.database,
            root=self.applications_dir,
        )
        state_store.payload = {
            "active_intake": {
                "application_id": second.application_id,
                "fingerprint": first.fingerprint,
                "job_description_path": str(
                    application_context.paths_for(
                        second.application_id, root=self.applications_dir
                    ).job_description.relative_to(self.root)
                ),
            }
        }
        state_store.save()

        with self._guard_context(), mock.patch.object(
            agent_guard.fit_map_service, "progress_guard"
        ) as progress_guard:
            result = agent_guard.guard(
                application_id=first.application_id,
                fingerprint=first.fingerprint,
                state_store=state_store,
                database=self.database,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "active_intake_application_mismatch")
        progress_guard.assert_not_called()

    def test_cli_guard_accepts_and_propagates_explicit_scope(self):
        with mock.patch.object(
            cli.agent_guard_service,
            "guard",
            return_value={"status": "ok"},
        ) as guard:
            with redirect_stdout(StringIO()):
                exit_code = cli.main(
                    [
                        "agent",
                        "guard",
                        "--application-id",
                        "notion_578",
                        "--fingerprint",
                        "fingerprint-578",
                    ]
                )

        self.assertEqual(exit_code, 0)
        guard.assert_called_once_with(
            application_id="notion_578", fingerprint="fingerprint-578"
        )

    def test_harness_resume_requires_explicit_application_scope_before_resuming(self):
        supervisor = HarnessSupervisor(self.root)
        with mock.patch.object(intake, "resume") as resume:
            result = supervisor._resume_and_continue(
                "continue", model=None, variant=None, application_id=None
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocker_reason"], "explicit_application_scope_required")
        resume.assert_not_called()

    def test_harness_specialist_execution_requires_explicit_application_scope(self):
        supervisor = HarnessSupervisor(self.root)

        result = supervisor.execute_specialist("fit-map", extras={})

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocker_reason"], "explicit_application_scope_required")

    def test_guard_requires_explicit_application_scope_instead_of_global_pointer(self):
        global_state = WorkflowStateStore(path=self.career_state / "workflow_state.json")
        WorkflowStateStore.write_active_pointer(
            application_id="notion_578",
            active_job={"fingerprint": "stale-global"},
            active_intake={"application_id": "notion_578"},
            path=self.career_state / "active_application.json",
        )

        with mock.patch.object(agent_guard, "CAREER_STATE", self.career_state):
            result = agent_guard.guard(state_store=global_state, database=self.database)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("required", result["reason"])

    def test_guard_discards_global_store_when_explicit_scope_is_declared(self):
        record = self._start(
            self._source(
                application_id="notion_578",
                company="Conexa",
                role="Diretor de Growth",
                text="Descricao Conexa " * 80,
            )
        )
        global_state = WorkflowStateStore(path=self.career_state / "workflow_state.json")
        global_state.payload = {
            "active_intake": {
                "application_id": "notion_other",
                "fingerprint": "global-fingerprint",
                "job_description_path": "wrong.md",
            }
        }
        global_state.save()

        with self._guard_context(), mock.patch.object(
            agent_guard.fit_map_service,
            "progress_guard",
            return_value={"next_required_step": "preencher .career-state/fit_map.draft.json"},
        ):
            result = agent_guard.guard(
                application_id=record.application_id,
                fingerprint=record.fingerprint,
                state_store=global_state,
                database=self.database,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["active_intake"]["application_id"], record.application_id)

    def test_guard_rejects_fingerprint_mismatch_before_consulting_draft_or_context(self):
        source = self._source(
            application_id="notion_578",
            company="Conexa",
            role="Diretor de Growth",
            text="Descricao Conexa " * 80,
        )
        record = self._start(source)
        state_store = WorkflowStateStore.for_application(
            record.application_id,
            database=self.database,
            root=self.applications_dir,
        )

        with self._guard_context(), mock.patch.object(
            agent_guard.fit_map_service, "progress_guard"
        ) as progress_guard:
            result = agent_guard.guard(
                application_id=record.application_id,
                fingerprint="fingerprint-incorreto",
                state_store=state_store,
                database=self.database,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "application_fingerprint_mismatch")
        progress_guard.assert_not_called()

    def test_guard_isolates_scoped_application_from_another_application_context(self):
        first = self._start(
            self._source(
                application_id="notion_578",
                company="Conexa",
                role="Diretor de Growth",
                text="Descricao Conexa " * 80,
            )
        )
        second = self._start(
            self._source(
                application_id="notion_900",
                company="People Meet",
                role="Diretor de Operacoes",
                text="Descricao People Meet " * 80,
            )
        )
        first_store = WorkflowStateStore.for_application(
            first.application_id,
            database=self.database,
            root=self.applications_dir,
        )
        first_store.payload = {
            "active_intake": {
                "application_id": first.application_id,
                "fingerprint": first.fingerprint,
                "job_description_path": str(
                    application_context.paths_for(first.application_id, root=self.applications_dir)
                    .job_description.relative_to(self.root)
                ),
            }
        }
        first_store.save()

        with self._guard_context(), mock.patch.object(agent_guard.fit_map_service, "progress_guard", return_value={
            "next_required_step": "preencher .career-state/fit_map.draft.json"
        }) as progress_guard:
            result = agent_guard.guard(
                application_id=first.application_id,
                fingerprint=first.fingerprint,
                state_store=first_store,
                database=self.database,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["active_intake"]["application_id"], first.application_id)
        self.assertNotEqual(result["active_intake"]["application_id"], second.application_id)
        self.assertEqual(progress_guard.call_args.kwargs["job_description_path"], application_context.paths_for(
            first.application_id, root=self.applications_dir
        ).job_description)

    def test_unknown_explicit_application_is_blocked_without_global_fallback(self):
        with self._guard_context():
            result = agent_guard.guard(
                application_id="notion_missing",
                fingerprint="missing-fingerprint",
                database=self.database,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "unknown_application")

    @contextmanager
    def _guard_context(self):
        with mock.patch.object(agent_guard, "ROOT", self.root), mock.patch.object(
            agent_guard, "CAREER_STATE", self.career_state
        ), mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ):
            yield

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
