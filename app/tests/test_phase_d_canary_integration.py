from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from career.services.canary_control import CanaryTarget, resolve_target_from_compose
from career.services.database import Database
from scripts.phase_d_canary import run_controlled_canary


def _target(tmp_path: Path, *, bot_name: str = "vagas_bot_01") -> CanaryTarget:
    workspace_root = tmp_path.resolve()
    state_root = workspace_root / ".career-state"
    state_root.mkdir(parents=True, exist_ok=True)
    adapter = workspace_root / "scripts" / "telegram_harness_adapter.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text("# fixture adapter\n", encoding="utf-8")
    profile_root = tmp_path / "profiles" / bot_name
    profile_root.mkdir(parents=True, exist_ok=True)
    hermes_config = profile_root / "config.yaml"
    hermes_config.write_text("{}", encoding="utf-8")
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_text("services: {}\n", encoding="utf-8")
    return CanaryTarget(
        bot_name=bot_name,
        compose_service=bot_name,
        hermes_config=hermes_config,
        adapter_script=adapter,
        control_db_path=state_root / "career.db",
        authority_ledger_path=state_root / "authority.json",
        workspace_root=workspace_root,
        compose_path=compose_path,
    )


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _write_compose_with_external_state(
    compose_path: Path, *, workspace_root: Path, external_state_root: Path
) -> None:
    profile_root = compose_path.parent / "profiles" / "vagas_bot_01"
    compose_path.write_text(
        "\n".join(
            [
                "services:",
                "  vagas_bot_01:",
                "    environment:",
                "      HERMES_HOME: /opt/data",
                "      CAREER_HERMES_PROFILE_ID: profile-01",
                "    volumes:",
                f"      - {compose_path.parent / 'runtime'}:/opt/data",
                f"      - {profile_root}:/opt/data/profiles/vagas_bot_01",
                f"      - {workspace_root}:/workspace/candidaturas:rw",
                f"      - {external_state_root}:/workspace/candidaturas/.career-state:rw",
                f"      - {workspace_root / 'inbox'}:/workspace/candidaturas/inbox:rw",
                f"      - {workspace_root / 'outputs'}:/workspace/candidaturas/outputs:rw",
                "    command:",
                "      - --profile",
                "      - vagas_bot_01",
                "      - gateway",
                "      - run",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_run_controlled_canary_executes_one_explicit_application(tmp_path):
    target = _target(tmp_path)
    untouched_dir = (
        tmp_path
        / ".career-state"
        / "applications_v2"
        / "untouched-app"
    )
    untouched_dir.mkdir(parents=True, exist_ok=True)
    untouched_marker = untouched_dir / "identity.json"
    untouched_marker.write_text(
        json.dumps({"application_id": "untouched-app"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    previous = {
        key: os.environ.get(key)
        for key in (
            "CAREER_CONTROL_DB_PATH",
            "CAREER_AUTHORITY_LEDGER_PATH",
            "CAREER_WORKSPACE_OWNER",
            "CAREER_CONTROL_DB_ID",
        )
    }
    try:
        result = run_controlled_canary(target, "canary-app", tmp_path)
    finally:
        _restore_env(previous)

    request = json.loads(Path(result["request_json"]).read_text(encoding="utf-8"))
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    draft = json.loads(Path(result["fit_map_draft"]).read_text(encoding="utf-8"))

    assert result["status"] == "completed"
    assert result["target"] == "vagas_bot_01"
    assert result["application_id"] == "canary-app"
    assert result["runner_kind"] == "controlled"
    assert result["execution"] == ["validated"]
    assert result["harness"]["command"][1].endswith("controlled_agent_worker.py")
    assert result["request_hash"] == result["runtime"]["request_hash"]
    assert result["request_cellular"] is True
    assert result["sqlite_counts"] == {
        "cell_inputs": 1,
        "cell_requests": 1,
        "cell_handovers": 1,
        "validation_receipts": 3,
        "runtime_runs": 1,
        "artifacts": 1,
        "runtime_observations": 2,
    }
    assert result["harness"]["isolation"]["status"] == "ok"

    assert request["application_id"] == "canary-app"
    assert request["run_id"] == result["run_id"]
    assert request["node_id"] == "analyze_fit"
    assert request["attempt"] == 1

    assert manifest["application_id"] == "canary-app"
    assert manifest["run_id"] == result["run_id"]
    assert manifest["node_id"] == "analyze_fit"
    assert manifest["attempt"] == 1

    assert draft["application_id"] == "canary-app"
    assert draft["run_id"] == result["run_id"]
    assert draft["attempt"] == 1

    database = Database(tmp_path / ".career-state" / "career.db")
    database.init_schema()
    assert database.fetch_one(
        "SELECT COUNT(*) AS count FROM application_runs",
    )["count"] == 1
    assert database.fetch_one(
        "SELECT COUNT(*) AS count FROM application_runs WHERE application_id = ?",
        ("canary-app",),
    )["count"] == 1
    assert database.fetch_one(
        "SELECT COUNT(*) AS count FROM application_runs WHERE application_id = ?",
        ("untouched-app",),
    )["count"] == 0
    runtime = database.fetch_one(
        "SELECT application_id, run_id, node_id, status FROM runtime_runs WHERE run_id = ?",
        (result["run_id"],),
    )
    assert database.fetch_one(
        "SELECT COUNT(*) AS count FROM runtime_runs",
    )["count"] == 1
    assert database.fetch_one(
        "SELECT COUNT(*) AS count FROM cell_nodes WHERE run_id <> ?",
        (result["run_id"],),
    )["count"] == 0
    assert runtime["application_id"] == "canary-app"
    assert runtime["node_id"] == "analyze_fit"
    assert runtime["status"] == "completed"
    database.close()
    assert {
        path.name for path in (tmp_path / ".career-state" / "applications_v2").iterdir()
    } == {"canary-app", "untouched-app"}
    assert untouched_marker.read_text(encoding="utf-8") == (
        json.dumps({"application_id": "untouched-app"}, sort_keys=True) + "\n"
    )


def test_run_controlled_canary_requires_explicit_application_id(tmp_path):
    target = _target(tmp_path)

    with pytest.raises(ValueError, match="application_id"):
        run_controlled_canary(target=target, application_id="", workspace=tmp_path)


def test_run_controlled_canary_accepts_compose_target_with_external_state_mount(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    external_state_root = tmp_path / "external-state"
    external_state_root.mkdir(parents=True, exist_ok=True)
    adapter = workspace_root / "scripts" / "telegram_harness_adapter.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text("# fixture adapter\n", encoding="utf-8")
    profile_root = tmp_path / "profiles" / "vagas_bot_01"
    profile_root.mkdir(parents=True, exist_ok=True)
    (profile_root / "config.yaml").write_text("{}", encoding="utf-8")
    compose_path = tmp_path / "compose.yaml"
    _write_compose_with_external_state(
        compose_path,
        workspace_root=workspace_root,
        external_state_root=external_state_root,
    )
    target = resolve_target_from_compose(
        compose_path=compose_path,
        bot_name="vagas_bot_01",
    )
    previous = {
        key: os.environ.get(key)
        for key in (
            "CAREER_CONTROL_DB_PATH",
            "CAREER_AUTHORITY_LEDGER_PATH",
            "CAREER_WORKSPACE_OWNER",
            "CAREER_CONTROL_DB_ID",
        )
    }
    try:
        result = run_controlled_canary(target, "canary-app", workspace_root)
    finally:
        _restore_env(previous)

    assert (workspace_root / ".career-state").resolve() == external_state_root.resolve()
    assert target.control_db_path == (external_state_root / "career.db").resolve()
    assert target.authority_ledger_path == (
        external_state_root / "authority.json"
    ).resolve()
    assert (external_state_root / "applications_v2" / "canary-app").is_dir()

    database = Database(target.control_db_path, authority_ledger_path=target.authority_ledger_path)
    database.init_schema()
    assert database.fetch_one(
        "SELECT COUNT(*) AS count FROM application_runs WHERE application_id = ?",
        ("canary-app",),
    )["count"] == 1
    database.close()
    assert Path(result["fit_map_draft"]).resolve().is_relative_to(external_state_root.resolve())


def test_run_controlled_canary_rejects_real_workspace_state_conflict(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    external_state_root = tmp_path / "external-state"
    external_state_root.mkdir(parents=True, exist_ok=True)
    conflicting_state_root = tmp_path / "conflicting-state"
    conflicting_state_root.mkdir(parents=True, exist_ok=True)
    adapter = workspace_root / "scripts" / "telegram_harness_adapter.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text("# fixture adapter\n", encoding="utf-8")
    profile_root = tmp_path / "profiles" / "vagas_bot_01"
    profile_root.mkdir(parents=True, exist_ok=True)
    (profile_root / "config.yaml").write_text("{}", encoding="utf-8")
    compose_path = tmp_path / "compose.yaml"
    _write_compose_with_external_state(
        compose_path,
        workspace_root=workspace_root,
        external_state_root=external_state_root,
    )
    target = resolve_target_from_compose(
        compose_path=compose_path,
        bot_name="vagas_bot_01",
    )
    (workspace_root / ".career-state").symlink_to(conflicting_state_root, target_is_directory=True)
    previous = {
        key: os.environ.get(key)
        for key in (
            "CAREER_CONTROL_DB_PATH",
            "CAREER_AUTHORITY_LEDGER_PATH",
            "CAREER_WORKSPACE_OWNER",
            "CAREER_CONTROL_DB_ID",
        )
    }
    try:
        with pytest.raises(ValueError, match="workspace"):
            run_controlled_canary(target, "canary-app", workspace_root)
    finally:
        _restore_env(previous)


def test_run_controlled_canary_blocks_noncanonical_authority_paths_without_mutation(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    adapter = workspace_root / "scripts" / "telegram_harness_adapter.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text("# fixture adapter\n", encoding="utf-8")
    profile_root = tmp_path / "profiles" / "vagas_bot_01"
    profile_root.mkdir(parents=True, exist_ok=True)
    hermes_config = profile_root / "config.yaml"
    hermes_config.write_text("{}", encoding="utf-8")
    external_state_root = tmp_path / "external-state"
    external_state_root.mkdir(parents=True, exist_ok=True)
    target = CanaryTarget(
        bot_name="vagas_bot_01",
        compose_service="vagas_bot_01",
        hermes_config=hermes_config,
        adapter_script=adapter,
        control_db_path=external_state_root / "custom-career.sqlite",
        authority_ledger_path=external_state_root / "custom-authority-ledger.json",
        workspace_root=workspace_root,
        compose_path=tmp_path / "compose.yaml",
    )
    previous = {
        key: os.environ.get(key)
        for key in (
            "CAREER_CONTROL_DB_PATH",
            "CAREER_AUTHORITY_LEDGER_PATH",
            "CAREER_WORKSPACE_OWNER",
            "CAREER_CONTROL_DB_ID",
        )
    }
    try:
        with pytest.raises(ValueError, match="canonical"):
            run_controlled_canary(target, "canary-app", workspace_root)
    finally:
        _restore_env(previous)

    assert not (workspace_root / ".career-state").exists()
    assert not target.control_db_path.exists()
    assert not target.authority_ledger_path.exists()
    assert not (external_state_root / "applications_v2" / "canary-app").exists()


def test_run_controlled_canary_blocks_existing_application_without_mutation(tmp_path):
    target = _target(tmp_path)
    existing_root = tmp_path / ".career-state" / "applications_v2" / "existing-app"
    existing_root.mkdir(parents=True, exist_ok=True)
    job_description = existing_root / "job_description.md"
    identity = existing_root / "identity.json"
    job_description.write_text("Original description\n", encoding="utf-8")
    identity.write_text(
        json.dumps({"kind": "application_identity", "application_id": "existing-app"}) + "\n",
        encoding="utf-8",
    )
    previous = {
        key: os.environ.get(key)
        for key in (
            "CAREER_CONTROL_DB_PATH",
            "CAREER_AUTHORITY_LEDGER_PATH",
            "CAREER_WORKSPACE_OWNER",
            "CAREER_CONTROL_DB_ID",
        )
    }
    before_job = job_description.read_text(encoding="utf-8")
    before_identity = identity.read_text(encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="already exists"):
            run_controlled_canary(target, "existing-app", tmp_path)
    finally:
        _restore_env(previous)

    assert job_description.read_text(encoding="utf-8") == before_job
    assert identity.read_text(encoding="utf-8") == before_identity
