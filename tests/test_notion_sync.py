from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import notion_sync
from career.services import notion as notion_service


def test_notion_projection_keeps_existing_governance_fields_and_adds_compact_positioning_snapshot() -> None:
    fit_map = {
        "keywords_para_ats": ["S&OP", "capacity planning"],
        "gaps_sem_cobertura": ["Sem experiência literal no setor"],
        "historias_selecionadas": {
            "principal": {"empresa": "iFood", "angulo": "escala operacional"}
        },
        "positioning_pack": {
            "application_id": "app-conexa",
            "fit_map_revision_id": "fit-v2",
            "positioning_revision_id": "positioning-v2",
            "candidate_evidence_revision_id": "evidence-v2",
            "thesis": "Escalar operações com governança.",
            "persona": "Executivo de operações",
            "stories": [
                {
                    "story_id": "story_a",
                    "title": "Escala",
                    "narrative": "Narrativa longa não deve ser enviada ao Notion.",
                }
            ],
            "claims": ["Claim defensável A"],
        },
    }

    values = notion_sync.governance_field_values(fit_map)
    blocks = notion_sync.notion_analysis_blocks(fit_map)
    serialized_blocks = json.dumps(blocks, ensure_ascii=False)

    assert values["keywords"] == "S&OP; capacity planning"
    assert values["gaps"] == "Sem experiência literal no setor"
    assert "Memória complementar" in serialized_blocks
    assert "positioning-v2" in serialized_blocks
    assert "evidence-v2" in serialized_blocks
    assert "story_a" in serialized_blocks
    assert "Narrativa longa não deve ser enviada" not in serialized_blocks


def test_notion_analysis_block_sequence_is_detected_as_already_present() -> None:
    fit_map = {
        "cargo": "Head de Operações",
        "empresa": "Dreamers.gr",
        "nota_aderencia": {"final": 4.75, "dimensoes": {}},
        "dor_central": "Conectar estratégia e execução.",
        "gaps_sem_cobertura": ["Sem experiência em agência"],
        "keywords_habilidade_ats": [],
    }
    blocks = notion_sync.notion_analysis_blocks(fit_map)

    assert notion_sync.analysis_blocks_already_present(blocks, blocks) is True
    assert notion_sync.analysis_blocks_already_present(blocks[:-1], blocks) is False


def test_automation_update_requires_an_allowed_funnel_stage() -> None:
    allowed = ("Aplicação Andamento", "Aplicação andamento", "Fila Agente", "Aplicação em Análise")
    for stage in allowed:
        notion_sync.ensure_page_status_allows_update(
            {"properties": {"Etapa Funil": {"type": "status", "status": {"name": stage}}}}
        )

    for stage in ("Aplicação Feita", "Desisti da vaga", "Entrevista", ""):
        try:
            notion_sync.ensure_page_status_allows_update(
                {"properties": {"Etapa Funil": {"type": "status", "status": {"name": stage}}}}
            )
        except SystemExit as exc:
            message = str(exc)
            assert "Etapa Funil" in message
            assert "alter" in message.casefold()
            assert "confirm" in message.casefold()
        else:
            raise AssertionError(f"stage must be blocked: {stage!r}")


def test_terminal_update_override_cannot_bypass_funnel_stage_guard() -> None:
    page = {"properties": {"Etapa Funil": {"type": "status", "status": {"name": "Aplicação Feita"}}}}

    try:
        notion_sync.ensure_page_status_allows_update(page, allow_terminal_status_update=True)
    except SystemExit:
        pass
    else:
        raise AssertionError("terminal stage must remain blocked even with the legacy override")


def test_description_update_checks_funnel_stage_before_loading_schema(tmp_path, monkeypatch) -> None:
    description = tmp_path / "job.md"
    description.write_text("# Operations Lead\n\n" + ("Lead operations and planning. " * 12), encoding="utf-8")
    page = {
        "id": "page-1",
        "properties": {"Etapa Funil": {"type": "status", "status": {"name": "Aplicação Feita"}}},
    }
    monkeypatch.setattr(notion_sync, "resolve_page_by_record_id", lambda *args: page)
    monkeypatch.setattr(
        notion_sync,
        "retrieve_data_source",
        lambda *args: (_ for _ in ()).throw(AssertionError("schema must not be loaded after a blocked stage")),
    )

    try:
        notion_sync.update_description_record("token", "database", 123, description)
    except SystemExit as exc:
        assert "Etapa Funil" in str(exc)
    else:
        raise AssertionError("description update must be blocked")


def test_status_update_checks_funnel_stage_before_writing(monkeypatch) -> None:
    monkeypatch.setattr(
        notion_sync,
        "extract_page_payload",
        lambda *args: {
            "properties": {
                "Etapa Funil": {
                    "type": "status",
                    "text": "Entrevista",
                }
            }
        },
    )
    monkeypatch.setattr(
        notion_sync,
        "discover_data_source_id",
        lambda *args: (_ for _ in ()).throw(AssertionError("schema must not be loaded after a blocked stage")),
    )

    try:
        notion_service.update_status("token", "database", "page-1", "Aplicação andamento")
    except SystemExit as exc:
        assert "Etapa Funil" in str(exc)
    else:
        raise AssertionError("status update must be blocked")
