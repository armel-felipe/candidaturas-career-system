from __future__ import annotations

import pytest

from career.services.database import Database
from career.services.runtime_control import RuntimeControl


def _runtime_control(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    return database, RuntimeControl(database)


def test_register_worker_is_idempotent_and_updates_last_seen(tmp_path):
    database, runtime = _runtime_control(tmp_path)

    first = runtime.register_worker(
        "worker-01",
        runtime="hermes",
        profile_id="vagas_bot_01",
        metadata={"mode": "legacy-observed"},
    )
    second = runtime.register_worker(
        "worker-01",
        runtime="hermes",
        profile_id="vagas_bot_01",
        metadata={"mode": "cellular-ready"},
    )

    assert first["worker_id"] == second["worker_id"] == "worker-01"
    assert second["last_seen"] >= first["last_seen"]
    row = database.fetch_one(
        "SELECT runtime, profile_id, metadata_json FROM runtime_workers WHERE worker_id = ?",
        ("worker-01",),
    )
    assert row["runtime"] == "hermes"
    assert row["profile_id"] == "vagas_bot_01"
    assert "cellular-ready" in row["metadata_json"]


def test_register_worker_rejects_oversized_metadata(tmp_path):
    _database, runtime = _runtime_control(tmp_path)

    with pytest.raises(ValueError, match="metadata exceeds"):
        runtime.register_worker("worker-01", runtime="hermes", metadata={"x": "a" * 5000})


def test_run_observation_and_finish_are_persisted(tmp_path):
    database, runtime = _runtime_control(tmp_path)
    runtime.register_worker("worker-01", runtime="hermes")

    started = runtime.start_run(
        "worker-01",
        run_id="cell-run-01",
        application_id="application-01",
        node_id="analyze_fit",
        session_id="session-01",
        request_bytes=1200,
        request_tokens=300,
        source="telegram-legacy",
    )
    observation = runtime.record_context_observation(
        started["runtime_run_id"],
        context_tokens=900,
        input_tokens=850,
        output_tokens=50,
        tool_calls=4,
        history_messages=12,
        request_bytes=3600,
        source="hermes-state-db",
        details={"compacted": False},
    )
    finished = runtime.finish_run(
        started["runtime_run_id"],
        status="completed",
        output_bytes=600,
    )

    assert observation["runtime_run_id"] == started["runtime_run_id"]
    assert finished["status"] == "completed"
    run = database.fetch_one(
        "SELECT status, worker_id, application_id, node_id, output_bytes FROM runtime_runs WHERE runtime_run_id = ?",
        (started["runtime_run_id"],),
    )
    assert dict(run) == {
        "status": "completed",
        "worker_id": "worker-01",
        "application_id": "application-01",
        "node_id": "analyze_fit",
        "output_bytes": 600,
    }
    row = database.fetch_one(
        "SELECT context_tokens, tool_calls, history_messages FROM runtime_observations WHERE id = ?",
        (observation["observation_id"],),
    )
    assert dict(row) == {"context_tokens": 900, "tool_calls": 4, "history_messages": 12}


def test_runtime_control_rejects_unknown_run_and_negative_metrics(tmp_path):
    _database, runtime = _runtime_control(tmp_path)
    runtime.register_worker("worker-01", runtime="hermes")

    with pytest.raises(KeyError, match="unknown runtime run"):
        runtime.record_context_observation("missing-run", context_tokens=1)

    started = runtime.start_run("worker-01")
    with pytest.raises(ValueError, match="must be non-negative"):
        runtime.record_context_observation(started["runtime_run_id"], tool_calls=-1)
