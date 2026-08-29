from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from career.services.database import Database, RuntimePersistenceMode
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.workflow.state_store import WorkflowStateStore


class SQLiteOnlyModeTests(unittest.TestCase):
    def test_sqlite_only_mode_rejects_unknown_scoped_application_even_when_json_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = Database(
                db_path=root / "control-plane" / "career.db",
                persistence_mode=RuntimePersistenceMode.SQLITE_ONLY,
            )
            state_path = root / ".career-state" / "applications_v2" / "notion_578" / "workflow_state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text('{"stage":"done"}', encoding="utf-8")
            store = WorkflowStateStore(
                application_id="notion_578",
                database=db,
                path=state_path,
            )

            with self.assertRaisesRegex(ValueError, "application_not_in_sqlite"):
                store.load()

            db.close()

    def test_runtime_persistence_mode_defaults_to_sqlite_primary(self) -> None:
        db = Database(db_path=Path(tempfile.mkdtemp()) / "runtime.db")
        try:
            self.assertEqual(db.persistence_mode, RuntimePersistenceMode.SQLITE_PRIMARY)
        finally:
            db.close()

    def test_sqlite_only_mode_does_not_write_compatibility_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = Database(
                db_path=root / "control-plane" / "career.db",
                persistence_mode=RuntimePersistenceMode.SQLITE_ONLY,
            )
            state_path = root / ".career-state" / "applications_v2" / "app-1" / "workflow_state.json"
            state_path.parent.mkdir(parents=True)
            original = '{"stage":"legacy"}'
            state_path.write_text(original, encoding="utf-8")
            store = WorkflowStateStore(
                application_id="app-1",
                database=db,
                path=state_path,
            )
            store.payload = {"active_job": {"application_id": "app-1"}}
            store.save()
            self.assertEqual(state_path.read_text(encoding="utf-8"), original)
            db.close()

    def test_sqlite_primary_ignores_tampered_legacy_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = Database(
                db_path=root / "control-plane" / "career.db",
                persistence_mode=RuntimePersistenceMode.SQLITE_PRIMARY,
            )
            ApplicationRepository(db).create_application(
                ApplicationIdentity(
                    application_id="authoritative-app",
                    company="Conexa",
                    role="Diretor de Growth",
                    fingerprint="a" * 64,
                )
            )
            state_path = (
                root
                / ".career-state"
                / "applications_v2"
                / "authoritative-app"
                / "workflow_state.json"
            )
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                '{"completed_states":["fit_map_validated"],'
                '"next_required_step":"post_processing_available"}',
                encoding="utf-8",
            )

            projected = WorkflowStateStore(
                application_id="authoritative-app",
                database=db,
                path=state_path,
            ).load()

            self.assertEqual(projected["completed_states"], [])
            self.assertEqual(projected["next_required_step"], "fill_fit_map_draft")
            db.close()


if __name__ == "__main__":
    unittest.main()
