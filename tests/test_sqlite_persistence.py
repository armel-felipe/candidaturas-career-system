from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from career.services.database import Database


class SQLitePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "runtime.db"
        self.database = Database(db_path=self.db_path)
        self.addCleanup(self.database.close)

    def test_migrate_registers_schema_and_runtime_pragmas(self) -> None:
        applied = self.database.migrate()

        self.assertEqual(applied, 3)
        self.assertEqual(
            self._migration_versions(),
            [
                "001_application_revisions.sql",
                "002_analysis_and_positioning.sql",
                "003_gates_artifacts_integrations.sql",
            ],
        )
        self.assertEqual(self._pragma("foreign_keys"), 1)
        self.assertEqual(self._pragma("busy_timeout"), 10000)
        self.assertEqual(self._pragma("synchronous"), 2)
        self.assertEqual(self._pragma("journal_mode"), "wal")

        tables = self._table_names()
        for table_name in (
            "application_runs",
            "applications",
            "artifacts",
            "validation_receipts",
            "workflow_events",
            "application_aliases",
            "application_revisions",
            "fit_map_revisions",
            "positioning_revisions",
            "gate_dependencies",
            "artifact_versions",
            "artifact_contents",
            "notion_records",
            "notion_syncs",
            "deliveries",
            "schema_migrations",
        ):
            self.assertIn(table_name, tables)

    def test_migrate_is_idempotent(self) -> None:
        self.database.migrate()

        applied = self.database.migrate()

        self.assertEqual(applied, 0)
        self.assertEqual(len(self._migration_versions()), 3)

    def test_transaction_rolls_back_and_foreign_keys_are_enforced(self) -> None:
        self.database.migrate()
        created_at = "2026-08-18T00:00:00+00:00"

        with self.assertRaises(RuntimeError):
            with self.database.transaction() as conn:
                conn.execute(
                    """INSERT INTO applications
                       (id, company, role, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    ("app-rollback", "Acme", "Director", created_at, created_at),
                )
                conn.execute(
                    """INSERT INTO application_aliases
                       (application_id, alias_type, alias_value, is_primary, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    ("app-rollback", "notion_id", "578", 1, created_at),
                )
                raise RuntimeError("abort")

        self.assertIsNone(
            self.database.fetch_one(
                "SELECT id FROM applications WHERE id = ?", ("app-rollback",)
            )
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute(
                """INSERT INTO application_aliases
                   (application_id, alias_type, alias_value, is_primary, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                ("missing-app", "notion_id", "579", 1, created_at),
            )

    def _migration_versions(self) -> list[str]:
        rows = self.database.fetch_all(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        return [row["version"] for row in rows]

    def _pragma(self, name: str) -> int | str:
        row = self.database.get_connection().execute(f"PRAGMA {name}").fetchone()
        self.assertIsNotNone(row)
        if isinstance(row, sqlite3.Row):
            return row[0]
        return row[0]

    def _table_names(self) -> set[str]:
        rows = self.database.fetch_all(
            """SELECT name FROM sqlite_master
               WHERE type = 'table' AND name != 'sqlite_sequence'"""
        )
        return {row["name"] for row in rows}


if __name__ == "__main__":
    unittest.main()
