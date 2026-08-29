from __future__ import annotations

from career.services import cover_letter, cv_content, feras, habilidades_chave


def _pack() -> dict:
    return {
        "application_id": "app-a",
        "fit_map_revision_id": "fit-a",
        "positioning_revision_id": "pos-a",
        "candidate_evidence_revision_id": "ref-a",
        "thesis": "Conectar execução e crescimento com disciplina operacional.",
        "persona": "Executivo de operações e negócios",
        "stories": [
            {
                "story_id": "story_a",
                "title": "Escala com governança",
                "context": "A operação precisava crescer com controle.",
                "actions": ["Estruturei o rito e os indicadores."],
                "results": ["Aumentei a escala com menor custo."],
                "metrics": ["10%"],
                "capabilities": ["operações", "crescimento"],
                "allowed_claims": ["Conectei escala e governança."],
                "source_refs": [{"path": "autoconhecimento.md", "lines": "1-2"}],
            }
        ],
        "claims": ["Conectei escala e governança."],
        "keywords": [{"keyword": "operações", "coverage": "covered_exact"}],
        "gaps": [],
        "artifact_targets": ["cv", "feras", "cover_letter", "habilidades"],
    }


def test_all_artifact_adapters_use_the_same_story_and_allowed_claim() -> None:
    pack = _pack()
    outputs = [
        cv_content.build_from_positioning_pack(pack),
        feras.build_from_positioning_pack(pack),
        cover_letter.build_from_positioning_pack(pack),
        habilidades_chave.build_from_positioning_pack(pack),
    ]

    for output in outputs:
        assert output["provenance"]["story_ids"] == ["story_a"]
        assert output["provenance"]["claim_ids"] == ["Conectei escala e governança."]
        assert "Conectei escala e governança." in output["content"]
        assert "Claim não permitido" not in output["content"]


def test_fit_map_builders_accept_positioning_pack_without_losing_legacy_input() -> None:
    pack = _pack()
    fit_map = {
        "cargo": "Diretor de Operações",
        "empresa": "Empresa A",
        "historias_selecionadas": {"principal": {"resultado": "Resultado legado"}},
        "keywords_para_ats": ["operações"],
    }
    normalized = {"positioning_pack": pack}

    assert "Resultado legado" in feras.build_from_fit_map(fit_map, normalized_pack=normalized)
    assert "Conectei escala e governança." in feras.build_from_fit_map(fit_map, normalized_pack=normalized)
    assert "Conectei escala e governança." in cover_letter.build_from_fit_map(fit_map, normalized_pack=normalized)
    assert "Conectei escala e governança." in habilidades_chave.build_from_fit_map(fit_map, normalized_pack=normalized)
