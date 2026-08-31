from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from career.services import cv_content, provenance
from career.services import candidate_evidence
from career.utils import ValidationFailure


def test_canonical_cv_facts_json_is_revisioned_and_drives_values(tmp_path, monkeypatch):
    facts_path = tmp_path / "candidate_cv_facts.json"
    facts = json.loads(cv_content.CV_FACTS_PATH.read_text(encoding="utf-8"))
    facts_path.write_text(json.dumps(facts), encoding="utf-8")
    monkeypatch.setattr(cv_content, "CV_FACTS_PATH", facts_path)
    monkeypatch.setattr(provenance, "CV_FACTS_PATH", facts_path)

    original_revision = provenance.candidate_facts_revision()
    original = cv_content.load_canonical_cv_facts()
    changed = deepcopy(facts)
    changed["candidate"]["location"] = "Canonical Test Location"
    changed["filename_slug"] = "canonical_test_cv"
    changed["summary_profiles"]["en"]["opening"] = "Canonical Test Summary"
    facts_path.write_text(json.dumps(changed), encoding="utf-8")

    assert provenance.candidate_facts_revision() != original_revision
    assert cv_content.load_canonical_cv_facts()["candidate"]["location"] == "Canonical Test Location"
    assert cv_content.load_canonical_cv_facts()["filename_slug"] == "canonical_test_cv"
    assert cv_content.load_canonical_cv_facts()["summary_profiles"]["en"]["opening"] == "Canonical Test Summary"
    selected = [
        cv_content._materialize_experience(item, "operations", language="en")
        for item in cv_content._facts_experiences()[:5]
    ]
    summary, _ = cv_content._build_summary(selected, {"cargo": "Test Role"}, language="en")
    assert summary.startswith("Canonical Test Summary")
    assert cv_content._output_name({"cargo": "Test Role", "empresa": "Test Company"}).startswith("canonical_test_cv_")
    with pytest.raises(ValidationFailure):
        cv_content.validate_canonical_provenance({"metadata": {"candidate_facts_revision": original_revision}})


def test_select_experiences_does_not_promote_fixed_trifil_fallback_for_cx():
    selected = cv_content._select_experiences(
        {
            "historias_selecionadas": {},
            "keywords_habilidade_ats": [
                {"keyword": "Customer Success", "prioridade": 1, "experiencia_alvo": ""},
                {"keyword": "conversão", "prioridade": 2, "experiencia_alvo": ""},
                {"keyword": "pipeline", "prioridade": 3, "experiencia_alvo": ""},
            ],
        }
    )

    selected_ids = [item["id"] for item in selected]
    assert "renault_cs" in selected_ids
    assert "trifil_expedicao" not in selected_ids


def test_new_evidence_story_is_available_to_cv_view() -> None:
    evidence = {
        "schema_version": 1,
        "candidate": {"name": "Felipe Armel"},
        "stories": [
            {
                "story_id": "sanofi_process_automation",
                "title": "Automação em produção",
                "experience_id": "sanofi_operador_producao",
                "context": "Contexto",
                "actions": ["Ação"],
                "results": ["Resultado"],
                "metrics": ["180 POPs"],
                "capabilities": ["produção"],
                "allowed_claims": ["Claim"],
                "source_refs": [{"path": "autoconhecimento.md", "lines": "53-65"}],
                "artifact_guidance": {"cv": "Formulação curta"},
                "cv_facts": {
                    "company": "Sanofi-Aventis",
                    "role": "Operador de Produção",
                    "period": "fev/1998 — jun/2000",
                    "scope_bullet": "Atuei em produção farmacêutica.",
                    "result_bullet": "Escrevi mais de 180 POPs.",
                    "focus_terms": ["produção"],
                    "leverage": {"default": "Estruturei controles operacionais."},
                },
            }
        ],
    }
    legacy = {
        "schema_version": 1,
        "candidate": {"name": "Felipe Armel"},
        "experiences": [
            {
                "id": "wehandle_head_operacoes",
                "company": "wehandle",
                "role": "Head de Operações",
                "period": "maio/2024 — fev/2026",
            }
        ],
    }

    view = candidate_evidence.build_cv_facts_view(evidence, legacy_facts=legacy)

    assert [item["id"] for item in view["experiences"]] == [
        "wehandle_head_operacoes",
        "sanofi_operador_producao",
    ]
    assert view["experiences"][1]["result_bullet"] == "Escrevi mais de 180 POPs."


def test_candidate_evidence_education_replaces_stale_localized_facts() -> None:
    evidence = {
        "schema_version": 1,
        "candidate": {"name": "Felipe Armel"},
        "stories": [
            {
                "story_id": "story_one",
                "title": "História um",
                "context": "Contexto",
                "actions": ["Ação"],
                "results": ["Resultado"],
                "metrics": [],
                "capabilities": ["operação"],
                "allowed_claims": ["Claim"],
                "source_refs": [{"path": "autoconhecimento.md", "lines": "1-2"}],
                "artifact_guidance": {"cv": "Formulação curta"},
            }
        ],
        "facts": {
            "education": {
                "pt-BR": ["MBA em Inteligência Artificial Aplicada a Negócios — FAAP"],
                "en": [
                    "Postgraduate Certificate in Applied Artificial Intelligence for Business: FAAP (expected May 2027)",
                    "Postgraduate Certificate in Corporate Strategy: BSP Business School São Paulo (2017)",
                ],
            }
        },
    }
    legacy = {
        "education": {
            "pt-BR": ["formação antiga"],
            "en": ["Specialization Certificate in Corporate Strategies"],
        },
        "experiences": [],
    }

    view = candidate_evidence.build_cv_facts_view(evidence, legacy_facts=legacy)

    assert view["education"]["en"] == evidence["facts"]["education"]["en"]
    assert view["education"]["pt-BR"] == evidence["facts"]["education"]["pt-BR"]


def test_rebuild_candidate_facts_writes_the_derived_view(tmp_path: Path) -> None:
    evidence_path = tmp_path / "candidate_evidence.json"
    legacy_path = tmp_path / "candidate_cv_facts.json"
    output_path = tmp_path / "derived_candidate_cv_facts.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate": {"name": "Felipe Armel"},
                "stories": [
                    {
                        "story_id": "story_one",
                        "title": "História um",
                        "context": "Contexto",
                        "actions": ["Ação"],
                        "results": ["Resultado"],
                        "metrics": [],
                        "capabilities": ["operações"],
                        "allowed_claims": ["Claim"],
                        "source_refs": [{"path": "autoconhecimento.md", "lines": "1-2"}],
                        "artifact_guidance": {"cv": "Formulação curta"},
                        "cv_facts": {
                            "company": "Acme",
                            "role": "Head de Operações",
                            "period": "2024 — 2026",
                            "scope_bullet": "Escopo.",
                            "result_bullet": "Resultado.",
                            "focus_terms": ["operações"],
                            "leverage": {"default": "Mecanismo."},
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    legacy_path.write_text(
        json.dumps({"schema_version": 1, "candidate": {}, "experiences": []}),
        encoding="utf-8",
    )

    result = candidate_evidence.rebuild_candidate_facts(
        evidence_path=evidence_path,
        legacy_facts_path=legacy_path,
        output_path=output_path,
    )

    assert result["output"] == output_path
    rebuilt = json.loads(output_path.read_text(encoding="utf-8"))
    assert rebuilt["experiences"][0]["id"] == "story_one"


def test_rebuild_candidate_facts_restores_readability_for_runtime_agent(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "candidate_evidence.json"
    legacy_path = tmp_path / "candidate_cv_facts.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate": {"name": "Felipe Armel"},
                "stories": [
                    {
                        "story_id": "story_one",
                        "title": "História um",
                        "context": "Contexto",
                        "actions": ["Ação"],
                        "results": ["Resultado"],
                        "metrics": [],
                        "capabilities": ["operação"],
                        "allowed_claims": ["Claim"],
                        "source_refs": [{"path": "autoconhecimento.md", "lines": "1-2"}],
                        "artifact_guidance": {"cv": "Formulação curta"},
                    }
                ],
                "facts": {"education": {"en": ["Postgraduate Certificate"]}},
            }
        ),
        encoding="utf-8",
    )
    legacy_path.write_text(
        json.dumps({"schema_version": 1, "candidate": {}, "experiences": []}),
        encoding="utf-8",
    )
    legacy_path.chmod(0o600)

    candidate_evidence.rebuild_candidate_facts(
        evidence_path=evidence_path,
        legacy_facts_path=legacy_path,
        output_path=legacy_path,
    )

    assert legacy_path.stat().st_mode & 0o004
