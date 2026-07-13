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
            "applications",
            "keyword_registry",
            "notion_cache",
            "session_memory",
            "workflow_events",
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
        assert len(tables) == 5

        db.close()
