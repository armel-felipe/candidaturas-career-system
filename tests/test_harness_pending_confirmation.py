import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from career.services.harness_supervisor import HarnessSupervisor
import hermes_harness_context_hook as hook


def test_yes_resolves_the_pending_question_for_same_session(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    supervisor._write_pending_input(
        {
            "input_kind": "confirmation",
            "session_id": "s1",
            "application_id": "app1",
            "turn_id": "t1",
            "display_text": "Gerar também o resumo ATS?",
        }
    )

    resolved = supervisor._resolve_pending_input(
        "sim", runtime_context={"session_id": "s1", "application_id": "app1"}
    )

    assert resolved["input_kind"] == "confirmation"
    assert resolved["answer"] is True


def test_no_does_not_resolve_a_confirmation_from_another_session(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    supervisor._write_pending_input(
        {
            "input_kind": "confirmation",
            "session_id": "s1",
            "application_id": "app1",
            "turn_id": "t1",
            "display_text": "Gerar também o resumo ATS?",
        }
    )

    assert (
        supervisor._resolve_pending_input(
            "não", runtime_context={"session_id": "s2", "application_id": "app1"}
        )
        is None
    )


def test_unresolved_pending_input_is_not_sent_to_generic_fallback(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    supervisor._write_pending_input(
        {
            "input_kind": "notion_id",
            "session_id": "s1",
            "application_id": "app1",
            "turn_id": "t1",
            "display_text": "Qual é o número da vaga no Notion?",
        }
    )

    result = supervisor.handle_message(
        "sim",
        channel="telegram",
        execute=True,
        runtime_context={
            "runtime": "hermes",
            "profile_id": "profile",
            "session_id": "s1",
        },
    )

    assert result["result"]["status"] == "awaiting_input"
    assert result["result"]["blocker_reason"] == "pending_input_unresolved"


def test_legacy_pending_notion_input_cannot_block_new_saved_jobs_route(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    supervisor._write_pending_input(
        {
            "input_kind": "notion_id",
            "display_text": "Qual é o número da vaga no Notion?",
        }
    )

    result = supervisor.handle_message(
        "lista de vagas salvas no linkedin",
        channel="telegram",
        execute=False,
        runtime_context={
            "runtime": "hermes",
            "profile_id": "profile",
            "session_id": "new-session",
        },
    )

    assert result["decision"]["workflow"] == "linkedin_saved_jobs"


def test_pending_input_from_previous_session_cannot_block_new_saved_jobs_route(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    supervisor._write_pending_input(
        {
            "input_kind": "notion_id",
            "session_id": "old-session",
            "display_text": "Qual é o número da vaga no Notion?",
        }
    )

    result = supervisor.handle_message(
        "lista de vagas salvas no linkedin",
        channel="telegram",
        execute=False,
        runtime_context={
            "runtime": "hermes",
            "profile_id": "profile",
            "session_id": "new-session",
        },
    )

    assert result["decision"]["workflow"] == "linkedin_saved_jobs"


def test_hook_ignores_legacy_pending_input_without_session_binding(tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "ROOT", tmp_path)
    pending_dir = tmp_path / ".career-state" / "harness"
    pending_dir.mkdir(parents=True)
    (pending_dir / "pending_input.json").write_text(
        '{"input_kind":"notion_id","display_text":"Qual é a vaga?"}\n',
        encoding="utf-8",
    )

    assert hook.should_intercept("sim") is False


def test_saved_jobs_menu_selection_accepts_analysis_phrase_without_using_notion_id(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    supervisor._write_menu_state(
        {
            "menu_context": "linkedin_saved_jobs",
            "headline": "Vagas salvas no LinkedIn",
            "numbered_items": [
                {
                    "number": 2,
                    "id": "linkedin_saved_job_2",
                    "title": "Director of Business Transformation & Operations",
                    "description": "Jobgether | Remoto",
                    "prompt": "https://www.linkedin.com/jobs/view/4456853995/",
                }
            ],
        }
    )

    decision = supervisor.classify("analise a vaga 2")

    assert decision.workflow == "linkedin_job_intake"
    assert decision.reason == "linkedin_job_url"
    assert decision.parameters["url"].endswith("4456853995/")


def test_saved_jobs_menu_selection_accepts_hash_phrase(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    supervisor._write_menu_state(
        {
            "menu_context": "linkedin_saved_jobs",
            "numbered_items": [
                {
                    "number": 2,
                    "id": "linkedin_saved_job_2",
                    "prompt": "https://www.linkedin.com/jobs/view/4456853995/",
                }
            ],
        }
    )

    decision = supervisor.classify("quero analisar a vaga #2")

    assert decision.workflow == "linkedin_job_intake"
