from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from career.services.database import Database


def _write_compose(
    path: Path,
    *,
    include_canary: bool = True,
    db_path: Path | None = None,
    include_control_db_env: bool = True,
    state_mount_root: Path | None = None,
) -> None:
    services: dict[str, object] = {}
    if include_canary:
        workspace_root = path.parent / "workspace"
        state_root = state_mount_root or workspace_root / ".career-state"
        environment = {
            "HERMES_HOME": "/opt/data",
            "CAREER_HERMES_PROFILE_ID": "profile-01",
        }
        if include_control_db_env:
            environment["CAREER_CONTROL_DB_PATH"] = str(db_path or path.parent / "career.db")
        services["vagas_bot_01"] = {
            "environment": environment,
            "volumes": [
                f"{path.parent / 'runtime'}:/opt/data",
                f"{path.parent / 'profiles' / 'vagas_bot_01'}:/opt/data/profiles/vagas_bot_01",
                f"{workspace_root}:/workspace/candidaturas:rw",
                f"{state_root}:/workspace/candidaturas/.career-state:rw",
                f"{workspace_root / 'inbox'}:/workspace/candidaturas/inbox:rw",
                f"{workspace_root / 'outputs'}:/workspace/candidaturas/outputs:rw",
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


def test_run_preflight_blocks_when_control_db_identity_env_is_missing(tmp_path, monkeypatch):
    from career.services.canary_control import run_preflight

    target = _canary_target(tmp_path)
    paths = _target_paths(tmp_path)
    _write_compose(paths["compose_path"], db_path=paths["control_db_path"])
    _provisioned_database(paths["control_db_path"], paths["authority_ledger_path"])
    monkeypatch.delenv("CAREER_CONTROL_DB_ID", raising=False)

    result = run_preflight(target, paths["compose_path"], env={})

    assert result["status"] == "blocked"
    assert result["mutations"] == []
    assert any(
        check["name"] == "control_db_identity"
        and check["status"] == "blocked"
        and "CAREER_CONTROL_DB_ID" in check["reason"]
        for check in result["checks"]
    )


def test_resolve_target_from_compose_uses_career_state_mount_when_env_path_absent(tmp_path):
    from career.services.canary_control import resolve_target_from_compose

    paths = _target_paths(tmp_path)
    state_mount_root = tmp_path / "state-mount"
    expected_db_path = state_mount_root / "career.db"
    expected_ledger_path = state_mount_root / "authority.json"
    _write_compose(
        paths["compose_path"],
        db_path=expected_db_path,
        include_control_db_env=False,
        state_mount_root=state_mount_root,
    )

    target = resolve_target_from_compose(compose_path=paths["compose_path"], bot_name="vagas_bot_01")

    assert target.workspace_root == paths["workspace_root"].resolve()
    assert target.control_db_path == expected_db_path.resolve()
    assert target.authority_ledger_path == expected_ledger_path.resolve()


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


def test_stage_hook_dry_run_does_not_write_config_and_limits_target_to_bot01(tmp_path):
    from career.services.canary_control import stage_hook

    target = _canary_target(tmp_path)
    original = "model:\n  default: test\nhooks: {}\n"
    target.hermes_config.write_text(original, encoding="utf-8")

    result = stage_hook(target, apply=False)

    assert result["status"] == "dry_run_ok"
    assert result["target"] == "vagas_bot_01"
    assert result["apply"] is False
    assert result["mutations"] == []
    assert target.hermes_config.read_text(encoding="utf-8") == original
    assert "vagas_bot_02" not in json.dumps(result, ensure_ascii=False)


def test_stage_hook_apply_creates_backup_and_rejects_bot02(tmp_path):
    from career.services.canary_control import stage_hook

    forbidden = _canary_target(tmp_path, bot_name="vagas_bot_02")
    with pytest.raises(ValueError, match="vagas_bot_01"):
        stage_hook(forbidden, apply=True)

    target = _canary_target(tmp_path)
    target.hermes_config.write_text("model:\n  default: test\nhooks: {}\n", encoding="utf-8")

    result = stage_hook(target, apply=True)

    assert result["status"] in {"installed", "already_configured"}
    assert result["target"] == "vagas_bot_01"
    assert result["apply"] is True
    backup_path = Path(result["backup"])
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == "model:\n  default: test\nhooks: {}\n"
    assert "career-harness-output" in target.hermes_config.read_text(encoding="utf-8")
    assert "restart" not in json.dumps(result, ensure_ascii=False).lower()


def test_rollback_dry_run_reports_reversible_state_without_writing(tmp_path):
    from career.services.canary_control import rollback_dry_run, stage_hook

    target = _canary_target(tmp_path)
    original = "model:\n  default: test\nhooks: {}\n"
    target.hermes_config.write_text(original, encoding="utf-8")
    stage_hook(target, apply=True)
    written = target.hermes_config.read_text(encoding="utf-8")

    result = rollback_dry_run(target)

    assert result["status"] == "dry_run_ok"
    assert result["target"] == "vagas_bot_01"
    assert result["apply"] is False
    assert Path(result["backup"]).exists()
    assert target.hermes_config.read_text(encoding="utf-8") == written


def test_route_smoke_uses_deterministic_ids_and_deduplicates(tmp_path):
    from career.services.canary_control import route_smoke

    class FakeSupervisor:
        def __init__(self):
            self.calls = 0

        def handle_message(self, message, **kwargs):
            self.calls += 1
            return {
                "status": "completed",
                "result": {
                    "display_text": f"ok:{message}",
                    "execute": kwargs["execute"],
                },
            }

    supervisor = FakeSupervisor()
    messages = [
        {"message_id": "d1-1", "message": "status das candidaturas"},
        {"message_id": "d1-1", "message": "status das candidaturas"},
        {"message_id": "d1-2", "message": "menu"},
    ]

    result = route_smoke(tmp_path, messages, execute=False, supervisor=supervisor)

    assert [item["message_id"] for item in result] == ["d1-1", "d1-1", "d1-2"]
    assert result[0]["deduplicated"] is False
    assert result[1]["deduplicated"] is True
    assert result[2]["deduplicated"] is False
    assert supervisor.calls == 2


def test_phase_d_canary_route_smoke_cli_uses_temp_root_and_route_only(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "phase_d_canary.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "route-smoke",
            "--root",
            str(tmp_path),
            "--message-id",
            "d1-1",
            "--message",
            "status das candidaturas",
            "--route-only",
        ],
        cwd=script.parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload[0]["message_id"] == "d1-1"
    assert payload[0]["deduplicated"] is False
    assert payload[1]["message_id"] == "d1-1"
    assert payload[1]["deduplicated"] is True
