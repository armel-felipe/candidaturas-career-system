from __future__ import annotations

import pytest

from career.services import notion


SCHEMA = {
    "properties": {
        "ID": {"id": "record-id", "type": "number", "number": {"format": "number"}},
        "Vaga": {"id": "title", "type": "title", "title": {}},
        "empresa_int": {"id": "company", "type": "rich_text", "rich_text": {}},
        "Etapa Funil": {
            "id": "stage",
            "type": "status",
            "status": {"options": [{"name": "Fila Agente"}, {"name": "Aplicação andamento"}]},
        },
        "avaliação de aderencia claude": {"id": "fit", "type": "number", "number": {"format": "number"}},
    }
}


def test_builds_native_and_filter_for_status_and_text():
    filters = notion.parse_application_filters(
        "Etapa Funil Fila Agente e empresa Mercado Livre", SCHEMA
    )

    assert notion.build_application_filter(filters) == {
        "and": [
            {"property": "Etapa Funil", "status": {"equals": "Fila Agente"}},
            {"property": "empresa_int", "rich_text": {"contains": "Mercado Livre"}},
        ]
    }


def test_builds_number_comparison_filter():
    filters = notion.parse_application_filters("aderência maior que 7", SCHEMA)

    assert notion.build_application_filter(filters) == {
        "property": "avaliação de aderencia claude",
        "number": {"greater_than": 7.0},
    }


def test_rejects_unknown_status_option():
    with pytest.raises(ValueError, match="Etapa Funil.*Fila inexistente"):
        notion.parse_application_filters("Etapa Funil Fila inexistente", SCHEMA)


def test_query_live_applications_uses_schema_and_native_filter(monkeypatch):
    monkeypatch.setattr(notion.legacy_notion, "discover_data_source_id", lambda *_: "source-1")
    monkeypatch.setattr(notion.legacy_notion, "retrieve_data_source", lambda *_: SCHEMA)
    captured = {}

    def query_data_source(_token, _source, payload):
        captured["payload"] = payload
        return {"results": []}

    monkeypatch.setattr(notion.legacy_notion, "query_data_source", query_data_source)

    result = notion.query_live_applications("token", "database", "Etapa Funil Fila Agente")

    assert result["count"] == 0
    assert captured["payload"]["filter"] == {
        "property": "Etapa Funil", "status": {"equals": "Fila Agente"}
    }
    assert captured["payload"]["page_size"] == 20


def test_format_application_table_uses_only_short_columns():
    text = notion.format_application_table({
        "filters": ["Etapa Funil = Fila Agente"],
        "count": 1,
        "records": [{
            "record_id": 123,
            "role": "Director",
            "company": "Acme",
            "status": "Fila Agente",
            "fit_score": 8.0,
            "notion_url": "https://notion.so/123",
        }],
    })

    assert "ID | Cargo | Empresa | Etapa Funil | Aderência | Link" in text
    assert "123" in text
    assert "description" not in text


def test_status_guidance_comes_from_live_schema():
    assert notion.application_filter_guidance(SCHEMA)["available_statuses"] == [
        "Fila Agente", "Aplicação andamento"
    ]
