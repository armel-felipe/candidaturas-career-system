from __future__ import annotations

import tempfile
import unittest

from career.services.database import Database


REQUIRED_TABLES = {
    "application_aliases",
    "application_revisions",
    "application_runs",
    "applications",
    "artifact_contents",
    "artifact_dependencies",
    "artifact_versions",
    "artifacts",
    "canonical_journal_snapshots",
    "candidate_evidence",
    "candidate_facts",
    "cell_attempts",
    "cell_handovers",
    "cell_inputs",
    "cell_nodes",
    "cell_requests",
    "deliveries",
    "fit_map_dimensions",
    "fit_map_evidence",
    "fit_map_keywords",
    "fit_map_objections",
    "fit_map_revisions",
    "fit_map_scores",
    "fit_map_stories",
    "gate_dependencies",
    "job_descriptions",
    "job_sections",
    "job_sources",
    "keyword_registry",
    "keyword_translations",
    "notion_cache",
    "notion_records",
    "notion_syncs",
    "positioning_principles",
    "positioning_revisions",
    "positioning_stories",
    "profile_application_bindings",
    "reference_documents",
    "resource_locks",
    "runtime_observations",
    "runtime_runs",
    "runtime_workers",
    "schema_migrations",
    "session_memory",
    "validation_receipts",
    "workflow_events",
    "workspace_authority",
    "workspace_authority_handoffs",
    "workspace_lease_takeovers",
    "workspace_leases",
}


def _table_names(db: Database) -> set[str]:
    tables = db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
    )
    return {table["name"] for table in tables}


class DatabaseTests(unittest.TestCase):
    def test_database_creates_schema(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as handle:
            db = Database(db_path=handle.name)
            try:
                db.init_schema()
                self.assertTrue(REQUIRED_TABLES.issubset(_table_names(db)))
            finally:
                db.close()

    def test_database_insert_and_query(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as handle:
            db = Database(db_path=handle.name)
            try:
                db.init_schema()

                db.execute(
                    """INSERT INTO applications (id, company, role, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    ("app-1", "Acme Corp", "Engineer", "2025-01-01", "2025-01-01"),
                )

                rows = db.fetch_all(
                    "SELECT * FROM applications WHERE funil_stage = ?",
                    ("Fila Agente",),
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["id"], "app-1")
                self.assertEqual(rows[0]["company"], "Acme Corp")
                self.assertEqual(rows[0]["role"], "Engineer")
            finally:
                db.close()

    def test_database_idempotent_schema(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as handle:
            db = Database(db_path=handle.name)
            try:
                db.init_schema()
                first_tables = _table_names(db)
                db.init_schema()

                self.assertTrue(REQUIRED_TABLES.issubset(first_tables))
                self.assertEqual(_table_names(db), first_tables)
            finally:
                db.close()

    def test_database_transaction_rolls_back_on_error(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as handle:
            db = Database(db_path=handle.name)
            try:
                db.init_schema()

                with self.assertRaisesRegex(RuntimeError, "abort"):
                    with db.transaction() as conn:
                        conn.execute(
                            """INSERT INTO applications (id, company, role, created_at, updated_at)
                               VALUES (?, ?, ?, ?, ?)""",
                            (
                                "app-rollback",
                                "Acme Corp",
                                "Engineer",
                                "2025-01-01",
                                "2025-01-01",
                            ),
                        )
                        raise RuntimeError("abort")

                self.assertIsNone(
                    db.fetch_one(
                        "SELECT id FROM applications WHERE id = ?",
                        ("app-rollback",),
                    )
                )
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
