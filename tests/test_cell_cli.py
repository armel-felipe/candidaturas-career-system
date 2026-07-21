from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from career import cli
from career.cells import executor as executor_module
from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career.services.application_context import paths_for
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


def test_fresh_cli_run_executes_registered_production_handler_and_validator(
    tmp_path, monkeypatch, capsys
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    application_paths = paths_for("app-1", root=applications_root)
    application_paths.app_dir.mkdir(parents=True)
    application_paths.job_description.write_text(
        "# Operations Manager\n\nLead planning and logistics operations.",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "Database", lambda: database)
    monkeypatch.setattr(executor_module, "APPLICATIONS_DIR", applications_root)
    try:
        assert cli.main(
            ["applications", "plan", "--application-id", "app-1", "--deliverable", "cv"]
        ) == 0
        run_id = json.loads(capsys.readouterr().out)["run_id"]

        assert cli.main(
            [
                "applications",
                "run",
                "--application-id",
                "app-1",
                "--run-id",
                run_id,
            ]
        ) == 0

        payload = json.loads(capsys.readouterr().out)
        assert payload["blocked_nodes"] == []
        assert payload["ready_nodes"] == ["analyze_fit"]
        assert database.fetch_one(
            "SELECT status FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (run_id, "normalize_job"),
        ) == {"status": "validated"}
        assert {
            row["artifact_name"]
            for row in database.fetch_all(
                "SELECT artifact_name FROM artifacts WHERE run_id = ?", (run_id,)
            )
        } == {"job_normalized.json", "handover_summary.json", "evidence_index.json"}
    finally:
        database.close()


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


def test_inspect_run_never_reports_completed_while_a_node_is_reserved(tmp_path, monkeypatch, capsys):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    monkeypatch.setattr(cli, "Database", lambda: database)
    monkeypatch.setattr(
        cli,
        "CellExecutor",
        lambda db, **kwargs: CellExecutor(db, applications_root=applications_root, **kwargs),
    )
    try:
        assert cli.main(
            ["applications", "plan", "--application-id", "app-1", "--deliverable", "cv"]
        ) == 0
        run_id = json.loads(capsys.readouterr().out)["run_id"]
        CellExecutor(database, applications_root=applications_root).store.reserve_node(
            run_id, "capture_source", "other-worker"
        )

        assert cli.main(
            [
                "applications",
                "inspect-run",
                "--application-id",
                "app-1",
                "--run-id",
                run_id,
            ]
        ) == 0

        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "running"
        assert payload["next_action"].startswith("career applications inspect-run")
    finally:
        database.close()


def test_run_finalizes_a_terminal_run_and_reports_published_artifacts(
    tmp_path, monkeypatch, capsys
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    application_paths = paths_for("app-1", root=applications_root)
    application_paths.app_dir.mkdir(parents=True)
    application_paths.job_description.write_text("Job description", encoding="utf-8")

    def handler(context):
        artifacts = {
            "normalize_job": {
                "job_normalized.json": "{}",
                "handover_summary.json": "{}",
                "evidence_index.json": "{}",
            },
            "analyze_fit": {"fit_map.json": "{}"},
            "sync_notion_initial": {"notion_initial_receipt.json": "{}"},
        }
        return CellOutput(artifacts=artifacts[context.node_id])

    def validator(context, output):
        report = context.paths.reviews_dir / f"{context.node_id}-{context.validator_command}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        return ValidatorResult.passed(context.validator_command, report)

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={
            "normalize_job": handler,
            "analyze_fit": handler,
            "sync_notion_initial": handler,
        },
        validators={
            "context:validate": validator,
            "validate:fit-map": validator,
            "validate:fit-map:quality": validator,
            "validate-provenance": validator,
            "validate-notion-receipt": validator,
        },
    )
    plan = executor.plan("app-1", {"notion"})
    while executor.ready_nodes(plan.run_id):
        executor.run_ready(plan.run_id)

    monkeypatch.setattr(cli, "Database", lambda: database)
    monkeypatch.setattr(
        cli,
        "CellExecutor",
        lambda db, **kwargs: CellExecutor(db, applications_root=applications_root, **kwargs),
    )
    try:
        assert cli.main(
            [
                "applications",
                "run",
                "--application-id",
                "app-1",
                "--run-id",
                plan.run_id,
            ]
        ) == 0

        payload = json.loads(capsys.readouterr().out)
        artifact_paths = [Path(path) for path in payload["artifact_paths"]]
        assert payload["status"] == "completed"
        assert artifact_paths and all(path.is_file() for path in artifact_paths)
        assert all(application_paths.artifacts_dir in path.parents for path in artifact_paths)
        assert database.fetch_one(
            "SELECT status FROM application_runs WHERE run_id = ?", (plan.run_id,)
        ) == {"status": "completed"}
        assert (
            application_paths.app_dir
            / "runs"
            / plan.run_id
            / "run_completion_manifest.json"
        ).is_file()
    finally:
        database.close()


@pytest.mark.parametrize("application_id", ["../escape", "/tmp/escape", "app/child", r"app\\child"])
def test_cli_rejects_unsafe_application_ids(application_id, capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["applications", "plan", "--application-id", application_id, "--deliverable", "cv"])

    assert exc_info.value.code == 2
    assert "application_id" in capsys.readouterr().err
