from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from career.cells.executor import CellExecutor
from career import cli
from career.services import applications_v2, derived_context, multiagent
from career.services.application_context import WorkspaceLease
from career.services.database import Database
from career.services.harness_runs import allowed_outputs_from_request
from career.utils import ValidationFailure, write_json


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    yield database
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

    assert lease.acquire("macbook", ttl_seconds=60) is True

    takeover = db.fetch_one(
        "SELECT prior_owner, prior_expires_at, new_owner "
        "FROM workspace_lease_takeovers ORDER BY id DESC LIMIT 1"
    )
    assert takeover == {
        "prior_owner": "rpi5",
        "prior_expires_at": expired_at,
        "new_owner": "macbook",
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
            workspace_owner="rpi5",
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
        },
    )

    assert allowed_outputs_from_request(request, tmp_path) == [output.resolve()]


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

    assert "Fatia E aprovada" in panel
    assert "pytest -q" in panel
    assert "runtime:diagnose" in panel
