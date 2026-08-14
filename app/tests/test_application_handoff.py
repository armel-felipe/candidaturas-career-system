from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
import yaml

from career.services.application_handoff import ApplicationHandoffService
from career.services.database import Database


APPLICATION_ID = "local_test_ifood_4453385301"
SOURCE_URL = "https://www.linkedin.com/jobs/view/4453385301/"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _make_source(root: Path, *, application_id: str = APPLICATION_ID) -> Path:
    app_dir = root / application_id
    app_dir.mkdir(parents=True)
    job_description = "# iFood\n\nGerente de Desenvolvimento de Negócios- Growth\n"
    (app_dir / "job_description.md").write_text(job_description, encoding="utf-8")
    _write_json(
        app_dir / "identity.json",
        {
            "kind": "application_identity",
            "application_id": application_id,
            "source_type": "linkedin_job",
            "source_id": SOURCE_URL,
            "company": "iFood",
            "role": "Gerente de Desenvolvimento de Negócios- Growth",
        },
    )
    _write_json(app_dir / "fit_map.draft.json", {"application_id": application_id, "status": "draft"})
    for name, payload in {
        "job_normalized.json": {"application_id": application_id, "title": "Growth"},
        "handover_summary.json": {"application_id": application_id, "summary": "compact"},
        "evidence_index.json": {"application_id": application_id, "items": []},
    }.items():
        _write_json(app_dir / "derived" / name, payload)
    return app_dir


def _make_compose(tmp_path: Path) -> Path:
    control_root = tmp_path / "control"
    workspace = tmp_path / "workspace"
    state01 = tmp_path / "state01"
    state02 = tmp_path / "state02"
    profile01 = tmp_path / "profile01"
    profile02 = tmp_path / "profile02"
    for path in (control_root, workspace, state01, state02, profile01, profile02):
        path.mkdir(parents=True, exist_ok=True)
    compose = {
        "services": {
            "vagas_bot_01": {
                "environment": {
                    "CAREER_CONTROL_DB_PATH": "/control/career.db",
                    "CAREER_CONTROL_DB_ID": "test-control",
                    "CAREER_HERMES_PROFILE_ID": "profile-01",
                },
                "volumes": [
                    f"{workspace}:/workspace/candidaturas",
                    f"{state01}:/workspace/candidaturas/.career-state",
                    f"{control_root}:/control",
                    f"{profile01}:/opt/data/profiles/vagas_bot_01",
                ],
            },
            "vagas_bot_02": {
                "environment": {
                    "CAREER_CONTROL_DB_PATH": "/control/career.db",
                    "CAREER_CONTROL_DB_ID": "test-control",
                    "CAREER_HERMES_PROFILE_ID": "profile-02",
                },
                "volumes": [
                    f"{workspace}:/workspace/candidaturas",
                    f"{state02}:/workspace/candidaturas/.career-state",
                    f"{control_root}:/control",
                    f"{profile02}:/opt/data/profiles/vagas_bot_02",
                ],
            },
        }
    }
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_text(yaml.safe_dump(compose), encoding="utf-8")
    return compose_path


def _target_state(compose_path: Path, bot_name: str) -> Path:
    payload = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    for volume in payload["services"][bot_name]["volumes"]:
        source, destination, *_ = volume.split(":")
        if destination == "/workspace/candidaturas/.career-state":
            return Path(source)
    raise AssertionError("state mount missing")


def _control_db(compose_path: Path) -> Path:
    payload = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    control_root = next(
        Path(volume.split(":")[0])
        for volume in payload["services"]["vagas_bot_01"]["volumes"]
        if volume.split(":")[1] == "/control"
    )
    return control_root / "career.db"


def _snapshot(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in path.rglob("*")
        if item.is_file()
    }


def test_dry_run_reports_projection_without_mutating_target_or_control_db(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    _make_source(source_root)
    compose_path = _make_compose(tmp_path)
    target_app = _target_state(compose_path, "vagas_bot_01") / "applications_v2" / APPLICATION_ID
    target_app.mkdir(parents=True)
    (target_app / "job_description.md").write_text("fixture\n", encoding="utf-8")
    before_target = _snapshot(target_app)

    result = ApplicationHandoffService(
        compose_path=compose_path,
        source_root=source_root,
    ).handoff(APPLICATION_ID, "vagas_bot_01", dry_run=True)

    assert result["status"] == "dry_run"
    assert result["source_fingerprint"] == hashlib.sha256(
        (source_root / APPLICATION_ID / "job_description.md").read_bytes()
    ).hexdigest()
    assert result["projection"]["files"]
    assert _snapshot(target_app) == before_target
    db = Database(_control_db(compose_path))
    db.init_schema()
    assert db.fetch_one("SELECT 1 FROM applications") is None
    assert db.fetch_one("SELECT 1 FROM application_runs") is None
    assert db.fetch_one("SELECT 1 FROM workflow_events") is None
    db.close()


def test_apply_quarantines_stale_target_and_projects_only_canonical_inputs(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_app = _make_source(source_root)
    compose_path = _make_compose(tmp_path)
    target_state = _target_state(compose_path, "vagas_bot_01")
    target_app = target_state / "applications_v2" / APPLICATION_ID
    target_app.mkdir(parents=True)
    (target_app / "job_description.md").write_text("Operations Lead\n", encoding="utf-8")
    (target_app / "stale-request.json").write_text("stale", encoding="utf-8")

    result = ApplicationHandoffService(compose_path=compose_path, source_root=source_root).handoff(
        APPLICATION_ID, "vagas_bot_01", apply=True
    )

    assert result["status"] == "applied"
    assert not (target_app / "stale-request.json").exists()
    assert (target_app / "job_description.md").read_bytes() == (source_app / "job_description.md").read_bytes()
    assert (target_app / "identity.json").is_file()
    assert (target_app / "fit_map.draft.json").is_file()
    assert (target_app / "derived" / "job_normalized.json").is_file()
    assert not (target_app / "fit_map.json").exists()
    quarantine = target_state / ".handoff_quarantine"
    assert any(item.is_dir() for item in quarantine.iterdir())
    assert (target_app.stat().st_mode & 0o700) == 0o700
    assert (target_app / "job_description.md").stat().st_mode & 0o600 == 0o600
    assert _snapshot(source_app) == _snapshot(source_root / APPLICATION_ID)


def test_apply_rejects_identity_or_source_fingerprint_mismatch(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_app = _make_source(source_root)
    compose_path = _make_compose(tmp_path)
    original = _snapshot(source_app)
    identity = json.loads((source_app / "identity.json").read_text(encoding="utf-8"))
    identity["application_id"] = "other-app"
    _write_json(source_app / "identity.json", identity)
    with pytest.raises(ValueError, match="identity application_id"):
        ApplicationHandoffService(compose_path=compose_path, source_root=source_root).handoff(
            APPLICATION_ID, "vagas_bot_01", apply=True
        )
    assert not (_target_state(compose_path, "vagas_bot_01") / "applications_v2" / APPLICATION_ID).exists()
    db = Database(_control_db(compose_path))
    db.init_schema()
    assert db.fetch_one("SELECT 1 FROM applications") is None
    db.close()
    assert original != _snapshot(source_app)


def test_apply_quarantines_target_with_same_application_id_but_old_fingerprint(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    _make_source(source_root)
    compose_path = _make_compose(tmp_path)
    target_app = _target_state(compose_path, "vagas_bot_01") / "applications_v2" / APPLICATION_ID
    target_app.mkdir(parents=True)
    _write_json(target_app / "identity.json", {"application_id": APPLICATION_ID})
    (target_app / "job_description.md").write_text("old source\n", encoding="utf-8")
    _write_json(target_app / "handoff_manifest.json", {"source_fingerprint": "0" * 64})

    result = ApplicationHandoffService(compose_path=compose_path, source_root=source_root).handoff(
        APPLICATION_ID, "vagas_bot_01", apply=True
    )

    assert result["status"] == "applied"
    assert any((_target_state(compose_path, "vagas_bot_01") / ".handoff_quarantine").iterdir())
    assert "old source" not in target_app.joinpath("job_description.md").read_text(encoding="utf-8")


def test_target_bot_is_resolved_from_canonical_compose_and_arbitrary_state_path_is_not_allowed(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    _make_source(source_root)
    compose_path = _make_compose(tmp_path)
    service = ApplicationHandoffService(compose_path=compose_path, source_root=source_root)
    assert service.resolve_target("vagas_bot_01").bot_name == "vagas_bot_01"
    assert service.resolve_target("vagas_bot_02").bot_name == "vagas_bot_02"
    assert "target_state_root" not in service.handoff.__annotations__


def test_same_fingerprint_handoff_is_idempotent_and_conflicting_live_handoff_fails(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    _make_source(source_root)
    compose_path = _make_compose(tmp_path)
    service = ApplicationHandoffService(compose_path=compose_path, source_root=source_root)
    first = service.handoff(APPLICATION_ID, "vagas_bot_01", apply=True)
    second = service.handoff(APPLICATION_ID, "vagas_bot_01", apply=True)
    assert first["status"] == "applied"
    assert second["status"] == "idempotent"
    with pytest.raises(RuntimeError, match="another bot"):
        service.handoff(APPLICATION_ID, "vagas_bot_02", apply=True)
    db = Database(_control_db(compose_path))
    db.init_schema()
    assert db.fetch_one("SELECT COUNT(*) AS count FROM applications")["count"] == 1
    assert db.fetch_one("SELECT COUNT(*) AS count FROM application_runs")["count"] == 1
    db.close()


def test_apply_registers_input_manifest_and_one_analyze_fit_cell(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    _make_source(source_root)
    compose_path = _make_compose(tmp_path)
    result = ApplicationHandoffService(compose_path=compose_path, source_root=source_root).handoff(
        APPLICATION_ID, "vagas_bot_01", apply=True
    )

    db = Database(_control_db(compose_path))
    db.init_schema()
    assert db.fetch_one("SELECT stage, funil_stage FROM applications WHERE id = ?", (APPLICATION_ID,))["stage"] == "analyze_pending"
    node = db.fetch_one("SELECT * FROM cell_nodes")
    assert node["node_id"] == "analyze_fit"
    assert node["status"] == "reserved"
    assert node["reserved_by"] == "vagas_bot_01"
    assert db.fetch_one("SELECT COUNT(*) AS count FROM cell_inputs")["count"] >= 4
    request = db.fetch_one("SELECT payload_json, payload_bytes FROM cell_requests")
    payload = json.loads(request["payload_json"])
    assert payload["cellular"] is True
    assert payload["application_id"] == APPLICATION_ID
    assert payload["limits"]["hard_context_tokens"] == 32000
    assert "conversation" not in json.dumps(payload).lower()
    assert db.fetch_one(
        "SELECT 1 FROM workflow_events WHERE application_id = ? AND event = 'controlled_handoff_prepared'",
        (APPLICATION_ID,),
    )
    assert db.fetch_one("SELECT 1 FROM workflow_events WHERE event LIKE '%notion%'") is None
    assert result["cell"]["node_id"] == "analyze_fit"
    db.close()
