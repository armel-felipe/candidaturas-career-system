from __future__ import annotations

import hashlib
from pathlib import Path

from career.services import application_context
from career.services.approvals import ApprovalStore
from career.cells.executor import CellExecutor
from career.services.database import Database
from career.services.harness_supervisor import HarnessSupervisor
from career.services.pipeline_intent import PipelineIntentStore


def test_explicit_hermes_profile_id_wins_over_hermes_home(monkeypatch):
    monkeypatch.setenv("HERMES_HOME", "/opt/data")
    monkeypatch.setenv("CAREER_HERMES_PROFILE_ID", "bcc27ffe51db")

    assert application_context.profile_id_from_env() == "bcc27ffe51db"


def test_pipeline_intent_is_idempotent_and_scoped_to_session(tmp_path: Path):
    store = PipelineIntentStore(tmp_path)

    first = store.bind(
        application_id="app_123",
        session_key="hermes:profile:session-1",
        requested_steps=["cv", "onedrive"],
    )
    second = store.bind(
        application_id="app_123",
        session_key="hermes:profile:session-1",
        requested_steps=["notion", "cv"],
    )

    assert first["application_id"] == "app_123"
    assert second["application_id"] == "app_123"
    assert second["requested_steps"] == ["cv", "onedrive", "notion"]
    assert store.resolve("hermes:profile:session-1")["application_id"] == "app_123"
    assert store.resolve("hermes:profile:other") is None
    assert HarnessSupervisor._requested_pipeline_steps(
        "crie o CV personalizado e envie para o OneDrive"
    ) == ["cv", "onedrive"]


def test_supervisor_uses_persisted_session_intent_when_registry_is_missing(
    tmp_path: Path, monkeypatch
):
    PipelineIntentStore(tmp_path).bind(
        application_id="app_456",
        session_key="hermes:profile:session-2",
        requested_steps=["cv"],
    )
    monkeypatch.setattr(application_context, "resolve_session", lambda **_: None)

    supervisor = HarnessSupervisor(tmp_path)
    resolved = supervisor._session_application_id(
        {
            "runtime": "hermes",
            "profile_id": "profile",
            "session_id": "session-2",
        },
        channel="telegram",
    )

    assert resolved == "app_456"


def test_storage_handoff_approval_is_idempotent(tmp_path: Path):
    store = ApprovalStore(tmp_path)

    first = store.create_idempotent(
        action="storage-handoff",
        idempotency_key="control-1:physical-1:felipe-canary",
        payload={"control_db_id": "control-1", "owner": "felipe-canary"},
    )
    second = store.create_idempotent(
        action="storage-handoff",
        idempotency_key="control-1:physical-1:felipe-canary",
        payload={"control_db_id": "control-1", "owner": "felipe-canary"},
    )

    assert first["approval_id"] == second["approval_id"]
    assert len(list((tmp_path / ".career-state" / "approvals").glob("*.json"))) == 1


def test_supervisor_turns_storage_authority_blocker_into_one_approval(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("CAREER_CONTROL_DB_ID", "control-1")
    monkeypatch.setenv("CAREER_WORKSPACE_OWNER", "felipe-canary")

    def blocked_heartbeat(_options):
        raise ValueError(
            "physical control database copy is not authoritative; "
            "an explicit storage handoff is required"
        )

    monkeypatch.setattr(
        "career.services.applications_v2.run_heartbeat", blocked_heartbeat
    )
    database = Database(tmp_path / "control-plane" / "career.db")
    database.init_schema()
    database.close()
    supervisor = HarnessSupervisor(tmp_path)

    first = supervisor.handle_message(
        "processar fila de candidaturas", execute=True
    )
    second = supervisor.handle_message(
        "processar fila de candidaturas", execute=True
    )

    assert first["result"]["status"] == "awaiting_approval"
    assert first["result"]["blocker_reason"] == "storage_handoff_required"
    assert second["result"]["approval"]["approval_id"] == first["result"]["approval"]["approval_id"]


def test_approved_handoff_uses_official_rebind_and_resumes(tmp_path: Path, monkeypatch):
    source_path = tmp_path / "source" / "career.db"
    target_path = tmp_path / "target" / "career.db"
    ledger_path = tmp_path / "shared" / "workspace-authority.json"

    source = Database(source_path)
    source.init_schema()
    control_db_id = source.control_db_identity()
    source.close()
    provisioned = Database(source_path, authority_ledger_path=ledger_path)
    provisioned.provision_authority_ledger(
        expected_control_db_id=control_db_id,
        provisioned_by="test-suite",
    )
    provisioned.init_schema()
    provisioned.close()
    target_path.parent.mkdir(parents=True)
    target_path.write_bytes(source_path.read_bytes())

    monkeypatch.setenv("CAREER_CONTROL_DB_PATH", str(target_path))
    monkeypatch.setenv("CAREER_AUTHORITY_LEDGER_PATH", str(ledger_path))
    monkeypatch.setenv("CAREER_CONTROL_DB_ID", control_db_id)
    monkeypatch.setenv("CAREER_WORKSPACE_OWNER", "felipe-canary")
    supervisor = HarnessSupervisor(tmp_path)
    prepared = supervisor.prepare_authority_handoff(
        application_id="app_789",
        blocker="physical control database copy is not authoritative",
    )
    approval_id = prepared["approval"]["approval_id"]
    ApprovalStore(tmp_path).approve(approval_id)
    monkeypatch.setattr(
        supervisor,
        "handle_message",
        lambda *_args, **_kwargs: {"status": "completed", "result": {"status": "completed"}},
    )

    executed = supervisor.execute_approved_action(approval_id)

    assert executed["status"] == "completed"
    assert executed["resumed"]["status"] == "completed"
    assert executed["approval"]["status"] == "consumed"
    verified = Database(target_path, authority_ledger_path=ledger_path)
    verified.assert_authoritative_storage()
    verified.close()


def test_storage_identity_is_mount_stable_across_container_hostnames(tmp_path: Path):
    database_path = tmp_path / "control-plane" / "career.db"
    database = Database(database_path)
    database.init_schema()

    stat = database_path.stat()
    expected = hashlib.sha256(
        f"career-control-db\0{stat.st_dev}\0{stat.st_ino}".encode("utf-8")
    ).hexdigest()

    assert database.physical_storage_identity() == expected
    database.close()


def test_cell_executor_releases_process_lease_at_boundary(tmp_path: Path):
    database = Database(tmp_path / "control-plane" / "career.db")
    database.init_schema()
    executor = CellExecutor(
        database,
        workspace_owner="test-owner",
        worker_id="test-worker",
    )

    executor._renew_workspace_lease()
    assert database.fetch_one(
        "SELECT worker_id FROM workspace_leases WHERE lease_name = ?",
        ("authoritative-workspace",),
    )["worker_id"] == "test-owner"
    assert executor.release_workspace_lease() is True
    assert database.fetch_one(
        "SELECT worker_id FROM workspace_leases WHERE lease_name = ?",
        ("authoritative-workspace",),
    ) is None
    database.close()
