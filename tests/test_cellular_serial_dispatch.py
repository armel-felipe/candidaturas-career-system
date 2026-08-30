from __future__ import annotations

from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career.services import applications_v2
from career.services.application_context import paths_for
from career.services.database import Database


def _serial_executor(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"

    def normalize_handler(_context):
        return CellOutput(
            artifacts={
                "job_normalized.json": "{}",
                "handover_summary.json": "{}",
                "evidence_index.json": "{}",
            }
        )

    def validator(context, _output):
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
    paths = paths_for("dispatch-app", root=applications_root)
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text("Job description", encoding="utf-8")
    return database, executor, paths


def test_analyze_dispatch_requires_current_stage_and_scoped_compact_request(tmp_path):
    database, executor, paths = _serial_executor(tmp_path)
    try:
        plan = executor.plan(
            paths.application_id,
            {"cv", "notion"},
            execution_mode="serial",
        )
        statuses = dict(executor.resume(plan.run_id).statuses)
        statuses.update(
            {"capture_source": "validated", "normalize_job": "validated"}
        )
        request_json = paths.requests_dir / "cellular" / "run" / "analyze" / "1" / "request.json"
        request_md = request_json.with_suffix(".md")

        assert not applications_v2._cellular_analyze_dispatch_allowed(
            plan=plan,
            statuses=statuses,
            ready_nodes={"analyze_fit"},
            request_json=request_json,
            request_md=request_md,
        )

        request_json.parent.mkdir(parents=True, exist_ok=True)
        request_json.write_text("{}", encoding="utf-8")
        request_md.write_text("# request", encoding="utf-8")
        assert applications_v2._cellular_analyze_dispatch_allowed(
            plan=plan,
            statuses=statuses,
            ready_nodes={"analyze_fit"},
            request_json=request_json,
            request_md=request_md,
        )

        cv_statuses = dict(statuses)
        cv_statuses.update(
            {
                "analyze_fit": "validated",
                "compose_cv": "validated",
                "render_cv": "validated",
            }
        )
        assert not applications_v2._cellular_analyze_dispatch_allowed(
            plan=plan,
            statuses=cv_statuses,
            ready_nodes={"analyze_fit"},
            request_json=request_json,
            request_md=request_md,
        )
    finally:
        executor.release_workspace_lease()
        database.close()


def test_serial_review_blocker_keeps_repair_inside_cv_stage(tmp_path):
    database, executor, paths = _serial_executor(tmp_path)
    try:
        plan = executor.plan(
            paths.application_id,
            {"cv", "notion"},
            execution_mode="serial",
        )
        statuses = {
            node_id: "validated"
            for node_id in ("capture_source", "normalize_job", "analyze_fit", "compose_cv", "render_cv")
        }
        statuses.update(
            {
                "review_cv": "blocked",
                "deliver_cv": "planned",
                "sync_notion_initial": "planned",
                "sync_notion_final": "planned",
            }
        )
        report = applications_v2.serial_stage_report(plan, statuses)
        assert report.stage == "cv"
        assert report.status == "blocked"
        assert "deliver_cv" not in report.allowed_nodes
        assert "sync_notion_initial" not in report.allowed_nodes
    finally:
        executor.release_workspace_lease()
        database.close()
