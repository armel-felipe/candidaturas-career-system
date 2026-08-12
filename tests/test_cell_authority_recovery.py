from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta

import pytest

from career.cells.executor import CellExecutor
from career.services.application_context import WorkspaceLease, paths_for
from career.services.database import Database


def _unbound_database(database_path):
    database = Database(database_path)
    database.init_schema()
    return database, database.control_db_identity()


def _provisioned_database(database_path, ledger_path):
    unbound, control_db_id = _unbound_database(database_path)
    unbound.close()
    database = Database(database_path, authority_ledger_path=ledger_path)
    database.provision_authority_ledger(
        expected_control_db_id=control_db_id,
        provisioned_by="test-origin",
    )
    database.init_schema()
    return database, control_db_id


def test_finalize_rejects_lease_owner_epoch_takeover_before_completion_commit(
    tmp_path, monkeypatch
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    paths = paths_for("app-a", root=applications_root)
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text("Lead operations.\n", encoding="utf-8")
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        workspace_owner="original-owner",
    )
    plan = executor.plan("app-a", {"cv"})
    for node in plan.nodes:
        executor.fail(plan.run_id, node.node_id, "terminal fixture")

    original_load = executor._load_run
    takeover_epoch = None

    def load_then_transfer_lease(run_id):
        nonlocal takeover_epoch
        loaded = original_load(run_id)
        database.execute(
            "UPDATE workspace_leases SET expires_at = ? WHERE lease_name = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                WorkspaceLease.LEASE_NAME,
            ),
        )
        successor = WorkspaceLease(
            database,
            expected_control_db_id=database.control_db_identity(),
        )
        assert successor.acquire("successor-owner", ttl_seconds=60) is True
        takeover_epoch = successor.fence_token
        return loaded

    monkeypatch.setattr(executor, "_load_run", load_then_transfer_lease)

    with pytest.raises(RuntimeError, match="stale authoritative workspace lease"):
        executor.finalize(plan.run_id)

    assert takeover_epoch is not None
    assert executor.workspace_fence_token is not None
    assert takeover_epoch > executor.workspace_fence_token
    assert database.fetch_one(
        "SELECT status FROM application_runs WHERE run_id = ?", (plan.run_id,)
    ) == {"status": "planned"}
    assert not paths.run_completion_manifest.exists()
    database.close()


def test_provisioning_recovers_after_crash_between_ledger_and_sqlite_binding(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source" / "career.db"
    ledger_path = tmp_path / "shared" / "workspace-authority.json"
    unbound, control_db_id = _unbound_database(database_path)
    unbound.close()
    database = Database(database_path, authority_ledger_path=ledger_path)
    original_write = database._write_authority_ledger

    def write_ledger_then_crash(payload):
        original_write(payload)
        raise RuntimeError("simulated crash after authority ledger write")

    monkeypatch.setattr(database, "_write_authority_ledger", write_ledger_then_crash)
    with pytest.raises(RuntimeError, match="simulated crash"):
        database.provision_authority_ledger(
            expected_control_db_id=control_db_id,
            provisioned_by="macbook",
        )

    persisted_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert database.fetch_one(
        "SELECT authority_ledger_id FROM workspace_authority WHERE singleton_id = 1"
    ) == {"authority_ledger_id": None}
    with pytest.raises(ValueError, match="provenance mismatch"):
        database.init_schema()

    monkeypatch.setattr(database, "_write_authority_ledger", original_write)
    recovered = database.provision_authority_ledger(
        expected_control_db_id=control_db_id,
        provisioned_by="macbook",
    )

    assert recovered["ledger_id"] == persisted_ledger["ledger_id"]
    assert database.fetch_one(
        "SELECT authority_ledger_id FROM workspace_authority WHERE singleton_id = 1"
    ) == {"authority_ledger_id": persisted_ledger["ledger_id"]}
    database.init_schema()
    assert database.assert_authoritative_storage() == database.physical_storage_identity()
    database.close()


def test_handoff_recovers_after_crash_between_sqlite_and_ledger_update(
    tmp_path, monkeypatch
):
    source_path = tmp_path / "source" / "career.db"
    target_path = tmp_path / "target" / "career.db"
    ledger_path = tmp_path / "shared" / "workspace-authority.json"
    source, control_db_id = _provisioned_database(source_path, ledger_path)
    source.close()
    target_path.parent.mkdir(parents=True)
    shutil.copy2(source_path, target_path)

    target = Database(target_path, authority_ledger_path=ledger_path)
    target.init_schema()
    original_write = target._write_authority_ledger

    def crash_before_ledger_update(_payload):
        raise RuntimeError("simulated crash after sqlite handoff commit")

    monkeypatch.setattr(target, "_write_authority_ledger", crash_before_ledger_update)
    with pytest.raises(RuntimeError, match="simulated crash"):
        target.authorize_storage_handoff(
            expected_control_db_id=control_db_id,
            new_owner="rpi5",
        )

    split_authority = target.fetch_one(
        "SELECT storage_identity, authority_epoch FROM workspace_authority "
        "WHERE singleton_id = 1"
    )
    stale_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert split_authority == {
        "storage_identity": target.physical_storage_identity(),
        "authority_epoch": int(stale_ledger["authority_epoch"]) + 1,
    }
    with pytest.raises(ValueError, match="authority epoch|another physical"):
        target.assert_authoritative_storage()

    monkeypatch.setattr(target, "_write_authority_ledger", original_write)
    rebound = target.authorize_storage_handoff(
        expected_control_db_id=control_db_id,
        new_owner="rpi5",
    )

    recovered_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert rebound == target.physical_storage_identity()
    assert recovered_ledger["authority_epoch"] == split_authority["authority_epoch"]
    assert recovered_ledger["storage_identity"] == split_authority["storage_identity"]
    assert target.fetch_one(
        "SELECT COUNT(*) AS count FROM workspace_authority_handoffs"
    ) == {"count": 1}
    assert target.assert_authoritative_storage() == target.physical_storage_identity()

    restarted_origin = Database(source_path, authority_ledger_path=ledger_path)
    try:
        with pytest.raises(ValueError, match="authority epoch|another physical|revoked"):
            restarted_origin.assert_authoritative_storage()
    finally:
        restarted_origin.close()
        target.close()
