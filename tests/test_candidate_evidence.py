from __future__ import annotations

import re

import pytest

from career.schemas.candidate_evidence import validate_candidate_evidence
from career.utils import ValidationFailure


def _valid_payload() -> dict:
    return {
        "schema_version": 1,
        "candidate": {"name": "Felipe Armel"},
        "stories": [
            {
                "story_id": "wehandle_margin_efficiency",
                "title": "Eficiência operacional em atendimento",
                "experience_id": "wehandle_head_operacoes",
                "context": "A operação precisava absorver volume sem perder qualidade.",
                "actions": ["Implantei automação e migrações de plataforma."],
                "results": ["Reduzi custo por atendimento."],
                "metrics": ["R$4,14 para R$3,61"],
                "capabilities": ["transformação digital"],
                "allowed_claims": ["Liderou transformação operacional baseada em dados."],
                "source_refs": [
                    {
                        "path": ".agents/skills/career-system/references/autoconhecimento.md",
                        "lines": "254-275",
                    }
                ],
                "artifact_guidance": {
                    "cv": "Resumo factual curto.",
                    "feras": "Narrativa em primeira pessoa.",
                    "interview": "Resposta situação-ação-resultado.",
                },
            }
        ],
    }


def test_valid_candidate_evidence_is_returned_normalized() -> None:
    payload = _valid_payload()

    assert validate_candidate_evidence(payload) == payload


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("story_id", "", "stories[0].story_id"),
        ("source_refs", [], "stories[0].source_refs"),
        ("allowed_claims", [""], "stories[0].allowed_claims"),
        ("metrics", [12], "stories[0].metrics"),
    ],
)
def test_candidate_evidence_rejects_invalid_story_fields(
    field: str, value: object, message: str
) -> None:
    payload = _valid_payload()
    payload["stories"][0][field] = value

    with pytest.raises(ValidationFailure, match=re.escape(message)):
        validate_candidate_evidence(payload)


def test_candidate_evidence_rejects_duplicate_story_ids() -> None:
    payload = _valid_payload()
    payload["stories"].append(dict(payload["stories"][0]))

    with pytest.raises(ValidationFailure, match="duplicate story_id"):
        validate_candidate_evidence(payload)
