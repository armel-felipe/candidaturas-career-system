from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from career.paths import CAREER_STATE, INBOX, ROOT
from career.services import fit_map as fit_map_service
from career.services import notion as notion_service
from career.services import project as project_service
from career.tasks.registry import run_task
from career.utils import ValidationFailure, sha256_file, utc_now_iso, write_json
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


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _is_generic_linkedin_metadata(company: str | None, role: str | None) -> bool:
    company_key = (company or "").strip().casefold()
    role_key = (role or "").strip().casefold()
    return (
        not company_key
        or not role_key
        or company_key in GENERIC_LINKEDIN_COMPANIES
        or role_key in GENERIC_LINKEDIN_ROLES
    )


def _load_state(state_store: WorkflowStateStore) -> dict[str, Any]:
    payload = state_store.load()
    payload.setdefault("completed_states", [])
    payload.setdefault("fingerprints", {})
    payload.setdefault("task_history", [])
    return payload


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
    active.update(
        {
            "status": result["status"],
            "next_required_step": result["next_required_step"],
            "draft_path": _relative(DRAFT_PATH),
            "fit_map_path": _relative(FIT_MAP_PATH),
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
                    "npm run cv:approve -- --artifact outputs/<cv>.docx",
                ],
                "gate": "DOCX final só é entrega se cv:approve aprovar o artefato em outputs/",
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
        draft_path=DRAFT_PATH,
        fit_map_path=FIT_MAP_PATH,
        job_description_path=job_description_path,
    )
    guard = fit_map_service.progress_guard(
        draft_path=DRAFT_PATH,
        fit_map_path=FIT_MAP_PATH,
        job_description_path=job_description_path,
    )
    payload = {
        "status": "ready_for_model_analysis",
        "source_type": source_type,
        "source_id": source_id,
        "company": company or "",
        "role": role or "",
        "record_id": record_id,
        "job_description_path": _relative(job_description_path),
        "description_chars": len(job_description_path.read_text(encoding="utf-8", errors="replace")),
        "draft_path": _relative(DRAFT_PATH),
        "fit_map_path": _relative(FIT_MAP_PATH),
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
        payload["extract"] = extra
    return payload


def _prepare_template(state_store: WorkflowStateStore) -> None:
    run_task("fit_map.template", {"output": str(DRAFT_PATH)}, state_store=state_store)


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
    _prepare_template(state_store)
    result = _status_payload(
        source_type=source_type,
        source_id=source_id,
        job_description_path=job_description_path,
        company=company,
        role=role,
        record_id=record_id,
        extra=extra,
    )
    _mark_template_ready(state_store, result)
    return result


def from_notion_record(record_id: int, state_store: WorkflowStateStore | None = None) -> dict[str, Any]:
    state_store = state_store or WorkflowStateStore()
    token, database_id = notion_service.notion_config()
    result = notion_service.prepare_analysis_from_record(
        token,
        database_id,
        record_id,
        INBOX / "notion",
        INBOX / "job_descriptions",
    )
    path = ROOT / result["job_description_path"]
    return _run_ready_pipeline(
        state_store,
        source_type="notion_record",
        source_id=str(record_id),
        job_description_path=path,
        company=result.get("company"),
        role=result.get("role"),
        record_id=record_id,
        extra=result,
    )


def from_paste(
    *,
    company: str,
    role: str,
    text: str,
    state_store: WorkflowStateStore | None = None,
) -> dict[str, Any]:
    state_store = state_store or WorkflowStateStore()
    output_path = project_service.save_job_description(company, role, text, INBOX / "job_descriptions")
    return _run_ready_pipeline(
        state_store,
        source_type="pasted_text",
        source_id=None,
        job_description_path=output_path,
        company=company,
        role=role,
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


def from_linkedin_job(url: str, state_store: WorkflowStateStore | None = None) -> dict[str, Any]:
    state_store = state_store or WorkflowStateStore()
    stdout, result = _run_command(["npm", "run", "linkedin:extract:authenticated", "--", "--url", url])
    path = _canonical_saved_path(stdout, result.get("output_path"))
    if _is_generic_linkedin_metadata(result.get("company"), result.get("role")):
        raise ValidationFailure(
            "LinkedIn extraction produced generic or implausible metadata "
            f"(company={result.get('company')!r}, role={result.get('role')!r}). "
            "Fix scripts/linkedin_extract_job.js inference before continuing."
        )
    return _run_ready_pipeline(
        state_store,
        source_type="linkedin_job",
        source_id=url,
        job_description_path=path,
        company=result.get("company"),
        role=result.get("role"),
        extra=result,
    )


def from_linkedin_post(
    *,
    url: str,
    company: str,
    role: str,
    state_store: WorkflowStateStore | None = None,
) -> dict[str, Any]:
    state_store = state_store or WorkflowStateStore()
    stdout, result = _run_command(
        [
            "npm",
            "run",
            "linkedin:post:extract:authenticated",
            "--",
            "--url",
            url,
            "--company",
            company,
            "--role",
            role,
        ]
    )
    path = _canonical_saved_path(stdout, result.get("job_output_path"))
    return _run_ready_pipeline(
        state_store,
        source_type="linkedin_post",
        source_id=url,
        job_description_path=path,
        company=company,
        role=role,
        extra=result,
    )


def from_url(
    *,
    url: str,
    company: str | None,
    role: str | None,
    state_store: WorkflowStateStore | None = None,
) -> dict[str, Any]:
    parsed = urlparse(url)
    host = parsed.hostname.replace("www.", "") if parsed.hostname else ""
    path = parsed.path or ""
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        if "/jobs/" in path or "/job/" in path:
            return from_linkedin_job(url, state_store=state_store)
        if any(marker in path for marker in ["/feed/update/", "/posts/", "/pulse/"]):
            if not company or not role:
                raise ValidationFailure("LinkedIn post intake requires --company and --role.")
            return from_linkedin_post(url=url, company=company, role=role, state_store=state_store)
    raise ValidationFailure(
        "unsupported_url_requires_paste: no deterministic extractor exists for this URL. "
        "Paste the job text and run `npm run intake:paste -- --company ... --role ... --text-file ...`."
    )


def resume(state_store: WorkflowStateStore | None = None) -> dict[str, Any]:
    state_store = state_store or WorkflowStateStore()
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
    path = ROOT / str(active["job_description_path"])
    if not path.exists():
        return {
            "status": "active_intake_broken",
            "job_description_path": active.get("job_description_path"),
            "next_required_step": "rerun_intake",
        }
    fit_status = fit_map_service.status(DRAFT_PATH, FIT_MAP_PATH, path)
    guidance = fit_map_service.resume_guidance(DRAFT_PATH, FIT_MAP_PATH, path)
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


def write_request_bundle(output_path: Path = CAREER_STATE / "intake_request.json") -> Path:
    payload = resume()
    write_json(output_path, payload)
    return output_path
