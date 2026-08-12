from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unicodedata
import warnings
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, ROOT
from career.services import applications_v2 as applications_v2_service
from career.services import cv_positioning
from career.services import derived_context as derived_context_service
from career.cells.capabilities import (
    canonical_node_executable,
    canonical_subprocess_environment,
)
from career.services import fit_map as fit_map_service
from career.services import provenance as provenance_service
from career.services.application_context import ApplicationPaths
from career.utils import (
    ValidationFailure,
    ensure,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)


PROFILE_FACTS_PATH = (
    ROOT / ".agents/skills/career-system/references/perfil_restricoes.md"
)
SELF_KNOWLEDGE_PATH = (
    ROOT / ".agents/skills/career-system/references/autoconhecimento.md"
)
CV_FACTS_PATH = (
    ROOT / ".agents/skills/career-system/references/candidate_cv_facts.json"
)


def load_canonical_cv_facts() -> dict[str, Any]:
    """Load the revisioned structured source for every renderer-facing fact."""
    payload = read_json(CV_FACTS_PATH)
    required = {"schema_version", "candidate", "experiences", "education", "languages", "stack", "localized_render_values"}
    if not isinstance(payload, dict) or required - set(payload):
        raise ValidationFailure("canonical CV facts schema is incomplete")
    return payload


def _facts_experiences() -> list[dict[str, Any]]:
    return list(load_canonical_cv_facts()["experiences"])


def _facts_education(language: str) -> list[str]:
    return list(load_canonical_cv_facts()["education"][language])


def _facts_languages(language: str) -> list[str]:
    return list(load_canonical_cv_facts()["languages"][language])


def _facts_stack(language: str = "pt-BR") -> str:
    stack = load_canonical_cv_facts()["stack"]
    if isinstance(stack, dict):
        return str(stack.get(language) or stack.get("pt-BR") or "")
    return str(stack)


CV_CONTENT_PATH = CAREER_STATE / "cv_content.json"

ENQUADRAMENTO_FILENAME = "enquadramento.json"


def _require_enquadramento(app_dir: Path, fit_map: dict[str, Any]) -> dict:
    """GATE OBRIGATÓRIO — enquadramento-posicionamento.

    Exige enquadramento.json no app_dir (ou .career-state) antes de construir o CV.
    Raises ValidationFailure se ausente, malformado ou sem fingerprint da vaga.
    """
    candidates = [
        app_dir / ENQUADRAMENTO_FILENAME,
        CAREER_STATE / ENQUADRAMENTO_FILENAME,
    ]
    chosen = None
    seen: set[str] = set()
    for cand in candidates:
        key = str(cand.resolve())
        if key in seen:
            continue
        seen.add(key)
        if cand.is_file():
            chosen = cand
            break
    if chosen is None:
        raise ValidationFailure(
            f"enquadramento_posicionamento_required: artefato {ENQUADRAMENTO_FILENAME} "
            "ausente. Execute a skill enquadramento-posicionamento e grave "
            "enquadramento.json no app dir antes de construir o CV."
        )
    data = read_json(chosen)
    if not isinstance(data, dict):
        raise ValidationFailure(
            "enquadramento_posicionamento_malformed: enquadramento.json deve ser um objeto"
        )
    experiencias = data.get("experiencias")
    if not isinstance(experiencias, list) or not experiencias:
        raise ValidationFailure(
            "enquadramento_posicionamento_empty: enquadramento.json precisa listar experiencias enquadradas"
        )
    if not any(data.get(key) for key in ("job_fingerprint", "fingerprint")):
        raise ValidationFailure(
            "enquadramento_posicionamento_stale: enquadramento.json precisa de job_fingerprint "
            "para provar que corresponde à vaga atual."
        )
    return data


FIT_MAP_PATH = CAREER_STATE / "fit_map.json"


def configure_paths(*, cv_content_path: Path | None = None, fit_map_path: Path | None = None) -> None:
    warnings.warn(
        "configure_paths is a deprecated legacy adapter; pass ApplicationPaths instead",
        DeprecationWarning,
        stacklevel=2,
    )
    global CV_CONTENT_PATH
    global FIT_MAP_PATH
    if cv_content_path is not None:
        CV_CONTENT_PATH = cv_content_path
    if fit_map_path is not None:
        FIT_MAP_PATH = fit_map_path


BULLET2_POLICY_BY_FAMILY: dict[str, dict[str, Any]] = {
    "project_management": {
        "signals": {
            "projeto",
            "projetos",
            "programa",
            "implantacao",
            "implantação",
            "pm",
            "pmo",
            "rollout",
        },
        "focus": "coordenação, governança e execução transversal",
    },
    "operations": {
        "signals": {
            "operacoes",
            "operações",
            "logistica",
            "logística",
            "supply",
            "last mile",
            "fulfillment",
        },
        "focus": "ritmo operacional, indicadores e eficiência",
    },
    "planning_sop_capacity": {
        "signals": {
            "planejamento",
            "s&op",
            "capacity",
            "forecast",
            "demanda",
            "supply planning",
        },
        "focus": "cenários, capacidade e governança de planejamento",
    },
    "cx_saas_operations": {
        "signals": {
            "cx",
            "customer success",
            "customer service",
            "suporte",
            "atendimento",
            "saas",
        },
        "focus": "jornada, automação e integração de atendimento",
    },
    "product_revenue_business_ops": {
        "signals": {
            "product",
            "produto",
            "revenue",
            "growth",
            "pricing",
            "business ops",
        },
        "focus": "dados, priorização e performance de negócio",
    },
}


_POSITIONING_CASES_EN = {
    "equilibrar demanda, capacidade, supply, custos, estoques e nivel de servico":
        "balancing demand, capacity, supply, costs, inventory, and service levels",
    "melhorar frota, transporte, distribuicao, cobertura, roteirizacao e nivel de servico":
        "improving fleet, transportation, distribution, coverage, routing, and service levels",
    "gerenciar compras, sourcing, materiais, estoque, armazenagem e abastecimento":
        "managing procurement, sourcing, materials, inventory, warehousing, and replenishment",
    "redesenhar operacoes para reduzir opex, desperdicios, tempo e custo unitario":
        "redesigning operations to reduce OPEX, waste, cycle time, and unit cost",
    "melhorar atendimento, sla, csat, canais, produtividade e custo do suporte":
        "improving service, SLA, CSAT, channels, productivity, and support cost",
    "estruturar onboarding, retencao, segmentacao, churn, nps e evolucao da carteira":
        "building onboarding, retention, segmentation, churn, NPS, and portfolio growth",
    "criar indicadores, dashboards, modelos analiticos e decisoes orientadas por dados":
        "building metrics, dashboards, analytical models, and data-driven decisions",
    "melhorar funil, conversao, produtividade comercial, aquisicao e execucao de crescimento":
        "improving funnels, conversion, commercial productivity, acquisition, and growth execution",
    "montar, reorganizar ou escalar times, estruturas, liderancas e modelos de gestao":
        "building, reorganizing, and scaling teams, structures, leaders, and management models",
    "melhorar producao, produtividade, conformidade, padronizacao e sistemas da qualidade":
        "improving production, productivity, compliance, standardization, and quality systems",
    "liderar a operacao integrando pessoas, tecnologia, custos e crescimento":
        "leading operations by integrating people, technology, costs, and growth",
    "transformar objetivos estrategicos em planos, analises, prioridades e execucao multifuncional":
        "turning strategic objectives into plans, analysis, priorities, and cross-functional execution",
    "conectar operacao, clientes, dados e produto para organizar roadmap e resolver problemas recorrentes":
        "connecting operations, customers, data, and product to shape roadmaps and solve recurring problems",
    "gerenciar oferta, parceiros, prestadores, sellers, entregadores ou outros lados de uma plataforma":
        "managing supply, partners, providers, sellers, couriers, and other sides of a platform",
    "automatizar processos, implantar plataformas, integrar dados e aplicar ia a operacao":
        "automating processes, implementing platforms, integrating data, and applying AI to operations",
    "otimizar preco, margem, incentivos, rentabilidade, capacidade e regras comerciais":
        "optimizing pricing, margin, incentives, profitability, capacity, and commercial rules",
    "gerenciar portfolio de projetos, cadencia, responsaveis, metas, prazos e captura de beneficios":
        "managing project portfolios, cadence, owners, targets, timelines, and benefit capture",
    "implantar operacoes em novas cidades, mercados, paises ou linhas de negocio":
        "launching operations in new cities, markets, countries, or business lines",
    "gerenciar orcamento e usar alavancas operacionais para melhorar margem, ebitda ou custos":
        "managing budgets and using operational levers to improve margin, EBITDA, and costs",
    "apoiar ceo/diretoria, organizar decisoes, metas, ritos, cenarios e coordenacao transversal":
        "supporting CEOs and executives through decisions, targets, operating cadences, scenarios, and cross-functional coordination",
}


def build_current_cv_content(path: Path = CV_CONTENT_PATH) -> dict[str, Any]:
    active = derived_context_service.resolve_active_job_context()
    _ensure_fit_map_matches_active(active)
    fit_map = read_json(FIT_MAP_PATH)
    payload = _build_cv_payload(active, fit_map, source_fit_map=str(FIT_MAP_PATH))
    write_json(path, payload)
    validate_cv_content(path)
    return payload


def build_cv_content(
    application_paths: ApplicationPaths,
    fit_map_path: Path,
    candidate_facts_revision: str,
) -> dict[str, Any]:
    """Build CV content from explicit application paths without global adapters."""
    resolved_fit_map = Path(fit_map_path).resolve()
    for label, path in (
        ("job description", application_paths.job_description.resolve()),
        ("FIT_MAP", resolved_fit_map),
        ("CV content", application_paths.cv_content.resolve()),
    ):
        try:
            path.relative_to(application_paths.app_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"{label} must stay within its application directory") from exc
    ensure(application_paths.job_description.is_file(), "application_job_description_missing")
    ensure(resolved_fit_map.is_file(), "application_fit_map_missing")
    identity = read_json(application_paths.identity) if application_paths.identity.is_file() else {}
    active = derived_context_service.ActiveJobContext(
        job_description_path=application_paths.job_description.resolve(),
        fingerprint=sha256_file(application_paths.job_description),
        company=str(identity.get("company") or ""),
        role=str(identity.get("role") or ""),
        source_type=str(identity.get("source_type") or "application_source"),
        source_id=str(identity.get("source_id") or "") or None,
    )
    fit_map = read_json(resolved_fit_map)
    fit_map_service.validate_application_fit_map(
        fit_map,
        application_paths=application_paths,
        expected_candidate_facts_revision=candidate_facts_revision,
    )
    # GATE OBRIGATÓRIO — enquadramento-posicionamento (não pulável)
    _require_enquadramento(application_paths.app_dir, fit_map)
    payload = _build_cv_payload(
        active,
        fit_map,
        source_fit_map=str(resolved_fit_map),
        candidate_facts_revision=candidate_facts_revision,
        application_id=application_paths.application_id,
        language=_application_cv_language(application_paths, fit_map),
    )
    return payload


def render_cv(content_path: Path, output_dir: Path, application_id: str) -> Path:
    """Render one immutable application CV without consulting global state."""
    content_path = Path(content_path).resolve()
    output_dir = Path(output_dir).resolve()
    if not content_path.is_file():
        raise ValueError("cv_content_missing")
    payload = read_json(content_path)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if metadata.get("application_id") != application_id:
        raise ValueError("cv_content_application_id_mismatch")
    output_name = str(payload.get("output_name") or "").strip()
    if not output_name or Path(output_name).name != output_name:
        raise ValueError("cv_content_output_name_invalid")
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(canonical_node_executable()),
        str((ROOT / "scripts/docx/generate_custom_cv.js").resolve()),
        "--content",
        str(content_path),
        "--output-dir",
        str(output_dir),
        "--application-id",
        application_id,
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=canonical_subprocess_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            "cv_renderer_failed:\n"
            f"stdout={result.stdout}\n"
            f"stderr={result.stderr}"
        )
    artifact = output_dir / output_name
    if not artifact.is_file():
        raise RuntimeError("cv_renderer_did_not_create_artifact")
    return artifact


def _build_cv_payload(
    active: derived_context_service.ActiveJobContext,
    fit_map: dict[str, Any],
    *,
    source_fit_map: str,
    candidate_facts_revision: str | None = None,
    application_id: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    job_family = _infer_job_family(fit_map)
    selected = _select_experiences(fit_map)
    ensure(4 <= len(selected) <= 8, "cv_content_requires_between_4_and_8_experiences")
    is_en = (language or _cv_language(fit_map)) == "en"
    selected_with_bullets = [_materialize_experience(entry, job_family, language="en" if is_en else "pt-BR") for entry in selected]
    top8 = _top8_keywords(fit_map)
    coverage = _build_ats_coverage(selected_with_bullets, top8)
    summary_inputs = bounded_summary_inputs(fit_map)
    positioning = cv_positioning.select_positioning(
        fit_map, active.job_description_path.read_text(encoding="utf-8")
    )
    summary_text, summary_support = _build_summary(
        selected_with_bullets,
        summary_inputs,
        positioning=positioning,
        language="en" if is_en else "pt-BR",
    )
    education_list = _facts_education("en" if is_en else "pt-BR")
    candidate = _candidate_contact_facts()
    payload = {
        "metadata": {
            "kind": "cv_content",
            "created_at": utc_now_iso(),
            "job_fingerprint": active.fingerprint,
            "job_description_path": derived_context_service._relative(active.job_description_path),
            "candidate_facts_revision": candidate_facts_revision,
            "application_id": application_id,
            "cargo": fit_map.get("cargo"),
            "empresa": fit_map.get("empresa"),
            "source_fit_map": source_fit_map,
            "job_family": job_family,
            "language": "en" if is_en else "pt-BR",
            "summary_inputs": summary_inputs,
            "summary_inputs_sha256": hashlib.sha256(
                json.dumps(summary_inputs, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "source_fit_map_sha256": sha256_file(Path(source_fit_map)) if Path(source_fit_map).is_file() else "",
        },
        "output_name": _output_name(fit_map, active=active, language="en" if is_en else "pt-BR"),
        "candidate": candidate,
        "mode": "concise",
        "persona": _persona_name(fit_map),
        "summary": summary_text,
        "resumo": summary_text,
        "experiences": [
            {
                "experience_id": exp["id"],
                "evidence_id": _evidence_id(exp["id"], "experience"),
                "role": exp["role"],
                "company": exp["company"],
                "period": _sanitize_punctuation(str(exp["period"])),
                "bullets": [
                    {
                        "text": bullet,
                        "experience_id": exp["id"],
                        "evidence_id": _evidence_id(exp["id"], f"bullet:{index}"),
                    }
                    for index, bullet in enumerate(exp["bullets"])
                ],
            }
            for exp in selected_with_bullets
        ],
        "experiencias": [
            {
                "experience_id": exp["id"],
                "evidence_id": _evidence_id(exp["id"], "experience"),
                "cargo": exp["role"],
                "empresa": exp["company"],
                "periodo": _sanitize_punctuation(str(exp["period"])),
                "bullets": [bullet for bullet in exp["bullets"]],
            }
            for exp in selected_with_bullets
        ],
        "education": list(education_list),
        "formacao": _facts_education("pt-BR"),
        "languages": _facts_languages("en" if is_en else "pt-BR"),
        "idiomas": _facts_languages("pt-BR"),
        "stack": _facts_stack("en" if is_en else "pt-BR"),
        "ats_keyword_coverage": coverage,
        "summary_support": summary_support,
        "positioning": positioning,
    }
    if positioning is not None:
        payload["positioning_support"] = {
            "catalog_entry_id": positioning["catalog_entry_id"],
            "caso": positioning["caso"],
            "evidence_id": "",
        }
    _attach_canonical_provenance(payload)
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
    status = fit_map_service.status(fit_map_path=FIT_MAP_PATH, job_description_path=active.job_description_path)
    ensure(status.get("fit_map", {}).get("matches_active_job"), "fit_map_stale_for_active_job")


def _top8_keywords(fit_map: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [item for item in fit_map.get("keywords_habilidade_ats", []) if isinstance(item, dict)]
    entries.sort(key=lambda item: int(item.get("prioridade") or 999))
    return entries[:8]


def _experience_relevance_score(
    entry: dict[str, Any], keywords: list[dict[str, Any]], job_family: str
) -> int:
    focus_terms = {_normalize(str(term)) for term in entry.get("focus_terms", []) if str(term).strip()}
    keyword_terms = {_normalize(str(item.get("keyword") or "")) for item in keywords}
    keyword_terms.discard("")
    score = len(focus_terms & keyword_terms)
    # NOTE (regra do usuário 2026-08-10): o bônus de família por signal era ingênuo —
    # premiava presença de termo genérico (ex.: "logística" em focus_terms da Expedição)
    # e empurrava experiência antiga de baixa aderência à frente da mais recente.
    # O fallback deve priorizar keyword-relevance real e, em empate, a experiência MAIS
    # recente não selecionada (regra do usuário). Remover o bônus devolve o ranking ao
    # desempate por cronologia (entry["order"] menor = mais recente primeiro).
    return score


def _select_experiences(fit_map: dict[str, Any]) -> list[dict[str, Any]]:
    selected_ids: list[str] = []
    story_companies = []
    stories = fit_map.get("historias_selecionadas", {}) if isinstance(fit_map.get("historias_selecionadas"), dict) else {}
    for key in ("principal", "secundaria", "terceira"):
        story = stories.get(key)
        if isinstance(story, dict):
            story_companies.append(str(story.get("empresa") or ""))
    top8_keywords = _top8_keywords(fit_map)
    targets = [str(item.get("experiencia_alvo") or "") for item in top8_keywords]
    for entry in _facts_experiences():
        company_norm = _normalize(entry["company"])
        role_norm = _normalize(entry["role"])
        if any(company_norm in _normalize(company) for company in story_companies if company):
            selected_ids.append(entry["id"])
            continue
        if any(company_norm in _normalize(target) or role_norm in _normalize(target) for target in targets):
            selected_ids.append(entry["id"])
    fallback_priority = load_canonical_cv_facts()["selectors"]["fallback_experience_priority"]
    fallback_rank = {item_id: index for index, item_id in enumerate(fallback_priority)}
    job_family = _infer_job_family(fit_map)
    remaining = [entry for entry in _facts_experiences() if entry["id"] not in selected_ids]
    remaining.sort(
        key=lambda entry: (
            -_experience_relevance_score(entry, top8_keywords, job_family),
            entry["order"],
            fallback_rank.get(entry["id"], len(fallback_rank)),
        )
    )
    for entry in remaining:
        selected_ids.append(entry["id"])
        if len(selected_ids) >= 5:
            break
    deduped = [item for item in _facts_experiences() if item["id"] in selected_ids]
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
                "experience_id": selected[match_index]["id"],
                "evidence_id": _evidence_id(
                    selected[match_index]["id"], f"bullet:{bullet_index}"
                ),
                "experience_role": selected[match_index]["role"],
                "bullet_index": bullet_index,
                "coverage_mode": "exact",
                "defensible_evidence": selected[match_index]["bullets"][bullet_index],
            }
        )
    return coverage


def _infer_job_family(fit_map: dict[str, Any]) -> str:
    tokens: list[str] = []
    for field in ("cargo", "empresa", "dor_central"):
        value = fit_map.get(field)
        if isinstance(value, str):
            tokens.append(value)
    for item in fit_map.get("keywords_habilidade_ats", []):
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("keyword") or "").strip()
        if keyword:
            tokens.append(keyword)
    haystack = " ".join(_normalize(token) for token in tokens)
    for family, payload in BULLET2_POLICY_BY_FAMILY.items():
        for signal in payload["signals"]:
            if _normalize(signal) in haystack:
                return family
    return "operations"


def _sanitize_punctuation(text: str) -> str:
    """Remove travessão '—' (regra do usuário 2026-08): deixa o texto com cara de IA.

    Substitui por pontuação de acordo com o contexto:
    - padrão IA ' — o que permitiu/viabilizou/...' -> ', o que ...' (vírgula)
    - intervalo de datas 'maio/2024 — fev/2026' -> 'maio/2024 - fev/2026' (hífen)
    - demais ' — ' -> ' - ' (hífen)
    """
    if not text:
        return text
    out = re.sub(r"\s+—\s+o que\b", ", o que", text)
    out = re.sub(r"\s+—\s+", " - ", out)
    return out


def _trim_leverage_to_mechanism(leverage: str, result: str) -> str:
    """Remove from the leverage bullet any result clauses that duplicate the result bullet.

    The leverage bullet (B2) should focus on the mechanism (how the result happened), not
    repeat the outcomes that already appear in the result bullet (B3). This trims the leverage
    text at the first result transition (e.g. "from X to Y") that also appears in the result
    bullet, cutting back to the start of the result clause that introduces it.

    Returns the trimmed leverage text unchanged if no duplication is detected.
    """
    if not leverage or not result:
        return leverage
    _result_verbs = r"(?:reduced|raised|improved|cut|increased|lowered|doubled|generated|expanded|boosted|eliminated|recovered|scaled|grew|saved)"
    _trans = r"(?:from|de)\s+[\d.,%R$]+\s+(?:to|para)\s+[\d.,%R$]+"
    trans_matches = list(re.finditer(_trans, leverage, flags=re.IGNORECASE))
    if not trans_matches:
        return leverage
    first_trans = trans_matches[0]
    prefix = leverage[: first_trans.start()]
    verb_matches = list(re.finditer(r"\b" + _result_verbs + r"\b", prefix, flags=re.IGNORECASE))
    if verb_matches:
        clause_start = verb_matches[-1].start()
        after_verb = leverage[clause_start:]
        if re.search(_trans, after_verb, flags=re.IGNORECASE):
            cut = clause_start
        else:
            cut = first_trans.start()
    else:
        cut = first_trans.start()
    trimmed = leverage[:cut].rstrip()
    trimmed = re.sub(r"[,\s]+$", "", trimmed)
    trimmed = re.sub(r"\s*-\s*which\s+allowed.*$", "", trimmed, flags=re.IGNORECASE)
    trimmed = re.sub(r"\s*\.\s*this\s+.*$", "", trimmed, flags=re.IGNORECASE)
    trimmed = re.sub(r"\s*,\s*and\s*$", "", trimmed, flags=re.IGNORECASE)
    trimmed = re.sub(r"\s+and\s*$", "", trimmed, flags=re.IGNORECASE)
    trimmed = trimmed.rstrip()
    if not trimmed.endswith("."):
        trimmed += "."
    return trimmed


def _materialize_experience(entry: dict[str, Any], job_family: str, *, language: str = "pt-BR") -> dict[str, Any]:
    if language == "en":
        role, scope, leverage, result = load_canonical_cv_facts()["localized_render_values"]["en"][entry["id"]]
        leverage = _trim_leverage_to_mechanism(leverage, result)
        return {
            **entry,
            "role": role,
            "period": _english_period(str(entry["period"])),
            "scope_bullet": _sanitize_punctuation(scope),
            "result_bullet": _sanitize_punctuation(result),
            "bullets": [_sanitize_punctuation(b) for b in [scope, leverage, result]],
            "job_family": job_family,
        }
    leverage = entry.get("leverage") if isinstance(entry.get("leverage"), dict) else {}
    bullet2 = str(leverage.get(job_family) or leverage.get("default") or "").strip()
    result_bullet = str(entry.get("result_bullet") or "").strip()
    bullet2 = _trim_leverage_to_mechanism(bullet2, result_bullet)
    bullets = [
        str(entry.get("scope_bullet") or "").strip(),
        bullet2,
        result_bullet,
    ]
    return {
        **entry,
        "bullets": [_sanitize_punctuation(b) for b in bullets],
        "job_family": job_family,
    }


def _best_bullet_index(bullets: list[str], keyword: str) -> int:
    keyword_norm = _normalize(keyword)
    for index, bullet in enumerate(bullets):
        if keyword_norm in _normalize(bullet):
            return index
    return 0


def _build_summary(
    selected: list[dict[str, Any]],
    fit_map: dict[str, Any],
    *,
    positioning: dict[str, Any] | None = None,
    language: str = "pt-BR",
) -> tuple[str, list[dict[str, Any]]]:
    cargo = str(fit_map.get("cargo") or "a vaga")
    support_pairs = _summary_support_pairs(selected, fit_map, language=language)
    supports = [
        {
            "summary_fragment": fragment,
            "experience_index": exp_index,
            "experience_id": selected[exp_index]["id"],
            "evidence_id": _evidence_id(
                selected[exp_index]["id"], f"bullet:{bullet_index}"
            ),
            "experience_role": selected[exp_index]["role"],
            "experience_company": selected[exp_index]["company"],
            "bullet_index": bullet_index,
            "defensible_evidence": selected[exp_index]["bullets"][bullet_index],
        }
        for fragment, exp_index, bullet_index in support_pairs
    ]
    if language == "pt-BR" and positioning is not None:
        opening = _compose_positioning_opening(fit_map)
        proof = f"Na trajetória recente, alcancei {supports[0]['summary_fragment']}. Também conduzi {supports[1]['summary_fragment']}."
        case = str(positioning["caso"]).strip().rstrip(".")
        used_terms = cv_positioning.normalize_tokens(f"{opening} {proof}")
        direction = ""
        if positioning.get("summary_direction_eligible") and not cv_positioning.normalize_tokens(case).issubset(used_terms):
            direction = f"Busco uma posição em que eu possa {case[:1].lower()}{case[1:]}."
        summary = " ".join(part for part in (opening, proof, direction) if part)
    else:
        profile = load_canonical_cv_facts()["summary_profiles"][language]
        opening = profile.get("opening") or _summary_opening(fit_map)
        summary = str(profile["template"]).format(
            opening=opening,
            first=supports[0]["summary_fragment"],
            second=supports[1]["summary_fragment"],
            cargo=cargo,
        )
        if language == "en" and positioning is not None and positioning.get("summary_direction_eligible"):
            case_en = _positioning_case_for_summary(positioning, language)
            if case_en:
                summary = (
                    f"{opening} I have delivered {supports[0]['summary_fragment']}. "
                    f"I also led initiatives that generated {supports[1]['summary_fragment']}. "
                    f"I am pursuing a {cargo} role focused on {case_en}."
                )
    return summary, supports


def _positioning_case_for_summary(positioning: dict[str, Any], language: str) -> str:
    case = str(positioning.get("caso") or "").strip().rstrip(".")
    if language != "en":
        return case
    return _POSITIONING_CASES_EN.get(_normalize(case), "")


def _summary_opening(fit_map: dict[str, Any]) -> str:
    text_parts = [
        str(fit_map.get("cargo") or ""),
        str(fit_map.get("empresa") or ""),
        str(fit_map.get("dor_central") or ""),
    ]
    for field in ("keywords_vaga", "competencias_vaga"):
        values = fit_map.get(field) or []
        if isinstance(values, list):
            text_parts.extend(str(item) for item in values)
    normalized = _normalize(" ".join(part for part in text_parts if part))
    profile = load_canonical_cv_facts()["summary_profiles"]["pt-BR"]
    engineering_signals = profile["engineering_signals"]
    if any(_normalize(signal) in normalized for signal in engineering_signals):
        return str(profile["engineering_opening"])
    return str(profile["default_opening"])


def _compose_positioning_opening(fit_map: dict[str, Any]) -> str:
    structured_context = cv_positioning.normalize_tokens(
        " ".join(
            json.dumps(fit_map.get(field) or "", ensure_ascii=False)
            for field in ("keywords_habilidade_ats", "keywords_vaga", "competencias_vaga")
        )
    )
    if structured_context & {"ai", "agentforce", "data", "adocao"}:
        focus = "transformação digital, adoção de tecnologia e geração de valor para clientes"
    elif structured_context & {"planejamento", "sop", "forecast", "demanda"}:
        focus = "planejamento integrado e excelência operacional"
    else:
        focus = "operações, planejamento e transformação de negócios"
    base = "Atuo há mais de 20 anos em operações, planejamento e transformação de negócios"
    return f"{base}." if focus == "operações, planejamento e transformação de negócios" else f"{base}, com foco em {focus}."


def _summary_support_pairs(
    selected: list[dict[str, Any]], fit_map: dict[str, Any], *, language: str = "pt-BR"
) -> list[tuple[str, int, int]]:
    desired = load_canonical_cv_facts()["selectors"]["summary_priority"]
    summary_fragments = load_canonical_cv_facts()["summary_fragments"][language]
    by_id = {entry["id"]: index for index, entry in enumerate(selected)}
    story_companies: list[str] = []
    stories = fit_map.get("historias_selecionadas")
    if isinstance(stories, dict):
        for key in ("principal", "secundaria", "terceira"):
            story = stories.get(key)
            if isinstance(story, dict) and str(story.get("empresa") or "").strip():
                story_companies.append(_normalize(str(story["empresa"])))
    story_priority: list[str] = []
    for company in story_companies:
        story_tokens = cv_positioning.normalize_tokens(company)
        candidates = [
            entry
            for entry in selected
            if entry["id"] in summary_fragments
            and story_tokens
            & cv_positioning.normalize_tokens(
                f"{entry.get('company', '')} {entry.get('role', '')}"
            )
        ]
        matched = max(
            candidates,
            key=lambda entry: len(
                story_tokens
                & cv_positioning.normalize_tokens(
                    f"{entry.get('company', '')} {entry.get('role', '')}"
                )
            ),
            default=None,
        )
        if matched is not None:
            story_priority.append(matched["id"])
    pairs: list[tuple[str, int, int]] = []
    for experience_id in [*story_priority, *desired]:
        if experience_id not in by_id:
            continue
        if any(existing[1] == by_id[experience_id] for existing in pairs):
            continue
        if experience_id not in summary_fragments:
            continue
        fragment, bullet_index = summary_fragments[experience_id]
        pairs.append((fragment, by_id[experience_id], bullet_index))
        if len(pairs) == 2:
            break
    ensure(len(pairs) >= 2, "cv_summary_requires_two_supported_experiences")
    return pairs


def _persona_name(fit_map: dict[str, Any]) -> str:
    cargo = _normalize(str(fit_map.get("cargo") or ""))
    if "growth" in cargo or "negocio" in cargo:
        return "growth_operacional"
    return "operacoes_planejamento"


def _output_name(
    fit_map: dict[str, Any], *, active: Any | None = None, language: str | None = None
) -> str:
    # Keep the artifact name stable across reruns by preferring the original
    # intake identity instead of translated/adapted labels inside the FIT_MAP.
    cargo_source = str(getattr(active, "role", "") or fit_map.get("cargo") or "vaga")
    empresa_source = str(getattr(active, "company", "") or fit_map.get("empresa") or "empresa")
    cargo = _slug(cargo_source)
    empresa = _slug(empresa_source)
    suffix = "_en" if (language or _cv_language(fit_map)) == "en" else ""
    return f"{load_canonical_cv_facts()['filename_slug']}_{cargo}_{empresa}{suffix}.docx"


def _cv_language(fit_map: dict[str, Any]) -> str:
    return "en" if str(fit_map.get("idioma") or "").strip().casefold().startswith("en") else "pt-BR"


def _application_cv_language(application_paths: ApplicationPaths, fit_map: dict[str, Any]) -> str:
    """Read the persisted normalized language; never infer it from marker words here."""
    for key in ("required_cv_language", "idioma", "language"):
        language = str(fit_map.get(key) or "").strip()
        if language in {"pt-BR", "en"}:
            return language
    extract_path = application_paths.derived_dir / "job_extract.json"
    if extract_path.is_file():
        extract = read_json(extract_path)
        language = str((extract.get("job_identity") or {}).get("language") or "").strip()
        if language in {"pt-BR", "en"}:
            return language
    raise ValidationFailure("application CV language is missing from normalized inputs")


def _candidate_contact_facts() -> dict[str, str]:
    """Extract immutable renderer-facing identity facts from the canonical profile."""
    values = dict(load_canonical_cv_facts()["candidate"])
    if not all(values.values()):
        raise ValidationFailure("canonical candidate contact facts are incomplete")
    return values


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _slug(text: str) -> str:
    slug = _normalize(text)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or "arquivo"


def _evidence_id(experience_id: str, claim: str) -> str:
    """Legacy placeholder replaced by canonical binding during payload assembly."""
    return f"unbound:{experience_id}:{claim}"


def _attach_canonical_provenance(payload: dict[str, Any]) -> None:
    """Bind every renderer-facing fact to immutable candidate source hashes."""
    revision = str(payload["metadata"].get("candidate_facts_revision") or "")
    sources = {
        "cv_facts": CV_FACTS_PATH,
        "profile": PROFILE_FACTS_PATH,
        "self_knowledge": SELF_KNOWLEDGE_PATH,
    }
    if payload.get("positioning") is not None:
        sources["positioning_catalog"] = cv_positioning.CATALOG_PATH
    catalog = {
        name: {"path": str(path), "sha256": sha256_file(path)}
        for name, path in sources.items()
    }
    source_bytes = {
        name: path.read_bytes()
        for name, path in sources.items()
    }
    source_text = {name: _normalize(raw.decode("utf-8")) for name, raw in source_bytes.items()}

    def value_hash(value: Any) -> str:
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()

    def evidence_id(source: str, kind: str, locator: str, value: Any) -> str:
        return hashlib.sha256(
            f"{revision}\0{source}\0{kind}\0{locator}\0{value_hash(value)}".encode("utf-8")
        ).hexdigest()

    evidence: dict[str, dict[str, str]] = {}

    def bind(source: str, kind: str, locator: str, value: Any) -> str:
        # A claim can only be published when its locator resolves in the
        # revision-pinned canonical source.  The opaque ID protects callers
        # from treating labels as proof while preserving auditability.
        if locator.startswith("catalog-entry:"):
            if source != "positioning_catalog":
                raise ValidationFailure("canonical catalog evidence source is invalid")
        elif _normalize(locator.split("::", 1)[0]) not in source_text[source]:
            raise ValidationFailure(f"canonical evidence locator is absent: {source}/{kind}")
        item_id = evidence_id(source, kind, locator, value)
        excerpt = _source_excerpt(source_bytes[source].decode("utf-8"), locator)
        evidence[item_id] = {
            "source": source,
            "kind": kind,
            "locator": locator,
            "source_excerpt": excerpt,
            "source_excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "source_value": excerpt,
            "source_value_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "value_sha256": value_hash(value),
        }
        return item_id

    for experience in payload["experiences"]:
        experience_id = str(experience["experience_id"])
        locator = _experience_source_locator(experience_id)
        experience["evidence_id"] = bind("cv_facts", "experience", locator, experience_id)
        experience["provenance"] = {
            "role": bind("cv_facts", "experience_role", locator, experience["role"]),
            "company": bind("cv_facts", "experience_company", locator, experience["company"]),
            "period": bind("cv_facts", "experience_period", locator, experience["period"]),
        }
        for index, bullet in enumerate(experience["bullets"]):
            bullet["evidence_id"] = bind(
                "cv_facts", "experience_bullet", f"{locator}::{index}", bullet["text"]
            )
    for experience in payload["experiencias"]:
        experience_id = str(experience["experience_id"])
        locator = _experience_source_locator(experience_id)
        experience["evidence_id"] = bind("cv_facts", "experience_pt", locator, experience_id)
        experience["provenance"] = {
            "cargo": bind("cv_facts", "experience_role_pt", locator, experience["cargo"]),
            "empresa": bind("cv_facts", "experience_company_pt", locator, experience["empresa"]),
            "periodo": bind("cv_facts", "experience_period_pt", locator, experience["periodo"]),
            "bullets": [
                bind("cv_facts", "experience_bullet_pt", f"{locator}::{index}", bullet)
                for index, bullet in enumerate(experience["bullets"])
            ],
        }
    for mapping in payload["ats_keyword_coverage"]:
        experience_id = str(mapping["experience_id"])
        mapping["evidence_id"] = bind(
            "self_knowledge",
            "ats_evidence",
            _experience_source_locator(experience_id),
            mapping["defensible_evidence"],
        )
    for support in payload["summary_support"]:
        experience_id = str(support["experience_id"])
        support["evidence_id"] = bind(
            "self_knowledge",
            "summary_evidence",
            _experience_source_locator(experience_id),
            support["defensible_evidence"],
        )
    positioning = payload.get("positioning")
    if isinstance(positioning, dict):
        support = payload.get("positioning_support")
        if not isinstance(support, dict):
            raise ValidationFailure("positioning support is missing")
        item_id = bind(
            "positioning_catalog",
            "positioning_catalog",
            f"catalog-entry:{int(positioning['catalog_entry_id'])}",
            positioning["caso"],
        )
        support["evidence_id"] = item_id
    education_evidence = []
    for index, _ in enumerate(payload["education"]):
        source, locator = _education_source_locator(index)
        education_evidence.append(bind(source, "education", locator, payload["education"][index]))
    payload["claim_provenance"] = {
        "summary": [item["evidence_id"] for item in payload["summary_support"]],
        "education": education_evidence,
        "languages": [bind("cv_facts", "language", "languages", value) for value in payload["languages"]],
        "stack": bind("cv_facts", "technical_stack", "stack", payload["stack"]),
        "candidate": {
            key: bind("cv_facts", f"candidate_{key}", value, value)
            for key, value in payload["candidate"].items()
        },
    }
    if isinstance(positioning, dict):
        payload["claim_provenance"]["positioning"] = payload["positioning_support"]["evidence_id"]
    payload["metadata"]["candidate_facts"] = {
        "revision": revision,
        "sources": catalog,
        "evidence": evidence,
    }


def bounded_summary_inputs(fit_map: dict[str, Any]) -> dict[str, Any]:
    return {
        key: fit_map.get(key)
        for key in ("cargo", "empresa", "dor_central", "keywords_vaga", "competencias_vaga", "keywords_habilidade_ats", "historias_selecionadas", "idioma")
    }


def validate_positioning_contract(payload: dict[str, Any]) -> None:
    positioning = payload.get("positioning")
    if positioning is None:
        return
    if not isinstance(positioning, dict):
        raise ValidationFailure("CV positioning is invalid")
    required = ("catalog_entry_id", "area", "caso", "score", "matched_signals", "summary_direction_eligible", "catalog_sha256")
    if any(key not in positioning for key in required):
        raise ValidationFailure("CV positioning is incomplete")
    entries = cv_positioning.load_catalog()
    entry = next((item for item in entries if item["id"] == positioning["catalog_entry_id"]), None)
    if entry is None:
        raise ValidationFailure("CV positioning catalog entry is missing")
    if (
        positioning["area"] != entry["area"]
        or positioning["caso"] != entry["casos"]
        or positioning["catalog_sha256"] != sha256_file(cv_positioning.CATALOG_PATH)
    ):
        raise ValidationFailure("CV positioning catalog binding is invalid")
    support = payload.get("positioning_support")
    claims = payload.get("claim_provenance") if isinstance(payload.get("claim_provenance"), dict) else {}
    if (
        not isinstance(support, dict)
        or support.get("catalog_entry_id") != positioning["catalog_entry_id"]
        or support.get("caso") != positioning["caso"]
        or support.get("evidence_id") != claims.get("positioning")
    ):
        raise ValidationFailure("CV positioning support is invalid")
    if (
        not isinstance(positioning["summary_direction_eligible"], bool)
        or positioning["summary_direction_eligible"]
        != cv_positioning.summary_direction_eligible(positioning["matched_signals"])
    ):
        raise ValidationFailure("CV positioning direction eligibility is invalid")
    language = (payload.get("metadata") or {}).get("language")
    summary = str(payload.get("summary") or payload.get("resumo") or "")
    if language == "pt-BR" and positioning["summary_direction_eligible"] and not cv_positioning.normalize_tokens(positioning["caso"]).issubset(
        cv_positioning.normalize_tokens(summary)
    ):
        raise ValidationFailure("CV positioning case is missing from summary")
    if language == "en" and positioning["summary_direction_eligible"]:
        case_en = _positioning_case_for_summary(positioning, language)
        if case_en and not cv_positioning.normalize_tokens(case_en).issubset(cv_positioning.normalize_tokens(summary)):
            raise ValidationFailure("CV positioning English direction is missing from summary")
    result_key = str(entry["resultado_chave"])
    if any(result_key in str(item.get("summary_fragment") or "") for item in payload.get("summary_support", [])):
        raise ValidationFailure("CV positioning result key cannot support summary claims")


def validate_canonical_provenance(
    payload: dict[str, Any], *, fit_map: dict[str, Any] | None = None,
    fit_map_path: Path | None = None, fit_map_sha256: str | None = None,
) -> None:
    """Resolve every submitted evidence ID against canonical source bytes."""
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    facts = metadata.get("candidate_facts") if isinstance(metadata.get("candidate_facts"), dict) else {}
    expected_revision = provenance_service.candidate_facts_revision()
    if (
        facts.get("revision") != expected_revision
        or metadata.get("candidate_facts_revision") != expected_revision
    ):
        raise ValidationFailure("CV candidate facts revision mismatch")
    sources = facts.get("sources") if isinstance(facts.get("sources"), dict) else {}
    evidence = facts.get("evidence") if isinstance(facts.get("evidence"), dict) else {}
    if not sources or not evidence:
        raise ValidationFailure("CV canonical evidence catalog is missing")
    expected_sources = {
        "cv_facts": CV_FACTS_PATH,
        "profile": PROFILE_FACTS_PATH,
        "self_knowledge": SELF_KNOWLEDGE_PATH,
    }
    if payload.get("positioning") is not None:
        expected_sources["positioning_catalog"] = cv_positioning.CATALOG_PATH
    if set(sources) != set(expected_sources):
        raise ValidationFailure("CV canonical evidence sources are invalid")
    source_bytes: dict[str, bytes] = {}
    for source_name, expected_path in expected_sources.items():
        source = sources.get(source_name)
        if not isinstance(source, dict):
            raise ValidationFailure("CV canonical evidence source is missing")
        path = Path(str(source.get("path") or ""))
        if path.resolve() != expected_path.resolve() or not path.is_file() or sha256_file(path) != source.get("sha256"):
            raise ValidationFailure("CV canonical evidence source changed")
        source_bytes[source_name] = expected_path.read_bytes()
    for item in evidence.values():
        source_name = str(item.get("source") or "")
        locator = str(item.get("locator") or "")
        path_record = sources.get(source_name) if isinstance(sources, dict) else None
        if not isinstance(path_record, dict):
            raise ValidationFailure("CV evidence references an unknown canonical source")
        source_path = Path(str(path_record.get("path") or ""))
        source_value = source_bytes[source_name].decode("utf-8")
        expected_excerpt = _source_excerpt(source_value, locator)
        if (
            not locator
            or not str(item.get("kind") or "")
            or not str(item.get("value_sha256") or "")
            or item.get("source_excerpt") != expected_excerpt
            or item.get("source_excerpt_sha256") != hashlib.sha256(expected_excerpt.encode("utf-8")).hexdigest()
            or item.get("source_value") != expected_excerpt
            or item.get("source_value_sha256") != hashlib.sha256(expected_excerpt.encode("utf-8")).hexdigest()
            or (not locator.startswith("catalog-entry:") and _normalize(locator.split("::", 1)[0]) not in _normalize(source_path.read_text(encoding="utf-8")))
        ):
            raise ValidationFailure("CV evidence locator cannot be resolved")

    _validate_trusted_renderer_values(payload, fit_map=fit_map, fit_map_path=fit_map_path, fit_map_sha256=fit_map_sha256)
    required: list[str] = []
    def require(item_id: Any, kind: str, value: Any) -> None:
        item_id = str(item_id or "")
        required.append(item_id)
        record = evidence.get(item_id)
        if not isinstance(record, dict) or record.get("kind") != kind:
            raise ValidationFailure("CV evidence kind cannot be resolved")
        if record.get("value_sha256") != hashlib.sha256(str(value).encode("utf-8")).hexdigest():
            raise ValidationFailure("CV evidence value hash mismatch")

    for experience in payload.get("experiences", []):
        require(experience.get("evidence_id"), "experience", experience.get("experience_id"))
        provenance = experience.get("provenance") if isinstance(experience.get("provenance"), dict) else {}
        for key in ("role", "company", "period"):
            require(provenance.get(key), f"experience_{key}", experience.get(key))
        for bullet in experience.get("bullets", []):
            require(bullet.get("evidence_id"), "experience_bullet", bullet.get("text"))
    for experience in payload.get("experiencias", []):
        require(experience.get("evidence_id"), "experience_pt", experience.get("experience_id"))
        provenance = experience.get("provenance") if isinstance(experience.get("provenance"), dict) else {}
        pt_kinds = {
            "cargo": "experience_role_pt",
            "empresa": "experience_company_pt",
            "periodo": "experience_period_pt",
        }
        for key, kind in pt_kinds.items():
            require(provenance.get(key), kind, experience.get(key))
        for item_id, bullet in zip(provenance.get("bullets", []), experience.get("bullets", []), strict=True):
            require(item_id, "experience_bullet_pt", bullet)
    for mapping in payload.get("ats_keyword_coverage", []):
        require(mapping.get("evidence_id"), "ats_evidence", mapping.get("defensible_evidence"))
    for item in payload.get("summary_support", []):
        require(item.get("evidence_id"), "summary_evidence", item.get("defensible_evidence"))
    if payload.get("positioning") is not None:
        require((payload.get("positioning_support") or {}).get("evidence_id"), "positioning_catalog", payload["positioning"].get("caso"))
    claims = payload.get("claim_provenance") if isinstance(payload.get("claim_provenance"), dict) else {}
    for item_id, value in zip(claims.get("education", []), payload.get("education", []), strict=True):
        require(item_id, "education", value)
    for item_id, value in zip(claims.get("languages", []), payload.get("languages", []), strict=True):
        require(item_id, "language", value)
    require(claims.get("stack"), "technical_stack", payload.get("stack"))
    for key, value in payload.get("candidate", {}).items():
        require((claims.get("candidate") or {}).get(key), f"candidate_{key}", value)
    validate_positioning_contract(payload)
    if not required or any(item not in evidence for item in required):
        raise ValidationFailure("CV evidence ID cannot be resolved against canonical facts")


def _source_excerpt(source_text: str, locator: str) -> str:
    if locator.startswith("catalog-entry:"):
        entry_id = int(locator.split(":", 1)[1])
        for entry in json.loads(source_text):
            if isinstance(entry, dict) and entry.get("id") == entry_id:
                return json.dumps({key: entry[key] for key in ("id", "area", "casos")}, ensure_ascii=False, sort_keys=True)
        raise ValidationFailure("canonical positioning catalog entry is missing")
    token = _normalize(locator.split("::", 1)[0])
    for line in source_text.splitlines():
        if token and token in _normalize(line):
            return line.strip()
    raise ValidationFailure("canonical source excerpt is missing")


def _validate_trusted_renderer_values(
    payload: dict[str, Any], *, fit_map: dict[str, Any] | None,
    fit_map_path: Path | None, fit_map_sha256: str | None,
) -> None:
    """Recompute renderer inputs from canonical sources and trusted transforms.

    The evidence catalog is intentionally ignored here: it is an audit trail,
    not an authority for the rendered text.
    """
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    language = metadata.get("language")
    if language not in {"pt-BR", "en"}:
        raise ValidationFailure("CV canonical evidence language is invalid")
    raw_experiences = payload.get("experiences") if isinstance(payload.get("experiences"), list) else []
    ids = [str(item.get("experience_id") or "") for item in raw_experiences if isinstance(item, dict)]
    catalog = {str(item["id"]): item for item in _facts_experiences()}
    if not ids or len(ids) != len(set(ids)) or any(item_id not in catalog for item_id in ids):
        raise ValidationFailure("CV canonical evidence experience selection is invalid")
    selected = [catalog[item_id] for item_id in ids]
    family = str(metadata.get("job_family") or "operations")
    materialized = [_materialize_experience(item, family, language=language) for item in selected]
    expected_candidate = _candidate_contact_facts()
    if fit_map is None or fit_map_path is None or not fit_map_sha256:
        raise ValidationFailure("CV canonical evidence requires immutable FIT_MAP input")
    summary_inputs = metadata.get("summary_inputs") if isinstance(metadata.get("summary_inputs"), dict) else {}
    expected_summary_inputs = bounded_summary_inputs(fit_map)
    if (
        metadata.get("summary_inputs_sha256")
        != hashlib.sha256(json.dumps(summary_inputs, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        or summary_inputs != expected_summary_inputs
        or summary_inputs.get("cargo") != metadata.get("cargo")
    ):
        raise ValidationFailure("CV canonical evidence summary inputs are invalid")
    source_fit_map = Path(str(metadata.get("source_fit_map") or ""))
    if (
        source_fit_map.resolve() != fit_map_path.resolve()
        or metadata.get("source_fit_map_sha256") != fit_map_sha256
        or (source_fit_map.is_file() and sha256_file(source_fit_map) != fit_map_sha256)
    ):
        raise ValidationFailure("CV canonical evidence FIT_MAP binding changed")
    job_description_path = Path(str(metadata.get("job_description_path") or ""))
    if not job_description_path.is_file():
        raise ValidationFailure("CV canonical evidence job description is missing")
    expected_positioning = cv_positioning.select_positioning(fit_map, job_description_path.read_text(encoding="utf-8"))
    if payload.get("positioning") != expected_positioning:
        raise ValidationFailure("CV canonical evidence positioning changed")
    expected_summary, _support = _build_summary(materialized, summary_inputs, positioning=expected_positioning, language=language)
    if payload.get("candidate") != expected_candidate or payload.get("stack") != _facts_stack(language):
        raise ValidationFailure("CV canonical evidence does not authorize rendered contact or stack")
    if language == "en":
        expected_experiences = [
            {"experience_id": item["id"], "role": item["role"], "company": item["company"], "period": item["period"], "bullets": item["bullets"]}
            for item in materialized
        ]
        actual_experiences = [
            {
                "experience_id": item.get("experience_id"), "role": item.get("role"), "company": item.get("company"),
                "period": item.get("period"), "bullets": [bullet.get("text") for bullet in item.get("bullets", [])],
            }
            for item in raw_experiences
        ]
        if (
            actual_experiences != expected_experiences
            or payload.get("education") != _facts_education("en")
            or payload.get("languages") != _facts_languages("en")
            or payload.get("summary") != expected_summary
        ):
            raise ValidationFailure("CV canonical evidence does not authorize rendered English values")
        return
    expected_experiences = [
        {"experience_id": item["id"], "cargo": item["role"], "empresa": item["company"], "periodo": item["period"], "bullets": item["bullets"]}
        for item in materialized
    ]
    actual_pt = [
        {"experience_id": item.get("experience_id"), "cargo": item.get("cargo"), "empresa": item.get("empresa"), "periodo": item.get("periodo"), "bullets": item.get("bullets")}
        for item in payload.get("experiencias", []) if isinstance(item, dict)
    ]
    if (
        actual_pt != expected_experiences
        or payload.get("formacao") != _facts_education("pt-BR")
        or payload.get("idiomas") != _facts_languages("pt-BR")
        or payload.get("resumo") != expected_summary
    ):
        raise ValidationFailure("CV canonical evidence does not authorize rendered Portuguese values")


def _english_period(period: str) -> str:
    months = {
        "jan": "Jan", "janeiro": "Jan", "fev": "Feb", "fevereiro": "Feb",
        "mar": "Mar", "março": "Mar", "abr": "Apr", "abril": "Apr",
        "mai": "May", "maio": "May", "jun": "Jun", "junho": "Jun",
        "jul": "Jul", "julho": "Jul", "ago": "Aug", "agosto": "Aug",
        "set": "Sep", "setembro": "Sep", "out": "Oct", "outubro": "Oct",
        "nov": "Nov", "novembro": "Nov", "dez": "Dec", "dezembro": "Dec",
    }
    translated = period
    for source, target in months.items():
        translated = re.sub(rf"\b{source}(?=/|\s)", target, translated, flags=re.IGNORECASE)
    return translated.replace("Atual", "Present").replace("/", " ")


def _experience_source_locator(experience_id: str) -> str:
    return str(load_canonical_cv_facts()["experience_locators"][experience_id])


def _education_source_locator(index: int) -> tuple[str, str]:
    return "cv_facts", str(load_canonical_cv_facts()["selectors"]["education_source_locators"][index])
