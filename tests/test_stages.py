from __future__ import annotations

import tempfile

import pytest

from career.services.database import Database
from career.services.stages import StageMachine, STAGE_GRAPH


def test_stage_allowed_transitions():
    db = Database(db_path=":memory:")
    db.init_schema()
    machine = StageMachine(db)

    transitions = machine.allowed_transitions("analyze_running")
    assert "generate_pending" in transitions
    assert "blocked_review" in transitions
    assert "error" in transitions

    db.close()


def test_stage_all_transitions_defined():
    db = Database(db_path=":memory:")
    db.init_schema()
    machine = StageMachine(db)

    for stage, expected in STAGE_GRAPH.items():
        assert machine.allowed_transitions(stage) == expected

    db.close()


def test_stage_unknown_stage():
    db = Database(db_path=":memory:")
    db.init_schema()
    machine = StageMachine(db)

    assert machine.allowed_transitions("nonexistent") == []

    db.close()


def test_stage_transition():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()

        db.execute(
            """INSERT INTO applications (id, company, role, stage, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("app-1", "Acme Corp", "Engineer", "analyze_pending", "active", "2025-01-01", "2025-01-01"),
        )

        machine = StageMachine(db)
        result = machine.transition("app-1", "analyze_pending", "analyze_running")

        assert result is True

        row = db.fetch_one("SELECT stage FROM applications WHERE id = ?", ("app-1",))
        assert row is not None
        assert row["stage"] == "analyze_running"

        db.close()


def test_stage_invalid_transition():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()

        db.execute(
            """INSERT INTO applications (id, company, role, stage, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("app-1", "Acme Corp", "Engineer", "done", "active", "2025-01-01", "2025-01-01"),
        )

        machine = StageMachine(db)
        result = machine.transition("app-1", "done", "analyze_pending")

        assert result is False

        row = db.fetch_one("SELECT stage FROM applications WHERE id = ?", ("app-1",))
        assert row is not None
        assert row["stage"] == "done"

        db.close()


def test_stage_transition_wrong_from_stage():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()

        db.execute(
            """INSERT INTO applications (id, company, role, stage, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("app-1", "Acme Corp", "Engineer", "generate_pending", "active", "2025-01-01", "2025-01-01"),
        )

        machine = StageMachine(db)
        result = machine.transition("app-1", "analyze_pending", "analyze_running")

        assert result is False

        row = db.fetch_one("SELECT stage FROM applications WHERE id = ?", ("app-1",))
        assert row is not None
        assert row["stage"] == "generate_pending"

        db.close()
