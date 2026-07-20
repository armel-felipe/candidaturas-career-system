import json
from dataclasses import FrozenInstanceError, replace

import pytest

from career.cells import planner
from career.cells.contracts import CELL_CONTRACTS
from career.cells.planner import compile_run_plan
from career.services.application_context import paths_for


def test_cv_and_notion_plan_has_ordered_nodes(tmp_path):
    plan = compile_run_plan("app-1", {"cv", "notion"}, paths_for("app-1", root=tmp_path))
    assert plan.dependencies_of("compose_cv") == ("analyze_fit",)
    assert plan.dependencies_of("review_cv") == ("render_cv",)
    assert plan.dependencies_of("sync_notion_final") == ("review_cv",)
    assert plan.is_acyclic()


def test_independent_output_branches_are_ready_after_fit(tmp_path):
    plan = compile_run_plan("app-1", {"cv", "feras"}, paths_for("app-1", root=tmp_path))
    assert {"compose_cv", "generate_feras"} <= set(plan.ready_after({"analyze_fit"}))


def test_plan_is_frozen_and_persisted_after_validation(tmp_path):
    paths = paths_for("app-1", root=tmp_path)

    plan = compile_run_plan("app-1", {"cv"}, paths)

    persisted = json.loads((paths.app_dir / "plans" / f"{plan.run_id}.json").read_text())
    assert persisted["application_id"] == "app-1"
    assert persisted["contract_version"] == plan.contract_version
    with pytest.raises(FrozenInstanceError):
        plan.application_id = "other-app"


def test_capture_source_is_only_included_without_a_job_description(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    paths.job_description.parent.mkdir(parents=True)
    paths.job_description.write_text("A persisted job description", encoding="utf-8")

    plan = compile_run_plan("app-1", {"feras"}, paths)

    assert "capture_source" not in {node.node_id for node in plan.nodes}
    assert plan.dependencies_of("normalize_job") == ()


def test_unknown_deliverables_are_rejected_without_persisting(tmp_path):
    paths = paths_for("app-1", root=tmp_path)

    with pytest.raises(ValueError, match="unknown deliverable"):
        compile_run_plan("app-1", {"video"}, paths)

    assert not (paths.app_dir / "plans").exists()


def test_missing_contract_is_rejected_without_persisting(tmp_path, monkeypatch):
    paths = paths_for("app-1", root=tmp_path)
    contracts = dict(CELL_CONTRACTS)
    del contracts["review_feras"]
    monkeypatch.setattr(planner, "CELL_CONTRACTS", contracts)

    with pytest.raises(ValueError, match="missing contract"):
        compile_run_plan("app-1", {"feras"}, paths)

    assert not (paths.app_dir / "plans").exists()


def test_duplicate_node_ids_are_rejected_without_persisting(tmp_path, monkeypatch):
    paths = paths_for("app-1", root=tmp_path)
    contracts = dict(CELL_CONTRACTS)
    contracts["duplicate"] = replace(contracts["analyze_fit"], node_id="normalize_job")
    monkeypatch.setattr(planner, "CELL_CONTRACTS", contracts)

    with pytest.raises(ValueError, match="duplicate node ID"):
        compile_run_plan("app-1", {"cv"}, paths)

    assert not (paths.app_dir / "plans").exists()


def test_output_path_collisions_are_rejected_without_persisting(tmp_path, monkeypatch):
    paths = paths_for("app-1", root=tmp_path)
    contracts = dict(CELL_CONTRACTS)
    contracts["generate_feras"] = replace(
        contracts["generate_feras"], produces=contracts["compose_cv"].produces
    )
    monkeypatch.setattr(planner, "CELL_CONTRACTS", contracts)

    with pytest.raises(ValueError, match="output-path collision"):
        compile_run_plan("app-1", {"cv", "feras"}, paths)

    assert not (paths.app_dir / "plans").exists()


def test_cycles_are_rejected_without_persisting(tmp_path, monkeypatch):
    paths = paths_for("app-1", root=tmp_path)
    contracts = dict(CELL_CONTRACTS)
    contracts["normalize_job"] = replace(contracts["normalize_job"], requires=("analyze_fit",))
    monkeypatch.setattr(planner, "CELL_CONTRACTS", contracts)

    with pytest.raises(ValueError, match="cycle"):
        compile_run_plan("app-1", {"cv"}, paths)

    assert not (paths.app_dir / "plans").exists()
