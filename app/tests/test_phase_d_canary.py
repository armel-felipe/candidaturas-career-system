from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from career.services.database import Database
from scripts import phase_d_canary


def _write_compose(
    path: Path,
    *,
    include_canary: bool = True,
    db_path: Path | None = None,
    authority_ledger_path: Path | None = None,
    include_control_db_env: bool = True,
    include_authority_ledger_env: bool = False,
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
        if include_authority_ledger_env:
            environment["CAREER_AUTHORITY_LEDGER_PATH"] = str(
                authority_ledger_path or path.parent / "authority.json"
            )
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
    state_root = workspace_root / ".career-state"
    state_root.mkdir(parents=True, exist_ok=True)
    adapter = workspace_root / "scripts" / "telegram_harness_adapter.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text("# adapter fixture\n", encoding="utf-8")
    hermes_config = tmp_path / "profiles" / "vagas_bot_01" / "config.yaml"
    hermes_config.parent.mkdir(parents=True, exist_ok=True)
    hermes_config.write_text("{}", encoding="utf-8")
    return {
        "workspace_root": workspace_root,
        "profile_root": hermes_config.parent,
        "adapter_script": adapter,
        "hermes_config": hermes_config,
        "control_db_path": state_root / "career.db",
        "authority_ledger_path": state_root / "authority.json",
        "compose_path": tmp_path / "compose.yaml",
    }


def _canary_target(
    tmp_path: Path,
    bot_name: str = "vagas_bot_01",
    *,
    hermes_config: Path | None = None,
):
    from career.services.canary_control import CanaryTarget

    paths = _target_paths(tmp_path)
    return CanaryTarget(
        bot_name=bot_name,
        compose_service=bot_name,
        hermes_config=(hermes_config or paths["hermes_config"]),
        adapter_script=paths["adapter_script"],
        control_db_path=paths["control_db_path"],
        authority_ledger_path=paths["authority_ledger_path"],
        workspace_root=paths["workspace_root"],
        compose_path=paths["compose_path"],
    )


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _materialize_runner_gate_request(
    root: Path,
    *,
    application_id: str = "canary-app",
    run_id: str = "run-canary",
    attempt: int = 1,
) -> tuple[Path, dict[str, object]]:
    request_dir = (
        root
        / ".career-state"
        / "applications_v2"
        / application_id
        / "requests"
        / "cellular"
        / run_id
        / "analyze_fit"
        / str(attempt)
    )
    request_dir.mkdir(parents=True, exist_ok=True)
    request_json = request_dir / "request.json"
    request_md = request_dir / "request.md"
    manifest = (
        root
        / ".career-state"
        / "applications_v2"
        / application_id
        / "cells"
        / "analyze_fit"
        / str(attempt)
        / "manifest.json"
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{}", encoding="utf-8")
    draft = root / ".career-state" / "applications_v2" / application_id / "fit_map.draft.json"
    payload: dict[str, object] = {
        "cellular": True,
        "application_id": application_id,
        "run_id": run_id,
        "node_id": "analyze_fit",
        "attempt": attempt,
        "manifest_path": str(manifest),
        "read_allowlist": [str(manifest)],
        "write_allowlist": [str(draft)],
        "objective": "Produce only the FIT_MAP draft.",
    }
    request_json.write_text(json.dumps(payload), encoding="utf-8")
    request_md.write_text("# request\n", encoding="utf-8")
    return request_json, payload


def _write_runner_gate_manifest(root: Path, request_json: Path, payload: dict[str, object]) -> Path:
    manifest_path = root / ".career-state" / "phase_d_runner_gate.json"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    body = {
        "kind": "phase_d_runner_gate_manifest",
        "version": 1,
        "target": "vagas_bot_01",
        "approvals": {
            "d0": {
                "kind": "phase_d_gate_evidence",
                "version": 1,
                "gate": "d0",
                "approved": True,
                "status": "ready",
                "evidence_path": str(root / ".career-state" / "phase_d_gates" / "d0_preflight.json"),
                "evidence_hash": "stub-d0",
            },
            "d1": {
                "kind": "phase_d_gate_evidence",
                "version": 1,
                "gate": "d1",
                "approved": True,
                "status": "dry_run_ok",
                "evidence_path": str(root / ".career-state" / "phase_d_gates" / "d1_stage_hook.json"),
                "evidence_hash": "stub-d1",
            },
            "d2": {
                "kind": "phase_d_gate_evidence",
                "version": 1,
                "gate": "d2",
                "approved": True,
                "status": "completed",
                "evidence_path": str(root / ".career-state" / "phase_d_gates" / "d2_controlled_run.json"),
                "evidence_hash": "stub-d2",
                "application_id": payload["application_id"],
                "run_id": payload["run_id"],
                "node_id": payload["node_id"],
                "attempt": payload["attempt"],
                "request_json": str(request_json),
                "request_md": str(request_json.with_suffix(".md")),
                "request_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                "read_allowlist": list(payload["read_allowlist"]),
                "write_allowlist": list(payload["write_allowlist"]),
            },
        },
    }
    evidence_dir = root / ".career-state" / "phase_d_gates"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_payloads = {
        "d0_preflight.json": {
            "kind": "phase_d_gate_evidence",
            "version": 1,
            "gate": "d0",
            "target": "vagas_bot_01",
            "approved": True,
            "status": "ready",
            "result": {"status": "ready"},
        },
        "d1_stage_hook.json": {
            "kind": "phase_d_gate_evidence",
            "version": 1,
            "gate": "d1",
            "target": "vagas_bot_01",
            "approved": True,
            "status": "dry_run_ok",
            "result": {"status": "dry_run_ok"},
        },
        "d2_controlled_run.json": {
            "kind": "phase_d_gate_evidence",
            "version": 1,
            "gate": "d2",
            "target": "vagas_bot_01",
            "approved": True,
            "status": "completed",
            "result": {
                "status": "completed",
                "application_id": payload["application_id"],
                "run_id": payload["run_id"],
                "node_id": payload["node_id"],
                "attempt": payload["attempt"],
                "request_json": str(request_json),
                "request_md": str(request_json.with_suffix(".md")),
                "request_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                "read_allowlist": list(payload["read_allowlist"]),
                "write_allowlist": list(payload["write_allowlist"]),
            },
        },
    }
    for name, evidence in evidence_payloads.items():
        evidence_path = evidence_dir / name
        serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        body["approvals"][evidence["gate"]]["evidence_hash"] = hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(body), encoding="utf-8")
    return manifest_path


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
    assert result["control_db"]["ledger_kind"] == Database.AUTHORITY_LEDGER_KIND
    assert result["control_db"]["ledger_schema_version"] == Database.AUTHORITY_LEDGER_VERSION
    assert result["control_db"]["actual_storage_identity"]
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


def test_run_preflight_blocks_when_copied_db_and_ledger_are_stale(tmp_path, monkeypatch):
    from career.services.canary_control import run_preflight

    source = tmp_path / "source"
    copied = tmp_path / "copied"
    source_paths = _target_paths(source)
    copied_paths = _target_paths(copied)
    _write_compose(source_paths["compose_path"], db_path=source_paths["control_db_path"])
    _write_compose(copied_paths["compose_path"], db_path=copied_paths["control_db_path"])
    database, control_db_id = _provisioned_database(
        source_paths["control_db_path"], source_paths["authority_ledger_path"]
    )
    database.execute("PRAGMA wal_checkpoint(FULL)")
    database.close()
    shutil.copy2(source_paths["control_db_path"], copied_paths["control_db_path"])
    shutil.copy2(source_paths["authority_ledger_path"], copied_paths["authority_ledger_path"])
    monkeypatch.setenv("CAREER_CONTROL_DB_ID", control_db_id)

    target = _canary_target(copied)
    result = run_preflight(target, copied_paths["compose_path"], env={})

    assert result["status"] == "blocked"
    assert result["mutations"] == []
    assert result["control_db"]["control_db_id"] == control_db_id
    assert result["control_db"]["stored_storage_identity"] != result["control_db"]["actual_storage_identity"]
    assert any(
        check["name"] == "authoritative_storage" and check["status"] == "blocked"
        for check in result["checks"]
    )


def test_run_preflight_blocks_when_authority_ledger_kind_is_invalid(tmp_path, monkeypatch):
    from career.services.canary_control import run_preflight

    target = _canary_target(tmp_path)
    paths = _target_paths(tmp_path)
    _write_compose(paths["compose_path"], db_path=paths["control_db_path"])
    _database, control_db_id = _provisioned_database(
        paths["control_db_path"], paths["authority_ledger_path"]
    )
    payload = json.loads(paths["authority_ledger_path"].read_text(encoding="utf-8"))
    payload["kind"] = "wrong-kind"
    paths["authority_ledger_path"].write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("CAREER_CONTROL_DB_ID", control_db_id)

    result = run_preflight(target, paths["compose_path"], env={})

    assert result["status"] == "blocked"
    assert any(
        check["name"] == "authority_ledger" and check["status"] == "blocked"
        for check in result["checks"]
    )


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


def test_resolve_target_from_compose_prefers_service_authority_ledger_path(tmp_path):
    from career.services.canary_control import resolve_target_from_compose

    paths = _target_paths(tmp_path)
    explicit_ledger_path = tmp_path / "custom-state" / "authority-ledger.json"
    _write_compose(
        paths["compose_path"],
        db_path=paths["control_db_path"],
        authority_ledger_path=explicit_ledger_path,
        include_authority_ledger_env=True,
    )

    target = resolve_target_from_compose(
        compose_path=paths["compose_path"], bot_name="vagas_bot_01"
    )

    assert target.control_db_path == paths["control_db_path"].resolve()
    assert target.authority_ledger_path == explicit_ledger_path.resolve()


def test_resolve_target_from_real_compose_uses_config_yaml():
    from career.services.canary_control import resolve_target_from_compose

    compose_path = Path(__file__).resolve().parents[1] / "deploy" / "hermes" / "compose.yaml"

    target = resolve_target_from_compose(compose_path=compose_path, bot_name="vagas_bot_01")

    assert target.hermes_config == Path(
        "/opt/agent-projects/candidaturas/hermes/vagas_bot_01/config.yaml"
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


def test_preflight_cli_is_read_only_and_does_not_persist_gate_evidence(
    monkeypatch, capsys, tmp_path
):
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_text("services: {}\n", encoding="utf-8")
    target = _canary_target(tmp_path)

    monkeypatch.setattr(
        phase_d_canary,
        "resolve_target_from_compose",
        lambda **kwargs: target,
    )
    monkeypatch.setattr(
        phase_d_canary,
        "run_preflight",
        lambda resolved_target, compose: {
            "status": "ready",
            "target": resolved_target.bot_name,
            "checks": [],
            "mutations": [],
        },
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("D0 preflight must not persist gate evidence")

    monkeypatch.setattr(phase_d_canary, "persist_gate_evidence", fail_if_called)

    exit_code = phase_d_canary.main(
        ["preflight", "--compose", str(compose_path), "--bot", "vagas_bot_01", "--json"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["mutations"] == []
    assert not (target.workspace_root / ".career-state" / "phase_d_gates" / "d0_preflight.json").exists()
    assert not (target.workspace_root / ".career-state" / "phase_d_runner_gate.json").exists()


def test_stage_hook_dry_run_does_not_write_config_and_limits_target_to_bot01(tmp_path):
    from career.services.canary_control import stage_hook

    target = _canary_target(tmp_path)
    _write_compose(_target_paths(tmp_path)["compose_path"], db_path=_target_paths(tmp_path)["control_db_path"])
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

    paths = _target_paths(tmp_path)
    _write_compose(paths["compose_path"], db_path=paths["control_db_path"])
    forbidden = _canary_target(tmp_path, bot_name="vagas_bot_02")
    with pytest.raises(ValueError, match="vagas_bot_01"):
        stage_hook(forbidden, apply=True)

    target = _canary_target(tmp_path)
    target.hermes_config.write_text("model:\n  default: test\nhooks: {}\n", encoding="utf-8")

    result = stage_hook(target, apply=True)

    assert result["status"] == "installed"
    assert result["target"] == "vagas_bot_01"
    assert result["apply"] is True
    backup_path = Path(result["backup"])
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == "model:\n  default: test\nhooks: {}\n"
    assert "career-harness-output" in target.hermes_config.read_text(encoding="utf-8")
    assert result["config"] == str(target.hermes_config)
    assert result["plugin"] == str(target.hermes_config.parent / "plugins" / "career-harness-output")
    assert result["mutations"] == [
        {"kind": "backup_config", "path": str(backup_path)},
        {"kind": "write_config", "path": str(target.hermes_config)},
        {"kind": "install_plugin", "path": str(target.hermes_config.parent / "plugins" / "career-harness-output")},
    ]
    assert "restart" not in json.dumps(result, ensure_ascii=False).lower()


def test_rollback_dry_run_reports_reversible_state_without_writing(tmp_path):
    from career.services.canary_control import rollback_dry_run, stage_hook

    target = _canary_target(tmp_path)
    _write_compose(_target_paths(tmp_path)["compose_path"], db_path=_target_paths(tmp_path)["control_db_path"])
    original = "model:\n  default: test\nhooks: {}\n"
    target.hermes_config.write_text(original, encoding="utf-8")
    stage_hook(target, apply=True)
    written = target.hermes_config.read_text(encoding="utf-8")

    result = rollback_dry_run(target)

    assert result["status"] == "dry_run_ok"
    assert result["target"] == "vagas_bot_01"
    assert result["apply"] is False
    assert Path(result["backup"]).exists()
    assert result["config"] == str(target.hermes_config)
    assert str(target.hermes_config).endswith("/vagas_bot_01/config.yaml")
    assert str(result["backup"]).endswith("/vagas_bot_01/config.yaml.bak.harness")
    assert target.hermes_config.read_text(encoding="utf-8") == written


def test_stage_hook_rejects_target_when_compose_resolves_bot01_to_another_profile_path(tmp_path):
    from career.services.canary_control import stage_hook

    paths = _target_paths(tmp_path)
    _write_compose(paths["compose_path"], db_path=paths["control_db_path"])
    wrong_profile = tmp_path / "profiles" / "other_profile" / "config.yaml"
    wrong_profile.parent.mkdir(parents=True, exist_ok=True)
    wrong_profile.write_text("model:\n  default: test\nhooks: {}\n", encoding="utf-8")
    target = _canary_target(tmp_path, hermes_config=wrong_profile)

    with pytest.raises(ValueError, match="compose-resolved profile path"):
        stage_hook(target, apply=False)


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


def test_phase_d_canary_route_smoke_cli_creates_ephemeral_root_when_omitted():
    script = Path(__file__).resolve().parents[1] / "scripts" / "phase_d_canary.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "route-smoke",
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
    assert payload[0]["deduplicated"] is False
    assert payload[1]["deduplicated"] is True


def test_run_controlled_canary_report_is_compact_and_leaves_bot02_snapshot_untouched(tmp_path):
    from scripts.phase_d_canary import run_controlled_canary

    target = _canary_target(tmp_path)
    bot02_snapshot = tmp_path / "bot02" / "session.json"
    bot02_snapshot.parent.mkdir(parents=True, exist_ok=True)
    bot02_snapshot.write_text(json.dumps({"bot": "vagas_bot_02", "messages": 3}), encoding="utf-8")
    before_hash = _hash_file(bot02_snapshot)
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
        result = run_controlled_canary(target, "canary-app", target.workspace_root)
    finally:
        _restore_env(previous)
    persisted_report = json.loads(
        (target.workspace_root / "canary_app_result.json").read_text(encoding="utf-8")
    )

    assert result["status"] == "completed"
    assert result["target"] == "vagas_bot_01"
    assert result["request_hash"] == result["runtime"]["request_hash"]
    assert result["sqlite_counts"] == {
        "cell_inputs": 1,
        "cell_requests": 1,
        "cell_handovers": 1,
        "validation_receipts": 3,
        "runtime_runs": 1,
        "artifacts": 1,
        "runtime_observations": 2,
    }
    assert "stdout" not in result["harness"]
    assert "stderr" not in result["harness"]
    assert "stdout" not in persisted_report["harness"]
    assert "stderr" not in persisted_report["harness"]
    serialized_report = json.dumps({"d2": persisted_report}, ensure_ascii=False)
    assert "Cargo: Operations Lead" not in serialized_report
    assert "Responsabilidades: liderar operações." not in serialized_report

    database = sqlite3.connect(target.control_db_path)
    database.row_factory = sqlite3.Row
    serialized_rows = json.dumps(
        {
            table: [dict(row) for row in database.execute(f"SELECT * FROM {table}")]
            for table in (
                "cell_inputs",
                "cell_requests",
                "cell_handovers",
                "validation_receipts",
                "artifacts",
                "runtime_observations",
            )
        },
        ensure_ascii=False,
    )
    database.close()
    assert "Cargo: Operations Lead" not in serialized_rows
    assert "Responsabilidades: liderar operações." not in serialized_rows
    assert _hash_file(bot02_snapshot) == before_hash


def test_stage_hook_cli_writes_compact_gate_evidence(monkeypatch, capsys, tmp_path):
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_text("services: {}\n", encoding="utf-8")
    target = _canary_target(tmp_path)

    monkeypatch.setattr(
        phase_d_canary,
        "resolve_target_from_compose",
        lambda **kwargs: target,
    )
    monkeypatch.setattr(
        phase_d_canary,
        "stage_hook",
        lambda resolved_target, apply=False: {
            "status": "dry_run_ok",
            "target": resolved_target.bot_name,
            "apply": apply,
            "config": str(resolved_target.hermes_config),
            "backup": str(resolved_target.hermes_config.with_suffix(".yaml.bak.harness")),
            "revertible": False,
            "mutations": [],
        },
    )

    exit_code = phase_d_canary.main(
        ["stage-hook", "--compose", str(compose_path), "--bot", "vagas_bot_01", "--json"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    evidence = json.loads(
        (target.workspace_root / ".career-state" / "phase_d_gates" / "d1_stage_hook.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (target.workspace_root / ".career-state" / "phase_d_runner_gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert exit_code == 0
    assert payload["status"] == "dry_run_ok"
    assert evidence["approved"] is True
    assert evidence["status"] == "dry_run_ok"
    assert manifest["approvals"]["d1"]["approved"] is True
    assert manifest["approvals"]["d1"]["status"] == "dry_run_ok"


def test_stage_hook_cli_apply_accepts_installed_as_successful_d1_gate(
    monkeypatch, capsys, tmp_path
):
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_text("services: {}\n", encoding="utf-8")
    target = _canary_target(tmp_path)

    monkeypatch.setattr(
        phase_d_canary,
        "resolve_target_from_compose",
        lambda **kwargs: target,
    )
    monkeypatch.setattr(
        phase_d_canary,
        "stage_hook",
        lambda resolved_target, apply=False: {
            "status": "installed",
            "target": resolved_target.bot_name,
            "apply": apply,
            "config": str(resolved_target.hermes_config),
            "backup": str(resolved_target.hermes_config.with_suffix(".yaml.bak.harness")),
            "revertible": True,
            "mutations": [],
        },
    )

    exit_code = phase_d_canary.main(
        [
            "stage-hook",
            "--compose",
            str(compose_path),
            "--bot",
            "vagas_bot_01",
            "--apply",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    evidence = json.loads(
        (target.workspace_root / ".career-state" / "phase_d_gates" / "d1_stage_hook.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (target.workspace_root / ".career-state" / "phase_d_runner_gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert exit_code == 0
    assert payload["status"] == "installed"
    assert evidence["approved"] is True
    assert evidence["status"] == "installed"
    assert manifest["approvals"]["d1"]["approved"] is True
    assert manifest["approvals"]["d1"]["status"] == "installed"


def test_controlled_run_cli_writes_gate_evidence_and_manifest(monkeypatch, capsys, tmp_path):
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_text("services: {}\n", encoding="utf-8")
    target = _canary_target(tmp_path)
    result = {
        "status": "completed",
        "target": "vagas_bot_01",
        "application_id": "canary-app",
        "run_id": "run-canary",
        "node_id": "analyze_fit",
        "attempt": 1,
        "request_json": str(target.workspace_root / ".career-state" / "applications_v2" / "canary-app" / "requests" / "cellular" / "run-canary" / "analyze_fit" / "1" / "request.json"),
        "request_md": str(target.workspace_root / ".career-state" / "applications_v2" / "canary-app" / "requests" / "cellular" / "run-canary" / "analyze_fit" / "1" / "request.md"),
        "request_hash": "request-hash",
        "read_allowlist": ["manifest.json"],
        "write_allowlist": ["fit_map.draft.json"],
        "harness": {"command": ["/usr/bin/python3", "controlled_agent_worker.py"]},
        "sqlite_counts": {"runtime_runs": 1},
    }

    monkeypatch.setattr(
        phase_d_canary,
        "resolve_target_from_compose",
        lambda **kwargs: target,
    )
    monkeypatch.setattr(
        phase_d_canary,
        "run_controlled_canary",
        lambda resolved_target, application_id, workspace: result,
    )

    exit_code = phase_d_canary.main(
        [
            "controlled-run",
            "--compose",
            str(compose_path),
            "--bot",
            "vagas_bot_01",
            "--application-id",
            "canary-app",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    evidence = json.loads(
        (target.workspace_root / ".career-state" / "phase_d_gates" / "d2_controlled_run.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (target.workspace_root / ".career-state" / "phase_d_runner_gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert exit_code == 0
    assert payload["status"] == "completed"
    assert evidence["approved"] is True
    assert evidence["result"]["application_id"] == "canary-app"
    assert manifest["approvals"]["d2"]["approved"] is True
    assert manifest["approvals"]["d2"]["status"] == "completed"


def test_probe_runner_compacts_prompt_and_preserves_bot02_snapshot(tmp_path, monkeypatch):
    from career.services.canary_control import probe_runner

    target = _canary_target(tmp_path)
    request_json, payload = _materialize_runner_gate_request(target.workspace_root)
    _write_runner_gate_manifest(target.workspace_root, request_json, payload)
    bot02_snapshot = tmp_path / "bot02" / "session.json"
    bot02_snapshot.parent.mkdir(parents=True, exist_ok=True)
    bot02_snapshot.write_text(json.dumps({"bot": "vagas_bot_02", "messages": 5}), encoding="utf-8")
    before_hash = _hash_file(bot02_snapshot)

    def fake_harness(self, **kwargs):
        return {
            "command": [
                "/usr/bin/hermes",
                "--accept-hooks",
                "-z",
                "Leia o arquivo .career-state/runner_probe/request.md. secret prompt with historical transcript and a long pasted job description",
            ],
            "returncode": 0,
            "stdout": "secret-stdout-token",
            "stderr": "secret-stderr-token",
            "isolation": {"status": "ok"},
        }

    monkeypatch.setattr(
        "career.services.canary_control.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        fake_harness,
    )

    result = probe_runner(
        target,
        {"kind": "hermes", "command": "hermes", "timeout_minutes": 90},
    )

    assert result["status"] == "completed"
    assert result["available"] is True
    assert result["returncode"] == 0
    assert "stdout" not in result
    assert "stderr" not in result
    serialized_report = json.dumps({"d3": result}, ensure_ascii=False)
    assert "secret prompt with historical transcript" not in serialized_report
    assert "secret-stdout-token" not in serialized_report
    assert "secret-stderr-token" not in serialized_report
    assert _hash_file(bot02_snapshot) == before_hash


@pytest.mark.parametrize("command", ["rollback-dry-run", "stage-hook", "controlled-run", "runner-probe"])
def test_phase_d_cli_blocks_bot02_before_resolution(monkeypatch, capsys, tmp_path, command):
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_text("services: {}\n", encoding="utf-8")
    seen: list[str] = []

    def explode(**kwargs):
        seen.append("resolve")
        raise AssertionError("resolve_target_from_compose must not be called for bot02")

    monkeypatch.setattr(phase_d_canary, "resolve_target_from_compose", explode)
    argv = [command, "--compose", str(compose_path), "--bot", "vagas_bot_02", "--json"]
    if command == "controlled-run":
        argv.extend(["--application-id", "existing-app"])

    exit_code = phase_d_canary.main(argv)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["status"] == "blocked"
    assert payload["target"] == "vagas_bot_02"
    assert seen == []
