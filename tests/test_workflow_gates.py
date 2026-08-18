from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from career import cli
from career.services import intake
from career.services import project as project_module
from career.services import database as database_module
from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.tasks import registry
from career.utils import sha256_text
from career.workflow import state_store as state_store_module
from career.workflow.state_store import WorkflowStateStore


class WorkflowGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.db_path = self.root / "runtime.db"
        self.db = Database(db_path=self.db_path)
        self.addCleanup(self.db.close)
        self.application_repository = ApplicationRepository(self.db)
        self.analysis_repository = AnalysisRepository(self.db)
        self.gate_repository = GateRepository(self.db)
        self.primary = self.application_repository.create_application(
            ApplicationIdentity(
                application_id="app-conexa",
                company="Conexa",
                role="Diretor de Growth",
                notion_id="578",
                fingerprint="fp-conexa",
            )
        )
        self.secondary = self.application_repository.create_application(
            ApplicationIdentity(
                application_id="app-people",
                company="People Meet",
                role="Diretor de Operacoes",
                notion_id="579",
                fingerprint="fp-people",
            )
        )

    def test_record_rejects_missing_application_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "application_id"):
            self.gate_repository.record(
                GateReceipt(
                    application_id="",
                    application_fingerprint="fp-conexa",
                    run_id="run-1",
                    gate="fit_map_draft_valid",
                    validator="fit_map.validate_draft",
                    input_hash=self._hash("draft"),
                    output_hash=self._hash("validated"),
                )
            )

    def test_record_rejects_missing_required_hashes_and_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "validator"):
            self.gate_repository.record(
                GateReceipt(
                    application_id=self.primary.application_id,
                    application_fingerprint=self.primary.fingerprint or "",
                    run_id="run-1",
                    gate="fit_map_draft_valid",
                    validator="",
                    input_hash=self._hash("draft"),
                    output_hash=self._hash("validated"),
                )
            )

        with self.assertRaisesRegex(ValueError, "input_hash"):
            self.gate_repository.record(
                GateReceipt(
                    application_id=self.primary.application_id,
                    application_fingerprint=self.primary.fingerprint or "",
                    run_id="run-1",
                    gate="fit_map_draft_valid",
                    validator="fit_map.validate_draft",
                    input_hash="",
                    output_hash=self._hash("validated"),
                )
            )

        with self.assertRaisesRegex(ValueError, "output_hash"):
            self.gate_repository.record(
                GateReceipt(
                    application_id=self.primary.application_id,
                    application_fingerprint=self.primary.fingerprint or "",
                    run_id="run-1",
                    gate="fit_map_draft_valid",
                    validator="fit_map.validate_draft",
                    input_hash=self._hash("draft"),
                    output_hash="",
                )
            )

    def test_record_rejects_unknown_application_and_wrong_fingerprint(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown application"):
            self.gate_repository.record(
                GateReceipt(
                    application_id="missing-app",
                    application_fingerprint="fp-missing",
                    run_id="run-1",
                    gate="fit_map_draft_valid",
                    validator="fit_map.validate_draft",
                    input_hash=self._hash("draft"),
                    output_hash=self._hash("validated"),
                )
            )

        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.gate_repository.record(
                GateReceipt(
                    application_id=self.primary.application_id,
                    application_fingerprint="fp-wrong",
                    run_id="run-1",
                    gate="fit_map_draft_valid",
                    validator="fit_map.validate_draft",
                    input_hash=self._hash("draft"),
                    output_hash=self._hash("validated"),
                )
            )

    def test_record_rejects_revision_mismatch_and_invalid_transition(self) -> None:
        revision_id = self._create_fit_map_revision(self.primary.application_id, "fp-conexa")
        other_revision_id = self._create_fit_map_revision(
            self.secondary.application_id, "fp-people"
        )

        with self.assertRaisesRegex(ValueError, "revision"):
            self.gate_repository.record(
                GateReceipt(
                    application_id=self.primary.application_id,
                    application_fingerprint=self.primary.fingerprint or "",
                    run_id="run-1",
                    gate="fit_map_built",
                    validator="fit_map.build",
                    input_hash=self._hash("build-input"),
                    output_hash=self._hash("build-output"),
                    revision_id=other_revision_id,
                )
            )

        with self.assertRaisesRegex(ValueError, "prerequisite"):
            self.gate_repository.record(
                GateReceipt(
                    application_id=self.primary.application_id,
                    application_fingerprint=self.primary.fingerprint or "",
                    run_id="run-1",
                    gate="fit_map_scored",
                    validator="fit_map.score",
                    input_hash=self._hash("score-input"),
                    output_hash=self._hash("score-output"),
                    revision_id=revision_id,
                )
            )

    def test_record_is_idempotent_for_equivalent_receipt(self) -> None:
        receipt = GateReceipt(
            application_id=self.primary.application_id,
            application_fingerprint=self.primary.fingerprint or "",
            run_id="run-1",
            gate="fit_map_draft_valid",
            validator="fit_map.validate_draft",
            input_hash=self._hash("draft"),
            output_hash=self._hash("validated"),
        )

        first = self.gate_repository.record(receipt)
        second = self.gate_repository.record(
            GateReceipt(
                application_id=receipt.application_id,
                application_fingerprint=receipt.application_fingerprint,
                run_id="run-2",
                gate=receipt.gate,
                validator=receipt.validator,
                input_hash=receipt.input_hash,
                output_hash=receipt.output_hash,
            )
        )

        self.assertEqual(first, second)
        rows = self.db.fetch_all(
            "SELECT receipt_id FROM validation_receipts WHERE application_id = ?",
            (self.primary.application_id,),
        )
        self.assertEqual(rows, [{"receipt_id": first}])

    def test_is_satisfied_is_scoped_per_application(self) -> None:
        self.gate_repository.record(
            GateReceipt(
                application_id=self.primary.application_id,
                application_fingerprint=self.primary.fingerprint or "",
                run_id="run-1",
                gate="fit_map_draft_valid",
                validator="fit_map.validate_draft",
                input_hash=self._hash("draft"),
                output_hash=self._hash("validated"),
            )
        )

        self.assertTrue(
            self.gate_repository.is_satisfied(
                self.primary.application_id, "fit_map_draft_valid"
            )
        )
        self.assertFalse(
            self.gate_repository.is_satisfied(
                self.secondary.application_id, "fit_map_draft_valid"
            )
        )

    def test_next_required_step_advances_only_after_valid_receipts(self) -> None:
        compatibility_path = self.root / "workflow_state.json"
        compatibility_path.write_text(
            '{"completed_states":["fit_map_validated"],"active_job":{"fingerprint":"stale"}}',
            encoding="utf-8",
        )
        fit_map_path = self.root / "fit_map.json"
        fit_map_path.write_text('{"fingerprint":"fp-conexa"}', encoding="utf-8")
        state_store = WorkflowStateStore(
            application_id=self.primary.application_id,
            database=self.db,
            path=compatibility_path,
        )

        payload = state_store.load()
        self.assertEqual(payload["completed_states"], [])
        self.assertEqual(payload["next_required_step"], "fill_fit_map_draft")

        self.gate_repository.record(
            GateReceipt(
                application_id=self.primary.application_id,
                application_fingerprint=self.primary.fingerprint or "",
                run_id="run-1",
                gate="fit_map_draft_valid",
                validator="fit_map.validate_draft",
                input_hash=self._hash("draft"),
                output_hash=self._hash("validated"),
            )
        )
        self.assertEqual(
            self.gate_repository.next_required_step(self.primary.application_id),
            "build_fit_map",
        )

        revision_id = self._create_fit_map_revision(self.primary.application_id, "fp-conexa")
        self.gate_repository.record(
            GateReceipt(
                application_id=self.primary.application_id,
                application_fingerprint=self.primary.fingerprint or "",
                run_id="run-1",
                gate="fit_map_built",
                validator="fit_map.build",
                input_hash=self._hash("build-input"),
                output_hash=self._hash("build-output"),
                revision_id=revision_id,
            )
        )
        self.assertEqual(
            self.gate_repository.next_required_step(self.primary.application_id),
            "score_fit_map",
        )

        self.gate_repository.record(
            GateReceipt(
                application_id=self.primary.application_id,
                application_fingerprint=self.primary.fingerprint or "",
                run_id="run-1",
                gate="fit_map_scored",
                validator="fit_map.score",
                input_hash=self._hash("score-input"),
                output_hash=self._hash("score-output"),
                revision_id=revision_id,
            )
        )
        self.assertEqual(
            self.gate_repository.next_required_step(self.primary.application_id),
            "validate_fit_map",
        )

        self.gate_repository.record(
            GateReceipt(
                application_id=self.primary.application_id,
                application_fingerprint=self.primary.fingerprint or "",
                run_id="run-1",
                gate="fit_map_validated",
                validator="fit_map.validate",
                input_hash=self._hash("validate-input"),
                output_hash=self._hash("validate-output"),
                revision_id=revision_id,
            )
        )
        self.assertEqual(
            self.gate_repository.next_required_step(self.primary.application_id),
            "build_cv",
        )

        payload = state_store.load()
        self.assertEqual(
            payload["completed_states"],
            [
                "fit_map_built",
                "fit_map_draft_valid",
                "fit_map_scored",
                "fit_map_validated",
            ],
        )
        self.assertEqual(payload["next_required_step"], "build_cv")

    def test_run_task_requires_application_scoped_store(self) -> None:
        draft = self.root / "fit_map.draft.json"
        draft.write_text("{}", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "application-scoped"):
            registry.run_task(
                "fit_map.validate_draft",
                arguments={"path": str(draft)},
            )

    def test_run_task_records_receipt_without_writing_workflow_json(self) -> None:
        draft = self.root / "fit_map.draft.json"
        draft.write_text("{}", encoding="utf-8")
        compatibility_path = self.root / "global-workflow-state.json"
        state_store = WorkflowStateStore(
            application_id=self.primary.application_id,
            database=self.db,
            path=compatibility_path,
        )

        with mock.patch.object(
            registry.fit_map_service,
            "validate_draft",
            return_value={"status": "ok"},
        ):
            result = registry.run_task(
                "fit_map.validate_draft",
                arguments={"path": str(draft)},
                state_store=state_store,
            )

        self.assertEqual(result, {"status": "ok"})
        self.assertTrue(
            self.gate_repository.is_satisfied(
                self.primary.application_id, "fit_map_draft_valid"
            )
        )
        self.assertFalse(compatibility_path.exists())
        payload = state_store.load()
        self.assertEqual(payload["next_required_step"], "build_fit_map")
        self.assertEqual(len(payload["task_history"]), 1)
        self.assertEqual(payload["task_history"][0]["task"], "fit_map.validate_draft")

    def test_run_task_generates_distinct_implicit_run_ids_per_application(self) -> None:
        draft = self.root / "fit_map.draft.json"
        draft.write_text("{}", encoding="utf-8")
        first_store = WorkflowStateStore(
            application_id=self.primary.application_id,
            database=self.db,
            path=self.root / "app-a" / "workflow_state.json",
        )
        second_store = WorkflowStateStore(
            application_id=self.secondary.application_id,
            database=self.db,
            path=self.root / "app-b" / "workflow_state.json",
        )

        with mock.patch.object(
            registry.fit_map_service,
            "validate_draft",
            return_value={"status": "ok"},
        ):
            registry.run_task(
                "fit_map.validate_draft",
                arguments={"path": str(draft)},
                state_store=first_store,
            )
            registry.run_task(
                "fit_map.validate_draft",
                arguments={"path": str(draft)},
                state_store=second_store,
            )

        rows = self.db.fetch_all(
            """SELECT application_id, run_id
               FROM validation_receipts
               ORDER BY application_id, created_at, receipt_id"""
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["application_id"], self.primary.application_id)
        self.assertEqual(rows[1]["application_id"], self.secondary.application_id)
        self.assertNotEqual(rows[0]["run_id"], rows[1]["run_id"])

    def test_for_application_defaults_to_canonical_database_without_keyword_argument(self) -> None:
        career_state = self.root / ".career-state"
        applications_root = career_state / "applications_v2"
        canonical_db = Database(db_path=career_state / "career.db")
        self.addCleanup(canonical_db.close)
        ApplicationRepository(canonical_db).create_application(
            ApplicationIdentity(
                application_id="app-canonical",
                company="Canonical",
                role="Director",
                fingerprint="fp-canonical",
            )
        )

        with mock.patch.object(database_module, "CAREER_STATE", career_state), mock.patch.object(
            state_store_module, "CAREER_STATE", career_state
        ):
            store = WorkflowStateStore.for_application(
                "app-canonical",
                root=applications_root,
            )
            payload = store.load()

        self.assertEqual(store.application_id, "app-canonical")
        self.assertIsNotNone(store.database)
        self.assertEqual(payload["application_id"], "app-canonical")

    def test_arbitrary_parent_workflow_state_path_stays_file_backed_compatibility_store(
        self,
    ) -> None:
        compatibility_path = self.root / "tmp" / "application" / "workflow_state.json"
        store = WorkflowStateStore(path=compatibility_path)
        store.payload = {
            "completed_states": ["legacy_state"],
            "task_history": [{"task": "legacy"}],
            "active_job": {"fingerprint": "legacy-fingerprint"},
            "active_intake": {"application_id": "legacy-app"},
        }

        store.save()

        self.assertIsNone(store._resolved_application_id())
        self.assertTrue(compatibility_path.exists())
        payload = store.load()
        self.assertEqual(payload["completed_states"], ["legacy_state"])
        self.assertEqual(payload["task_history"], [{"task": "legacy"}])
        self.assertEqual(payload["active_job"], {"fingerprint": "legacy-fingerprint"})
        self.assertEqual(payload["active_intake"], {"application_id": "legacy-app"})

    def test_unregistered_canonical_shape_loads_metadata_without_file_gate_authority(
        self,
    ) -> None:
        compatibility_path = (
            self.root
            / ".career-state"
            / "applications_v2"
            / "notion_578"
            / "workflow_state.json"
        )
        compatibility_path.parent.mkdir(parents=True, exist_ok=True)
        compatibility_path.write_text(
            json.dumps(
                {
                    "completed_states": ["bogus_file_gate"],
                    "task_history": [{"task": "bogus.local"}],
                    "fingerprints": {"bogus.local": {"status": "ok"}},
                    "active_intake": {
                        "application_id": "notion_578",
                        "company": "Conexa",
                        "role": "Diretor de Growth",
                    },
                }
            ),
            encoding="utf-8",
        )

        payload = WorkflowStateStore(path=compatibility_path).load()

        self.assertEqual(payload["application_id"], "notion_578")
        self.assertEqual(payload["completed_states"], [])
        self.assertEqual(payload["task_history"], [])
        self.assertEqual(payload["fingerprints"], {})
        self.assertEqual(payload["active_intake"]["company"], "Conexa")

    def test_global_pointer_is_display_metadata_and_scoped_resume_reads_state(
        self,
    ) -> None:
        job_description = self.root / "inbox" / "job_descriptions" / "conexa.md"
        job_description.parent.mkdir(parents=True, exist_ok=True)
        job_description.write_text("Conexa job description", encoding="utf-8")
        app_store = WorkflowStateStore(
            application_id=self.primary.application_id,
            database=self.db,
            path=self.root / ".career-state" / "applications_v2" / self.primary.application_id / "workflow_state.json",
        )
        app_store.payload = {
            "active_job": {"path": "inbox/job_descriptions/conexa.md", "fingerprint": "fp-conexa"},
            "active_intake": {
                "application_id": self.primary.application_id,
                "source_type": "notion_record",
                "source_id": "578",
                "company": "Conexa",
                "role": "Diretor de Growth",
                "job_description_path": "inbox/job_descriptions/conexa.md",
                "next_required_step": "fill_fit_map_draft",
                "status": "fit_map_template_ready",
                "updated_at": "2026-08-18T00:00:00+00:00",
            },
        }
        app_store.save()
        global_store = WorkflowStateStore(path=self.root / ".career-state" / "workflow_state.json")

        with mock.patch.object(intake, "CAREER_STATE", self.root / ".career-state"), mock.patch.object(
            state_store_module, "CAREER_STATE", self.root / ".career-state"
        ), mock.patch.object(intake, "ROOT", self.root):
            intake._sync_global_active_pointer(app_store, global_store)
            resumed = intake.resume(
                state_store=WorkflowStateStore(
                    application_id=self.primary.application_id,
                    database=self.db,
                    path=app_store.path,
                ),
                application_id=self.primary.application_id,
            )

        self.assertTrue(global_store.path.exists())
        self.assertFalse((self.root / ".career-state" / "active_application.json").exists())
        mirrored = json.loads(global_store.path.read_text(encoding="utf-8"))
        self.assertEqual(mirrored["application_id"], self.primary.application_id)
        self.assertEqual(mirrored["active_intake"]["application_id"], self.primary.application_id)
        self.assertEqual(resumed["status"], "active_intake_ready")
        self.assertEqual(resumed["active_intake"]["application_id"], self.primary.application_id)

    def test_unknown_active_pointer_is_metadata_only_and_never_a_gate_source(self) -> None:
        career_state = self.root / ".career-state"
        global_state = career_state / "workflow_state.json"
        global_state.parent.mkdir(parents=True, exist_ok=True)
        global_state.write_text(
            json.dumps(
                {
                    "completed_states": ["stale_global_state"],
                    "task_history": [{"task": "stale.global"}],
                    "fingerprints": {"stale.global": {"status": "ok"}},
                }
            ),
            encoding="utf-8",
        )
        pointer = career_state / "active_application.json"
        WorkflowStateStore.write_active_pointer(
            application_id="notion_578",
            active_job={"path": "job_description.md", "fingerprint": "fp-stale"},
            active_intake={
                "application_id": "notion_578",
                "company": "Conexa",
                "role": "Diretor de Growth",
            },
            path=pointer,
        )

        with mock.patch.object(state_store_module, "CAREER_STATE", career_state), mock.patch.object(
            state_store_module, "DEFAULT_STATE_PATH", global_state
        ), mock.patch.object(database_module, "CAREER_STATE", career_state):
            payload = WorkflowStateStore().load()

        self.assertEqual(payload["application_id"], "notion_578")
        self.assertEqual(payload["completed_states"], [])
        self.assertEqual(payload["task_history"], [])
        self.assertEqual(payload["fingerprints"], {})
        self.assertEqual(payload["active_intake"]["company"], "Conexa")

    def test_unscoped_store_ignores_stale_global_workflow_state_as_pointer(self) -> None:
        career_state = self.root / ".career-state"
        global_state = career_state / "workflow_state.json"
        global_state.parent.mkdir(parents=True, exist_ok=True)
        global_state.write_text(
            json.dumps(
                {
                    "active_intake": {"application_id": "notion_578"},
                    "completed_states": ["stale_global_state"],
                }
            ),
            encoding="utf-8",
        )

        with mock.patch.object(state_store_module, "CAREER_STATE", career_state), mock.patch.object(
            state_store_module, "DEFAULT_STATE_PATH", global_state
        ), mock.patch.object(database_module, "CAREER_STATE", career_state):
            payload = WorkflowStateStore().load()

        self.assertIsNone(payload["active_intake"])
        self.assertEqual(payload["active_application_id"], None)
        self.assertEqual(payload["completed_states"], [])

    def test_cli_workflow_run_task_requires_scope_before_invoking_registry(self) -> None:
        draft = self.root / "fit_map.draft.json"
        draft.write_text("{}", encoding="utf-8")
        stdout = io.StringIO()

        with mock.patch.object(state_store_module, "CAREER_STATE", self.root / ".career-state"), mock.patch.object(
            state_store_module, "DEFAULT_STATE_PATH", self.root / ".career-state" / "workflow_state.json"
        ), mock.patch.object(cli, "run_task") as run_task_mock, redirect_stdout(stdout):
            exit_code = cli.main(
                [
                    "workflow",
                    "run-task",
                    "fit_map.validate_draft",
                    "--arguments",
                    json.dumps({"path": str(draft)}),
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertFalse(run_task_mock.called)
        self.assertIn("--application-id", stdout.getvalue())

    def test_cli_workflow_reset_state_requires_scope_before_reset(self) -> None:
        stdout = io.StringIO()

        with mock.patch.object(state_store_module, "CAREER_STATE", self.root / ".career-state"), mock.patch.object(
            state_store_module, "DEFAULT_STATE_PATH", self.root / ".career-state" / "workflow_state.json"
        ), redirect_stdout(stdout):
            exit_code = cli.main(["workflow", "reset-state"])

        self.assertEqual(exit_code, 1)
        self.assertIn("--application-id", stdout.getvalue())

    def test_cli_workflow_run_pipeline_requires_explicit_application_id(
        self,
    ) -> None:
        canonical_db = Database(db_path=self.root / ".career-state" / "career.db")
        self.addCleanup(canonical_db.close)
        ApplicationRepository(canonical_db).create_application(
            ApplicationIdentity(
                application_id=self.primary.application_id,
                company=self.primary.company,
                role=self.primary.role,
                notion_id=self.primary.notion_id,
                fingerprint=self.primary.fingerprint,
            )
        )
        pointer_path = self.root / ".career-state" / "active_application.json"
        WorkflowStateStore.write_active_pointer(
            application_id=self.primary.application_id,
            active_job={"fingerprint": "fp-conexa"},
            active_intake={
                "application_id": self.primary.application_id,
                "job_description_path": "inbox/job_descriptions/conexa.md",
            },
            path=pointer_path,
        )
        captured_store: dict[str, WorkflowStateStore] = {}
        stdout = io.StringIO()

        def _fake_run_pipeline(task_names, arguments, *, state_store):
            captured_store["state_store"] = state_store
            return {"status": "ok", "tasks": list(task_names), "arguments": arguments}

        with mock.patch.object(state_store_module, "CAREER_STATE", self.root / ".career-state"), mock.patch.object(
            state_store_module, "DEFAULT_STATE_PATH", self.root / ".career-state" / "workflow_state.json"
        ), mock.patch.object(database_module, "CAREER_STATE", self.root / ".career-state"), mock.patch.object(
            cli, "run_pipeline", side_effect=_fake_run_pipeline
        ), redirect_stdout(stdout):
            exit_code = cli.main(
                [
                    "workflow",
                    "run-pipeline",
                    "fit_map.validate_draft",
                    "fit_map.build",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertNotIn("state_store", captured_store)
        self.assertIn("requires --application-id", stdout.getvalue())

    def test_cli_workflow_reset_state_clears_active_pointer_before_unscoped_commands(
        self,
    ) -> None:
        career_state = self.root / ".career-state"
        canonical_db = Database(db_path=career_state / "career.db")
        self.addCleanup(canonical_db.close)
        ApplicationRepository(canonical_db).create_application(
            ApplicationIdentity(
                application_id=self.primary.application_id,
                company=self.primary.company,
                role=self.primary.role,
                notion_id=self.primary.notion_id,
                fingerprint=self.primary.fingerprint,
            )
        )
        scoped_store = WorkflowStateStore(
            application_id=self.primary.application_id,
            database=canonical_db,
            path=career_state / "applications_v2" / self.primary.application_id / "workflow_state.json",
        )
        scoped_store.payload = {
            "active_job": {"fingerprint": self.primary.fingerprint},
            "active_intake": {
                "application_id": self.primary.application_id,
                "job_description_path": "inbox/job_descriptions/conexa.md",
                "next_required_step": "fill_fit_map_draft",
            },
        }
        scoped_store.save()
        pointer_path = career_state / "active_application.json"
        WorkflowStateStore.write_active_pointer(
            application_id=self.primary.application_id,
            active_job={"fingerprint": self.primary.fingerprint},
            active_intake={
                "application_id": self.primary.application_id,
                "job_description_path": "inbox/job_descriptions/conexa.md",
            },
            path=pointer_path,
        )
        draft = self.root / "fit_map.draft.json"
        draft.write_text("{}", encoding="utf-8")
        reset_stdout = io.StringIO()
        task_stdout = io.StringIO()
        pipeline_stdout = io.StringIO()

        with mock.patch.object(state_store_module, "CAREER_STATE", career_state), mock.patch.object(
            state_store_module, "DEFAULT_STATE_PATH", career_state / "workflow_state.json"
        ), mock.patch.object(database_module, "CAREER_STATE", career_state), redirect_stdout(reset_stdout):
            reset_exit = cli.main(
                ["workflow", "reset-state", "--application-id", self.primary.application_id]
            )

        self.assertEqual(reset_exit, 0)
        self.assertFalse(pointer_path.exists())

        with mock.patch.object(state_store_module, "CAREER_STATE", career_state), mock.patch.object(
            state_store_module, "DEFAULT_STATE_PATH", career_state / "workflow_state.json"
        ), mock.patch.object(database_module, "CAREER_STATE", career_state), mock.patch.object(
            cli, "run_task"
        ) as run_task_mock, redirect_stdout(task_stdout):
            task_exit = cli.main(
                [
                    "workflow",
                    "run-task",
                    "fit_map.validate_draft",
                    "--arguments",
                    json.dumps({"path": str(draft)}),
                ]
            )

        self.assertEqual(task_exit, 1)
        self.assertFalse(run_task_mock.called)
        self.assertIn("--application-id", task_stdout.getvalue())

        with mock.patch.object(state_store_module, "CAREER_STATE", career_state), mock.patch.object(
            state_store_module, "DEFAULT_STATE_PATH", career_state / "workflow_state.json"
        ), mock.patch.object(database_module, "CAREER_STATE", career_state), mock.patch.object(
            cli, "run_pipeline"
        ) as run_pipeline_mock, redirect_stdout(pipeline_stdout):
            pipeline_exit = cli.main(
                [
                    "workflow",
                    "run-pipeline",
                    "fit_map.validate_draft",
                ]
            )

        self.assertEqual(pipeline_exit, 1)
        self.assertFalse(run_pipeline_mock.called)
        self.assertIn("--application-id", pipeline_stdout.getvalue())

    def test_diagnose_runtime_marks_global_workflow_state_non_authoritative(self) -> None:
        career_state = self.root / ".career-state"
        canonical_db = Database(db_path=career_state / "career.db")
        self.addCleanup(canonical_db.close)
        ApplicationRepository(canonical_db).create_application(
            ApplicationIdentity(
                application_id=self.primary.application_id,
                company=self.primary.company,
                role=self.primary.role,
                notion_id=self.primary.notion_id,
                fingerprint=self.primary.fingerprint,
            )
        )
        workflow_state = career_state / "workflow_state.json"
        workflow_state.parent.mkdir(parents=True, exist_ok=True)
        workflow_state.write_text(
            json.dumps(
                {
                    "completed_states": ["stale-a", "stale-b", "stale-c"],
                    "task_history": [{"task": "stale"} for _ in range(4)],
                }
            ),
            encoding="utf-8",
        )
        WorkflowStateStore.write_active_pointer(
            application_id=self.primary.application_id,
            active_job={"fingerprint": self.primary.fingerprint},
            active_intake={
                "application_id": self.primary.application_id,
                "job_description_path": "inbox/job_descriptions/conexa.md",
            },
            path=career_state / "active_application.json",
        )
        GateRepository(canonical_db).record(
            GateReceipt(
                application_id=self.primary.application_id,
                application_fingerprint=self.primary.fingerprint or "",
                run_id="run-diagnose",
                gate="fit_map_draft_valid",
                validator="fit_map.validate_draft",
                input_hash=self._hash("draft"),
                output_hash=self._hash("validated"),
            )
        )

        with mock.patch.object(project_module, "CAREER_STATE", career_state), mock.patch.object(
            project_module, "ROOT", self.root
        ), mock.patch.object(state_store_module, "CAREER_STATE", career_state), mock.patch.object(
            state_store_module, "DEFAULT_STATE_PATH", workflow_state
        ), mock.patch.object(database_module, "CAREER_STATE", career_state):
            diagnosis = project_module.diagnose_runtime()

        self.assertFalse(diagnosis["workflow_state"]["authoritative"])
        self.assertEqual(diagnosis["workflow_state"]["completed_states"], 1)
        self.assertEqual(diagnosis["workflow_state"]["task_history"], 1)

    def _create_fit_map_revision(self, application_id: str, fingerprint: str) -> str:
        return self.analysis_repository.create_revision(
            application_id,
            {
                "fingerprint": fingerprint,
                "dimensions": [],
                "keywords": [],
                "stories": [],
                "evidence": [],
                "scores": [],
                "objections": [],
            },
            source_hash=self._hash(f"source:{application_id}:{fingerprint}"),
        )

    @staticmethod
    def _hash(value: str) -> str:
        return sha256_text(value)


if __name__ == "__main__":
    unittest.main()
