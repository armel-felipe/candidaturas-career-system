from __future__ import annotations

from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, ROOT
from career.services import application_context as application_context_service
from career.services import fit_map as fit_map_service
from career.services import intake as intake_service
from career.services import multiagent as multiagent_service
from career.services.database import Database
from career.services.persistence.application_repository import ApplicationNotFoundError
from career.utils import ValidationFailure
from career.workflow.state_store import WorkflowStateStore


FORBIDDEN_ROOT_PATTERNS = [
    ".extract_notion.py",
    "fetch_notion.py",
    "fetch_notion_v2.py",
    "fetch_record_*.py",
    "gen_*.py",
    "generate_*fitmap*.py",
    "create_drafi.py",
    "create_draft.py",
    "tmp_*.py",
    "query_record.py",
    "query_*_notion.py",
]

FORBIDDEN_ACTIONS = [
    "read_env",
    "copy_notion_token",
    "curl_notion_api",
    "browser_notion_login",
    "web_search_notion_record",
    "grep_local_cache_for_notion_id",
    "create_fetch_or_query_script",
    "invent_npm_command",
    "ask_user_for_notion_auth_when_intake_exists",
]


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def forbidden_root_files() -> list[str]:
    found: list[str] = []
    for pattern in FORBIDDEN_ROOT_PATTERNS:
        found.extend(_relative(path) for path in ROOT.glob(pattern) if path.is_file())
    return sorted(found)


def _active_intake_payload(state_store: WorkflowStateStore) -> dict[str, Any] | None:
    payload = state_store.load()
    active = payload.get("active_intake")
    return active if isinstance(active, dict) else None


def guard(
    state_store: WorkflowStateStore | None = None,
    *,
    application_id: str | None = None,
    fingerprint: str | None = None,
    database: Database | None = None,
) -> dict[str, Any]:
    """Validate a declared, SQLite-resolved application before agent work.

    Active pointers are intentionally not consulted here: they are discovery
    metadata and cannot authorize draft/context creation for an agent.
    """
    application_id = str(application_id or "").strip()
    fingerprint = str(fingerprint or "").strip()
    if not application_id:
        return {
            "status": "blocked",
            "reason": "explicit_application_scope_required",
            "forbidden_actions": FORBIDDEN_ACTIONS,
        }
    if not fingerprint:
        return {
            "status": "blocked",
            "reason": "application_fingerprint_required",
            "application_id": application_id,
            "forbidden_actions": FORBIDDEN_ACTIONS,
        }
    try:
        application = application_context_service.resolve_application(
            application_id=application_id,
            database=database,
            allow_legacy=False,
        )
    except ApplicationNotFoundError:
        return {
            "status": "blocked",
            "reason": "unknown_application",
            "application_id": application_id,
            "forbidden_actions": FORBIDDEN_ACTIONS,
        }
    if application.fingerprint != fingerprint:
        return {
            "status": "blocked",
            "reason": "application_fingerprint_mismatch",
            "application_id": application_id,
            "forbidden_actions": FORBIDDEN_ACTIONS,
        }
    if state_store is not None and state_store.application_id not in {None, application_id}:
        return {
            "status": "blocked",
            "reason": "application_scope_mismatch",
            "application_id": application_id,
            "forbidden_actions": FORBIDDEN_ACTIONS,
        }
    if state_store is None or state_store.application_id is None:
        state_store = WorkflowStateStore.for_application(
            application_id, database=database
        )
    forbidden_files = forbidden_root_files()
    active = _active_intake_payload(state_store)
    application_root = (
        state_store.path.parent.parent
        if state_store.path.parent.parent.name == "applications_v2"
        else None
    )
    application_paths = application_context_service.paths_for(
        application_id, root=application_root
    )

    if forbidden_files:
        return {
            "status": "blocked",
            "reason": "forbidden_temporary_notion_scripts",
            "forbidden_files": forbidden_files,
            "allowed_next_action": "move_or_delete_forbidden_files_then_rerun_agent_guard",
            "allowed_next_command": "npm run agent:guard",
            "forbidden_actions": FORBIDDEN_ACTIONS,
        }

    if not active or not active.get("job_description_path"):
        return {
            "status": "blocked",
            "reason": "no_active_intake",
            "allowed_next_action": "run_intake",
            "allowed_next_commands": [
                "npm run intake:notion-record -- <id_unico>",
                "npm run intake:paste -- --company \"<empresa>\" --role \"<cargo>\" --text-file <arquivo>",
                "npm run intake:linkedin-job -- --url \"<url>\"",
                "npm run intake:linkedin-post -- --url \"<url>\" --company \"<empresa>\" --role \"<cargo>\"",
                "npm run intake:url -- --url \"<url>\" --company \"<empresa>\" --role \"<cargo>\"",
            ],
            "forbidden_actions": FORBIDDEN_ACTIONS,
        }

    active_fingerprint = str(active.get("fingerprint") or "").strip()
    if active_fingerprint and active_fingerprint != fingerprint:
        return {
            "status": "blocked",
            "reason": "application_fingerprint_mismatch",
            "application_id": application_id,
            "forbidden_actions": FORBIDDEN_ACTIONS,
        }
    job_path = application_paths.job_description
    if not job_path.exists():
        return {
            "status": "blocked",
            "reason": "active_intake_job_description_missing",
            "active_intake": active,
            "allowed_next_action": "rerun_intake",
            "allowed_next_command": "npm run intake:resume",
            "forbidden_actions": FORBIDDEN_ACTIONS,
        }

    fit_guard = fit_map_service.progress_guard(
        draft_path=application_paths.fit_map_draft if application_paths else CAREER_STATE / "fit_map.draft.json",
        fit_map_path=application_paths.fit_map if application_paths else CAREER_STATE / "fit_map.json",
        job_description_path=job_path,
    )
    next_step = fit_guard.get("next_required_step")
    if next_step == "preencher .career-state/fit_map.draft.json":
        return {
            "status": "ok",
            "active_intake": active,
            "allowed_next_action": "fill_fit_map_draft",
            "allowed_next_command": "editar .career-state/fit_map.draft.json",
            "must_not_continue_with": FORBIDDEN_ACTIONS + [
                "deliver_textual_analysis",
                "run_notion_fallback",
                "reuse_old_fit_map",
            ],
            "fit_map_guard": fit_guard,
        }
    if next_step == "npm run fit-map:finalize":
        return {
            "status": "ok",
            "active_intake": active,
            "allowed_next_action": "finalize_fit_map",
            "allowed_next_command": "npm run fit-map:finalize",
            "must_not_continue_with": FORBIDDEN_ACTIONS,
            "fit_map_guard": fit_guard,
        }
    if next_step == "python scripts/register_keywords.py --fit-map .career-state/fit_map.json --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json":
        return {
            "status": "ok",
            "active_intake": active,
            "allowed_next_action": "register_keywords",
            "allowed_next_command": "npm run keywords:register",
            "must_not_continue_with": FORBIDDEN_ACTIONS,
            "fit_map_guard": fit_guard,
        }
    return {
        "status": "ok",
        "active_intake": active,
        "allowed_next_action": "follow_fit_map_guard",
        "allowed_next_command": fit_guard.get("required_next_command") or next_step,
        "must_not_continue_with": FORBIDDEN_ACTIONS,
        "fit_map_guard": fit_guard,
    }


def evaluate_notion(record_id: int, state_store: WorkflowStateStore | None = None) -> dict[str, Any]:
    # A Notion evaluation creates/resumes a cellular application.  Passing the
    # legacy global store here makes intake persist the job in the global state
    # while the application identity is written to applications_v2.  Resolve
    # the application first, then guard the same scoped state that intake used.
    intake_result = intake_service.from_notion_record(record_id)
    application_id = str(intake_result.get("application_id") or "").strip()
    fingerprint = str(intake_result.get("fingerprint") or "").strip()
    scoped_state_store = (
        WorkflowStateStore.for_application(application_id)
        if application_id
        else state_store or WorkflowStateStore()
    )
    guard_result = guard(
        state_store=scoped_state_store,
        application_id=application_id,
        fingerprint=fingerprint,
    )
    if guard_result.get("status") != "ok":
        raise ValidationFailure(f"agent guard blocked after intake: {guard_result.get('reason')}")
    return {
        "status": "ok",
        "record_id": record_id,
        "intake": {
            "status": intake_result.get("status"),
            "job_description_path": intake_result.get("job_description_path"),
            "next_required_step": intake_result.get("next_required_step"),
            "description_chars": intake_result.get("description_chars"),
            "fingerprint": fingerprint,
        },
        "guard": guard_result,
    }


def evaluate_notion_local(record_id: int, state_store: WorkflowStateStore | None = None) -> dict[str, Any]:
    """Deterministic entrypoint for smaller/local models.

    Runs the mechanical setup the model repeatedly skips, then returns the
    single compact request it must read before editing the draft.
    """
    state_store = state_store or WorkflowStateStore()
    local_map = multiagent_service.write_local_model_map()
    evaluation = evaluate_notion(record_id, state_store=state_store)
    fit_map_request = multiagent_service.write_request("fit-map")
    return {
        "status": "ok",
        "record_id": record_id,
        "local_model_map": local_map,
        "evaluation": evaluation,
        "fit_map_request": fit_map_request,
        "required_next_action": "read_fit_map_request_then_edit_draft",
        "required_next_file": ".career-state/agent_requests/fit-map_request.md",
        "required_validation_after_edit": "npm run validate:fit-map:draft",
        "do_not": [
            "ask_user_to_fill_draft",
            "reuse_stale_fit_map",
            "invent_evidence_or_numbers",
            "use_partial_json_patches",
            "respond_before_validate_fit_map_draft",
        ],
    }
