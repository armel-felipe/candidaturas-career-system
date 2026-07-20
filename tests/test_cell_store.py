from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from career.services.cell_store import CellStore
from career.services.database import Database


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    yield database
    database.close()


def test_reserve_node_allows_distinct_applications(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["fit"]})
    store.create_run("app-b", "run-b", graph={"nodes": ["fit"]})

    assert store.reserve_node("run-a", "fit", "worker-a")["status"] == "reserved"
    assert store.reserve_node("run-b", "fit", "worker-b")["status"] == "reserved"


def test_reserve_node_returns_busy_for_live_reservation(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["fit"]})

    assert store.reserve_node("run-a", "fit", "worker-a")["status"] == "reserved"
    assert store.reserve_node("run-a", "fit", "worker-b") == {"status": "busy"}


def test_resource_lock_is_exclusive(db):
    store = CellStore(db)

    assert store.acquire_resource_lock("notion-write", "worker-a")["acquired"] is True
    assert store.acquire_resource_lock("notion-write", "worker-b")["acquired"] is False


def test_expired_resource_lock_can_be_acquired_by_another_worker(db):
    store = CellStore(db)
    acquired_at = datetime.now(UTC).isoformat()
    expired_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    db.execute(
        """INSERT INTO resource_locks (resource_name, worker_id, acquired_at, expires_at)
           VALUES (?, ?, ?, ?)""",
        ("notion-write", "worker-a", acquired_at, expired_at),
    )

    lock = store.acquire_resource_lock("notion-write", "worker-b")

    assert lock["acquired"] is True
    assert lock["worker_id"] == "worker-b"


def test_finish_attempt_updates_node_and_attempt_status(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["fit"]})
    reservation = store.reserve_node("run-a", "fit", "worker-a")

    result = store.finish_attempt(
        "run-a", "fit", reservation["attempt"], "validated", worker_id="worker-a"
    )

    assert result["status"] == "validated"
    assert db.fetch_one(
        "SELECT status FROM cell_attempts WHERE run_id = ? AND node_id = ? AND attempt = ?",
        ("run-a", "fit", reservation["attempt"]),
    ) == {"status": "validated"}
    assert db.fetch_one(
        "SELECT status FROM cell_nodes WHERE run_id = ? AND node_id = ?", ("run-a", "fit")
    ) == {"status": "validated"}


def test_list_ready_nodes_excludes_nodes_with_unvalidated_dependencies(db):
    store = CellStore(db)
    store.create_run(
        "app-a",
        "run-a",
        graph={
            "nodes": [
                {"id": "fit"},
                {"id": "cv", "requires": ["fit"]},
            ]
        },
    )

    assert [node["node_id"] for node in store.list_ready_nodes("run-a")] == ["fit"]
    reservation = store.reserve_node("run-a", "fit", "worker-a")
    store.finish_attempt("run-a", "fit", reservation["attempt"], "validated", worker_id="worker-a")

    assert [node["node_id"] for node in store.list_ready_nodes("run-a")] == ["cv"]
