from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from career.services.database import Database
from career.utils import sha256_text


class SQLitePersistenceTests(unittest.TestCase):
    EXPECTED_VERSIONS = [
        "001_application_revisions.sql",
        "002_analysis_and_positioning.sql",
        "003_gates_artifacts_integrations.sql",
        "004_legacy_compatibility.py",
        "005_reference_versioning_and_payload_hashes.py",
    ]

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "runtime.db"
        self.database = Database(db_path=self.db_path)
        self.addCleanup(self.database.close)

    def test_migrate_registers_schema_and_runtime_pragmas(self) -> None:
        applied = self.database.migrate()

        self.assertEqual(applied, 5)
        self.assertEqual(self._migration_versions(), self.EXPECTED_VERSIONS)
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
            "keyword_translation_versions",
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
        self.assertEqual(self._migration_versions(), self.EXPECTED_VERSIONS)

    def test_migration_checksum_normalizes_line_endings_for_sql_and_python(self) -> None:
        sql_lf = Path(self.tempdir.name) / "010_line_endings.sql"
        sql_crlf = Path(self.tempdir.name) / "011_line_endings.sql"
        py_lf = Path(self.tempdir.name) / "012_line_endings.py"
        py_crlf = Path(self.tempdir.name) / "013_line_endings.py"
        sql_lf.write_text("CREATE TABLE sample (id INTEGER);\n", encoding="utf-8")
        sql_crlf.write_bytes(b"CREATE TABLE sample (id INTEGER);\r\n")
        py_lf.write_text(
            "from __future__ import annotations\n\ndef apply(conn):\n    return None\n",
            encoding="utf-8",
        )
        py_crlf.write_bytes(
            b"from __future__ import annotations\r\n\r\ndef apply(conn):\r\n    return None\r\n"
        )

        self.assertEqual(
            self.database._migration_checksum(sql_lf),
            self.database._migration_checksum(sql_crlf),
        )
        self.assertEqual(
            self.database._migration_checksum(py_lf),
            self.database._migration_checksum(py_crlf),
        )

    def test_migrate_does_not_treat_crlf_only_change_as_checksum_drift(self) -> None:
        migration_path = Path(self.tempdir.name) / "001_line_endings.sql"
        migration_path.write_text(
            "CREATE TABLE line_endings_sample (id INTEGER PRIMARY KEY);\n",
            encoding="utf-8",
        )
        self.database._migration_paths = lambda: [migration_path]

        applied = self.database.migrate()

        self.assertEqual(applied, 1)
        migration_path.write_bytes(
            b"CREATE TABLE line_endings_sample (id INTEGER PRIMARY KEY);\r\n"
        )

        reapplied = self.database.migrate()

        self.assertEqual(reapplied, 0)
        self.assertEqual(
            self.database.fetch_all("SELECT version FROM schema_migrations"),
            [{"version": "001_line_endings.sql"}],
        )

    def test_migrate_upgrades_legacy_compatibility_schema_via_versioned_migration(
        self,
    ) -> None:
        self.database.close()
        self._seed_legacy_compatibility_schema(self.db_path)
        self.database = Database(db_path=self.db_path)
        self.addCleanup(self.database.close)

        applied = self.database.migrate()

        self.assertEqual(applied, 5)
        self.assertEqual(self._migration_versions(), self.EXPECTED_VERSIONS)
        self.assertEqual(
            self._columns("resource_locks"),
            {"resource_name", "worker_id", "lease_id", "acquired_at", "expires_at"},
        )
        self.assertEqual(
            self._columns("workspace_leases"),
            {
                "lease_name",
                "worker_id",
                "run_id",
                "lease_epoch",
                "acquired_at",
                "expires_at",
            },
        )
        self.assertTrue(
            {
                "singleton_id",
                "control_db_id",
                "storage_identity",
                "authority_ledger_id",
                "authority_epoch",
                "lease_epoch_counter",
                "created_at",
            }.issubset(self._columns("workspace_authority"))
        )
        self.assertTrue(
            {
                "id",
                "control_db_id",
                "prior_storage_identity",
                "new_storage_identity",
                "new_owner",
                "prior_authority_epoch",
                "new_authority_epoch",
                "authorized_at",
            }.issubset(self._columns("workspace_authority_handoffs"))
        )

        reapplied = self.database.migrate()

        self.assertEqual(reapplied, 0)
        self.assertEqual(self._migration_versions(), self.EXPECTED_VERSIONS)

    def test_migrate_005_backfills_reference_and_payload_hash_columns(self) -> None:
        self.database.close()
        self._seed_pre_005_schema(self.db_path)
        self.database = Database(db_path=self.db_path)
        self.addCleanup(self.database.close)

        applied = self.database.migrate()

        self.assertEqual(applied, 1)
        self.assertEqual(self._migration_versions(), self.EXPECTED_VERSIONS)
        self.assertTrue(
            {"logical_key", "content_hash"}.issubset(self._columns("reference_documents"))
        )
        self.assertIn("payload_hash", self._columns("fit_map_revisions"))
        self.assertIn("payload_hash", self._columns("positioning_revisions"))
        self.assertIn("keyword_translation_versions", self._table_names())

        reference_row = self.database.fetch_one(
            """SELECT logical_key, content_hash FROM reference_documents
               WHERE reference_id = ?""",
            ("ref-existing",),
        )
        self.assertEqual(reference_row["logical_key"], "candidate_cv_facts")
        self.assertEqual(len(str(reference_row["content_hash"])), 64)

        fit_map_row = self.database.fetch_one(
            "SELECT payload_json, payload_hash FROM fit_map_revisions WHERE revision_id = ?",
            ("fit-existing",),
        )
        self.assertEqual(
            fit_map_row["payload_hash"],
            sha256_text(str(fit_map_row["payload_json"])),
        )

        positioning_row = self.database.fetch_one(
            "SELECT payload_json, payload_hash FROM positioning_revisions WHERE revision_id = ?",
            ("pos-existing",),
        )
        self.assertEqual(
            positioning_row["payload_hash"],
            sha256_text(str(positioning_row["payload_json"])),
        )

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

    def _columns(self, table_name: str) -> set[str]:
        rows = self.database.get_connection().execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
        return {row[1] for row in rows}

    def _seed_legacy_compatibility_schema(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE resource_locks (
                    resource_name TEXT PRIMARY KEY,
                    worker_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE TABLE workspace_leases (
                    lease_name TEXT PRIMARY KEY,
                    worker_id TEXT NOT NULL,
                    run_id TEXT,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE TABLE workspace_authority (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    control_db_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE workspace_authority_handoffs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    control_db_id TEXT NOT NULL,
                    prior_storage_identity TEXT NOT NULL,
                    new_storage_identity TEXT NOT NULL,
                    new_owner TEXT NOT NULL,
                    authorized_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _seed_pre_005_schema(self, db_path: Path) -> None:
        payload = '{"stories":[{"story_key":"base","narrative":"Base"}]}'
        positioning = '{"headline":"Executivo"}'
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """CREATE TABLE schema_migrations (
                       version TEXT PRIMARY KEY,
                       checksum TEXT NOT NULL,
                       applied_at TEXT NOT NULL
                   )"""
            )
            migration_dir = Path(__file__).resolve().parent.parent / "src" / "career" / "services" / "persistence" / "migrations"
            for version in self.EXPECTED_VERSIONS[:-1]:
                migration_path = migration_dir / version
                checksum = self.database._migration_checksum(migration_path)
                conn.execute(
                    "INSERT INTO schema_migrations (version, checksum, applied_at) VALUES (?, ?, ?)",
                    (version, checksum, "2026-08-18T00:00:00+00:00"),
                )
            conn.executescript(
                """
                CREATE TABLE reference_documents (
                    reference_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    reference_key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(kind, reference_key)
                );

                CREATE TABLE keyword_translations (
                    keyword TEXT NOT NULL,
                    locale TEXT NOT NULL,
                    translation TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(keyword, locale)
                );

                CREATE TABLE fit_map_revisions (
                    revision_id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    application_revision_id TEXT,
                    fingerprint TEXT,
                    source_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    score_final REAL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE positioning_revisions (
                    revision_id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    fit_map_revision_id TEXT,
                    source_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """INSERT INTO reference_documents
                   (reference_id, kind, reference_key, content, source_hash, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    "ref-existing",
                    "candidate_facts",
                    "candidate_cv_facts#legacyhash",
                    '{"candidate":{"name":"Felipe Armel"}}',
                    "source-existing",
                    "2026-08-18T00:00:00+00:00",
                    "2026-08-18T00:00:00+00:00",
                ),
            )
            conn.execute(
                """INSERT INTO fit_map_revisions
                   (revision_id, application_id, source_hash, payload_json, score_final, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    "fit-existing",
                    "app-conexa",
                    "fit-source-existing",
                    payload,
                    7.2,
                    "2026-08-18T00:00:00+00:00",
                ),
            )
            conn.execute(
                """INSERT INTO positioning_revisions
                   (revision_id, application_id, fit_map_revision_id, source_hash, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    "pos-existing",
                    "app-conexa",
                    "fit-existing",
                    "positioning-source-existing",
                    positioning,
                    "2026-08-18T00:00:00+00:00",
                ),
            )
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
