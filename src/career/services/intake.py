from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from career.paths import CAREER_STATE, INBOX, ROOT
from career.services import application_context as application_context_service
from career.services import derived_context as derived_context_service
from career.services import fit_map as fit_map_service
from career.services import notion as notion_service
from career.services import project as project_service
from career.services.database import Database
from career.services.persistence.application_repository import ApplicationRecord
from career.tasks.registry import run_task
from career.utils import (
    ValidationFailure,
    read_json,
    sha256_file,
    sha256_text,
    utc_now_iso,
    write_json,
    write_text,
)
from career.workflow.state_store import WorkflowStateStore


DRAFT_PATH = CAREER_STATE / "fit_map.draft.json"
FIT_MAP_PATH = CAREER_STATE / "fit_map.json"
MIN_DESCRIPTION_CHARS = 500
GENERIC_LINKEDIN_COMPANIES = {
    "empresa linkedin",
    "mexico",
    "méxico",
    "brazil",
    "brasil",
    "chile",
    "peru",
    "colombia",
    "costa rica",
    "sao paulo",
    "são paulo",
}
GENERIC_LINKEDIN_ROLES = {"cargo linkedin", "vaga linkedin"}
GENERIC_URL_COMPANIES = {"empresa", "company", "careers", "jobs", "job", "portal", "talent"}
GENERIC_URL_ROLES = {"vaga", "job", "opportunity", "career opportunity"}
INTAKE_STATES_TO_CLEAR = {
    "fit_map_draft_valid",
    "fit_map_built",
    "fit_map_scored",
    "fit_map_validated",
    "cv_review_passed",
}
INTAKE_FINGERPRINTS_TO_CLEAR = {
    "fit_map.validate_draft",
    "fit_map.build",
    "fit_map.score",
    "fit_map.validate",
    "cv.review",
    "cv.approve",
}


@dataclass(frozen=True)
class JobSource:
    """Normalized source accepted by the canonical SQLite intake boundary."""

    source_type: str
    source_id: str | None
    company: str
    role: str
    text: str
    application_id: str | None = None
    notion_id: str | None = None
    record_id: int | str | None = None
    source_url: str | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)
    preferred_id: str | None = None

    def __post_init__(self) -> None:
        if self.application_id is None and self.preferred_id:
            object.__setattr__(self, "application_id", self.preferred_id)


def start_intake(source: JobSource, *, database: Database | None = None) -> ApplicationRecord:
    """Persist canonical intake records before draft/context materialization."""
    if not isinstance(source, JobSource):
        raise TypeError("start_intake requires JobSource")
    fingerprint = sha256_text(source.text)
    paths, record = application_context_service.persist_intake(
        source_type=source.source_type,
        source_id=source.source_id,
        company=source.company,
        role=source.role,
        source_text=source.text,
        fingerprint=fingerprint,
        record_id=source.record_id if source.record_id is not None else source.notion_id,
        preferred_id=source.preferred_id or source.application_id,
        source_url=source.source_url,
        source_metadata=source.source_metadata,
        database=database,
    )
    capture_source(
        paths,
        source_text=source.text,
        source_metadata={
            **source.source_metadata,
            "source_id": source.source_id,
            "source_type": source.source_type,
        },
    )
    compatibility_store = WorkflowStateStore.for_application(
        record.application_id,
        database=database,
    )
    compatibility_store.payload = {
        "active_job": {
            "path": _relative(paths.job_description),
            "fingerprint": fingerprint,
            "company": record.company,
            "role": record.role,
            "source": f"intake.{source.source_type}",
        },
        "active_intake": {
            "application_id": record.application_id,
            "application_dir": _relative(paths.app_dir),
            "source_type": source.source_type,
            "source_id": source.source_id,
            "company": record.company,
            "role": record.role,
            "job_description_path": _relative(paths.job_description),
            "description_chars": len(source.text),
            "fingerprint": fingerprint,
            "status": "job_description_saved",
            "next_required_step": "fill_fit_map_draft",
            "updated_at": utc_now_iso(),
        },
    }
    compatibility_store.save()
    return record


def capture_source(
    application_paths: application_context_service.ApplicationPaths,
    *,
    source_text: str,
    source_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one source only inside its immutable application path set."""
    if not isinstance(source_text, str) or not source_text.strip():
        raise ValidationFailure("source job description must be non-empty text")
    if application_paths.application_id != application_paths.app_dir.name:
        raise ValueError("ApplicationPaths identity does not match its application directory")
    application_paths.app_dir.mkdir(parents=True, exist_ok=True)
    write_text(application_paths.job_description, source_text)
    metadata = dict(source_metadata or {})
    persisted_metadata = {
        "application_id": application_paths.application_id,
        "job_description_path": str(application_paths.job_description),
        "job_fingerprint": sha256_text(source_text),
        "source_id": metadata.get("source_id"),
        "source_type": str(metadata.get("source_type") or "application_source"),
    }
    write_json(application_paths.source_metadata, persisted_metadata)
    return persisted_metadata


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _paths_from_state_store(state_store: WorkflowStateStore) -> application_context_service.ApplicationPaths | None:
    parent = state_store.path.parent
    if parent.parent == application_context_service.APPLICATIONS_DIR:
        return application_context_service.paths_for(parent.name)
    return None


def _draft_path(state_store: WorkflowStateStore) -> Path:
    paths = _paths_from_state_store(state_store)
    return paths.fit_map_draft if paths else DRAFT_PATH


def _fit_map_path(state_store: WorkflowStateStore) -> Path:
    paths = _paths_from_state_store(state_store)
    return paths.fit_map if paths else FIT_MAP_PATH


def _canonical_job_description_path(
    job_description_path: Path,
    application_paths: application_context_service.ApplicationPaths | None,
) -> Path:
    if not application_paths:
        return job_description_path
    text = job_description_path.read_text(encoding="utf-8", errors="replace")
    write_text(application_paths.job_description, text)
    write_text(application_paths.saved_job_description, _relative(job_description_path) + "\n")
    return application_paths.job_description


def _is_generic_linkedin_metadata(company: str | None, role: str | None) -> bool:
    company_key = (company or "").strip().casefold()
    role_key = (role or "").strip().casefold()
    return (
        not company_key
        or not role_key
        or company_key in GENERIC_LINKEDIN_COMPANIES
        or role_key in GENERIC_LINKEDIN_ROLES
    )


def _is_generic_url_metadata(company: str | None, role: str | None) -> bool:
    company_key = (company or "").strip().casefold()
    role_key = (role or "").strip().casefold()
    return (
        not company_key
        or not role_key
        or company_key in GENERIC_URL_COMPANIES
        or role_key in GENERIC_URL_ROLES
    )


def _linkedin_job_key(url: str) -> str:
    match = re.search(r"/jobs/view/(\d+)", str(url or ""))
    return match.group(1) if match else ""


def _saved_job_metadata_hints_for_url(url: str) -> dict[str, str]:
    """Resolve selector metadata for a URL when LinkedIn hides its top card."""
    saved_jobs_path = INBOX / "linkedin_saved_jobs.json"
    if not saved_jobs_path.is_file():
        return {}
    try:
        payload = read_json(saved_jobs_path)
    except (OSError, TypeError, ValueError):
        return {}
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        return {}

    requested_key = _linkedin_job_key(url)
    if not requested_key:
        return {}
    for item in payload["jobs"]:
        if not isinstance(item, dict):
            continue
        item_key = str(item.get("jobId") or "") or _linkedin_job_key(str(item.get("url") or ""))
        if item_key != requested_key:
            continue
        hints = {
            "company": str(item.get("company") or "").strip(),
            "role": str(item.get("title") or "").strip(),
            "location": str(item.get("location") or "").strip(),
        }
        return {key: value for key, value in hints.items() if value}
    return {}


def _load_state(state_store: WorkflowStateStore) -> dict[str, Any]:
    payload = state_store.load()
    payload.setdefault("completed_states", [])
    payload.setdefault("fingerprints", {})
    payload.setdefault("task_history", [])
    return payload


def _sync_global_active_pointer(
    state_store: WorkflowStateStore,
    global_state_store: WorkflowStateStore | None = None,
) -> None:
    """Expose selected application metadata for discovery/display only.

    It is not an execution selector: all task, guard, resume and request
    paths must receive an application ID explicitly.
    """
    application_payload = _load_state(state_store)
    active_intake = application_payload.get("active_intake")
    if not isinstance(active_intake, dict) or not active_intake.get("job_description_path"):
        return
    WorkflowStateStore.write_active_pointer(
        application_id=str(active_intake.get("application_id") or state_store.application_id or ""),
        active_job=application_payload.get("active_job")
        if isinstance(application_payload.get("active_job"), dict)
        else None,
        active_intake=dict(active_intake),
        path=global_state_store.path if global_state_store is not None else None,
    )


def _ensure_scoped_state_store(
    state_store: WorkflowStateStore | None,
    application_id: str,
) -> WorkflowStateStore:
    if state_store is not None and state_store.application_id == application_id:
        return state_store
    return WorkflowStateStore.for_application(application_id)


def _set_active_job(
    state_store: WorkflowStateStore,
    path: Path,
    *,
    source_type: str,
    source_id: str | None,
    company: str | None,
    role: str | None,
) -> dict[str, Any]:
    fingerprint = sha256_file(path)
    active_job = {
        "path": _relative(path),
        "fingerprint": fingerprint,
        "company": company or "",
        "role": role or "",
        "source": f"intake.{source_type}",
    }
    payload = _load_state(state_store)
    payload["active_job"] = active_job
    payload["active_intake"] = {
        "source_type": source_type,
        "source_id": source_id,
        "company": company or "",
        "role": role or "",
        "job_description_path": _relative(path),
        "description_chars": len(path.read_text(encoding="utf-8", errors="replace")),
        "fingerprint": fingerprint,
        "status": "job_description_saved",
        "next_required_step": "npm run fit-map:template",
        "updated_at": utc_now_iso(),
    }
    payload["completed_states"] = sorted(
        (set(payload.get("completed_states", [])) - INTAKE_STATES_TO_CLEAR) | {"job_description_saved"}
    )
    fingerprints = payload.setdefault("fingerprints", {})
    for key in INTAKE_FINGERPRINTS_TO_CLEAR:
        fingerprints.pop(key, None)
    state_store.payload = payload
    state_store.save()
    return active_job


def _mark_template_ready(state_store: WorkflowStateStore, result: dict[str, Any]) -> None:
    payload = _load_state(state_store)
    active = payload.get("active_intake") if isinstance(payload.get("active_intake"), dict) else {}
    draft_path = _draft_path(state_store)
    fit_map_path = _fit_map_path(state_store)
    active.update(
        {
            "status": result["status"],
            "next_required_step": result["next_required_step"],
            "draft_path": _relative(draft_path),
            "fit_map_path": _relative(fit_map_path),
            "updated_at": utc_now_iso(),
        }
    )
    payload["active_intake"] = active
    state_store.payload = payload
    state_store.save()


def _delivery_plan(record_id: int | None = None, job_description_path: Path | None = None) -> dict[str, Any]:
    job_arg = f" --job-description {_relative(job_description_path)}" if job_description_path else ""
    notion_dry_run = (
        f"npm run notion:update-record-current -- {record_id}{job_arg} --dry-run"
        if record_id
        else f"npm run notion:create-current --{job_arg} --dry-run"
    )
    notion_write = (
        f"npm run notion:update-record-current -- {record_id}{job_arg}"
        if record_id
        else f"npm run notion:create-current --{job_arg}"
    )
    return {
        "after_fit_map_draft_filled": [
            {
                "step": "finalize_analysis",
                "command": "npm run fit-map:finalize",
                "purpose": "canonizar, pontuar e validar o FIT_MAP",
            },
            {
                "step": "register_keywords",
                "command": "npm run keywords:register",
                "purpose": "registrar keywords ATS extraídas",
            },
        ],
        "production_outputs": {
            "cv": {
                "skill": "cv-generator",
                "commands": [
                    "npm run cv:docx",
                    "npm run validate:docx",
                    "npm run cv:deliver -- --artifact outputs/<cv>.docx",
                ],
                "gate": "DOCX final só é entrega se cv:deliver aprovar o artefato em outputs/ e registrar status=delivered; cv:approve isolado é gate local/diagnóstico",
            },
            "feras": {
                "skill": "feras-pitch",
                "expected_artifact": "outputs/ ou .career-state/applications_v2/<ID>/feras_formal.md",
                "gate": "rodar output-reviewer após produzir o texto",
            },
            "cover_letter": {
                "skill": "cover-letter",
                "expected_artifact": "outputs/<cover_letter>.md ou outputs/<cover_letter>.docx",
                "gate": "rodar output-reviewer após produzir o documento",
            },
            "habilidades": {
                "skill": "habilidades-chave",
                "commands": [
                    "npm run habilidades:check",
                    "npm run habilidades:validate:gupy -- <arquivo>",
                    "npm run habilidades:validate:mercado-livre -- <arquivo>",
                ],
            },
            "notion_update": {
                "skill": "notion-transactions",
                "dry_run_command": notion_dry_run,
                "write_command": notion_write,
                "gate": "escrita real no Notion exige pedido explícito; dry-run primeiro",
            },
        },
    }


def _status_payload(
    *,
    source_type: str,
    source_id: str | None,
    job_description_path: Path,
    company: str | None,
    role: str | None,
    record_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fit_status = fit_map_service.status(
        draft_path=Path(extra.get("_draft_path")) if extra and extra.get("_draft_path") else DRAFT_PATH,
        fit_map_path=Path(extra.get("_fit_map_path")) if extra and extra.get("_fit_map_path") else FIT_MAP_PATH,
        job_description_path=job_description_path,
    )
    guard = fit_map_service.progress_guard(
        draft_path=Path(extra.get("_draft_path")) if extra and extra.get("_draft_path") else DRAFT_PATH,
        fit_map_path=Path(extra.get("_fit_map_path")) if extra and extra.get("_fit_map_path") else FIT_MAP_PATH,
        job_description_path=job_description_path,
    )
    draft_path = Path(extra.get("_draft_path")) if extra and extra.get("_draft_path") else DRAFT_PATH
    fit_map_path = Path(extra.get("_fit_map_path")) if extra and extra.get("_fit_map_path") else FIT_MAP_PATH
    payload = {
        "status": "ready_for_model_analysis",
        "application_id": extra.get("application_id") if extra else None,
        "fingerprint": extra.get("fingerprint") if extra else None,
        "application_dir": extra.get("application_dir") if extra else None,
        "source_type": source_type,
        "source_id": source_id,
        "company": company or "",
        "role": role or "",
        "record_id": record_id,
        "job_description_path": _relative(job_description_path),
        "description_chars": len(job_description_path.read_text(encoding="utf-8", errors="replace")),
        "draft_path": _relative(draft_path),
        "fit_map_path": _relative(fit_map_path),
        "next_required_step": "fill_fit_map_draft",
        "required_next_command": "editar .career-state/fit_map.draft.json",
        "agent_instruction": (
            "Preencha .career-state/fit_map.draft.json usando career-fit-analysis. "
            "Não entregue análise textual, não calcule nota no chat e não use FIT_MAP antigo antes de finalizar."
        ),
        "fit_map_status": fit_status,
        "guard": guard,
        "delivery_plan": _delivery_plan(record_id=record_id, job_description_path=job_description_path),
    }
    if extra:
        payload["extract"] = {key: value for key, value in extra.items() if not str(key).startswith("_")}
    try:
        payload["derived_context"] = derived_context_service.derived_summary()
    except ValidationFailure:
        payload["derived_context"] = {"status": "blocked", "missing_outputs": ["derived_context_unavailable"]}
    return payload


def _prepare_template(state_store: WorkflowStateStore) -> None:
    run_task("fit_map.template", {"output": str(_draft_path(state_store))}, state_store=state_store)


def _run_ready_pipeline(
    state_store: WorkflowStateStore,
    *,
    source_type: str,
    source_id: str | None,
    job_description_path: Path,
    company: str | None,
    role: str | None,
    record_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not state_store.application_id:
        raise ValidationFailure(
            "ready intake pipeline requires an explicit application_id-scoped state store"
        )
    application_paths = _paths_from_state_store(state_store)
    job_description_path = _canonical_job_description_path(job_description_path, application_paths)
    if not job_description_path.exists():
        raise ValidationFailure(f"Job description file not found: {job_description_path}")
    text = job_description_path.read_text(encoding="utf-8", errors="replace")
    if len(text.strip()) < MIN_DESCRIPTION_CHARS:
        raise ValidationFailure(
            f"Job description has only {len(text.strip())} chars; expected at least {MIN_DESCRIPTION_CHARS}."
        )
    _set_active_job(
        state_store,
        job_description_path,
        source_type=source_type,
        source_id=source_id,
        company=company,
        role=role,
    )
    if application_paths:
        payload = _load_state(state_store)
        active = payload.get("active_intake") if isinstance(payload.get("active_intake"), dict) else {}
        active["application_id"] = application_paths.application_id
        active["application_dir"] = _relative(application_paths.app_dir)
        payload["active_intake"] = active
        state_store.payload = payload
        state_store.save()
    _prepare_template(state_store)
    if application_paths:
        derived_context_service.build_all_for_fit_map(application_paths)
    else:
        derived_context_service.build_all_for_fit_map()
    extra_payload = dict(extra or {})
    if application_paths:
        extra_payload.update(
            {
                "application_id": application_paths.application_id,
                "application_dir": _relative(application_paths.app_dir),
                "_draft_path": str(application_paths.fit_map_draft),
                "_fit_map_path": str(application_paths.fit_map),
            }
        )
    result = _status_payload(
        source_type=source_type,
        source_id=source_id,
        job_description_path=job_description_path,
        company=company,
        role=role,
        record_id=record_id,
        extra=extra_payload,
    )
    _mark_template_ready(state_store, result)
    _sync_global_active_pointer(state_store)
    return result


def from_notion_record(
    record_id: int,
    state_store: WorkflowStateStore | None = None,
    *,
    application_id: str | None = None,
) -> dict[str, Any]:
    token, database_id = notion_service.notion_config()
    result = notion_service.prepare_analysis_from_record(
        token,
        database_id,
        record_id,
        INBOX / "notion",
        INBOX / "job_descriptions",
    )
    path = ROOT / result["job_description_path"]
    source_text = path.read_text(encoding="utf-8", errors="replace")
    application = start_intake(
        JobSource(
            source_type="notion_record",
            source_id=str(record_id),
            company=str(result.get("company") or ""),
            role=str(result.get("role") or ""),
            text=source_text,
            record_id=record_id,
            source_url=str(result.get("source_url") or result.get("url") or "") or None,
            source_metadata=result,
            preferred_id=application_id,
        )
    )
    app_paths = application_context_service.paths_for(application.application_id)
    state_store = _ensure_scoped_state_store(state_store, application.application_id)
    return _run_ready_pipeline(
        state_store,
        source_type="notion_record",
        source_id=str(record_id),
        job_description_path=app_paths.job_description,
        company=result.get("company"),
        role=result.get("role"),
        record_id=record_id,
        extra={**result, "fingerprint": application.fingerprint},
    )


def from_paste(
    *,
    company: str,
    role: str,
    text: str,
    state_store: WorkflowStateStore | None = None,
    application_id: str | None = None,
) -> dict[str, Any]:
    application = start_intake(
        JobSource(
            source_type="pasted_text",
            source_id=None,
            company=company,
            role=role,
            text=text,
            preferred_id=application_id,
        )
    )
    app_paths = application_context_service.paths_for(application.application_id)
    state_store = _ensure_scoped_state_store(state_store, application.application_id)
    output_path = project_service.save_job_description(company, role, text, INBOX / "job_descriptions")
    write_text(app_paths.saved_job_description, _relative(output_path) + "\n")
    return _run_ready_pipeline(
        state_store,
        source_type="pasted_text",
        source_id=None,
        job_description_path=app_paths.job_description,
        company=company,
        role=role,
        extra={"fingerprint": application.fingerprint},
    )


def _run_command(command: list[str]) -> tuple[str, dict[str, Any]]:
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    combined = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    if completed.returncode != 0:
        combined_cf = combined.casefold()
        login_markers = [
            "login is required",
            "login required",
            "not authenticated",
            "authwall",
            "checkpoint",
            "security verification",
            "verificação de segurança",
            "sessão expirada",
            "session expired",
            "run `npm run linkedin:auth`",
            "faça login",
            "fazer login",
        ]
        if any(marker in combined_cf for marker in login_markers):
            raise ValidationFailure(
                "LinkedIn extraction blocked, likely by expired session. Run `npm run linkedin:auth` and retry."
            )
        raise ValidationFailure(f"Command failed ({completed.returncode}): {' '.join(command)}\n{combined[-4000:]}")
    decoder = json.JSONDecoder()
    starts = [match.start() for match in re.finditer(r"\{", completed.stdout)]
    for start in reversed(starts):
        try:
            parsed, _ = decoder.raw_decode(completed.stdout[start:])
            if isinstance(parsed, dict):
                return completed.stdout, parsed
        except json.JSONDecodeError:
            continue
    return completed.stdout, {}


def _canonical_saved_path(raw_output: str, fallback: str | None) -> Path:
    match = re.search(r"Job description saved:\s*(.+)", raw_output)
    if match:
        candidate = ROOT / match.group(1).strip()
        if candidate.exists():
            return candidate
    if fallback:
        candidate = ROOT / fallback
        if candidate.exists():
            return candidate
    raise ValidationFailure("Extraction finished but no saved job description path could be resolved.")


def from_linkedin_job(
    url: str,
    state_store: WorkflowStateStore | None = None,
    *,
    metadata_hints: dict[str, str] | None = None,
    application_id: str | None = None,
) -> dict[str, Any]:
    command = ["npm", "run", "linkedin:extract:authenticated", "--", "--url", url, "--headless"]
    hints = _saved_job_metadata_hints_for_url(url)
    hints.update({key: value for key, value in (metadata_hints or {}).items() if value})
    if hints.get("company"):
        command.extend(["--fallback-company", str(hints["company"])])
    if hints.get("role"):
        command.extend(["--fallback-role", str(hints["role"])])
    if hints.get("location"):
        command.extend(["--fallback-location", str(hints["location"])])
    stdout, result = _run_command(command)
    path = _canonical_saved_path(stdout, result.get("output_path"))
    if _is_generic_linkedin_metadata(result.get("company"), result.get("role")):
        raise ValidationFailure(
            "LinkedIn extraction produced generic or implausible metadata "
            f"(company={result.get('company')!r}, role={result.get('role')!r}). "
            "Fix scripts/linkedin_extract_job.js inference before continuing."
        )
    source_text = path.read_text(encoding="utf-8", errors="replace")
    application = start_intake(
        JobSource(
            source_type="linkedin_job",
            source_id=url,
            company=str(result.get("company") or ""),
            role=str(result.get("role") or ""),
            text=source_text,
            source_url=url,
            source_metadata=result,
            preferred_id=application_id,
        )
    )
    app_paths = application_context_service.paths_for(application.application_id)
    state_store = _ensure_scoped_state_store(state_store, application.application_id)
    return _run_ready_pipeline(
        state_store,
        source_type="linkedin_job",
        source_id=url,
        job_description_path=app_paths.job_description,
        company=result.get("company"),
        role=result.get("role"),
        extra={**result, "fingerprint": application.fingerprint},
    )


def from_linkedin_post(
    *,
    url: str,
    company: str,
    role: str,
    state_store: WorkflowStateStore | None = None,
    application_id: str | None = None,
) -> dict[str, Any]:
    stdout, result = _run_command(
        [
            "npm",
            "run",
            "linkedin:post:extract:authenticated",
            "--",
            "--url",
            url,
            "--headless",
            "--company",
            company,
            "--role",
            role,
        ]
    )
    path = _canonical_saved_path(stdout, result.get("job_output_path"))
    source_text = path.read_text(encoding="utf-8", errors="replace")
    application = start_intake(
        JobSource(
            source_type="linkedin_post",
            source_id=url,
            company=company,
            role=role,
            text=source_text,
            source_url=url,
            source_metadata=result,
            preferred_id=application_id,
        )
    )
    app_paths = application_context_service.paths_for(application.application_id)
    state_store = _ensure_scoped_state_store(state_store, application.application_id)
    return _run_ready_pipeline(
        state_store,
        source_type="linkedin_post",
        source_id=url,
        job_description_path=app_paths.job_description,
        company=company,
        role=role,
        extra={**result, "fingerprint": application.fingerprint},
    )


def from_url(
    *,
    url: str,
    company: str | None,
    role: str | None,
    state_store: WorkflowStateStore | None = None,
    application_id: str | None = None,
) -> dict[str, Any]:
    parsed = urlparse(url)
    host = parsed.hostname.replace("www.", "") if parsed.hostname else ""
    path = parsed.path or ""
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        if "/jobs/" in path or "/job/" in path:
            hints = {key: value for key, value in {"company": company, "role": role}.items() if value}
            return from_linkedin_job(
                url,
                state_store=state_store,
                metadata_hints=hints,
                application_id=application_id,
            )
        if any(marker in path for marker in ["/feed/update/", "/posts/", "/pulse/"]):
            if not company or not role:
                raise ValidationFailure("LinkedIn post intake requires --company and --role.")
            return from_linkedin_post(url=url, company=company, role=role, state_store=state_store, application_id=application_id)
    command = ["npm", "run", "url:extract", "--", "--url", url]
    if company:
        command.extend(["--fallback-company", company])
    if role:
        command.extend(["--fallback-role", role])
    _stdout, result = _run_command(command)
    output_path = result.get("output_path")
    if not output_path:
        raise ValidationFailure(
            "generic_url_extraction_failed: extractor finished without output_path. "
            "Retry `npm run intake:url -- --url \"<url>\"` or paste the raw job text."
        )
    path = ROOT / str(output_path)
    if _is_generic_url_metadata(result.get("company"), result.get("role")):
        raise ValidationFailure(
            "Generic URL extraction produced weak metadata "
            f"(company={result.get('company')!r}, role={result.get('role')!r}). "
            "Retry with --company/--role or paste the raw job text."
        )
    source_text = path.read_text(encoding="utf-8", errors="replace")
    application = start_intake(
        JobSource(
            source_type="external_url",
            source_id=url,
            company=str(result.get("company") or ""),
            role=str(result.get("role") or ""),
            text=source_text,
            source_url=url,
            source_metadata=result,
            preferred_id=application_id,
        )
    )
    app_paths = application_context_service.paths_for(application.application_id)
    state_store = _ensure_scoped_state_store(state_store, application.application_id)
    return _run_ready_pipeline(
        state_store,
        source_type="external_url",
        source_id=url,
        job_description_path=app_paths.job_description,
        company=result.get("company"),
        role=result.get("role"),
        extra={**result, "fingerprint": application.fingerprint},
    )


def resume(state_store: WorkflowStateStore | None = None, *, application_id: str | None = None) -> dict[str, Any]:
    application_id = str(application_id or "").strip()
    if not application_id:
        return {
            "status": "blocked",
            "reason": "explicit_application_scope_required",
            "next_required_step": "supply_application_id",
        }
    if state_store is not None and state_store.application_id not in {None, application_id}:
        return {
            "status": "blocked",
            "reason": "application_scope_mismatch",
            "application_id": application_id,
        }
    # A global state store is discovery metadata, not an execution scope.
    state_store = (
        state_store
        if state_store is not None and state_store.application_id == application_id
        else WorkflowStateStore.for_application(application_id)
    )
    payload = state_store.load()
    active = payload.get("active_intake")
    if not isinstance(active, dict) or not active.get("job_description_path"):
        return {
            "status": "no_active_intake",
            "next_required_step": "run_intake",
            "accepted_commands": [
                "npm run intake:notion-record -- <id_unico>",
                "npm run intake:paste -- --company \"<empresa>\" --role \"<cargo>\" --text-file <arquivo>",
                "npm run intake:linkedin-job -- --url \"<url>\"",
                "npm run intake:linkedin-post -- --url \"<url>\" --company \"<empresa>\" --role \"<cargo>\"",
                "npm run intake:url -- --url \"<url>\" --company \"<empresa>\" --role \"<cargo>\"",
            ],
        }
    active_application_id = str(active.get("application_id") or "").strip()
    if active_application_id != application_id:
        return {
            "status": "blocked",
            "reason": "active_intake_application_mismatch",
            "application_id": application_id,
        }
    path = ROOT / str(active["job_description_path"])
    if not path.exists():
        return {
            "status": "active_intake_broken",
            "job_description_path": active.get("job_description_path"),
            "next_required_step": "rerun_intake",
        }
    fit_status = fit_map_service.status(_draft_path(state_store), _fit_map_path(state_store), path)
    guidance = fit_map_service.resume_guidance(_draft_path(state_store), _fit_map_path(state_store), path)
    return {
        "status": "active_intake_ready",
        "active_intake": active,
        "fit_map_status": fit_status,
        "resume": guidance.get("resume"),
        "next_required_step": guidance.get("resume", {}).get("action"),
        "delivery_plan": _delivery_plan(
            record_id=int(active["source_id"])
            if active.get("source_type") == "notion_record" and str(active.get("source_id", "")).isdigit()
            else None,
            job_description_path=path,
        ),
    }


def write_request_bundle(
    output_path: Path | None = None,
    *,
    application_id: str | None = None,
) -> Path:
    application_id = str(application_id or "").strip()
    if not application_id:
        raise ValueError("write_request_bundle requires application_id")
    payload = resume(application_id=application_id)
    if output_path is None:
        output_path = application_context_service.paths_for(application_id).requests_dir / "intake_request.json"
    write_json(output_path, payload)
    return output_path
