from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import notion_sync


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
