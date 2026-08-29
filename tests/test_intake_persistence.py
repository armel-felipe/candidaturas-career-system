from __future__ import annotations

import unittest
import tempfile
from unittest import mock
from pathlib import Path

from career.services import agent_guard, application_context, derived_context, harness_supervisor, multiagent
from career.utils import read_json, write_json
from career.workflow.state_store import WorkflowStateStore


class IntakePersistenceTests(unittest.TestCase):
    def test_notion_intake_persists_canonical_description_before_template(self):
        """A draft must never be prepared before its Notion source is in SQLite."""
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            career_state = root / ".career-state"
            source_path = root / "inbox" / "job_descriptions" / "notion_578.md"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_text = "# Diretor de Growth\n" + ("Responsabilidade relevante. " * 40)
            source_path.write_text(source_text, encoding="utf-8")
            observed: dict[str, object] = {}

            def assert_persisted_before_template(state_store):
                application_id = state_store.application_id
                self.assertEqual(application_id, "notion_578")
                database = application_context.Database(
                    db_path=root / "control-plane" / "career.db"
                )
                application = database.fetch_one(
                    "SELECT id FROM applications WHERE id = ?", (application_id,)
                )
                description = database.fetch_one(
                    "SELECT content, content_hash FROM job_descriptions WHERE application_id = ?",
                    (application_id,),
                )
                observed["application"] = application
                observed["description"] = description

            def ready_payload(state_store, **kwargs):
                assert_persisted_before_template(state_store)
                return {
                    "status": "ready_for_model_analysis",
                    "application_id": state_store.application_id,
                    "fingerprint": application_context.hashlib.sha256(
                        source_text.encode("utf-8")
                    ).hexdigest(),
                    "job_description_path": ".career-state/applications_v2/notion_578/job_description.md",
                    "next_required_step": "fill_fit_map_draft",
                    "description_chars": len(source_text),
                }

            prepared = {
                "company": "Conexa",
                "role": "Diretor de Growth",
                "job_description_path": str(source_path.relative_to(root)),
                "source_url": "https://www.notion.so/578",
            }
            with mock.patch.object(application_context, "ROOT", root), mock.patch.object(
                application_context, "CAREER_STATE", career_state
            ), mock.patch.object(
                application_context, "APPLICATIONS_DIR", career_state / "applications_v2"
            ), mock.patch.object(agent_guard.intake_service, "ROOT", root), mock.patch.object(
                agent_guard.intake_service, "CAREER_STATE", career_state
            ), mock.patch.object(agent_guard.intake_service, "INBOX", root / "inbox"), mock.patch.object(
                agent_guard.intake_service.notion_service, "notion_config", return_value=("token", "database")
            ), mock.patch.object(
                agent_guard.intake_service.notion_service,
                "prepare_analysis_from_record",
                return_value=prepared,
            ), mock.patch.object(
                agent_guard.intake_service,
                "_run_ready_pipeline",
                side_effect=ready_payload,
            ):
                result = agent_guard.intake_service.from_notion_record(578)

            self.assertEqual(result["application_id"], "notion_578")
            self.assertIsNotNone(observed["application"])
            self.assertEqual(observed["description"]["content"], source_text)

    def test_evaluate_notion_routes_guard_to_application_state(self):
        global_state = WorkflowStateStore(path=Path(self.id()).with_name("workflow_state.json"))
        observed: dict[str, object] = {}

        def fake_from_notion_record(record_id: int, state_store=None, **_kwargs):
            observed["record_id"] = record_id
            observed["intake_state_store"] = state_store
            return {
                "status": "ok",
                "application_id": "notion_578",
                "fingerprint": "fingerprint-578",
                "job_description_path": "inbox/job_descriptions/notion_record_578.md",
                "next_required_step": "fill_fit_map_draft",
                "description_chars": 1200,
            }

        def fake_guard(*, state_store, application_id, fingerprint, **_kwargs):
            observed["guard_state_store"] = state_store
            observed["application_id"] = application_id
            observed["fingerprint"] = fingerprint
            return {"status": "ok", "allowed_next_action": "fill_fit_map_draft"}

        with mock.patch.object(
            agent_guard.intake_service,
            "from_notion_record",
            side_effect=fake_from_notion_record,
        ), mock.patch.object(agent_guard, "guard", side_effect=fake_guard):
            result = agent_guard.evaluate_notion(578, state_store=global_state)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["application_id"], "notion_578")
        self.assertEqual(observed["record_id"], 578)
        self.assertIsNone(observed["intake_state_store"])
        scoped_store = observed["guard_state_store"]
        self.assertIsInstance(scoped_store, WorkflowStateStore)
        self.assertEqual(
            scoped_store.path, application_context.paths_for("notion_578").workflow_state
        )
        self.assertEqual(observed["application_id"], "notion_578")
        self.assertEqual(observed["fingerprint"], "fingerprint-578")

    def test_application_input_packs_read_application_fit_map(self):
        root = Path("/tmp/candidaturas-persistence-test")
        app_dir = root / ".career-state" / "applications_v2" / "notion_578"
        derived_dir = app_dir / "derived"
        job_path = app_dir / "job_description.md"
        job_path.parent.mkdir(parents=True, exist_ok=True)
        job_path.write_text("# Cargo da aplicação\nEmpresa: Conexa\n" + ("Contexto. " * 40), encoding="utf-8")
        write_json(
            app_dir / "workflow_state.json",
            {
                "active_intake": {
                    "job_description_path": ".career-state/applications_v2/notion_578/job_description.md",
                    "fingerprint": "application-fingerprint",
                    "company": "Conexa",
                    "role": "Cargo da aplicação",
                }
            },
        )
        write_json(app_dir / "fit_map.json", {"cargo": "Cargo da aplicação", "empresa": "Conexa"})
        write_json(root / ".career-state" / "fit_map.json", {"cargo": "Cargo global errado", "empresa": "Global"})
        derived_dir.mkdir(parents=True, exist_ok=True)
        write_json(derived_dir / "job_keywords.json", {"top_focus_terms": ["growth"]})

        try:
            with mock.patch.object(derived_context, "ROOT", root), mock.patch.object(
                derived_context, "CAREER_STATE", root / ".career-state"
            ):
                derived_context.configure_derived_dir(derived_dir)
                derived_context.configure_state_store_path(app_dir / "workflow_state.json")
                habilidades = derived_context.build_habilidades_input_pack()
                feras = derived_context.build_feras_input_pack()
        finally:
            import importlib

            importlib.reload(derived_context)

        self.assertEqual(habilidades["job_identity"]["cargo"], "Cargo da aplicação")
        self.assertEqual(feras["job_identity"]["cargo"], "Cargo da aplicação")

    def test_scoped_derived_configuration_keeps_canonical_manifest_name(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            derived_dir = Path(temporary_dir) / "derived"
            derived_dir.mkdir(parents=True)
            try:
                derived_context.configure_derived_dir(derived_dir)
                self.assertEqual(
                    derived_context.DERIVED_MANIFEST_PATH,
                    derived_dir / "manifest.json",
                )
            finally:
                import importlib

                importlib.reload(derived_context)

    def test_generation_request_persists_text_outputs_inside_application(self):
        with mock.patch.object(multiagent, "_prepare_compact_inputs_for_step"), mock.patch.object(
            multiagent,
            "_active_intake",
            return_value={
                "application_id": "notion_578",
                "company": "Conexa",
                "role": "Diretor de Growth",
                "job_description_path": "inbox/job_descriptions/notion_record_578.md",
            },
        ):
            request = multiagent.write_request(
                "feras", application_id="notion_578", extras={"application_id": "notion_578"}
            )

        payload = read_json(Path(request["request_json"]))
        self.assertIn(
            ".career-state/applications_v2/notion_578/feras_formal.md",
            payload["expected_outputs"],
        )

    def test_global_state_migration_rewrites_pointers_to_application(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            career_state = root / ".career-state"
            job_path = root / "inbox" / "job_descriptions" / "job.md"
            job_path.parent.mkdir(parents=True, exist_ok=True)
            job_path.write_text("# Cargo\nEmpresa: Conexa\nDescrição.\n", encoding="utf-8")
            write_json(
                career_state / "workflow_state.json",
                {
                    "active_intake": {
                        "source_type": "notion_record",
                        "source_id": "578",
                        "company": "",
                        "role": "Cargo",
                        "job_description_path": "inbox/job_descriptions/job.md",
                    }
                },
            )
            write_json(career_state / "fit_map.json", {"empresa": "Conexa", "cargo": "Cargo"})

            with mock.patch.object(application_context, "ROOT", root), mock.patch.object(
                application_context, "CAREER_STATE", career_state
            ), mock.patch.object(
                application_context,
                "APPLICATIONS_DIR",
                career_state / "applications_v2",
            ):
                application_context.migrate_global_state(application_id="notion_test")
                migrated = read_json(
                    career_state / "applications_v2" / "notion_test" / "workflow_state.json"
                )

            active = migrated["active_intake"]
            self.assertEqual(
                active["job_description_path"],
                ".career-state/applications_v2/notion_test/job_description.md",
            )
            self.assertEqual(active["application_id"], "notion_test")
            identity = read_json(
                career_state / "applications_v2" / "notion_test" / "identity.json"
            )
            self.assertEqual(identity["company"], "Conexa")

    def test_application_text_artifacts_are_mirrored_to_discoverable_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / ".career-state" / "applications_v2" / "notion_578" / "feras_formal.md"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("# FERAS\n", encoding="utf-8")
            expected = str(source.relative_to(root))

            with mock.patch.object(harness_supervisor, "OUTPUTS", root / "outputs"):
                persisted = harness_supervisor._mirror_application_outputs(
                    root,
                    "feras",
                    {"application_id": "notion_578", "expected_outputs": [expected]},
                )

            mirrored = root / "outputs" / "notion_578_feras_formal.md"
            self.assertTrue(mirrored.exists())
            self.assertEqual(mirrored.read_text(encoding="utf-8"), "# FERAS\n")
            self.assertEqual(persisted[0]["path"], str(mirrored.relative_to(root)))
            manifest = read_json(
                root
                / ".career-state"
                / "applications_v2"
                / "notion_578"
                / "artifacts_manifest.json"
            )
            self.assertEqual(
                manifest["artifacts"]["feras"],
                ".career-state/applications_v2/notion_578/feras_formal.md",
            )
