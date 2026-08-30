from __future__ import annotations

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
