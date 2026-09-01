from __future__ import annotations

import json

import pytest

from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career.services.application_context import paths_for
from career.services.database import Database


@pytest.fixture
def serial_executor(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"

    def normalize_handler(context):
        return CellOutput(
            artifacts={
                "job_normalized.json": "{}",
                "handover_summary.json": "{}",
                "evidence_index.json": "{}",
            }
        )

    def validator(context, output):
        report = context.paths.reviews_dir / f"{context.node_id}-{context.attempt}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        return ValidatorResult.passed(context.validator_command, report)

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={"normalize_job": normalize_handler},
        validators={"context:validate": validator},
    )
    application_paths = paths_for("serial-app", root=applications_root)
    application_paths.app_dir.mkdir(parents=True)
    application_paths.job_description.write_text("Job description", encoding="utf-8")
    yield executor
    database.close()


def test_serial_run_consumes_only_current_stage_node(serial_executor):
    plan = serial_executor.plan(
        "serial-app", {"cv", "notion"}, execution_mode="serial"
    )

    results = serial_executor.run_ready(plan.run_id)

    assert [result.node_id for result in results] == ["normalize_job"]
    assert serial_executor.node_status(plan.run_id, "normalize_job") == "validated"
    assert serial_executor.node_status(plan.run_id, "analyze_fit") == "planned"
    assert serial_executor.node_status(plan.run_id, "compose_cv") == "planned"
    assert serial_executor.node_status(plan.run_id, "sync_notion_initial") == "planned"


def test_serial_executor_rejects_node_from_later_stage(serial_executor):
    plan = serial_executor.plan(
        "serial-app", {"cv", "notion"}, execution_mode="serial"
    )
    for node_id in ("normalize_job", "analyze_fit", "compose_cv", "render_cv", "review_cv"):
        serial_executor.mark_validated(plan.run_id, node_id)

    with pytest.raises(ValueError, match="outside current serial stage"):
        serial_executor.run_one_ready(plan.run_id, "sync_notion_initial")

    with pytest.raises(ValueError, match="outside current serial stage"):
        serial_executor.run_ready(
            plan.run_id, _allowed_nodes={"sync_notion_initial"}, _max_nodes=1
        )

    assert serial_executor.node_status(plan.run_id, "deliver_cv") == "planned"
    assert serial_executor.node_status(plan.run_id, "sync_notion_initial") == "planned"


def test_stale_analyze_binding_is_quarantined_and_new_attempt_is_planned(
    tmp_path,
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={},
        validators={},
    )
    application_id = "stale-analyze-app"
    paths = paths_for(application_id, root=applications_root)
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text("Operations leadership\n", encoding="utf-8")

    try:
        plan = executor.plan(application_id, {"cv"})
        executor.mark_validated(plan.run_id, "normalize_job")
        for _ in range(5):
            prepared = executor.prepare_ready_node(plan.run_id, "analyze_fit")
            executor.defer_prepared_attempt(prepared, reason="seed stale attempt")

        paths.fit_map_draft.write_text('{"stale": true}', encoding="utf-8")
        (paths.app_dir / "fit_map.draft.binding.json").write_text(
            json.dumps(
                {
                    "kind": "cellular_fit_map_draft_binding",
                    "application_id": application_id,
                    "run_id": plan.run_id,
                    "node_id": "analyze_fit",
                    "attempt": 5,
                    "job_fingerprint": "wrong",
                    "draft_sha256": "wrong",
                    "manifest_path": "/old/manifest.json",
                }
            ),
            encoding="utf-8",
        )
        executor.fail(plan.run_id, "analyze_fit", "draft binding invalid")

        result = executor.recover_stale_external_attempt(
            plan.run_id, "analyze_fit"
        )

        assert result["status"] == "planned"
        assert result["next_attempt"] == 6
        assert not paths.fit_map_draft.exists()
        assert paths.requests_dir.joinpath("quarantine").is_dir()
        assert list(paths.requests_dir.joinpath("quarantine").rglob("*.json"))
        row = database.fetch_one(
            "SELECT status, latest_attempt, reserved_by, reservation_expires_at "
            "FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (plan.run_id, "analyze_fit"),
        )
        assert row["status"] == "planned"
        assert row["latest_attempt"] == 5
        assert row["reserved_by"] is None
        assert row["reservation_expires_at"] is None
        fresh = executor.prepare_ready_node(plan.run_id, "analyze_fit")
        assert fresh.attempt == 6
        executor.defer_prepared_attempt(fresh, reason="test cleanup")
    finally:
        database.close()
