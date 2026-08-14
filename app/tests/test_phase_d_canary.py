from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from career.services.database import Database


def _write_compose(path: Path, *, include_canary: bool = True, db_path: Path | None = None) -> None:
    services: dict[str, object] = {}
    if include_canary:
        services["vagas_bot_01"] = {
            "environment": {
                "HERMES_HOME": "/opt/data",
                "CAREER_HERMES_PROFILE_ID": "profile-01",
                "CAREER_CONTROL_DB_PATH": str(db_path or path.parent / "career.db"),
            },
            "volumes": [
                f"{path.parent / 'runtime'}:/opt/data",
                f"{path.parent / 'profiles' / 'vagas_bot_01'}:/opt/data/profiles/vagas_bot_01",
                f"{path.parent / 'workspace'}:/workspace/candidaturas:rw",
                f"{path.parent / 'workspace' / '.career-state'}:/workspace/candidaturas/.career-state:rw",
                f"{path.parent / 'workspace' / 'inbox'}:/workspace/candidaturas/inbox:rw",
                f"{path.parent / 'workspace' / 'outputs'}:/workspace/candidaturas/outputs:rw",
            ],
            "command": ["--profile", "vagas_bot_01", "gateway", "run"],
        }
    services["vagas_bot_02"] = {
        "environment": {"HERMES_HOME": "/opt/data"},
        "volumes": [f"{path.parent / 'bot02'}:/opt/data"],
    }
    path.write_text(yaml.safe_dump({"services": services}), encoding="utf-8")


def _provisioned_database(database_path: Path, ledger_path: Path) -> tuple[Database, str]:
    database = Database(database_path, authority_ledger_path=ledger_path)
    database.prepare_authority_ledger_provisioning()
    control_db_id = database.control_db_identity()
    database.provision_authority_ledger(
        expected_control_db_id=control_db_id,
        provisioned_by="test-phase-d-canary",
    )
    database.init_schema()
    return database, control_db_id


def _target_paths(tmp_path: Path) -> dict[str, Path]:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    adapter = tmp_path / "scripts" / "telegram_harness_adapter.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text("# adapter fixture\n", encoding="utf-8")
    hermes_config = tmp_path / "profiles" / "vagas_bot_01" / "hermes.config.json"
    hermes_config.parent.mkdir(parents=True, exist_ok=True)
    hermes_config.write_text("{}", encoding="utf-8")
    return {
        "workspace_root": workspace_root,
        "adapter_script": adapter,
        "hermes_config": hermes_config,
        "control_db_path": tmp_path / "career.db",
        "authority_ledger_path": tmp_path / "authority.json",
        "compose_path": tmp_path / "compose.yaml",
    }


def _canary_target(tmp_path: Path, bot_name: str = "vagas_bot_01"):
    from career.services.canary_control import CanaryTarget

    paths = _target_paths(tmp_path)
    return CanaryTarget(
        bot_name=bot_name,
        compose_service=bot_name,
        hermes_config=paths["hermes_config"],
        adapter_script=paths["adapter_script"],
        control_db_path=paths["control_db_path"],
        authority_ledger_path=paths["authority_ledger_path"],
        workspace_root=paths["workspace_root"],
    )


def test_assert_canary_target_rejects_non_canary_bot(tmp_path):
    from career.services.canary_control import assert_canary_target

    target = _canary_target(tmp_path, bot_name="vagas_bot_02")

    with pytest.raises(ValueError, match="vagas_bot_01"):
        assert_canary_target(target)


def test_run_preflight_blocks_when_compose_lacks_canary_service(tmp_path, monkeypatch):
    from career.services.canary_control import run_preflight

    target = _canary_target(tmp_path)
    paths = _target_paths(tmp_path)
    _write_compose(paths["compose_path"], include_canary=False, db_path=paths["control_db_path"])

    result = run_preflight(target, paths["compose_path"], env={})

    assert result["status"] == "blocked"
    assert result["target"] == "vagas_bot_01"
    assert result["mutations"] == []
    assert any(
        check["name"] == "compose_service" and check["status"] == "blocked"
        for check in result["checks"]
    )


@pytest.mark.parametrize("missing_key", ["adapter_script", "hermes_config", "control_db_path"])
def test_run_preflight_blocks_when_required_files_are_missing(tmp_path, missing_key):
    from career.services.canary_control import run_preflight

    target = _canary_target(tmp_path)
    paths = _target_paths(tmp_path)
    _write_compose(paths["compose_path"], db_path=paths["control_db_path"])
    if missing_key != "control_db_path":
        paths[missing_key].unlink()

    result = run_preflight(target, paths["compose_path"], env={})

    assert result["status"] == "blocked"
    assert result["mutations"] == []
    expected_check = {
        "adapter_script": "adapter_script",
        "hermes_config": "hermes_config",
        "control_db_path": "control_plane_sqlite",
    }[missing_key]
    assert any(
        check["name"] == expected_check and check["status"] == "blocked"
        for check in result["checks"]
    )


def test_run_preflight_opens_sqlite_read_only_and_reports_identity(tmp_path, monkeypatch):
    from career.services.canary_control import run_preflight

    target = _canary_target(tmp_path)
    paths = _target_paths(tmp_path)
    _write_compose(paths["compose_path"], db_path=paths["control_db_path"])
    database, control_db_id = _provisioned_database(
        paths["control_db_path"], paths["authority_ledger_path"]
    )
    monkeypatch.setenv("CAREER_CONTROL_DB_ID", control_db_id)

    result = run_preflight(target, paths["compose_path"], env={"PATH": str(Path(sys.executable).parent)})

    assert result["status"] == "ready"
    assert result["target"] == "vagas_bot_01"
    assert result["mutations"] == []
    assert result["control_db"]["control_db_id"] == control_db_id
    assert result["control_db"]["read_only"] is True
    assert result["control_db"]["ledger_id"].startswith("ledger_")
    sqlite_check = next(
        check for check in result["checks"] if check["name"] == "control_plane_sqlite"
    )
    assert sqlite_check["status"] == "ok"
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        sqlite3.connect(
            f"file:{paths['control_db_path']}?mode=ro",
            uri=True,
        ).execute("CREATE TABLE should_fail(name TEXT)")
    assert database.fetch_one(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'should_fail'"
    ) is None


def test_run_preflight_blocks_on_control_db_identity_mismatch(tmp_path, monkeypatch):
    from career.services.canary_control import run_preflight

    target = _canary_target(tmp_path)
    paths = _target_paths(tmp_path)
    _write_compose(paths["compose_path"], db_path=paths["control_db_path"])
    _database, control_db_id = _provisioned_database(
        paths["control_db_path"], paths["authority_ledger_path"]
    )
    monkeypatch.setenv("CAREER_CONTROL_DB_ID", f"{control_db_id}-wrong")

    result = run_preflight(target, paths["compose_path"], env={})

    assert result["status"] == "blocked"
    assert result["mutations"] == []
    assert any(
        check["name"] == "control_db_identity" and check["status"] == "blocked"
        for check in result["checks"]
    )


def test_phase_d_canary_preflight_cli_returns_json_and_non_zero_for_blocked(tmp_path):
    paths = _target_paths(tmp_path)
    _write_compose(paths["compose_path"], include_canary=False, db_path=paths["control_db_path"])
    script = Path(__file__).resolve().parents[1] / "scripts" / "phase_d_canary.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "preflight",
            "--compose",
            str(paths["compose_path"]),
            "--bot",
            "vagas_bot_01",
            "--json",
        ],
        cwd=script.parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    payload = json.loads(completed.stdout)
    assert payload["status"] == "blocked"
    assert payload["mutations"] == []
