from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from career import cli
from career.cells.executor import CellExecutor
from career.services.database import Database


@pytest.fixture
def seeded_application(tmp_path, monkeypatch):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"

    monkeypatch.setattr(cli, "Database", lambda: database, raising=False)
    monkeypatch.setattr(
        cli,
        "CellExecutor",
        lambda db, **kwargs: CellExecutor(
            db, applications_root=applications_root, **kwargs
        ),
        raising=False,
    )
    yield "app-1"
    database.close()


def test_plan_requires_application_id_and_emits_run_id(capsys, seeded_application):
    code = cli.main(
        [
            "applications",
            "plan",
            "--application-id",
            seeded_application,
            "--deliverable",
            "cv",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"]
    assert set(payload) == {
        "status",
        "run_id",
        "ready_nodes",
        "blocked_nodes",
        "artifact_paths",
        "next_action",
    }


def test_cellular_run_rejects_missing_application_id(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["applications", "run", "--run-id", "run-1"])

    assert exc_info.value.code == 2
    assert "--application-id" in capsys.readouterr().err


def test_run_repair_and_inspect_are_scoped_to_the_application(capsys, seeded_application):
    cli.main(
        [
            "applications",
            "plan",
            "--application-id",
            seeded_application,
            "--deliverable",
            "cv",
        ]
    )
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    assert cli.main(
        [
            "applications",
            "run",
            "--application-id",
            seeded_application,
            "--run-id",
            run_id,
        ]
    ) == 0
    run_payload = json.loads(capsys.readouterr().out)
    assert run_payload["run_id"] == run_id
    assert run_payload["blocked_nodes"] == ["capture_source"]

    assert cli.main(
        [
            "applications",
            "repair",
            "--application-id",
            seeded_application,
            "--run-id",
            run_id,
            "--node",
            "capture_source",
            "--reason",
            "source retry",
        ]
    ) == 0
    repair_payload = json.loads(capsys.readouterr().out)
    assert repair_payload["run_id"] == run_id
    assert repair_payload["ready_nodes"] == ["capture_source"]

    assert cli.main(
        [
            "applications",
            "inspect-run",
            "--application-id",
            seeded_application,
            "--run-id",
            run_id,
        ]
    ) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["run_id"] == run_id
    assert inspect_payload["ready_nodes"] == ["capture_source"]


def test_run_rejects_a_run_owned_by_a_different_application(capsys, seeded_application):
    cli.main(
        [
            "applications",
            "plan",
            "--application-id",
            seeded_application,
            "--deliverable",
            "cv",
        ]
    )
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    assert cli.main(
        [
            "applications",
            "run",
            "--application-id",
            "other-app",
            "--run-id",
            run_id,
        ]
    ) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"status": "blocked", "error": "run does not belong to application: other-app"}
