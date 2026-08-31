from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unicodedata
import warnings
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Mapping

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
from career.services.positioning_pack import artifact_claim_text, artifact_provenance, validate_positioning_pack
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


def _facts_stack() -> str:
    return str(load_canonical_cv_facts()["stack"])


CV_CONTENT_PATH = CAREER_STATE / "cv_content.json"
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


def build_current_cv_content(
    path: Path | None = None,
    *,
    application_paths: ApplicationPaths | None = None,
) -> dict[str, Any]:
    if application_paths is None:
        raise ValidationFailure("explicit_application_scope_required")
    path = Path(path or application_paths.cv_content)
    payload = build_cv_content(
        application_paths,
        application_paths.fit_map,
        provenance_service.candidate_facts_revision(),
    )
    write_json(path, payload)
    validate_cv_content(path, application_paths=application_paths)
    return payload


def build_cv_content(
    application_paths: ApplicationPaths,
    fit_map_path: Path,
    candidate_facts_revision: str,
    *,
    language: str | None = None,
    positioning_pack: Mapping[str, Any] | None = None,
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
    payload = _build_cv_payload(
        active,
        fit_map,
        source_fit_map=str(resolved_fit_map),
        candidate_facts_revision=candidate_facts_revision,
        application_id=application_paths.application_id,
        language=language or _application_cv_language(application_paths, fit_map),
        positioning_pack=positioning_pack,
    )
    return payload


def build_from_positioning_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_positioning_pack(pack)
    story_text = " ".join(
        str(item).strip()
        for story in validated["stories"]
        for item in (story.get("context"), *(story.get("actions") or []), *(story.get("results") or []))
        if str(item).strip()
    )
    content = f"{validated['thesis']} {story_text} {artifact_claim_text(validated)}".strip()
    return {"content": content, "provenance": artifact_provenance(validated)}


def output_name_for_application(
    application_paths: ApplicationPaths, fit_map: dict[str, Any]
) -> str:
    """Return the validated remote basename for an application CV."""
    identity = read_json(application_paths.identity) if application_paths.identity.is_file() else {}
    active = derived_context_service.ActiveJobContext(
        job_description_path=application_paths.job_description.resolve(),
        fingerprint=sha256_file(application_paths.job_description),
        company=str(identity.get("company") or ""),
        role=str(identity.get("role") or ""),
        source_type=str(identity.get("source_type") or "application_source"),
        source_id=str(identity.get("source_id") or "") or None,
    )
    return _output_name(
        fit_map,
        active=active,
        language=_application_cv_language(application_paths, fit_map),
    )


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
    positioning_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    job_family = _infer_job_family(fit_map)
    selected = _select_experiences(fit_map)
    ensure(4 <= len(selected) <= 8, "cv_content_requires_between_4_and_8_experiences")
    is_en = (language or _cv_language(fit_map)) == "en"
    top8 = _top8_keywords(fit_map)
    selected_with_bullets = [
        _materialize_experience(
            entry,
            job_family,
            language="en" if is_en else "pt-BR",
            ats_keywords=top8,
        )
        for entry in selected
    ]
    coverage = _build_ats_coverage(
        selected_with_bullets,
        top8,
        declared_gap_keywords=fit_map.get("gaps_sem_cobertura") or (),
    )
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
                "period": exp["period"],
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
                "periodo": exp["period"],
                "bullets": [bullet for bullet in exp["bullets"]],
            }
            for exp in selected_with_bullets
        ],
        "education": list(education_list),
        "formacao": _facts_education("pt-BR"),
        "languages": _facts_languages("en" if is_en else "pt-BR"),
        "idiomas": _facts_languages("pt-BR"),
        "stack": _facts_stack(),
        "ats_keyword_coverage": coverage,
        "summary_support": summary_support,
        "positioning": positioning,
    }
    if positioning_pack is not None:
        validated_pack = validate_positioning_pack(positioning_pack)
        payload["positioning_strategy"] = {
            "thesis": validated_pack["thesis"],
            "persona": validated_pack["persona"],
            "story_ids": [story["story_id"] for story in validated_pack["stories"]],
            "claim_ids": list(validated_pack["claims"]),
        }
        payload["metadata"]["positioning_revision_id"] = validated_pack["positioning_revision_id"]
        payload["metadata"]["candidate_evidence_revision_id"] = validated_pack["candidate_evidence_revision_id"]
    if positioning is not None:
        payload["positioning_support"] = {
            "catalog_entry_id": positioning["catalog_entry_id"],
            "caso": positioning["caso"],
            "evidence_id": "",
        }
    _attach_canonical_provenance(payload)
    return payload


def validate_cv_content(
    path: Path | None = None,
    *,
    application_paths: ApplicationPaths | None = None,
) -> dict[str, Any]:
    if application_paths is None:
        raise ValidationFailure("explicit_application_scope_required")
    path = Path(path or application_paths.cv_content)
    ensure(path.exists(), f"cv_content_missing: {path}")
    active = derived_context_service.resolve_active_job_context(application_paths)
    payload = read_json(path)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    ensure(metadata.get("job_fingerprint") == active.fingerprint, "cv_content_stale_for_active_job")
    ensure(str(metadata.get("cargo") or "").strip(), "cv_content_missing_cargo_metadata")
    ensure(str(metadata.get("empresa") or "").strip(), "cv_content_missing_empresa_metadata")
    mock_paths = {
        "cv_content": path,
        "fit_map": application_paths.fit_map,
    }
    applications_v2_service._validate_cv_content_contract(mock_paths)
    return {
        "status": "ok",
        "path": str(path),
        "job_fingerprint": metadata.get("job_fingerprint"),
        "output_name": payload.get("output_name"),
        "experiences_count": len(payload.get("experiences", []) or []),
    }


def active_artifact_status(
    *, application_paths: ApplicationPaths | None = None,
) -> dict[str, Any]:
    if application_paths is None:
        raise ValidationFailure("explicit_application_scope_required")
    active = derived_context_service.resolve_active_job_context(application_paths)
    fit_map_status = fit_map_service.status(
        draft_path=application_paths.fit_map_draft,
        fit_map_path=application_paths.fit_map,
        job_description_path=application_paths.job_description,
        registry_path=application_paths.derived_dir / "keyword_ats_registry.json",
    )
    cv_status = {
        "exists": application_paths.cv_content.exists(),
        "path": str(application_paths.cv_content),
        "matches_active_job": False,
    }
    if application_paths.cv_content.exists():
        payload = read_json(application_paths.cv_content)
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


def invalidate_stale_artifacts(
    *, application_paths: ApplicationPaths | None = None,
) -> dict[str, Any]:
    if application_paths is None:
        raise ValidationFailure("explicit_application_scope_required")
    active = derived_context_service.resolve_active_job_context(application_paths)
    invalidated: list[str] = []
    for path in (application_paths.cv_content,):
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


def _ensure_fit_map_matches_active(
    active: Any, *, application_paths: ApplicationPaths | None = None
) -> None:
    if application_paths is None:
        raise ValidationFailure("explicit_application_scope_required")
    status = fit_map_service.status(
        fit_map_path=application_paths.fit_map,
        job_description_path=active.job_description_path,
        registry_path=application_paths.derived_dir / "keyword_ats_registry.json",
    )
    ensure(status.get("fit_map", {}).get("matches_active_job"), "fit_map_stale_for_active_job")


def _top8_keywords(fit_map: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [item for item in fit_map.get("keywords_habilidade_ats", []) if isinstance(item, dict)]
    entries.sort(key=lambda item: int(item.get("prioridade") or 999))
    return entries[:8]


def _experience_relevance_score(
    entry: dict[str, Any], keywords: list[dict[str, Any]]
) -> int:
    """Score an unselected experience against the vacancy's ATS keywords."""
    focus_terms = {
        _normalize(str(term))
        for term in entry.get("focus_terms", [])
        if str(term).strip()
    }
    keyword_terms = {
        _normalize(str(item.get("keyword") or ""))
        for item in keywords
        if str(item.get("keyword") or "").strip()
    }
    return sum(
        1
        for focus_term in focus_terms
        if any(
            focus_term == keyword_term
            or focus_term in keyword_term
            or keyword_term in focus_term
            for keyword_term in keyword_terms
        )
    )


def _experience_matches_target(experience: dict[str, Any], target: str) -> bool:
    """Match company and role aliases used in FIT_MAP experience targets."""
    alternatives = [part.strip() for part in re.split(r"\s*/\s*", target) if part.strip()]
    if len(alternatives) > 1:
        return any(_experience_matches_target(experience, part) for part in alternatives)
    target_norm = _normalize(target)
    project_scope = {
        "projeto entrega certa": {"trifil_sop"},
    }
    for project_name, allowed_ids in project_scope.items():
        if project_name in target_norm:
            return str(experience.get("id") or "") in allowed_ids
    role = _normalize(str(experience.get("role") or ""))
    company_match = _experience_matches_company_reference(experience, target)
    role_separator = re.search(r"\s[—–|-]\s|\|", target)
    if role and role in target_norm:
        return bool(company_match or not role_separator)
    if not company_match:
        return False

    # A company-only target intentionally matches every role in that company.
    # When a role is present, however, matching the company alone can map a
    # keyword for Trifil Intelligence to Trifil S&OP or Expedição.
    if not role_separator:
        return True

    target_role = re.split(r"\s*[—–|-]\s*|\|", target_norm, maxsplit=1)[-1]
    target_titles = _role_title_groups(target_role)
    experience_titles = _role_title_groups(role)
    target_specific = _role_specific_terms(target_role)
    if not target_titles and "projeto" in target_specific:
        # Project names in the FIT_MAP identify the story, not a job title.
        return True
    if target_titles and experience_titles and not target_titles.intersection(experience_titles):
        return False
    if len(target_titles) > 1 and target_titles.intersection(experience_titles):
        return True

    experience_specific = _role_specific_terms(role)
    if target_titles.intersection(experience_titles) and not target_specific:
        return True
    return bool(target_specific.intersection(experience_specific))


def _experience_matches_company_reference(
    experience: dict[str, Any], reference: str
) -> bool:
    """Match a FIT_MAP story reference against company aliases."""
    reference_norm = _normalize(reference)
    company = str(experience.get("company") or "")
    aliases = [_normalize(company)]
    aliases.extend(
        _normalize(match) for match in re.findall(r"\(([^)]+)\)", company)
    )
    return any(alias and alias in reference_norm for alias in aliases)


_ROLE_TITLE_GROUPS = {
    "head": {"head", "lider", "lideranca"},
    "director": {"director", "diretor", "diretora"},
    "manager": {"manager", "gerente", "gerencia"},
    "coordinator": {"coordinator", "coordenador", "coordenadora"},
}
_ROLE_TERM_ALIASES = {
    "commercial": "commercial",
    "comercial": "commercial",
    "dispatch": "dispatch",
    "expedicao": "dispatch",
    "intelligence": "intelligence",
    "inteligencia": "intelligence",
    "operations": "operations",
    "operation": "operations",
    "operacoes": "operations",
    "operacao": "operations",
    "planning": "planning",
    "planejamento": "planning",
    "s&op": "s&op",
    "sop": "s&op",
}
_ROLE_STOPWORDS = {"a", "as", "and", "da", "das", "de", "do", "dos", "e", "of", "o", "the"}


def _role_title_groups(role: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9&]+", _normalize(role)))
    return {
        group
        for group, aliases in _ROLE_TITLE_GROUPS.items()
        if terms.intersection(aliases)
    }


def _role_specific_terms(role: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9&]+", _normalize(role)))
    title_terms = set().union(*_ROLE_TITLE_GROUPS.values())
    return {
        _ROLE_TERM_ALIASES.get(term, term)
        for term in terms - title_terms - _ROLE_STOPWORDS
    }


def _period_bounds(period: str) -> tuple[int, int]:
    """Return comparable start/end month keys for Portuguese or English periods."""
    months = {
        "jan": 1, "janeiro": 1, "january": 1,
        "fev": 2, "feb": 2, "fevereiro": 2, "february": 2,
        "mar": 3, "marco": 3, "março": 3, "march": 3,
        "abr": 4, "apr": 4, "abril": 4, "april": 4,
        "mai": 5, "may": 5, "maio": 5,
        "jun": 6, "june": 6, "junho": 6,
        "jul": 7, "july": 7, "julho": 7,
        "ago": 8, "aug": 8, "agosto": 8, "august": 8,
        "set": 9, "sep": 9, "setembro": 9, "september": 9,
        "out": 10, "oct": 10, "outubro": 10, "october": 10,
        "nov": 11, "novembro": 11, "november": 11,
        "dez": 12, "dec": 12, "dezembro": 12, "december": 12,
    }
    normalized = _normalize(period)
    if re.search(r"\b(?:present|current|atual)\b", normalized):
        end_override = 10**9
    else:
        end_override = None
    matches = re.findall(r"([a-z]+)\s*/?\s*(\d{4})", normalized)
    if not matches:
        return 0, 0
    keys = [int(year) * 12 + months.get(month, 0) for month, year in matches]
    return keys[0], end_override if end_override is not None else keys[-1]


def _period_end_key(period: str) -> int:
    """Return a comparable month key for Portuguese or English periods."""
    return _period_bounds(period)[1]


def _period_start_key(period: str) -> int:
    """Return the first comparable month key in a career period."""
    return _period_bounds(period)[0]


def _chronological_gaps(
    experiences: list[dict[str, Any]], *, threshold_months: int = 36
) -> list[tuple[int, int, int]]:
    ordered = sorted(
        experiences,
        key=lambda item: _period_start_key(str(item.get("period") or "")),
    )
    gaps: list[tuple[int, int, int]] = []
    for previous, following in zip(ordered, ordered[1:]):
        previous_end = _period_end_key(str(previous.get("period") or ""))
        following_start = _period_start_key(str(following.get("period") or ""))
        gap_months = following_start - previous_end - 1
        if gap_months > threshold_months:
            gaps.append((gap_months, previous_end, following_start))
    return sorted(gaps, reverse=True)


def _experience_covers_gap(
    experience: dict[str, Any], previous_end: int, following_start: int
) -> bool:
    start = _period_start_key(str(experience.get("period") or ""))
    end = _period_end_key(str(experience.get("period") or ""))
    return start <= following_start and end >= previous_end


def _select_experiences(fit_map: dict[str, Any]) -> list[dict[str, Any]]:
    selected_ids: list[str] = []
    facts = _facts_experiences()
    story_companies = []
    stories = fit_map.get("historias_selecionadas", {}) if isinstance(fit_map.get("historias_selecionadas"), dict) else {}
    for key in ("principal", "secundaria", "terceira"):
        story = stories.get(key)
        if isinstance(story, dict):
            story_companies.append(str(story.get("empresa") or ""))
    targets = [str(item.get("experiencia_alvo") or "") for item in _top8_keywords(fit_map)]
    for entry in facts:
        if any(
            _experience_matches_company_reference(entry, company)
            for company in story_companies
            if company
        ):
            selected_ids.append(entry["id"])
            continue
        if any(_experience_matches_target(entry, target) for target in targets):
            selected_ids.append(entry["id"])
    # Fill a short list by relevance first and recency second. The old fixed
    # fallback list promoted ``trifil_expedicao`` by position alone, even for
    # unrelated vacancies, and could exclude a more suitable experience.
    fallback_priority = load_canonical_cv_facts()["selectors"].get(
        "fallback_experience_priority", []
    )
    fallback_rank = {
        item_id: index for index, item_id in enumerate(fallback_priority)
    }
    remaining = [item for item in facts if item["id"] not in selected_ids]
    has_target_keywords = any(
        str(item.get("keyword") or "").strip()
        for item in _top8_keywords(fit_map)
    )
    remaining.sort(
        key=lambda item: (
            -_experience_relevance_score(item, _top8_keywords(fit_map)),
            item["order"],
            fallback_rank.get(item["id"], len(fallback_rank)),
        )
    )
    if len(selected_ids) < 5:
        for item in remaining:
            relevance = _experience_relevance_score(item, _top8_keywords(fit_map))
            if has_target_keywords and relevance <= 0 and len(selected_ids) >= 4:
                break
            if item["id"] not in selected_ids:
                selected_ids.append(item["id"])
            if len(selected_ids) >= 5:
                break

    # Preserve career continuity when there is room in the CV.  Relevance
    # remains the primary selector, but a gap longer than three years is a
    # material omission when a canonical experience can cover it.
    while len(selected_ids) < 8:
        selected = [item for item in facts if item["id"] in selected_ids]
        gaps = _chronological_gaps(selected)
        if not gaps:
            break
        _gap_months, previous_end, following_start = gaps[0]
        gap_candidates = [
            item
            for item in facts
            if item["id"] not in selected_ids
            and _experience_covers_gap(item, previous_end, following_start)
        ]
        if not gap_candidates:
            break
        gap_candidates.sort(
            key=lambda item: (
                _period_end_key(str(item.get("period") or ""))
                - _period_start_key(str(item.get("period") or "")),
                _experience_relevance_score(item, _top8_keywords(fit_map)),
                -_period_start_key(str(item.get("period") or "")),
            ),
            reverse=True,
        )
        selected_ids.append(gap_candidates[0]["id"])

    deduped = [item for item in facts if item["id"] in selected_ids]
    deduped.sort(key=lambda item: (-_period_end_key(str(item.get("period") or "")), item["order"]))
    return deduped[:8]


def _build_ats_coverage(
    selected: list[dict[str, Any]],
    top8: list[dict[str, Any]],
    *,
    declared_gap_keywords: Iterable[str] = (),
) -> list[dict[str, Any]]:
    declared_gaps = {_normalize(str(keyword)) for keyword in declared_gap_keywords}
    coverage: list[dict[str, Any]] = []
    for keyword_entry in top8:
        keyword = str(keyword_entry.get("keyword") or "").strip()
        target = _normalize(str(keyword_entry.get("experiencia_alvo") or ""))
        scoped_ids = _PORTUGUESE_ATS_EXPERIENCE_SCOPE.get(_normalize(keyword), set())
        matching_indices = [
            index
            for index, experience in enumerate(selected)
            if _experience_matches_target(experience, target)
        ]
        # A few historical FIT_MAPs used broad or stale story labels.  When a
        # keyword has a canonical evidence owner, coverage must follow that
        # owner instead of silently attaching the claim to the first selected
        # experience.
        scoped_indices = [
            index
            for index, experience in enumerate(selected)
            if str(experience.get("id") or "") in scoped_ids
        ]
        if scoped_indices and not matching_indices:
            matching_indices = scoped_indices
        if not matching_indices:
            matching_indices = [0]
        keyword_norm = _normalize(keyword)
        matching_with_keyword = [
            index
            for index in matching_indices
            if keyword_norm in _normalize(" ".join(selected[index]["bullets"]))
        ]
        match_index = (matching_with_keyword or matching_indices)[0]
        bullet_index = 0
        bullet_index = _best_bullet_index(selected[match_index]["bullets"], keyword)
        bullet = selected[match_index]["bullets"][bullet_index]
        if _normalize(keyword) in _normalize(bullet):
            coverage_mode = "exact"
        elif any(
            _normalize(variant) in _normalize(bullet)
            for variant in _keyword_translation_variants(keyword)
        ):
            coverage_mode = "similar"
        elif (
            _normalize(keyword) in declared_gaps
            or "gap" in str(keyword_entry.get("origem") or "").casefold()
        ):
            coverage_mode = "declared_gap"
        else:
            coverage_mode = "missing_unexplained"
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
                "coverage_mode": coverage_mode,
                "defensible_evidence": bullet,
            }
        )
    return coverage


def _keyword_translation_variants(keyword: str) -> list[str]:
    """Return curated variants allowed to count as non-exact coverage."""
    registry_path = ROOT / ".agents/skills/career-system/references/keyword_translation_registry.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    normalized_keyword = _normalize(keyword)
    for key, entry in (registry.get("entries") or {}).items():
        if not isinstance(entry, dict):
            continue
        aliases = [key, entry.get("canonical_keyword"), entry.get("en_cv_preferred")]
        if not any(_normalize(str(alias or "")) == normalized_keyword for alias in aliases):
            continue
        variants = [entry.get("pt_br_preferred"), entry.get("en_cv_preferred")]
        variants.extend(entry.get("pt_br_alternatives") or [])
        variants.extend(entry.get("accepted_variants") or [])
        return [str(variant) for variant in variants if str(variant or "").strip()]
    return []


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


def _materialize_experience(
    entry: dict[str, Any],
    job_family: str,
    *,
    language: str = "pt-BR",
    ats_keywords: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if language == "en":
        role, scope, leverage, result = load_canonical_cv_facts()["localized_render_values"]["en"][entry["id"]]
        bullet2 = _positioning_bullet(leverage, result, entry["id"])
        _ensure_quantified_result(result, entry["id"])
        materialized = {
            **entry,
            "role": role,
            "period": _english_period(str(entry["period"])),
            "scope_bullet": scope,
            "result_bullet": result,
            "bullets": [scope, bullet2, result],
            "job_family": job_family,
        }
        if ats_keywords:
            return _apply_defensible_english_ats_keywords(materialized, ats_keywords)
        return materialized
    leverage = entry.get("leverage") if isinstance(entry.get("leverage"), dict) else {}
    result = str(entry.get("result_bullet") or "").strip()
    _ensure_quantified_result(result, str(entry.get("id") or "unknown"))
    leverage_text = _select_leverage_text(leverage, job_family)
    bullet2 = _positioning_bullet(leverage_text, result, str(entry.get("id") or "unknown"))
    bullets = [
        str(entry.get("scope_bullet") or "").strip(),
        bullet2,
        result,
    ]
    return {
        **entry,
        "bullets": bullets,
        "job_family": job_family,
    } if not ats_keywords else _apply_defensible_portuguese_ats_keywords(
        {
            **entry,
            "bullets": bullets,
            "job_family": job_family,
        },
        ats_keywords,
    )


def _ensure_quantified_result(result: str, experience_id: str) -> None:
    if not _contains_quantitative_result(result):
        raise ValidationFailure(
            f"experience {experience_id} result_bullet must contain a defensible metric"
        )


def _contains_quantitative_result(text: str) -> bool:
    """Recognize the numeric evidence required by a concise result bullet."""
    return bool(re.search(r"(?:R\$\s*\d|\b\d+(?:[.,]\d+)?\b)", text or ""))


def _select_leverage_text(leverage: dict[str, Any], job_family: str) -> str:
    keys = [job_family, "default"]
    keys.extend(key for key in sorted(leverage) if key not in keys)
    for key in keys:
        value = leverage.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _positioning_bullet(leverage: str, result: str, experience_id: str) -> str:
    """Keep bullet 2 on mechanism/case and out of quantitative outcomes."""
    fragments = re.split(r"(?<=[.!?])\s+|\s+[—–]\s+|\s*;\s*", leverage or "")
    safe_fragments: list[str] = []
    consequence_starts = (
        "o que ",
        "gerando ",
        "resultando ",
        "which ",
        "generating ",
        "resulting ",
    )
    for fragment in fragments:
        cleaned = fragment.strip(" .;\n\t")
        if not cleaned:
            continue
        lowered = cleaned.casefold()
        if lowered.startswith(consequence_starts) or _contains_quantitative_result(cleaned):
            continue
        safe_fragments.append(cleaned)
    positioning = "; ".join(safe_fragments).strip()
    if positioning and _normalize(positioning) != _normalize(result):
        return f"{positioning}."
    raise ValidationFailure(
        f"experience {experience_id} has no non-quantitative positioning/case for bullet 2"
    )


def _best_bullet_index(bullets: list[str], keyword: str) -> int:
    keyword_norm = _normalize(keyword)
    for index, bullet in enumerate(bullets):
        if keyword_norm in _normalize(bullet):
            return index
    return 0


_ENGLISH_ATS_CLAUSES = {
    "business transformation": "The work connected operating changes to business transformation.",
    "operational excellence": "The cadence reinforced operational excellence through measurable trade-offs.",
    "operations management": "Led operations management across FieldOps, Payments, and New Business.",
    "service operations": "Led service operations across Support, CX, and Back Office.",
    "multi-location operations": "Coordinated multi-location operations through fleet planning and network expansion.",
    "digital conversion": "Drove digital conversion through an SDR pipeline and daily conversion dashboards.",
    "customer retention": "Connected service quality and customer retention to customer-operation routines.",
    "operational efficiency": "Drove operational efficiency through an executive S&OP cadence, using scenarios and trade-offs to allocate fleet and budget.",
    "contribution margin": "Connected service operations to contribution margin through cost, quality, and back-office decisions.",
    "change management": "The rollout used change management to embed the new operating model.",
    "organizational design": "The redesign clarified organizational design as the operation scaled.",
    "process redesign": "The migration relied on process redesign, not only new tooling.",
    "ai transformation": "The work advanced AI transformation in the operation.",
    "digital transformation": "The work accelerated digital transformation in the operation.",
    "cross-functional leadership": "The cadence depended on cross-functional leadership across teams.",
    "ai adoption": "The rollout accelerated AI adoption in the operation.",
    "ai use cases": "Translated customer-operation needs into practical AI use cases.",
    "ai pilots": "Implemented AI pilots in customer operations using human-centered automation.",
    "stakeholder management": "Applied stakeholder management across marketing, product, supply, and operations through an executive S&OP cadence.",
    "data-driven": "Used data-driven decision-making with SQL, Databricks, and real-time operational dashboards.",
    "operating cadence": "The monthly ritual became an operating cadence for cross-functional trade-offs.",
    "program management": "The work applied program management rigor to a multi-team rollout.",
    "senior-management credibility": "The quantified trade-offs strengthened senior-management credibility.",
    "technical literacy": "The work demonstrated technical literacy across data and operations.",
    "leading through influence": "The design required leading through influence across teams.",
    "strategy operations": "The role connected strategy operations to day-to-day execution.",
    "sales & operations planning (s&op)": "Led Sales & Operations Planning (S&OP) across demand, supply, capacity, and service trade-offs.",
    "master production scheduling": "Connected master production scheduling with MRP validation and manufacturing capacity decisions.",
    "capacity planning": "Coordinated capacity planning across production, logistics, and service-level requirements.",
    "demand forecasting": "Used demand forecasting to align the operating plan with capacity, inventory, and service commitments.",
    "inventory management": "Led inventory management across finished goods, brands, and distribution channels.",
    "safety stock": "Managed safety stock policies to balance availability, working capital, and service levels.",
    "lead time management": "Improved lead time management through distribution process redesign.",
    "mrp": "Built an Excel/VBA simulator to validate MRP scenarios before manufacturing decisions were committed.",
    "supply chain": "Managed supply chain planning across demand, inventory, materials, and manufacturing interfaces.",
    "continuous improvement": "Applied continuous improvement to picking, warehousing, and planning processes through operating indicators.",
    "supply chain management": "Led integrated supply chain management across demand planning, materials, sourcing, and manufacturing interfaces.",
    "production scheduling": "Aligned production scheduling with demand, capacity, inventory, and service-level trade-offs.",
    "on-time delivery": "Managed on-time delivery performance through OTIF and fill-rate operating indicators.",
    "infor erp": "Served as a key user for Infor ERP in materials and warehouse operations.",
    "data analysis": "Used data analysis with SQL, Excel/VBA, and operational dashboards to support planning decisions.",
}


_PORTUGUESE_ATS_CLAUSES = {
    "logistica de ultima milha": "Liderei operações de logística de última milha (last mile), conectando cobertura geográfica, frota e nível de serviço.",
    "last mile": "Liderei operações de logística de última milha (last mile), conectando cobertura geográfica, frota e nível de serviço.",
    "gestao de p&l": "Atuei com Gestão de P&L na linha de custo logístico, usando alavancas operacionais e budget.",
    "otif": "Estruturei indicadores de OTIF e fill rate para acompanhar nível de serviço e planejamento integrado.",
    "tms": "Usei um roteirizador logístico proprietário, funcionalmente equivalente a um TMS de mercado, para apoiar rotas e entregas.",
    "gestao de multiplas unidades": "Apliquei Gestão de múltiplas unidades, coordenando FieldOps, frota e expansão geográfica.",
    "desenvolvimento de liderancas": "Apoiei o desenvolvimento de lideranças ao estruturar processos e contratar a liderança da área de CS.",
    "excelencia operacional": "Apliquei excelência operacional ao criar a área de S&OP do zero, integrando demanda, capacidade, estoques e nível de serviço.",
    "produtividade de picking": "Estruturei a produtividade de picking com coletores RF e Wi-Fi e sistema visual de abastecimento, acompanhando os indicadores da expedição e reduzindo pedidos incompletos.",
    "customer experience": "Liderei a operação de Customer Experience (CX), suporte e backoffice, conectando atendimento, produto e dados.",
    "gestao de customer experience": "Atuei na gestão de Customer Experience (CX), conectando atendimento, produto e dados.",
    "gestao de operacoes de atendimento": "Liderei a gestão de operações de atendimento com foco em escala, qualidade e eficiência.",
    "sla de atendimento": "Defini e acompanhei SLA de atendimento para orientar a operação e a experiência do cliente.",
    "csat (satisfacao do cliente)": "Acompanhei CSAT (satisfação do cliente) como indicador de qualidade da operação.",
    "autoatendimento e automacao": "Estruturei autoatendimento e automação para absorver contatos de primeiro nível.",
    "inteligencia artificial aplicada a atendimento": "Estruturei soluções de inteligência artificial aplicada a atendimento com decisão sobre onde manter o humano.",
    "monitoria de qualidade de atendimento": "Estruturei monitoria de qualidade de atendimento com indicadores e ciclos de feedback.",
    "zendesk": "Implantei o Zendesk como plataforma central e integrei três plataformas de atendimento via API.",
    "planejamento estrategico": "Conduzi ciclos de planejamento estratégico, conectando cenários operacionais, alocação de recursos e execução.",
    "governanca operacional": "Estruturei governança operacional com ritos executivos, indicadores e planos de ação para conectar decisão e execução.",
    "lideranca interfuncional": "Exerci liderança interfuncional, coordenando marketing, produto, supply e operação em decisões de crescimento.",
    "automacao de processos": "Liderei automação de processos com inteligência artificial para escalar o atendimento e liberar o time para casos complexos.",
    "escalabilidade operacional": "Conduzi iniciativas de escalabilidade operacional, conectando expansão, capacidade, indicadores e disciplina financeira.",
    "otimizacao de processos": "Apliquei otimização de processos em migrações e rotinas operacionais, conectando tecnologia, dados e eficiência.",
    "planejamento orcamentario": "Conduzi planejamento orçamentário com acompanhamento de budget e cenários de execução.",
    "forecast": "Usei forecast e cenários para alinhar demanda, capacidade e nível de serviço.",
    "analise de investimentos": "Apoiei análise de investimentos com modelagem de ROI para decisões de transformação.",
    "matematica financeira": "Apliquei conceitos de matemática financeira na análise de ROI e viabilidade econômica.",
    "indicadores de negocio": "Acompanhei indicadores de negócio e desempenho para orientar decisões operacionais e financeiras.",
    "precificacao": "Conduzi análises de precificação para calibrar oferta, demanda e alocação de recursos.",
    "margens": "Acompanhei margens e indicadores financeiros para orientar decisões de eficiência operacional.",
    "gestao de mis": "Estruturei a Gestão de MIS com rotinas de indicadores para apoiar a diretoria.",
    "mis (management information system)": "Estruturei um Management Information System (MIS) com rotinas de indicadores para apoiar a diretoria.",
    "inteligencia operacional": "Conectei planejamento de capacidade, indicadores e dashboards à Inteligência Operacional.",
    "business intelligence": "Apoiei a diretoria com Business Intelligence (BI), normalização de dados e rotinas de análise.",
    "dashboards gerenciais": "Estruturei Dashboards Gerenciais e rotinas de modelagem de dados para apoiar decisões executivas.",
    "dashboards gerenciais e executivos": "Estruturei Dashboards Gerenciais e Executivos a partir de dados operacionais para apoiar decisões da diretoria.",
    "automacao de relatorios": "Criei automação de relatórios e rotinas diárias para acelerar a análise da diretoria.",
    "automacao de relatorios e indicadores": "Criei automação de relatórios e indicadores para acelerar a análise da diretoria.",
    "gestao de indicadores": "Estruturei a Gestão de Indicadores com rotinas de acompanhamento para apoiar decisões operacionais.",
    "governanca de dados": "Conectei atendimento, produto e dados com Governança de Dados para orientar a operação.",
    "analise de performance": "Acompanhei Análise de Performance com indicadores de qualidade, tempo e custo da operação.",
    "indicadores de contact center": "Estruturei Indicadores de Contact Center para acompanhar qualidade, SLA e experiência do cliente.",
}

# Some FIT_MAP targets intentionally list alternative stories.  Keep the
# clause itself human-readable while pinning claims whose evidence belongs to
# one specific experience; otherwise a broad target can copy the claim into a
# different company's role.
_PORTUGUESE_ATS_EXPERIENCE_SCOPE = {
    "governanca operacional": {"ifood_diretor_operacoes"},
    "lideranca interfuncional": {"ifood_diretor_operacoes"},
    "automacao de processos": {"wehandle_head_operacoes"},
    "escalabilidade operacional": {"ifood_diretor_operacoes"},
    "otimizacao de processos": {"wehandle_head_operacoes"},
    "gestao de p&l": {"ifood_diretor_operacoes"},
    "otif": {"trifil_sop"},
    "tms": {"ifood_diretor_operacoes"},
    "desenvolvimento de liderancas": {"vivareal_planejamento_operacoes"},
    "excelencia operacional": {"trifil_sop"},
    "produtividade de picking": {"trifil_expedicao"},
}


def _apply_defensible_portuguese_ats_keywords(
    experience: dict[str, Any], keywords: list[dict[str, Any]]
) -> dict[str, Any]:
    """Add targeted, evidence-backed ATS wording to a Portuguese CV.

    Only clauses with canonical evidence are allowed here.  The insertion is
    limited to a selected experience and to the FIT_MAP's top-eight targets;
    it is not a general keyword dump.
    """
    updated = dict(experience)
    bullets = [str(item) for item in experience.get("bullets", [])]
    applicable_bullet2: list[str] = []
    applicable_bullet3: list[str] = []
    current_text = " ".join(bullets)
    for item in sorted(keywords, key=lambda value: int(value.get("prioridade") or 999)):
        keyword = str(item.get("keyword") or "").strip()
        target = _normalize(str(item.get("experiencia_alvo") or ""))
        phrase = _PORTUGUESE_ATS_CLAUSES.get(_normalize(keyword))
        if not keyword or not phrase or not target:
            continue
        scoped_experiences = _PORTUGUESE_ATS_EXPERIENCE_SCOPE.get(_normalize(keyword))
        if scoped_experiences and str(experience.get("id") or "") not in scoped_experiences:
            continue
        if not scoped_experiences and not _experience_matches_target(experience, target):
            continue
        if _normalize(keyword) in _normalize(current_text):
            continue
        if _contains_quantitative_result(phrase):
            applicable_bullet3.append(phrase)
        else:
            applicable_bullet2.append(phrase)
        current_text = f"{current_text} {phrase}"

    if applicable_bullet2:
        additions = " ".join(applicable_bullet2)
        bullets[1 if len(bullets) > 1 else 0] = (
            f"{bullets[1 if len(bullets) > 1 else 0].rstrip()} {additions}"
        )
    if applicable_bullet3 and len(bullets) > 2:
        bullets[2] = f"{bullets[2].rstrip()} {' '.join(applicable_bullet3)}"
    updated["bullets"] = bullets
    return updated


def _apply_defensible_english_ats_keywords(
    experience: dict[str, Any], keywords: list[dict[str, Any]]
) -> dict[str, Any]:
    """Add only targeted, evidence-backed ATS wording to an English CV.

    The generator already selects the right experience for each FIT_MAP keyword,
    but previously discarded that mapping when materializing English bullets. The
    controlled clauses keep the wording factual and place no more than the
    vacancy's targeted keywords into an experience.
    """
    updated = dict(experience)
    bullets = [str(item) for item in experience.get("bullets", [])]
    applicable_bullet2: list[str] = []
    applicable_bullet3: list[str] = []
    current_text = " ".join(bullets)
    for item in sorted(keywords, key=lambda value: int(value.get("prioridade") or 999)):
        keyword = str(item.get("keyword") or "").strip()
        target = _normalize(str(item.get("experiencia_alvo") or ""))
        phrase = _ENGLISH_ATS_CLAUSES.get(_normalize(keyword))
        if not keyword or not phrase or not target:
            continue
        if not _experience_matches_target(experience, target):
            continue
        if _normalize(keyword) in _normalize(current_text):
            continue
        if _contains_quantitative_result(phrase):
            applicable_bullet3.append(phrase)
        else:
            applicable_bullet2.append(phrase)
        current_text = f"{current_text} {phrase}"

    if applicable_bullet2:
        index = 1 if len(bullets) > 1 else 0
        bullets[index] = f"{bullets[index].rstrip()} {' '.join(applicable_bullet2)}"
    if applicable_bullet3 and len(bullets) > 2:
        bullets[2] = f"{bullets[2].rstrip()} {' '.join(applicable_bullet3)}"
    updated["bullets"] = bullets
    return updated


def _build_summary(
    selected: list[dict[str, Any]],
    fit_map: dict[str, Any],
    *,
    positioning: dict[str, Any] | None = None,
    language: str = "pt-BR",
) -> tuple[str, list[dict[str, Any]]]:
    cargo = str(fit_map.get("cargo") or "a vaga")
    support_pairs = _summary_support_pairs(
        selected,
        fit_map=fit_map,
        language=language,
    )
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
        profile = load_canonical_cv_facts()["summary_profiles"][language]
        opening = profile.get("opening") or _summary_opening(fit_map)
        proof = f"Na trajetória recente, liderei {supports[0]['summary_fragment']}. Também conduzi {supports[1]['summary_fragment']}."
        case = str(positioning["caso"]).strip().rstrip(".")
        used_terms = cv_positioning.normalize_tokens(f"{opening} {proof}")
        direction = ""
        if not cv_positioning.normalize_tokens(case).issubset(used_terms):
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
    return summary, supports


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


def _summary_support_pairs(
    selected: list[dict[str, Any]],
    *,
    fit_map: dict[str, Any] | None = None,
    language: str = "pt-BR",
) -> list[tuple[str, int, int]]:
    desired = load_canonical_cv_facts()["selectors"]["summary_priority"]
    summary_fragments = load_canonical_cv_facts()["summary_fragments"][language]
    by_id = {entry["id"]: index for index, entry in enumerate(selected)}
    desired_rank = {experience_id: index for index, experience_id in enumerate(desired)}
    ordered_ids: list[str] = []

    if isinstance(fit_map, dict) and _top8_keywords(fit_map):
        target_stats: dict[str, tuple[int, int]] = {}
        for item in _top8_keywords(fit_map):
            target = str(item.get("experiencia_alvo") or "").strip()
            if not target:
                continue
            priority = int(item.get("prioridade") or 999)
            for experience in selected:
                if not _experience_matches_target(experience, target):
                    continue
                experience_id = str(experience["id"])
                count, first_priority = target_stats.get(experience_id, (0, 999))
                target_stats[experience_id] = (
                    count + 1,
                    min(first_priority, priority),
                )
        ordered_ids.extend(
            sorted(
                target_stats,
                key=lambda experience_id: (
                    -target_stats[experience_id][0],
                    target_stats[experience_id][1],
                    desired_rank.get(experience_id, len(desired_rank)),
                    experience_id,
                ),
            )
        )

    ordered_ids.extend(experience_id for experience_id in desired if experience_id not in ordered_ids)
    pairs: list[tuple[str, int, int]] = []
    for experience_id in ordered_ids:
        if experience_id not in by_id:
            continue
        fragment_data = summary_fragments.get(experience_id)
        if fragment_data is None:
            continue
        fragment, bullet_index = fragment_data
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
        for key in ("cargo", "empresa", "dor_central", "keywords_vaga", "competencias_vaga", "keywords_habilidade_ats", "idioma")
    }


def validate_positioning_contract(payload: dict[str, Any]) -> None:
    positioning = payload.get("positioning")
    if positioning is None:
        return
    if not isinstance(positioning, dict):
        raise ValidationFailure("CV positioning is invalid")
    required = ("catalog_entry_id", "area", "caso", "score", "matched_signals", "catalog_sha256")
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
    language = (payload.get("metadata") or {}).get("language")
    summary = str(payload.get("summary") or payload.get("resumo") or "")
    if language == "pt-BR" and not cv_positioning.normalize_tokens(positioning["caso"]).issubset(
        cv_positioning.normalize_tokens(summary)
    ):
        raise ValidationFailure("CV positioning case is missing from summary")
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
    materialized = [
        _materialize_experience(
            item,
            family,
            language=language,
            ats_keywords=_top8_keywords(fit_map),
        )
        for item in selected
    ]
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
    if payload.get("candidate") != expected_candidate or payload.get("stack") != _facts_stack():
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
