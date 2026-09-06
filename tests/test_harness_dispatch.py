import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from career.services.harness_supervisor import HarnessSupervisor
from career.services.harness_conversation import ContextualPlanner
from career.services.maintenance_orchestrator import MaintenanceOrchestrator
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)

from tests.test_canonical_maintenance import make_git_fixture


def _maintenance_payload(**overrides):
    payload = {
        "kind": "canonical_maintenance",
        "requester_profile": "vagas_bot_01",
        "objective": "corrigir leitor canonico",
        "allowed_paths": ["src/career/services/cv_content.py"],
        "roadmap_id": "MAINT-002",
        "spec": {
            "requirements": [
                {"id": "REQ-1", "text": "Encaminhar pedido ao orquestrador"}
            ]
        },
        "evidence": {"error": "falha reproduzida pelo bot"},
    }
    payload.update(overrides)
    return payload


def test_blocked_pipeline_result_exposes_next_step_to_async_worker():
    result = HarnessSupervisor._pipeline_result(
        intake={
            "application_id": "app-demo",
            "next_required_step": "fill_fit_map_draft",
        },
        specialist={
            "status": "blocked",
            "step": "fit-map",
            "blocker_reason": "fit_map_draft_required",
        },
    )

    assert result["status"] == "blocked"
    assert "app-demo" in result["display_text"]
    assert "fit_map.draft.json" in result["display_text"]


def test_menu_state_is_isolated_by_hermes_profile_and_session(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    bot_01 = {
        "runtime": "hermes", "profile_id": "vagas_bot_01", "session_id": "chat-1"
    }
    bot_02 = {
        "runtime": "hermes", "profile_id": "vagas_bot_02", "session_id": "chat-1"
    }

    supervisor._write_menu_state(
        {"menu_context": "linkedin_saved_jobs", "headline": "Bot 01", "numbered_items": [{"number": 1}]},
        runtime_context=bot_01,
        channel="telegram",
    )
    supervisor._write_menu_state(
        {"menu_context": "active_job", "headline": "Bot 02", "numbered_items": [{"number": 2}]},
        runtime_context=bot_02,
        channel="telegram",
    )

    assert supervisor._menu_state_payload(bot_01, channel="telegram")["headline"] == "Bot 01"
    assert supervisor._menu_state_payload(bot_02, channel="telegram")["headline"] == "Bot 02"
    assert supervisor._resolve_menu_selection("1", runtime_context=bot_02, channel="telegram") is None


def test_fit_map_summary_question_is_a_session_bound_read(monkeypatch):
    supervisor = HarnessSupervisor()
    context = {"runtime": "hermes", "profile_id": "vagas_bot_01", "session_id": "chat-1"}
    monkeypatch.setattr(
        supervisor, "_session_application_id", lambda *_args, **_kwargs: "app-bot-01"
    )
    monkeypatch.setattr(
        supervisor,
        "_materialized_fit_map_summary",
        lambda application_id: {
            "cargo": "Cargo correto", "empresa": "Empresa correta", "nota_final": 8.5,
            "gaps_count": 1, "objecoes_count": 2, "keyword_registration": {},
        },
    )

    assert supervisor.classify("qual o fit-map da vaga analisada?").workflow == "fit_map_summary"
    result = supervisor._session_fit_map_summary(runtime_context=context, channel="telegram")

    assert result["application_id"] == "app-bot-01"
    assert "Cargo correto | Empresa correta" in result["display_text"]


def test_natural_application_reference_extracts_id_and_intent():
    supervisor = HarnessSupervisor()

    decision = supervisor.classify(
        "tem uma vaga 625 do notion queria que entendesse, porque quero a experiencia da wehandle no cv"
    )

    assert decision.workflow == "natural_application_route"
    assert decision.parameters == {"record_id": 625, "intent": "cv"}

    decision = supervisor.classify("quero que olhe a candidatura 625 do notion")
    assert decision.workflow == "natural_application_route"
    assert decision.parameters == {"record_id": 625, "intent": "analysis"}


@pytest.mark.parametrize(
    "message",
    ["continue", "Finalize", "Pode executar", "pode prosseguir", "pode seguir"],
)
def test_short_pipeline_controls_use_deterministic_pipeline_route(message):
    decision = HarnessSupervisor().classify(message)

    assert decision.workflow == "pipeline"
    assert decision.reason == "short_pipeline_control"
    assert decision.parameters == {"requested_steps": []}


def test_pipeline_continuation_finalizes_a_valid_fit_map_draft(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    monkeypatch.setattr(
        "career.services.intake.resume",
        lambda **_kwargs: {
            "status": "active_intake_ready",
            "application_id": "app-live",
            "next_required_step": "build_fit_map",
        },
    )
    captured = {}

    def fake_finalize_fit_map(**kwargs):
        captured.update(kwargs)
        return {"status": "completed", "application_id": "app-live"}

    monkeypatch.setattr(
        supervisor, "_finalize_fit_map_pipeline", fake_finalize_fit_map
    )

    result = supervisor._execute_pipeline_request(
        "prossiga",
        requested_steps=[],
        application_id="app-live",
        model=None,
        variant=None,
        runtime_context=None,
        channel="telegram",
    )

    assert result["status"] == "completed"
    assert result["stages"] == [{"status": "completed", "application_id": "app-live"}]
    assert captured == {"application_id": "app-live"}


def test_affirmative_reply_to_explicit_execution_offer_uses_pipeline(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    context = {
        "runtime": "hermes",
        "profile_id": "vagas_bot_01",
        "session_id": "affirmative-offer",
    }
    monkeypatch.setattr(
        supervisor, "_session_application_id", lambda *_args, **_kwargs: "app-live"
    )
    monkeypatch.setattr(
        supervisor,
        "_session_pipeline_intent",
        lambda *_args, **_kwargs: {"application_id": "app-live", "requested_steps": []},
    )
    captured = {}

    def fake_pipeline(message, **kwargs):
        captured.update(kwargs)
        return {"status": "completed", "application_id": "app-live"}

    monkeypatch.setattr(supervisor, "_execute_pipeline_request", fake_pipeline)
    monkeypatch.setattr(
        supervisor,
        "_run_generic_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("affirmative execution confirmation must not use generic chat")
        ),
    )

    result = supervisor.handle_message(
        "sim",
        channel="telegram",
        execute=True,
        runtime_context=context,
        conversation_history=[
            {
                "role": "assistant",
                "content": "O draft está pronto. Quer que eu prossiga?",
            }
        ],
    )

    assert result["decision"]["workflow"] == "pipeline"
    assert result["decision"]["reason"] == "contextual_pipeline_confirmation"
    assert captured["application_id"] == "app-live"
    assert captured["requested_steps"] == []


def test_contextual_plan_advances_bound_internal_next_step(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    ApplicationRepository(supervisor.db).create_application(
        ApplicationIdentity(
            application_id="app-live",
            notion_id="626",
            company="Keeta",
            role="Operations Director",
            fingerprint="fp-live",
        )
    )
    context = {
        "runtime": "hermes",
        "profile_id": "vagas_bot_01",
        "session_id": "contextual-next-step",
    }
    supervisor.conversation_planner = ContextualPlanner(
        output_provider=lambda _prompt: (
            '{"intent":"resume","target_hints":{},"requested_steps":[],'
            '"authorization":"user_request","confidence":"high"}'
        )
    )
    monkeypatch.setattr(
        supervisor, "_session_application_id", lambda *_args, **_kwargs: "app-live"
    )
    captured = {}

    def fake_pipeline(message, **kwargs):
        captured.update(kwargs)
        return {"status": "completed", "application_id": "app-live"}

    monkeypatch.setattr(supervisor, "_execute_pipeline_request", fake_pipeline)
    monkeypatch.setattr(
        supervisor,
        "_run_generic_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("contextual continuation must not use generic chat")
        ),
    )

    result = supervisor.handle_message(
        "faz o próximo passo desta candidatura",
        channel="telegram",
        execute=True,
        runtime_context=context,
    )

    assert result["decision"]["workflow"] == "pipeline"
    assert result["decision"]["reason"] == "contextual_plan"
    assert result["result"]["application_id"] == "app-live"
    assert captured["requested_steps"] == []


def test_contextual_plan_resolves_unique_canonical_target(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    ApplicationRepository(supervisor.db).create_application(
        ApplicationIdentity(
            application_id="app-keeta-sales",
            notion_id="625",
            company="Keeta",
            role="Sales Operations Manager",
            fingerprint="fp-keeta-sales",
        )
    )
    supervisor.conversation_planner = ContextualPlanner(
        output_provider=lambda _prompt: (
            '{"intent":"analyze","target_hints":{"company":"Keeta",'
            '"role":"Sales Operations Manager"},"requested_steps":[],'
            '"authorization":"user_request","confidence":"high"}'
        )
    )
    captured = {}
    monkeypatch.setattr(
        supervisor,
        "_execute_natural_application",
        lambda message, resolution, **kwargs: captured.update(resolution)
        or {"status": "completed", "application_id": resolution["application_id"]},
    )

    result = supervisor.handle_message(
        "olhe essa oportunidade e veja o fit",
        channel="telegram",
        execute=True,
        runtime_context={
            "runtime": "hermes",
            "profile_id": "vagas_bot_01",
            "session_id": "contextual-unique",
        },
    )

    assert result["decision"]["workflow"] == "natural_application_route"
    assert captured["application_id"] == "app-keeta-sales"
    assert captured["source"] == "canonical_company_role"


def test_contextual_plan_shows_ambiguous_canonical_targets(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    repository = ApplicationRepository(supervisor.db)
    for index, (suffix, role) in enumerate(
        (("one", "Sales Operations Manager"), ("two", "Sales Operations Lead")),
        start=1,
    ):
        repository.create_application(
            ApplicationIdentity(
                application_id=f"app-keeta-{suffix}",
                notion_id=str(620 + index),
                company="Keeta",
                role=role,
                fingerprint=f"fp-keeta-{suffix}",
            )
        )
    supervisor.conversation_planner = ContextualPlanner(
        output_provider=lambda _prompt: (
            '{"intent":"analyze","target_hints":{"company":"Keeta"},'
            '"requested_steps":[],"authorization":"user_request",'
            '"confidence":"high"}'
        )
    )
    monkeypatch.setattr(
        supervisor,
        "_execute_natural_application",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("ambiguous target must not execute")
        ),
    )

    result = supervisor.handle_message(
        "analisa uma oportunidade da Keeta",
        channel="telegram",
        execute=True,
        runtime_context={
            "runtime": "hermes",
            "profile_id": "vagas_bot_01",
            "session_id": "contextual-ambiguous",
        },
    )

    assert result["decision"]["workflow"] == "natural_application_route"
    assert result["result"]["status"] == "awaiting_input"
    assert len(result["result"]["candidates"]) == 2
    assert "Keeta" in result["result"]["display_text"]


def test_contextual_plan_keeps_external_action_approval_gated(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    ApplicationRepository(supervisor.db).create_application(
        ApplicationIdentity(
            application_id="app-live",
            notion_id="626",
            company="Keeta",
            role="Operations Director",
            fingerprint="fp-live",
        )
    )
    supervisor.conversation_planner = ContextualPlanner(
        output_provider=lambda _prompt: (
            '{"intent":"update_notion","target_hints":{},"requested_steps":[],'
            '"authorization":"user_request","confidence":"high"}'
        )
    )
    monkeypatch.setattr(
        supervisor, "_session_application_id", lambda *_args, **_kwargs: "app-live"
    )
    monkeypatch.setattr(
        supervisor,
        "execute_specialist",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("approval preparation must not execute a specialist")
        ),
    )
    monkeypatch.setattr(
        supervisor,
        "prepare_specialist",
        lambda *args, **kwargs: {
            "status": "prepared",
            "request": {"request_id": "request-test"},
            "approval": {"approval_id": "approval-test", "status": "pending"},
        },
    )
    decision = supervisor.classify("atualiza o registro dessa vaga")
    assert decision.workflow == "generic_assistant"

    result = supervisor.handle_message(
        "atualiza o registro dessa vaga",
        channel="telegram",
        execute=True,
        runtime_context={
            "runtime": "hermes",
            "profile_id": "vagas_bot_01",
            "session_id": "contextual-external",
        },
    )

    assert result["decision"]["workflow"] == "notion_update"
    assert result["decision"]["requires_approval"] is True


def test_contextual_plan_records_understood_application_event(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    ApplicationRepository(supervisor.db).create_application(
        ApplicationIdentity(
            application_id="app-keeta-sales",
            notion_id="625",
            company="Keeta",
            role="Sales Operations Manager",
            fingerprint="fp-keeta-sales",
        )
    )
    supervisor.conversation_planner = ContextualPlanner(
        output_provider=lambda _prompt: (
            '{"intent":"analyze","target_hints":{"company":"Keeta",'
            '"role":"Sales Operations Manager"},"requested_steps":[],'
            '"authorization":"user_request","confidence":"high"}'
        )
    )
    monkeypatch.setattr(
        supervisor,
        "_execute_natural_application",
        lambda message, resolution, **kwargs: {
            "status": "completed",
            "application_id": resolution["application_id"],
        },
    )

    supervisor.handle_message(
        "analisa essa oportunidade",
        channel="telegram",
        execute=True,
        runtime_context={
            "runtime": "hermes",
            "profile_id": "vagas_bot_01",
            "session_id": "contextual-audit",
            "turn_id": "turn-1",
        },
    )

    event = supervisor.db.fetch_one(
        "SELECT event, fingerprint, metadata FROM workflow_events "
        "WHERE application_id = ? AND event = ?",
        ("app-keeta-sales", "harness_conversational_plan"),
    )
    assert event is not None
    assert event["fingerprint"] == "fp-keeta-sales"
    assert "entendi" in event["metadata"].casefold()


def test_short_pipeline_control_executes_bound_pipeline_intent(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    context = {
        "runtime": "hermes",
        "profile_id": "vagas_bot_01",
        "session_id": "short-control",
    }
    monkeypatch.setattr(
        supervisor, "_session_application_id", lambda *_args, **_kwargs: "app-live"
    )
    monkeypatch.setattr(
        supervisor,
        "_session_pipeline_intent",
        lambda *_args, **_kwargs: {
            "application_id": "app-live",
            "requested_steps": ["cv", "onedrive", "notion"],
        },
    )
    captured = {}

    def fake_pipeline(message, **kwargs):
        captured.update(kwargs)
        return {"status": "completed", "application_id": "app-live"}

    monkeypatch.setattr(supervisor, "_execute_pipeline_request", fake_pipeline)

    result = supervisor.handle_message(
        "Pode executar",
        channel="telegram",
        execute=True,
        runtime_context=context,
    )

    assert result["decision"]["workflow"] == "pipeline"
    assert captured["application_id"] == "app-live"
    assert captured["requested_steps"] == ["cv", "onedrive", "notion"]


def test_pipeline_blocker_explains_canonical_next_step(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    monkeypatch.setattr(
        "career.services.intake.resume",
        lambda **_kwargs: {
            "status": "blocked",
            "application_id": "app-live",
            "next_required_step": "reconcile_fit_map_receipts",
        },
    )

    result = supervisor._execute_pipeline_request(
        "continue",
        requested_steps=["cv"],
        application_id="app-live",
        model=None,
        variant=None,
        runtime_context=None,
        channel="telegram",
    )

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "no_pipeline_stage_executed"
    assert "Não executei nenhuma etapa" in result["display_text"]
    assert "reconcile_fit_map_receipts" in result["display_text"]


def test_pipeline_stage_blocker_explains_isolation_failure(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    monkeypatch.setattr(
        "career.services.intake.resume",
        lambda **_kwargs: {
            "status": "active_intake_ready",
            "application_id": "app-live",
            "next_required_step": "build_cv",
        },
    )
    monkeypatch.setattr(
        supervisor,
        "execute_specialist",
        lambda *_args, **_kwargs: {
            "status": "blocked",
            "blocker_reason": "specialist_isolation_failed",
            "execution": {
                "isolation": {"unauthorized_changes": ["dispatch.lock"]}
            },
        },
    )

    result = supervisor._execute_pipeline_request(
        "continue",
        requested_steps=["cv"],
        application_id="app-live",
        model=None,
        variant=None,
        runtime_context=None,
        channel="telegram",
    )

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "specialist_isolation_failed"
    assert "isolamento" in result["display_text"].casefold()
    assert "dispatch.lock" in result["display_text"]


def test_natural_application_reference_resolves_unique_canonical_company(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    ApplicationRepository(supervisor.db).create_application(
        ApplicationIdentity(
            application_id="app-keeta-sales",
            notion_id="625",
            company="Keeta",
            role="Sales Operations Manager",
            source_type="notion",
        )
    )

    result = supervisor._resolve_natural_application(
        "olhe a candidatura da Keeta para Sales Operations Manager"
    )

    assert result["status"] == "resolved"
    assert result["application_id"] == "app-keeta-sales"
    assert result["source"] == "canonical_company_role"


def test_model_interpreter_extracts_paraphrased_company_and_role_before_resolution(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    ApplicationRepository(supervisor.db).create_application(
        ApplicationIdentity(
            application_id="app-keeta-sales",
            notion_id="625",
            company="Keeta",
            role="Sales Operations Manager",
            source_type="notion",
        )
    )
    calls = []
    supervisor.application_interpreter = lambda message: calls.append(message) or {
        "intent": "analysis",
        "company": "Keeta",
        "role": "Sales Operations Manager",
    }

    decision = supervisor.classify("dê uma olhada naquela posição de operações comerciais na Keeta")

    assert decision.workflow == "natural_application_route"
    assert decision.parameters == {
        "intent": "analysis",
        "company": "Keeta",
        "role": "Sales Operations Manager",
        "interpretation_source": "model",
    }
    assert calls == ["dê uma olhada naquela posição de operações comerciais na Keeta"]
    result = supervisor._resolve_natural_application(
        "dê uma olhada naquela posição de operações comerciais na Keeta",
        interpreted_parameters=decision.parameters,
    )
    assert result["status"] == "resolved"
    assert result["application_id"] == "app-keeta-sales"


def test_model_interpreter_cannot_select_application_id_or_break_ambiguity(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    repository = ApplicationRepository(supervisor.db)
    for application_id, role in (
        ("app-keeta-sales", "Sales Operations Manager"),
        ("app-keeta-revenue", "Revenue Operations Manager"),
    ):
        repository.create_application(
            ApplicationIdentity(
                application_id=application_id,
                notion_id=application_id.rsplit("-", 1)[-1],
                company="Keeta",
                role=role,
                source_type="notion",
            )
        )
    supervisor.application_interpreter = lambda _message: {
        "intent": "cv",
        "application_id": "app-keeta-sales",
        "company": "Keeta",
    }

    decision = supervisor.classify("prepare o currículo para a oportunidade da Keeta")

    assert decision.workflow == "natural_application_route"
    assert "application_id" not in (decision.parameters or {})
    result = supervisor._resolve_natural_application(
        "prepare o currículo para a oportunidade da Keeta",
        interpreted_parameters=decision.parameters,
    )
    assert result["status"] == "awaiting_input"
    assert result["blocker_reason"] == "natural_application_ambiguous"


def test_model_interpreter_uses_bounded_json_only_and_no_tools(monkeypatch, tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    captured = {}
    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout='```json\n{"intent":"cv","company":"Keeta","role":"Sales Operations Manager"}\n```',
            stderr="",
        )

    monkeypatch.setattr("career.services.harness_supervisor.subprocess.run", fake_run)
    monkeypatch.setattr(
        "career.services.harness_supervisor.resolve_hermes_command",
        lambda _root: (["/opt/hermes/bin/hermes"], None),
    )
    result = supervisor._model_natural_application_interpretation(
        "prepare o currículo para a oportunidade da Keeta"
    )

    assert result["company"] == "Keeta"
    assert "--safe-mode" in captured["command"]
    assert "--toolsets" in captured["command"]
    assert captured["kwargs"]["timeout"] == 20


def test_catalog_fallback_resolves_company_when_model_is_unavailable(tmp_path):
    supervisor = HarnessSupervisor(tmp_path, application_interpreter=lambda _message: None)
    ApplicationRepository(supervisor.db).create_application(
        ApplicationIdentity(
            application_id="app-keeta-sales",
            notion_id="625",
            company="Keeta",
            role="Sales Operations Manager",
            source_type="notion",
        )
    )

    decision = supervisor.classify("dê uma olhada naquela posição de operações comerciais na Keeta")

    assert decision.workflow == "natural_application_route"
    assert decision.parameters["company"] == "Keeta"
    assert decision.parameters["interpretation_source"] == "canonical_catalog"


def test_natural_application_reference_never_picks_weak_or_ambiguous_match(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    repository = ApplicationRepository(supervisor.db)
    for application_id, role in (
        ("app-keeta-sales", "Sales Operations Manager"),
        ("app-keeta-revenue", "Revenue Operations Manager"),
    ):
        repository.create_application(
            ApplicationIdentity(
                application_id=application_id,
                notion_id=application_id.rsplit("-", 1)[-1],
                company="Keeta",
                role=role,
                source_type="notion",
            )
        )

    result = supervisor._resolve_natural_application("quero olhar uma vaga da Keeta")

    assert result["status"] == "awaiting_input"
    assert result["blocker_reason"] == "natural_application_ambiguous"
    assert {item["application_id"] for item in result["candidates"]} == {
        "app-keeta-sales",
        "app-keeta-revenue",
    }
    assert "Não escolhi" in result["display_text"]


def test_new_session_can_recover_profile_context_and_audits_resolution(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    ApplicationRepository(supervisor.db).create_application(
        ApplicationIdentity(
            application_id="app-keeta-sales",
            notion_id="625",
            company="Keeta",
            role="Sales Operations Manager",
            source_type="notion",
            fingerprint="fp-keeta-sales",
        )
    )
    old_context = {
        "runtime": "hermes",
        "profile_id": "vagas_bot_02",
        "session_id": f"chat-old-{tmp_path.name}",
    }
    new_context = {**old_context, "session_id": f"chat-new-{tmp_path.name}"}
    supervisor._bind_session_to_application(
        old_context, "app-keeta-sales", channel="telegram"
    )
    monkeypatch.setattr(
        supervisor,
        "_resume_and_continue",
        lambda *args, **kwargs: {
            "status": "completed",
            "application_id": kwargs["application_id"],
            "display_text": "Retomado.",
        },
    )

    result = supervisor.handle_message(
        "continue o trabalho em andamento",
        channel="telegram",
        execute=True,
        runtime_context=new_context,
    )

    assert result["result"]["application_id"] == "app-keeta-sales"
    assert result["result"]["resolution"]["source"] == "profile_recovery"
    assert "Entendi esta referência" in result["result"]["display_text"]
    event = supervisor.db.fetch_one(
        "SELECT event, fingerprint, metadata FROM workflow_events WHERE application_id = ?",
        ("app-keeta-sales",),
    )
    assert event["event"] == "natural_application_resolved"
    assert event["fingerprint"] == "fp-keeta-sales"


def test_notion_identity_hint_does_not_authorize_or_create_a_pipeline_stage():
    supervisor = HarnessSupervisor()

    cv_decision = supervisor.classify("gere o CV da vaga Notion 625 incluindo WeHandle")
    write_decision = supervisor.classify("atualize no Notion a candidatura 625")
    pipeline_decision = supervisor.classify(
        "gere o CV da vaga 625 e atualize o registro no Notion"
    )

    assert cv_decision.workflow == "cv"
    assert cv_decision.parameters == {"record_id": 625}
    assert write_decision.workflow == "notion_update"
    assert write_decision.requires_approval is True
    assert pipeline_decision.workflow == "pipeline"
    assert pipeline_decision.parameters["requested_steps"] == ["cv", "notion"]


def test_natural_ambiguity_becomes_scoped_selection_before_resume(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    repository = ApplicationRepository(supervisor.db)
    repository.create_application(
        ApplicationIdentity(
            application_id="app-keeta-sales",
            notion_id="625",
            company="Keeta",
            role="Sales Operations Manager",
        )
    )
    repository.create_application(
        ApplicationIdentity(
            application_id="app-keeta-revenue",
            notion_id="626",
            company="Keeta",
            role="Revenue Operations Manager",
        )
    )
    monkeypatch.setattr(
        supervisor,
        "_resume_and_continue",
        lambda *args, **kwargs: {
            "status": "completed",
            "application_id": kwargs["application_id"],
        },
    )
    context = {
        "runtime": "hermes",
        "profile_id": "selection-profile",
        "session_id": f"selection-{tmp_path.name}",
    }

    pending = supervisor.handle_message(
        "olhe uma vaga da Keeta",
        channel="telegram",
        execute=True,
        runtime_context=context,
    )
    selected = supervisor.handle_message(
        "2",
        channel="telegram",
        execute=True,
        runtime_context=context,
    )

    assert pending["status"] == "awaiting_input"
    assert pending["result"]["blocker_reason"] == "natural_application_ambiguous"
    assert "vaga 625 da Keeta" in pending["result"]["display_text"]
    assert selected["result"]["application_id"] == "app-keeta-revenue"


def test_negated_outputs_are_not_treated_as_requested_pipeline_steps():
    supervisor = HarnessSupervisor()

    decision = supervisor.classify(
        "quero que olhe a candidatura 625 do notion e me diga o que entendeu; "
        "não gere CV, não atualize o Notion e não envie nada"
    )

    assert decision.workflow == "natural_application_route"
    assert decision.parameters == {"record_id": 625, "intent": "analysis"}


def test_cv_pipeline_can_start_when_scoped_analysis_is_already_complete(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    monkeypatch.setattr(
        "career.services.intake.resume",
        lambda **kwargs: {
            "status": "active_intake_ready",
            "next_required_step": "complete",
            "fit_map_status": {
                "next_required_step": "análise concluída",
                "active_job": {"fingerprint": "fp-current"},
            },
        },
    )
    monkeypatch.setattr(supervisor, "_can_reuse_completed_fit_map", lambda _app: True)
    monkeypatch.setattr(
        supervisor,
        "execute_specialist",
        lambda step, **kwargs: {"status": "completed", "step": step},
    )

    result = supervisor._execute_pipeline_request(
        "gere o CV da candidatura",
        requested_steps=["cv"],
        application_id="app-keeta-sales",
        model=None,
        variant=None,
        runtime_context=None,
        channel="cli",
    )

    assert result["status"] == "completed"
    assert result["stages"] == [{"status": "completed", "step": "cv"}]


def test_delivery_only_cv_request_does_not_create_cv_pipeline():
    decision = HarnessSupervisor().classify("pode enviar o cv para o onedrive")

    assert decision.workflow == "pipeline"
    assert decision.parameters["requested_steps"] == ["onedrive"]


def test_delivery_only_request_reuses_existing_cv_without_running_cv_or_analysis(
    tmp_path, monkeypatch
):
    supervisor = HarnessSupervisor(tmp_path)
    monkeypatch.setattr(
        "career.services.intake.resume",
        lambda **kwargs: {
            "status": "active_intake_ready",
            "next_required_step": "complete",
        },
    )
    monkeypatch.setattr(supervisor, "_has_scoped_cv_artifact", lambda _app: True)
    delivered = []
    monkeypatch.setattr(
        supervisor,
        "_deliver_scoped_cv",
        lambda application_id: delivered.append(application_id)
        or {"status": "completed", "step": "onedrive"},
    )

    def fail_if_specialist_runs(*args, **kwargs):
        raise AssertionError("delivery-only requests must not run CV or analysis")

    monkeypatch.setattr(supervisor, "execute_specialist", fail_if_specialist_runs)

    result = supervisor._execute_pipeline_request(
        "pode enviar o cv para o onedrive",
        requested_steps=["onedrive"],
        application_id="app-keeta-sales",
        model=None,
        variant=None,
        runtime_context=None,
        channel="cli",
    )

    assert result["status"] == "completed"
    assert delivered == ["app-keeta-sales"]
    assert result["stages"] == [{"status": "completed", "step": "onedrive"}]


def test_supervisor_persists_and_reuses_bounded_conversation_history(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(tmp_path)
    observed = []
    decision = supervisor._decision("generic_assistant", "chat", "high", "free_question")
    monkeypatch.setattr(supervisor, "classify", lambda _message: decision)

    def fake_generic(_message, **kwargs):
        observed.append(kwargs.get("conversation_history"))
        return {"status": "completed", "display_text": "Contexto usado."}

    monkeypatch.setattr(supervisor, "_run_generic_message", fake_generic)
    context = {
        "runtime": "hermes",
        "profile_id": "vagas_bot_01",
        "session_id": "context-session",
        "turn_id": "turn-1",
    }
    history = [
        {"role": "user", "content": "analise a vaga 625"},
        {"role": "assistant", "content": "A análise foi concluída."},
    ]

    supervisor.handle_message(
        "qual foi a decisão?",
        channel="telegram",
        execute=True,
        runtime_context=context,
        conversation_history=history,
    )
    supervisor.handle_message(
        "continue",
        channel="telegram",
        execute=True,
        runtime_context={**context, "turn_id": "turn-2"},
    )

    assert observed == [history, history]


def test_scoped_cv_artifact_can_be_recovered_from_approved_report(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    application_id = "app-approved-cv"
    ApplicationRepository(supervisor.db).create_application(
        ApplicationIdentity(
            application_id=application_id,
            company="Keeta",
            role="Sales Operations Manager",
        )
    )
    artifact = tmp_path / "outputs" / "felipe_armel_cv_keeta.docx"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"approved cv")
    report_path = (
        tmp_path
        / ".career-state"
        / "applications_v2"
        / application_id
        / "cv_review_report.json"
    )
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "approved_for_delivery": True,
                "artifact": "outputs/felipe_armel_cv_keeta.docx",
            }
        ),
        encoding="utf-8",
    )

    assert supervisor._has_scoped_cv_artifact(application_id) is True


class _ApprovedMaintenanceRunner:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run_attempt(self, request: dict[str, object], attempt_number: int) -> dict[str, object]:
        patch_path = self.root.parent / f"candidate-{attempt_number}.patch"
        patch_text = (
            "--- a/src/career/services/cv_content.py\n"
            "+++ b/src/career/services/cv_content.py\n"
            "@@ -1 +1 @@\n"
            "-BASE\n"
            "+CHANGED\n"
        )
        patch_path.write_text(patch_text, encoding="utf-8")
        checks = {
            "status": "passed",
            "commands": [
                {"name": name, "returncode": 0}
                for name in [
                    "git_diff_check",
                    "base_commit",
                    "changed_paths",
                    "candidate_diff",
                    "required_pytest",
                ]
            ],
            "changed_files": ["src/career/services/cv_content.py"],
        }
        review = {
            "status": "approved",
            "score": 99.0,
            "requirements": [
                {"id": "REQ-1", "status": "met", "evidence": "offline canary"}
            ],
            "blockers": [],
            "warnings": [],
            "reviewer_model": "maintenance-reviewer",
            "diff_sha256": hashlib.sha256(patch_text.encode("utf-8")).hexdigest(),
            "spec_sha256": hashlib.sha256(
                json.dumps(
                    request["spec"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        }
        return {
            "status": "approved",
            "candidate": {
                "patch_path": str(patch_path),
                "changed_files": ["src/career/services/cv_content.py"],
            },
            "checks": checks,
            "review": review,
        }

    def post_apply_checks(
        self, request: dict[str, object], patch_path: Path
    ) -> dict[str, object]:
        assert patch_path.is_file()
        return self.run_attempt(request, 1)["checks"]


def _maintenance_root(tmp_path):
    return make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )


@pytest.mark.parametrize("profile", ["vagas_bot_01", "vagas_bot_02"])
def test_bot_maintenance_request_is_not_classified_as_pasted_job(profile):
    decision = HarnessSupervisor().classify(
        json.dumps(_maintenance_payload(requester_profile=profile))
    )

    assert decision.workflow == "maintenance"
    assert decision.requires_approval is False


def test_maintenance_prose_is_not_classified_as_maintenance():
    decision = HarnessSupervisor().classify(
        "manutencao canonica solicitada pelo bot para corrigir src/career/services/cv_content.py"
    )

    assert decision.workflow != "maintenance"


def test_maintenance_request_requires_canonical_application_scope_when_cellular(
    tmp_path, monkeypatch
):
    class ExplodingOrchestrator:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("cellular scope must block before orchestrator")

    monkeypatch.setattr(
        "career.services.harness_supervisor.MaintenanceOrchestrator",
        ExplodingOrchestrator,
        raising=False,
    )
    supervisor = HarnessSupervisor(_maintenance_root(tmp_path))

    result = supervisor.handle_message(
        json.dumps(_maintenance_payload(cellular=True)),
        execute=True,
    )

    assert result["status"] == "blocked"
    assert result["result"]["status"] == "blocked"
    assert result["result"]["blocker_reason"] == "explicit_application_scope_required"


def test_maintenance_request_execute_false_prepares_and_validates(tmp_path):
    supervisor = HarnessSupervisor(_maintenance_root(tmp_path))

    result = supervisor.handle_message(
        json.dumps(_maintenance_payload()),
        execute=False,
    )

    assert result["status"] == "prepared"
    assert result["executed"] is False
    assert result["decision"]["workflow"] == "maintenance"
    assert result["result"]["status"] == "prepared"
    assert result["result"]["validation"]["status"] == "ok"
    assert result["result"]["request"]["requester_profile"] == "vagas_bot_01"


@pytest.mark.parametrize("status", ["blocked", "rejected", "committed"])
def test_maintenance_request_execute_true_preserves_orchestrator_status(
    tmp_path, monkeypatch, status
):
    captured = {}

    class FakeOrchestrator:
        def __init__(self, root):
            captured["root"] = root

        def process(self, request_path):
            captured["request_path"] = request_path
            request = json.loads(request_path.read_text(encoding="utf-8"))
            captured["request"] = request
            return {
                "status": status,
                "request_id": request["request_id"],
                "attempts": 1,
                "blocker_reason": "reviewer_rejected" if status != "committed" else None,
            }

    monkeypatch.setattr(
        "career.services.harness_supervisor.MaintenanceOrchestrator",
        FakeOrchestrator,
        raising=False,
    )
    supervisor = HarnessSupervisor(_maintenance_root(tmp_path))

    result = supervisor.handle_message(
        json.dumps(
            _maintenance_payload(
                cellular=True,
                application_id="app_demo",
                run_id="run_demo",
            )
        ),
        execute=True,
    )

    assert result["status"] == status
    assert result["result"]["status"] == status
    assert result["result"]["application_id"] == "app_demo"
    assert captured["request"]["run_id"] == "run_demo"


@pytest.mark.parametrize("profile", ["vagas_bot_01", "vagas_bot_02"])
def test_structured_profile_request_commits_in_disposable_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    production_target = Path(__file__).resolve().parents[1] / "src/career/services/cv_content.py"
    production_before = production_target.read_bytes()
    root = _maintenance_root(tmp_path / "checkout")
    base_commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    payload = _maintenance_payload(
        requester_profile=profile,
        application_id="app_disposable",
        run_id="run_disposable",
        base_commit=base_commit,
    )
    orchestrator = MaintenanceOrchestrator(root, runner=_ApprovedMaintenanceRunner(root))
    monkeypatch.setattr(
        orchestrator,
        "reload_profiles_if_needed",
        lambda changed_paths: {
            "status": "not_required",
            "policy": {"runtime_affecting": False, "changed_paths": changed_paths},
            "command": None,
            "docker_compose_ps": "",
        },
    )
    monkeypatch.setattr(
        orchestrator,
        "resume_original_run",
        lambda request: {
            "status": "resumed",
            "command": [
                "npm",
                "run",
                "applications:run",
                "--",
                "--application-id",
                request["application_id"],
                "--run-id",
                request["run_id"],
                "--run-agent",
            ],
            "returncode": 0,
            "stdout": "resumed\n",
            "stderr": "",
        },
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.MaintenanceOrchestrator",
        lambda candidate_root: orchestrator,
    )

    result = HarnessSupervisor(root).handle_message(
        json.dumps(payload),
        execute=True,
    )

    assert result["status"] == "committed"
    assert result["executed"] is True
    assert result["result"]["request"]["requester_profile"] == profile
    assert result["result"]["review"]["score"] >= 99.0
    assert result["result"]["reload"]["status"] == "not_required"
    assert result["result"]["resume"]["status"] == "resumed"
    receipt_path = Path(str(result["result"]["receipt_path"]))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "committed"
    assert receipt["requester_profile"] == profile
    assert receipt["commit"] == result["result"]["commit"]
    assert receipt["review"]["score"] >= 99.0
    assert receipt["reload"]["status"] == "not_required"
    assert receipt["resume"]["status"] == "resumed"
    assert production_target.read_bytes() == production_before
    committed_paths = subprocess.run(
        ["git", "-C", str(root), "show", "--format=", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert committed_paths == ["src/career/services/cv_content.py"]


def test_cv_onedrive_notion_is_one_scoped_pipeline():
    decision = HarnessSupervisor().classify(
        "crie o cv, envie para o onedrive e crie o registro no notion "
        "application_id local_test"
    )

    assert decision.workflow == "pipeline"
    assert decision.parameters["application_id"] == "local_test"
    assert decision.parameters["requested_steps"] == ["cv", "onedrive", "notion"]


def test_application_id_prevents_collecting_notion_id():
    decision = HarnessSupervisor().classify(
        "retome application_id local_test e prossiga com CV, OneDrive e Notion"
    )

    assert decision.workflow == "pipeline"
    assert decision.workflow != "collect_notion_id"


def test_explicit_run_resume_precedes_long_pasted_job_detection():
    message = """
    Retome a candidatura existente no mesmo run. Não faça novo intake nem nova análise.
    application_id: local_20260827T151213_541737_modaxo_8959c053
    run_id: run_62621fc435554290be1fbe127968c29b
    Repare compose_cv, depois render_cv e review_cv.
    """ + (" Contexto operacional da candidatura. " * 30)

    decision = HarnessSupervisor().classify(message)

    assert decision.workflow == "resume"
    assert decision.stage == "resume"
    assert decision.parameters == {
        "application_id": "local_20260827T151213_541737_modaxo_8959c053",
        "run_id": "run_62621fc435554290be1fbe127968c29b",
        "repair_node": "compose_cv",
    }


def test_explicit_run_resume_extracts_natural_language_repair_node():
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)

    decision = supervisor.classify(
        "Repare primeiro o normalize_job e depois prossiga no mesmo run. "
        "application_id: app_modaxo run_id: run_123"
    )

    assert decision.workflow == "resume"
    assert decision.parameters["repair_node"] == "normalize_job"


def test_harness_result_report_is_not_classified_as_a_pasted_job():
    message = """
    Resumo do resultado (executado pelo HarnessSupervisor)
    Status: blocked — a mensagem não foi executada (executed: false).
    O supervisor classificou errado a sua mensagem como vaga colada.
    Workflow: pasted_job_missing_metadata. Stage: intake. Confidence: high.
    O bloqueio objetivo está relacionado ao CV e ao fit_map, não a uma nova vaga.
    O próximo passo é confirmar o estado de applications_v2.py e preparar o patch.
    Quer que eu confirme o estado atual e corrija os sinais em inglês?
    """ + (" Contexto operacional do resultado. " * 30)

    decision = HarnessSupervisor().classify(message)

    assert decision.workflow == "generic_assistant"
    assert decision.reason == "harness_result_report"


def test_explicit_cellular_resume_runs_scoped_official_repair_command(monkeypatch):
    supervisor = HarnessSupervisor()
    supervisor.db.fetch_one = lambda *_args: {"application_id": "app_modaxo"}
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout='{"status":"completed"}', stderr="")

    monkeypatch.setattr("career.services.harness_supervisor.subprocess.run", fake_run)

    result = supervisor._resume_cellular_run(
        application_id="app_modaxo",
        run_id="run_modaxo",
        repair_node="compose_cv",
        reason="corrigir o conteúdo do CV no mesmo run",
    )

    assert result["status"] == "completed"
    assert captured["command"][:8] == [
        "npm", "run", "applications:repair", "--",
        "--application-id", "app_modaxo", "--run-id", "run_modaxo",
    ]
    assert "--node" in captured["command"]


def test_explicit_cellular_resume_runs_agent_nodes_for_plain_run(monkeypatch):
    supervisor = HarnessSupervisor()
    supervisor.db.fetch_one = lambda *_args: {"application_id": "app_modaxo"}
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout='{"status":"ready"}', stderr="")

    monkeypatch.setattr("career.services.harness_supervisor.subprocess.run", fake_run)

    result = supervisor._resume_cellular_run(
        application_id="app_modaxo",
        run_id="run_modaxo",
        repair_node=None,
        reason="retomar o mesmo run",
    )

    assert result["status"] == "completed"
    assert captured["command"][-1] == "--run-agent"


def test_explicit_cellular_resume_exposes_permission_preflight_blocker(monkeypatch):
    supervisor = HarnessSupervisor()
    supervisor.db.fetch_one = lambda *_args: {"application_id": "app_modaxo"}

    def fake_run(command, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout=(
                '{"status":"blocked","error":"cellular workspace preflight '
                'cannot read identity.json (owner=0:0 mode=600)"}'
            ),
            stderr="",
        )

    monkeypatch.setattr("career.services.harness_supervisor.subprocess.run", fake_run)

    result = supervisor._resume_cellular_run(
        application_id="app_modaxo",
        run_id="run_modaxo",
        repair_node=None,
        reason="retomar o mesmo run",
    )

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "cellular_workspace_permission"
    assert "UID 10000" in result["next_action"]
