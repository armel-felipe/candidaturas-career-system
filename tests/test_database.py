from __future__ import annotations

import tempfile

import pytest

from career.services.database import Database


def test_database_creates_schema():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()

        tables = db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence' ORDER BY name"
        )
        names = [t["name"] for t in tables]

        assert names == [
            "application_runs",
            "applications",
            "artifact_dependencies",
            "artifacts",
            "canonical_journal_snapshots",
            "cell_attempts",
            "cell_nodes",
            "keyword_registry",
            "notion_cache",
            "resource_locks",
            "session_memory",
                "workflow_events",
                "workspace_authority",
                "workspace_authority_handoffs",
                "workspace_lease_takeovers",
                "workspace_leases",
        ]

        db.close()


def test_database_insert_and_query():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()

        db.execute(
            """INSERT INTO applications (id, company, role, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("app-1", "Acme Corp", "Engineer", "2025-01-01", "2025-01-01"),
        )

        rows = db.fetch_all(
            "SELECT * FROM applications WHERE funil_stage = ?", ("Fila Agente",)
        )
        assert len(rows) == 1
        assert rows[0]["id"] == "app-1"
        assert rows[0]["company"] == "Acme Corp"
        assert rows[0]["role"] == "Engineer"

        db.close()


def test_database_idempotent_schema():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()
        db.init_schema()

        tables = db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence' ORDER BY name"
        )
        assert len(tables) == 16

        db.close()


def test_database_transaction_rolls_back_on_error():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()

        with pytest.raises(RuntimeError, match="abort"):
            with db.transaction() as conn:
                conn.execute(
                    """INSERT INTO applications (id, company, role, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    ("app-rollback", "Acme Corp", "Engineer", "2025-01-01", "2025-01-01"),
                )
                raise RuntimeError("abort")

        assert db.fetch_one("SELECT id FROM applications WHERE id = ?", ("app-rollback",)) is None
        db.close()
