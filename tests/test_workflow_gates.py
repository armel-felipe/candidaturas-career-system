from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.tasks import registry
from career.utils import sha256_text
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
