from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from career.services.database import Database


class OrphanReceiptQuarantineTests(unittest.TestCase):
    def test_migration_quarantines_unscoped_receipts_and_blocks_new_ones(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(db_path=Path(directory) / "career.db")
            connection = database.get_connection()
            database._ensure_schema_migrations_table(connection)
            for migration_path in database._migration_paths():
                if migration_path.name.startswith("010_"):
                    break
                checksum = database._migration_checksum(migration_path)
                database._apply_migration(connection, migration_path)
                connection.execute(
                    "INSERT INTO schema_migrations (version, checksum, applied_at) VALUES (?, ?, 'now')",
                    (migration_path.name, checksum),
                )
            connection.commit()
            connection.execute(
                """INSERT INTO applications
                   (id, company, role, created_at, updated_at)
                   VALUES ('orphan-app', 'Legacy', 'Legacy role', 'now', 'now')"""
            )
            connection.execute(
                """INSERT INTO application_runs
                   (run_id, application_id, graph_json, status, created_at, updated_at)
                   VALUES ('orphan-run', 'orphan-app', '{}', 'legacy', 'now', 'now')"""
            )
            connection.execute(
                """INSERT INTO cell_nodes
                   (run_id, node_id, status, requires_json, latest_attempt, created_at, updated_at)
                   VALUES ('orphan-run', 'legacy', 'validated', '{}', 1, 'now', 'now')"""
            )
            connection.execute(
                """INSERT INTO validation_receipts
                   (receipt_id, run_id, node_id, attempt, validator, result,
                    details_json, created_at, gate, input_hash, output_hash)
                   VALUES ('orphan-receipt', 'orphan-run', 'legacy', 1,
                           'legacy.validator', 'passed', '{}', 'now',
                           'legacy_gate', 'input', 'output')"""
            )
            connection.commit()

            database.migrate()

            self.assertIsNone(
                connection.execute(
                    "SELECT 1 FROM validation_receipts WHERE receipt_id = 'orphan-receipt'"
                ).fetchone()
            )
            quarantined = connection.execute(
                "SELECT reason FROM quarantined_validation_receipts WHERE receipt_id = 'orphan-receipt'"
            ).fetchone()
            self.assertIsNotNone(quarantined)
            self.assertIn("missing_scope", quarantined[0])

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """INSERT INTO validation_receipts
                       (receipt_id, run_id, node_id, attempt, validator, result,
                        details_json, created_at, gate, input_hash, output_hash)
                       VALUES ('new-orphan', 'orphan-run', 'legacy', 1,
                               'legacy.validator', 'passed', '{}', 'now',
                               'legacy_gate', 'input-2', 'output-2')"""
                )

            database.close()


if __name__ == "__main__":
    unittest.main()
