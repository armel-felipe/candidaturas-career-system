from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, ROOT
from career.services import memory as memory_service
from career.utils import ensure, read_json, read_text, sha256_file, utc_now_iso, write_json
from career.workflow.state_store import WorkflowStateStore


DERIVED_DIR = CAREER_STATE / "derived"
ACTIVE_CONTEXT_PATH = DERIVED_DIR / "active_context.json"
REFERENCES = ROOT / ".opencode" / "skills" / "career-system" / "references"
JOB_EXTRACT_PATH = DERIVED_DIR / "job_extract.json"
JOB_SECTIONS_PATH = DERIVED_DIR / "job_sections.json"
JOB_KEYWORDS_PATH = DERIVED_DIR / "job_keywords.json"
JOB_REQUIREMENTS_PATH = DERIVED_DIR / "job_requirements.json"
JOB_RESPONSIBILITIES_PATH = DERIVED_DIR / "job_responsibilities.json"
JOB_COMPANY_CONTEXT_PATH = DERIVED_DIR / "job_company_context.json"
REFERENCE_DIGEST_PATH = DERIVED_DIR / "reference_digest.json"
CANDIDATE_EVIDENCE_PACK_PATH = DERIVED_DIR / "candidate_evidence_pack.json"
CANDIDATE_EVIDENCE_BY_THEME_PATH = DERIVED_DIR / "candidate_evidence_by_theme.json"
FIT_MAP_SEED_PATH = DERIVED_DIR / "fit_map_seed.json"
CV_INPUT_PACK_PATH = DERIVED_DIR / "cv_input_pack.json"
CV_CONTENT_SEED_PATH = DERIVED_DIR / "cv_content_seed.json"
HABILIDADES_INPUT_PACK_PATH = DERIVED_DIR / "habilidades_input_pack.json"
FERAS_INPUT_PACK_PATH = DERIVED_DIR / "feras_input_pack.json"
COVER_LETTER_INPUT_PACK_PATH = DERIVED_DIR / "cover_letter_input_pack.json"
DERIVED_MANIFEST_PATH = DERIVED_DIR / "manifest.json"

KEYWORD_DICTIONARY_PATH = REFERENCES / "dicionario_palavras_chave_mercado.md"
CAREER_KEYWORDS_PATH = REFERENCES / "palavras_chave_carreira.md"
PROFILE_RESTRICTIONS_PATH = REFERENCES / "perfil_restricoes.md"
SELF_KNOWLEDGE_PATH = REFERENCES / "autoconhecimento.md"


@dataclass(frozen=True)
class ActiveJobContext:
    job_description_path: Path
    fingerprint: str
    company: str
    role: str
    source_type: str
    source_id: str | None


def build_all_for_fit_map() -> dict[str, Any]:
    active = resolve_active_job_context()
    memory_service.build_memory_bundle()
    active_context = build_active_context(active)
    job_extract = build_job_extract(active)
    job_sections = build_job_sections(active, job_extract=job_extract)
    job_requirements = build_job_requirements(active, job_sections=job_sections)
    job_responsibilities = build_job_responsibilities(active, job_sections=job_sections)
    job_company_context = build_job_company_context(active, job_extract=job_extract, job_sections=job_sections)
    job_keywords = build_job_keywords(active, job_extract=job_extract, job_sections=job_sections)
    reference_digest = build_reference_digest(active, job_keywords=job_keywords)
    evidence_pack = build_candidate_evidence_pack(active, job_keywords=job_keywords)
    evidence_by_theme = build_candidate_evidence_by_theme(active, evidence_pack=evidence_pack)
    fit_map_seed = build_fit_map_seed(
        active,
        job_extract=job_extract,
        job_keywords=job_keywords,
        reference_digest=reference_digest,
        evidence_pack=evidence_pack,
    )
    cv_input_pack = build_cv_input_pack(active)
    cv_content_seed = build_cv_content_seed(active, cv_input_pack=cv_input_pack)
    habilidades_input_pack = build_habilidades_input_pack(active)
    feras_input_pack = build_feras_input_pack(active)
    cover_letter_input_pack = build_cover_letter_input_pack(active)
    manifest = write_manifest(
        active,
        {
            "active_context": ACTIVE_CONTEXT_PATH,
            "job_extract": JOB_EXTRACT_PATH,
            "job_sections": JOB_SECTIONS_PATH,
            "job_requirements": JOB_REQUIREMENTS_PATH,
            "job_responsibilities": JOB_RESPONSIBILITIES_PATH,
            "job_company_context": JOB_COMPANY_CONTEXT_PATH,
            "job_keywords": JOB_KEYWORDS_PATH,
            "reference_digest": REFERENCE_DIGEST_PATH,
            "candidate_evidence_pack": CANDIDATE_EVIDENCE_PACK_PATH,
            "candidate_evidence_by_theme": CANDIDATE_EVIDENCE_BY_THEME_PATH,
            "fit_map_seed": FIT_MAP_SEED_PATH,
            "cv_input_pack": CV_INPUT_PACK_PATH,
            "cv_content_seed": CV_CONTENT_SEED_PATH,
            "habilidades_input_pack": HABILIDADES_INPUT_PACK_PATH,
            "feras_input_pack": FERAS_INPUT_PACK_PATH,
            "cover_letter_input_pack": COVER_LETTER_INPUT_PACK_PATH,
        },
    )
    return {
        "status": "ok",
        "job_description_path": _relative(active.job_description_path),
        "fingerprint": active.fingerprint,
        "outputs": {
            "active_context": _relative(ACTIVE_CONTEXT_PATH),
            "job_extract": _relative(JOB_EXTRACT_PATH),
            "job_sections": _relative(JOB_SECTIONS_PATH),
            "job_requirements": _relative(JOB_REQUIREMENTS_PATH),
            "job_responsibilities": _relative(JOB_RESPONSIBILITIES_PATH),
            "job_company_context": _relative(JOB_COMPANY_CONTEXT_PATH),
            "job_keywords": _relative(JOB_KEYWORDS_PATH),
            "reference_digest": _relative(REFERENCE_DIGEST_PATH),
            "candidate_evidence_pack": _relative(CANDIDATE_EVIDENCE_PACK_PATH),
            "candidate_evidence_by_theme": _relative(CANDIDATE_EVIDENCE_BY_THEME_PATH),
            "fit_map_seed": _relative(FIT_MAP_SEED_PATH),
            "cv_input_pack": _relative(CV_INPUT_PACK_PATH),
            "cv_content_seed": _relative(CV_CONTENT_SEED_PATH),
            "habilidades_input_pack": _relative(HABILIDADES_INPUT_PACK_PATH),
            "feras_input_pack": _relative(FERAS_INPUT_PACK_PATH),
            "cover_letter_input_pack": _relative(COVER_LETTER_INPUT_PACK_PATH),
            "manifest": _relative(DERIVED_MANIFEST_PATH),
        },
        "summary": {
            "active_context_role": active_context.get("role"),
            "language": job_extract.get("job_identity", {}).get("language"),
            "requirements_count": len(job_requirements.get("requirements", []) or []),
            "responsibilities_count": len(job_responsibilities.get("responsibilities", []) or []),
            "keywords_count": len(job_keywords.get("matched_keywords", []) or []),
            "evidence_items": len(evidence_by_theme.get("themes", {}) or {}),
            "digest_rules": len(reference_digest.get("fit_rules", []) or []),
        },
        "manifest": manifest,
    }


def build_active_context(active: ActiveJobContext | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    payload = {
        "kind": "active_context",
        "created_at": utc_now_iso(),
        "job_description_path": _relative(active.job_description_path),
        "fingerprint": active.fingerprint,
        "company": active.company,
        "role": active.role,
        "source_type": active.source_type,
        "source_id": active.source_id,
    }
    write_json(ACTIVE_CONTEXT_PATH, payload)
    return payload


def build_job_extract(active: ActiveJobContext | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    text = read_text(active.job_description_path)
    lines = [line.strip() for line in text.splitlines()]
    description = _extract_description_body(text)
    header_title = _extract_markdown_title(lines)
    metadata = _extract_metadata(lines)
    sections = _split_sections(description)
    payload = {
        "kind": "job_extract",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
            "source_type": active.source_type,
            "source_id": active.source_id,
        },
        "job_identity": {
            "company": metadata.get("company") or active.company,
            "role": header_title or metadata.get("title") or active.role,
            "location": metadata.get("location") or "",
            "language": _infer_language(description),
        },
        "description_stats": {
            "chars": len(description),
            "lines": len([line for line in description.splitlines() if line.strip()]),
            "sections": len(sections),
        },
        "description_preview": _preview_lines(description, limit=8),
        "section_names": [item["name"] for item in sections],
    }
    _validate_job_extract(payload)
    write_json(JOB_EXTRACT_PATH, payload)
    return payload


def build_job_sections(active: ActiveJobContext | None = None, *, job_extract: dict[str, Any] | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    text = read_text(active.job_description_path)
    description = _extract_description_body(text)
    sections = _split_sections(description)
    payload = {
        "kind": "job_sections",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "language": (job_extract or {}).get("job_identity", {}).get("language") or _infer_language(description),
        "sections": sections,
    }
    write_json(JOB_SECTIONS_PATH, payload)
    return payload


def build_job_requirements(active: ActiveJobContext | None = None, *, job_sections: dict[str, Any] | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    sections_payload = job_sections or build_job_sections(active)
    requirements = _extract_section_lines(
        sections_payload,
        markers=("requisito", "qualific", "buscando", "requirements", "conhecimento", "experi"),
    )
    payload = {
        "kind": "job_requirements",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "requirements": requirements[:20],
    }
    write_json(JOB_REQUIREMENTS_PATH, payload)
    return payload


def build_job_responsibilities(active: ActiveJobContext | None = None, *, job_sections: dict[str, Any] | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    sections_payload = job_sections or build_job_sections(active)
    responsibilities = _extract_section_lines(
        sections_payload,
        markers=("responsabil", "atividad", "desafio", "role", "missão", "missao"),
    )
    payload = {
        "kind": "job_responsibilities",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "responsibilities": responsibilities[:25],
    }
    write_json(JOB_RESPONSIBILITIES_PATH, payload)
    return payload


def build_job_company_context(
    active: ActiveJobContext | None = None,
    *,
    job_extract: dict[str, Any] | None = None,
    job_sections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    extract_payload = job_extract or build_job_extract(active)
    sections_payload = job_sections or build_job_sections(active, job_extract=extract_payload)
    preview_lines = extract_payload.get("description_preview", []) or []
    overview = next((section for section in sections_payload.get("sections", []) if section.get("name") == "Sobre a vaga"), None)
    payload = {
        "kind": "job_company_context",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "company": extract_payload.get("job_identity", {}).get("company") or active.company,
        "role": extract_payload.get("job_identity", {}).get("role") or active.role,
        "location": extract_payload.get("job_identity", {}).get("location") or "",
        "language": extract_payload.get("job_identity", {}).get("language") or "",
        "context_lines": (overview or {}).get("content_preview") or preview_lines[:5],
    }
    write_json(JOB_COMPANY_CONTEXT_PATH, payload)
    return payload


def build_job_keywords(
    active: ActiveJobContext | None = None,
    *,
    job_extract: dict[str, Any] | None = None,
    job_sections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    text = read_text(active.job_description_path)
    description = _extract_description_body(text)
    normalized_description = _normalize(description)
    dictionary_terms = _load_table_terms(KEYWORD_DICTIONARY_PATH)
    career_terms = _load_table_terms(CAREER_KEYWORDS_PATH)
    matched = _matched_terms(normalized_description, dictionary_terms, source_name=_relative(KEYWORD_DICTIONARY_PATH))
    matched.extend(_matched_terms(normalized_description, career_terms, source_name=_relative(CAREER_KEYWORDS_PATH)))
    matched = _dedupe_keyword_matches(matched)
    fallback_lines = _extract_requirement_lines(job_sections or build_job_sections(active, job_extract=job_extract))
    payload = {
        "kind": "job_keywords",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "language": (job_extract or {}).get("job_identity", {}).get("language") or _infer_language(description),
        "matched_keywords": matched[:40],
        "fallback_requirement_lines": fallback_lines[:15],
        "top_focus_terms": [item["term"] for item in matched[:12]],
    }
    write_json(JOB_KEYWORDS_PATH, payload)
    return payload


def build_reference_digest(active: ActiveJobContext | None = None, *, job_keywords: dict[str, Any] | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    memory_bundle = memory_service.build_memory_bundle()
    profile_facts = read_json(memory_bundle["profile_facts.json"])
    application_rules = read_json(memory_bundle["application_rules.json"])
    objections = _extract_bullets_under_heading(SELF_KNOWLEDGE_PATH, "## Objeções mapeadas para vaga ideal")
    restrictions = _extract_table_rows(PROFILE_RESTRICTIONS_PATH, "## NÚMEROS CRÍTICOS — NUNCA ALTERAR", limit=12)
    payload = {
        "kind": "reference_digest",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "language_rules": profile_facts.get("language_rules", {}),
        "protected_claims": profile_facts.get("protected_claims", []),
        "critical_metrics": profile_facts.get("critical_metrics", {}),
        "fit_rules": application_rules.get("fit_rules", []),
        "tone": application_rules.get("tone"),
        "objections": objections[:8],
        "critical_numbers": restrictions,
        "focus_terms": (job_keywords or {}).get("top_focus_terms", []),
    }
    write_json(REFERENCE_DIGEST_PATH, payload)
    return payload


def build_candidate_evidence_pack(active: ActiveJobContext | None = None, *, job_keywords: dict[str, Any] | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    keywords_payload = job_keywords or read_json(JOB_KEYWORDS_PATH)
    focus_terms = [item["term"] for item in keywords_payload.get("matched_keywords", [])[:12]]
    evidence_items: list[dict[str, Any]] = []
    evidence_items.extend(_evidence_from_dictionary_terms(focus_terms))
    evidence_items.extend(_evidence_from_career_keywords(focus_terms))
    evidence_items = _dedupe_evidence_items(evidence_items)
    payload = {
        "kind": "candidate_evidence_pack",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "focus_terms": focus_terms,
        "evidence_items": evidence_items[:30],
    }
    write_json(CANDIDATE_EVIDENCE_PACK_PATH, payload)
    return payload


def build_candidate_evidence_by_theme(
    active: ActiveJobContext | None = None,
    *,
    evidence_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    evidence_payload = evidence_pack or read_json(CANDIDATE_EVIDENCE_PACK_PATH)
    themes: dict[str, list[dict[str, Any]]] = {
        "leadership": [],
        "growth": [],
        "pricing": [],
        "channels": [],
        "pipeline_conversion": [],
        "data_dashboards": [],
        "digital_ai": [],
        "industry": [],
        "strategy_planning": [],
    }
    for item in evidence_payload.get("evidence_items", []):
        if not isinstance(item, dict):
            continue
        term = _normalize(str(item.get("job_term") or item.get("candidate_evidence") or ""))
        target_keys: list[str] = []
        if any(token in term for token in ("lider", "team", "people", "leader")):
            target_keys.append("leadership")
        if any(token in term for token in ("growth", "upsell", "cross", "business development", "negocio")):
            target_keys.append("growth")
        if any(token in term for token in ("pric", "preco", "margem", "margin")):
            target_keys.append("pricing")
        if any(token in term for token in ("canal", "channel", "vendas", "sales")):
            target_keys.append("channels")
        if any(token in term for token in ("pipeline", "convers", "lead")):
            target_keys.append("pipeline_conversion")
        if any(token in term for token in ("data", "dash", "insight", "bi", "sql")):
            target_keys.append("data_dashboards")
        if any(token in term for token in ("digital", "ia", "ai", "autom")):
            target_keys.append("digital_ai")
        if any(token in term for token in ("industr", "manufact", "s&op", "otif", "mrp")):
            target_keys.append("industry")
        if any(token in term for token in ("strateg", "planning", "forecast", "s&op")):
            target_keys.append("strategy_planning")
        for key in target_keys:
            themes[key].append(item)
    payload = {
        "kind": "candidate_evidence_by_theme",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "themes": {key: value[:8] for key, value in themes.items() if value},
    }
    write_json(CANDIDATE_EVIDENCE_BY_THEME_PATH, payload)
    return payload


def build_fit_map_seed(
    active: ActiveJobContext | None = None,
    *,
    job_extract: dict[str, Any] | None = None,
    job_keywords: dict[str, Any] | None = None,
    reference_digest: dict[str, Any] | None = None,
    evidence_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    extract_payload = job_extract or read_json(JOB_EXTRACT_PATH)
    keywords_payload = job_keywords or read_json(JOB_KEYWORDS_PATH)
    digest_payload = reference_digest or read_json(REFERENCE_DIGEST_PATH)
    evidence_payload = evidence_pack or read_json(CANDIDATE_EVIDENCE_PACK_PATH)
    payload = {
        "kind": "fit_map_seed",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "cargo": extract_payload["job_identity"]["role"],
        "empresa": extract_payload["job_identity"]["company"],
        "idioma": extract_payload["job_identity"]["language"],
        "dor_central_candidates": keywords_payload.get("fallback_requirement_lines", [])[:5],
        "keywords_vaga_candidates": keywords_payload.get("matched_keywords", [])[:15],
        "keywords_habilidade_ats_candidates": keywords_payload.get("top_focus_terms", [])[:12],
        "candidate_evidence_candidates": evidence_payload.get("evidence_items", [])[:12],
        "rules": {
            "fit_rules": digest_payload.get("fit_rules", []),
            "protected_claims": digest_payload.get("protected_claims", []),
        },
    }
    write_json(FIT_MAP_SEED_PATH, payload)
    return payload


def build_cv_input_pack(active: ActiveJobContext | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    fit_map_path = CAREER_STATE / "fit_map.json"
    ensure(fit_map_path.exists(), "build_cv_input_pack_requires_fit_map")
    fit_map = read_json(fit_map_path)
    digest = read_json(REFERENCE_DIGEST_PATH) if REFERENCE_DIGEST_PATH.exists() else build_reference_digest(active)
    requirements = read_json(JOB_REQUIREMENTS_PATH) if JOB_REQUIREMENTS_PATH.exists() else build_job_requirements(active)
    responsibilities = read_json(JOB_RESPONSIBILITIES_PATH) if JOB_RESPONSIBILITIES_PATH.exists() else build_job_responsibilities(active)
    evidence_by_theme = (
        read_json(CANDIDATE_EVIDENCE_BY_THEME_PATH)
        if CANDIDATE_EVIDENCE_BY_THEME_PATH.exists()
        else build_candidate_evidence_by_theme(active)
    )
    payload = {
        "kind": "cv_input_pack",
        "created_at": utc_now_iso(),
        "source": {
            "fit_map_path": _relative(fit_map_path),
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "job_identity": {
            "cargo": fit_map.get("cargo"),
            "empresa": fit_map.get("empresa"),
            "language": _infer_cv_language(fit_map, active),
        },
        "dor_central": fit_map.get("dor_central"),
        "requirements": requirements.get("requirements", []),
        "responsibilities": responsibilities.get("responsibilities", []),
        "selected_stories": fit_map.get("historias_selecionadas", {}),
        "keywords_habilidade_ats": fit_map.get("keywords_habilidade_ats", []),
        "keywords_para_ats": fit_map.get("keywords_para_ats", []),
        "gaps_sem_cobertura": fit_map.get("gaps_sem_cobertura", []),
        "evidence_by_theme": evidence_by_theme.get("themes", {}),
        "critical_rules": {
            "protected_claims": digest.get("protected_claims", []),
            "critical_metrics": digest.get("critical_metrics", {}),
            "tone": digest.get("tone"),
        },
    }
    write_json(CV_INPUT_PACK_PATH, payload)
    return payload


def build_habilidades_input_pack(active: ActiveJobContext | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    fit_map_path = CAREER_STATE / "fit_map.json"
    ensure(fit_map_path.exists(), "build_habilidades_input_pack_requires_fit_map")
    fit_map = read_json(fit_map_path)
    job_keywords = read_json(JOB_KEYWORDS_PATH) if JOB_KEYWORDS_PATH.exists() else build_job_keywords(active)
    payload = {
        "kind": "habilidades_input_pack",
        "created_at": utc_now_iso(),
        "source": {
            "fit_map_path": _relative(fit_map_path),
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "job_identity": {
            "cargo": fit_map.get("cargo"),
            "empresa": fit_map.get("empresa"),
        },
        "keywords_habilidade_ats": fit_map.get("keywords_habilidade_ats", []),
        "keywords_vaga_candidates": job_keywords.get("top_focus_terms", []),
        "gaps_sem_cobertura": fit_map.get("gaps_sem_cobertura", []),
    }
    write_json(HABILIDADES_INPUT_PACK_PATH, payload)
    return payload


def build_cv_content_seed(active: ActiveJobContext | None = None, *, cv_input_pack: dict[str, Any] | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    cv_input = cv_input_pack or (read_json(CV_INPUT_PACK_PATH) if CV_INPUT_PACK_PATH.exists() else build_cv_input_pack(active))
    payload = {
        "kind": "cv_content_seed",
        "created_at": utc_now_iso(),
        "source": {
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
            "fit_map_path": ".career-state/fit_map.json",
        },
        "job_identity": cv_input.get("job_identity", {}),
        "dor_central": cv_input.get("dor_central"),
        "top8_keywords": list((cv_input.get("keywords_habilidade_ats") or [])[:8]),
        "selected_stories": cv_input.get("selected_stories", {}),
        "requirements": cv_input.get("requirements", []),
        "responsibilities": cv_input.get("responsibilities", []),
        "evidence_by_theme": cv_input.get("evidence_by_theme", {}),
        "critical_rules": cv_input.get("critical_rules", {}),
    }
    write_json(CV_CONTENT_SEED_PATH, payload)
    return payload


def build_cover_letter_input_pack(active: ActiveJobContext | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    fit_map_path = CAREER_STATE / "fit_map.json"
    ensure(fit_map_path.exists(), "build_cover_letter_input_pack_requires_fit_map")
    fit_map = read_json(fit_map_path)
    company_context = (
        read_json(JOB_COMPANY_CONTEXT_PATH)
        if JOB_COMPANY_CONTEXT_PATH.exists()
        else build_job_company_context(active)
    )
    payload = {
        "kind": "cover_letter_input_pack",
        "created_at": utc_now_iso(),
        "source": {
            "fit_map_path": _relative(fit_map_path),
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "job_identity": {
            "cargo": fit_map.get("cargo"),
            "empresa": fit_map.get("empresa"),
            "language": _infer_cv_language(fit_map, active),
        },
        "dor_central": fit_map.get("dor_central"),
        "selected_stories": fit_map.get("historias_selecionadas", {}),
        "keywords_para_ats": fit_map.get("keywords_para_ats", []),
        "company_context": company_context.get("context_lines", []),
        "gaps_sem_cobertura": fit_map.get("gaps_sem_cobertura", []),
    }
    write_json(COVER_LETTER_INPUT_PACK_PATH, payload)
    return payload


def build_feras_input_pack(active: ActiveJobContext | None = None) -> dict[str, Any]:
    active = active or resolve_active_job_context()
    fit_map_path = CAREER_STATE / "fit_map.json"
    ensure(fit_map_path.exists(), "build_feras_input_pack_requires_fit_map")
    fit_map = read_json(fit_map_path)
    payload = {
        "kind": "feras_input_pack",
        "created_at": utc_now_iso(),
        "source": {
            "fit_map_path": _relative(fit_map_path),
            "job_description_path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "job_identity": {
            "cargo": fit_map.get("cargo"),
            "empresa": fit_map.get("empresa"),
            "language": _infer_cv_language(fit_map, active),
        },
        "dor_central": fit_map.get("dor_central"),
        "selected_stories": fit_map.get("historias_selecionadas", {}),
        "keywords_para_ats": fit_map.get("keywords_para_ats", []),
        "objecoes": fit_map.get("objecoes", []),
    }
    write_json(FERAS_INPUT_PACK_PATH, payload)
    return payload


def write_manifest(active: ActiveJobContext, outputs: dict[str, Path]) -> dict[str, Any]:
    payload = {
        "kind": "derived_manifest",
        "created_at": utc_now_iso(),
        "job_description_path": _relative(active.job_description_path),
        "fingerprint": active.fingerprint,
        "outputs": {
            name: {
                "path": _relative(path),
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
            for name, path in outputs.items()
        },
    }
    write_json(DERIVED_MANIFEST_PATH, payload)
    return payload


def validate_manifest() -> dict[str, Any]:
    active = resolve_active_job_context()
    ensure(DERIVED_MANIFEST_PATH.exists(), "derived_manifest_missing")
    manifest = read_json(DERIVED_MANIFEST_PATH)
    ensure(manifest.get("fingerprint") == active.fingerprint, "derived_manifest_stale_for_active_job")
    required = [
        "active_context",
        "job_extract",
        "job_sections",
        "job_requirements",
        "job_responsibilities",
        "job_company_context",
        "job_keywords",
        "reference_digest",
        "candidate_evidence_pack",
        "candidate_evidence_by_theme",
        "fit_map_seed",
        "cv_input_pack",
        "cv_content_seed",
        "habilidades_input_pack",
        "feras_input_pack",
        "cover_letter_input_pack",
    ]
    outputs = manifest.get("outputs", {}) if isinstance(manifest.get("outputs"), dict) else {}
    missing = [name for name in required if not isinstance(outputs.get(name), dict) or not outputs[name].get("exists")]
    return {
        "status": "blocked" if missing else "ok",
        "job_description_path": manifest.get("job_description_path"),
        "fingerprint": manifest.get("fingerprint"),
        "missing_outputs": missing,
        "outputs": outputs,
    }


def derived_summary() -> dict[str, Any]:
    active = resolve_active_job_context()
    manifest_status = validate_manifest() if DERIVED_MANIFEST_PATH.exists() else {"status": "blocked", "missing_outputs": ["manifest"]}
    outputs = manifest_status.get("outputs", {}) if isinstance(manifest_status.get("outputs"), dict) else {}
    return {
        "status": manifest_status.get("status"),
        "job_description_path": _relative(active.job_description_path),
        "fingerprint": active.fingerprint,
        "compact_files": fit_map_compact_files(),
        "fallback_reference_files": fit_map_fallback_reference_files(),
        "sizes": {
            name: (item.get("bytes") if isinstance(item, dict) else None)
            for name, item in outputs.items()
        },
        "missing_outputs": manifest_status.get("missing_outputs", []),
    }


def context_doctor() -> dict[str, Any]:
    active = resolve_active_job_context()
    files = [
        ACTIVE_CONTEXT_PATH,
        JOB_EXTRACT_PATH,
        JOB_SECTIONS_PATH,
        JOB_REQUIREMENTS_PATH,
        JOB_RESPONSIBILITIES_PATH,
        JOB_COMPANY_CONTEXT_PATH,
        JOB_KEYWORDS_PATH,
        REFERENCE_DIGEST_PATH,
        CANDIDATE_EVIDENCE_PACK_PATH,
        CANDIDATE_EVIDENCE_BY_THEME_PATH,
        FIT_MAP_SEED_PATH,
        CV_INPUT_PACK_PATH,
        CV_CONTENT_SEED_PATH,
        HABILIDADES_INPUT_PACK_PATH,
        FERAS_INPUT_PACK_PATH,
        COVER_LETTER_INPUT_PACK_PATH,
    ]
    report = []
    large = []
    for path in files:
        item = {
            "path": _relative(path),
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
        }
        report.append(item)
        if item["exists"] and item["bytes"] > 50_000:
            large.append(item["path"])
    return {
        "status": "blocked" if large else "ok",
        "active_job": {
            "path": _relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "derived_files": report,
        "oversized_outputs": large,
    }


def fit_map_compact_files() -> list[str]:
    return [
        ".career-state/derived/active_context.json",
        ".career-state/fit_map.draft.json",
        ".career-state/derived/job_extract.json",
        ".career-state/derived/job_sections.json",
        ".career-state/derived/job_requirements.json",
        ".career-state/derived/job_responsibilities.json",
        ".career-state/derived/job_company_context.json",
        ".career-state/derived/job_keywords.json",
        ".career-state/derived/reference_digest.json",
        ".career-state/derived/candidate_evidence_pack.json",
        ".career-state/derived/candidate_evidence_by_theme.json",
        ".career-state/derived/fit_map_seed.json",
        ".career-state/derived/manifest.json",
        ".career-state/memory/profile_facts.json",
        ".career-state/memory/application_rules.json",
        ".career-state/memory/evidence_index.json",
    ]


def fit_map_fallback_reference_files() -> list[str]:
    return [
        ".opencode/skills/career-system/references/dicionario_palavras_chave_mercado.md",
        ".opencode/skills/career-system/references/palavras_chave_carreira.md",
        ".opencode/skills/career-system/references/autoconhecimento.md",
        ".opencode/skills/career-system/references/perfil_restricoes.md",
    ]


def cv_compact_files() -> list[str]:
    return [
        ".career-state/fit_map.json",
        ".career-state/derived/cv_input_pack.json",
        ".career-state/derived/cv_content_seed.json",
        ".career-state/derived/reference_digest.json",
        ".career-state/derived/manifest.json",
        ".career-state/memory/profile_facts.json",
        ".career-state/memory/application_rules.json",
    ]


def resolve_active_job_context() -> ActiveJobContext:
    payload = WorkflowStateStore().load()
    active = payload.get("active_intake")
    ensure(isinstance(active, dict), "active_intake_missing")
    job_description_rel = active.get("job_description_path")
    ensure(isinstance(job_description_rel, str) and job_description_rel.strip(), "active_intake_missing_job_description_path")
    job_description_path = ROOT / job_description_rel
    ensure(job_description_path.exists(), f"active_job_description_missing: {job_description_rel}")
    fingerprint = sha256_file(job_description_path)
    return ActiveJobContext(
        job_description_path=job_description_path,
        fingerprint=fingerprint,
        company=str(active.get("company") or ""),
        role=str(active.get("role") or ""),
        source_type=str(active.get("source_type") or ""),
        source_id=str(active.get("source_id") or "") or None,
    )


def _validate_job_extract(payload: dict[str, Any]) -> None:
    ensure(payload.get("kind") == "job_extract", "job_extract_kind_invalid")
    ensure(isinstance(payload.get("job_identity"), dict), "job_extract_missing_job_identity")
    ensure(payload["job_identity"].get("role"), "job_extract_missing_role")
    ensure(payload["job_identity"].get("company") is not None, "job_extract_missing_company")
    stats = payload.get("description_stats")
    ensure(isinstance(stats, dict) and int(stats.get("chars") or 0) > 200, "job_extract_description_too_short")


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _extract_markdown_title(lines: list[str]) -> str:
    for line in lines:
        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            if title:
                return title
    return ""


def _extract_metadata(lines: list[str]) -> dict[str, str]:
    metadata = {"company": "", "location": "", "title": ""}
    for line in lines[:20]:
        if line.lower().startswith("empresa:"):
            metadata["company"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("localização:") or line.lower().startswith("localizacao:"):
            metadata["location"] = line.split(":", 1)[1].strip()
    return metadata


def _extract_description_body(text: str) -> str:
    marker = "## Descrição da vaga"
    if marker in text:
        return text.split(marker, 1)[1].strip()
    return text.strip()


def _split_sections(text: str) -> list[dict[str, Any]]:
    lines = [line.rstrip() for line in text.splitlines()]
    sections: list[dict[str, Any]] = []
    current_name = "overview"
    current_lines: list[str] = []

    def flush() -> None:
        content = "\n".join(line for line in current_lines if line.strip()).strip()
        if not content:
            return
        bullets = [
            _clean_bullet(line)
            for line in content.splitlines()
            if _looks_like_bullet(line)
        ]
        sections.append(
            {
                "name": current_name,
                "content_preview": _preview_lines(content, limit=5),
                "bullets": bullets[:20],
                "chars": len(content),
            }
        )

    for line in lines:
        stripped = line.strip()
        if _is_section_heading(stripped):
            flush()
            current_name = stripped.rstrip(":").strip()
            current_lines = []
            continue
        current_lines.append(line)
    flush()
    return sections


def _is_section_heading(line: str) -> bool:
    if not line:
        return False
    lowered = line.casefold().rstrip(":")
    candidates = (
        "sobre a vaga",
        "about the job",
        "responsabilidades",
        "responsabilidades e atribuições",
        "responsabilidades e atribuicoes",
        "atribuições",
        "atribuicoes",
        "qualificações",
        "qualificacoes",
        "requisitos",
        "requisitos e qualificações",
        "requisitos e qualificacoes",
        "local de trabalho e modelo de contratação",
        "local de trabalho e modelo de contratacao",
        "location",
        "requirements",
        "what you'll do",
        "what you will do",
    )
    return lowered in candidates


def _preview_lines(text: str, *, limit: int) -> list[str]:
    preview = []
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            preview.append(cleaned)
        if len(preview) >= limit:
            break
    return preview


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _load_table_terms(path: Path) -> list[dict[str, str]]:
    terms: list[dict[str, str]] = []
    if not path.exists():
        return terms
    for line_number, raw_line in enumerate(read_text(path).splitlines(), start=1):
        if not raw_line.startswith("|"):
            continue
        cells = [cell.strip() for cell in raw_line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        term = cells[0]
        if not term or term.casefold().startswith("palavra-chave") or set(term) == {"-"}:
            continue
        terms.append(
            {
                "term": term,
                "normalized": _normalize(term.replace("(uso cauteloso)", "").strip()),
                "line_number": str(line_number),
            }
        )
    return terms


def _matched_terms(text: str, terms: list[dict[str, str]], *, source_name: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for item in terms:
        term = item["term"]
        normalized = item["normalized"]
        if not normalized or len(normalized) < 3:
            continue
        if normalized in text:
            matches.append(
                {
                    "term": term,
                    "source": source_name,
                    "line_number": int(item["line_number"]),
                    "match_type": "dictionary_term",
                }
            )
    return matches


def _dedupe_keyword_matches(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = _normalize(str(item.get("term") or ""))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_requirement_lines(job_sections: dict[str, Any]) -> list[str]:
    results: list[str] = []
    for section in job_sections.get("sections", []):
        if not isinstance(section, dict):
            continue
        name = _normalize(str(section.get("name") or ""))
        if any(token in name for token in ("requis", "qualific", "responsab", "what you'll do", "what you will do")):
            for bullet in section.get("bullets", []) or []:
                cleaned = bullet.strip()
                if cleaned and cleaned not in results:
                    results.append(cleaned)
    return results


def _extract_section_lines(job_sections: dict[str, Any], *, markers: tuple[str, ...]) -> list[str]:
    results: list[str] = []
    for section in job_sections.get("sections", []):
        if not isinstance(section, dict):
            continue
        name = _normalize(str(section.get("name") or ""))
        if any(marker in name for marker in markers):
            for bullet in section.get("bullets", []) or []:
                cleaned = str(bullet).strip()
                if cleaned and cleaned not in results:
                    results.append(cleaned)
            for line in section.get("content_preview", []) or []:
                cleaned = str(line).strip()
                if cleaned and cleaned not in results:
                    results.append(cleaned)
    if not results:
        return _extract_requirement_lines(job_sections)
    return results


def _extract_bullets_under_heading(path: Path, heading: str) -> list[str]:
    text = read_text(path)
    if heading not in text:
        return []
    tail = text.split(heading, 1)[1]
    lines = []
    for raw_line in tail.splitlines()[1:]:
        if raw_line.startswith("## "):
            break
        stripped = raw_line.strip()
        if stripped.startswith("* "):
            lines.append(stripped.removeprefix("* ").strip())
    return lines


def _extract_table_rows(path: Path, heading: str, *, limit: int) -> list[dict[str, str]]:
    text = read_text(path)
    if heading not in text:
        return []
    tail = text.split(heading, 1)[1]
    rows: list[dict[str, str]] = []
    for raw_line in tail.splitlines()[1:]:
        if raw_line.startswith("## "):
            break
        if not raw_line.startswith("|"):
            continue
        cells = [cell.strip() for cell in raw_line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0].casefold() == "empresa" or set(cells[0]) == {"-"}:
            continue
        rows.append({"empresa": cells[0], "metrica": cells[1], "valor": cells[2]})
        if len(rows) >= limit:
            break
    return rows


def _evidence_from_dictionary_terms(focus_terms: list[str]) -> list[dict[str, Any]]:
    if not KEYWORD_DICTIONARY_PATH.exists():
        return []
    results: list[dict[str, Any]] = []
    lines = read_text(KEYWORD_DICTIONARY_PATH).splitlines()
    current_section = ""
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped.removeprefix("## ").strip()
            continue
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 3 or cells[0].casefold().startswith("termo da vaga") or set(cells[0]) == {"-"}:
            continue
        term = cells[0]
        if _normalize(term) not in {_normalize(item) for item in focus_terms}:
            continue
        results.append(
            {
                "term": term,
                "source": _relative(KEYWORD_DICTIONARY_PATH),
                "section": current_section,
                "line_number": index,
                "candidate_evidence": cells[1],
                "suggested_cv_phrase": cells[2],
            }
        )
    return results


def _evidence_from_career_keywords(focus_terms: list[str]) -> list[dict[str, Any]]:
    if not CAREER_KEYWORDS_PATH.exists():
        return []
    focus = {_normalize(item) for item in focus_terms}
    results: list[dict[str, Any]] = []
    lines = read_text(CAREER_KEYWORDS_PATH).splitlines()
    current_section = ""
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped.removeprefix("## ").strip()
            continue
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 3 or cells[0].casefold().startswith("palavra-chave") or set(cells[0]) == {"-"}:
            continue
        term = cells[0]
        normalized = _normalize(term)
        if normalized not in focus:
            if not any(token in normalized for token in focus):
                continue
        results.append(
            {
                "term": term,
                "source": _relative(CAREER_KEYWORDS_PATH),
                "section": current_section,
                "line_number": index,
                "candidate_origin": cells[1],
                "story_result": cells[2],
            }
        )
    return results


def _dedupe_evidence_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = (_normalize(str(item.get("term") or "")), str(item.get("source") or ""))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _infer_language(text: str) -> str:
    normalized = _normalize(text)
    pt_markers = (" vaga ", " requisitos ", " qualificacoes ", " local de trabalho ", " responsabilidades ")
    en_markers = (" about the job ", " requirements ", " qualifications ", " location ", " responsibilities ")
    pt_score = sum(marker in f" {normalized} " for marker in pt_markers)
    en_score = sum(marker in f" {normalized} " for marker in en_markers)
    return "pt-BR" if pt_score >= en_score else "en"


def _infer_cv_language(fit_map: dict[str, Any], active: ActiveJobContext) -> str:
    for key in ("idioma", "required_cv_language", "language"):
        value = str(fit_map.get(key) or "").strip()
        if value:
            return value
    if JOB_EXTRACT_PATH.exists():
        extract = read_json(JOB_EXTRACT_PATH)
        language = str((extract.get("job_identity") or {}).get("language") or "").strip()
        if language:
            return language
    return _infer_language(read_text(active.job_description_path))


def _looks_like_bullet(line: str) -> bool:
    stripped = line.strip()
    return (
        stripped.startswith(("-", "*", "•"))
        or stripped.endswith(";")
        or bool(re.match(r"^\d+[.)]\s+", stripped))
    )


def _clean_bullet(line: str) -> str:
    stripped = line.strip()
    stripped = re.sub(r"^[-*•]\s*", "", stripped)
    stripped = re.sub(r"^\d+[.)]\s*", "", stripped)
    return stripped.strip()
