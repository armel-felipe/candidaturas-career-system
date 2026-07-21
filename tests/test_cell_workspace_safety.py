from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career import cli
from career.services import applications_v2, derived_context, multiagent
from career.services.application_context import WorkspaceLease
from career.services.database import Database
from career.services.harness_runs import HarnessRunStore, allowed_outputs_from_request
from career.services.harness_supervisor import HarnessSupervisor
from career.utils import ValidationFailure, write_json


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    yield database
    database.close()


def _control_db_id(v2_dir: Path) -> str:
    database = Database(v2_dir.parent / "career.db")
    database.init_schema()
    try:
        return database.control_db_identity()
    finally:
        database.close()


def test_second_workspace_owner_is_blocked_but_same_owner_can_schedule_many_apps(db):
    lease = WorkspaceLease(db)

    assert lease.acquire("rpi5", ttl_seconds=60) is True
    assert lease.acquire("rpi5", ttl_seconds=60) is True
    assert lease.acquire("macbook", ttl_seconds=60) is False


def test_workspace_lease_heartbeat_and_release_require_the_current_owner(db):
    lease = WorkspaceLease(db)
    assert lease.acquire("rpi5", ttl_seconds=60) is True

    assert lease.heartbeat("macbook") is False
    assert lease.heartbeat("rpi5") is True
    assert lease.release("macbook") is False
    assert lease.release("rpi5") is True
    assert lease.acquire("macbook", ttl_seconds=60) is True


def test_expired_workspace_takeover_records_prior_owner_and_expiry(db):
    lease = WorkspaceLease(db)
    assert lease.acquire("rpi5", ttl_seconds=60) is True
    expired_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    db.execute(
        "UPDATE workspace_leases SET expires_at = ? WHERE lease_name = ?",
        (expired_at, WorkspaceLease.LEASE_NAME),
    )

    assert lease.acquire("macbook", ttl_seconds=60) is False
    authorized = WorkspaceLease(
        db, expected_control_db_id=lease.control_db_id
    )
    assert authorized.acquire("macbook", ttl_seconds=60) is True

    takeover = db.fetch_one(
        "SELECT prior_owner, prior_expires_at, new_owner "
        "FROM workspace_lease_takeovers ORDER BY id DESC LIMIT 1"
    )
    assert takeover == {
        "prior_owner": "rpi5",
        "prior_expires_at": expired_at,
        "new_owner": "macbook",
    }


def test_separate_control_database_identity_cannot_authorize_machine_handoff(
    tmp_path,
):
    first = Database(tmp_path / "rpi" / "career.db")
    second = Database(tmp_path / "mac" / "career.db")
    first.init_schema()
    second.init_schema()
    try:
        rpi = WorkspaceLease(first)
        assert rpi.acquire("rpi5", ttl_seconds=60) is True
        assert rpi.control_db_id != WorkspaceLease(second).control_db_id
        with pytest.raises(ValueError, match="authoritative control database"):
            WorkspaceLease(
                second, expected_control_db_id=rpi.control_db_id
            )
    finally:
        first.close()
        second.close()


def test_production_workspace_entry_point_requires_authority_and_rejects_copy(
    tmp_path,
):
    authoritative_db = Database(tmp_path / "authoritative" / "career.db")
    copied_db = Database(tmp_path / "copied" / "career.db")
    authoritative_db.init_schema()
    copied_db.init_schema()
    applications_root = tmp_path / "applications"
    try:
        with pytest.raises(ValueError, match="CAREER_CONTROL_DB_ID"):
            CellExecutor(
                authoritative_db,
                applications_root=applications_root,
                require_authoritative_workspace=True,
            )

        authority = authoritative_db.control_db_identity()
        executor = CellExecutor(
            authoritative_db,
            applications_root=applications_root,
            workspace_control_db_id=authority,
            require_authoritative_workspace=True,
        )
        paths = applications_v2.paths_for("app-a", root=applications_root)
        paths.app_dir.mkdir(parents=True)
        paths.job_description.write_text("# Role\n\nLead operations.\n", encoding="utf-8")
        assert executor.plan("app-a", {"cv"}).application_id == "app-a"

        with pytest.raises(ValueError, match="authoritative control database"):
            CellExecutor(
                copied_db,
                applications_root=applications_root,
                workspace_control_db_id=authority,
                require_authoritative_workspace=True,
            )
    finally:
        authoritative_db.close()
        copied_db.close()


def test_expired_workspace_reacquire_records_takeover_even_for_same_owner(db):
    lease = WorkspaceLease(db)
    assert lease.acquire("rpi5", ttl_seconds=60) is True
    expired_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    db.execute(
        "UPDATE workspace_leases SET expires_at = ? WHERE lease_name = ?",
        (expired_at, WorkspaceLease.LEASE_NAME),
    )

    assert lease.acquire("rpi5", ttl_seconds=60) is True
    assert db.fetch_one(
        "SELECT prior_owner, prior_expires_at, new_owner "
        "FROM workspace_lease_takeovers ORDER BY id DESC LIMIT 1"
    ) == {
        "prior_owner": "rpi5",
        "prior_expires_at": expired_at,
        "new_owner": "rpi5",
    }


def test_cell_executor_renews_one_workspace_owner_and_blocks_a_second(db, tmp_path):
    applications_root = tmp_path / "applications"
    rpi = CellExecutor(
        db,
        applications_root=applications_root,
        workspace_owner="rpi5",
    )
    mac = CellExecutor(
        db,
        applications_root=applications_root,
        workspace_owner="macbook",
    )

    first = rpi.plan("app-a", {"feras"})
    second = rpi.plan("app-b", {"feras"})

    assert first.application_id == "app-a"
    assert second.application_id == "app-b"
    with pytest.raises(RuntimeError, match="workspace lease"):
        mac.plan("app-c", {"feras"})


def test_cell_executor_keeps_workspace_lease_alive_during_a_long_handler(
    tmp_path,
):
    database_path = tmp_path / "career.db"
    database = Database(database_path)
    database.init_schema()
    applications_root = tmp_path / "applications"
    paths = applications_v2.paths_for("app-a", root=applications_root)
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text(
        "# Operations Lead\n\nLead operations, planning, data and governance.\n",
        encoding="utf-8",
    )
    write_json(
        paths.identity,
        {
            "kind": "application_identity",
            "application_id": "app-a",
            "company": "Acme",
            "role": "Operations Lead",
        },
    )
    started = threading.Event()
    contender_result: list[bool] = []

    def slow_normalize(_context):
        started.set()
        time.sleep(1.4)
        return CellOutput(
            artifacts={
                "job_normalized.json": b"{}",
                "handover_summary.json": b"{}",
                "evidence_index.json": b"{}",
            }
        )

    def pass_validator(context, _output):
        report = context.paths.reviews_dir / "keepalive.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        return ValidatorResult.passed(context.validator_command, report)

    def contend_after_original_expiry():
        assert started.wait(timeout=2)
        time.sleep(1.05)
        contender_db = Database(database_path)
        contender_db.init_schema()
        try:
            contender_result.append(
                WorkspaceLease(contender_db).acquire("macbook", ttl_seconds=1)
            )
        finally:
            contender_db.close()

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={"normalize_job": slow_normalize},
        validators={"context:validate": pass_validator},
        workspace_owner="rpi5",
        lease_seconds=1,
    )
    plan = executor.plan("app-a", {"cv"})
    contender = threading.Thread(target=contend_after_original_expiry)
    contender.start()
    try:
        result = executor.run_ready(plan.run_id)
    finally:
        contender.join(timeout=3)
        database.close()

    assert result[0].status == "validated"
    assert contender_result == [False]


def test_cell_executor_keeps_leases_alive_through_a_long_validator(tmp_path):
    database_path = tmp_path / "career.db"
    database = Database(database_path)
    database.init_schema()
    applications_root = tmp_path / "applications"
    paths = applications_v2.paths_for("app-a", root=applications_root)
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text(
        "# Operations Lead\n\nLead operations, planning, data and governance.\n",
        encoding="utf-8",
    )
    validator_started = threading.Event()
    contender_result: list[bool] = []

    def normalize(_context):
        return CellOutput(
            artifacts={
                "job_normalized.json": b"{}",
                "handover_summary.json": b"{}",
                "evidence_index.json": b"{}",
            }
        )

    def slow_validator(context, _output):
        validator_started.set()
        time.sleep(1.4)
        report = context.paths.reviews_dir / "slow-validator.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        return ValidatorResult.passed(context.validator_command, report)

    def contend_after_original_expiry():
        assert validator_started.wait(timeout=2)
        time.sleep(1.05)
        contender_db = Database(database_path)
        contender_db.init_schema()
        try:
            contender_result.append(
                WorkspaceLease(contender_db).acquire("macbook", ttl_seconds=1)
            )
        finally:
            contender_db.close()

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={"normalize_job": normalize},
        validators={"context:validate": slow_validator},
        workspace_owner="rpi5",
        lease_seconds=1,
    )
    plan = executor.plan("app-a", {"cv"})
    contender = threading.Thread(target=contend_after_original_expiry)
    contender.start()
    try:
        result = executor.run_ready(plan.run_id)
    finally:
        contender.join(timeout=3)
        database.close()

    assert result[0].status == "validated"
    assert contender_result == [False]


def test_cellular_multiagent_request_requires_complete_identity_and_never_configures_globals(
    tmp_path, monkeypatch
):
    application_dir = tmp_path / ".career-state" / "applications_v2" / "app-a"
    manifest = application_dir / "cells" / "analyze_fit" / "1" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    write_json(
        manifest,
        {
            "kind": "cell_attempt_manifest",
            "application_id": "app-a",
            "run_id": "run-a",
            "node_id": "analyze_fit",
            "capabilities": {
                "read_paths": [str(application_dir / "derived")],
                "write_paths": [str(manifest.parent / "staging")],
            },
        },
    )

    with pytest.raises(ValidationFailure, match="run_id"):
        multiagent.validate_cellular_request_context(
            {
                "cellular": True,
                "application_id": "app-a",
            },
            root=tmp_path,
        )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("cellular request must not configure mutable global paths")

    monkeypatch.setattr(derived_context, "configure_derived_dir", forbidden)
    monkeypatch.setattr(derived_context, "configure_state_store_path", forbidden)
    context = multiagent.validate_cellular_request_context(
        {
            "cellular": True,
            "application_id": "app-a",
            "run_id": "run-a",
            "node_id": "analyze_fit",
            "manifest_path": str(manifest),
            "read_allowlist": [str(application_dir / "derived")],
            "write_allowlist": [str(manifest.parent / "staging")],
        },
        root=tmp_path,
    )

    assert context["application_id"] == "app-a"
    assert context["run_id"] == "run-a"
    assert context["node_id"] == "analyze_fit"
    assert context["manifest_path"] == str(manifest.resolve())


def test_cellular_request_rejects_allowlists_not_declared_by_attempt_manifest(
    tmp_path,
):
    application_dir = tmp_path / ".career-state" / "applications_v2" / "app-a"
    manifest = application_dir / "cells" / "analyze_fit" / "1" / "manifest.json"
    staging = manifest.parent / "staging"
    derived = application_dir / "derived"
    manifest.parent.mkdir(parents=True)
    write_json(
        manifest,
        {
            "kind": "cell_attempt_manifest",
            "application_id": "app-a",
            "run_id": "run-a",
            "node_id": "analyze_fit",
            "capabilities": {
                "read_paths": [str(derived)],
                "write_paths": [str(staging)],
            },
        },
    )

    with pytest.raises(ValidationFailure, match="manifest capabilities"):
        multiagent.validate_cellular_request_context(
            {
                "cellular": True,
                "application_id": "app-a",
                "run_id": "run-a",
                "node_id": "analyze_fit",
                "manifest_path": str(manifest),
                "read_allowlist": [str(derived), str(application_dir / "identity.json")],
                "write_allowlist": [str(application_dir)],
            },
            root=tmp_path,
        )


def test_agent_heartbeat_schedules_cellular_nodes_with_full_handover_context(
    tmp_path, monkeypatch
):
    v2_dir = tmp_path / ".career-state" / "applications_v2"
    monkeypatch.setattr(applications_v2, "V2_DIR", v2_dir)
    monkeypatch.setattr(applications_v2, "V2_LOG_DIR", v2_dir / "_logs")
    monkeypatch.setattr(applications_v2, "V2_INDEX", v2_dir / "index.json")
    monkeypatch.setattr(
        applications_v2,
        "_load_config",
        lambda: {**applications_v2.DEFAULT_CONFIG, "max_per_run": 2},
    )
    monkeypatch.setattr(
        applications_v2, "_run_maintenance_sync", lambda *_args: {"executed": False}
    )
    monkeypatch.setattr(
        applications_v2.notion_service,
        "notion_config",
        lambda: ("unused", "unused"),
    )
    monkeypatch.setattr(
        applications_v2,
        "_load_queue",
        lambda *_args: [
            {
                "record_id": 101,
                "page_id": "page-a",
                "company": "Acme",
                "role": "Operations Lead",
                "title": "Operations Lead",
                "status": "Fila Agente",
                "description": "Lead regional operations, planning, data and continuous improvement. "
                * 20,
            },
            {
                "record_id": 102,
                "page_id": "page-b",
                "company": "Beta",
                "role": "Planning Lead",
                "title": "Planning Lead",
                "status": "Fila Agente",
                "description": "Lead national capacity, logistics, indicators and governance. "
                * 20,
            },
        ],
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("cellular heartbeat must not configure mutable globals")

    monkeypatch.setattr(derived_context, "configure_derived_dir", forbidden)
    monkeypatch.setattr(derived_context, "configure_state_store_path", forbidden)
    result = applications_v2.run_heartbeat(
        applications_v2.HeartbeatV2Options(
            max_per_run=2,
            run_agent=True,
            dry_run=False,
            skip_maintenance=True,
            cellular=True,
            control_db_id=_control_db_id(v2_dir),
        )
    )

    assert result["mode"] == "cellular"
    assert len(result["results"]) == 2
    for item in result["results"]:
        assert item["application_id"]
        assert item["run_id"]
        assert item["node_id"] == "normalize_job"
        assert Path(item["manifest_path"]).is_file()
        assert item["read_allowlist"]
        assert item["write_allowlist"]


def test_agent_heartbeat_second_cycle_invokes_cellular_harness_with_model_variant(
    tmp_path, monkeypatch
):
    v2_dir = tmp_path / ".career-state" / "applications_v2"
    monkeypatch.setattr(applications_v2, "V2_DIR", v2_dir)
    monkeypatch.setattr(applications_v2, "V2_LOG_DIR", v2_dir / "_logs")
    monkeypatch.setattr(applications_v2, "V2_INDEX", v2_dir / "index.json")
    monkeypatch.setattr(
        applications_v2,
        "_load_config",
        lambda: {**applications_v2.DEFAULT_CONFIG, "max_per_run": 1},
    )
    monkeypatch.setattr(
        applications_v2, "_run_maintenance_sync", lambda *_args: {"executed": False}
    )
    monkeypatch.setattr(
        applications_v2.notion_service,
        "notion_config",
        lambda: ("unused", "unused"),
    )
    monkeypatch.setattr(
        applications_v2,
        "_load_queue",
        lambda *_args: [
            {
                "record_id": 101,
                "page_id": "page-a",
                "company": "Acme",
                "role": "Operations Lead",
                "title": "Operations Lead",
                "status": "Fila Agente",
                "description": "Lead operations, planning, data and governance. " * 30,
            }
        ],
    )
    calls: list[dict] = []

    def blocked_agent(self, **kwargs):
        calls.append(kwargs)
        request_payload = json.loads(
            Path(kwargs["request_json"]).read_text(encoding="utf-8")
        )
        draft_path = next(
            Path(path)
            for path in request_payload["write_allowlist"]
            if Path(path).name == "fit_map.draft.json"
        )
        draft_path.write_text('{"partial": true}', encoding="utf-8")
        return {
            "returncode": 1,
            "stderr": "agent unavailable",
            "isolation": {"status": "ok"},
        }

    monkeypatch.setattr(HarnessSupervisor, "run_application_stage", blocked_agent)
    options = applications_v2.HeartbeatV2Options(
        max_per_run=1,
        run_agent=True,
        dry_run=False,
        model="openai/gpt-test",
        variant="medium",
        skip_maintenance=True,
        cellular=True,
        workspace_owner="rpi5",
        control_db_id=_control_db_id(v2_dir),
    )

    first = applications_v2.run_heartbeat(options)
    second = applications_v2.run_heartbeat(options)

    assert first["results"][0]["node_id"] == "normalize_job"
    assert second["results"][0]["node_id"] == "analyze_fit"
    assert second["results"][0]["status"] == "awaiting_agent"
    assert "draft" not in str(second["results"][0].get("blocker", "")).casefold()
    assert calls and calls[0]["model"] == "openai/gpt-test"
    assert calls[0]["variant"] == "medium"
    paths = applications_v2.paths_for("101", root=v2_dir)
    assert not paths.fit_map_draft.exists()
    assert list(paths.requests_dir.rglob("failed_fit_map.draft.json"))

    third = applications_v2.run_heartbeat(options)
    assert third["results"][0]["status"] == "awaiting_agent"
    assert len(calls) == 2


def test_cellular_reprocess_refreshes_job_and_quarantines_stale_draft(
    tmp_path,
):
    applications_root = tmp_path / ".career-state" / "applications_v2"
    first = {
        "record_id": 101,
        "page_id": "page-a",
        "company": "Acme",
        "role": "Operations Lead",
        "status": "Fila Agente",
        "description": "Original operations description. " * 20,
    }
    paths = applications_v2._ensure_cellular_application(
        first, applications_root=applications_root
    )
    paths.fit_map_draft.write_text('{"stale": true}', encoding="utf-8")
    revised = {
        **first,
        "status": "Reprocessar",
        "description": "Revised planning and governance description. " * 20,
    }

    applications_v2._ensure_cellular_application(
        revised, applications_root=applications_root
    )

    assert paths.job_description.read_text(encoding="utf-8").startswith(
        "Revised planning"
    )
    assert not paths.fit_map_draft.exists()
    assert list(paths.requests_dir.rglob("stale_fit_map.draft.json"))


def test_cellular_reprocess_creates_one_new_run_then_resumes_it(
    tmp_path, monkeypatch
):
    v2_dir = tmp_path / ".career-state" / "applications_v2"
    monkeypatch.setattr(applications_v2, "V2_DIR", v2_dir)
    monkeypatch.setattr(applications_v2, "V2_LOG_DIR", v2_dir / "_logs")
    monkeypatch.setattr(applications_v2, "V2_INDEX", v2_dir / "index.json")
    monkeypatch.setattr(
        applications_v2,
        "_load_config",
        lambda: {**applications_v2.DEFAULT_CONFIG, "max_per_run": 1},
    )
    monkeypatch.setattr(
        applications_v2, "_run_maintenance_sync", lambda *_args: {"executed": False}
    )
    monkeypatch.setattr(
        applications_v2.notion_service,
        "notion_config",
        lambda: ("unused", "unused"),
    )
    application = {
        "record_id": 101,
        "page_id": "page-a",
        "company": "Acme",
        "role": "Operations Lead",
        "title": "Operations Lead",
        "status": "Reprocessar",
        "description": "Revised planning and governance description. " * 30,
    }
    monkeypatch.setattr(
        applications_v2, "_load_queue", lambda *_args: [application]
    )
    monkeypatch.setattr(
        HarnessSupervisor,
        "run_application_stage",
        lambda *_args, **_kwargs: {
            "returncode": 1,
            "isolation": {"status": "ok"},
        },
    )
    options = applications_v2.HeartbeatV2Options(
        max_per_run=1,
        run_agent=True,
        dry_run=False,
        skip_maintenance=True,
        cellular=True,
        control_db_id=_control_db_id(v2_dir),
    )

    first = applications_v2.run_heartbeat(options)
    second = applications_v2.run_heartbeat(options)

    assert first["results"][0]["node_id"] == "normalize_job"
    assert second["results"][0]["status"] == "awaiting_agent"
    assert second["results"][0]["run_id"] == first["results"][0]["run_id"]
    marker = json.loads(
        (v2_dir / "101" / "requests" / "cellular_reprocess_request.json").read_text(
            encoding="utf-8"
        )
    )
    assert marker["status"] == "consumed"
    assert marker["run_id"] == first["results"][0]["run_id"]
    database = Database(v2_dir.parent / "career.db")
    try:
        assert database.fetch_one(
            "SELECT COUNT(*) AS count FROM application_runs WHERE application_id = ?",
            ("101",),
        ) == {"count": 1}
    finally:
        database.close()


def test_cellular_heartbeat_does_not_consume_unbound_existing_draft(
    tmp_path, monkeypatch
):
    v2_dir = tmp_path / ".career-state" / "applications_v2"
    monkeypatch.setattr(applications_v2, "V2_DIR", v2_dir)
    monkeypatch.setattr(applications_v2, "V2_LOG_DIR", v2_dir / "_logs")
    monkeypatch.setattr(applications_v2, "V2_INDEX", v2_dir / "index.json")
    monkeypatch.setattr(
        applications_v2,
        "_load_config",
        lambda: {**applications_v2.DEFAULT_CONFIG, "max_per_run": 1},
    )
    monkeypatch.setattr(
        applications_v2, "_run_maintenance_sync", lambda *_args: {"executed": False}
    )
    monkeypatch.setattr(
        applications_v2.notion_service,
        "notion_config",
        lambda: ("unused", "unused"),
    )
    monkeypatch.setattr(
        applications_v2,
        "_load_queue",
        lambda *_args: [
            {
                "record_id": 101,
                "page_id": "page-a",
                "company": "Acme",
                "role": "Operations Lead",
                "status": "Fila Agente",
                "description": "Lead operations, planning, data and governance. " * 30,
            }
        ],
    )
    calls: list[dict] = []

    def blocked_agent(self, **kwargs):
        calls.append(kwargs)
        return {"returncode": 1, "isolation": {"status": "ok"}}

    monkeypatch.setattr(HarnessSupervisor, "run_application_stage", blocked_agent)
    options = applications_v2.HeartbeatV2Options(
        max_per_run=1,
        run_agent=True,
        dry_run=False,
        skip_maintenance=True,
        cellular=True,
        workspace_owner="rpi5",
        control_db_id=_control_db_id(v2_dir),
    )
    first = applications_v2.run_heartbeat(options)
    assert first["results"][0]["node_id"] == "normalize_job"
    paths = applications_v2.paths_for("101", root=v2_dir)
    paths.fit_map_draft.write_text('{"unbound": true}', encoding="utf-8")

    second = applications_v2.run_heartbeat(options)

    assert second["results"][0]["status"] == "awaiting_agent"
    assert calls
    assert not paths.fit_map_draft.exists()


def test_cellular_heartbeat_processes_distinct_applications_concurrently(
    tmp_path, monkeypatch
):
    v2_dir = tmp_path / ".career-state" / "applications_v2"
    monkeypatch.setattr(applications_v2, "V2_DIR", v2_dir)
    monkeypatch.setattr(applications_v2, "V2_LOG_DIR", v2_dir / "_logs")
    monkeypatch.setattr(applications_v2, "V2_INDEX", v2_dir / "index.json")
    monkeypatch.setattr(
        applications_v2,
        "_load_config",
        lambda: {**applications_v2.DEFAULT_CONFIG, "max_per_run": 2},
    )
    monkeypatch.setattr(
        applications_v2, "_run_maintenance_sync", lambda *_args: {"executed": False}
    )
    monkeypatch.setattr(
        applications_v2.notion_service,
        "notion_config",
        lambda: ("unused", "unused"),
    )
    queue = [
        {
            "record_id": record_id,
            "page_id": f"page-{record_id}",
            "company": f"Company {record_id}",
            "role": "Operations Lead",
            "title": "Operations Lead",
            "status": "Fila Agente",
            "description": "Lead operations, planning, data and governance. " * 30,
        }
        for record_id in (101, 102)
    ]
    monkeypatch.setattr(applications_v2, "_load_queue", lambda *_args: queue)
    barrier = threading.Barrier(2)
    intervals: dict[str, tuple[int, int]] = {}

    def fake_process(application, *, options, config, database_path):
        application_id = str(application["record_id"])
        barrier.wait(timeout=2)
        entered = time.time_ns()
        time.sleep(0.1)
        exited = time.time_ns()
        intervals[application_id] = (entered, exited)
        return [
            {
                "status": "validated",
                "application_id": application_id,
                "run_id": f"run-{application_id}",
                "node_id": "normalize_job",
            }
        ]

    monkeypatch.setattr(
        applications_v2, "_process_cellular_application", fake_process, raising=False
    )

    result = applications_v2.run_heartbeat(
        applications_v2.HeartbeatV2Options(
            max_per_run=2,
            run_agent=True,
            dry_run=False,
            skip_maintenance=True,
            cellular=True,
            workspace_owner="rpi5",
            control_db_id=_control_db_id(v2_dir),
        )
    )

    assert len(result["results"]) == 2
    assert set(intervals) == {"101", "102"}
    first, second = intervals.values()
    assert max(first[0], second[0]) < min(first[1], second[1])


def test_agent_heartbeat_cli_defaults_to_cellular_and_legacy_is_explicit(
    monkeypatch, capsys
):
    received = []

    def fake_run(options):
        received.append(options)
        return {"status": "ok", "results": []}

    monkeypatch.setattr(applications_v2, "run_heartbeat", fake_run)
    assert (
        cli.main(
            [
                "applications",
                "heartbeat",
                "--run-agent",
                "--skip-maintenance",
                "--format",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert received[-1].cellular is True

    assert (
        cli.main(
            [
                "applications",
                "heartbeat",
                "--run-agent",
                "--legacy-non-cellular",
                "--skip-maintenance",
                "--format",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert received[-1].cellular is False


def test_migrate_cellular_cli_dry_run_never_opens_control_db_or_acquires_lease(
    tmp_path, monkeypatch, capsys
):
    legacy = tmp_path / "legacy-app"
    legacy.mkdir()
    (legacy / "job_description.md").write_text(
        "# Operations Lead\n\nLead planning and logistics.\n", encoding="utf-8"
    )
    before = {
        str(path.relative_to(legacy)): path.read_bytes()
        for path in legacy.rglob("*")
        if path.is_file()
    }

    def forbidden_database(*_args, **_kwargs):
        raise AssertionError("dry-run must not open or mutate the control database")

    monkeypatch.setattr(cli, "Database", forbidden_database)

    assert (
        cli.main(
            [
                "applications",
                "migrate-cellular",
                "--application-id",
                "app-1",
                "--application-dir",
                str(legacy),
                "--dry-run",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry_run"
    assert not (legacy / "cellular_migration_manifest.json").exists()
    assert {
        str(path.relative_to(legacy)): path.read_bytes()
        for path in legacy.rglob("*")
        if path.is_file()
    } == before


def test_harness_uses_the_cellular_write_allowlist_without_global_patterns(tmp_path):
    application_dir = tmp_path / ".career-state" / "applications_v2" / "app-a"
    output = application_dir / "cells" / "analyze_fit" / "1" / "staging" / "fit_map.json"
    request = application_dir / "requests" / "request.json"
    write_json(
        request,
        {
            "cellular": True,
            "application_id": "app-a",
            "run_id": "run-a",
            "node_id": "analyze_fit",
            "manifest_path": str(application_dir / "cells/analyze_fit/1/manifest.json"),
            "read_allowlist": [str(application_dir / "derived")],
            "write_allowlist": [str(output)],
            "allowed_outputs": [str(tmp_path / "outputs" / "legacy.docx")],
            "outputs": {"allowed_files": [str(tmp_path / ".career-state" / "fit_map.json")]},
            "required_output": {"legacy": str(tmp_path / "outputs" / "legacy.json")},
        },
    )

    assert allowed_outputs_from_request(request, tmp_path) == [output.resolve()]


def test_cellular_harness_detects_global_and_cross_application_writes(tmp_path):
    application_dir = tmp_path / ".career-state" / "applications_v2" / "app-a"
    allowed = application_dir / "fit_map.draft.json"
    request = application_dir / "requests" / "request.json"
    request_md = application_dir / "requests" / "request.md"
    write_json(
        request,
        {
            "cellular": True,
            "write_allowlist": [str(allowed)],
        },
    )
    request_md.parent.mkdir(parents=True, exist_ok=True)
    request_md.write_text("request", encoding="utf-8")
    run = HarnessRunStore(tmp_path, application_dir).begin(
        "analyze", request, request_md
    )

    global_state = tmp_path / ".career-state" / "fit_map.json"
    other_app = (
        tmp_path
        / ".career-state"
        / "applications_v2"
        / "app-b"
        / "fit_map.draft.json"
    )
    rogue_output = tmp_path / "outputs" / "rogue.docx"
    for path in (global_state, other_app, rogue_output):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("rogue", encoding="utf-8")

    isolation = run.inspect()

    assert isolation["status"] == "blocked"
    assert set(isolation["unauthorized_workspace_changes"]) == {
        ".career-state/fit_map.json",
        ".career-state/applications_v2/app-b/fit_map.draft.json",
        "outputs/rogue.docx",
    }


def test_cellular_request_rules_never_direct_the_agent_to_global_state(tmp_path):
    context = {
        "cellular": True,
        "application_id": "app-a",
        "run_id": "run-a",
        "node_id": "analyze_fit",
        "manifest_path": str(tmp_path / "manifest.json"),
        "read_allowlist": [str(tmp_path / "inputs")],
        "write_allowlist": [str(tmp_path / "staging")],
    }

    rules = multiagent.cellular_operational_rules(context)

    joined = "\n".join(rules)
    assert "application_id=app-a" in joined
    assert "run_id=run-a" in joined
    assert "node_id=analyze_fit" in joined
    assert ".career-state/fit_map.json" not in joined
    assert "configure_" not in joined
    assert "global" in joined.casefold()


def test_cellular_fit_map_specialist_never_runs_the_legacy_global_postprocess():
    assert HarnessSupervisor.should_auto_finalize_fit_map(
        step="fit-map", status="completed", enabled=True, cellular=True
    ) is False
    assert HarnessSupervisor.should_auto_finalize_fit_map(
        step="fit-map", status="completed", enabled=True, cellular=False
    ) is True


def test_canonical_operational_docs_lock_down_cellular_handover_and_no_fallback():
    root = Path(__file__).resolve().parent.parent
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    skill = (root / ".agents/skills/career-system/SKILL.md").read_text(
        encoding="utf-8"
    )
    panel = (
        root / "docs/superpowers/status/cellular-orchestration-progress.md"
    ).read_text(encoding="utf-8")

    for document in (agents, skill):
        assert "uma única cópia autoritativa do workspace" in document
        assert "MacBook" in document and "RPi5" in document
        assert "applications:migrate-cellular" in document
        assert "applications:verify-parallel" in document
        assert "applications:repair" in document
        assert "handover_summary.json" in document
        assert "proibido cair para estado global" in document
        assert "application_id" in document
        assert "run_id" in document
        assert "node_id" in document
        assert "CAREER_CONTROL_DB_ID" in document
        assert "bancos SQLite fisicamente separados não se coordenam" in document
        assert "awaiting_agent" in document
        assert "pool limitado" in document
        assert "entrypoint celular de produção exige `CAREER_CONTROL_DB_ID`" in document
        assert "`_approval_meta`" in document
        assert "draft sem vínculo" in document
        assert "cellular_reprocess_request.json" in document
        assert "estado global, `outputs/` e outras candidaturas" in document
        assert "`sync_notion_initial`" in document
        assert "`CellContract.resources`" in document

    assert "Fatia E em revalidação" in panel
    assert "gate final aprovado" not in panel
    assert "pytest -q" in panel
    assert "runtime:diagnose" in panel
