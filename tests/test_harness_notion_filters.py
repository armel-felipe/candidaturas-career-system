from __future__ import annotations

from career.services.harness_supervisor import HarnessSupervisor


def test_classifies_notion_status_list_request():
    supervisor = HarnessSupervisor()

    decision = supervisor.classify("traga vagas com Etapa Funil Fila Agente")

    assert decision.workflow == "notion_application_list"
    assert decision.parameters == {"filter_text": "Etapa Funil Fila Agente"}


def test_selection_from_filtered_list_routes_to_existing_analysis(tmp_path):
    supervisor = HarnessSupervisor(root=tmp_path)
    supervisor._write_pending_input({"input_kind": "notion_record_selection", "record_ids": [123]})

    assert supervisor._resolve_pending_input("123") == {
        "input_kind": "notion_record_selection",
        "message": "avalie vaga Notion 123",
    }


def test_unlisted_filtered_record_id_is_rejected(tmp_path):
    supervisor = HarnessSupervisor(root=tmp_path)
    supervisor._write_pending_input({"input_kind": "notion_record_selection", "record_ids": [123]})

    assert supervisor._invalid_pending_record_selection("999") == "notion_record_selection_not_found"


def test_filter_reply_resumes_generic_list_request(tmp_path):
    supervisor = HarnessSupervisor(root=tmp_path)
    supervisor._write_pending_input({"input_kind": "notion_application_filter"})

    assert supervisor._resolve_pending_input("Etapa Funil Fila Agente") == {
        "input_kind": "notion_application_filter",
        "message": "traga vagas com Etapa Funil Fila Agente",
    }
