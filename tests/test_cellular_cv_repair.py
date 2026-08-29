from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from career.services import applications_v2
from career.cells.executor import CellExecutor, PreparedCellAttempt
from career.cells import handlers as cell_handlers
from career.cells.capabilities import CapabilitySet
from career.cells.handlers import CellOutput, ValidatorResult
from career.services.application_context import paths_for
from career.services import multiagent
from career.cells.executor import CellExecutionResult
from career.cells.handlers import CellExecutionContext
from career.services.database import Database
from career.utils import ValidationFailure, write_json


def test_explicit_cellular_application_uses_application_id_not_notion_record_id():
    application_id = "local_20260829T012907_793390_daki_66644a79"

    assert applications_v2._record_key(
        {
            "application_id": application_id,
            "record_id": 617,
            "_explicit_cellular": True,
        }
    ) == application_id
    assert applications_v2._record_key(
        {
            "application_id": application_id,
            "record_id": 617,
            "_local_cellular": True,
        }
    ) == application_id
    assert applications_v2._record_key(
        {"application_id": application_id, "record_id": 617}
    ) == "617"


def test_cellular_cv_repair_request_is_scoped_and_lists_missing_top8(tmp_path):
    paths = paths_for("repair-cell", root=tmp_path / "applications")
    run_id = "run_repair"
    attempt = 2
    manifest_path = paths.app_dir / "cells" / run_id / "compose_cv" / str(attempt) / "manifest.json"
    candidate_path = paths.requests_dir / "cellular" / run_id / "repair" / str(attempt) / "cv_content.json"
    review_path = paths.app_dir / "cells" / run_id / "review_cv" / "1" / "staging" / "cv_review.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        manifest_path,
        {
            "application_id": paths.application_id,
            "run_id": run_id,
            "node_id": "compose_cv",
            "attempt": attempt,
            "capabilities": {
                "read_paths": [str(review_path.resolve())],
                "write_paths": [str(candidate_path.resolve())],
            },
        },
    )
    write_json(
        review_path,
        {
            "top8_keywords": [
                {
                    "keyword": "Gestão de P&L",
                    "coverage_class": "missing_unexplained",
                    "experience_target": "iFood",
                }
            ],
            "blockers": [{"id": "ats_top8_no_missing_unexplained"}],
        },
    )

    request_json, request_md = applications_v2._write_cellular_cv_repair_request(
        paths=paths,
        run_id=run_id,
        attempt=attempt,
        manifest_path=manifest_path,
        review_report_path=review_path,
        candidate_path=candidate_path,
    )

    payload = json.loads(request_json.read_text(encoding="utf-8"))
    assert payload["application_id"] == paths.application_id
    assert payload["run_id"] == run_id
    assert payload["node_id"] == "compose_cv"
    assert payload["missing_unexplained_top8"][0]["keyword"] == "Gestão de P&L"
    assert payload["blocking_review_ids"] == ["ats_top8_no_missing_unexplained"]
    assert payload["expected_outputs"] == [str(candidate_path.resolve())]
    assert str(paths.app_dir.resolve()) in payload["expected_outputs"][0]
    assert set(payload["read_allowlist"]) == {str(review_path.resolve())}
    assert set(payload["write_allowlist"]) == {str(candidate_path.resolve())}
    assert str(Path(".career-state/derived/keyword_ats_registry.json")) not in request_md.read_text(encoding="utf-8")
    assert request_json.stat().st_mode & 0o004
    assert request_md.stat().st_mode & 0o004
    assert review_path.stat().st_mode & 0o004
    assert candidate_path.parent.stat().st_mode & 0o002


def test_external_agent_handoff_prepares_nested_uid_access_only_inside_application(tmp_path):
    paths = paths_for("handoff-permissions", root=tmp_path / "applications")
    input_path = paths.app_dir / "nested" / "input" / "review.json"
    output_path = paths.app_dir / "nested" / "output" / "candidate.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("{}", encoding="utf-8")
    input_path.parent.chmod(0o700)
    input_path.chmod(0o600)
    output_path.parent.chmod(0o700)

    applications_v2._prepare_external_agent_handoff(
        request_json=paths.app_dir / "request.json",
        request_md=paths.app_dir / "request.md",
        read_allowlist=[str(input_path)],
        write_allowlist=[str(output_path)],
        application_dir=paths.app_dir,
    )

    assert input_path.stat().st_mode & 0o004
    assert input_path.parent.stat().st_mode & 0o001
    assert output_path.parent.stat().st_mode & 0o003
    assert not (tmp_path.stat().st_mode & 0o002)


def test_repair_candidate_binding_adds_attempt_identity_and_rejects_conflicts(tmp_path):
    candidate = tmp_path / "application" / "repair" / "cv_content.json"
    write_json(candidate, {"metadata": {"application_id": "app-1"}, "experiences": []})

    applications_v2._bind_cellular_cv_repair_candidate(
        candidate, application_id="app-1", run_id="run-1", attempt=2
    )
    metadata = json.loads(candidate.read_text(encoding="utf-8"))["metadata"]
    assert metadata["application_id"] == "app-1"
    assert metadata["run_id"] == "run-1"
    assert metadata["compose_attempt"] == 2

    write_json(
        candidate,
        {"metadata": {"application_id": "app-1", "run_id": "other-run"}},
    )
    with pytest.raises(ValidationFailure, match="another run"):
        applications_v2._bind_cellular_cv_repair_candidate(
            candidate, application_id="app-1", run_id="run-1", attempt=2
        )


def test_persisted_blocked_review_resume_requires_real_manifest_identity(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    application_id = "resume-real"
    paths = paths_for(application_id, root=root)
    executor = CellExecutor(database, applications_root=root)
    try:
        plan = executor.plan(application_id, {"cv"})
        for node_id in ("normalize_job", "analyze_fit", "compose_cv", "render_cv"):
            executor.mark_validated(plan.run_id, node_id)
        executor.fail(plan.run_id, "review_cv", "ats_top8_no_missing_unexplained")

        persisted = applications_v2._existing_blocked_cellular_review(
            executor, paths, plan.run_id
        )
        assert persisted is not None
        assert persisted.run_id == plan.run_id
        assert persisted.attempt == 1
        assert persisted.blocker == "ats_top8_no_missing_unexplained"
        persisted_manifest = json.loads(
            persisted.manifest_path.read_text(encoding="utf-8")
        )
        assert persisted_manifest["application_id"] == application_id

        manifest_path = persisted.manifest_path
        base_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for field, value in (
            ("application_id", "another-application"),
            ("run_id", "another-run"),
            ("node_id", "compose_cv"),
            ("attempt", 2),
            ("status", "validated"),
        ):
            invalid_manifest = {**base_manifest, field: value}
            manifest_path.write_text(json.dumps(invalid_manifest), encoding="utf-8")
            with pytest.raises(ValidationFailure, match="manifest identity"):
                applications_v2._existing_blocked_cellular_review(
                    executor, paths, plan.run_id
                )
        manifest_path.write_text(json.dumps(base_manifest), encoding="utf-8")

        repair = executor.repair(
            plan.run_id, "compose_cv", "ats_top8_no_missing_unexplained"
        )
        executor.defer_prepared_attempt(
            PreparedCellAttempt(
                run_id=plan.run_id,
                application_id=application_id,
                node_id="compose_cv",
                attempt=repair.attempt,
                worker_id=executor.worker_id,
                manifest_path=repair.manifest_path,
            ),
            reason="agent_failed_to_write_candidate",
        )
        pending = applications_v2._pending_cellular_cv_repair(
            executor, paths, plan.run_id
        )
        assert pending is not None
        assert pending.run_id == plan.run_id
        assert pending.blocker == "ats_top8_no_missing_unexplained"
    finally:
        database.close()


def test_blocked_review_dispatches_scoped_repair_and_reenters_same_run(monkeypatch, tmp_path):
    root = tmp_path / "applications"
    database = Database(tmp_path / "career.db")
    database.init_schema()
    application_id = "repair-dispatch"
    run_id = "run_repair_dispatch"
    database.execute(
        "INSERT INTO application_runs "
        "(run_id, application_id, graph_json, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'blocked', '2026-08-29T00:00:00+00:00', '2026-08-29T00:00:00+00:00')",
        (run_id, application_id, "{}"),
    )
    database.execute(
        "INSERT INTO cell_nodes "
        "(run_id, node_id, status, requires_json, latest_attempt, created_at, updated_at) "
        "VALUES (?, 'review_cv', 'blocked', '[]', 1, '2026-08-29T00:00:00+00:00', '2026-08-29T00:00:00+00:00')",
        (run_id,),
    )
    paths = paths_for(application_id, root=root)
    review_manifest = paths.app_dir / "cells" / run_id / "review_cv" / "1" / "manifest.json"
    review_report = review_manifest.parent / "staging" / "cv_review.json"
    review_report.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        review_manifest,
        {
            "kind": "cell_attempt_manifest",
            "run_id": run_id,
            "application_id": application_id,
            "node_id": "review_cv",
            "attempt": 1,
            "status": "blocked",
            "blocker": {"reason": "ats_top8_no_missing_unexplained"},
        },
    )
    write_json(
        review_report,
        {
            "top8_keywords": [
                {
                    "keyword": "Gestão de P&L",
                    "coverage_class": "missing_unexplained",
                    "experience_target": "iFood",
                }
            ],
            "blockers": [{"id": "ats_top8_no_missing_unexplained"}],
        },
    )

    class FakeExecutor:
        worker_id = "test-worker"

        def __init__(self, database, **_kwargs):
            self.database = database
            self.calls = []
            self.round = 0

        def ready_nodes(self, _run_id):
            return ()

        def run_ready(self, _run_id):
            self.round += 1
            if self.round == 1:
                return ()
            return tuple(
                CellExecutionResult(
                    run_id=run_id,
                    node_id=node,
                    attempt=2 if node == "compose_cv" else 1,
                    status="validated",
                    manifest_path=review_manifest,
                )
                for node in ("compose_cv", "render_cv", "review_cv")
            )

        def repair(self, requested_run_id, node_id, reason):
            self.calls.append((requested_run_id, node_id, reason))
            manifest = paths.app_dir / "cells" / run_id / "compose_cv" / "2" / "manifest.json"
            candidate = applications_v2._cellular_cv_repair_candidate_path(paths, run_id, 2)
            manifest.parent.mkdir(parents=True, exist_ok=True)
            write_json(
                manifest,
                {
                    "kind": "cell_attempt_manifest",
                    "application_id": application_id,
                    "run_id": run_id,
                    "node_id": "compose_cv",
                    "attempt": 2,
                    "capabilities": {
                        "read_paths": [str(review_report.resolve())],
                        "write_paths": [str(candidate.resolve())],
                    },
                },
            )
            return SimpleNamespace(
                run_id=requested_run_id,
                attempt=2,
                node_id=node_id,
                manifest_path=manifest,
            )

        def is_terminal(self, _run_id):
            return False

    fake_executor = FakeExecutor(database)
    monkeypatch.setattr(applications_v2, "V2_DIR", root)
    monkeypatch.setattr("career.cells.executor.CellExecutor", lambda *args, **kwargs: fake_executor)

    def fake_repair_agent(*, paths, repair_result, **_kwargs):
        candidate = applications_v2._cellular_cv_repair_candidate_path(
            paths, repair_result.run_id, repair_result.attempt
        )
        candidate.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            candidate,
            {
                "metadata": {
                    "application_id": paths.application_id,
                    "run_id": repair_result.run_id,
                    "compose_attempt": repair_result.attempt,
                },
                "experiences": [],
            },
        )
        return {"returncode": 0, "isolation": {"status": "ok"}}, candidate

    monkeypatch.setattr(applications_v2, "_cellular_cv_repair_agent", fake_repair_agent)
    try:
        result = applications_v2._process_cellular_application(
            {
                "application_id": application_id,
                "description": "Operações, planejamento e liderança.",
                "company": "Acme",
                "role": "Head de Operações",
                "status": "Fila Agente",
                "_cellular_run_id": run_id,
            },
            options=SimpleNamespace(
                workspace_owner="test-owner",
                control_db_id="",
                model="",
                variant="",
                release_workspace_lease=False,
            ),
            config={"repair_max_attempts": 1, "success_status": "CV pronto"},
            database_path=database.db_path,
        )
    finally:
        database.close()

    assert fake_executor.calls == [(run_id, "compose_cv", "ats_top8_no_missing_unexplained")]
    assert any(item["node_id"] == "compose_cv" for item in result)
    assert any(item["node_id"] == "review_cv" and item["status"] == "validated" for item in result)


def test_real_compose_repair_manifest_passes_cellular_context_guard(tmp_path):
    workspace = tmp_path / ".career-state"
    applications_root = workspace / "applications_v2"
    database = Database(tmp_path / "career.db")
    database.init_schema()
    application_id = "repair-real-manifest"
    run_id = "run_real_manifest"
    paths = paths_for(application_id, root=applications_root)
    executor = CellExecutor(database, applications_root=applications_root)
    try:
        plan = executor.plan(application_id, {"cv"})
        run_id = plan.run_id
        for node_id in ("normalize_job", "analyze_fit", "compose_cv", "review_cv"):
            executor.mark_validated(run_id, node_id)
        review_path = paths.cells_dir / run_id / "review_cv" / "1" / "staging" / "cv_review.json"
        write_json(
            review_path,
            {
                "blockers": [{"id": "ats_top8_no_missing_unexplained"}],
                "top8_keywords": [
                    {
                        "keyword": "Gestão de P&L",
                        "coverage_class": "missing_unexplained",
                        "experience_target": "iFood",
                    }
                ],
            },
        )
        repaired = executor.repair(run_id, "compose_cv", "ats_top8_no_missing_unexplained")
        candidate = applications_v2._cellular_cv_repair_candidate_path(
            paths, run_id, repaired.attempt
        )
        request_json, _request_md = applications_v2._write_cellular_cv_repair_request(
            paths=paths,
            run_id=run_id,
            attempt=repaired.attempt,
            manifest_path=repaired.manifest_path,
            review_report_path=review_path,
            candidate_path=candidate,
        )
        payload = json.loads(request_json.read_text(encoding="utf-8"))
        context = multiagent.validate_cellular_request_context(payload, root=tmp_path)
        assert context["application_id"] == application_id
        assert context["run_id"] == run_id
        assert context["node_id"] == "compose_cv"
        assert context["write_allowlist"] == [str(candidate.resolve())]
        assert all(str(workspace) in path for path in context["read_allowlist"] + context["write_allowlist"])
    finally:
        database.close()


def test_repaired_compose_consumes_candidate_instead_of_rebuilding_from_fit_map(monkeypatch, tmp_path):
    paths = paths_for("repair-handler", root=tmp_path / "applications")
    fit_map_path = paths.app_dir / "fit_map.json"
    normalized_path = paths.app_dir / "job_normalized.json"
    candidate = applications_v2._cellular_cv_repair_candidate_path(paths, "run_handler", 2)
    fit_map_path.parent.mkdir(parents=True, exist_ok=True)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        fit_map_path,
        {"provenance": {"candidate_facts_revision": "facts-1"}},
    )
    write_json(normalized_path, {"job_identity": {"language": "pt-BR"}})
    repaired_payload = {
        "metadata": {
            "application_id": paths.application_id,
            "run_id": "run_handler",
            "compose_attempt": 2,
        },
        "experiences": [{"company": "iFood", "role": "Head", "bullets": []}],
    }
    write_json(candidate, repaired_payload)

    def fail_rebuild(*_args, **_kwargs):
        raise AssertionError("repair must consume the agent candidate")

    monkeypatch.setattr(cell_handlers.cv_content_service, "build_cv_content", fail_rebuild)
    inputs = {
        "fit_map.json": {
            "path": str(fit_map_path),
            "sha256": applications_v2.sha256_file(fit_map_path),
            "application_id": paths.application_id,
        },
        "job_normalized.json": {
            "path": str(normalized_path),
            "sha256": applications_v2.sha256_file(normalized_path),
            "application_id": paths.application_id,
        },
    }
    context = CellExecutionContext(
        application_id=paths.application_id,
        run_id="run_handler",
        node_id="compose_cv",
        attempt=2,
        paths=paths,
        manifest_path=paths.app_dir / "manifest.json",
        staging_dir=paths.app_dir / "staging",
        inputs=inputs,
        output_paths=(),
        capabilities=CapabilitySet(
            application_root=paths.app_dir,
            read_paths=(fit_map_path, normalized_path, candidate),
            write_paths=(candidate,),
        ),
        repair_scope="cv_content_only",
        repair_reason="ats_top8_no_missing_unexplained",
    )

    output = cell_handlers._compose_cv(context)
    assert json.loads(output.artifacts["cv_content.json"]) == repaired_payload


def test_repaired_compose_rejects_candidate_from_another_run(tmp_path):
    paths = paths_for("repair-handler-identity", root=tmp_path / "applications")
    fit_map_path = paths.app_dir / "fit_map.json"
    normalized_path = paths.app_dir / "job_normalized.json"
    candidate = applications_v2._cellular_cv_repair_candidate_path(paths, "run_actual", 2)
    fit_map_path.parent.mkdir(parents=True, exist_ok=True)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    write_json(fit_map_path, {"provenance": {"candidate_facts_revision": "facts-1"}})
    write_json(normalized_path, {"job_identity": {"language": "pt-BR"}})
    write_json(
        candidate,
        {
            "metadata": {
                "application_id": paths.application_id,
                "run_id": "run_other",
                "compose_attempt": 2,
            },
            "experiences": [],
        },
    )
    inputs = {
        "fit_map.json": {"path": str(fit_map_path), "sha256": applications_v2.sha256_file(fit_map_path), "application_id": paths.application_id},
        "job_normalized.json": {"path": str(normalized_path), "sha256": applications_v2.sha256_file(normalized_path), "application_id": paths.application_id},
    }
    context = CellExecutionContext(
        application_id=paths.application_id,
        run_id="run_actual",
        node_id="compose_cv",
        attempt=2,
        paths=paths,
        manifest_path=paths.app_dir / "manifest.json",
        staging_dir=paths.app_dir / "staging",
        inputs=inputs,
        output_paths=(),
        capabilities=CapabilitySet(application_root=paths.app_dir, read_paths=(fit_map_path, normalized_path, candidate), write_paths=(candidate,)),
        repair_scope="cv_content_only",
        repair_reason="ats_top8_no_missing_unexplained",
    )

    import pytest

    with pytest.raises(ValueError, match="another run"):
        cell_handlers._compose_cv(context)


def test_real_executor_repair_republishes_cv_and_reruns_all_cv_gates(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    def passing_validator(command):
        def validate(context, _output):
            report = context.paths.reviews_dir / f"{context.node_id}-{context.attempt}-{command.replace(':', '-')}.json"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text("{}", encoding="utf-8")
            return ValidatorResult.passed(command, report)

        return validate

    executor = CellExecutor(
        database,
        applications_root=root,
        handlers={
            "compose_cv": lambda _context: CellOutput(
                artifacts={"cv_content.json": '{"metadata": {"application_id": "real-flow"}}'}
            ),
            "render_cv": lambda _context: CellOutput(artifacts={"cv.docx": b"docx"}),
            "review_cv": lambda _context: CellOutput(
                artifacts={
                    "cv_review.json": '{"approved_for_delivery": true}',
                    "polish_review.json": "{}",
                    "approved_cv_manifest.json": '{"approved_for_delivery": true}',
                    "keyword_ats_registry.json": "{}",
                }
            ),
            "deliver_cv": lambda _context: CellOutput(
                artifacts={"cv_delivery_receipt.json": '{"status": "delivered"}'},
            ),
        },
        validators={
            command: passing_validator(command)
            for command in (
                "cv:validate-content",
                "validate-cv-provenance",
                "validate:docx",
                "cv:approve",
                "validate-delivery-receipt",
            )
        },
    )
    try:
        seeded_paths = paths_for("real-flow", root=root)
        seeded_paths.app_dir.mkdir(parents=True, exist_ok=True)
        seeded_paths.job_description.write_text("Head de Operações", encoding="utf-8")
        plan = executor.plan("real-flow", {"cv"})
        for node_id in ("normalize_job", "analyze_fit", "compose_cv", "render_cv", "review_cv", "deliver_cv"):
            executor.mark_validated(plan.run_id, node_id)
        executor.fail(plan.run_id, "review_cv", "ats_top8_no_missing_unexplained")

        repaired = executor.repair(plan.run_id, "compose_cv", "ats_top8_no_missing_unexplained")
        assert repaired.attempt == 2
        assert executor.node_status(plan.run_id, "render_cv") == "superseded"
        assert executor.node_status(plan.run_id, "review_cv") == "superseded"
        assert executor.node_status(plan.run_id, "deliver_cv") == "superseded"

        results = list(executor.run_ready(plan.run_id))
        for _ in range(8):
            results.extend(executor.run_ready(plan.run_id))
        assert {item.node_id for item in results} >= {"compose_cv", "render_cv", "review_cv", "deliver_cv"}
        assert all(item.status == "validated" for item in results)
        assert executor.node_status(plan.run_id, "compose_cv") == "validated"
        assert executor.node_status(plan.run_id, "render_cv") == "validated"
        assert executor.node_status(plan.run_id, "review_cv") == "validated"
        assert executor.node_status(plan.run_id, "deliver_cv") == "validated"
        manifests = database.fetch_all(
            "SELECT node_id, attempt, status FROM cell_attempts WHERE run_id = ? AND attempt = 2 ORDER BY node_id",
            (plan.run_id,),
        )
        assert {row["node_id"] for row in manifests} >= {"compose_cv", "render_cv", "review_cv", "deliver_cv"}
        assert all(row["status"] == "validated" for row in manifests)
    finally:
        database.close()
