from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE
from career.services import applications_v2 as applications_v2_service
from career.services import derived_context as derived_context_service
from career.services import fit_map as fit_map_service
from career.utils import ValidationFailure, ensure, read_json, utc_now_iso, write_json


CV_CONTENT_PATH = CAREER_STATE / "cv_content.json"
FIT_MAP_PATH = CAREER_STATE / "fit_map.json"


EXPERIENCE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "wehandle_head_operacoes",
        "company": "wehandle",
        "role": "Head de Operações",
        "period": "maio/2024 — fev/2026",
        "order": 1,
        "focus_terms": {"transformação digital", "inteligência artificial", "liderança", "dados", "cx"},
        "bullets": [
            "Fui responsável pela operação de suporte, CX e backoffice, liderando um time de 30 pessoas e conectando atendimento, produto e dados para acelerar a transformação digital da companhia.",
            "Implantei duas migrações de plataforma, automação com inteligência artificial humanizada e integração de dados via API para dar escala operacional e melhorar a priorização com o time de produto.",
            "Reduzi o custo por atendimento de R$4,14 para R$3,61 (-13%), elevei o CSAT de 85% para 92%, reduzi o TME de 20 para 8 minutos e gerei impacto de 15% na margem bruta.",
        ],
    },
    {
        "id": "ifood_diretor_operacoes",
        "company": "iFood",
        "role": "Diretor de Operações",
        "period": "abr/2022 — mar/2024",
        "order": 2,
        "focus_terms": {"growth", "liderança", "planejamento estratégico", "budget", "canais", "pipeline"},
        "bullets": [
            "Fui responsável por FieldOps, Meios de Pagamento e Novos Negócios, liderando 240 pessoas entre diretos e indiretos e operando growth com expansão geográfica, frota dedicada e alocação de budget.",
            "Conectei marketing, produto, supply e operação em um rito executivo mensal de S&OP, conduzindo cenários, trade-offs e governança para sustentar decisões de crescimento e eficiência.",
            "Ampliei a cobertura logística de 400 para 800 cidades, reduzi a indisponibilidade da frota de 5% para 1%, aumentei viagens agrupadas de 12% para 25% e gerenciei budget de R$300MM/ano.",
        ],
    },
    {
        "id": "ifood_head_operacoes",
        "company": "iFood",
        "role": "Head de Operações",
        "period": "nov/2018 — mar/2022",
        "order": 3,
        "focus_terms": {"dashboards", "pricing", "data-driven growth", "growth", "dados"},
        "bullets": [
            "Fui responsável por liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota, liderando 28 pessoas em uma operação que exigia decisões rápidas e coordenação multifuncional.",
            "Estruturei Dashboards em Grafana, modelei dados com SQL, Databricks e Tableau e conduzi testes controlados de pricing e incentivos para equilibrar oferta, demanda e nível de serviço.",
            "Gerei saving de R$70MM/ano com um simulador de nível de serviço, reduzi o custo de distribuição de MPOS em 80%, cortei o prazo de entrega de 14 para 2 dias e reduzi cancelamentos em 60% no México.",
        ],
    },
    {
        "id": "renault_cs",
        "company": "Renault do Brasil",
        "role": "Gerente de Customer Success",
        "period": "jan/2018 — out/2018",
        "order": 4,
        "focus_terms": {"pipeline", "taxa de conversão", "conversão", "leads"},
        "bullets": [
            "Fui responsável pela transição de dois BPOs com 40 PAs para uma estrutura internalizada de 8 pessoas, redesenhando a operação de leads com mais controle de qualidade e SLA.",
            "Estruturei governança de funil com dados, discadores programados por mim e acompanhamento em tempo real para estabilizar a execução comercial.",
            "Elevei a taxa de conversão de leads de 24% para 46% e aprovei o projeto de transformação em 2 reuniões com base em um ROI corretamente modelado.",
        ],
    },
    {
        "id": "vivareal_planejamento_operacoes",
        "company": "VivaReal",
        "role": "Gerente de Planejamento Comercial e Operações",
        "period": "mai/2015 — dez/2017",
        "order": 5,
        "focus_terms": {"desenvolvimento de negócios", "canais de vendas", "política de preços", "pipeline", "taxa de conversão", "liderança"},
        "bullets": [
            "Fui responsável por planejamento comercial, desenvolvimento de negócios, canais de vendas, política de preços e operações ligadas a SDR, qualidade e cadastro de imóveis, totalizando 33 pessoas e 5 lideranças diretas.",
            "Estruturei Dashboards diários com SQL e Excel automatizado, organizei o pipeline de SDR, defini metas com o time comercial e priorizei roadmap de produto para sustentar expansão e execução.",
            "Elevei a taxa de conversão de SDR inbound de 18% para 50%, reduzi o custo de vendas em 40%, recuperei R$1M em campanhas de inadimplência e escalei a área desenhada de CS para 91 pessoas.",
        ],
    },
    {
        "id": "trifil_inteligencia_comercial",
        "company": "Scalina (Trifil)",
        "role": "Coordenador de Inteligência Comercial",
        "period": "jan/2009 — dez/2009",
        "order": 6,
        "focus_terms": {"data-driven growth", "dashboards", "insights", "pricing", "canais de vendas"},
        "bullets": [
            "Fui responsável por criar a área de inteligência comercial, apoiando a diretoria com informações de mercado, canais de vendas, comissionamento, oportunidades comerciais e política de preços.",
            "Estruturei Data-driven Growth com dados, BI, Dashboards e rotinas em Excel/VBA para sustentar decisões comerciais, normalizar dados do ERP e preparar a base para o sistema B2B.",
            "Reduzi o tempo dos relatórios diários de 4 horas para 14 minutos e aumentei o faturamento anual de R$80M para R$120M com um algoritmo de alocação de estoque orientado por margem e receita.",
        ],
    },
]


DEFAULT_EDUCATION = [
    "MBA Corporate Strategy — BSP Business School São Paulo (2017)",
    "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)",
    "Six Sigma Green Belt — Setec Consulting (2020)",
]

DEFAULT_LANGUAGES = [
    "Português — Nativo",
    "Inglês — Avançado",
]

DEFAULT_STACK = "Excel/VBA · SQL · Python · Databricks · Grafana · Tableau · Power BI · Metabase"


def build_current_cv_content(path: Path = CV_CONTENT_PATH) -> dict[str, Any]:
    active = derived_context_service.resolve_active_job_context()
    _ensure_fit_map_matches_active(active)
    fit_map = read_json(FIT_MAP_PATH)
    selected = _select_experiences(fit_map)
    ensure(4 <= len(selected) <= 8, "cv_content_requires_between_4_and_8_experiences")
    top8 = _top8_keywords(fit_map)
    coverage = _build_ats_coverage(selected, top8)
    payload = {
        "metadata": {
            "kind": "cv_content",
            "created_at": utc_now_iso(),
            "job_fingerprint": active.fingerprint,
            "job_description_path": derived_context_service._relative(active.job_description_path),
            "cargo": fit_map.get("cargo"),
            "empresa": fit_map.get("empresa"),
            "source_fit_map": ".career-state/fit_map.json",
        },
        "output_name": _output_name(fit_map),
        "mode": "concise",
        "persona": _persona_name(fit_map),
        "summary": _build_summary(fit_map),
        "resumo": _build_summary(fit_map),
        "experiences": [
            {
                "role": exp["role"],
                "company": exp["company"],
                "period": exp["period"],
                "bullets": [{"text": bullet} for bullet in exp["bullets"]],
            }
            for exp in selected
        ],
        "experiencias": [
            {
                "cargo": exp["role"],
                "empresa": exp["company"],
                "periodo": exp["period"],
                "bullets": [bullet for bullet in exp["bullets"]],
            }
            for exp in selected
        ],
        "education": list(DEFAULT_EDUCATION),
        "formacao": list(DEFAULT_EDUCATION),
        "languages": list(DEFAULT_LANGUAGES),
        "idiomas": list(DEFAULT_LANGUAGES),
        "stack": DEFAULT_STACK,
        "ats_keyword_coverage": coverage,
    }
    write_json(path, payload)
    validate_cv_content(path)
    return payload


def validate_cv_content(path: Path = CV_CONTENT_PATH) -> dict[str, Any]:
    ensure(path.exists(), f"cv_content_missing: {path}")
    active = derived_context_service.resolve_active_job_context()
    payload = read_json(path)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    ensure(metadata.get("job_fingerprint") == active.fingerprint, "cv_content_stale_for_active_job")
    ensure(str(metadata.get("cargo") or "").strip(), "cv_content_missing_cargo_metadata")
    ensure(str(metadata.get("empresa") or "").strip(), "cv_content_missing_empresa_metadata")
    mock_paths = {
        "cv_content": path,
        "fit_map": FIT_MAP_PATH,
    }
    applications_v2_service._validate_cv_content_contract(mock_paths)
    return {
        "status": "ok",
        "path": str(path),
        "job_fingerprint": metadata.get("job_fingerprint"),
        "output_name": payload.get("output_name"),
        "experiences_count": len(payload.get("experiences", []) or []),
    }


def active_artifact_status() -> dict[str, Any]:
    active = derived_context_service.resolve_active_job_context()
    fit_map_status = fit_map_service.status()
    cv_status = {
        "exists": CV_CONTENT_PATH.exists(),
        "path": str(CV_CONTENT_PATH),
        "matches_active_job": False,
    }
    if CV_CONTENT_PATH.exists():
        payload = read_json(CV_CONTENT_PATH)
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        cv_status["matches_active_job"] = metadata.get("job_fingerprint") == active.fingerprint
        cv_status["output_name"] = payload.get("output_name")
    return {
        "status": "ok" if fit_map_status.get("fit_map", {}).get("matches_active_job") and cv_status["matches_active_job"] else "blocked",
        "active_job": {
            "path": derived_context_service._relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "fit_map": fit_map_status.get("fit_map", {}),
        "cv_content": cv_status,
    }


def invalidate_stale_artifacts() -> dict[str, Any]:
    active = derived_context_service.resolve_active_job_context()
    invalidated: list[str] = []
    for path in (CV_CONTENT_PATH,):
        if not path.exists():
            continue
        payload = read_json(path)
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        if metadata.get("job_fingerprint") != active.fingerprint:
            stale_path = path.with_suffix(path.suffix + ".stale")
            path.rename(stale_path)
            invalidated.append(str(stale_path))
    return {
        "status": "ok",
        "active_fingerprint": active.fingerprint,
        "invalidated": invalidated,
    }


def _ensure_fit_map_matches_active(active: Any) -> None:
    status = fit_map_service.status()
    ensure(status.get("fit_map", {}).get("matches_active_job"), "fit_map_stale_for_active_job")


def _top8_keywords(fit_map: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [item for item in fit_map.get("keywords_habilidade_ats", []) if isinstance(item, dict)]
    entries.sort(key=lambda item: int(item.get("prioridade") or 999))
    return entries[:8]


def _select_experiences(fit_map: dict[str, Any]) -> list[dict[str, Any]]:
    selected_ids: list[str] = []
    story_companies = []
    stories = fit_map.get("historias_selecionadas", {}) if isinstance(fit_map.get("historias_selecionadas"), dict) else {}
    for key in ("principal", "secundaria", "terceira"):
        story = stories.get(key)
        if isinstance(story, dict):
            story_companies.append(str(story.get("empresa") or ""))
    targets = [str(item.get("experiencia_alvo") or "") for item in _top8_keywords(fit_map)]
    for entry in EXPERIENCE_CATALOG:
        company_norm = _normalize(entry["company"])
        role_norm = _normalize(entry["role"])
        if any(company_norm in _normalize(company) for company in story_companies if company):
            selected_ids.append(entry["id"])
            continue
        if any(company_norm in _normalize(target) or role_norm in _normalize(target) for target in targets):
            selected_ids.append(entry["id"])
    fallback_priority = [
        "ifood_diretor_operacoes",
        "ifood_head_operacoes",
        "vivareal_planejamento_operacoes",
        "trifil_inteligencia_comercial",
        "wehandle_head_operacoes",
        "renault_cs",
    ]
    for item_id in fallback_priority:
        if item_id not in selected_ids:
            selected_ids.append(item_id)
        if len(selected_ids) >= 5:
            break
    deduped = [item for item in EXPERIENCE_CATALOG if item["id"] in selected_ids]
    deduped.sort(key=lambda item: item["order"])
    return deduped[:8]


def _build_ats_coverage(selected: list[dict[str, Any]], top8: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coverage: list[dict[str, Any]] = []
    for keyword_entry in top8:
        keyword = str(keyword_entry.get("keyword") or "").strip()
        target = _normalize(str(keyword_entry.get("experiencia_alvo") or ""))
        match_index = 0
        bullet_index = 0
        for index, experience in enumerate(selected):
            if _normalize(experience["company"]) in target or _normalize(experience["role"]) in target:
                match_index = index
                break
        bullet_index = _best_bullet_index(selected[match_index]["bullets"], keyword)
        coverage.append(
            {
                "keyword": keyword,
                "experience_index": match_index,
                "experience_role": selected[match_index]["role"],
                "bullet_index": bullet_index,
                "coverage_mode": "exact",
                "defensible_evidence": selected[match_index]["bullets"][bullet_index],
            }
        )
    return coverage


def _best_bullet_index(bullets: list[str], keyword: str) -> int:
    keyword_norm = _normalize(keyword)
    for index, bullet in enumerate(bullets):
        if keyword_norm in _normalize(bullet):
            return index
    return 0


def _build_summary(fit_map: dict[str, Any]) -> str:
    cargo = str(fit_map.get("cargo") or "a vaga")
    stories = fit_map.get("historias_selecionadas", {}) if isinstance(fit_map.get("historias_selecionadas"), dict) else {}
    principal = stories.get("principal") if isinstance(stories.get("principal"), dict) else {}
    secondary = stories.get("secundaria") if isinstance(stories.get("secundaria"), dict) else {}
    primary_result = str(principal.get("resultado") or "escala operacional e comercial")
    secondary_result = str(secondary.get("resultado") or "melhoria de conversão e eficiência comercial")
    return (
        "Engenheiro químico com mais de 20 anos em operações, planejamento comercial e inteligência de negócios. "
        f"Na trajetória recente, entreguei {primary_result}. "
        f"Também liderei frentes que geraram {secondary_result}. "
        f"Busco posição de {cargo} conectando canais, pricing, dados e execução."
    )


def _persona_name(fit_map: dict[str, Any]) -> str:
    cargo = _normalize(str(fit_map.get("cargo") or ""))
    if "growth" in cargo or "negocio" in cargo:
        return "growth_operacional"
    return "operacoes_planejamento"


def _output_name(fit_map: dict[str, Any]) -> str:
    cargo = _slug(str(fit_map.get("cargo") or "vaga"))
    empresa = _slug(str(fit_map.get("empresa") or "empresa"))
    suffix = "_en" if str(fit_map.get("idioma") or "").strip().lower().startswith("en") else ""
    return f"felipe_armel_cv_{cargo}_{empresa}{suffix}.docx"


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _slug(text: str) -> str:
    slug = _normalize(text)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or "arquivo"
