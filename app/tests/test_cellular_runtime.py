from __future__ import annotations

import json

import pytest

from career.cells.contracts import CELL_CONTRACTS
from career.services.agent_requests import CellRequestBuilder
from career.services.cell_store import CellStore
from career.services.cellular_runtime import CellularRuntime
from career.services.database import Database


def test_cellular_runtime_records_a_fresh_bounded_session(tmp_path):
    db = Database(tmp_path / "career.db")
    db.init_schema()
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["analyze_fit"]})
    reservation = store.reserve_node("run-a", "analyze_fit", "worker-a")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"application_id": "app-a", "run_id": "run-a", "node_id": "analyze_fit"}),
        encoding="utf-8",
    )
    request = CellRequestBuilder(db).build(
        run_id="run-a",
        node_id="analyze_fit",
        attempt=reservation["attempt"],
        cellular_context={
            "cellular": True,
            "manifest_path": str(manifest),
            "read_allowlist": [str(manifest)],
            "write_allowlist": [str(tmp_path / "fit_map.draft.json")],
            "objective": "Produce only the FIT_MAP draft.",
        },
    )
    request_json, _ = CellRequestBuilder(db).materialize(
        request, tmp_path / "request"
    )

    runtime = CellularRuntime(db, root=tmp_path, worker_id="runtime-worker")
    tampered = tmp_path / "tampered.json"
    tampered.write_text(
        json.dumps({**request, "objective": "read all history"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="materialized cell request hash"):
        runtime.begin(tampered, request)
    started = runtime.begin(request_json, request)
    runtime.observe(
        started["runtime_run_id"],
        returncode=0,
        stdout="controlled",
        isolation_status="ok",
    )
    finished = runtime.finish(
        started["runtime_run_id"],
        status="completed",
        stdout="controlled",
    )

    row = db.fetch_one(
        "SELECT * FROM runtime_runs WHERE runtime_run_id = ?",
        (started["runtime_run_id"],),
    )
    observation = db.fetch_one(
        "SELECT * FROM runtime_observations WHERE runtime_run_id = ? "
        "ORDER BY id DESC",
        (started["runtime_run_id"],),
    )
    assert row["status"] == "completed"
    assert row["source"] == "cellular-harness"
    assert row["request_tokens"] <= 12000
    assert started["request_hash"]
    assert observation["history_messages"] == 0
    assert observation["source"] == "cellular-result"
    assert finished["status"] == "completed"
    worker = db.fetch_one(
        "SELECT status FROM runtime_workers WHERE worker_id = ?",
        ("runtime-worker",),
    )
    assert worker["status"] == "inactive"
    db.close()
