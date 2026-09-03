from __future__ import annotations

import fnmatch
import json

import pytest

from career.services.approvals import ApprovalStore
from career.services.harness_supervisor import (
    SPECIALIST_OUTPUT_PATTERNS,
    HarnessSupervisor,
)


def test_processar_vaga_is_a_scoped_pipeline_request():
    decision = HarnessSupervisor().classify("pode processar a vaga?")

    assert decision.workflow == "pipeline"
    assert decision.parameters["requested_steps"] == ["cv", "onedrive", "notion"]


@pytest.mark.parametrize(
    "message",
    [
        "Pode criar o registro no notion?",
        "Quero registrar a vaga no Notion",
        "Pode salvar a análise no Notion?",
    ],
)
def test_notion_write_variants_route_to_notion_update(message):
    decision = HarnessSupervisor().classify(message)

    assert decision.workflow == "notion_update"
    assert decision.reason == "notion_write_request"


def test_fit_map_reuse_requires_scoped_final_artifact(tmp_path):
    application_dir = (
        tmp_path / ".career-state" / "applications_v2" / "app-live"
    )
    application_dir.mkdir(parents=True)
    (application_dir / "job_description.md").write_text(
        "Empresa: Example\nCargo: Operations Manager\nDescrição da vaga.",
        encoding="utf-8",
    )
    supervisor = HarnessSupervisor(tmp_path)

    assert supervisor._can_reuse_completed_fit_map("app-live") is False


def test_processar_vaga_uses_bound_session_and_returns_pipeline_result(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    captured: dict[str, object] = {}
    supervisor._record_session_intent = lambda *args, **kwargs: None
    supervisor._session_application_id = lambda *args, **kwargs: "app-live"

    def run_pipeline(message, **kwargs):
        captured.update(kwargs)
        return {"status": "awaiting_agent", "display_text": "Pipeline iniciado."}

    supervisor._execute_pipeline_request = run_pipeline
    result = supervisor.handle_message(
        "pode processar a vaga?",
        channel="telegram",
        execute=True,
        runtime_context={
            "runtime": "hermes",
            "profile_id": "bot01",
            "session_id": "session-live",
        },
    )

    assert captured["application_id"] == "app-live"
    assert captured["requested_steps"] == ["cv", "onedrive", "notion"]
    assert result["status"] == "awaiting_agent"
    assert result["result"]["display_text"] == "Pipeline iniciado."


def test_valid_notion_update_materializes_current_fit_map(monkeypatch, tmp_path):
    import career.services.multiagent as multiagent

    app_dir = tmp_path / "applications_v2" / "app-live"
    app_dir.mkdir(parents=True)
    app_paths = type(
        "Paths",
        (),
        {
            "application_id": "app-live",
            "derived_dir": app_dir / "derived",
        },
    )()
    expected = {"kind": "fit_map_seed", "context": {"analysis": {}}}
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        multiagent.derived_context_service,
        "materialize_context",
        lambda application_id, kind, database: calls.append((application_id, kind)) or expected,
    )
    monkeypatch.setattr(
        multiagent.derived_context_service,
        "export_materialized_context",
        lambda application_id, kind, destination, database: destination.parent.mkdir(parents=True, exist_ok=True),
    )

    result = multiagent._prepare_scoped_compact_inputs(
        "notion-update", app_paths, database=object()
    )

    assert result == expected
    assert calls == [("app-live", "fit_map_seed")]


def test_confirmation_resumes_approved_action(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    approval = ApprovalStore(tmp_path).create(
        action="notion-update",
        payload={"pending_action_path": ".career-state/pending_actions/update.json"},
    )
    supervisor.execute_approved_action = lambda approval_id: {
        "status": "completed",
        "approval_id": approval_id,
    }
    context = {
        "runtime": "hermes",
        "profile_id": "bot02",
        "session_id": "session-approval",
        "application_id": "app-live",
    }
    supervisor._write_pending_input(
        {
            "input_kind": "confirmation",
            "approval_id": approval["approval_id"],
            "application_id": "app-live",
            "session_id": "session-approval",
            "display_text": "Confirme a atualização.",
        },
        runtime_context=context,
        channel="telegram",
    )

    result = supervisor.handle_message(
        "sim", channel="telegram", execute=True, runtime_context=context
    )

    assert result["status"] == "completed"
    assert result["result"]["display_text"] == "A ação foi confirmada e executada."
    assert ApprovalStore(tmp_path).get(approval["approval_id"])["status"] == "approved"


def test_unroutable_message_is_blocked_with_reply(tmp_path):
    result = HarnessSupervisor(tmp_path).handle_message(
        "uma mensagem sem ação definida", execute=True
    )

    assert result["status"] == "blocked"
    assert result["result"]["blocker_reason"] == "generic_runner_unavailable"
    assert result["result"]["display_text"]


def test_cv_isolation_allows_outputs_of_mandatory_scoped_gate(tmp_path):
    import fnmatch

    patterns = SPECIALIST_OUTPUT_PATTERNS["cv"]
    expected = {
        ".career-state/applications_v2/app-keeta/fit_map.json",
        ".career-state/applications_v2/app-keeta/derived/keyword_ats_registry.json",
        ".career-state/applications_v2/app-keeta/derived/keyword_translation_candidates.json",
        ".career-state/applications_v2/app-keeta/cv_content.json",
        ".career-state/applications_v2/app-keeta/cv_review_report.json",
        ".career-state/applications_v2/app-keeta/polish_review.json",
        ".career-state/derived/keyword_ats_registry.json",
        ".career-state/derived/keyword_translation_candidates.json",
        "outputs/felipe_armel_cv_keeta_en.docx",
        "outputs/_tmp/cv_deliver_report.json",
        "outputs/_tmp/delivery_report.json",
        "outputs/_tmp/output_review_report.json",
    }
    assert all(any(fnmatch.fnmatch(path, pattern) for pattern in patterns) for path in expected)
    assert not any(
        fnmatch.fnmatch(".career-state/applications_v2/app-keeta/not_allowed.json", pattern)
        for pattern in patterns
    )


def test_fit_map_menu_counts_legacy_payload_gaps_and_objections(monkeypatch):
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)
    supervisor.db = object()
    supervisor.root = None
    monkeypatch.setattr(
        supervisor,
        "_materialized_fit_map_summary",
        lambda _application_id: {
            "cargo": "Head de Operações",
            "empresa": "Dreamers.gr",
            "nota_final": 4.0,
            "gaps_count": 3,
            "objecoes_count": 3,
            "keyword_registration": {},
        },
    )
    # The user-facing menu consumes these normalized counters; this guards
    # against the previous truthiness fallback converting valid counts to 0.
    result = supervisor._build_agent_menu_for_result(
        {"status": "completed", "step": "fit-map", "application_id": "notion_624"},
        runtime_context=None,
    )
    assert "Gaps mapeados: 3 | Objecoes mapeadas: 3" in result["summary_lines"]


@pytest.mark.parametrize("step", ["notion-update", "email-draft"])
def test_control_action_allowlist_accepts_scoped_pending_action(step):
    allowed = (
        ".career-state/applications_v2/notion_624/pending_actions/request-1.json"
    )
    forbidden = ".career-state/applications_v2/notion_624/not_allowed.json"
    patterns = SPECIALIST_OUTPUT_PATTERNS[step]

    assert any(fnmatch.fnmatch(allowed, pattern) for pattern in patterns)
    assert not any(fnmatch.fnmatch(forbidden, pattern) for pattern in patterns)


def test_notion_update_scoped_pending_action_is_awaiting_approval(monkeypatch, tmp_path):
    from subprocess import CompletedProcess

    application_dir = (
        tmp_path / ".career-state" / "applications_v2" / "notion_624"
    )
    request_dir = application_dir / "requests" / "manual_agent_requests" / "runs" / "req-1"
    request_dir.mkdir(parents=True)
    request_json = request_dir / "request.json"
    request_md = request_dir / "request.md"
    request_json.write_text(
        '{"application_id":"notion_624","extras":{"pending_action_path":".career-state/applications_v2/notion_624/pending_actions/req-1.json"}}',
        encoding="utf-8",
    )
    request_md.write_text("request", encoding="utf-8")

    supervisor = HarnessSupervisor(tmp_path)
    supervisor.prepare_specialist = lambda *args, **kwargs: {
        "status": "prepared",
        "request": {
            "request_id": "req-1",
            "versioned_request_json": str(request_json.relative_to(tmp_path)),
            "versioned_request_md": str(request_md.relative_to(tmp_path)),
        },
        "validation": {"status": "ok"},
        "approval": {"approval_id": "approval-1", "status": "pending"},
    }
    supervisor._maybe_auto_execute_approved_action = lambda *args, **kwargs: None

    class FakeRunner:
        def build_command(self, _request):
            return ["fake-hermes"]

        def run(self, _request):
            pending = application_dir / "pending_actions" / "req-1.json"
            pending.parent.mkdir(parents=True)
            pending.write_text("{}", encoding="utf-8")
            return CompletedProcess(["fake-hermes"], 0, "ok", "")

    supervisor.runner = FakeRunner()
    result = supervisor._execute_pipeline_specialist(
        "notion-update", objective="atualizar registro", extras={"application_id": "notion_624"}
    )

    assert result["status"] == "awaiting_approval"
    assert result.get("blocker_reason") is None
    assert result["execution"]["isolation"]["status"] == "ok"


def test_specialist_reported_blocker_is_not_collapsed_into_no_output(tmp_path):
    from subprocess import CompletedProcess

    application_dir = tmp_path / ".career-state" / "applications_v2" / "app-live"
    request_dir = application_dir / "requests" / "manual_agent_requests" / "runs" / "req-1"
    request_dir.mkdir(parents=True)
    request_json = request_dir / "request.json"
    request_md = request_dir / "request.md"
    request_json.write_text(
        '{"application_id":"app-live","expected_outputs":["cv_content.json"]}',
        encoding="utf-8",
    )
    request_md.write_text("request", encoding="utf-8")

    supervisor = HarnessSupervisor(tmp_path)
    supervisor.prepare_specialist = lambda *args, **kwargs: {
        "status": "prepared",
        "request": {
            "request_id": "req-1",
            "versioned_request_json": str(request_json.relative_to(tmp_path)),
            "versioned_request_md": str(request_md.relative_to(tmp_path)),
        },
        "validation": {"status": "ok"},
    }

    class FakeRunner:
        def build_command(self, _request):
            return ["fake-hermes"]

        def run(self, _request):
            return CompletedProcess(
                ["fake-hermes"],
                0,
                "A solicitação foi bloqueada pelo fluxo canônico (serial_run_failed).",
                "",
            )

    supervisor.runner = FakeRunner()
    result = supervisor._execute_pipeline_specialist(
        "cv", objective="criar CV", extras={"application_id": "app-live"}
    )

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "specialist_reported_blocked"
    assert result["execution"]["reported_blocker_reason"] == "serial_run_failed"
    persisted = json.loads(
        (
            tmp_path
            / result["execution"]["run_dir"]
            / "result.json"
        ).read_text(encoding="utf-8")
    )
    assert persisted["blocker_reason"] == "specialist_reported_blocked"


def test_manual_cv_reconciles_only_current_approved_artifact(monkeypatch, tmp_path):
    import hashlib
    import json
    from types import SimpleNamespace

    from career.services.persistence.analysis_repository import AnalysisRepository
    from career.services.persistence.application_repository import (
        ApplicationIdentity,
        ApplicationRepository,
    )

    supervisor = HarnessSupervisor(tmp_path)
    ApplicationRepository(supervisor.db).create_application(
        ApplicationIdentity(
            application_id="app-live",
            company="Example",
            role="Operations Director",
            fingerprint="fp-live",
        )
    )
    revision_id = AnalysisRepository(supervisor.db).create_revision(
        "app-live",
        {"fingerprint": "fp-live", "dimensions": [], "keywords": []},
        source_hash="source-live",
    )
    app_dir = tmp_path / ".career-state" / "applications_v2" / "app-live"
    app_dir.mkdir(parents=True)
    fit_map = app_dir / "fit_map.json"
    fit_map.write_text("current-fit-map", encoding="utf-8")
    artifact = tmp_path / "outputs" / "cv.docx"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"approved-cv")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    fit_digest = hashlib.sha256(fit_map.read_bytes()).hexdigest()
    report = app_dir / "cv_review_report.json"
    report.write_text(
        json.dumps(
            {
                "kind": "cv",
                "artifact": str(artifact),
                "artifact_sha256": digest,
                "approved_for_delivery": True,
                "_approval_meta": {
                    "artifact_sha256": digest,
                    "fit_map_sha256": fit_digest,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "career.services.review.record_approved_cv_provenance",
        lambda **kwargs: SimpleNamespace(
            artifact_id="artv-reconciled", path=str(kwargs["artifact"])
        ),
    )

    result = supervisor._reconcile_manual_cv_provenance(
        "app-live", run_id="req-live"
    )

    assert result == {
        "status": "registered",
        "artifact_id": "artv-reconciled",
        "artifact_path": str(artifact),
        "source_revision_id": revision_id,
    }


def test_control_action_rejects_pending_path_from_another_application():
    payload = {
        "application_id": "notion_624",
        "extras": {
            "pending_action_path": ".career-state/applications_v2/other-app/pending_actions/req-1.json"
        },
    }

    error = HarnessSupervisor._control_artifact_scope_error("notion-update", payload)

    assert error is not None
