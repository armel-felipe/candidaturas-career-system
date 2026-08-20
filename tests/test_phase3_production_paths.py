from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest import mock

from career import cli
from career.services import application_context, intake
from career.services import database as database_module
from career.services.context_materializer import ContextMaterializer
from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.gate_repository import GateRepository
from career.services.persistence.reference_repository import ReferenceRepository
from career.tasks.registry import finalize_fit_map
from career.utils import write_json
from career.workflow import state_store as state_store_module
from career.workflow.state_store import WorkflowStateStore

from tests.test_phase3_integration_e2e import _valid_draft


class Phase3ProductionPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_dir.cleanup)
        self.root = Path(self.temporary_dir.name)
        self.career_state = self.root / ".career-state"
        self.applications_dir = self.career_state / "applications_v2"
        self.database = Database(self.root / "control-plane" / "career.db")
        self.addCleanup(self.database.close)
        self.application_id = "notion_578"
        self.company = "Conexa"
        self.role = "Diretor de Growth"

    def test_public_fit_map_commands_create_revision_bound_receipts(self) -> None:
        with self._runtime():
            self._intake("DESCRICAO PUBLIC CLI CONEXA " * 80)
            self._seed_reference()
            paths = application_context.paths_for(self.application_id)
            write_json(
                paths.fit_map_draft,
                _valid_draft(self.company, self.role, "public-cli"),
            )

            self.assertEqual(
                self._run_cli("fit-map", "validate-draft", "--application-id", self.application_id),
                0,
            )
            expected_gates = []
            for action, gate in (
                ("build", "fit_map_built"),
                ("score", "fit_map_scored"),
                ("validate", "fit_map_validated"),
            ):
                with self.subTest(action=action):
                    self.assertEqual(
                        self._run_cli(
                            "fit-map", action, "--application-id", self.application_id
                        ),
                        0,
                    )
                    expected_gates.append(gate)
                    revision = AnalysisRepository(self.database).get_current(
                        self.application_id
                    )
                    receipts = GateRepository(self.database)
                    for expected_gate in expected_gates:
                        self.assertTrue(
                            receipts.is_satisfied(
                                self.application_id,
                                expected_gate,
                                revision_id=revision.revision_id,
                            ),
                            f"{expected_gate} must be bound to {revision.revision_id}",
                        )

        current = AnalysisRepository(self.database).get_current(self.application_id)
        self.assertIsNotNone(current.score_final)
        self.assertEqual(
            current.application_revision_id,
            ApplicationRepository(self.database).get_current_revision_id(
                self.application_id
            ),
        )

    def test_reintake_v2_finalizes_with_same_gate_hashes_and_preserves_v1(self) -> None:
        shared_draft = _valid_draft(self.company, self.role, "same-stage-bytes")

        with self._runtime():
            self._intake("DESCRICAO V1 CONEXA " * 80)
            self._seed_reference()
            paths = application_context.paths_for(self.application_id)
            write_json(paths.fit_map_draft, shared_draft)
            self.assertEqual(
                self._run_cli("fit-map", "validate-draft", "--application-id", self.application_id),
                0,
            )
            self.assertEqual(
                self._run_cli("fit-map", "finalize", "--application-id", self.application_id),
                0,
            )
            v1 = AnalysisRepository(self.database).get_current(self.application_id)

            self._intake("DESCRICAO V2 CONEXA NOVA " * 80)
            paths = application_context.paths_for(self.application_id)
            write_json(paths.fit_map_draft, shared_draft)
            self.assertEqual(
                self._run_cli("fit-map", "validate-draft", "--application-id", self.application_id),
                0,
            )
            self.assertEqual(
                self._run_cli("fit-map", "finalize", "--application-id", self.application_id),
                0,
            )
            v2 = AnalysisRepository(self.database).get_current(self.application_id)

        self.assertNotEqual(v1.revision_id, v2.revision_id)
        rows = self.database.fetch_all(
            """SELECT gd.dependency_id AS revision_id, vr.gate,
                      vr.input_hash, vr.output_hash
                 FROM validation_receipts AS vr
                 JOIN gate_dependencies AS gd ON gd.receipt_id = vr.receipt_id
                WHERE vr.application_id = ?
                  AND gd.dependency_type = 'fit_map_revision'
                  AND gd.dependency_id IN (?, ?)
                ORDER BY gd.dependency_id, vr.gate""",
            (self.application_id, v1.revision_id, v2.revision_id),
        )
        by_revision: dict[str, dict[str, tuple[str, str]]] = {}
        for row in rows:
            by_revision.setdefault(str(row["revision_id"]), {})[
                str(row["gate"])
            ] = (str(row["input_hash"]), str(row["output_hash"]))
        expected_gates = {
            "fit_map_built",
            "fit_map_scored",
            "fit_map_validated",
        }
        self.assertEqual(set(by_revision[v1.revision_id]), expected_gates)
        self.assertEqual(set(by_revision[v2.revision_id]), expected_gates)
        for gate in expected_gates:
            self.assertEqual(
                by_revision[v1.revision_id][gate],
                by_revision[v2.revision_id][gate],
                f"fixture must exercise equal {gate} hashes across revisions",
            )

        materializer = ContextMaterializer(self.database)
        pinned_v1 = materializer.build(
            self.application_id, "cv_input", revision_id=v1.revision_id
        )
        current_v2 = materializer.build(self.application_id, "cv_input")
        self.assertIn(
            "DESCRICAO V1 CONEXA",
            pinned_v1["context"]["job_description"]["content"],
        )
        self.assertNotIn(
            "DESCRICAO V2 CONEXA",
            json.dumps(pinned_v1, ensure_ascii=False),
        )
        self.assertIn(
            "DESCRICAO V2 CONEXA NOVA",
            current_v2["context"]["job_description"]["content"],
        )

    def test_finalization_rolls_back_revision_and_receipts_on_gate_failure(self) -> None:
        with self._runtime():
            self._intake("DESCRICAO ATOMICIDADE CONEXA " * 80)
            self._seed_reference()
            paths = application_context.paths_for(self.application_id)
            write_json(
                paths.fit_map_draft,
                _valid_draft(self.company, self.role, "atomic-failure"),
            )
            self.assertEqual(
                self._run_cli("fit-map", "validate-draft", "--application-id", self.application_id),
                0,
            )
            self.database.get_connection().execute(
                """CREATE TRIGGER abort_fit_map_scored_receipt
                   BEFORE INSERT ON validation_receipts
                   WHEN NEW.gate = 'fit_map_scored'
                   BEGIN
                     SELECT RAISE(ABORT, 'forced receipt failure');
                   END"""
            )
            self.database.get_connection().commit()
            store = WorkflowStateStore.for_application(
                self.application_id,
                database=self.database,
                root=self.applications_dir,
            )

            with self.assertRaisesRegex(sqlite3.IntegrityError, "forced receipt failure"):
                finalize_fit_map(
                    state_store=store,
                    draft_path=paths.fit_map_draft,
                    output_path=paths.fit_map,
                    run_id="forced-atomic-failure",
                )

        self.assertEqual(
            self.database.fetch_one(
                "SELECT COUNT(*) AS total FROM fit_map_revisions WHERE application_id = ?",
                (self.application_id,),
            )["total"],
            0,
        )
        self.assertEqual(
            self.database.fetch_one(
                """SELECT COUNT(*) AS total
                     FROM validation_receipts
                    WHERE application_id = ?
                      AND gate IN ('fit_map_built', 'fit_map_scored', 'fit_map_validated')""",
                (self.application_id,),
            )["total"],
            0,
        )

    def test_public_build_without_source_revision_fails_before_fit_map_write(self) -> None:
        application_id = "app-without-source-revision"
        with self._runtime():
            ApplicationRepository(self.database).create_application(
                ApplicationIdentity(
                    application_id=application_id,
                    company="Acme",
                    role="Director",
                )
            )
            paths = application_context.paths_for(application_id)
            paths.app_dir.mkdir(parents=True, exist_ok=True)
            write_json(paths.fit_map_draft, _valid_draft("Acme", "Director", "no-rev"))
            paths.fit_map.write_text("sentinel-fit-map\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "no current source revision"):
                self._run_cli("fit-map", "build", "--application-id", application_id)

        self.assertEqual(paths.fit_map.read_text(encoding="utf-8"), "sentinel-fit-map\n")

    def _intake(self, description: str) -> None:
        result = intake.from_paste(
            company=self.company,
            role=self.role,
            text=description,
            application_id=self.application_id,
            database=self.database,
        )
        self.assertEqual(result["status"], "ready_for_model_analysis")

    def _seed_reference(self) -> str:
        return ReferenceRepository(self.database).upsert_version(
            "candidate_facts",
            "felipe",
            json.dumps({"facts": ["Escalou operacoes"]}, ensure_ascii=False),
            "candidate-source-v1",
        )

    @staticmethod
    def _run_cli(*arguments: str) -> int:
        with redirect_stdout(io.StringIO()):
            return cli.main(list(arguments))

    @contextmanager
    def _runtime(self):
        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ), mock.patch.object(
            application_context,
            "ALIAS_INDEX",
            self.career_state / "application_alias_index.json",
        ), mock.patch.object(
            application_context,
            "SESSION_REGISTRY",
            self.career_state / "session_registry.json",
        ), mock.patch.object(intake, "ROOT", self.root), mock.patch.object(
            intake, "CAREER_STATE", self.career_state
        ), mock.patch.object(intake, "INBOX", self.root / "inbox"), mock.patch.object(
            database_module, "ROOT", self.root
        ), mock.patch.object(
            state_store_module, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            state_store_module,
            "DEFAULT_STATE_PATH",
            self.career_state / "workflow_state.json",
        ), mock.patch.object(cli, "CAREER_STATE", self.career_state):
            yield


if __name__ == "__main__":
    unittest.main()
