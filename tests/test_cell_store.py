from __future__ import annotations

import json
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


def test_reclaimed_resource_lock_cannot_be_released_by_stale_lease(db):
    store = CellStore(db)
    first = store.acquire_resource_lock("notion-write", "worker-a")
    db.execute(
        "UPDATE resource_locks SET expires_at = ? WHERE resource_name = ?",
        ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), "notion-write"),
    )
    second = store.acquire_resource_lock("notion-write", "worker-b")

    stale_release = store.release_resource_lock(
        "notion-write", "worker-a", lease_id=first["lease_id"]
    )

    assert second["acquired"] is True
    assert stale_release["released"] is False
    assert db.fetch_one(
        "SELECT worker_id, lease_id FROM resource_locks WHERE resource_name = ?",
        ("notion-write",),
    ) == {"worker_id": "worker-b", "lease_id": second["lease_id"]}


def test_reclaiming_expired_node_cancels_old_attempt(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["fit"]})
    first = store.reserve_node("run-a", "fit", "worker-a")
    db.execute(
        "UPDATE cell_nodes SET reservation_expires_at = ? WHERE run_id = ? AND node_id = ?",
        ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), "run-a", "fit"),
    )

    second = store.reserve_node("run-a", "fit", "worker-b")

    assert second["attempt"] == 2
    assert db.fetch_one(
        "SELECT status, finished_at FROM cell_attempts "
        "WHERE run_id = ? AND node_id = ? AND attempt = ?",
        ("run-a", "fit", first["attempt"]),
    )["status"] == "cancelled"


def test_node_lease_can_only_be_renewed_while_live_and_owned(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["fit"]})
    reservation = store.reserve_node("run-a", "fit", "worker-a")

    assert store.renew_node_reservation(
        "run-a", "fit", reservation["attempt"], "worker-a"
    )["renewed"] is True
    db.execute(
        "UPDATE cell_nodes SET reservation_expires_at = ? WHERE run_id = ? AND node_id = ?",
        ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), "run-a", "fit"),
    )

    assert store.renew_node_reservation(
        "run-a", "fit", reservation["attempt"], "worker-a"
    )["renewed"] is False


def test_finish_attempt_updates_node_and_attempt_status(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["fit"]})
    reservation = store.reserve_node("run-a", "fit", "worker-a")

    result = store.finish_attempt(
        "run-a",
        "fit",
        reservation["attempt"],
        "validated",
        worker_id="worker-a",
        receipt={
            "status": "validated",
            "paths": ["outputs/cv.docx"],
            "hashes": {"outputs/cv.docx": "a" * 64},
            "metadata": {"review": "passed"},
        },
    )

    assert result["status"] == "validated"
    assert db.fetch_one(
        "SELECT status FROM cell_attempts WHERE run_id = ? AND node_id = ? AND attempt = ?",
        ("run-a", "fit", reservation["attempt"]),
    ) == {"status": "validated"}
    assert db.fetch_one(
        "SELECT status FROM cell_nodes WHERE run_id = ? AND node_id = ?", ("run-a", "fit")
    ) == {"status": "validated"}
    assert json.loads(
        db.fetch_one(
            "SELECT detail_json FROM cell_attempts WHERE run_id = ? AND node_id = ? AND attempt = ?",
            ("run-a", "fit", reservation["attempt"]),
        )["detail_json"]
    ) == {
        "hashes": {"outputs/cv.docx": "a" * 64},
        "metadata": {"review": "passed"},
        "paths": ["outputs/cv.docx"],
        "status": "validated",
    }


def test_finish_attempt_rejects_oversized_receipt_before_writing(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["fit"]})
    reservation = store.reserve_node("run-a", "fit", "worker-a")

    with pytest.raises(ValueError, match="receipt"):
        store.finish_attempt(
            "run-a",
            "fit",
            reservation["attempt"],
            "validated",
            worker_id="worker-a",
            receipt={
                "status": "validated",
                "paths": [],
                "hashes": {},
                "metadata": {"agent_output": "x" * 4097},
            },
        )

    assert db.fetch_one(
        "SELECT status, finished_at, detail_json FROM cell_attempts "
        "WHERE run_id = ? AND node_id = ? AND attempt = ?",
        ("run-a", "fit", reservation["attempt"]),
    ) == {"status": "reserved", "finished_at": None, "detail_json": None}
    assert db.fetch_one(
        "SELECT status, reserved_by, latest_attempt FROM cell_nodes WHERE run_id = ? AND node_id = ?",
        ("run-a", "fit"),
    ) == {"status": "reserved", "reserved_by": "worker-a", "latest_attempt": 1}


def test_finish_attempt_rejects_stale_attempt_without_mutating_current_node(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["fit"]})
    first = store.reserve_node("run-a", "fit", "worker-a")
    db.execute(
        "UPDATE cell_nodes SET reservation_expires_at = ? WHERE run_id = ? AND node_id = ?",
        ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), "run-a", "fit"),
    )
    second = store.reserve_node("run-a", "fit", "worker-b")

    with pytest.raises(RuntimeError, match="stale or unowned"):
        store.finish_attempt(
            "run-a",
            "fit",
            first["attempt"],
            "validated",
            worker_id="worker-a",
            receipt={"status": "validated", "paths": [], "hashes": {}, "metadata": {}},
        )

    assert second["attempt"] == 2
    assert db.fetch_one(
        "SELECT status, worker_id, finished_at FROM cell_attempts "
        "WHERE run_id = ? AND node_id = ? AND attempt = ?",
        ("run-a", "fit", first["attempt"]),
    )["status"] == "cancelled"
    assert db.fetch_one(
        "SELECT status, reserved_by, latest_attempt FROM cell_nodes WHERE run_id = ? AND node_id = ?",
        ("run-a", "fit"),
    ) == {"status": "reserved", "reserved_by": "worker-b", "latest_attempt": 2}


def test_finish_attempt_rejects_expired_lease_without_mutating_node(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["fit"]})
    reservation = store.reserve_node("run-a", "fit", "worker-a")
    db.execute(
        "UPDATE cell_nodes SET reservation_expires_at = ? WHERE run_id = ? AND node_id = ?",
        ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), "run-a", "fit"),
    )

    with pytest.raises(RuntimeError, match="stale or unowned"):
        store.finish_attempt(
            "run-a",
            "fit",
            reservation["attempt"],
            "validated",
            worker_id="worker-a",
            receipt={"status": "validated", "paths": [], "hashes": {}, "metadata": {}},
        )

    assert db.fetch_one(
        "SELECT status, worker_id, finished_at FROM cell_attempts "
        "WHERE run_id = ? AND node_id = ? AND attempt = ?",
        ("run-a", "fit", reservation["attempt"]),
    ) == {"status": "reserved", "worker_id": "worker-a", "finished_at": None}
    assert db.fetch_one(
        "SELECT status, reserved_by FROM cell_nodes WHERE run_id = ? AND node_id = ?",
        ("run-a", "fit"),
    ) == {"status": "reserved", "reserved_by": "worker-a"}


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
    store.finish_attempt(
        "run-a",
        "fit",
        reservation["attempt"],
        "validated",
        worker_id="worker-a",
        receipt={"status": "validated", "paths": [], "hashes": {}, "metadata": {}},
    )

    assert [node["node_id"] for node in store.list_ready_nodes("run-a")] == ["cv"]


def test_reserve_node_rechecks_dependencies_inside_reservation_transaction(db):
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

    assert store.reserve_node("run-a", "cv", "worker-a") == {"status": "busy"}
    fit = store.reserve_node("run-a", "fit", "worker-a")
    store.finish_attempt(
        "run-a",
        "fit",
        fit["attempt"],
        "validated",
        worker_id="worker-a",
        receipt={"status": "validated", "paths": [], "hashes": {}, "metadata": {}},
    )

    assert store.reserve_node("run-a", "cv", "worker-a")["status"] == "reserved"
