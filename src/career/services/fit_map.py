from __future__ import annotations

import re
from pathlib import Path

try:  # Legacy CLIs add scripts/ directly to sys.path.
    import build_fit_map as legacy_build_fit_map
    import score_fit_map as legacy_score_fit_map
    import validate_fit_map as legacy_validate_fit_map
except ModuleNotFoundError:  # Package/test imports resolve scripts as a namespace.
    from scripts import build_fit_map as legacy_build_fit_map
    from scripts import score_fit_map as legacy_score_fit_map
    from scripts import validate_fit_map as legacy_validate_fit_map

from career.paths import CAREER_STATE, INBOX, ROOT
from career.services import provenance as provenance_service
from career.services.application_context import ApplicationPaths
from career.schemas.fit_map import (
    FitMapDraftSchema,
    FitMapFinalSchema,
    PLACEHOLDER_MARKERS,
    WEAK_PLACEHOLDER_PATTERNS,
    WEAK_PLACEHOLDER_VALUES,
)
from career.utils import ValidationFailure, read_json, sha256_file, write_json


KEYWORD_REGISTRY = Path(".career-state/derived/keyword_ats_registry.json")
SUSPICIOUS_TEXT_MARKERS = (
    "B2P",
    "Engineiro",
    "genericpo",
    "eventtos",
    "omnicaonfavel",
    "construla",
    "operarom",
    "interfície",
    "diferenciais_desejaveis",
)
MOJIBAKE_MARKERS = ("Ã", "Â", "�", "â€", "√")


def write_template(output_path: Path) -> Path:
    write_json(output_path, legacy_build_fit_map.draft_template())
    return output_path


def _iter_strings(value, trail: str = "$"):
    if isinstance(value, str):
        yield trail, value
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_strings(item, f"{trail}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _iter_strings(item, f"{trail}.{key}")


def _placeholder_paths(payload: dict) -> list[str]:
    placeholders: list[str] = []
    for field_path, text in _iter_strings(payload):
        lowered = text.strip().casefold()
        if (
            lowered in WEAK_PLACEHOLDER_VALUES
            or any(pattern.search(text) for pattern in WEAK_PLACEHOLDER_PATTERNS)
            or any(marker.casefold() in lowered for marker in PLACEHOLDER_MARKERS)
        ):
            placeholders.append(field_path)
    return placeholders


def _draft_validation_error(draft: dict | None, placeholders: list[str]) -> str | None:
    if not isinstance(draft, dict) or placeholders:
        return None
    try:
        FitMapDraftSchema(draft).validate()
        legacy_build_fit_map.canonical_fit_map(draft)
    except Exception as exc:
        return f"{exc.__class__.__name__}: {exc}"
    return None


def _safe_read_json(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, None
    try:
        payload = read_json(path)
    except Exception as exc:
        return None, f"{exc.__class__.__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, "JSON root is not an object"
    return payload, None


def _latest_job_description() -> Path | None:
    job_dir = INBOX / "job_descriptions"
    if not job_dir.exists():
        return None
    candidates = [path for path in job_dir.glob("*.md") if path.is_file()]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def _state_path_for_artifact(fit_map_path: Path) -> Path:
    parent = fit_map_path.parent
    if parent != CAREER_STATE and (parent / "workflow_state.json").exists():
        return parent / "workflow_state.json"
    return CAREER_STATE / "workflow_state.json"


def _fit_map_state_fingerprint_match(fit_map_path: Path, job_path: Path | None) -> bool:
    if not job_path or not job_path.exists():
        return False
    state_path = _state_path_for_artifact(fit_map_path)
    if not state_path.exists():
        return False
    state = read_json(state_path)
    active = state.get("active_intake") if isinstance(state.get("active_intake"), dict) else {}
    active_fingerprint = str(active.get("fingerprint") or "").strip()
    task_fingerprints = state.get("fingerprints") if isinstance(state.get("fingerprints"), dict) else {}
    fit_map_task = None
    for task_name in ("fit_map.validate", "fit_map.score", "fit_map.build"):
        payload = task_fingerprints.get(task_name)
        if isinstance(payload, dict):
            fit_map_task = payload
            break
    fit_map_fingerprint = str((fit_map_task or {}).get("active_job_fingerprint") or "").strip()
    job_fingerprint = sha256_file(job_path)
    return bool(
        active_fingerprint
        and fit_map_fingerprint
        and active_fingerprint == fit_map_fingerprint == job_fingerprint
    )


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")


def _application_key(fit_map: dict) -> str:
    return f"{_normalize_key(fit_map.get('empresa'))}__{_normalize_key(fit_map.get('cargo'))}"


def _fit_map_keywords(fit_map: dict) -> set[str]:
    keywords = set()
    for item in fit_map.get("keywords_habilidade_ats", []) or []:
        if isinstance(item, dict):
            keyword = str(item.get("keyword") or "").strip()
            if keyword:
                keywords.add(keyword.casefold())
    return keywords


def _count_items(value) -> int:
    return len(value) if isinstance(value, list) else 0


def _score_summary(payload: dict) -> dict:
    score = payload.get("nota_aderencia") if isinstance(payload.get("nota_aderencia"), dict) else {}
    dimensions = score.get("dimensoes") if isinstance(score.get("dimensoes"), dict) else {}
    return {
        "nota_final": score.get("final"),
        "dimension_points": {
            key: value.get("pontos")
            for key, value in dimensions.items()
            if isinstance(value, dict) and "pontos" in value
        },
    }


def payload_summary(path: Path = CAREER_STATE / "fit_map.json", *, kind: str = "fit_map") -> dict:
    payload, error = _safe_read_json(path)
    if error or not isinstance(payload, dict):
        return {"status": "blocked", "path": str(path), "error": error or "missing_or_invalid_json"}
    summary = {
        "status": "ok",
        "kind": kind,
        "path": str(path),
        "cargo": payload.get("cargo"),
        "empresa": payload.get("empresa"),
        "keywords_vaga_count": _count_items(payload.get("keywords_vaga")),
        "competencias_vaga_count": _count_items(payload.get("competencias_vaga")),
        "mapa_ajuste_count": _count_items(payload.get("mapa_ajuste")),
        "objecoes_count": _count_items(payload.get("objecoes")),
        "keywords_ats_count": _count_items(payload.get("keywords_habilidade_ats")),
        "gaps_count": _count_items(payload.get("gaps_sem_cobertura")),
    }
    summary.update(_score_summary(payload))
    if kind == "fit_map":
        summary["keyword_registration"] = _keywords_registered(payload)
    return summary


def draft_summary(path: Path = CAREER_STATE / "fit_map.draft.json") -> dict:
    summary = payload_summary(path, kind="draft")
    if summary.get("status") != "ok":
        return summary
    payload = read_json(path)
    placeholders = _placeholder_paths(payload) if isinstance(payload, dict) else []
    summary["placeholder_count"] = len(placeholders)
    summary["placeholder_paths_sample"] = placeholders[:10]
    return summary


def registry_summary(
    registry_path: Path = KEYWORD_REGISTRY,
    fit_map_path: Path = CAREER_STATE / "fit_map.json",
) -> dict:
    fit_map, fit_map_error = _safe_read_json(fit_map_path)
    if fit_map_error or not isinstance(fit_map, dict):
        return {"status": "blocked", "reason": fit_map_error or "fit_map_missing", "fit_map": str(fit_map_path)}
    registration = _keywords_registered(fit_map, registry_path=registry_path)
    return {
        "status": "ok" if registration.get("registered") else "blocked",
        "fit_map": str(fit_map_path),
        "registry": str(registry_path),
        "application_key": registration.get("application_key"),
        "registered": registration.get("registered"),
        "updated_at": registration.get("updated_at"),
        "missing_keywords": registration.get("missing_keywords", []),
    }


def _string_hits(payload: dict, markers: tuple[str, ...]) -> list[dict]:
    hits: list[dict] = []
    for path, text in _iter_strings(payload):
        for marker in markers:
            if marker in text:
                hits.append({"path": path, "marker": marker, "sample": text[:160]})
    return hits


def quality_report(
    path: Path = CAREER_STATE / "fit_map.json",
    job_description_path: Path | None = None,
) -> dict:
    payload, error = _safe_read_json(path)
    if error or not isinstance(payload, dict):
        return {"status": "blocked", "path": str(path), "blockers": [error or "missing_or_invalid_json"], "warnings": []}

    job_path = job_description_path or _latest_job_description()
    job_text = job_path.read_text(encoding="utf-8", errors="replace") if job_path and job_path.exists() else ""
    blockers: list[dict | str] = []
    warnings: list[dict | str] = []

    suspicious = _string_hits(payload, SUSPICIOUS_TEXT_MARKERS)
    if suspicious:
        blockers.append({"code": "suspicious_text_markers", "hits": suspicious[:8], "total": len(suspicious)})

    mojibake = _string_hits(payload, MOJIBAKE_MARKERS)
    if mojibake:
        blockers.append({"code": "mojibake_or_encoding_artifact", "hits": mojibake[:8], "total": len(mojibake)})

    payload_text = "\n".join(text for _, text in _iter_strings(payload))
    if "B2B" in job_text and "B2B" not in payload_text:
        blockers.append({"code": "lost_literal_keyword", "keyword": "B2B"})
    if "B2B" in job_text and "B2P" in payload_text:
        blockers.append({"code": "keyword_corruption", "expected": "B2B", "found": "B2P"})

    company = str(payload.get("empresa") or "").strip()
    role = str(payload.get("cargo") or "").strip()
    if job_text:
        lowered_job = job_text.casefold()
        if company and company.casefold() not in lowered_job:
            warnings.append({"code": "company_not_literal_in_job_description", "empresa": company})
        if role and role.casefold() not in lowered_job:
            warnings.append({"code": "role_not_literal_in_job_description", "cargo": role})

    english_fragments = [
        {"path": path, "sample": text[:160]}
        for path, text in _iter_strings(payload)
        if re.search(r"\b(need|coverage|focus|board-ready|end-to-end|lifecycle)\b", text, flags=re.IGNORECASE)
    ]
    if english_fragments:
        warnings.append({"code": "english_fragments_in_ptbr_fit_map", "hits": english_fragments[:6], "total": len(english_fragments)})

    return {
        "status": "blocked" if blockers else "ok",
        "path": str(path),
        "job_description_path": str(job_path) if job_path else None,
        "cargo": payload.get("cargo"),
        "empresa": payload.get("empresa"),
        "blockers": blockers,
        "warnings": warnings,
    }


def _keywords_registered(fit_map: dict, registry_path: Path = KEYWORD_REGISTRY) -> dict:
    if not registry_path.exists():
        return {"registered": False, "reason": "registry_missing", "path": str(registry_path)}

    registry = read_json(registry_path)
    if not isinstance(registry, dict):
        return {"registered": False, "reason": "registry_invalid", "path": str(registry_path)}

    expected_key = _application_key(fit_map)
    expected_keywords = _fit_map_keywords(fit_map)
    for application in registry.get("applications", []) or []:
        if not isinstance(application, dict):
            continue
        if application.get("application_key") != expected_key:
            continue
        registered_keywords = {
            str(record.get("canonical") or record.get("keyword") or "").strip().casefold()
            for record in application.get("keyword_records", []) or []
            if isinstance(record, dict) and str(record.get("canonical") or record.get("keyword") or "").strip()
        }
        missing = sorted(expected_keywords - registered_keywords)
        return {
            "registered": not missing,
            "reason": "ok" if not missing else "missing_keywords",
            "path": str(registry_path),
            "application_key": expected_key,
            "updated_at": application.get("updated_at"),
            "missing_keywords": missing,
        }

    return {
        "registered": False,
        "reason": "application_not_found",
        "path": str(registry_path),
        "application_key": expected_key,
    }


def status(
    draft_path: Path = CAREER_STATE / "fit_map.draft.json",
    fit_map_path: Path = CAREER_STATE / "fit_map.json",
    job_description_path: Path | None = None,
) -> dict:
    job_path = job_description_path or _latest_job_description()
    draft, draft_error = _safe_read_json(draft_path)
    fit_map, fit_map_error = _safe_read_json(fit_map_path)
    draft_placeholders = _placeholder_paths(draft) if isinstance(draft, dict) else []
    draft_validation_error = _draft_validation_error(draft, draft_placeholders)
    fit_map_job_match = _fit_map_state_fingerprint_match(fit_map_path, job_path)
    keyword_registration = {"registered": False, "reason": "fit_map_missing", "path": str(KEYWORD_REGISTRY)}
    if job_path and isinstance(fit_map, dict) and not fit_map_job_match:
        job_text = job_path.read_text(encoding="utf-8", errors="replace").casefold()
        cargo = str(fit_map.get("cargo", "")).casefold()
        empresa = str(fit_map.get("empresa", "")).casefold()
        fit_map_job_match = bool(cargo and empresa and cargo in job_text and empresa in job_text)
    if fit_map_job_match and isinstance(fit_map, dict):
        keyword_registration = _keywords_registered(fit_map)

    if not job_path:
        next_step = "salvar descrição da vaga"
    elif not draft_path.exists() or draft_error:
        next_step = "npm run fit-map:template"
    elif draft_placeholders:
        next_step = "preencher .career-state/fit_map.draft.json"
    elif draft_validation_error:
        next_step = "preencher .career-state/fit_map.draft.json"
    elif not fit_map_job_match:
        next_step = "npm run fit-map:finalize"
    elif not keyword_registration.get("registered"):
        next_step = "python scripts/register_keywords.py --fit-map .career-state/fit_map.json"
    else:
        next_step = "análise concluída"

    return {
        "active_job": {
            "path": str(job_path) if job_path else None,
            "fingerprint": sha256_file(job_path) if job_path and job_path.exists() else None,
        },
        "draft": {
            "path": str(draft_path),
            "exists": draft_path.exists(),
            "valid_json": draft_error is None if draft_path.exists() else None,
            "json_error": draft_error,
            "placeholder_count": len(draft_placeholders),
            "placeholder_paths": draft_placeholders[:20],
            "validation_error": draft_validation_error,
            "cargo": draft.get("cargo") if isinstance(draft, dict) else None,
            "empresa": draft.get("empresa") if isinstance(draft, dict) else None,
        },
        "fit_map": {
            "path": str(fit_map_path),
            "exists": fit_map_path.exists(),
            "valid_json": fit_map_error is None if fit_map_path.exists() else None,
            "json_error": fit_map_error,
            "cargo": fit_map.get("cargo") if isinstance(fit_map, dict) else None,
            "empresa": fit_map.get("empresa") if isinstance(fit_map, dict) else None,
            "matches_active_job": fit_map_job_match,
        },
        "keyword_registration": keyword_registration,
        "next_required_step": next_step,
    }


def resume_guidance(
    draft_path: Path = CAREER_STATE / "fit_map.draft.json",
    fit_map_path: Path = CAREER_STATE / "fit_map.json",
    job_description_path: Path | None = None,
) -> dict:
    current = status(draft_path=draft_path, fit_map_path=fit_map_path, job_description_path=job_description_path)
    next_step = current["next_required_step"]
    guidance = {
        "salvar descrição da vaga": {
            "action": "save_job_description",
            "instruction": "Salve a descrição bruta da vaga antes de qualquer análise.",
            "command": 'python scripts/save_job_description.py --company "<empresa>" --role "<cargo>" --text-file <arquivo>',
        },
        "npm run fit-map:template": {
            "action": "run_template",
            "instruction": "Gere o template canônico e pare a narrativa até o comando concluir.",
            "command": "npm run fit-map:template",
        },
        "preencher .career-state/fit_map.draft.json": {
            "action": "fill_draft",
            "instruction": (
                "Preencha .career-state/fit_map.draft.json agora. "
                "Nao recalcule nota na conversa, nao explique o workflow e nao use o FIT_MAP antigo."
            ),
            "command": "editar .career-state/fit_map.draft.json e depois rodar npm run fit-map:check:extract",
        },
        "npm run fit-map:finalize": {
            "action": "finalize_fit_map",
            "instruction": "Canonize, pontue e valide o draft ja preenchido.",
            "command": "npm run fit-map:finalize",
        },
        "python scripts/register_keywords.py --fit-map .career-state/fit_map.json": {
            "action": "register_keywords",
            "instruction": "Registre as keywords ATS do FIT_MAP validado.",
            "command": "npm run keywords:register",
        },
        "análise concluída": {
            "action": "complete",
            "instruction": "FIT_MAP validado e keywords registradas. A análise pode ser entregue ou usada pelas próximas skills.",
            "command": None,
        },
    }.get(
        next_step,
        {
            "action": "inspect_status",
            "instruction": "Siga exatamente o next_required_step retornado pelo status.",
            "command": next_step,
        },
    )
    return {
        "status": current,
        "resume": guidance,
    }


def progress_guard(
    draft_path: Path = CAREER_STATE / "fit_map.draft.json",
    fit_map_path: Path = CAREER_STATE / "fit_map.json",
    job_description_path: Path | None = None,
) -> dict:
    current = status(draft_path=draft_path, fit_map_path=fit_map_path, job_description_path=job_description_path)
    next_step = current["next_required_step"]
    blocked_steps = {
        "salvar descrição da vaga",
        "npm run fit-map:template",
        "preencher .career-state/fit_map.draft.json",
        "npm run fit-map:finalize",
    }
    blocked = next_step in blocked_steps
    instruction_by_step = {
        "salvar descrição da vaga": "Salve a descrição da vaga antes de analisar.",
        "npm run fit-map:template": "Execute npm run fit-map:template antes de continuar.",
        "preencher .career-state/fit_map.draft.json": (
            "PARE A NARRATIVA. Edite .career-state/fit_map.draft.json agora. "
            "Nao explique o workflow, nao calcule nota no chat e nao use FIT_MAP antigo."
        ),
        "npm run fit-map:finalize": "Execute npm run fit-map:finalize antes de entregar a análise.",
    }
    return {
        "guard": "blocked" if blocked else "clear",
        "blocked": blocked,
        "next_required_step": next_step,
        "instruction": instruction_by_step.get(next_step, "Estado liberado para o próximo passo."),
        "required_next_command": (
            "editar .career-state/fit_map.draft.json"
            if next_step == "preencher .career-state/fit_map.draft.json"
            else next_step
        ),
        "forbidden_when_blocked": [
            "entregar análise textual",
            "recalcular nota na conversa",
            "usar .career-state/fit_map.json antigo",
            "explicar novamente o workflow",
        ] if blocked else [],
        "status": current,
    }


def validate_draft(path: Path) -> dict:
    draft = read_json(path)
    FitMapDraftSchema(draft).validate()
    try:
        legacy_build_fit_map.canonical_fit_map(draft)
    except Exception as exc:  # pragma: no cover - delegated validation
        raise ValidationFailure(f"Draft FIT_MAP invalid: {exc}") from exc
    return draft


def validate_draft_stage(path: Path, stage: str) -> dict:
    draft = read_json(path)
    stage_fields = {
        "extract": ["cargo", "empresa", "dor_central", "keywords_vaga", "competencias_vaga"],
        "map-evidence": ["mapa_ajuste", "objecoes"],
        "score-draft": ["nota_aderencia"],
        "complete-draft": [
            "historias_selecionadas",
            "keywords_habilidade_ats",
            "gaps_sem_cobertura",
        ],
    }
    if stage not in stage_fields:
        raise ValidationFailure(f"Unknown draft stage: {stage}")
    partial = {field: draft.get(field) for field in stage_fields[stage]}
    placeholders = _placeholder_paths(partial)
    if placeholders:
        raise ValidationFailure(
            f"Draft stage {stage} still contains placeholders:\n- " + "\n- ".join(placeholders)
        )
    if stage == "complete-draft":
        validate_draft(path)
    return {"stage": stage, "status": "ok", "path": str(path)}


def build_fit_map(draft_path: Path, output_path: Path) -> Path:
    draft = validate_draft(draft_path)
    fit_map = legacy_build_fit_map.canonical_fit_map(draft)
    write_json(output_path, fit_map)
    return output_path


def score_fit_map(path: Path) -> Path:
    fit_map = read_json(path)
    score_payload = fit_map.get("nota_aderencia")
    if not isinstance(score_payload, dict):
        raise ValidationFailure("nota_aderencia must be an object with dimensoes to be scored")
    fit_map["nota_aderencia"] = legacy_score_fit_map.compute_score(score_payload)
    write_json(path, fit_map)
    return path


def validate_fit_map(path: Path) -> dict:
    fit_map = read_json(path)
    try:
        if legacy_validate_fit_map.main:
            pass
    except Exception:
        pass
    FitMapFinalSchema(fit_map).validate()
    return fit_map


def build_application_fit_map(
    application_paths: ApplicationPaths,
    *,
    expected_job_fingerprint: str,
    candidate_facts_revision: str,
    produced_by_attempt: int,
    contract_version: str,
    draft_path: Path | None = None,
) -> dict:
    """Build and validate a FIT_MAP without consulting global active state."""
    draft_path = Path(draft_path or application_paths.fit_map_draft).resolve()
    _assert_application_path(application_paths, draft_path, "FIT_MAP draft")
    job_path = application_paths.job_description.resolve()
    _assert_application_path(application_paths, job_path, "job description")
    if not job_path.is_file():
        raise ValidationFailure(f"application job description is missing: {job_path}")
    actual_job_fingerprint = sha256_file(job_path)
    if actual_job_fingerprint != expected_job_fingerprint:
        raise ValidationFailure("normalized job fingerprint does not match application job fingerprint")

    manifest_path = application_paths.derived_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        if manifest.get("application_id") != application_paths.application_id:
            raise ValidationFailure("derived manifest belongs to another application")
        if manifest.get("fingerprint") != actual_job_fingerprint:
            raise ValidationFailure("derived manifest job fingerprint mismatch")
        if manifest.get("candidate_facts_revision") != candidate_facts_revision:
            raise ValidationFailure("derived manifest candidate facts revision mismatch")

    draft = validate_draft(draft_path)
    declared = draft.get("provenance") or draft.get("_provenance")
    if isinstance(declared, dict):
        declared_fingerprint = str(declared.get("job_fingerprint") or "")
        if declared_fingerprint and declared_fingerprint != actual_job_fingerprint:
            raise ValidationFailure("FIT_MAP draft job fingerprint mismatch")
        declared_revision = str(declared.get("candidate_facts_revision") or "")
        if declared_revision and declared_revision != candidate_facts_revision:
            raise ValidationFailure("FIT_MAP draft candidate facts revision mismatch")

    payload = legacy_build_fit_map.canonical_fit_map(draft)
    score_payload = payload.get("nota_aderencia")
    if not isinstance(score_payload, dict):
        raise ValidationFailure(
            "nota_aderencia must be an object with dimensoes to be scored"
        )
    payload["nota_aderencia"] = legacy_score_fit_map.compute_score(score_payload)
    payload["provenance"] = provenance_service.fit_map_provenance(
        application_paths,
        candidate_revision=candidate_facts_revision,
        draft_path=draft_path,
        contract_version=contract_version,
        produced_by_attempt=produced_by_attempt,
    )
    validate_application_fit_map(
        payload,
        application_paths=application_paths,
        expected_candidate_facts_revision=candidate_facts_revision,
    )
    return payload


def validate_application_fit_map(
    payload: dict,
    *,
    application_paths: ApplicationPaths,
    expected_candidate_facts_revision: str | None = None,
    expected_draft_sha256: str | None = None,
    expected_contract_version: str | None = None,
    expected_produced_by_attempt: int | None = None,
) -> dict:
    FitMapFinalSchema(payload).validate()
    provenance_service.validate_fit_map_provenance(
        payload,
        application_paths=application_paths,
        expected_candidate_facts_revision=expected_candidate_facts_revision,
        expected_draft_sha256=expected_draft_sha256,
        expected_contract_version=expected_contract_version,
        expected_produced_by_attempt=expected_produced_by_attempt,
    )
    return payload


def _assert_application_path(
    application_paths: ApplicationPaths, path: Path, label: str
) -> Path:
    target = Path(path).resolve()
    try:
        target.relative_to(application_paths.app_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must stay within its application directory") from exc
    return target
