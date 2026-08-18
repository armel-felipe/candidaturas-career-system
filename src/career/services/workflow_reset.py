from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, ROOT
from career.utils import utc_now_iso, write_json
from career.workflow.state_store import DEFAULT_PAYLOAD, WorkflowStateStore


DERIVED_TRANSIENT_FILES = [
    "active_context.json",
    "job_extract.json",
    "job_sections.json",
    "job_requirements.json",
    "job_responsibilities.json",
    "job_company_context.json",
    "job_keywords.json",
    "reference_digest.json",
    "candidate_evidence_pack.json",
    "candidate_evidence_by_theme.json",
    "fit_map_seed.json",
    "cv_input_pack.json",
    "cv_content_seed.json",
    "habilidades_input_pack.json",
    "feras_input_pack.json",
    "cover_letter_input_pack.json",
    "manifest.json",
]


TRANSIENT_FILES = [
    ".career-state/fit_map.draft.json",
    ".career-state/fit_map.json",
    ".career-state/cv_content.json",
    ".career-state/linkedin_job_extract.json",
    ".career-state/linkedin_post_extract.json",
    ".career-state/url_job_extract.json",
    ".career-state/intake_request.json",
    ".career-state/agent_requests/fit-map_request.json",
    ".career-state/agent_requests/fit-map_request.md",
    ".career-state/agent_requests/cv_request.json",
    ".career-state/agent_requests/cv_request.md",
    ".career-state/agent_requests/cover-letter_request.json",
    ".career-state/agent_requests/cover-letter_request.md",
    ".career-state/agent_requests/feras_request.json",
    ".career-state/agent_requests/feras_request.md",
    ".career-state/agent_requests/habilidades_request.json",
    ".career-state/agent_requests/habilidades_request.md",
    ".career-state/agent_requests/notion-update_request.json",
    ".career-state/agent_requests/notion-update_request.md",
    ".career-state/agent_requests/email-draft_request.json",
    ".career-state/agent_requests/email-draft_request.md",
    ".career-state/agent_requests/linkedin_request.json",
    ".career-state/agent_requests/linkedin_request.md",
    ".career-state/harness/menu_state.json",
    ".career-state/harness/pending_input.json",
    ".career-state/derived/job_extract_repair.json",
    "outputs/_tmp/output_review_report.json",
    "outputs/_tmp/polish_review.json",
    "outputs/_tmp/delivery_report.json",
]


def _relative(path: Path) -> str:
    try:
        return str(path.absolute().relative_to(ROOT.absolute()))
    except ValueError:
        return str(path)


def _candidate_paths() -> list[Path]:
    paths = [ROOT / item for item in TRANSIENT_FILES]
    paths.extend((CAREER_STATE / "derived" / item) for item in DERIVED_TRANSIENT_FILES)
    return paths


def _backup_path(path: Path, backup_dir: Path) -> Path:
    rel = path.absolute().relative_to(ROOT.absolute())
    return backup_dir / rel


def operational_reset(*, dry_run: bool = False, backup: bool = True) -> dict[str, Any]:
    """Clear current-job runtime state while preserving captured history and final outputs."""

    existing_paths = [path for path in _candidate_paths() if path.exists()]
    timestamp = utc_now_iso().replace(":", "").replace("+", "_").replace(".", "_")
    backup_dir = CAREER_STATE / "reset_backups" / f"reset_{timestamp}"

    state_store = WorkflowStateStore()
    previous_state = state_store.load()
    actions: list[dict[str, Any]] = []

    if backup and (existing_paths or previous_state):
        actions.append({"action": "backup_state", "path": _relative(backup_dir)})

    for path in existing_paths:
        actions.append({"action": "remove_file", "path": _relative(path)})

    actions.append(
        {
            "action": "clear_active_application_pointer",
            "path": _relative(CAREER_STATE / "active_application.json"),
        }
    )

    if dry_run:
        return {
            "status": "dry_run",
            "backup_enabled": backup,
            "backup_path": _relative(backup_dir) if backup else None,
            "planned_actions": actions,
            "preserved": _preserved_paths(),
            "next_required_step": "run_intake",
        }

    if backup:
        backup_dir.mkdir(parents=True, exist_ok=True)
        write_json(backup_dir / "workflow_state.before.json", previous_state)
        for path in existing_paths:
            destination = _backup_path(path, backup_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)

    for path in existing_paths:
        path.unlink()

    WorkflowStateStore.clear_active_pointer()

    return {
        "status": "reset",
        "backup_enabled": backup,
        "backup_path": _relative(backup_dir) if backup else None,
        "removed_files": [_relative(path) for path in existing_paths],
        "active_pointer": _relative(CAREER_STATE / "active_application.json"),
        "preserved": _preserved_paths(),
        "next_required_step": "run_intake",
        "accepted_commands": [
            "npm run intake:linkedin-job -- --url \"<url>\"",
            "npm run intake:notion-record -- <id_unico>",
            "npm run intake:paste -- --company \"<empresa>\" --role \"<cargo>\" --text-file <arquivo>",
            "npm run intake:url -- --url \"<url>\" --company \"<empresa>\" --role \"<cargo>\"",
        ],
    }


def _preserved_paths() -> list[str]:
    return [
        "analysis history is preserved",
        "inbox/job_descriptions/",
        "outputs/ final artifacts (transient outputs/_tmp reports are reset)",
        ".career-state/derived/keyword_ats_registry.json",
        ".career-state/derived/keyword_translation_candidates.json",
        ".career-state/applications_v2/",
        "inbox/notion/",
        "inbox/linkedin_saved_jobs.json",
        ".career-state/agent_requests/runs/",
        ".career-state/telegram/messages/",
    ]
