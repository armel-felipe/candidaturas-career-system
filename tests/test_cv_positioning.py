import json
from copy import deepcopy
from pathlib import Path

import pytest

from career.services import applications_v2, cv_content, cv_positioning, derived_context, provenance
from career.services.cv_positioning import load_catalog, select_positioning
from career.utils import ValidationFailure, sha256_file


def _entry(entry_id, area, caso, resultado_chave, indice=1):
    return {
        "id": entry_id,
        "area": area,
        "indice": indice,
        "casos": caso,
        "resultado_chave": resultado_chave,
    }


def _write_catalog(tmp_path, entries):
    path = tmp_path / "catalogo.json"
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


def _planning_fit_map():
    return {
        "cargo": "Head de Planejamento",
        "dor_central": "Equilibrar capacidade e nível de serviço",
        "keywords_habilidade_ats": [{"keyword": "S&OP", "prioridade": 1}],
        "keywords_vaga": ["forecast"],
        "competencias_vaga": ["planejamento de demanda"],
        "historias_selecionadas": {"principal": {"empresa": "iFood", "resultado": "cenários"}},
        "objecoes": ["experiência setorial"],
    }


def test_select_positioning_prefers_case_matching_full_fit_context(tmp_path):
    catalog = _write_catalog(
        tmp_path,
        [
            _entry(
                1,
                "Planejamento integrado e S&OP",
                "Equilibrar demanda, capacidade e nível de serviço.",
                "Governança de orçamento e cenários.",
            ),
            _entry(2, "Customer success", "Reduzir churn e ampliar adoção.", "Aumentei retenção."),
        ],
    )

    selected = select_positioning(
        _planning_fit_map(),
        "Responsável por forecast, demanda e capacidade.",
        catalog_path=catalog,
    )

    assert selected["catalog_entry_id"] == 1
    assert selected["caso"] == "Equilibrar demanda, capacidade e nível de serviço."
    assert selected["matched_signals"]


def test_result_key_breaks_tie_without_being_returned(tmp_path):
    catalog = _write_catalog(
        tmp_path,
        [
            _entry(1, "Planejamento", "Equilibrar demanda", "Acelerei atendimento em suporte."),
            _entry(2, "Planejamento", "Equilibrar demanda", "Estruturei cenários de capacidade."),
        ],
    )

    selected = select_positioning(
        {"cargo": "Gerente de Planejamento", "dor_central": "demanda e cenários de capacidade"},
        "",
        catalog_path=catalog,
    )

    assert selected["catalog_entry_id"] == 2
    assert "resultado_chave" not in selected
    assert "Estruturei cenários" not in json.dumps(selected, ensure_ascii=False)


def test_lower_id_breaks_final_tie(tmp_path):
    catalog = _write_catalog(
        tmp_path,
        [
            _entry(9, "Planejamento", "Equilibrar demanda", "Mesmo texto"),
            _entry(3, "Planejamento", "Equilibrar demanda", "Mesmo texto"),
        ],
    )

    selected = select_positioning({"cargo": "Planejamento"}, "", catalog_path=catalog)

    assert selected["catalog_entry_id"] == 3


def test_selector_returns_none_without_area_or_case_intersection(tmp_path):
    catalog = _write_catalog(
        tmp_path,
        [_entry(1, "Planejamento", "Equilibrar demanda", "Cenários de capacidade")],
    )

    assert select_positioning({"cargo": "Advogado tributário"}, "contencioso fiscal", catalog_path=catalog) is None


@pytest.mark.parametrize(
    "entries",
    [
        [_entry(1, "Planejamento", "", "Cenários")],
        [_entry(1, "Planejamento", "Demanda", "Cenários"), _entry(1, "Operações", "Custos", "Eficiência")],
    ],
)
def test_load_catalog_rejects_invalid_entries(tmp_path, entries):
    catalog = _write_catalog(tmp_path, entries)

    with pytest.raises(ValidationFailure, match="catalog"):
        load_catalog(catalog)


def test_cv_payload_emits_case_without_publishing_catalog_result_key(monkeypatch, tmp_path):
    catalog = _write_catalog(
        tmp_path,
        [
            _entry(
                1,
                "Planejamento integrado e S&OP",
                "Equilibrar demanda, capacidade e nível de serviço.",
                "RESULTADO EXCLUSIVO R$ 999 milhões que não pode aparecer no CV.",
            )
        ],
    )
    job_description = tmp_path / "vaga.md"
    job_description.write_text("Liderar planejamento de demanda, capacidade e S&OP.", encoding="utf-8")
    fit_map_path = tmp_path / "fit_map.json"
    fit_map = {
        **_planning_fit_map(),
        "empresa": "Acme",
        "idioma": "pt-BR",
        "historias_selecionadas": {
            "principal": {"empresa": "iFood"},
            "secundaria": {"empresa": "wehandle"},
            "terceira": {"empresa": "VivaReal"},
        },
    }
    fit_map_path.write_text(json.dumps(fit_map, ensure_ascii=False), encoding="utf-8")
    active = derived_context.ActiveJobContext(
        job_description_path=job_description,
        fingerprint=sha256_file(job_description),
        company="Acme",
        role="Head de Planejamento",
        source_type="test",
        source_id=None,
    )
    monkeypatch.setattr(cv_positioning, "CATALOG_PATH", catalog)

    payload = cv_content._build_cv_payload(
        active,
        fit_map,
        source_fit_map=str(fit_map_path),
        candidate_facts_revision=provenance.candidate_facts_revision(),
    )

    assert cv_positioning.normalize_tokens(payload["positioning"]["caso"]).issubset(
        cv_positioning.normalize_tokens(payload["summary"])
    )
    assert payload["positioning_support"]["catalog_entry_id"] == 1
    assert payload["claim_provenance"]["positioning"] == payload["positioning_support"]["evidence_id"]
    assert "RESULTADO EXCLUSIVO R$ 999 milhões" not in payload["summary"]
    assert all("RESULTADO EXCLUSIVO" not in item["summary_fragment"] for item in payload["summary_support"])


def test_canonical_provenance_rejects_tampered_positioning_case(monkeypatch, tmp_path):
    catalog = _write_catalog(
        tmp_path,
        [_entry(1, "Planejamento", "Equilibrar demanda e capacidade.", "Cenários de capacidade")],
    )
    job_description = tmp_path / "vaga.md"
    job_description.write_text("Planejamento de demanda e capacidade.", encoding="utf-8")
    fit_map_path = tmp_path / "fit_map.json"
    fit_map = {
        **_planning_fit_map(),
        "empresa": "Acme",
        "idioma": "pt-BR",
        "historias_selecionadas": {"principal": {"empresa": "iFood"}},
    }
    fit_map_path.write_text(json.dumps(fit_map, ensure_ascii=False), encoding="utf-8")
    active = derived_context.ActiveJobContext(
        job_description_path=job_description,
        fingerprint=sha256_file(job_description),
        company="Acme",
        role="Head de Planejamento",
        source_type="test",
        source_id=None,
    )
    monkeypatch.setattr(cv_positioning, "CATALOG_PATH", catalog)
    payload = cv_content._build_cv_payload(
        active,
        fit_map,
        source_fit_map=str(fit_map_path),
        candidate_facts_revision=provenance.candidate_facts_revision(),
    )
    cv_content.validate_canonical_provenance(
        payload,
        fit_map=fit_map,
        fit_map_path=fit_map_path,
        fit_map_sha256=sha256_file(fit_map_path),
    )
    tampered = deepcopy(payload)
    tampered["positioning"]["caso"] = "Caso adulterado"

    with pytest.raises(ValidationFailure, match="positioning"):
        cv_content.validate_canonical_provenance(
            tampered,
            fit_map=fit_map,
            fit_map_path=fit_map_path,
            fit_map_sha256=sha256_file(fit_map_path),
        )


def test_application_contract_rejects_tampered_positioning_case(monkeypatch, tmp_path):
    catalog = _write_catalog(
        tmp_path,
        [_entry(1, "Planejamento", "Equilibrar demanda e capacidade.", "Cenários de capacidade")],
    )
    job_description = tmp_path / "vaga.md"
    job_description.write_text("Planejamento de demanda e capacidade.", encoding="utf-8")
    fit_map_path = tmp_path / "fit_map.json"
    fit_map = {
        **_planning_fit_map(),
        "empresa": "Acme",
        "idioma": "pt-BR",
        "historias_selecionadas": {"principal": {"empresa": "iFood"}},
    }
    fit_map_path.write_text(json.dumps(fit_map, ensure_ascii=False), encoding="utf-8")
    active = derived_context.ActiveJobContext(job_description, sha256_file(job_description), "Acme", "Head de Planejamento", "test", None)
    monkeypatch.setattr(cv_positioning, "CATALOG_PATH", catalog)
    payload = cv_content._build_cv_payload(
        active,
        fit_map,
        source_fit_map=str(fit_map_path),
        candidate_facts_revision=provenance.candidate_facts_revision(),
    )
    payload["positioning"]["caso"] = "Caso adulterado"
    content_path = tmp_path / "cv_content.json"
    content_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationFailure, match="positioning"):
        applications_v2._validate_cv_content_contract({"cv_content": content_path, "fit_map": fit_map_path})


def test_positioning_catalog_is_a_declared_canonical_reference():
    skill = Path(".agents/skills/career-system/SKILL.md").read_text(encoding="utf-8")

    assert "catalogo_resultados_chave.json" in skill
    assert "não é fonte de alegação" in skill
