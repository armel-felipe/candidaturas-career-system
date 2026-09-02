from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from bot_runtime_switch import (
    RuntimeModeError,
    status_bot_mode,
    switch_bot_mode,
    unlock_bot_mode,
)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "candidaturas"
    config_dir = project / "workspaces" / "vagas_bot_02" / "state" / "applications_v2"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "max_per_run": 2,
                "analysis_runner": {
                    "kind": "hermes",
                    "command": "hermes",
                    "agent": "build",
                    "timeout_minutes": 90,
                },
                "generation_runner": {
                    "kind": "hermes",
                    "command": "hermes",
                    "agent": "build",
                    "timeout_minutes": 90,
                },
            }
        ),
        encoding="utf-8",
    )
    return project


def _database(tmp_path: Path) -> Path:
    database_path = tmp_path / "career.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        "CREATE TABLE application_runs (run_id TEXT PRIMARY KEY, application_id TEXT, graph_json TEXT, status TEXT, created_at TEXT, updated_at TEXT)"
    )
    connection.execute(
        "CREATE TABLE cell_nodes (run_id TEXT, node_id TEXT, status TEXT, reserved_by TEXT, reservation_expires_at TEXT)"
    )
    connection.commit()
    connection.close()
    return database_path


def test_switches_one_bot_to_opencode_and_records_the_isolation_roots(tmp_path):
    project = _project(tmp_path)

    result = switch_bot_mode(
        project,
        "vagas_bot_02",
        "opencode",
        control_db_path=tmp_path / "career.db",
    )

    config = json.loads(
        (
            project
            / "workspaces/vagas_bot_02/state/applications_v2/config.json"
        ).read_text(encoding="utf-8")
    )
    assert result["mode"] == "opencode"
    assert config["analysis_runner"]["kind"] == "opencode"
    assert config["generation_runner"]["command"] == "opencode"
    assert config["runtime_mode"]["host_project_root"] == "/opt/agent-projects/candidaturas"
    assert config["runtime_mode"]["container_project_root"] == "/workspace/candidaturas"
    assert (project / "workspaces/vagas_bot_02/state/runtime_mode.lock.json").exists()


def test_lock_requires_explicit_unlock_to_change_modes(tmp_path):
    project = _project(tmp_path)
    database_path = _database(tmp_path)
    switch_bot_mode(project, "vagas_bot_02", "opencode", control_db_path=database_path)

    with pytest.raises(RuntimeModeError, match="runtime_mode_locked"):
        switch_bot_mode(project, "vagas_bot_02", "hermes", control_db_path=database_path)

    result = switch_bot_mode(
        project,
        "vagas_bot_02",
        "hermes",
        control_db_path=database_path,
        unlock=True,
    )
    assert result["mode"] == "hermes"
    assert status_bot_mode(project, "vagas_bot_02")["mode"] == "hermes"


def test_active_cell_blocks_mode_switch_but_waiting_agent_can_be_retargeted(tmp_path):
    project = _project(tmp_path)
    database_path = _database(tmp_path)
    connection = sqlite3.connect(database_path)
    connection.execute(
        "INSERT INTO application_runs VALUES (?, ?, ?, ?, ?, ?)",
        ("run-1", "app-1", "{}", "running", "now", "now"),
    )
    connection.commit()
    connection.close()

    with pytest.raises(RuntimeModeError, match="active_cell_run"):
        switch_bot_mode(project, "vagas_bot_02", "opencode", control_db_path=database_path)

    connection = sqlite3.connect(database_path)
    connection.execute("UPDATE application_runs SET status='awaiting_agent'")
    connection.commit()
    connection.close()
    result = switch_bot_mode(
        project,
        "vagas_bot_02",
        "opencode",
        control_db_path=database_path,
    )
    assert result["mode"] == "opencode"


def test_rejects_unknown_bot_and_never_reads_token_from_cli(tmp_path):
    project = _project(tmp_path)

    with pytest.raises(RuntimeModeError, match="unsupported_bot"):
        switch_bot_mode(project, "vagas_bot_03", "opencode")


def test_rejects_a_missing_bot_workspace_instead_of_creating_configuration(tmp_path):
    with pytest.raises(RuntimeModeError, match="bot_config_missing"):
        switch_bot_mode(tmp_path / "wrong-root", "vagas_bot_02", "opencode")


def test_unlock_also_refuses_an_active_cell(tmp_path):
    project = _project(tmp_path)
    database_path = _database(tmp_path)
    switch_bot_mode(project, "vagas_bot_02", "opencode", control_db_path=database_path)
    connection = sqlite3.connect(database_path)
    connection.execute(
        "INSERT INTO application_runs VALUES (?, ?, ?, ?, ?, ?)",
        ("run-2", "app-2", "{}", "running", "now", "now"),
    )
    connection.commit()
    connection.close()

    with pytest.raises(RuntimeModeError, match="active_cell_run"):
        unlock_bot_mode(
            project,
            "vagas_bot_02",
            control_db_path=database_path,
        )
