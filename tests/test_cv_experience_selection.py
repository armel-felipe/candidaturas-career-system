from __future__ import annotations

import re

import pytest

from career.services import applications_v2
import career.services.cv_content as cv_content
from career.services.cv_content import _select_experiences
from career.utils import ValidationFailure


def _vivo_mis_fit_map() -> dict:
    return {
        "cargo": "Gerente MIS Operações",
        "empresa": "Vivo (Telefônica Brasil)",
        "historias_selecionadas": {
            "principal": {"empresa": "WeHandle"},
            "secundaria": {"empresa": "iFood — Diretor de Operações"},
            "terceira": {"empresa": "Trifil — Coordenador de Inteligência Comercial"},
        },
        "keywords_habilidade_ats": [
            {"prioridade": 1, "keyword": "Gestão de MIS", "experiencia_alvo": "Trifil — Coordenador de Inteligência Comercial"},
            {"prioridade": 2, "keyword": "Inteligência Operacional", "experiencia_alvo": "iFood — Diretor de Operações"},
            {"prioridade": 3, "keyword": "Business Intelligence", "experiencia_alvo": "Trifil — Coordenador de Inteligência Comercial"},
            {"prioridade": 4, "keyword": "Dashboards Gerenciais", "experiencia_alvo": "iFood — Head de Operações"},
            {"prioridade": 5, "keyword": "Automação de Relatórios", "experiencia_alvo": "Trifil — Coordenador de Inteligência Comercial"},
            {"prioridade": 6, "keyword": "Governança de Dados", "experiencia_alvo": "WeHandle — Head de Operações"},
            {"prioridade": 7, "keyword": "Análise de Performance", "experiencia_alvo": "WeHandle — Head de Operações"},
            {"prioridade": 8, "keyword": "Indicadores de Contact Center", "experiencia_alvo": "WeHandle — Head de Operações"},
        ],
    }


def test_fifth_experience_is_most_recent_non_direct_fallback() -> None:
    fit_map = {
        "historias_selecionadas": {},
        "keywords_habilidade_ats": [
            {"prioridade": 1, "experiencia_alvo": "wehandle"},
            {"prioridade": 2, "experiencia_alvo": "iFood"},
            {"prioridade": 3, "experiencia_alvo": "VivaReal"},
        ],
    }

    selected = _select_experiences(fit_map)

    assert [item["id"] for item in selected] == [
        "wehandle_head_operacoes",
        "ifood_diretor_operacoes",
        "ifood_head_operacoes",
        "renault_cs",
        "vivareal_planejamento_operacoes",
    ]
    assert "trifil_expedicao" not in [item["id"] for item in selected]


def test_vivo_fit_map_does_not_append_customer_success_when_targets_are_sufficient() -> None:
    selected_ids = [item["id"] for item in _select_experiences(_vivo_mis_fit_map())]

    assert "renault_cs" not in selected_ids
    assert set(selected_ids) == {
        "wehandle_head_operacoes",
        "ifood_diretor_operacoes",
        "ifood_head_operacoes",
        "trifil_sop",
        "trifil_inteligencia_comercial",
        "trifil_expedicao",
    }


def test_vivo_targeted_fit_map_does_not_fill_minimum_with_unrelated_customer_success() -> None:
    fit_map = {
        "historias_selecionadas": {
            "principal": {"empresa": "iFood - Diretor de Operações"},
            "secundaria": {"empresa": "wehandle - Head de Operações"},
            "terceira": {"empresa": "VivaReal - Gerente de Planejamento Comercial e Operações"},
        },
        "keywords_habilidade_ats": [
            {
                "prioridade": 1,
                "keyword": "Dashboards Gerenciais e Executivos",
                "experiencia_alvo": "iFood / wehandle",
            }
        ],
    }

    selected_ids = [item["id"] for item in _select_experiences(fit_map)]

    assert "renault_cs" not in selected_ids
    assert "trifil_inteligencia_comercial" in selected_ids


def test_summary_support_prefers_vivo_mis_target_experiences() -> None:
    fit_map = _vivo_mis_fit_map()
    selected = _select_experiences(fit_map)

    pairs = cv_content._summary_support_pairs(selected, fit_map=fit_map)

    assert [item[0] for item in pairs] == [
        "faturamento anual de R$80M para R$120M com algoritmo de alocação de estoque",
        "redução de 13% no custo por atendimento e impacto de 15% na margem bruta",
    ]


def test_summary_support_skips_selected_experience_without_summary_fragment() -> None:
    selected = [
        {
            "id": "trifil_expedicao",
            "company": "Scalina (Trifil)",
            "role": "Coordenador de Expedição",
        },
        {
            "id": "ifood_diretor_operacoes",
            "company": "iFood",
            "role": "Diretor de Operações",
        },
        {
            "id": "wehandle_head_operacoes",
            "company": "wehandle",
            "role": "Head de Operações",
        },
    ]
    fit_map = {
        "keywords_habilidade_ats": [
            {
                "prioridade": 1,
                "keyword": "expedição",
                "experiencia_alvo": "Trifil — Coordenador de Expedição",
            }
        ]
    }

    pairs = cv_content._summary_support_pairs(selected, fit_map=fit_map)

    assert [selected[index]["id"] for _fragment, index, _bullet in pairs] == [
        "wehandle_head_operacoes",
        "ifood_diretor_operacoes",
    ]


def test_vivo_mis_keywords_materialize_only_in_target_experiences() -> None:
    fit_map = _vivo_mis_fit_map()
    facts = cv_content.load_canonical_cv_facts()["experiences"]
    materialized = {}

    for experience in facts:
        targeted_keywords = [
            item
            for item in fit_map["keywords_habilidade_ats"]
            if cv_content._experience_matches_target(
                experience, str(item["experiencia_alvo"])
            )
        ]
        materialized[experience["id"]] = cv_content._materialize_experience(
            experience,
            "operations",
            language="pt-BR",
            ats_keywords=targeted_keywords,
        )

    for item in fit_map["keywords_habilidade_ats"]:
        target = next(
            experience
            for experience in facts
            if cv_content._experience_matches_target(
                experience, str(item["experiencia_alvo"])
            )
        )
        target_text = " ".join(materialized[target["id"]]["bullets"])
        assert cv_content._normalize(str(item["keyword"])) in cv_content._normalize(target_text)

    assert "customer success" not in " ".join(
        materialized["renault_cs"]["bullets"]
    ).casefold()


def test_vivo_mis_fit_map_keyword_variants_materialize_exactly() -> None:
    facts = cv_content.load_canonical_cv_facts()["experiences"]
    keywords = [
        {
            "prioridade": 1,
            "keyword": "Dashboards Gerenciais e Executivos",
            "experiencia_alvo": "iFood / wehandle",
        },
        {
            "prioridade": 2,
            "keyword": "Gestão de Indicadores",
            "experiencia_alvo": "wehandle - Head de Operações",
        },
        {
            "prioridade": 3,
            "keyword": "Automação de Relatórios e Indicadores",
            "experiencia_alvo": "iFood / wehandle",
        },
    ]

    for experience in facts:
        targeted = [
            item
            for item in keywords
            if cv_content._experience_matches_target(
                experience, str(item["experiencia_alvo"])
            )
        ]
        materialized = cv_content._materialize_experience(
            experience,
            "operations",
            language="pt-BR",
            ats_keywords=targeted,
        )
        text = " ".join(materialized["bullets"])
        for item in targeted:
            assert cv_content._normalize(str(item["keyword"])) in cv_content._normalize(text)


def test_english_cv_materializes_targeted_ats_keywords_in_defensible_bullets() -> None:
    experience = {
        "id": "ifood_diretor_operacoes",
        "company": "iFood",
        "role": "Operations Director",
        "bullets": [
            "Led a 240-person organization.",
            "Ran a monthly executive S&OP cadence with product and operations.",
            "Expanded coverage from 400 to 800 cities.",
        ],
    }
    keywords = [
        {
            "keyword": "Operational Excellence",
            "experiencia_alvo": "iFood - Operations Director",
            "prioridade": 1,
        },
        {
            "keyword": "Cross-functional Leadership",
            "experiencia_alvo": "iFood - Operations Director",
            "prioridade": 2,
        },
    ]

    result = cv_content._apply_defensible_english_ats_keywords(experience, keywords)
    text = " ".join(result["bullets"])

    assert "operational excellence" in text.lower()
    assert "cross-functional leadership" in text.lower()
    assert "Expanded coverage from 400 to 800 cities." in text


def test_materialize_experience_accepts_targeted_ats_keywords_for_provenance() -> None:
    experience = {
        "id": "ifood_diretor_operacoes",
        "company": "iFood",
        "role": "Operations Director",
        "period": "jan/2020 a dez/2022",
        "scope_bullet": "Led a 240-person organization.",
        "leverage": {"default": "Ran a monthly executive cadence."},
        "result_bullet": "Expanded coverage from 400 to 800 cities.",
    }
    keywords = [
        {
            "keyword": "Operational Excellence",
            "experiencia_alvo": "iFood - Operations Director",
            "prioridade": 1,
        }
    ]

    result = cv_content._materialize_experience(
        experience,
        "operations",
        language="en",
        ats_keywords=keywords,
    )

    assert "operational excellence" in " ".join(result["bullets"]).lower()


def test_quantified_experience_result_is_reserved_for_bullet_three() -> None:
    experience = next(
        item
        for item in cv_content.load_canonical_cv_facts()["experiences"]
        if item["id"] == "ifood_diretor_operacoes"
    )

    result = cv_content._materialize_experience(
        experience,
        "operations",
        language="pt-BR",
    )

    bullet2, bullet3 = result["bullets"][1:3]

    assert "400 para 800" not in bullet2
    assert "400 para 800" in bullet3
    assert re.search(r"(?:R\$|\d+(?:[.,]\d+)?\s*%)", bullet3)
    assert bullet2.casefold() != bullet3.casefold()


def test_budget_responsibility_is_not_repeated_as_a_result_metric() -> None:
    experience = next(
        item
        for item in cv_content.load_canonical_cv_facts()["experiences"]
        if item["id"] == "ifood_diretor_operacoes"
    )

    result = cv_content._materialize_experience(
        experience,
        "operations",
        language="pt-BR",
    )

    bullet1, bullet2, bullet3 = result["bullets"]

    assert "r$300mm/ano" in bullet1.casefold()
    assert "r$300mm/ano" not in bullet2.casefold()
    assert "r$300mm/ano" not in bullet3.casefold()


def test_concise_contract_rejects_result_metric_repeated_in_scope() -> None:
    experience = {
        "bullets": [
            {"text": "Fui responsável por operações e pelo budget de R$300MM/ano."},
            {"text": "Conduzi o planejamento com cenários para sustentar a execução."},
            {"text": "Ampliei a cobertura logística de 400 para 800 cidades e gerenciei budget de R$300MM/ano."},
        ]
    }

    with pytest.raises(ValidationFailure, match="bullet 1.*bullet 3.*quantitative"):
        applications_v2._validate_concise_bullet2(experience, 1)


def test_targeted_ats_clause_keeps_multi_location_keyword_out_of_result_range() -> None:
    experience = next(
        item
        for item in cv_content.load_canonical_cv_facts()["experiences"]
        if item["id"] == "ifood_diretor_operacoes"
    )

    result = cv_content._materialize_experience(
        experience,
        "operations",
        language="en",
        ats_keywords=[
            {
                "keyword": "Multi-location Operations",
                "experiencia_alvo": "iFood - Diretor de Operações",
                "prioridade": 1,
            }
        ],
    )

    bullet2, bullet3 = result["bullets"][1:3]

    assert "multi-location operations" in bullet2.casefold()
    assert "400 to 800" not in bullet2
    assert "400 to 800" in bullet3


def test_materialize_experience_rejects_result_without_a_metric() -> None:
    experience = {
        "id": "synthetic_experience",
        "company": "Example",
        "role": "Operations Manager",
        "period": "jan/2020 a dez/2022",
        "scope_bullet": "Fui responsável pela operação.",
        "leverage": {"default": "Estruturei o rito operacional para sustentar a execução."},
        "result_bullet": "Melhorei a operação com uma nova rotina.",
    }

    with pytest.raises(ValidationFailure, match="result_bullet"):
        cv_content._materialize_experience(experience, "operations", language="pt-BR")


def test_concise_contract_rejects_quantified_bullet_two() -> None:
    experience = {
        "bullets": [
            {"text": "Fui responsável pela operação e pelo time."},
            {"text": "Conduzi o planejamento com cenários para ampliar a cobertura de 400 para 800 cidades."},
            {"text": "Ampliei a cobertura logística de 400 para 800 cidades."},
        ]
    }

    with pytest.raises(ValidationFailure, match="bullet 2.*quantitative"):
        applications_v2._validate_concise_bullet2(experience, 1)


def test_concise_contract_requires_metric_in_bullet_three() -> None:
    experience = {
        "bullets": [
            {"text": "Fui responsável pela operação e pelo time."},
            {"text": "Conduzi o planejamento com cenários para sustentar a execução."},
            {"text": "Melhorei a operação com uma nova rotina."},
        ]
    }

    with pytest.raises(ValidationFailure, match="bullet 3.*metric"):
        applications_v2._validate_concise_bullet2(experience, 1)


def test_portuguese_cv_materializes_supported_customer_experience_and_zendesk() -> None:
    experience = next(
        item
        for item in cv_content.load_canonical_cv_facts()["experiences"]
        if item["id"] == "wehandle_head_operacoes"
    )
    result = cv_content._materialize_experience(
        experience,
        "cx_saas_operations",
        language="pt-BR",
        ats_keywords=[
            {
                "keyword": "Customer Experience",
                "experiencia_alvo": "WeHandle - Head de Operações",
                "prioridade": 1,
            },
            {
                "keyword": "Zendesk",
                "experiencia_alvo": "WeHandle - Head de Operações",
                "prioridade": 2,
            },
        ],
    )
    text = " ".join(result["bullets"]).lower()

    assert "customer experience" in text
    assert "zendesk" in text


def test_portuguese_cv_materializes_customer_support_keywords_from_evidence() -> None:
    experience = next(
        item
        for item in cv_content.load_canonical_cv_facts()["experiences"]
        if item["id"] == "wehandle_head_operacoes"
    )
    keywords = [
        "Gestão de Customer Experience",
        "Gestão de Operações de Atendimento",
        "SLA de Atendimento",
        "CSAT (Satisfação do Cliente)",
        "Autoatendimento e Automação",
        "Inteligência Artificial aplicada a Atendimento",
        "Monitoria de Qualidade de Atendimento",
    ]

    result = cv_content._materialize_experience(
        experience,
        "cx_saas_operations",
        language="pt-BR",
        ats_keywords=[
            {
                "keyword": keyword,
                "experiencia_alvo": "wehandle - Head de Operações",
                "prioridade": index,
            }
            for index, keyword in enumerate(keywords, start=1)
        ],
    )
    text = " ".join(result["bullets"]).casefold()

    for keyword in keywords:
        assert cv_content._normalize(keyword) in cv_content._normalize(text)


def test_tempo_portuguese_keywords_are_materialized_from_targeted_evidence() -> None:
    facts = cv_content.load_canonical_cv_facts()["experiences"]
    targets = {
        "planejamento estratégico": "iFood — Diretor de Operações",
        "planejamento orçamentário": "iFood — Diretor de Operações",
        "forecast": "iFood — Diretor de Operações",
        "análise de investimentos": "Renault do Brasil — Gerente de Customer Success",
        "matemática financeira": "Renault do Brasil — Gerente de Customer Success",
        "indicadores de negócio": "iFood — Diretor de Operações",
        "precificação": "iFood — Head de Operações",
        "margens": "wehandle — Head de Operações",
    }
    selected_ids = {
        "ifood_diretor_operacoes",
        "renault_cs",
        "ifood_head_operacoes",
        "wehandle_head_operacoes",
    }
    materialized = []
    for experience in facts:
        if experience["id"] not in selected_ids:
            continue
        materialized.append(
            cv_content._materialize_experience(
                experience,
                "operations",
                language="pt-BR",
                ats_keywords=[
                    {
                        "keyword": keyword,
                        "experiencia_alvo": target,
                        "prioridade": index,
                    }
                    for index, (keyword, target) in enumerate(targets.items(), start=1)
                    if cv_content._experience_matches_target(experience, target)
                ],
            )
        )

    text = " ".join(" ".join(item["bullets"]) for item in materialized).casefold()

    for keyword in targets:
        assert keyword.casefold() in text
    assert "r$300mm/ano" in text
    assert "24% para 46%" in text
    assert "15% na margem bruta" in text


def test_jobgether_operations_keywords_are_materialized_from_candidate_evidence() -> None:
    facts = cv_content.load_canonical_cv_facts()["experiences"]
    targets = {
        "Operations Management": "iFood - Diretor de Operações",
        "Service Operations": "wehandle - Head de Operações",
        "Multi-location Operations": "iFood - Diretor de Operações",
        "Digital Conversion": "VivaReal - Gerente de Planejamento Comercial",
        "Customer Retention": "wehandle - Head de Operações",
        "Operational Efficiency": "iFood - Diretor de Operações",
        "Contribution Margin": "wehandle - Head de Operações",
    }
    selected = [
        cv_content._materialize_experience(
            item,
            "operations",
            language="en",
            ats_keywords=[
                {
                    "keyword": keyword,
                    "experiencia_alvo": target,
                    "prioridade": index,
                }
                for index, (keyword, target) in enumerate(targets.items(), start=1)
                if item["company"].casefold() in target.casefold()
                or item["role"].casefold() in target.casefold()
            ],
        )
        for item in facts
        if item["company"].casefold() in {"ifood", "wehandle", "vivareal"}
    ]
    text = " ".join(" ".join(item["bullets"]) for item in selected).lower()

    for keyword in targets:
        assert keyword.casefold() in text


def test_modaxo_ai_keywords_are_materialized_from_candidate_evidence() -> None:
    facts = cv_content.load_canonical_cv_facts()["experiences"]
    targets = {
        "AI Transformation": "WeHandle - Head de Operações",
        "AI Adoption": "WeHandle - Head de Operações",
        "AI Use Cases": "WeHandle - Head de Operações",
        "AI Pilots": "WeHandle - Head de Operações",
        "Stakeholder Management": "iFood - Diretor de Operações",
        "Data-Driven": "iFood / WeHandle - Head/Diretor",
    }
    selected = [
        cv_content._materialize_experience(
            item,
            "operations",
            language="en",
            ats_keywords=[
                {
                    "keyword": keyword,
                    "experiencia_alvo": target,
                    "prioridade": index,
                }
                for index, (keyword, target) in enumerate(targets.items(), start=1)
                if item["company"].casefold() in target.casefold()
                or item["role"].casefold() in target.casefold()
            ],
        )
        for item in facts
        if item["company"].casefold() in {"ifood", "wehandle"}
    ]
    text = " ".join(" ".join(item["bullets"]) for item in selected).lower()

    for keyword in targets:
        assert keyword.casefold() in text


def test_planning_keywords_are_materialized_only_from_canonical_evidence() -> None:
    facts = cv_content.load_canonical_cv_facts()["experiences"]
    target = "Trifil - Coordenador de S&OP"
    keywords = [
        "Sales & Operations Planning (S&OP)",
        "Capacity Planning",
        "Demand Forecasting",
        "Inventory Management",
        "Safety Stock",
        "Lead Time Management",
    ]
    experience = next(item for item in facts if item["id"] == "trifil_sop")

    result = cv_content._materialize_experience(
        experience,
        "planning_sop_capacity",
        language="en",
        ats_keywords=[
            {
                "keyword": keyword,
                "experiencia_alvo": target,
                "prioridade": index,
            }
            for index, keyword in enumerate(keywords, start=1)
        ],
    )
    text = " ".join(result["bullets"]).lower()

    for keyword in keywords:
        assert keyword.casefold() in text
    assert "siop" not in text


def test_siop_accepts_sop_as_curated_english_cv_equivalent() -> None:
    variants = cv_content._keyword_translation_variants("SIOP")

    assert "S&OP" in variants


def test_supply_chain_keyword_materializes_from_planning_evidence() -> None:
    experience = next(
        item
        for item in cv_content.load_canonical_cv_facts()["experiences"]
        if item["id"] == "trifil_sop"
    )
    result = cv_content._materialize_experience(
        experience,
        "planning_sop_capacity",
        language="en",
        ats_keywords=[
            {
                "keyword": "supply chain",
                "experiencia_alvo": "Trifil - S&OP Coordinator",
                "prioridade": 1,
            }
        ],
    )

    assert "supply chain" in " ".join(result["bullets"]).lower()
