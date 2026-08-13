from __future__ import annotations

import hashlib
import json

import pytest

from career.services.agent_requests import CellRequestBuilder
from career.services.cell_store import CellStore
from career.services.database import Database


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    yield database
    database.close()


def _cellular_context(tmp_path):
    manifest = tmp_path / "applications" / "app-a" / "cells" / "analyze_fit" / "1" / "manifest.json"
    read_path = manifest.parent / "fit_map.draft.json"
    write_path = manifest.parent / "staging"
    return {
        "cellular": True,
        "manifest_path": str(manifest),
        "read_allowlist": [str(read_path)],
        "write_allowlist": [str(write_path)],
        "objective": "Produce only the application-scoped FIT_MAP draft.",
    }


def test_cellular_request_persists_its_identity_and_allowlists(db, tmp_path):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["analyze_fit"]})
    reservation = store.reserve_node("run-a", "analyze_fit", "worker-a")

    payload = CellRequestBuilder(db).build(
        run_id="run-a",
        node_id="analyze_fit",
        attempt=reservation["attempt"],
        cellular_context=_cellular_context(tmp_path),
    )

    assert payload["cellular"] is True
    assert payload["application_id"] == "app-a"
    assert payload["run_id"] == "run-a"
    assert payload["node_id"] == "analyze_fit"
    assert payload["attempt"] == 1
    assert payload["read_allowlist"]
    assert payload["write_allowlist"]
    persisted = db.fetch_one(
        "SELECT payload_json, payload_hash FROM cell_requests "
        "WHERE run_id = ? AND node_id = ? AND attempt = ?",
        ("run-a", "analyze_fit", 1),
    )
    assert hashlib.sha256(persisted["payload_json"].encode()).hexdigest() == persisted[
        "payload_hash"
    ]


def test_materialized_cellular_request_is_loaded_from_sqlite_and_tamper_is_rejected(
    db, tmp_path
):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["analyze_fit"]})
    reservation = store.reserve_node("run-a", "analyze_fit", "worker-a")
    builder = CellRequestBuilder(db)
    builder.build(
        run_id="run-a",
        node_id="analyze_fit",
        attempt=reservation["attempt"],
        cellular_context=_cellular_context(tmp_path),
    )
    request_json, request_md = builder.materialize(
        builder.load("run-a", "analyze_fit", reservation["attempt"]),
        tmp_path / "request",
    )

    assert request_json.is_file()
    assert request_md.is_file()
    assert builder.load("run-a", "analyze_fit", reservation["attempt"])["run_id"] == "run-a"

    tampered = json.loads(request_json.read_text(encoding="utf-8"))
    tampered["objective"] = "history Telegram"
    request_json.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(ValueError, match="request hash"):
        builder.validate_materialized(
            "run-a", "analyze_fit", reservation["attempt"], request_json
        )
