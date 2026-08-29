from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career.services import application_context
from career.services.database import Database
from career.services.database import RuntimePersistenceMode
from career.services.harness_supervisor import HarnessSupervisor
from career.services.pipeline_intent import PipelineIntentStore


class RuntimeRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.db = Database(self.root / "control-plane" / "career.db")
        self.db.init_schema()
        self.db.execute(
            """INSERT INTO applications
               (id, company, role, created_at, updated_at, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("app_runtime", "Conexa", "Diretor de Growth", "2026-08-28", "2026-08-28", "active"),
        )
        self.supervisor = HarnessSupervisor(self.root)
        self.supervisor.db.close()
        self.supervisor.db = self.db
        self.registry_path = self.root / ".career-state" / "session_registry.json"

    def tearDown(self) -> None:
        self.db.close()
        self.tempdir.cleanup()

    def test_session_binding_survives_without_json_registry(self) -> None:
        with mock.patch.object(application_context, "SESSION_REGISTRY", self.registry_path):
            application_context.register_session(
                runtime="hermes",
                profile_id="profile",
                session_id="session-sqlite",
                application_id="app_runtime",
                channel="telegram",
                database=self.db,
            )
            self.registry_path.unlink()

            resolved = application_context.resolve_session(
                runtime="hermes",
                profile_id="profile",
                session_id="session-sqlite",
                database=self.db,
            )

        self.assertEqual(resolved, "app_runtime")

    def test_sqlite_only_never_falls_back_to_json_session_registry(self) -> None:
        registry = self.registry_path
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            '{"sessions":{"hermes:profile:json-only":{"application_id":"app_runtime"}}}',
            encoding="utf-8",
        )
        sqlite_only = Database(
            self.root / "control-plane" / "career.db",
            persistence_mode=RuntimePersistenceMode.SQLITE_ONLY,
        )
        try:
            resolved = application_context.resolve_session(
                runtime="hermes",
                profile_id="profile",
                session_id="json-only",
                database=sqlite_only,
            )
        finally:
            sqlite_only.close()
        self.assertIsNone(resolved)

    def test_generic_continuation_uses_bound_application_and_pipeline_intent(self) -> None:
        runtime_context = {
            "runtime": "hermes",
            "profile_id": "profile",
            "session_id": "session-continue",
        }
        with mock.patch.object(application_context, "SESSION_REGISTRY", self.registry_path):
            application_context.register_session(
                runtime="hermes",
                profile_id="profile",
                session_id="session-continue",
                application_id="app_runtime",
                channel="telegram",
                database=self.db,
            )
            self.registry_path.unlink()
        PipelineIntentStore(self.root).bind(
            application_id="app_runtime",
            session_key="hermes:profile:session-continue",
            requested_steps=["cv", "onedrive", "notion"],
        )
        captured: dict[str, object] = {}

        def fake_pipeline(message: str, **kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {
                "status": "completed",
                "application_id": kwargs["application_id"],
                "stages": [{"status": "completed"}],
            }

        with mock.patch.object(self.supervisor, "_execute_pipeline_request", side_effect=fake_pipeline):
            result = self.supervisor.handle_message(
                "ok, então use processe-a-vaga",
                channel="telegram",
                execute=True,
                runtime_context=runtime_context,
            )

        self.assertEqual(result["result"]["application_id"], "app_runtime")
        self.assertEqual(captured["application_id"], "app_runtime")
        self.assertEqual(captured["requested_steps"], ["cv", "onedrive", "notion"])

    def test_notion_duplicate_precheck_has_deterministic_route(self) -> None:
        decision = self.supervisor.classify(
            "pode pesquisar se já existe vaga registrada no Notion? "
            "se sim informe o id antes da escrita real; se não proceda a escrita real"
        )

        self.assertEqual(decision.workflow, "notion_preflight")
        self.assertTrue(decision.requires_approval)

    def test_pipeline_without_executed_stage_is_blocked(self) -> None:
        with mock.patch(
            "career.services.intake.resume",
            return_value={"next_required_step": "unknown_step"},
        ):
            result = self.supervisor._execute_pipeline_request(
                "continue",
                requested_steps=["cv"],
                application_id="app_runtime",
                model=None,
                variant=None,
                runtime_context=None,
                channel="cli",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocker_reason"], "no_pipeline_stage_executed")

    def test_pending_input_from_another_session_does_not_hijack_turn(self) -> None:
        pending_path = self.root / ".career-state" / "harness" / "pending_input.json"
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        pending_path.write_text(
            '{"status":"awaiting_input","input_kind":"linkedin_job_url",'
            '"session_id":"old-session","display_text":"Envie a URL da vaga."}',
            encoding="utf-8",
        )

        result = self.supervisor.handle_message(
            "ok, então use processe-a-vaga",
            channel="telegram",
            execute=True,
            runtime_context={
                "runtime": "hermes",
                "profile_id": "profile",
                "session_id": "new-session",
            },
        )

        self.assertNotEqual(result["result"].get("input_kind"), "linkedin_job_url")


if __name__ == "__main__":
    unittest.main()
