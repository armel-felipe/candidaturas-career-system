from __future__ import annotations

from career.cells.planner import compile_run_plan
from career.cells.serial import serial_stage_report, stage_node_ids
from career.services.application_context import paths_for


def test_serial_stage_report_stops_at_first_incomplete_stage(tmp_path):
    paths = paths_for("app-serial", root=tmp_path)
    paths.job_description.parent.mkdir(parents=True)
    paths.job_description.write_text("A persisted job description", encoding="utf-8")
    plan = compile_run_plan("app-serial", {"cv", "notion"}, paths, execution_mode="serial")

    statuses = {node.node_id: "planned" for node in plan.nodes}
    statuses["normalize_job"] = "validated"

    report = serial_stage_report(plan, statuses)

    assert report.stage == "analyze"
    assert report.status == "ready"
    assert report.next_stage == "cv"
    assert report.completed_nodes == ("normalize_job",)
    assert report.blocked_nodes == ()


def test_serial_cv_stage_has_internal_order(tmp_path):
    paths = paths_for("app-serial", root=tmp_path)
    paths.job_description.parent.mkdir(parents=True)
    paths.job_description.write_text("A persisted job description", encoding="utf-8")
    plan = compile_run_plan("app-serial", {"cv", "notion"}, paths, execution_mode="serial")

    assert stage_node_ids("cv") == ("compose_cv", "render_cv", "review_cv")

    statuses = {node.node_id: "validated" for node in plan.nodes}
    statuses["compose_cv"] = "validated"
    statuses["render_cv"] = "validated"
    statuses["review_cv"] = "planned"
    statuses["deliver_cv"] = "planned"
    statuses["sync_notion_initial"] = "planned"
    statuses["sync_notion_final"] = "planned"

    report = serial_stage_report(plan, statuses)

    assert report.stage == "cv"
    assert report.status == "ready"
    assert report.next_stage == "delivery"


def test_serial_report_does_not_expose_notion_before_delivery(tmp_path):
    paths = paths_for("app-serial", root=tmp_path)
    paths.job_description.parent.mkdir(parents=True)
    paths.job_description.write_text("A persisted job description", encoding="utf-8")
    plan = compile_run_plan("app-serial", {"cv", "notion"}, paths, execution_mode="serial")

    statuses = {node.node_id: "validated" for node in plan.nodes}
    statuses["deliver_cv"] = "planned"
    statuses["sync_notion_initial"] = "planned"
    statuses["sync_notion_final"] = "planned"

    report = serial_stage_report(plan, statuses)

    assert report.stage == "delivery"
    assert report.next_stage == "notion"
    assert "sync_notion_initial" not in report.allowed_nodes
    assert "sync_notion_final" not in report.allowed_nodes


def test_serial_report_preserves_blocked_and_awaiting_statuses(tmp_path):
    paths = paths_for("app-serial", root=tmp_path)
    paths.job_description.parent.mkdir(parents=True)
    paths.job_description.write_text("A persisted job description", encoding="utf-8")
    plan = compile_run_plan("app-serial", {"cv"}, paths, execution_mode="serial")

    statuses = {node.node_id: "validated" for node in plan.nodes}
    statuses["analyze_fit"] = "awaiting_agent"
    analyze_report = serial_stage_report(plan, statuses)
    assert analyze_report.stage == "analyze"
    assert analyze_report.status == "awaiting_agent"

    statuses["analyze_fit"] = "validated"
    statuses["review_cv"] = "blocked"
    blocked_report = serial_stage_report(plan, statuses)
    assert blocked_report.stage == "cv"
    assert blocked_report.status == "blocked"
    assert blocked_report.blocked_nodes == ("review_cv",)
