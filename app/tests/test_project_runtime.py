from __future__ import annotations

import sqlite3

from career.services.database import Database
from career.services.project import diagnose_runtime, inspect_hermes_state_db


def _create_hermes_fixture(path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            api_call_count INTEGER DEFAULT 0,
            started_at REAL DEFAULT 0
        );
        CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, content TEXT);
        CREATE TABLE session_model_usage (
            session_id TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            api_call_count INTEGER DEFAULT 0
        );
        INSERT INTO sessions VALUES ('short', 4, 1, 200, 30, 2, 1);
        INSERT INTO sessions VALUES ('long', 80, 30, 50000, 500, 31, 2);
        INSERT INTO messages VALUES (1, 'long', 'must not be returned');
        INSERT INTO session_model_usage VALUES ('long', 50000, 500, 31);
        """
    )
    connection.commit()
    connection.close()


def test_inspect_hermes_state_db_returns_bounded_session_metrics_without_content(tmp_path):
    state_db = tmp_path / "state.db"
    _create_hermes_fixture(state_db)

    result = inspect_hermes_state_db(state_db)

    assert result["status"] == "ok"
    assert result["session_count"] == 2
    assert result["message_count"] == 1
    assert result["max_session"]["session_id"] == "long"
    assert result["max_session"]["message_count"] == 80
    assert result["usage"]["input_tokens"] == 50000
    assert "must not be returned" not in str(result)


def test_inspect_hermes_state_db_reports_missing_file(tmp_path):
    result = inspect_hermes_state_db(tmp_path / "missing.db")

    assert result == {"status": "unavailable", "reason": "missing"}


def test_diagnose_runtime_reports_effective_control_plane(monkeypatch, tmp_path):
    control_path = tmp_path / "control" / "career.db"
    database = Database(control_path)
    database.init_schema()
    monkeypatch.setenv("CAREER_CONTROL_DB_PATH", str(control_path))
    monkeypatch.setenv("CAREER_HERMES_ROOT", str(tmp_path / "hermes"))

    result = diagnose_runtime()

    control = result["control_plane"]
    assert control["path"] == str(control_path.resolve())
    assert control["configured"] is True
    assert control["status"] == "ready"
    assert control["control_db_id"].startswith("control_")
    assert result["runtime_observability"]["worker_count"] == 0
    assert result["hermes_profiles"] == []
