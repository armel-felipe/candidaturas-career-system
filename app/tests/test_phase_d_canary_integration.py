from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from career.services.canary_control import CanaryTarget
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
    hermes_config = profile_root / "hermes.config.json"
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
        result = run_controlled_canary(
            target=target,
            application_id="canary-app",
            workspace=tmp_path,
        )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

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
    assert runtime["application_id"] == "canary-app"
    assert runtime["node_id"] == "analyze_fit"
    assert runtime["status"] == "completed"
    database.close()
    assert untouched_marker.read_text(encoding="utf-8") == (
        json.dumps({"application_id": "untouched-app"}, sort_keys=True) + "\n"
    )


def test_run_controlled_canary_requires_explicit_application_id(tmp_path):
    target = _target(tmp_path)

    with pytest.raises(ValueError, match="application_id"):
        run_controlled_canary(target=target, application_id="", workspace=tmp_path)
