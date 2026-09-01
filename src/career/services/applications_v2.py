from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from career.paths import CAREER_STATE, INBOX, OUTPUTS, ROOT
from career.services import fit_map as fit_map_service
from career.services import habilidades_chave as habilidades_chave_service
from career.services import memory as memory_service
from career.services import notion as notion_service
from career.services import review as review_service
from career.services.harness_supervisor import HarnessSupervisor
from career.services.harness_runs import ExclusiveRunLock
from career.services.application_context import (
    WorkspaceLease,
    canonical_database,
    paths_for,
    workspace_owner_from_env,
)
from career.services.persistence.application_repository import (
    ApplicationNotFoundError,
    ApplicationRepository,
)
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.artifact_repository import ArtifactRepository
from career.services.persistence.gate_repository import GateRepository
from career.services.cell_store import CellStore
from career.cells.serial import serial_stage_report
from career.services.database import Database
from career.services.job_language import detect_job_language
from career.utils import (
    ValidationFailure,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
    write_text,
)


V2_DIR = CAREER_STATE / "applications_v2"
V2_CONFIG = V2_DIR / "config.json"
V2_INDEX = V2_DIR / "index.json"
V2_LOG_DIR = V2_DIR / "_logs"
V2_MAINTENANCE_STATE = V2_DIR / "maintenance_state.json"
NOTION_CACHE = ROOT / "inbox" / "notion" / "applications_cache.json"
KEYWORD_REGISTRY = ROOT / ".career-state" / "derived" / "keyword_ats_registry.json"
TRANSLATION_REGISTRY = ROOT / ".agents/skills/career-system/references/keyword_translation_registry.json"

DEFAULT_CONFIG = {
    "active_model": "",
    "active_variant": "",
    "max_per_run": 2,
    "score_threshold": 6.0,
    "queue_status_aliases": ["Fila Agente", "Aplicação em Análise", "Em análise", "em analise", "Analisando"],
    "reprocess_status_aliases": ["Reprocessar"],
    "running_status": "Fila Agente",
    "low_fit_status": "Aplicação em Análise",
    "success_status": "Aplicação andamento",
    "error_status": "Aplicação em Análise",
    "blocked_review_status": "Aplicação andamento",
    "no_description_status": "Sem descrição de vaga",
    "analyze_retry_max_attempts": 1,
    "repair_max_attempts": 2,
    "llm_session_budget_per_application": 4,
    "maintenance": {
        "enabled": True,
        "refresh": "missing",
        "full_refresh_every_runs": 24,
        "force_full_after_hours": 24,
        "governance_backfill": True,
    },
    "analysis_runner": {
        "kind": "hermes",
        "command": "hermes",
        "agent": "build",
        "timeout_minutes": 90,
    },
    "generation_runner": {
        "kind": "hermes",
        "command": "hermes",
        "agent": "build",
        "timeout_minutes": 90,
    },
    "harness": {
        "fit_map": {
            "auto_finalize": True,
        },
        "approvals": {
            "notion_write": "explicit_request",
            "email_draft": "manual",
        },
    },
}

STAGE_METADATA = {
    "no_description": {"group": "intake", "status": "blocked", "terminal": True, "retryable": False, "next_action": "move_to_no_description_status"},
    "analyze_pending": {"group": "analyze", "status": "pending", "terminal": False, "retryable": True, "next_action": "run_analyze"},
    "analyze_running": {"group": "analyze", "status": "running", "terminal": False, "retryable": True, "next_action": "await_analyze"},
    "analyze_retry_pending": {"group": "analyze", "status": "retry_pending", "terminal": False, "retryable": True, "next_action": "rerun_analyze"},
    "generate_pending": {"group": "generate", "status": "pending", "terminal": False, "retryable": True, "next_action": "run_generate"},
    "generate_running": {"group": "generate", "status": "running", "terminal": False, "retryable": True, "next_action": "await_generate"},
    "repair_pending": {"group": "repair", "status": "pending", "terminal": False, "retryable": True, "next_action": "run_repair"},
    "repair_running": {"group": "repair", "status": "running", "terminal": False, "retryable": True, "next_action": "await_repair"},
    "blocked_review": {"group": "review", "status": "blocked", "terminal": False, "retryable": True, "next_action": "repair_review_blockers"},
    "blocked_review_exhausted": {"group": "review", "status": "blocked", "terminal": True, "retryable": False, "next_action": "manual_review_required"},
    "low_fit": {"group": "decision", "status": "completed", "terminal": True, "retryable": False, "next_action": "wait_for_reprocess_or_manual_followup"},
    "done": {"group": "finalize", "status": "completed", "terminal": True, "retryable": False, "next_action": None},
    "error": {"group": "error", "status": "failed", "terminal": True, "retryable": False, "next_action": "inspect_error_report"},
}


class ApplicationStage(str, Enum):
    """Authoritative lifecycle stages derived from SQLite provenance."""

    INTAKE_PENDING = "intake_pending"
    FIT_MAP_PENDING = "fit_map_pending"
    FIT_MAP_VALIDATED = "fit_map_validated"
    CV_PENDING = "cv_pending"
    CV_REVIEW_PENDING = "cv_review_pending"
    CV_APPROVED = "cv_approved"
    ONEDRIVE_PENDING = "onedrive_pending"
    NOTION_PENDING = "notion_pending"
    CORE_PACKAGE_SEALED = "core_package_sealed"
    POST_PROCESSING_AVAILABLE = "post_processing_available"
    BLOCKED_RECONCILIATION = "blocked_reconciliation"
    FAILED_RETRYABLE = "failed_retryable"


@dataclass(frozen=True)
class ApplicationProjection:
    """Read-only compatibility projection backed exclusively by SQLite."""

    application_id: str
    company: str
    role: str
    notion_id: str | None
    fingerprint: str | None
    stage: ApplicationStage
    next_required_step: str
    fit_map_revision_id: str | None
    cv_artifact_id: str | None
    delivery_profile: str
    base_package_sealed: bool
    compatibility_payload: dict[str, Any]
    observations: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class _StageDecision:
    stage: ApplicationStage
    next_required_step: str
    fit_map_revision_id: str | None
    cv_artifact_id: str | None


def derive_application_stage(application_id: str, db: Database) -> ApplicationStage:
    """Derive an application's lifecycle stage without consulting legacy files."""

    return _derive_application_stage_decision(application_id, db).stage


def build_sqlite_application_projection(
    application_id: str,
    db: Database,
    *,
    legacy_state_path: Path | None = None,
) -> ApplicationProjection:
    """Build the compatibility shape from receipts, artifacts and integrations.

    ``legacy_state_path`` is inspected only to record a drift observation.  It
    never changes the decision returned from the canonical database.
    """

    applications = ApplicationRepository(db)
    try:
        application = applications.resolve(application_id=application_id)
    except ApplicationNotFoundError as exc:
        raise ValueError(f"unknown application: {application_id}") from exc

    decision = _derive_application_stage_decision(application.application_id, db)
    gates = GateRepository(db)
    receipt_payload = gates.compatibility_payload(application.application_id)
    status = "completed" if decision.stage is ApplicationStage.CORE_PACKAGE_SEALED else "pending"
    payload = {
        **receipt_payload,
        "application_id": application.application_id,
        "stage": decision.stage.value,
        "stage_status": status,
        "status": status,
        "next_action": decision.next_required_step,
        "next_required_step": decision.next_required_step,
        "active_job": {
            "application_id": application.application_id,
            "fingerprint": application.fingerprint,
            "company": application.company,
            "role": application.role,
            "source": "sqlite_projection",
        },
    }
    observations = _observe_legacy_stage_divergence(
        application_id=application.application_id,
        decision=decision,
        db=db,
        legacy_state_path=legacy_state_path,
    )
    return ApplicationProjection(
        application_id=application.application_id,
        company=application.company,
        role=application.role,
        notion_id=application.notion_id,
        fingerprint=application.fingerprint,
        stage=decision.stage,
        next_required_step=decision.next_required_step,
        fit_map_revision_id=decision.fit_map_revision_id,
        cv_artifact_id=decision.cv_artifact_id,
        delivery_profile=application.delivery_profile,
        base_package_sealed=decision.stage is ApplicationStage.CORE_PACKAGE_SEALED,
        compatibility_payload=payload,
        observations=observations,
    )


def _derive_application_stage_decision(application_id: str, db: Database) -> _StageDecision:
    applications = ApplicationRepository(db)
    try:
        application = applications.resolve(application_id=application_id)
    except ApplicationNotFoundError as exc:
        raise ValueError(f"unknown application: {application_id}") from exc

    gates = GateRepository(db)
    if not gates.is_satisfied(application_id, "job_description_saved"):
        return _StageDecision(ApplicationStage.INTAKE_PENDING, "save_job_description", None, None)

    gate_step = gates.next_required_step(application_id)
    if gate_step != "build_cv":
        return _StageDecision(ApplicationStage.FIT_MAP_PENDING, gate_step, None, None)

    revision_id = _current_validated_fit_map_revision(application_id, db)
    if revision_id is None:
        return _StageDecision(ApplicationStage.BLOCKED_RECONCILIATION, "reconcile_fit_map_receipts", None, None)

    if application.delivery_profile == "gupy_registration":
        if not _has_verified_notion_registration(application_id, db):
            return _StageDecision(ApplicationStage.NOTION_PENDING, "register_gupy_application", revision_id, None)
        return _StageDecision(ApplicationStage.CORE_PACKAGE_SEALED, "post_processing_available", revision_id, None)

    cv = _latest_cv_for_revision(application_id, revision_id, db)
    if cv is None:
        return _StageDecision(ApplicationStage.FIT_MAP_VALIDATED, "build_cv", revision_id, None)

    artifact_id = str(cv["version_id"])
    if str(cv["status"]) != "review_passed":
        return _StageDecision(ApplicationStage.CV_REVIEW_PENDING, "review_cv", revision_id, artifact_id)
    validation = ArtifactRepository(db).validate_path(artifact_id)
    if not validation.valid:
        return _StageDecision(ApplicationStage.CV_REVIEW_PENDING, "rerun_cv_review", revision_id, artifact_id)

    if not _has_verified_onedrive_delivery(application_id, cv, db):
        return _StageDecision(ApplicationStage.ONEDRIVE_PENDING, "deliver_cv_onedrive", revision_id, artifact_id)
    if not _has_verified_notion_sync(application_id, cv, db):
        return _StageDecision(ApplicationStage.NOTION_PENDING, "sync_notion", revision_id, artifact_id)
    return _StageDecision(ApplicationStage.CORE_PACKAGE_SEALED, "post_processing_available", revision_id, artifact_id)


def _current_validated_fit_map_revision(application_id: str, db: Database) -> str | None:
    try:
        revision_id = AnalysisRepository(db).get_current(application_id).revision_id
    except ValueError:
        return None
    if not GateRepository(db).is_satisfied(application_id, "fit_map_validated", revision_id=revision_id):
        return None
    return revision_id


def _latest_cv_for_revision(application_id: str, revision_id: str, db: Database):
    return db.fetch_one(
        """SELECT version_id, status, run_id, content_hash, source_revision_id,
                      positioning_revision_id
             FROM artifact_versions
            WHERE application_id = ?
              AND kind = 'cv'
              AND source_revision_id = ?
            ORDER BY created_at DESC, version_id DESC
            LIMIT 1""",
        (application_id, revision_id),
    )


def _has_verified_onedrive_delivery(application_id: str, artifact, db: Database) -> bool:
    row = db.fetch_one(
        """SELECT delivery_id, report_path, report_hash, payload_json
             FROM deliveries
            WHERE application_id = ?
              AND artifact_version_id = ?
              AND channel = 'onedrive'
              AND status IN ('delivered', 'validated')
            ORDER BY delivered_at DESC, delivery_id DESC
            LIMIT 1""",
        (application_id, str(artifact["version_id"])),
    )
    if row is None:
        return False
    return _receipt_row_matches_artifact(
        row,
        artifact,
        application_id=application_id,
        require_report=True,
        require_receipt_path=False,
    )


def _has_verified_notion_sync(application_id: str, artifact, db: Database) -> bool:
    row = db.fetch_one(
        """SELECT ns.sync_id, ns.record_id, ns.payload_json
             FROM notion_syncs AS ns
             JOIN notion_records AS nr
               ON nr.record_id = ns.record_id
              AND nr.application_id = ns.application_id
            WHERE ns.application_id = ?
              AND ns.status IN ('succeeded', 'success', 'completed', 'synced')
            ORDER BY synced_at DESC, sync_id DESC
            LIMIT 1""",
        (application_id,),
    )
    if row is None:
        return False
    return _receipt_row_matches_artifact(
        row,
        artifact,
        application_id=application_id,
        require_report=False,
        require_receipt_path=True,
        expected_record_id=str(row["record_id"]),
    )


def _has_verified_notion_registration(application_id: str, db: Database) -> bool:
    """A Gupy application is sealed by its Notion registration, not a CV."""
    row = db.fetch_one(
        """SELECT ns.record_id, ns.payload_json
             FROM notion_syncs AS ns
             JOIN notion_records AS nr
               ON nr.record_id = ns.record_id
              AND nr.application_id = ns.application_id
            WHERE ns.application_id = ?
              AND ns.status IN ('succeeded', 'success', 'completed', 'synced')
            ORDER BY synced_at DESC, sync_id DESC
            LIMIT 1""",
        (application_id,),
    )
    if row is None:
        return False
    try:
        payload = json.loads(str(row["payload_json"] or "{}"))
    except (TypeError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, dict)
        and str(payload.get("application_id") or "") == application_id
        and bool(payload.get("record_id") or row["record_id"])
    )


def _receipt_row_matches_artifact(
    row,
    artifact,
    *,
    application_id: str,
    require_report: bool,
    require_receipt_path: bool,
    expected_record_id: str | None = None,
) -> bool:
    """Verify an external receipt's bytes and its current artifact binding."""

    report_path = str(row["report_path"] or "").strip() if "report_path" in row.keys() else ""
    report_hash = str(row["report_hash"] or "").strip() if "report_hash" in row.keys() else ""
    try:
        payload = json.loads(str(row["payload_json"] or "{}"))
    except (TypeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if not _semantic_receipt_matches(
        payload,
        artifact,
        application_id=application_id,
        expected_record_id=expected_record_id,
    ):
        return False
    if require_report:
        if not report_path or not _valid_sha256(report_hash):
            return False
        report_payload = _read_verified_json(Path(report_path), report_hash)
        if report_payload is None or not _semantic_receipt_matches(
            report_payload,
            artifact,
            application_id=application_id,
            expected_record_id=expected_record_id,
        ):
            return False
    if require_receipt_path:
        receipt_path = str(payload.get("receipt_path") or "").strip()
        receipt_hash = str(payload.get("receipt_hash") or "").strip()
        if not receipt_path or not _valid_sha256(receipt_hash):
            return False
        receipt_payload = _read_verified_json(Path(receipt_path), receipt_hash)
        if receipt_payload is None or not _semantic_receipt_matches(
            receipt_payload,
            artifact,
            application_id=application_id,
            expected_record_id=expected_record_id,
        ):
            return False
    return True


def _semantic_receipt_matches(
    payload: dict[str, Any],
    artifact,
    *,
    application_id: str,
    expected_record_id: str | None,
) -> bool:
    required_fields = {
        "application_id",
        "artifact_version_id",
        "artifact_hash",
        "source_revision_id",
        "positioning_revision_id",
        "run_id",
    }
    if not required_fields.issubset(payload):
        return False
    if str(payload["application_id"]) != application_id:
        return False
    if str(payload["artifact_version_id"]) != str(artifact["version_id"]):
        return False
    if str(payload["artifact_hash"]) != str(artifact["content_hash"]):
        return False
    if str(payload["source_revision_id"]) != str(artifact["source_revision_id"]):
        return False
    if payload["positioning_revision_id"] != artifact["positioning_revision_id"]:
        return False
    if str(payload["run_id"]) != str(artifact["run_id"]):
        return False
    if expected_record_id is not None and str(payload.get("record_id") or "") != expected_record_id:
        return False
    return True


def _read_verified_json(path: Path, expected_hash: str) -> dict[str, Any] | None:
    if not path.is_file() or sha256_file(path) != expected_hash:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _observe_legacy_stage_divergence(
    *,
    application_id: str,
    decision: _StageDecision,
    db: Database,
    legacy_state_path: Path | None,
) -> tuple[dict[str, Any], ...]:
    if legacy_state_path is None or not legacy_state_path.is_file():
        return ()
    try:
        legacy = json.loads(legacy_state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(legacy, dict):
        return ()
    legacy_stage = str(legacy.get("stage") or "").strip()
    legacy_next = str(legacy.get("next_required_step") or legacy.get("next_action") or "").strip()
    if legacy_stage == decision.stage.value and legacy_next in {"", decision.next_required_step}:
        return ()
    details = {
        "legacy_path": str(legacy_state_path),
        "legacy_stage": legacy_stage or None,
        "legacy_next_required_step": legacy_next or None,
        "sqlite_stage": decision.stage.value,
        "sqlite_next_required_step": decision.next_required_step,
    }
    metadata = json.dumps(details, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    existing = db.fetch_one(
        """SELECT id FROM workflow_events
             WHERE application_id = ? AND event = ? AND metadata = ?
             LIMIT 1""",
        (application_id, "application_projection_divergence", metadata),
    )
    if existing is None:
        with db.transaction(immediate=True) as conn:
            conn.execute(
                """INSERT INTO workflow_events
                   (application_id, event, fingerprint, metadata, created_at)
                   VALUES (?, ?, NULL, ?, ?)""",
                (application_id, "application_projection_divergence", metadata, utc_now_iso()),
            )
    return (details,)


@dataclass
class HeartbeatV2Options:
    max_per_run: int | None
    run_agent: bool
    dry_run: bool
    model: str | None = None
    variant: str | None = None
    skip_maintenance: bool = False
    maintenance_refresh: str | None = None
    cellular: bool = False
    workspace_owner: str | None = None
    control_db_id: str | None = None
    release_workspace_lease: bool = False


def _emit(message: str) -> None:
    print(f"[applications-v2] {message}", file=sys.stderr, flush=True)


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "item"))
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") or "item"


def _notion_slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return value or "vaga_sem_nome"


def _normalize_status(value: str) -> str:
    replacements = str.maketrans(
        {"á": "a", "à": "a", "ã": "a", "â": "a", "é": "e", "ê": "e", "í": "i", "ó": "o", "ô": "o", "õ": "o", "ú": "u", "ç": "c"}
    )
    return " ".join((value or "").casefold().translate(replacements).split())


def _record_key(application: dict[str, Any]) -> str:
    if application.get("_explicit_cellular") or application.get("_local_cellular"):
        return str(application.get("application_id") or "")
    record_id = application.get("record_id")
    if record_id is not None:
        return str(record_id)
    return str(application.get("page_id") or application.get("application_id") or "")


def _app_dir(record_key: str) -> Path:
    return V2_DIR / record_key


def _app_paths(app_dir: Path) -> dict[str, Path]:
    return {
        "manifest": app_dir / "manifest.json",
        "state": app_dir / "state.json",
        "job_description": app_dir / "job_description.md",
        "saved_job_description": app_dir / "saved_job_description_path.txt",
        "fit_map_draft": app_dir / "fit_map.draft.json",
        "fit_map": app_dir / "fit_map.json",
        "analysis_request_json": app_dir / "analysis_request.json",
        "analysis_request_md": app_dir / "analysis_request.md",
        "generation_request_json": app_dir / "generation_request.json",
        "generation_request_md": app_dir / "generation_request.md",
        "repair_request_json": app_dir / "repair_request.json",
        "repair_request_md": app_dir / "repair_request.md",
        "cv_input_pack": app_dir / "cv_input_pack.json",
        "cv_content_seed": app_dir / "cv_content_seed.json",
        "feras_input_pack": app_dir / "feras_input_pack.json",
        "habilidades_input_pack": app_dir / "habilidades_input_pack.json",
        "fit_map_notion_payload": app_dir / "fit_map_notion_payload.json",
        "conversation_context": app_dir / "conversation_context.md",
        "cv_content": app_dir / "cv_content.json",
        "feras_formal": app_dir / "feras_formal.md",
        "habilidades_gupy": app_dir / "habilidades_gupy.md",
        "habilidades_mercado_livre": app_dir / "habilidades_mercado_livre.md",
        "cv_review_report": app_dir / "cv_review_report.json",
        "polish_review": app_dir / "polish_review.json",
        "notion_update_payload": app_dir / "notion_update_payload.json",
        "agent_run": app_dir / "agent_run.json",
        "agent_run_analyze": app_dir / "agent_run_analyze.json",
        "agent_run_generate": app_dir / "agent_run_generate.json",
        "agent_run_repair": app_dir / "agent_run_repair.json",
        "run_result": app_dir / "run_result.json",
        "error_report": app_dir / "error_report.json",
        "event_log": app_dir / "event_log.json",
    }


def _set_stage(state: dict[str, Any], stage: str) -> dict[str, Any]:
    metadata = STAGE_METADATA.get(stage, {"group": "unknown", "status": "unknown", "terminal": False, "retryable": False, "next_action": None})
    state["stage"] = stage
    state["stage_group"] = metadata["group"]
    state["stage_status"] = metadata["status"]
    state["terminal"] = metadata["terminal"]
    state["retryable"] = metadata["retryable"]
    state["next_action"] = metadata["next_action"]
    return state


def _write_default_config() -> Path:
    if not V2_CONFIG.exists():
        write_json(V2_CONFIG, DEFAULT_CONFIG)
    return V2_CONFIG


def write_default_config() -> Path:
    return _write_default_config()


def _load_config() -> dict[str, Any]:
    _write_default_config()
    payload = read_json(V2_CONFIG)
    merged = {**DEFAULT_CONFIG, **payload}
    merged["maintenance"] = {**DEFAULT_CONFIG["maintenance"], **payload.get("maintenance", {})}
    merged["analysis_runner"] = {**DEFAULT_CONFIG["analysis_runner"], **payload.get("analysis_runner", {})}
    merged["generation_runner"] = {**DEFAULT_CONFIG["generation_runner"], **payload.get("generation_runner", {})}
    merged["harness"] = {**DEFAULT_CONFIG["harness"], **payload.get("harness", {})}
    merged["harness"]["fit_map"] = {
        **DEFAULT_CONFIG["harness"]["fit_map"],
        **payload.get("harness", {}).get("fit_map", {}),
    }
    merged["harness"]["approvals"] = {
        **DEFAULT_CONFIG["harness"]["approvals"],
        **payload.get("harness", {}).get("approvals", {}),
    }
    merged["success_status"] = notion_service.sanitize_automation_status(str(merged.get("success_status") or ""))
    merged["blocked_review_status"] = notion_service.sanitize_automation_status(str(merged.get("blocked_review_status") or ""))
    return merged


def _run_maintenance_sync(config: dict[str, Any], options: HeartbeatV2Options) -> dict[str, Any] | None:
    maintenance = config.get("maintenance", {}) if isinstance(config.get("maintenance"), dict) else {}
    if options.skip_maintenance or not bool(maintenance.get("enabled", True)):
        return {
            "executed": False,
            "reason": "disabled" if not bool(maintenance.get("enabled", True)) else "skipped_by_option",
        }
    refresh_mode, cadence_reason = _decide_maintenance_refresh_mode(maintenance, options)
    token, database_id = notion_service.notion_config()
    refresh_result = notion_service.refresh_cache(token, database_id, refresh=refresh_mode)
    registry_result = memory_service.rebuild_keyword_registry_from_cache()
    memory_result = memory_service.build_memory_bundle()
    governance_enabled = bool(maintenance.get("governance_backfill", True))
    governance_result = (
        notion_service.backfill_governance(token, database_id, dry_run=options.dry_run)
        if governance_enabled
        else {
            "generated_at": utc_now_iso(),
            "dry_run": options.dry_run,
            "totals": None,
            "reason": "disabled_by_config",
        }
    )
    _write_maintenance_state(refresh_mode)
    outputs_summary = (
        ((refresh_result.get("outputs") or {}).get("summary") or {})
        if isinstance(refresh_result, dict)
        else {}
    )
    sync_summary = ((refresh_result.get("sync") or {}) if isinstance(refresh_result, dict) else {})
    return {
        "executed": True,
        "refresh_mode": refresh_mode,
        "cadence_reason": cadence_reason,
        "refresh": {
            "sync": {
                "generated_at": sync_summary.get("generated_at"),
                "refresh_mode": sync_summary.get("refresh_mode"),
                "remote_total_pages": sync_summary.get("remote_total_pages"),
                "local_files_before": sync_summary.get("local_files_before"),
                "synced_pages": sync_summary.get("synced_pages"),
                "missing_before_sync": sync_summary.get("missing_before_sync"),
                "orphan_local_files": sync_summary.get("orphan_local_files"),
                "invalid_local_files": sync_summary.get("invalid_local_files"),
            },
            "summary": {
                "generated_at": outputs_summary.get("generated_at"),
                "total_pages": outputs_summary.get("total_pages"),
                "applications_with_description": outputs_summary.get("applications_with_description"),
                "coverage": outputs_summary.get("coverage"),
            },
        },
        "registry": {
            "cache_path": registry_result.get("cache_path"),
            "output_path": registry_result.get("output_path"),
            "applications_exported": registry_result.get("applications_exported"),
            "canonical_keywords": registry_result.get("canonical_keywords"),
        },
        "memory": {key: str(value) for key, value in memory_result.items()},
        "governance_backfill": {
            "executed": governance_enabled,
            "generated_at": governance_result.get("generated_at"),
            "dry_run": governance_result.get("dry_run"),
            "totals": governance_result.get("totals"),
            "reason": governance_result.get("reason"),
        },
    }


def _read_maintenance_state() -> dict[str, Any]:
    if V2_MAINTENANCE_STATE.exists():
        payload = read_json(V2_MAINTENANCE_STATE)
        if isinstance(payload, dict):
            return payload
    return {
        "last_refresh_mode": None,
        "last_sync_at": None,
        "last_full_sync_at": None,
        "runs_since_full": 0,
    }


def _write_maintenance_state(refresh_mode: str) -> None:
    state = _read_maintenance_state()
    runs_since_full = 0 if refresh_mode == "full" else int(state.get("runs_since_full") or 0) + 1
    payload = {
        "last_refresh_mode": refresh_mode,
        "last_sync_at": utc_now_iso(),
        "last_full_sync_at": utc_now_iso() if refresh_mode == "full" else state.get("last_full_sync_at"),
        "runs_since_full": runs_since_full,
    }
    write_json(V2_MAINTENANCE_STATE, payload)


def _hours_since(iso_value: str | None) -> float | None:
    if not iso_value:
        return None
    try:
        timestamp = notion_service.legacy_notion.datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
    except ValueError:
        return None
    delta = notion_service.legacy_notion.datetime.now(notion_service.legacy_notion.timezone.utc) - timestamp
    return max(delta.total_seconds() / 3600, 0.0)


def _decide_maintenance_refresh_mode(maintenance: dict[str, Any], options: HeartbeatV2Options) -> tuple[str, str]:
    if options.maintenance_refresh:
        return str(options.maintenance_refresh), "explicit_override"
    default_mode = str(maintenance.get("refresh") or "missing").strip() or "missing"
    state = _read_maintenance_state()
    full_every_runs = int(maintenance.get("full_refresh_every_runs") or 0)
    force_full_after_hours = float(maintenance.get("force_full_after_hours") or 0)
    runs_since_full = int(state.get("runs_since_full") or 0)
    hours_since_full = _hours_since(state.get("last_full_sync_at"))
    if not state.get("last_sync_at"):
        return default_mode, "bootstrap_default_missing"
    if full_every_runs > 0 and runs_since_full >= full_every_runs:
        return "full", f"cadence_runs>={full_every_runs}"
    if force_full_after_hours > 0 and (hours_since_full is None or hours_since_full >= force_full_after_hours):
        return "full", f"cadence_hours>={int(force_full_after_hours)}"
    return default_mode, "default_missing"


def _load_queue(token: str, database_id: str) -> list[dict[str, Any]]:
    payload = notion_service.list_database_applications(token, database_id)
    return payload.get("applications", [])


def _is_reprocess_requested(application: dict[str, Any], config: dict[str, Any]) -> bool:
    aliases = {_normalize_status(item) for item in config.get("reprocess_status_aliases", [])}
    return _normalize_status(str(application.get("status") or "")) in aliases


def _eligible(applications: list[dict[str, Any]], config: dict[str, Any], max_per_run: int | None) -> list[dict[str, Any]]:
    queue_aliases = {_normalize_status(item) for item in config.get("queue_status_aliases", [])}
    reprocess_aliases = {_normalize_status(item) for item in config.get("reprocess_status_aliases", [])}
    selected = []
    for application in applications:
        if application.get("is_archived"):
            continue
        status = _normalize_status(str(application.get("status") or ""))
        if status not in queue_aliases and status not in reprocess_aliases:
            continue
        selected.append(application)

    def sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
        status = _normalize_status(str(item.get("status") or ""))
        priority = 0 if status in reprocess_aliases else 1
        try:
            numeric_record = -int(item.get("record_id") or 0)
        except (TypeError, ValueError):
            numeric_record = 0
        return (priority, numeric_record, str(item.get("page_id") or ""))

    selected.sort(key=sort_key)
    return selected if max_per_run is None else selected[:max_per_run]


_NOTION_PAGE_ID_RE = re.compile(
    r"^(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32})$"
)


def _valid_notion_page_id(value: Any) -> str:
    candidate = str(value or "").strip()
    return candidate if _NOTION_PAGE_ID_RE.fullmatch(candidate) else ""


def _local_cellular_candidates(
    database_path: Path, *, applications_root: Path
) -> list[dict[str, Any]]:
    """Discover active cellular runs created outside the Notion queue.

    LinkedIn/local intakes are deliberately not forced through a synthetic
    Notion queue record.  Only the newest active run per application and only
    runs with a real persisted plan and at least one ready node are eligible.
    """
    database = Database(database_path)
    try:
        rows = database.fetch_all(
            """SELECT ar.application_id, ar.run_id
               FROM application_runs ar
               WHERE ar.status NOT IN ('completed', 'cancelled')
                 AND ar.created_at = (
                   SELECT MAX(latest.created_at)
                   FROM application_runs latest
                   WHERE latest.application_id = ar.application_id
                     AND latest.status NOT IN ('completed', 'cancelled')
                 )
               ORDER BY ar.created_at ASC"""
        )
        store = CellStore(database)
        candidates: list[dict[str, Any]] = []
        for row in rows:
            application_id = str(row["application_id"] or "").strip()
            run_id = str(row["run_id"] or "").strip()
            if not application_id or not run_id:
                continue
            paths = paths_for(application_id, root=applications_root)
            if not (paths.job_description.is_file() and (paths.plans_dir / f"{run_id}.json").is_file()):
                continue
            try:
                ready_nodes = store.list_ready_nodes(run_id)
            except (KeyError, OSError, ValueError):
                continue
            if not ready_nodes:
                continue
            identity = read_json(paths.identity) if paths.identity.is_file() else {}
            aliases = identity.get("aliases") if isinstance(identity.get("aliases"), dict) else {}
            record_id = str(aliases.get("notion_record_id") or "").strip()
            page_id = _valid_notion_page_id(aliases.get("notion_page_id"))
            candidates.append(
                {
                    "application_id": application_id,
                    "record_id": int(record_id) if record_id.isdigit() else None,
                    "page_id": page_id or None,
                    "company": str(identity.get("company") or ""),
                    "role": str(identity.get("role") or ""),
                    "title": str(identity.get("role") or ""),
                    "status": "Fila Agente",
                    "description": paths.job_description.read_text(encoding="utf-8"),
                    "source_type": str(identity.get("source_type") or "local"),
                    "source_id": str(identity.get("source_id") or application_id),
                    "source_url": str(identity.get("source_url") or ""),
                    "_cellular_run_id": run_id,
                    "_local_cellular": True,
                }
            )
        return candidates
    finally:
        database.close()


def _write_package(application: dict[str, Any], *, reset: bool = False) -> tuple[Path, dict[str, Path]]:
    record_key = _record_key(application)
    app_dir = _app_dir(record_key)
    if reset and app_dir.exists():
        shutil.rmtree(app_dir)
    app_dir.mkdir(parents=True, exist_ok=True)
    paths = _app_paths(app_dir)
    description = str(application.get("description") or "").strip()
    company = str(application.get("company") or "empresa")
    role = str(application.get("role") or application.get("title") or "cargo")
    job_language = detect_job_language(description) if description else None
    required_cv_language = "en" if job_language == "en" else "pt-BR"
    required_cv_filename_suffix = "_en" if required_cv_language == "en" else ""
    write_text(paths["job_description"], description + ("\n" if description else ""))
    if description:
        saved_job_description = _write_canonical_job_description(description, company=company, role=role)
        write_text(paths["saved_job_description"], str(saved_job_description))
    write_json(
        paths["manifest"],
        {
            "record_key": record_key,
            "record_id": application.get("record_id"),
            "page_id": application.get("page_id"),
            "title": application.get("title"),
            "company": application.get("company"),
            "role": application.get("role"),
            "status": application.get("status"),
            "job_description_chars": len(description),
            "job_description_language": job_language,
            "required_cv_language": required_cv_language,
            "required_cv_filename_suffix": required_cv_filename_suffix,
            "saved_job_description_path": str(paths["saved_job_description"]) if paths["saved_job_description"].exists() else None,
            "updated_at": utc_now_iso(),
        },
    )
    if not paths["fit_map_draft"].exists():
        write_json(paths["fit_map_draft"], fit_map_service.legacy_build_fit_map.draft_template())
    return app_dir, paths


def _read_state(paths: dict[str, Path], record_key: str, application: dict[str, Any]) -> dict[str, Any]:
    if paths["state"].exists():
        payload = read_json(paths["state"])
        if isinstance(payload, dict):
            if payload.get("stage"):
                _set_stage(payload, str(payload["stage"]))
            return payload
    return _set_stage({
        "record_key": record_key,
        "score": None,
        "status": application.get("status"),
        "review_status": "pending",
        "polish_status": "pending",
        "output_docx": None,
        "notion_status": application.get("status"),
        "last_error": None,
        "retry_count_analyze": 0,
        "repair_attempt_count": 0,
        "llm_session_count": 0,
        "llm_stage_attempts": {},
        "updated_at": utc_now_iso(),
    }, "analyze_pending")


def _saved_job_descriptions_dir() -> Path:
    path = INBOX / "job_descriptions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_canonical_job_description(text: str, *, company: str, role: str) -> Path:
    output_dir = _saved_job_descriptions_dir()
    output_path = output_dir / f"{_notion_slug(company or 'empresa')}_{_notion_slug(role or 'cargo')}.md"
    write_text(output_path, text if text.endswith("\n") else text + "\n")
    return output_path


def _sync_saved_job_description(paths: dict[str, Path], *, company: str, role: str) -> Path | None:
    if not paths["job_description"].exists():
        return None
    text = paths["job_description"].read_text(encoding="utf-8")
    if not text.strip():
        return None
    output_path = _write_canonical_job_description(text, company=company, role=role)
    write_text(paths["saved_job_description"], str(output_path))
    return output_path


def _load_saved_job_description_path(paths: dict[str, Path]) -> Path | None:
    if not paths["saved_job_description"].exists():
        return None
    candidate = Path(paths["saved_job_description"].read_text(encoding="utf-8").strip())
    return candidate if str(candidate).strip() and candidate.exists() else None


def _write_state(paths: dict[str, Path], payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now_iso()
    write_json(paths["state"], payload)


def _append_event(paths: dict[str, Path], event_type: str, **data: Any) -> None:
    payload = read_json(paths["event_log"]) if paths["event_log"].exists() else {"events": []}
    payload.setdefault("events", []).append(
        {
            "at": utc_now_iso(),
            "type": event_type,
            "data": data,
        }
    )
    write_json(paths["event_log"], payload)


def _fit_score(path: Path) -> float | None:
    if not path.exists():
        return None
    payload = read_json(path)
    score = payload.get("nota_aderencia", {}).get("final")
    if isinstance(score, (int, float)):
        return float(score)
    return None


def _current_llm_session_count(state: dict[str, Any]) -> int:
    return int(state.get("llm_session_count") or 0)


def _llm_session_budget(config: dict[str, Any]) -> int:
    return max(int(config.get("llm_session_budget_per_application") or 0), 0)


def _remaining_llm_sessions(state: dict[str, Any], config: dict[str, Any]) -> int | None:
    budget = _llm_session_budget(config)
    if budget <= 0:
        return None
    return max(budget - _current_llm_session_count(state), 0)


def _consume_llm_session_budget(
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    stage: str,
    paths: dict[str, Path],
) -> None:
    budget = _llm_session_budget(config)
    current = _current_llm_session_count(state)
    if budget > 0 and current >= budget:
        remaining = _remaining_llm_sessions(state, config)
        _append_event(
            paths,
            "llm_budget_blocked",
            stage=stage,
            llm_session_count=current,
            llm_session_budget=budget,
            llm_session_remaining=remaining,
        )
        raise SystemExit(
            f"LLM session budget exhausted for application {state.get('record_key') or '<unknown>'}: "
            f"{current}/{budget} sessions already used."
        )
    state["llm_session_count"] = current + 1
    attempts = state.get("llm_stage_attempts")
    if not isinstance(attempts, dict):
        attempts = {}
    attempts[stage] = int(attempts.get(stage) or 0) + 1
    state["llm_stage_attempts"] = attempts


def _is_retryable_analyze_error(validation_error: str) -> bool:
    message = str(validation_error or "").casefold()
    retryable_markers = (
        "placeholder",
        "placeholders",
        "invalid json",
        "json",
        "must contain",
        "must be",
        "required",
        "missing",
        "empty",
        "enum",
        "did not produce",
        "draft",
    )
    non_retryable_markers = (
        "timed out",
        "wrote outside allowed outputs",
        "keyword registration failed",
    )
    if any(marker in message for marker in non_retryable_markers):
        return False
    return any(marker in message for marker in retryable_markers)


def _can_retry_analyze(validation_error: str, state: dict[str, Any], config: dict[str, Any]) -> tuple[bool, str]:
    retry_count = int(state.get("retry_count_analyze") or 0)
    retry_limit = max(int(config.get("analyze_retry_max_attempts") or 0), 0)
    if retry_limit <= 0:
        return False, "analyze_retry_disabled_by_config"
    if retry_count >= retry_limit:
        return False, "analyze_retry_limit_reached"
    if not _is_retryable_analyze_error(validation_error):
        return False, "analyze_error_not_retryable"
    remaining = _remaining_llm_sessions(state, config)
    if remaining is not None and remaining <= 0:
        return False, "llm_session_budget_exhausted"
    return True, "retryable_contract_error"


def _repairable_review_blocker_ids(review_report: dict[str, Any]) -> list[str]:
    blockers = review_report.get("blockers", []) if isinstance(review_report, dict) else []
    return [str(item.get("id")) for item in blockers if isinstance(item, dict) and item.get("id")]


def _missing_unexplained_top8(review_report: dict[str, Any]) -> list[dict[str, Any]]:
    top8 = review_report.get("top8_keywords", []) if isinstance(review_report, dict) else []
    return [
        item for item in top8
        if isinstance(item, dict) and item.get("coverage_class") == "missing_unexplained"
    ]


def _repair_decision(review_report: dict[str, Any], polish_report: dict[str, Any], state: dict[str, Any], config: dict[str, Any]) -> tuple[bool, str]:
    polish_blockers = polish_report.get("approval_blockers", []) if isinstance(polish_report, dict) else []
    if polish_blockers:
        return False, "polish_blockers_require_manual_review"
    review_blocker_ids = _repairable_review_blocker_ids(review_report)
    missing_top8 = _missing_unexplained_top8(review_report)
    if missing_top8:
        return True, "missing_unexplained_top8"
    allowed_review_blockers = {
        "ats_top8_minimum_score",
        "ats_top8_no_missing_unexplained",
        "summary_facts_backed_by_experiences",
        "summary_within_limit",
        "english_cv_role_titles_in_english",
    }
    disallowed = [item for item in review_blocker_ids if item not in allowed_review_blockers]
    if disallowed:
        return False, "review_blockers_not_repairable_by_text"
    max_attempts = max(int(config.get("repair_max_attempts") or 0), 0)
    if max_attempts <= 0:
        return False, "repair_disabled_by_config"
    if int(state.get("repair_attempt_count") or 0) >= max_attempts:
        return False, "repair_attempt_limit_reached"
    remaining = _remaining_llm_sessions(state, config)
    if remaining is not None and remaining <= 0:
        return False, "llm_session_budget_exhausted"
    if review_blocker_ids:
        return True, "review_blockers_repairable_by_text"
    return False, "no_repairable_blockers_detected"


def _ascii_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "item"))
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return _slug(ascii_only)


def _expected_cv_docx_path(paths: dict[str, Path]) -> Path:
    manifest = read_json(paths["manifest"])
    role = str(manifest.get("role") or manifest.get("title") or "vaga")
    company = str(manifest.get("company") or "empresa")
    # Keep the artifact name tied to the original application identity so a
    # translated/adapted FIT_MAP label does not create a second DOCX filename.
    output_name = f"felipe_armel_cv_{_ascii_slug(role)}_{_ascii_slug(company)}{manifest.get('required_cv_filename_suffix') or ''}.docx"
    return OUTPUTS / output_name


def _extract_job_lines(text: str, limit: int) -> list[str]:
    items: list[str] = []
    for raw in text.splitlines():
        line = raw.strip(" -•\t")
        if len(line) < 25:
            continue
        if not any(ch.isalpha() for ch in line):
            continue
        items.append(line)
        if len(items) >= limit:
            break
    return items


def _write_generation_inputs(paths: dict[str, Path]) -> dict[str, str]:
    manifest = read_json(paths["manifest"])
    fit_map = read_json(paths["fit_map"])
    job_text = paths["job_description"].read_text(encoding="utf-8") if paths["job_description"].exists() else ""
    role = str(fit_map.get("cargo") or manifest.get("role") or manifest.get("title") or "vaga")
    company = str(fit_map.get("empresa") or manifest.get("company") or "empresa")
    language = str(manifest.get("required_cv_language") or "pt-BR")
    extracted_lines = _extract_job_lines(job_text, 12)
    requirements = extracted_lines[:6]
    responsibilities = extracted_lines[6:12]
    if not responsibilities:
        responsibilities = requirements[:4]
    selected = fit_map.get("historias_selecionadas", {}) if isinstance(fit_map.get("historias_selecionadas"), dict) else {}
    top8 = [
        str(item.get("keyword") or "").strip()
        for item in sorted(
            [entry for entry in fit_map.get("keywords_habilidade_ats", []) if isinstance(entry, dict)],
            key=lambda item: int(item.get("prioridade") or 999),
        )[:8]
        if str(item.get("keyword") or "").strip()
    ]
    cv_input_pack = {
        "kind": "cv_input_pack",
        "created_at": utc_now_iso(),
        "source": {
            "fit_map_path": str(paths["fit_map"].relative_to(ROOT)),
            "job_description_path": str(paths["job_description"].relative_to(ROOT)),
        },
        "job_identity": {"cargo": role, "empresa": company, "language": language},
        "dor_central": fit_map.get("dor_central"),
        "requirements": requirements,
        "responsibilities": responsibilities,
        "selected_stories": selected,
        "keywords_para_ats": fit_map.get("keywords_para_ats", []),
        "top8_keywords": top8,
        "objecoes": fit_map.get("objecoes", []),
        "required_output_name": _expected_cv_docx_path(paths).name,
    }
    cv_content_seed = {
        "kind": "cv_content_seed",
        "created_at": utc_now_iso(),
        "job_identity": {"cargo": role, "empresa": company, "language": language},
        "persona_hint": "concise",
        "top8_keywords": top8,
        "selected_stories": selected,
        "required_output_name": _expected_cv_docx_path(paths).name,
    }
    feras_input_pack = {
        "kind": "feras_input_pack",
        "created_at": utc_now_iso(),
        "job_identity": {"cargo": role, "empresa": company, "language": language},
        "dor_central": fit_map.get("dor_central"),
        "selected_stories": selected,
        "keywords_para_ats": fit_map.get("keywords_para_ats", []),
        "objecoes": fit_map.get("objecoes", []),
    }
    habilidades_input_pack = {
        "kind": "habilidades_input_pack",
        "created_at": utc_now_iso(),
        "job_identity": {"cargo": role, "empresa": company, "language": language},
        "keywords_para_ats": fit_map.get("keywords_para_ats", []),
        "gaps_sem_cobertura": fit_map.get("gaps_sem_cobertura", []),
        "selected_stories": selected,
    }
    payloads = {
        "cv_input_pack": cv_input_pack,
        "cv_content_seed": cv_content_seed,
        "feras_input_pack": feras_input_pack,
        "habilidades_input_pack": habilidades_input_pack,
    }
    for key, payload in payloads.items():
        write_json(paths[key], payload)
    return {key: str(paths[key].relative_to(ROOT)) for key in payloads}


def _is_review_approved(paths: dict[str, Path]) -> bool:
    artifact = _expected_cv_docx_path(paths)
    if not artifact.exists():
        return False
    if not paths["cv_review_report"].exists() or not paths["polish_review"].exists():
        return False
    review_report = read_json(paths["cv_review_report"])
    polish_report = read_json(paths["polish_review"])
    return bool(review_report.get("approved_for_delivery")) and not bool(polish_report.get("approval_blockers"))


def _review_gate_state(paths: dict[str, Path]) -> str:
    artifact = _expected_cv_docx_path(paths)
    if _is_review_approved(paths):
        return "approved"
    if artifact.exists() or paths["cv_review_report"].exists() or paths["polish_review"].exists():
        return "blocked"
    return "pending"


def _persist_job_description_into_fit_map(paths: dict[str, Path]) -> None:
    if not paths["fit_map"].exists() or not paths["job_description"].exists():
        return
    fit_map = read_json(paths["fit_map"])
    if not isinstance(fit_map, dict):
        return
    job_description = paths["job_description"].read_text(encoding="utf-8").strip()
    if not job_description:
        return
    if str(fit_map.get("descricao_vaga") or "").strip() != job_description:
        fit_map["descricao_vaga"] = job_description
        write_json(paths["fit_map"], fit_map)


def _derive_stage(paths: dict[str, Path], config: dict[str, Any]) -> tuple[str, float | None]:
    job_text = paths["job_description"].read_text(encoding="utf-8") if paths["job_description"].exists() else ""
    if not job_text.strip():
        return "no_description", None
    score = _fit_score(paths["fit_map"])
    if score is None:
        return "analyze_pending", None
    if score < float(config["score_threshold"]):
        return "low_fit", score
    review_state = _review_gate_state(paths)
    if review_state == "approved":
        return "done", score
    if review_state == "blocked":
        return "blocked_review", score
    return "generate_pending", score


def _analysis_request(application: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "stage": "analyze",
        "goal": "Editar o fit_map.draft.json desta candidatura e salvar um draft completo e validável.",
        "candidate": {
            "record_id": application.get("record_id"),
            "title": application.get("title"),
            "company": application.get("company"),
            "role": application.get("role"),
        },
        "inputs": {
            "job_description_path": str(paths["job_description"].relative_to(ROOT)),
        },
        "outputs": {
            "fit_map_draft_path": str(paths["fit_map_draft"].relative_to(ROOT)),
            "allowed_files": [str(paths["fit_map_draft"].relative_to(ROOT))],
        },
        "instructions": [
            "Abra e edite o template existente em fit_map.draft.json.",
            "Salve o arquivo no path exato informado.",
            "Não execute pipeline completo.",
            "Não gere CV, não atualize Notion e não rode validações locais.",
            "Antes de encerrar, confira que o arquivo foi gravado.",
        ],
        "draft_template": fit_map_service.legacy_build_fit_map.draft_template(),
    }


def _analysis_retry_request(application: dict[str, Any], paths: dict[str, Path], validation_error: str) -> dict[str, Any]:
    payload = _analysis_request(application, paths)
    payload["goal"] = "Editar o fit_map.draft.json template existente e salvar um draft completo, sem placeholders."
    payload["instructions"] = [
        "O template existe e continua incompleto; edite o arquivo existente agora.",
        "Substitua todos os placeholders por conteúdo real da vaga e da base.",
        "Não deixe campos com colchetes, enums genéricos ou texto de exemplo.",
        "Salve o arquivo no path exato do fit_map.draft.json antes de encerrar.",
        "Não execute pipeline completo.",
        f"Erro atual de validação: {validation_error}",
    ]
    payload["previous_validation_error"] = validation_error
    return payload


def _generation_request(application: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    manifest = read_json(paths["manifest"])
    fit_map = read_json(paths["fit_map"])
    compact_inputs = _write_generation_inputs(paths)
    top8_keywords = [
        {
            "priority": item.get("prioridade"),
            "keyword": item.get("keyword"),
            "experience_target": item.get("experiencia_alvo"),
            "suggested_bullet_slot": item.get("bullet_sugerido"),
        }
        for item in sorted(
            [entry for entry in fit_map.get("keywords_habilidade_ats", []) if isinstance(entry, dict)],
            key=lambda item: int(item.get("prioridade") or 999),
        )[:8]
    ]
    return {
        "stage": "generate",
        "goal": "Gerar somente os artefatos textuais da candidatura a partir do FIT_MAP já aprovado localmente.",
        "candidate": {
            "record_id": application.get("record_id"),
            "title": application.get("title"),
            "company": application.get("company"),
            "role": application.get("role"),
        },
        "compact_inputs": {
            "primary_files": compact_inputs,
            "fallback_files": {
                "fit_map_path": str(paths["fit_map"].relative_to(ROOT)),
                "job_description_path": str(paths["job_description"].relative_to(ROOT)),
            },
            "fit_map_snapshot": {
                "cargo": fit_map.get("cargo"),
                "empresa": fit_map.get("empresa"),
                "dor_central": fit_map.get("dor_central"),
                "nota_final": fit_map.get("nota_aderencia", {}).get("final"),
            },
        },
        "required_output": {
            "cv_content_path": str(paths["cv_content"].relative_to(ROOT)),
            "feras_formal_path": str(paths["feras_formal"].relative_to(ROOT)),
            "habilidades_gupy_path": str(paths["habilidades_gupy"].relative_to(ROOT)),
            "habilidades_mercado_livre_path": str(paths["habilidades_mercado_livre"].relative_to(ROOT)),
        },
        "cv_content_contract": {
            "summary": "string",
            "mode": "concise",
            "bullet_count_per_experience": 3,
            "ats_keyword_coverage": [
                {
                    "keyword": "string",
                    "experience_index": "integer (0-based)",
                    "experience_role": "string",
                    "bullet_index": "integer (0-based)",
                    "coverage_mode": "exact | similar | declared_gap | missing_unexplained",
                    "defensible_evidence": "string",
                }
            ],
            "experiences": [
                {
                    "role": "string",
                    "company": "string",
                    "period": "string",
                    "bullets": [{"text": "string"}],
                }
            ],
            "education": ["string"],
            "languages": ["string"],
        },
        "top8_keywords_must_cover": top8_keywords,
        "instructions": [
            "Leia primeiro os arquivos em compact_inputs.primary_files.",
            "Use FIT_MAP e job_description apenas como fallback quando os packs compactos não forem suficientes para uma lacuna objetiva.",
            "Gere somente os artefatos textuais pedidos.",
            "Não renderize DOCX, não rode reviewers e não atualize Notion.",
            f"Use idioma visível {manifest.get('required_cv_language')}.",
            "Mantenha tom factual, direto e defensável.",
            "Para BSP, use somente o ano de conclusão 2017.",
            "Modo padrão obrigatório: concise. Use exatamente 3 bullets por experiência, salvo pedido explícito do usuário por modo expandido/bullet points.",
            "Se você inferir que modo expandido seria melhor, não gere expandido automaticamente; registre a recomendação e peça validação do usuário. Sem confirmação explícita, mantenha concise.",
            "O cv_content.json deve trazer no mínimo 4 e no máximo 8 experiências, mesmo quando o impulso inicial do modelo for sintetizar demais.",
            "Nunca junte experiências, cargos, promoções, fases ou escopos em uma única entrada; se faltar espaço, selecione experiências separadas por aderência.",
            "Títulos compostos como 'Head e Diretor', 'Head + Diretor' ou 'S&OP | Expedição | Supply Chain' são inválidos em cv_content.json.",
            "As 8 keywords-habilidade ATS prioritárias precisam ser alocadas em experiências e bullets defensáveis do cv_content.json; não deixar isso implícito.",
            "Se uma keyword top 8 não puder ser sustentada por fato real, registrar coverage_mode=declared_gap somente quando o FIT_MAP declarar o gap; caso contrário, usar coverage_mode=missing_unexplained. Nunca forçar wording artificial.",
            "Evite usar o resumo como muleta para cobrir ATS; a cobertura principal deve estar distribuída nas experiências.",
            "Antes de encerrar, confira que todos os arquivos exigidos foram gravados.",
        ],
    }


def _write_request(paths: dict[str, Path], stage: str, payload: dict[str, Any]) -> None:
    if stage == "analyze":
        json_path = paths["analysis_request_json"]
        md_path = paths["analysis_request_md"]
        output_ref = str(paths["fit_map_draft"].relative_to(ROOT))
    else:
        json_path = paths["generation_request_json"]
        md_path = paths["generation_request_md"]
        output_ref = json.dumps(payload.get("required_output", {}), ensure_ascii=False, indent=2)
    write_json(json_path, payload)
    write_text(
        md_path,
        "\n".join(
            [
                f"# Application V2 Stage: {stage}",
                "",
                f"- Leia `{json_path.relative_to(ROOT)}`.",
                "- Atualize apenas os arquivos permitidos desta etapa.",
                "- Não execute o pipeline inteiro.",
                "",
                "## Objetivo",
                payload["goal"],
                "",
                "## Saída esperada",
                output_ref,
            ]
        )
        + "\n",
    )
    _append_event(
        paths,
        f"{stage}_request_written",
        request_json=str(json_path.relative_to(ROOT)),
        request_md=str(md_path.relative_to(ROOT)),
    )


def _write_context(application: dict[str, Any], paths: dict[str, Path], state: dict[str, Any]) -> None:
    output_docx = state.get("output_docx") or str(_expected_cv_docx_path(paths).relative_to(ROOT))
    write_text(
        paths["conversation_context"],
        "\n".join(
            [
                f"# {application.get('title') or application.get('role') or 'Candidatura'}",
                "",
                f"- ID: {_record_key(application)}",
                f"- Etapa: {state.get('stage')}",
                f"- Status serviço: {state.get('service_status') or state.get('stage')}",
                f"- Score: {state.get('score') if state.get('score') is not None else 'pendente'}",
                f"- Draft: {paths['fit_map_draft'].relative_to(ROOT)}",
                f"- FIT_MAP: {paths['fit_map'].relative_to(ROOT)}",
                f"- CV content: {paths['cv_content'].relative_to(ROOT)}",
                f"- Output DOCX esperado: {output_docx}",
                f"- Job description: {paths['job_description'].relative_to(ROOT)}",
            ]
        )
        + "\n",
    )
    _append_event(paths, "context_written", stage=state.get("stage"), score=state.get("score"))


def _run_agent(
    stage: str,
    application: dict[str, Any],
    paths: dict[str, Path],
    config: dict[str, Any],
    options: HeartbeatV2Options,
    state: dict[str, Any],
) -> None:
    runner_key = "analysis_runner" if stage == "analyze" else "generation_runner"
    runner = config[runner_key]
    model = options.model or str(config.get("active_model") or "").strip()
    variant = options.variant or str(config.get("active_variant") or "").strip()
    request_md = (
        paths["analysis_request_md"]
        if stage == "analyze"
        else paths["repair_request_md"]
        if stage == "repair"
        else paths["generation_request_md"]
    )
    request_json = (
        paths["analysis_request_json"]
        if stage == "analyze"
        else paths["repair_request_json"]
        if stage == "repair"
        else paths["generation_request_json"]
    )
    supervisor = HarnessSupervisor(ROOT)
    _consume_llm_session_budget(state, config, stage=stage, paths=paths)

    def on_start(command: list[str]) -> None:
        _emit("command: " + " ".join(f'"{part}"' if " " in part else part for part in command))
        _append_event(
            paths,
            "agent_started",
            stage=stage,
            command=command,
            llm_session_count=_current_llm_session_count(state),
            llm_session_budget=_llm_session_budget(config),
            llm_session_remaining=_remaining_llm_sessions(state, config),
        )

    payload = supervisor.run_application_stage(
        stage=stage,
        record_key=_record_key(application),
        application_dir=paths["manifest"].parent,
        request_json=request_json,
        request_md=request_md,
        runner_config=runner,
        model=model,
        variant=variant,
        on_start=on_start,
    )
    write_json(paths["agent_run"], payload)
    write_json(paths[f"agent_run_{stage}"], payload)
    _append_event(
        paths,
        "agent_finished",
        stage=stage,
        returncode=payload["returncode"],
        stdout_preview=payload["stdout"][:4000],
        stderr_preview=payload["stderr"][:2000],
    )
    if payload["stdout"].strip():
        print(payload["stdout"], file=sys.stderr, end="" if payload["stdout"].endswith("\n") else "\n")
    elif payload["stderr"].strip():
        print(payload["stderr"], file=sys.stderr, end="" if payload["stderr"].endswith("\n") else "\n")
    if payload["returncode"] != 0:
        raise SystemExit(f"OpenCode {stage} failed for application {_record_key(application)}")
    if payload["isolation"].get("status") != "ok":
        raise SystemExit(
            f"Agent {stage} wrote outside allowed outputs for application {_record_key(application)}: "
            + ", ".join(payload["isolation"].get("unauthorized_changes", []))
        )


def _normalize_fit_map_draft_file(path: Path) -> None:
    payload = read_json(path)
    if not isinstance(payload, dict):
        return
    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    nested = payload.get("fit_map_draft")
    if isinstance(nested, dict):
        if "metadata" in nested:
            metadata = nested.pop("metadata")
            if isinstance(metadata, dict):
                nested.setdefault("cargo", metadata.get("cargo") or metadata.get("titulo"))
                nested.setdefault("empresa", metadata.get("empresa"))
        payload = nested
        meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else meta
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else metadata
    payload.setdefault("cargo", meta.get("vaga") or meta.get("role") or metadata.get("role") or metadata.get("title"))
    payload.setdefault("empresa", meta.get("empresa") or meta.get("company") or metadata.get("company") or metadata.get("empresa"))
    if str(payload.get("modo") or "").strip().casefold() == "draft":
        payload["modo"] = "Modo 1 - vaga especifica"
    ats_entries = payload.get("keywords_habilidade_ats")
    if isinstance(ats_entries, list):
        for index, item in enumerate(ats_entries, start=1):
            if not isinstance(item, dict):
                continue
            if item.get("experiencia") and not item.get("experiencia_alvo"):
                item["experiencia_alvo"] = item.get("experiencia")
            if item.get("prioridade") is None:
                item["prioridade"] = index
    write_json(path, payload)


def _register_fit_map_keywords(fit_map_path: Path) -> None:
    command = [
        sys.executable,
        "scripts/register_keywords.py",
        "--fit-map",
        str(fit_map_path),
        "--translation-registry",
        str(TRANSLATION_REGISTRY),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise SystemExit(
            "FIT_MAP keyword registration failed.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )


def _postprocess_analyze(paths: dict[str, Path]) -> float:
    if not paths["fit_map_draft"].exists():
        raise SystemExit(f"Stage analyze did not produce {paths['fit_map_draft']}")
    _append_event(paths, "postprocess_started", stage="analyze")
    _normalize_fit_map_draft_file(paths["fit_map_draft"])
    fit_map_service.validate_draft(paths["fit_map_draft"])
    fit_map_service.build_fit_map(paths["fit_map_draft"], paths["fit_map"])
    fit_map_service.score_fit_map(paths["fit_map"])
    fit_map_service.validate_fit_map(paths["fit_map"])
    _persist_job_description_into_fit_map(paths)
    _register_fit_map_keywords(paths["fit_map"])
    score = _fit_score(paths["fit_map"]) or 0.0
    _append_event(paths, "postprocess_finished", stage="analyze", score=score, fit_map=str(paths["fit_map"].relative_to(ROOT)))
    return float(score)


def _run_analyze_with_retry(application: dict[str, Any], paths: dict[str, Path], config: dict[str, Any], options: HeartbeatV2Options, state: dict[str, Any]) -> float:
    _write_request(paths, "analyze", _analysis_request(application, paths))
    _write_context(application, paths, state)
    _run_agent("analyze", application, paths, config, options, state)
    try:
        return _postprocess_analyze(paths)
    except (SystemExit, ValidationFailure) as exc:
        validation_error = str(exc)
        can_retry, retry_reason = _can_retry_analyze(validation_error, state, config)
        _append_event(
            paths,
            "analyze_retry_evaluated",
            message=validation_error,
            retry_allowed=can_retry,
            retry_reason=retry_reason,
        )
        if not can_retry:
            raise
        state["retry_count_analyze"] = int(state.get("retry_count_analyze") or 0) + 1
        _set_stage(state, "analyze_retry_pending")
        state["last_error"] = validation_error
        _write_state(paths, state)
        _write_request(paths, "analyze", _analysis_retry_request(application, paths, validation_error))
        _write_context(application, paths, state)
        _run_agent("analyze", application, paths, config, options, state)
        return _postprocess_analyze(paths)


def _render_cv_docx(paths: dict[str, Path]) -> Path:
    artifact = _expected_cv_docx_path(paths)
    command = [
        "node",
        str((ROOT / "scripts" / "docx" / "generate_general_cv_docx.js").resolve()),
        str(paths["cv_content"].resolve()),
        artifact.name,
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise SystemExit(f"DOCX generation failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return artifact


def _validate_cv_content_contract(paths: dict[str, Path]) -> None:
    payload = read_json(paths["cv_content"])
    if not isinstance(payload, dict):
        raise ValidationFailure("cv_content.json must be a JSON object.")
    experiences = payload.get("experiences")
    if not isinstance(experiences, list):
        raise ValidationFailure("cv_content.json must contain an experiences list.")
    if len(experiences) < 4 or len(experiences) > 8:
        raise ValidationFailure(
            f"cv_content.json must contain between 4 and 8 experiences; received {len(experiences)}."
        )
    mode = str(payload.get("mode") or "concise").strip().casefold()
    if mode not in {"concise", "expanded"}:
        raise ValidationFailure("cv_content.json mode must be concise or expanded.")
    summary = str(payload.get("summary") or payload.get("resumo") or "").strip()
    if not summary:
        raise ValidationFailure("cv_content.json must include a non-empty summary/resumo.")
    from career.services import cv_content as cv_content_service

    cv_content_service.validate_positioning_contract(payload)
    consolidated_markers = [
        "head e diretor",
        "head + diretor",
        "head and director",
        "head & director",
        "s&op | expedicao",
        "s&op | expedição",
        "s&op + expedicao",
        "s&op + expedição",
    ]
    for index, experience in enumerate(experiences, start=1):
        if not isinstance(experience, dict):
            raise ValidationFailure(f"experiences[{index}] must be an object.")
        role = str(experience.get("role") or "").casefold()
        period = str(experience.get("period") or "").casefold()
        company = str(experience.get("company") or "").casefold()
        haystack = f"{role} {company}"
        if any(marker in haystack for marker in consolidated_markers):
            raise ValidationFailure(
                f"experiences[{index}] appears to consolidate multiple roles; keep each role as a separate experience."
            )
        if "ifood" in company and "2018" in period and "2024" in period:
            raise ValidationFailure(
                f"experiences[{index}] appears to use the aggregated iFood period; split Head and Director roles."
            )
        if "trifil" in company and "2006" in period and "2014" in period:
            raise ValidationFailure(
                f"experiences[{index}] appears to use the aggregated Trifil period; select separate Trifil roles."
            )
        bullets = experience.get("bullets")
        if not isinstance(bullets, list) or not bullets:
            raise ValidationFailure(f"experiences[{index}] must contain at least one bullet.")
        if mode == "concise" and len(bullets) != 3:
            raise ValidationFailure(
                f"experiences[{index}] must contain exactly 3 bullets in concise mode; received {len(bullets)}."
            )
        if mode == "concise":
            _validate_concise_bullet2(experience, index)
    coverage = payload.get("ats_keyword_coverage")
    if not isinstance(coverage, list):
        raise ValidationFailure("cv_content.json must include ats_keyword_coverage for the top 8 ATS keywords.")
    fit_map = read_json(paths["fit_map"])
    required_keywords = [
        str(item.get("keyword")).strip()
        for item in sorted(
            [entry for entry in fit_map.get("keywords_habilidade_ats", []) if isinstance(entry, dict)],
            key=lambda item: int(item.get("prioridade") or 999),
        )[:8]
        if str(item.get("keyword") or "").strip()
    ]
    coverage_by_keyword: dict[str, dict[str, Any]] = {}
    for item in coverage:
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("keyword") or "").strip()
        if keyword and keyword not in coverage_by_keyword:
            coverage_by_keyword[keyword] = item
    missing = [keyword for keyword in required_keywords if keyword not in coverage_by_keyword]
    if missing:
        raise ValidationFailure(
            "cv_content.json is missing ats_keyword_coverage entries for top 8 keywords: " + ", ".join(missing)
        )
    invalid_mappings = []
    for keyword in required_keywords:
        item = coverage_by_keyword[keyword]
        try:
            exp_index = int(item.get("experience_index"))
            bullet_index = int(item.get("bullet_index"))
        except (TypeError, ValueError):
            invalid_mappings.append(f"{keyword} -> invalid experience_index/bullet_index")
            continue
        if exp_index < 0 or exp_index >= len(experiences):
            invalid_mappings.append(f"{keyword} -> experience_index out of range ({exp_index})")
            continue
        bullets = experiences[exp_index].get("bullets") or []
        if bullet_index < 0 or bullet_index >= len(bullets):
            invalid_mappings.append(f"{keyword} -> bullet_index out of range ({bullet_index})")
            continue
        coverage_mode = str(item.get("coverage_mode") or "").strip()
        if coverage_mode not in {"exact", "similar", "declared_gap", "missing_unexplained"}:
            invalid_mappings.append(f"{keyword} -> invalid coverage_mode {coverage_mode!r}")
            continue
        if coverage_mode in {"exact", "similar"} and not str(item.get("defensible_evidence") or "").strip():
            invalid_mappings.append(f"{keyword} -> defensible_evidence missing")
    if invalid_mappings:
        raise ValidationFailure("cv_content.json has invalid ats_keyword_coverage mappings:\n- " + "\n- ".join(invalid_mappings))
    summary_support = payload.get("summary_support")
    if not isinstance(summary_support, list) or len(summary_support) < 2:
        raise ValidationFailure("cv_content.json must include summary_support with at least two supported summary fragments.")
    summary_errors = []
    for item in summary_support:
        if not isinstance(item, dict):
            summary_errors.append("summary_support item must be an object")
            continue
        fragment = str(item.get("summary_fragment") or "").strip()
        if not fragment:
            summary_errors.append("summary_support.summary_fragment missing")
        elif fragment not in summary:
            summary_errors.append(f"summary fragment not found in summary: {fragment}")
        try:
            exp_index = int(item.get("experience_index"))
            bullet_index = int(item.get("bullet_index"))
        except (TypeError, ValueError):
            summary_errors.append(f"{fragment or '<missing fragment>'} -> invalid experience_index/bullet_index")
            continue
        if exp_index < 0 or exp_index >= len(experiences):
            summary_errors.append(f"{fragment or '<missing fragment>'} -> experience_index out of range ({exp_index})")
            continue
        bullets = experiences[exp_index].get("bullets") or []
        if bullet_index < 0 or bullet_index >= len(bullets):
            summary_errors.append(f"{fragment or '<missing fragment>'} -> bullet_index out of range ({bullet_index})")
            continue
        bullet = bullets[bullet_index]
        bullet_text = str((bullet or {}).get("text") or bullet or "").strip()
        evidence = str(item.get("defensible_evidence") or "").strip()
        if evidence and evidence != bullet_text:
            summary_errors.append(f"{fragment or '<missing fragment>'} -> defensible_evidence does not match mapped bullet")
        if not evidence:
            summary_errors.append(f"{fragment or '<missing fragment>'} -> defensible_evidence missing")
        fragment_anchors = _extract_fact_anchors(fragment)
        if fragment_anchors:
            bullet_norm = _normalize_fact_text(bullet_text)
            missing_anchors = [anchor for anchor in fragment_anchors if anchor not in bullet_norm]
            if missing_anchors:
                summary_errors.append(
                    f"{fragment or '<missing fragment>'} -> mapped bullet does not contain factual anchors: {', '.join(missing_anchors)}"
                )
    if summary_errors:
        raise ValidationFailure("cv_content.json has invalid summary_support mappings:\n- " + "\n- ".join(summary_errors))


def _extract_fact_anchors(text: str) -> list[str]:
    patterns = [
        r"R\$\s?\d+(?:[.,]\d+)?\s?(?:MM|M|mil)?",
        r"\d+(?:[.,]\d+)?%",
        r"\d+\+?\s*POPs?",
        r"\d+\+?\s*SKUs",
        r"\d+\+?\s*cidades",
        r"\d+\+?\s*pessoas",
        r"\d+\+?\s*pedidos/m[eê]s",
        r"\d+\s*[KkMm]?\s*→\s*\d+\s*[KkMm]?",
    ]
    anchors: list[str] = []
    for pattern in patterns:
        anchors.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    deduped = []
    seen = set()
    for anchor in anchors:
        key = _normalize_fact_text(anchor)
        if key and key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped


def _normalize_fact_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_quantitative_result(text: str) -> bool:
    return bool(re.search(r"(?:R\$\s*\d|\b\d+(?:[.,]\d+)?\b)", text or ""))


def _quantitative_claims(text: str) -> set[str]:
    """Return normalized quantitative claims so the same result is not repeated."""
    claims: set[str] = set()
    normalized = _normalize_fact_text(text)
    for match in re.finditer(
        r"r\$\s*\d+(?:[.,]\d+)?\s*(?:mm|mi|m|k)?(?:\s*/\s*[a-z]+)?"
        r"|\b\d+(?:[.,]\d+)?\s*%"
        r"|\b\d+(?:[.,]\d+)?\s*(?:pessoas?|people|cidades?|cities|dias?|days|"
        r"minutos?|minutes|horas?|hours|meses?|months|pas|workstations?)\b",
        normalized,
    ):
        claims.add(re.sub(r"\s+", "", match.group(0)))
    return claims


def _validate_concise_bullet2(experience: dict[str, Any], index: int) -> None:
    bullets = experience.get("bullets") or []
    bullet1 = str((bullets[0] or {}).get("text") or "").strip() if len(bullets) > 0 and isinstance(bullets[0], dict) else ""
    bullet2 = str((bullets[1] or {}).get("text") or "").strip() if len(bullets) > 1 and isinstance(bullets[1], dict) else ""
    bullet3 = str((bullets[2] or {}).get("text") or "").strip() if len(bullets) > 2 and isinstance(bullets[2], dict) else ""
    lowered = bullet2.casefold()
    generic_starts = ("liderei ", "conduzi ", "atuei ", "apoiei ", "fiz ")
    mechanism_signals = (
        "govern",
        "governance",
        "cenario",
        "cenário",
        "scenario",
        "prioriz",
        "priorit",
        "roadmap",
        "dashboard",
        "dashboards",
        "sql",
        "api",
        "s&op",
        "autom",
        "integra",
        "integrat",
        "stakeholder",
        "trade-off",
        "dados",
        "data",
        "indicador",
        "indicator",
        "rito",
        "cadencia",
        "cadência",
        "cadence",
        "rollout",
        "teste",
        "test",
        "experiment",
        "pricing",
        "roi",
        "implemented",
        "configured",
        "organized",
        "modeled",
        "built",
        "pipeline",
        "funnel",
        "monitoring",
        "inventory",
        "cycle counting",
        "picking",
        "warehousing",
        "allocation",
        "supply",
        "demand",
        "process",
        "workflow",
        "using",
        "rf",
        "wms",
    )
    tool_dump_markers = (" · ", " / ", ", ", " e ")
    if not bullet2:
        raise ValidationFailure(f"experiences[{index}] bullet 2 is empty in concise mode.")
    if _contains_quantitative_result(bullet2):
        raise ValidationFailure(
            f"experiences[{index}] bullet 2 must be positioning/mechanism prose, not a quantitative result."
        )
    if not _contains_quantitative_result(bullet3):
        raise ValidationFailure(
            f"experiences[{index}] bullet 3 must contain a quantitative result metric."
        )
    if bullet2 and bullet3 and _normalize_fact_text(bullet2) == _normalize_fact_text(bullet3):
        raise ValidationFailure(
            f"experiences[{index}] bullet 2 must not duplicate bullet 3."
        )
    duplicated_claims = _quantitative_claims(bullet1) & _quantitative_claims(bullet3)
    if duplicated_claims:
        raise ValidationFailure(
            f"experiences[{index}] bullet 1 and bullet 3 must not duplicate quantitative claims: "
            + ", ".join(sorted(duplicated_claims))
        )
    if lowered.startswith(generic_starts) and not any(signal in lowered for signal in mechanism_signals):
        raise ValidationFailure(
            f"experiences[{index}] bullet 2 is too generic; include mechanism, governance, tooling or transferable capability."
        )
    if all(token not in lowered for token in mechanism_signals):
        raise ValidationFailure(
            f"experiences[{index}] bullet 2 must explain how the result happened using a concrete mechanism or transferable capability."
        )
    if bullet2.count(" e ") + bullet2.count(",") >= 4 and not any(
        signal in lowered for signal in ("para ", "com ", "usando ", "a fim de ", "to ", "with ", "using ")
    ):
        raise ValidationFailure(
            f"experiences[{index}] bullet 2 looks like a loose list of tools/skills; convert it into causal prose."
        )
    if bullet1:
        overlap = _token_overlap_ratio(bullet1, bullet2)
        if overlap > 0.6:
            raise ValidationFailure(
                f"experiences[{index}] bullet 2 repeats too much of bullet 1; use it for repositioning leverage instead of scope."
            )
    if bullet3 and not any(connector in lowered for connector in ("para ", "com ", "usando ", "a fim de ", "sustentar ", "to ", "with ", "using ", "in order to ", "to sustain ")):
        raise ValidationFailure(
            f"experiences[{index}] bullet 2 must create a clearer bridge to bullet 3 using causal phrasing."
        )


def _token_overlap_ratio(left: str, right: str) -> float:
    stopwords = {
        "a",
        "ao",
        "as",
        "com",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "na",
        "no",
        "o",
        "os",
        "para",
        "por",
        "que",
        "um",
        "uma",
    }
    left_tokens = {
        token
        for token in re.findall(r"[a-z0-9&+/.-]+", left.casefold())
        if len(token) > 2 and token not in stopwords
    }
    right_tokens = {
        token
        for token in re.findall(r"[a-z0-9&+/.-]+", right.casefold())
        if len(token) > 2 and token not in stopwords
    }
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))


def _write_repair_request(paths: dict[str, Path], state: dict[str, Any], review_report: dict, polish_report: dict) -> None:
    top8 = review_report.get("top8_keywords", []) if isinstance(review_report, dict) else []
    missing_top8 = [
        {
            "keyword": item.get("keyword"),
            "experience_target": item.get("experience_target"),
            "coverage_note": item.get("coverage_note"),
        }
        for item in top8
        if item.get("coverage_class") == "missing_unexplained"
    ]
    payload = {
        "stage": "repair",
        "goal": "Corrigir apenas os artefatos textuais bloqueados pelo gate local, sem reiniciar o pipeline inteiro.",
        "inputs": {
            "fit_map_path": str(paths["fit_map"].relative_to(ROOT)),
            "cv_content_path": str(paths["cv_content"].relative_to(ROOT)),
            "review_report_path": str(paths["cv_review_report"].relative_to(ROOT)),
            "polish_report_path": str(paths["polish_review"].relative_to(ROOT)),
        },
        "allowed_outputs": [
            str(paths["cv_content"].relative_to(ROOT)),
            str(paths["feras_formal"].relative_to(ROOT)),
            str(paths["habilidades_gupy"].relative_to(ROOT)),
            str(paths["habilidades_mercado_livre"].relative_to(ROOT)),
        ],
        "blocking_review_ids": [item.get("id") for item in review_report.get("blockers", [])],
        "missing_unexplained_top8": missing_top8,
        "repair_rules": [
            "Resolver primeiro as keywords top 8 ausentes, colocando cada uma em uma experiência defensável do cv_content.json.",
            "Nunca forçar keyword sem evidência factual; quando não houver sustentação real, manter como gap declarado no mapeamento.",
            "Manter entre 4 e 8 experiências no cv_content.json.",
            "Manter modo concise com exatamente 3 bullets por experiência, salvo pedido explícito do usuário por modo expandido/bullet points.",
            "Se a correção parecer pedir modo expandido, bloquear e pedir validação do usuário antes de alterar o modo.",
            "Atualizar ats_keyword_coverage para refletir exatamente onde cada keyword top 8 ficou coberta.",
            "Não renderizar DOCX, não rodar reviewers e não atualizar Notion nesta etapa.",
        ],
        "state_snapshot": {
            "stage": state.get("stage"),
            "service_status": state.get("service_status") or state.get("stage"),
            "score": state.get("score"),
            "last_error": state.get("last_error"),
            "review_status": state.get("review_status"),
            "polish_status": state.get("polish_status"),
            "repair_attempt_count": state.get("repair_attempt_count"),
        },
        "polish_blockers": polish_report.get("approval_blockers", []),
    }
    write_json(paths["repair_request_json"], payload)
    write_text(
        paths["repair_request_md"],
        "\n".join(
            [
                "# Application V2 Stage: repair",
                "",
                f"- Leia `{paths['repair_request_json'].relative_to(ROOT)}`.",
                "- Corrija apenas os artefatos textuais permitidos.",
                "- O foco principal é cobrir as keywords top 8 faltantes em experiências defensáveis.",
                "- Mantenha 4 a 8 experiências no cv_content.json.",
                "- Mantenha modo concise com exatamente 3 bullets por experiência, salvo pedido explícito do usuário por modo expandido/bullet points.",
                "- Se a correção parecer pedir modo expandido, peça validação do usuário antes de alterar o modo.",
            ]
        )
        + "\n",
    )
    _append_event(
        paths,
        "repair_request_written",
        request_json=str(paths["repair_request_json"].relative_to(ROOT)),
        request_md=str(paths["repair_request_md"].relative_to(ROOT)),
        missing_top8=[item.get("keyword") for item in missing_top8],
    )


def _postprocess_generate(paths: dict[str, Path]) -> dict[str, Any]:
    required = [paths["cv_content"], paths["feras_formal"], paths["habilidades_gupy"], paths["habilidades_mercado_livre"]]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Stage generate did not produce required artifacts: " + ", ".join(missing))
    _append_event(paths, "postprocess_started", stage="generate")
    _validate_cv_content_contract(paths)
    habilidades_chave_service.validate_artifact(paths["habilidades_gupy"], mode="gupy", expected_count=10, fit_map_path=paths["fit_map"])
    habilidades_chave_service.validate_artifact(paths["habilidades_mercado_livre"], mode="mercado_livre", expected_count=10, fit_map_path=paths["fit_map"])
    artifact = _render_cv_docx(paths)
    try:
        report = review_service.approve_cv(
            artifact=artifact,
            fit_map_path=paths["fit_map"],
            registry_path=KEYWORD_REGISTRY,
            report_path=paths["cv_review_report"],
            polish_report_path=paths["polish_review"],
            translation_registry_path=TRANSLATION_REGISTRY,
        )
        _append_event(
            paths,
            "postprocess_finished",
            stage="generate",
            output_docx=str(artifact.relative_to(ROOT)),
            review_approved=bool(report.get("approved_for_delivery")),
        )
        return {
            "stage": "done",
            "output_docx": str(artifact.relative_to(ROOT)),
            "review_status": "approved",
            "polish_status": "approved",
        }
    except SystemExit as exc:
        review_report = read_json(paths["cv_review_report"]) if paths["cv_review_report"].exists() else {}
        polish_report = read_json(paths["polish_review"]) if paths["polish_review"].exists() else {}
        _append_event(
            paths,
            "postprocess_finished",
            stage="generate",
            output_docx=str(artifact.relative_to(ROOT)),
            review_approved=False,
            review_blockers=[item.get("id") for item in review_report.get("blockers", [])],
            polish_blockers=polish_report.get("approval_blockers", []),
        )
        return {
            "stage": "blocked_review",
            "output_docx": str(artifact.relative_to(ROOT)),
            "review_status": "blocked",
            "polish_status": "blocked" if polish_report.get("approval_blockers") else "pending",
            "message": str(exc),
            "review_report": review_report,
            "polish_report": polish_report,
        }


def _update_notion_status(application: dict[str, Any], status: str, *, dry_run: bool) -> dict | None:
    token, database_id = notion_service.notion_config()
    if application.get("page_id"):
        return notion_service.update_status(token, database_id, str(application["page_id"]), status, dry_run=dry_run)
    return None


def _set_service_status(state: dict[str, Any], value: str | None = None) -> dict[str, Any]:
    state["service_status"] = value or state.get("stage")
    return state


def _fit_map_for_notion(
    paths: dict[str, Path],
    state: dict[str, Any],
    *,
    review_report: dict | None = None,
    polish_report: dict | None = None,
) -> Path:
    config = _load_config()
    fit_map = read_json(paths["fit_map"])
    manifest = read_json(paths["manifest"]) if paths["manifest"].exists() else {}
    report = review_report if isinstance(review_report, dict) else (read_json(paths["cv_review_report"]) if paths["cv_review_report"].exists() else {})
    polish = polish_report if isinstance(polish_report, dict) else (read_json(paths["polish_review"]) if paths["polish_review"].exists() else {})
    top8 = report.get("top8_keywords", []) if isinstance(report, dict) else []
    missing_top8 = [str(item.get("keyword")) for item in top8 if item.get("coverage_class") == "missing_unexplained"]
    covered_top8 = [str(item.get("keyword")) for item in top8 if item.get("covered")]
    declared_gap_keywords = [str(item.get("keyword")) for item in top8 if item.get("coverage_class") == "declared_gap"]
    fit_map["service_status"] = state.get("service_status") or state.get("stage")
    fit_map["service_stage"] = state.get("stage")
    fit_map["service_stage_status"] = state.get("stage_status")
    fit_map["service_next_action"] = state.get("next_action")
    fit_map["service_llm_session_count"] = _current_llm_session_count(state)
    fit_map["service_llm_session_budget"] = _llm_session_budget(config)
    fit_map["service_review_status"] = state.get("review_status") or ("approved" if report.get("approved_for_delivery") else "pending")
    fit_map["service_review_blockers"] = [item.get("id") for item in report.get("blockers", [])] if isinstance(report, dict) else []
    fit_map["service_missing_top8"] = missing_top8
    fit_map["service_covered_top8_keywords"] = covered_top8
    fit_map["service_declared_gap_keywords"] = declared_gap_keywords
    fit_map["service_repair_attempt_count"] = int(state.get("repair_attempt_count") or 0)
    fit_map["service_polish_blockers"] = polish.get("approval_blockers", []) if isinstance(polish, dict) else []
    fit_map["service_required_cv_language"] = manifest.get("required_cv_language")
    fit_map["service_final_artifact"] = state.get("output_docx")
    if report.get("approved_for_delivery"):
        fit_map["service_final_cv_language"] = manifest.get("required_cv_language")
    fit_map["service_summary"] = (
        f"status_servico={fit_map['service_status']} | "
        f"score={state.get('score')} | "
        f"blockers={', '.join(fit_map['service_review_blockers']) if fit_map['service_review_blockers'] else 'none'} | "
        f"missing_top8={', '.join(missing_top8) if missing_top8 else 'none'}"
    )
    write_json(paths["fit_map_notion_payload"], fit_map)
    return paths["fit_map_notion_payload"]


def _update_notion_from_fit_map(application: dict[str, Any], paths: dict[str, Path], status: str, *, dry_run: bool) -> dict | None:
    token, database_id = notion_service.notion_config()
    record_id = application.get("record_id")
    if record_id is None:
        return None
    fit_map = read_json(paths["fit_map"])
    saved_job_description = _sync_saved_job_description(
        paths,
        company=str(fit_map.get("empresa") or application.get("company") or "empresa"),
        role=str(fit_map.get("cargo") or application.get("role") or application.get("title") or "cargo"),
    )
    if saved_job_description is None:
        saved_job_description = _load_saved_job_description_path(paths)
    return notion_service.update_from_fit_map_record(
        token,
        database_id,
        int(record_id),
        paths["fit_map_notion_payload"] if paths["fit_map_notion_payload"].exists() else paths["fit_map"],
        saved_job_description,
        status=status,
        dry_run=dry_run,
    )


def _publish_notion_service_state(
    application: dict[str, Any],
    paths: dict[str, Path],
    state: dict[str, Any],
    *,
    status: str,
    review_report: dict | None = None,
    polish_report: dict | None = None,
) -> dict | None:
    _fit_map_for_notion(paths, state, review_report=review_report, polish_report=polish_report)
    payload = _update_notion_from_fit_map(application, paths, status, dry_run=False)
    if payload is not None:
        write_json(paths["notion_update_payload"], payload)
    state["notion_status"] = status
    _append_event(paths, "notion_status_updated", status=status, service_status=state.get("service_status"))
    return payload


def _write_index(entries: list[dict[str, Any]]) -> None:
    existing = read_json(V2_INDEX) if V2_INDEX.exists() else {"version": 1, "applications": []}
    by_key = {str(item.get("record_key")): item for item in existing.get("applications", [])}
    for entry in entries:
        by_key[str(entry["record_key"])] = entry
    write_json(
        V2_INDEX,
        {
            "version": 1,
            "updated_at": utc_now_iso(),
            "applications": sorted(by_key.values(), key=lambda item: str(item.get("updated_at") or ""), reverse=True),
        },
    )


def _result_payload(application: dict[str, Any], paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    config = _load_config()
    return {
        "record_key": _record_key(application),
        "record_id": application.get("record_id"),
        "title": application.get("title"),
        "company": application.get("company"),
        "role": application.get("role"),
        "status": state["stage"],
        "service_status": state.get("service_status") or state.get("stage"),
        "stage_group": state.get("stage_group"),
        "stage_status": state.get("stage_status"),
        "retryable": state.get("retryable"),
        "score": state.get("score"),
        "llm_session_count": _current_llm_session_count(state),
        "llm_session_budget": _llm_session_budget(config),
        "llm_session_remaining": _remaining_llm_sessions(state, config),
        "application_dir": str(paths["manifest"].parent.relative_to(ROOT)),
        "conversation_context": str(paths["conversation_context"].relative_to(ROOT)),
        "output_docx": state.get("output_docx"),
        "updated_at": utc_now_iso(),
    }


def _run_repair_cycle(
    application: dict[str, Any],
    paths: dict[str, Path],
    config: dict[str, Any],
    options: HeartbeatV2Options,
    state: dict[str, Any],
    initial_result: dict[str, Any],
) -> dict[str, Any]:
    max_attempts = int(config.get("repair_max_attempts") or 0)
    latest_result = initial_result
    review_report = latest_result.get("review_report", {}) if isinstance(latest_result.get("review_report"), dict) else {}
    polish_report = latest_result.get("polish_report", {}) if isinstance(latest_result.get("polish_report"), dict) else {}

    while state.get("stage") == "blocked_review" and int(state.get("repair_attempt_count") or 0) < max_attempts:
        state["repair_attempt_count"] = int(state.get("repair_attempt_count") or 0) + 1
        _write_repair_request(paths, state, review_report, polish_report)
        _set_stage(state, "repair_pending")
        _set_service_status(state, "repair_pending")
        _write_state(paths, state)
        _write_context(application, paths, state)
        _publish_notion_service_state(
            application,
            paths,
            state,
            status=str(config["blocked_review_status"]),
            review_report=review_report,
            polish_report=polish_report,
        )

        _set_stage(state, "repair_running")
        _set_service_status(state, "repair_running")
        _write_state(paths, state)
        _write_context(application, paths, state)
        _run_agent("repair", application, paths, config, options, state)

        latest_result = _postprocess_generate(paths)
        _set_stage(state, str(latest_result["stage"]))
        _set_service_status(state, str(latest_result["stage"]))
        state["output_docx"] = latest_result.get("output_docx")
        state["review_status"] = latest_result.get("review_status", state.get("review_status"))
        state["polish_status"] = latest_result.get("polish_status", state.get("polish_status"))
        state["last_error"] = latest_result.get("message") if state["stage"] != "done" else None
        review_report = latest_result.get("review_report", {}) if isinstance(latest_result.get("review_report"), dict) else {}
        polish_report = latest_result.get("polish_report", {}) if isinstance(latest_result.get("polish_report"), dict) else {}

        if state["stage"] == "done":
            _publish_notion_service_state(
                application,
                paths,
                state,
                status=str(config["success_status"]),
                review_report=review_report,
                polish_report=polish_report,
            )
            return latest_result

        _publish_notion_service_state(
            application,
            paths,
            state,
            status=str(config["blocked_review_status"]),
            review_report=review_report,
            polish_report=polish_report,
        )

    if state.get("stage") == "blocked_review":
        _set_stage(state, "blocked_review_exhausted")
        _set_service_status(state, "blocked_review_exhausted")
        _publish_notion_service_state(
            application,
            paths,
            state,
            status=str(config["blocked_review_status"]),
            review_report=review_report,
            polish_report=polish_report,
        )
    return latest_result


def run_heartbeat(options: HeartbeatV2Options) -> dict[str, Any]:
    with ExclusiveRunLock(V2_DIR / ".heartbeat.lock", "applications heartbeat"):
        if options.cellular:
            return _run_cellular_heartbeat(options)
        return _run_heartbeat_unlocked(options)


def _draft_binding_path(paths: Any) -> Path:
    return paths.app_dir / "fit_map.draft.binding.json"


def _reprocess_request_path(paths: Any) -> Path:
    return paths.requests_dir / "cellular_reprocess_request.json"


def _source_revision_path(paths: Any) -> Path:
    return paths.app_dir / "cellular_source_revision.json"


def _completion_receipt_path(paths: Any) -> Path:
    return paths.app_dir / "cellular_completion_receipt.json"


def _reprocess_request_fingerprint(
    application: dict[str, Any], canonical_description: str
) -> str:
    payload = {
        "application_id": _record_key(application),
        "page_id": str(application.get("page_id") or ""),
        "description": canonical_description,
        "source_updated_at": str(
            application.get("last_edited_time")
            or application.get("updated_at")
            or ""
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _read_reprocess_request(paths: Any) -> dict[str, Any]:
    marker = _reprocess_request_path(paths)
    if not marker.is_file():
        return {}
    try:
        payload = read_json(marker)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _quarantine_cellular_draft(
    paths: Any,
    *,
    reason: str,
    target_dir: Path | None = None,
) -> Path | None:
    binding = _draft_binding_path(paths)
    if not paths.fit_map_draft.exists() and not binding.exists():
        return None
    quarantine_dir = target_dir or (
        paths.requests_dir
        / "quarantine"
        / f"{utc_now_iso().replace(':', '').replace('+', '_')}_{reason}"
    )
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantined: Path | None = None
    if paths.fit_map_draft.exists():
        quarantined = quarantine_dir / f"{reason}_fit_map.draft.json"
        os.replace(paths.fit_map_draft, quarantined)
    if binding.exists():
        os.replace(binding, quarantine_dir / f"{reason}_fit_map.draft.binding.json")
    return quarantined


def _prepare_cellular_analyze_attempt(executor: Any, paths: Any, run_id: str) -> Any:
    """Quarantine and reserve analyze_fit as one serialized operation."""
    lock_factory = getattr(executor, "_external_attempt_lock", None)
    if callable(lock_factory):
        with lock_factory(paths, run_id):
            _quarantine_cellular_draft(paths, reason="stale")
            return executor.prepare_ready_node(
                run_id, "analyze_fit", _lock_held=True
            )
    _quarantine_cellular_draft(paths, reason="stale")
    return executor.prepare_ready_node(run_id, "analyze_fit")


def _ensure_cellular_application(
    application: dict[str, Any],
    *,
    applications_root: Path,
    database_path: Path | None = None,
) -> Any:
    application_id = _record_key(application)
    if not application_id:
        raise ValidationFailure("cellular heartbeat requires an application ID")
    paths = paths_for(application_id, root=applications_root)
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    for directory in (
        paths.plans_dir,
        paths.cells_dir,
        paths.artifacts_dir,
        paths.reviews_dir,
        paths.derived_dir,
        paths.requests_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    description = str(application.get("description") or "").strip()
    if not description:
        raise ValidationFailure(
            f"cellular heartbeat requires a job description: {application_id}"
        )
    canonical_description = description + "\n"
    previous_description = (
        paths.job_description.read_text(encoding="utf-8")
        if paths.job_description.exists()
        else None
    )
    reprocess = _normalize_status(str(application.get("status") or "")) == "reprocessar"
    reprocess_marker = _read_reprocess_request(paths)
    reprocess_fingerprint = _reprocess_request_fingerprint(
        application, canonical_description
    )
    new_reprocess_request = reprocess and (
        reprocess_marker.get("request_fingerprint") != reprocess_fingerprint
    )
    if previous_description != canonical_description or new_reprocess_request:
        # In the production cellular path, recovery owns draft quarantine and
        # performs it under the analyze_fit recovery lock. Keep this helper's
        # standalone legacy behavior for callers that do not have the
        # authoritative database available (notably setup/tests).
        if database_path is None:
            _quarantine_cellular_draft(paths, reason="stale")
        write_text(paths.job_description, canonical_description)
        previous_fingerprint = (
            hashlib.sha256(previous_description.encode("utf-8")).hexdigest()
            if previous_description is not None
            else ""
        )
        write_json(
            _source_revision_path(paths),
            {
                "kind": "cellular_source_revision",
                "application_id": application_id,
                "previous_fingerprint": previous_fingerprint,
                "job_fingerprint": sha256_file(paths.job_description),
                "changed_at": utc_now_iso(),
                "applied_run_id": "",
            },
        )
    if new_reprocess_request:
        write_json(
            _reprocess_request_path(paths),
            {
                "kind": "cellular_reprocess_request",
                "application_id": application_id,
                "request_fingerprint": reprocess_fingerprint,
                "status": "pending",
                "run_id": "",
                "created_at": utc_now_iso(),
            },
        )
    elif not reprocess and _reprocess_request_path(paths).exists():
        _reprocess_request_path(paths).unlink()
    identity = read_json(paths.identity) if paths.identity.exists() else {}
    existing_aliases = (
        dict(identity.get("aliases"))
        if isinstance(identity.get("aliases"), dict)
        else {}
    )
    aliases = {
        key: str(value)
        for key, value in existing_aliases.items()
        if (
            key != "notion_record_id"
            or str(value or "").strip().isdigit()
        )
        and (
            key != "notion_page_id"
            or bool(_valid_notion_page_id(value))
        )
    }
    incoming_record_id = str(application.get("record_id") or "").strip()
    incoming_page_id = _valid_notion_page_id(application.get("page_id"))
    if incoming_record_id.isdigit():
        aliases["notion_record_id"] = incoming_record_id
    if incoming_page_id:
        aliases["notion_page_id"] = incoming_page_id
    source_type = str(
        application.get("source_type")
        or identity.get("source_type")
        or "notion_queue"
    )
    source_id = str(
        application.get("source_id")
        or identity.get("source_id")
        or incoming_page_id
        or incoming_record_id
        or application_id
    )
    identity.update(
        {
            "kind": "application_identity",
            "application_id": application_id,
            "source_type": source_type,
            "source_id": source_id,
            "source_url": str(
                application.get("source_url") or identity.get("source_url") or ""
            ),
            "delivery_profile": str(
                application.get("delivery_profile")
                or identity.get("delivery_profile")
                or "standard_cv"
            ),
            "company": str(application.get("company") or ""),
            "role": str(application.get("role") or application.get("title") or ""),
            "aliases": aliases,
            "updated_at": utc_now_iso(),
        }
    )
    write_json(paths.identity, identity)
    return paths


def _cancel_run_for_changed_source(database: Database, run_id: str) -> None:
    now = utc_now_iso()
    with database.transaction(immediate=True) as conn:
        conn.execute(
            "UPDATE application_runs SET status = 'cancelled', updated_at = ? "
            "WHERE run_id = ? AND status NOT IN ('completed', 'cancelled')",
            (now, run_id),
        )
        conn.execute(
            """UPDATE cell_nodes SET status = 'cancelled', reserved_by = NULL,
                      reservation_expires_at = NULL, updated_at = ?
               WHERE run_id = ? AND status NOT IN ('validated', 'blocked', 'cancelled')""",
            (now, run_id),
        )
        conn.execute(
            """UPDATE cell_attempts SET status = 'cancelled', finished_at = ?
               WHERE run_id = ? AND status IN ('reserved', 'running')""",
            (now, run_id),
        )


def _select_or_plan_cellular_run(
    application: dict[str, Any], *, paths: Any, executor: Any, config: dict[str, Any]
) -> str:
    lock_path = paths.requests_dir / "cellular" / ".run-selection.lock"
    with ExclusiveRunLock(lock_path, f"cellular run selection: {paths.application_id}"):
        return _select_or_plan_cellular_run_unlocked(
            application, paths=paths, executor=executor, config=config
        )


def _select_or_plan_cellular_run_unlocked(
    application: dict[str, Any], *, paths: Any, executor: Any, config: dict[str, Any]
) -> str:
    database = executor.database
    requested_run_id = str(application.get("_cellular_run_id") or "").strip()
    if requested_run_id:
        requested = database.fetch_one(
            "SELECT run_id, application_id FROM application_runs WHERE run_id = ?",
            (requested_run_id,),
        )
        if requested is None or str(requested["application_id"]) != paths.application_id:
            raise ValidationFailure(
                f"requested cellular run does not belong to application: {requested_run_id}"
            )
        return requested_run_id
    latest = database.fetch_one(
        """SELECT run_id, status, created_at FROM application_runs
           WHERE application_id = ? ORDER BY created_at DESC LIMIT 1""",
        (paths.application_id,),
    )
    source_revision = (
        read_json(_source_revision_path(paths))
        if _source_revision_path(paths).is_file()
        else {}
    )
    current_fingerprint = sha256_file(paths.job_description)
    source_changed_for_latest = bool(
        latest
        and source_revision.get("job_fingerprint") == current_fingerprint
        and source_revision.get("applied_run_id") != latest["run_id"]
        and source_revision.get("previous_fingerprint")
        and source_revision.get("previous_fingerprint") != current_fingerprint
    )
    if source_changed_for_latest and latest["status"] not in {"completed", "cancelled"}:
        _cancel_run_for_changed_source(database, str(latest["run_id"]))
        latest = None

    reprocess_request = (
        _read_reprocess_request(paths)
        if _is_reprocess_requested(application, config)
        else {}
    )
    reprocess_run_id = str(reprocess_request.get("run_id") or "")
    reprocess_run = (
        database.fetch_one(
            "SELECT run_id, status FROM application_runs "
            "WHERE run_id = ? AND application_id = ?",
            (reprocess_run_id, paths.application_id),
        )
        if reprocess_run_id
        else None
    )
    if (
        reprocess_run is None
        and reprocess_request
        and reprocess_request.get("status") == "pending"
        and latest is not None
        and latest["status"] not in {"completed", "cancelled"}
        and str(latest.get("created_at") or "")
        >= str(reprocess_request.get("created_at") or "")
    ):
        reprocess_run = latest
    if reprocess_run is not None:
        run_id = str(reprocess_run["run_id"])
    elif latest is None or latest["status"] in {"completed", "cancelled"} or reprocess_request:
        run_id = executor.plan(paths.application_id, {"cv", "notion"}).run_id
    else:
        run_id = str(latest["run_id"])

    if source_revision.get("job_fingerprint") == current_fingerprint:
        write_json(
            _source_revision_path(paths),
            {**source_revision, "applied_run_id": run_id, "applied_at": utc_now_iso()},
        )
    if reprocess_request and (
        reprocess_request.get("status") != "consumed"
        or reprocess_request.get("run_id") != run_id
    ):
        write_json(
            _reprocess_request_path(paths),
            {
                **reprocess_request,
                "status": "consumed",
                "run_id": run_id,
                "consumed_at": utc_now_iso(),
            },
        )
    return run_id


def _complete_cellular_application_once(
    application: dict[str, Any],
    *,
    paths: Any,
    run_id: str,
    job_fingerprint: str,
    delivery,
    update_tracker,
    success_status: str,
) -> dict[str, Any]:
    """Persist a source-keyed completion receipt so later runs cannot redeliver."""
    receipt_path = _completion_receipt_path(paths)
    reprocess_request = _read_reprocess_request(paths)
    reprocess_for_run = bool(
        reprocess_request
        and (
            reprocess_request.get("status") == "pending"
            or (
                reprocess_request.get("status") == "consumed"
                and reprocess_request.get("run_id") == run_id
            )
        )
    )
    if receipt_path.is_file():
        existing = read_json(receipt_path)
        if (
            existing.get("status") == "completed"
            and existing.get("job_fingerprint") == job_fingerprint
            and not reprocess_for_run
        ):
            return {**existing, "status": "already_completed"}
    delivery_receipt = dict(delivery())
    if delivery_receipt.get("status") not in {"delivered", "validated"}:
        raise ValidationFailure("cellular delivery did not complete")
    update_tracker(success_status)
    receipt = {
        "kind": "cellular_completion_receipt",
        "application_id": paths.application_id,
        "notion_page_id": str(application.get("page_id") or ""),
        "run_id": run_id,
        "job_fingerprint": job_fingerprint,
        "delivery": delivery_receipt,
        "tracker_status": success_status,
        "status": "completed",
        "completed_at": utc_now_iso(),
    }
    write_json(receipt_path, receipt)
    if reprocess_for_run:
        write_json(
            _reprocess_request_path(paths),
            {
                **reprocess_request,
                "status": "completed",
                "run_id": run_id,
                "completed_at": receipt["completed_at"],
            },
        )
    return receipt


def _recover_completed_cellular_receipt(
    application: dict[str, Any],
    *,
    paths: Any,
    job_fingerprint: str,
    success_status: str,
    update_tracker,
) -> dict[str, Any] | None:
    """Recover the cross-run receipt from a completed, source-bound run."""
    run_root = paths.app_dir / "runs"
    manifests = sorted(
        run_root.glob("*/run_completion_manifest.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for manifest_path in manifests:
        try:
            completion = read_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if (
            completion.get("kind") != "run_completion_manifest"
            or completion.get("application_id") != paths.application_id
            or completion.get("status") != "completed"
        ):
            continue
        artifacts = completion.get("validated_artifacts")
        if not isinstance(artifacts, list):
            continue
        normalized_handover = next(
            (
                item
                for item in artifacts
                if isinstance(item, dict)
                and item.get("node_id") == "normalize_job"
                and item.get("artifact_name") == "handover_summary.json"
            ),
            None,
        )
        delivery_artifact = next(
            (
                item
                for item in artifacts
                if isinstance(item, dict)
                and item.get("node_id") == "deliver_cv"
                and item.get("artifact_name") == "cv_delivery_receipt.json"
            ),
            None,
        )
        if normalized_handover is None or delivery_artifact is None:
            continue
        try:
            handover = read_json(Path(str(normalized_handover["path"])))
            delivery = read_json(Path(str(delivery_artifact["path"])))
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
        if handover.get("job_fingerprint") != job_fingerprint:
            continue
        return _complete_cellular_application_once(
            application,
            paths=paths,
            run_id=str(completion.get("run_id") or manifest_path.parent.name),
            job_fingerprint=job_fingerprint,
            delivery=lambda: {"status": "delivered", **delivery},
            update_tracker=update_tracker,
            success_status=success_status,
        )
    return None


def _run_cellular_heartbeat(options: HeartbeatV2Options) -> dict[str, Any]:
    """Schedule application-scoped cells without mutable global path adapters."""
    if not options.run_agent or options.dry_run:
        raise ValidationFailure(
            "cellular heartbeat requires --run-agent and does not downgrade to dry-run globals"
        )
    control_db_id = str(
        options.control_db_id or os.environ.get("CAREER_CONTROL_DB_ID") or ""
    ).strip()
    if not control_db_id:
        raise ValueError(
            "CAREER_CONTROL_DB_ID is required for an authoritative workspace entry point"
        )
    database_path = canonical_database().db_path
    if not database_path.is_file():
        raise ValueError("authoritative control database does not exist")
    owner = options.workspace_owner or _production_workspace_owner()
    authority_database = Database(database_path)
    try:
        actual_control_db_id = authority_database.control_db_identity()
        if actual_control_db_id != control_db_id:
            raise ValueError(
                "configured authoritative control database identity does not match "
                f"this database: expected={control_db_id} actual={actual_control_db_id}"
            )
        authority_database.init_schema()
        authority = WorkspaceLease(
            authority_database,
            expected_control_db_id=control_db_id,
            require_authority=True,
        )
        if not authority.acquire(owner, ttl_seconds=300):
            raise ValidationFailure("authoritative workspace lease is unavailable")
    finally:
        authority_database.close()
    try:
        return _run_cellular_heartbeat_authorized(
            replace(
                options,
                workspace_owner=owner,
                control_db_id=control_db_id,
            ),
            database_path=database_path,
        )
    finally:
        release_database = Database(database_path)
        try:
            WorkspaceLease(
                release_database,
                expected_control_db_id=control_db_id,
                require_authority=True,
            ).release(owner)
        finally:
            release_database.close()


def _production_workspace_owner() -> str:
    explicit = str(os.environ.get("CAREER_WORKSPACE_OWNER") or "").strip()
    if explicit:
        return explicit
    return f"{workspace_owner_from_env()}:{os.getpid()}:{uuid4().hex}"


def _run_cellular_heartbeat_authorized(
    options: HeartbeatV2Options, *, database_path: Path
) -> dict[str, Any]:
    V2_DIR.mkdir(parents=True, exist_ok=True)
    V2_LOG_DIR.mkdir(parents=True, exist_ok=True)
    started_at = utc_now_iso()
    config = _load_config()
    maintenance_report = _run_maintenance_sync(config, options)
    token, database_id = notion_service.notion_config()
    queue = _load_queue(token, database_id)
    effective_max = (
        options.max_per_run
        if options.max_per_run is not None
        else int(config["max_per_run"])
    )
    # Local/LinkedIn runs do not necessarily have a Notion queue record.  Give
    # those already-planned runs priority, while retaining the existing queue
    # behavior and deduplicating by the execution key.
    local_selected = _local_cellular_candidates(
        database_path, applications_root=V2_DIR
    )
    queue_selected = _eligible(queue, config, None)
    queue_keys = {_record_key(application) for application in queue_selected}
    local_selected = [
        application
        for application in local_selected
        if not (
            str(application.get("source_type") or "") == "notion_queue"
            and _record_key(application) in queue_keys
        )
    ]
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    for application in [*local_selected, *queue_selected]:
        key = _record_key(application)
        if not key or key in selected_keys:
            continue
        selected.append(application)
        selected_keys.add(key)
        if effective_max is not None and len(selected) >= effective_max:
            break
    results: list[dict[str, Any]] = []
    worker_count = min(
        len(selected),
        max(1, int(config.get("cellular_max_workers") or effective_max)),
        max(1, effective_max),
    )
    if selected:
        by_index: dict[int, list[dict[str, Any]]] = {}
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="applications-cellular",
        ) as pool:
            future_indexes = {
                pool.submit(
                    _process_cellular_application,
                    application,
                    options=options,
                    config=config,
                    database_path=database_path,
                ): index
                for index, application in enumerate(selected)
            }
            for future in as_completed(future_indexes):
                index = future_indexes[future]
                application = selected[index]
                try:
                    by_index[index] = future.result()
                except Exception as exc:
                    by_index[index] = [
                        {
                            "status": "error",
                            "application_id": _record_key(application),
                            "blocker": f"{type(exc).__name__}:{exc}",
                        }
                    ]
        for index in range(len(selected)):
            results.extend(by_index[index])
    summary = {
        "status": "ok",
        "mode": "cellular",
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "run_agent": True,
        "maintenance": maintenance_report,
        "max_per_run": effective_max,
        "selected": len(selected),
        "worker_count": worker_count,
        "results": results,
        "global_fallback": False,
    }
    log_path = V2_LOG_DIR / (
        started_at.replace(":", "").replace("+", "Z") + "-cellular.json"
    )
    write_json(log_path, summary)
    summary["log"] = str(log_path)
    return summary


def _cell_execution_payload(execution: Any, *, application_id: str) -> dict[str, Any]:
    manifest = read_json(execution.manifest_path)
    capabilities = (
        manifest.get("capabilities")
        if isinstance(manifest.get("capabilities"), dict)
        else {}
    )
    return {
        "status": execution.status,
        "application_id": application_id,
        "run_id": execution.run_id,
        "node_id": execution.node_id,
        "manifest_path": str(execution.manifest_path),
        "read_allowlist": list(capabilities.get("read_paths") or []),
        "write_allowlist": list(capabilities.get("write_paths") or []),
        "artifact_paths": [
            str(item.get("path"))
            for item in manifest.get("outputs", [])
            if isinstance(item, dict) and item.get("path")
        ],
        "blocker": execution.blocker,
    }


def _cellular_workspace_root() -> Path:
    state_dir = V2_DIR.parent
    if state_dir.name != ".career-state":
        raise ValidationFailure(
            "cellular applications directory must be under .career-state"
        )
    return state_dir.parent.resolve()


def _write_cellular_analyze_request(
    paths: Any,
    prepared: Any,
    *,
    workspace_owner: str,
    control_db_id: str,
) -> tuple[Path, Path]:
    manifest = read_json(prepared.manifest_path)
    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ValidationFailure("cellular attempt manifest is missing capabilities")
    read_allowlist = list(capabilities.get("read_paths") or [])
    write_allowlist = list(capabilities.get("write_paths") or [])
    request_dir = (
        paths.requests_dir
        / "cellular"
        / prepared.run_id
        / prepared.node_id
        / str(prepared.attempt)
    )
    request_json = request_dir / "request.json"
    request_md = request_dir / "request.md"
    payload = {
        "kind": "cellular_agent_request",
        "cellular": True,
        "step": "fit-map",
        "application_id": prepared.application_id,
        "run_id": prepared.run_id,
        "node_id": prepared.node_id,
        "manifest_path": str(prepared.manifest_path.resolve()),
        "read_allowlist": read_allowlist,
        "write_allowlist": write_allowlist,
        "workspace_owner": workspace_owner,
        "control_db_id": control_db_id,
        "objective": (
            "Produce only the application-scoped FIT_MAP draft required by "
            "this analyze_fit attempt."
        ),
        "allowed_files": read_allowlist,
        "expected_outputs": write_allowlist,
    }
    from career.services import multiagent as multiagent_service

    context = multiagent_service.validate_cellular_request_context(
        payload, root=_cellular_workspace_root()
    )
    payload.update(context)
    payload["operational_rules"] = multiagent_service.cellular_operational_rules(
        context
    )
    write_json(request_json, payload)
    write_text(
        request_md,
        "# Cellular analyze_fit request\n\n"
        + "\n".join(f"- {rule}" for rule in payload["operational_rules"])
        + "\n",
    )
    _prepare_external_agent_handoff(
        request_json=request_json,
        request_md=request_md,
        read_allowlist=read_allowlist,
        write_allowlist=write_allowlist,
        application_dir=paths.app_dir,
    )
    return request_json, request_md


def _run_cellular_analyze_agent(
    paths: Any,
    prepared: Any,
    *,
    options: HeartbeatV2Options,
    config: dict[str, Any],
    request_paths: tuple[Path, Path] | None = None,
) -> dict[str, Any]:
    workspace_owner = options.workspace_owner or os.environ.get(
        "CAREER_WORKSPACE_OWNER"
    ) or ""
    if request_paths is None:
        request_json, request_md = _write_cellular_analyze_request(
            paths,
            prepared,
            workspace_owner=workspace_owner,
            control_db_id=str(
                options.control_db_id
                or os.environ.get("CAREER_CONTROL_DB_ID")
                or ""
            ),
        )
    else:
        request_json, request_md = request_paths
        if not request_json.is_file() or not request_md.is_file():
            raise ValidationFailure("cellular analyze compact request is missing")
    supervisor = HarnessSupervisor(_cellular_workspace_root())
    return supervisor.run_application_stage(
        stage="analyze",
        record_key=paths.application_id,
        application_dir=paths.app_dir,
        request_json=request_json,
        request_md=request_md,
        runner_config=dict(config.get("analysis_runner") or {}),
        model=str(options.model or config.get("active_model") or ""),
        variant=str(options.variant or config.get("active_variant") or ""),
        workspace_owner=workspace_owner,
        control_db_id=str(
            options.control_db_id
            or os.environ.get("CAREER_CONTROL_DB_ID")
            or ""
        ),
    )


def _cellular_cv_repair_candidate_path(paths: Any, run_id: str, attempt: int) -> Path:
    return (
        paths.requests_dir
        / "cellular"
        / run_id
        / "repair"
        / str(attempt)
        / "cv_content.json"
    )


def _cellular_repair_progress_path(paths: Any, run_id: str, attempt: int) -> Path:
    return (
        paths.requests_dir
        / "cellular"
        / run_id
        / "repair"
        / str(attempt)
        / "progress.json"
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def inspect_repair_progress(
    *,
    review_report: dict[str, Any],
    cv_content_sha256: str,
    previous_progress: dict[str, Any] | None = None,
    polish_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify a cellular CV repair using artifact and blocker fingerprints."""
    blockers = review_report.get("blockers", []) if isinstance(review_report, dict) else []
    blocker_ids = sorted(
        str(item.get("id"))
        for item in blockers
        if isinstance(item, dict) and item.get("id")
    )
    top8 = review_report.get("top8_keywords", []) if isinstance(review_report, dict) else []
    missing_top8 = sorted(
        str(item.get("keyword"))
        for item in top8
        if isinstance(item, dict)
        and item.get("coverage_class") == "missing_unexplained"
        and item.get("keyword")
    )
    polish_blocker_ids = sorted(
        str(item.get("id") or item.get("code"))
        for item in (polish_report or {}).get("approval_blockers", [])
        if isinstance(item, dict) and (item.get("id") or item.get("code"))
    )
    blocker_fingerprint = _sha256_json(
        {
            "blocker_ids": blocker_ids,
            "missing_top8": missing_top8,
            "polish_blocker_ids": polish_blocker_ids,
        }
    )
    evidence = {
        "cv_content_sha256": str(cv_content_sha256 or ""),
        "blocker_fingerprint": blocker_fingerprint,
        "blocker_ids": blocker_ids,
        "missing_top8": missing_top8,
        "polish_blocker_ids": polish_blocker_ids,
    }
    if not isinstance(previous_progress, dict):
        return {"status": "changed", **evidence}
    if (
        evidence["cv_content_sha256"]
        and previous_progress.get("cv_content_sha256")
        and previous_progress.get("cv_content_sha256") == evidence["cv_content_sha256"]
        and previous_progress.get("blocker_fingerprint")
        == evidence["blocker_fingerprint"]
    ):
        return {
            "status": "no_progress",
            "blocker_reason": "cv_repair_no_progress",
            **evidence,
        }
    return {"status": "retryable", **evidence}


def _latest_cellular_cv_content_sha256(executor: Any, paths: Any, run_id: str) -> str:
    row = executor.database.fetch_one(
        "SELECT latest_attempt FROM cell_nodes "
        "WHERE run_id = ? AND node_id = 'compose_cv' AND status = 'validated'",
        (run_id,),
    )
    if row is None or int(row["latest_attempt"] or 0) <= 0:
        return ""
    manifest_path = (
        paths.cells_dir
        / run_id
        / "compose_cv"
        / str(int(row["latest_attempt"]))
        / "manifest.json"
    )
    if not manifest_path.is_file():
        return ""
    manifest = read_json(manifest_path)
    for output in manifest.get("outputs", []):
        if not isinstance(output, dict) or output.get("artifact_name") != "cv_content.json":
            continue
        artifact_path = Path(str(output.get("path") or ""))
        if artifact_path.is_file():
            return sha256_file(artifact_path)
    return ""


def _latest_cellular_repair_progress(
    executor: Any, paths: Any, run_id: str
) -> dict[str, Any] | None:
    repair_root = paths.requests_dir / "cellular" / run_id / "repair"
    candidates = sorted(
        (path for path in repair_root.glob("*/progress.json") if path.is_file()),
        key=lambda path: int(path.parent.name) if path.parent.name.isdigit() else -1,
    )
    for path in reversed(candidates):
        payload = read_json(path)
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            return payload
    # Backfill a baseline from the preceding persisted review/compose pair.
    # This makes old runs safe on their first resume even if progress.json did
    # not exist before this hardening was deployed.
    review_row = executor.database.fetch_one(
        "SELECT latest_attempt FROM cell_nodes "
        "WHERE run_id = ? AND node_id = 'review_cv'",
        (run_id,),
    )
    latest_review = int(review_row["latest_attempt"] or 0) if review_row else 0
    if latest_review <= 1:
        return None
    previous_review = (
        paths.cells_dir
        / run_id
        / "review_cv"
        / str(latest_review - 1)
        / "staging"
        / "cv_review.json"
    )
    previous_compose = (
        paths.cells_dir
        / run_id
        / "compose_cv"
        / str(latest_review - 1)
        / "manifest.json"
    )
    if not previous_review.is_file() or not previous_compose.is_file():
        return None
    report = read_json(previous_review)
    compose_manifest = read_json(previous_compose)
    cv_hash = ""
    for output in compose_manifest.get("outputs", []):
        if isinstance(output, dict) and output.get("artifact_name") == "cv_content.json":
            artifact = Path(str(output.get("path") or ""))
            if artifact.is_file():
                cv_hash = sha256_file(artifact)
                break
    if not cv_hash:
        return None
    return {
        "kind": "cellular_cv_repair_progress",
        "application_id": paths.application_id,
        "run_id": run_id,
        **inspect_repair_progress(
            review_report=report,
            cv_content_sha256=cv_hash,
        ),
    }
    return None


def _persist_cellular_repair_progress(
    paths: Any, run_id: str, attempt: int, evidence: dict[str, Any]
) -> Path:
    path = _cellular_repair_progress_path(paths, run_id, attempt)
    write_json(
        path,
        {
            "kind": "cellular_cv_repair_progress",
            "application_id": paths.application_id,
            "run_id": run_id,
            "compose_attempt": attempt,
            "recorded_at": utc_now_iso(),
            **evidence,
        },
    )
    return path


def _prepare_external_agent_handoff(
    *,
    request_json: Path,
    request_md: Path,
    read_allowlist: list[str],
    write_allowlist: list[str],
    application_dir: Path,
) -> None:
    """Make only declared handoff inputs/outputs accessible to the profile uid."""
    app_dir = application_dir.resolve()

    def ensure_inside(path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(app_dir):
            raise ValidationFailure("external agent handoff path escapes application")
        return resolved

    def grant_traverse(path: Path) -> None:
        current = path.resolve()
        while True:
            current.chmod(current.stat().st_mode | 0o001)
            if current == app_dir:
                return
            if current.parent == current or not current.parent.is_relative_to(app_dir):
                raise ValidationFailure("external agent handoff parent escapes application")
            current = current.parent

    for readable in (request_json, request_md, *map(Path, read_allowlist)):
        readable = ensure_inside(readable)
        if readable.is_file():
            readable.chmod(readable.stat().st_mode | 0o004)
            grant_traverse(readable.parent)
        elif readable.is_dir():
            grant_traverse(readable)
            readable.chmod(readable.stat().st_mode | 0o005)
    for declared in map(Path, write_allowlist):
        declared = ensure_inside(declared)
        target = declared if declared.exists() and declared.is_dir() else declared.parent
        grant_traverse(target)
        target.chmod(target.stat().st_mode | 0o003)


def _write_cellular_cv_repair_request(
    *,
    paths: Any,
    run_id: str,
    attempt: int,
    manifest_path: Path,
    review_report_path: Path,
    candidate_path: Path,
) -> tuple[Path, Path]:
    """Create the scoped repair handoff for a failed cellular CV review."""
    manifest = read_json(manifest_path)
    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ValidationFailure("cellular repair manifest capabilities are missing")
    if (
        manifest.get("application_id") != paths.application_id
        or manifest.get("run_id") != run_id
        or manifest.get("node_id") != "compose_cv"
        or int(manifest.get("attempt") or 0) != attempt
    ):
        raise ValidationFailure("cellular repair manifest identity does not match request")
    read_allowlist = [str(Path(item).resolve()) for item in capabilities.get("read_paths", [])]
    manifest_write_allowlist = [
        str(Path(item).resolve()) for item in capabilities.get("write_paths", [])
    ]
    app_dir = paths.app_dir.resolve()
    for label, values in (("read", read_allowlist), ("write", manifest_write_allowlist)):
        for value in values:
            if not Path(value).is_relative_to(app_dir):
                raise ValidationFailure(f"cellular repair {label} path escapes application")
    resolved_review = review_report_path.resolve()
    resolved_candidate = candidate_path.resolve()
    if str(resolved_review) not in read_allowlist:
        raise ValidationFailure("cellular repair review report is outside read allowlist")
    if str(resolved_candidate) not in manifest_write_allowlist:
        raise ValidationFailure("cellular repair candidate is outside write allowlist")
    # Do not pass the whole compose staging capability to the external agent.
    # The only permitted mutation in this stage is the repaired content file.
    write_allowlist = [str(resolved_candidate)]
    review_report = read_json(review_report_path)
    top8 = review_report.get("top8_keywords", []) if isinstance(review_report, dict) else []
    missing_top8 = [
        {
            "keyword": item.get("keyword"),
            "experience_target": item.get("experience_target"),
            "coverage_note": item.get("coverage_note"),
        }
        for item in top8
        if isinstance(item, dict) and item.get("coverage_class") == "missing_unexplained"
    ]
    request_dir = candidate_path.parent
    request_json = request_dir / "request.json"
    request_md = request_dir / "request.md"
    payload = {
        "kind": "cellular_cv_repair_request",
        "cellular": True,
        "step": "repair",
        "application_id": paths.application_id,
        "run_id": run_id,
        "node_id": "compose_cv",
        "manifest_path": str(manifest_path.resolve()),
        "read_allowlist": read_allowlist,
        "write_allowlist": write_allowlist,
        "allowed_files": read_allowlist,
        "expected_outputs": [str(candidate_path.resolve())],
        "objective": (
            "Corrigir somente o cv_content.json para resolver os blockers do review_cv "
            "com keywords ATS em histórias defensáveis da candidatura."
        ),
        "review_report_path": str(review_report_path.resolve()),
        "blocking_review_ids": [
            item.get("id")
            for item in review_report.get("blockers", [])
            if isinstance(item, dict) and item.get("id")
        ],
        "missing_unexplained_top8": missing_top8,
        "repair_rules": [
            "Editar somente o candidato cv_content.json indicado em expected_outputs.",
            "Preservar ou incluir metadata.application_id, metadata.run_id e metadata.compose_attempt exatamente como no request.",
            "Posicionar cada keyword somente em uma experiência com evidência factual real.",
            "Não inventar métricas, cargos, empresas, ferramentas, escopo ou resultados.",
            "Manter 4 a 8 experiências e exatamente 3 bullets por experiência em modo concise.",
            "Se não houver evidência real para uma keyword, preservar o gap declarado.",
            "Preservar a proveniência canônica e o idioma do CV.",
        ],
        "operational_rules": [
            f"Preserve application_id={paths.application_id}, run_id={run_id}, node_id=compose_cv.",
            f"Read the immutable attempt manifest first: {manifest_path.resolve()}.",
            "Read only read_allowlist and write only write_allowlist.",
            "Do not request or infer a new application ID.",
        ],
        "forbidden_actions": [
            "editar DOCX diretamente",
            "usar estado global ou outra candidatura",
            "inserir keyword sem evidência",
            "alterar FIT_MAP, registry ou Notion",
        ],
    }
    write_json(request_json, payload)
    write_text(
        request_md,
        "# Cellular CV repair request\n\n"
        + "\n".join(
            [
                f"- application_id: `{paths.application_id}`",
                f"- run_id: `{run_id}`",
                f"- node_id: `compose_cv`",
                f"- manifest: `{manifest_path.resolve()}`",
                f"- review: `{review_report_path.resolve()}`",
                f"- output: `{candidate_path.resolve()}`",
                "",
                "## Missing top 8",
                *[f"- {item['keyword']} -> {item.get('experience_target') or 'target from review'}" for item in missing_top8],
                "",
                "## Rules",
                *[f"- {rule}" for rule in payload["repair_rules"]],
            ]
        )
        + "\n",
    )
    _prepare_external_agent_handoff(
        request_json=request_json,
        request_md=request_md,
        read_allowlist=read_allowlist,
        write_allowlist=[str(candidate_path.resolve())],
        application_dir=paths.app_dir,
    )
    return request_json, request_md


def _bind_cellular_cv_repair_candidate(
    candidate_path: Path, *, application_id: str, run_id: str, attempt: int
) -> None:
    """Bind agent-authored content to the reserved compose attempt."""
    payload = read_json(candidate_path)
    if not isinstance(payload, dict):
        raise ValidationFailure("cellular CV repair candidate must be a JSON object")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValidationFailure("cellular CV repair candidate metadata is missing")
    if metadata.get("application_id") not in {None, application_id}:
        raise ValidationFailure("cellular CV repair candidate belongs to another application")
    if metadata.get("run_id") not in {None, "", run_id}:
        raise ValidationFailure("cellular CV repair candidate belongs to another run")
    if metadata.get("compose_attempt") not in {None, "", attempt}:
        try:
            if int(metadata.get("compose_attempt")) != attempt:
                raise ValidationFailure("cellular CV repair candidate belongs to another compose attempt")
        except (TypeError, ValueError) as exc:
            raise ValidationFailure("cellular CV repair candidate compose attempt is invalid") from exc
    metadata = dict(metadata)
    metadata["application_id"] = application_id
    metadata["run_id"] = run_id
    metadata["compose_attempt"] = attempt
    payload["metadata"] = metadata
    write_json(candidate_path, payload)


def _cellular_cv_repair_agent(
    *,
    paths: Any,
    repair_result: Any,
    review_report_path: Path,
    options: HeartbeatV2Options,
    config: dict[str, Any],
) -> tuple[dict[str, Any], Path]:
    candidate_path = _cellular_cv_repair_candidate_path(
        paths, repair_result.run_id, repair_result.attempt
    )
    request_json, request_md = _write_cellular_cv_repair_request(
        paths=paths,
        run_id=repair_result.run_id,
        attempt=repair_result.attempt,
        manifest_path=repair_result.manifest_path,
        review_report_path=review_report_path,
        candidate_path=candidate_path,
    )
    supervisor = HarnessSupervisor(_cellular_workspace_root())
    result = supervisor.run_application_stage(
        stage="repair",
        record_key=paths.application_id,
        application_dir=paths.app_dir,
        request_json=request_json,
        request_md=request_md,
        runner_config=dict(config.get("generation_runner") or {}),
        model=str(options.model or config.get("active_model") or ""),
        variant=str(options.variant or config.get("active_variant") or ""),
        workspace_owner=str(options.workspace_owner or os.environ.get("CAREER_WORKSPACE_OWNER") or ""),
        control_db_id=str(options.control_db_id or os.environ.get("CAREER_CONTROL_DB_ID") or ""),
    )
    return result, candidate_path


def _cellular_review_report_path(paths: Any, run_id: str, node_id: str = "review_cv") -> Path:
    database = canonical_database()
    try:
        row = database.fetch_one(
            "SELECT latest_attempt FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (run_id, node_id),
        )
    finally:
        database.close()
    if row is None or int(row["latest_attempt"] or 0) <= 0:
        raise ValidationFailure(f"cellular review attempt is missing: {run_id}")
    return (
        paths.app_dir
        / "cells"
        / run_id
        / node_id
        / str(row["latest_attempt"])
        / "staging"
        / "cv_review.json"
    )


def _drain_cellular_ready_waves(executor: Any, run_id: str) -> list[Any]:
    """Advance deterministic cells until an external node or blocker remains."""
    executed: list[Any] = []
    for _ in range(16):
        ready = tuple(executor.ready_nodes(run_id))
        if "analyze_fit" in ready:
            break
        batch = list(executor.run_ready(run_id))
        if not batch:
            break
        executed.extend(batch)
    return executed


def _execute_cellular_ready(executor: Any, run_id: str) -> list[Any]:
    """Execute one cellular window, respecting the persisted run policy."""
    if not hasattr(executor, "_load_run"):
        # Compatibility adapter for legacy service doubles. Production
        # executors always expose the persisted policy below.
        executed = list(executor.run_ready(run_id))
        executed.extend(_drain_cellular_ready_waves(executor, run_id))
        return executed
    plan, _paths = executor._load_run(run_id)
    if plan.execution_mode == "serial":
        return list(executor.run_serial_stage(run_id))
    executed = list(executor.run_ready(run_id))
    executed.extend(_drain_cellular_ready_waves(executor, run_id))
    return executed


def _cellular_analyze_dispatch_allowed(
    *,
    plan: Any,
    statuses: dict[str, str],
    ready_nodes: set[str] | tuple[str, ...] | list[str],
    request_json: Path,
    request_md: Path,
) -> bool:
    """Keep external FIT_MAP dispatch scoped to the current serial window."""
    if plan.execution_mode == "serial":
        report = serial_stage_report(plan, statuses)
        if report.stage != "analyze" or report.status != "ready":
            return False
    elif "analyze_fit" not in ready_nodes:
        return False
    return (
        "analyze_fit" in ready_nodes
        and request_json.is_file()
        and request_md.is_file()
    )


def _existing_blocked_cellular_review(
    executor: Any, paths: Any, run_id: str
) -> Any | None:
    """Expose a persisted blocked review so an explicit resume can repair it."""
    row = executor.database.fetch_one(
        "SELECT status, latest_attempt FROM cell_nodes "
        "WHERE run_id = ? AND node_id = 'review_cv'",
        (run_id,),
    )
    if row is None or str(row["status"]) != "blocked":
        return None
    attempt = int(row["latest_attempt"] or 0)
    manifest_path = paths.cells_dir / run_id / "review_cv" / str(attempt) / "manifest.json"
    if attempt <= 0 or not manifest_path.is_file():
        return None
    manifest = read_json(manifest_path)
    if (
        manifest.get("kind") != "cell_attempt_manifest"
        or manifest.get("application_id") != paths.application_id
        or manifest.get("run_id") != run_id
        or manifest.get("node_id") != "review_cv"
        or int(manifest.get("attempt") or 0) != attempt
        or manifest.get("status") != "blocked"
    ):
        raise ValidationFailure("persisted cellular review manifest identity is invalid")
    blocker = manifest.get("blocker") if isinstance(manifest.get("blocker"), dict) else {}
    from career.cells.executor import CellExecutionResult

    return CellExecutionResult(
        run_id=run_id,
        node_id="review_cv",
        attempt=attempt,
        status="blocked",
        manifest_path=manifest_path,
        blocker=str(blocker.get("reason") or "review_cv_blocked"),
    )


def _pending_cellular_cv_repair(
    executor: Any, paths: Any, run_id: str
) -> Any | None:
    """Recover a deferred compose repair whose agent never wrote a candidate."""
    compose = executor.database.fetch_one(
        "SELECT status, latest_attempt FROM cell_nodes "
        "WHERE run_id = ? AND node_id = 'compose_cv'",
        (run_id,),
    )
    review = executor.database.fetch_one(
        "SELECT status, latest_attempt FROM cell_nodes "
        "WHERE run_id = ? AND node_id = 'review_cv'",
        (run_id,),
    )
    if (
        compose is None
        or str(compose["status"]) not in {"planned", "repairing"}
        or int(compose["latest_attempt"] or 0) <= 1
        or review is None
        or int(review["latest_attempt"] or 0) <= 0
    ):
        return None
    candidate_path = _cellular_cv_repair_candidate_path(
        paths, run_id, int(compose["latest_attempt"])
    )
    if candidate_path.is_file():
        return None
    review_attempt = int(review["latest_attempt"])
    manifest_path = (
        paths.cells_dir
        / run_id
        / "review_cv"
        / str(review_attempt)
        / "manifest.json"
    )
    if not manifest_path.is_file():
        return None
    manifest = read_json(manifest_path)
    if (
        manifest.get("kind") != "cell_attempt_manifest"
        or manifest.get("application_id") != paths.application_id
        or manifest.get("run_id") != run_id
        or manifest.get("node_id") != "review_cv"
        or int(manifest.get("attempt") or 0) != review_attempt
        or manifest.get("status") not in {"blocked", "superseded"}
    ):
        raise ValidationFailure("pending cellular review manifest identity is invalid")
    blocker = manifest.get("blocker") if isinstance(manifest.get("blocker"), dict) else {}
    from career.cells.executor import CellExecutionResult

    return CellExecutionResult(
        run_id=run_id,
        node_id="review_cv",
        attempt=review_attempt,
        status="blocked",
        manifest_path=manifest_path,
        blocker=str(blocker.get("reason") or "review_cv_blocked"),
    )


def _process_cellular_application(
    application: dict[str, Any],
    *,
    options: HeartbeatV2Options,
    config: dict[str, Any],
    database_path: Path,
) -> list[dict[str, Any]]:
    """Advance one application independently; callers may run this concurrently."""
    from career.cells.executor import CellExecutor, CellExecutionResult, PreparedCellAttempt
    from career.cells.handlers import (
        production_handler_registry,
        production_validator_registry,
    )

    database = Database(database_path)
    database.init_schema()
    paths = _ensure_cellular_application(
        application,
        applications_root=V2_DIR,
        database_path=database_path,
    )
    executor = CellExecutor(
        database,
        applications_root=V2_DIR,
        handlers=production_handler_registry(),
        validators=production_validator_registry(),
        worker_id=f"applications-cellular-{paths.application_id}-{os.getpid()}-{id(database)}",
        workspace_owner=options.workspace_owner,
        workspace_control_db_id=options.control_db_id,
        require_authoritative_workspace=True,
    )
    try:
        job_fingerprint = sha256_file(paths.job_description)
        completion_path = _completion_receipt_path(paths)
        reprocess_request = _read_reprocess_request(paths)
        reprocess_pending = bool(
            _is_reprocess_requested(application, config)
            and reprocess_request.get("status") in {"pending", "consumed"}
        )
        if not completion_path.is_file() and not reprocess_pending:
            _recover_completed_cellular_receipt(
                application,
                paths=paths,
                job_fingerprint=job_fingerprint,
                success_status=str(config["success_status"]),
                update_tracker=lambda status: _update_notion_status(
                    application, status, dry_run=False
                ),
            )
        requested_run_id = str(application.get("_cellular_run_id") or "").strip()
        if completion_path.is_file() and not reprocess_pending:
            completion = read_json(completion_path)
            if (
                completion.get("status") == "completed"
                and completion.get("job_fingerprint") == job_fingerprint
                and (
                    not requested_run_id
                    or str(completion.get("run_id") or "") == requested_run_id
                )
            ):
                return [
                    {
                        "status": "already_completed",
                        "application_id": paths.application_id,
                        "run_id": completion.get("run_id"),
                        "node_id": "sync_notion_final",
                        "artifact_paths": [],
                        "blocker": "",
                    }
                ]

        run_id = _select_or_plan_cellular_run(
            application, paths=paths, executor=executor, config=config
        )

        recover_stale_attempt = getattr(
            executor, "recover_stale_external_attempt", None
        )
        stale_analyze_recovery = (
            recover_stale_attempt(run_id, "analyze_fit")
            if callable(recover_stale_attempt)
            else {"status": "unchanged"}
        )
        if stale_analyze_recovery.get("status") == "blocked":
            return [
                {
                    "status": "blocked",
                    "application_id": paths.application_id,
                    "run_id": run_id,
                    "node_id": "analyze_fit",
                    "artifact_paths": [],
                    "blocker": stale_analyze_recovery.get(
                        "blocker_reason", "active_analyze_fit_lease"
                    ),
                }
            ]
        if stale_analyze_recovery.get("status") in {"planned", "awaiting_agent"}:
            return [
                {
                    "status": "awaiting_agent",
                    "application_id": paths.application_id,
                    "run_id": run_id,
                    "node_id": "analyze_fit",
                    "attempt": stale_analyze_recovery["next_attempt"],
                    "manifest_path": stale_analyze_recovery.get("handoff_manifest_path", ""),
                    "handoff_path": stale_analyze_recovery.get("handoff_path", ""),
                    "artifact_paths": [],
                    "blocker": "stale_analyze_binding_recovered",
                }
            ]

        ready_before_analyze = set(executor.ready_nodes(run_id))
        if "analyze_fit" in ready_before_analyze:
            plan, _run_paths = executor._load_run(run_id)
            dispatch_statuses = dict(executor.resume(run_id).statuses)
            prepared = _prepare_cellular_analyze_attempt(executor, paths, run_id)
            try:
                request_json, request_md = _write_cellular_analyze_request(
                    paths,
                    prepared,
                    workspace_owner=options.workspace_owner
                    or os.environ.get("CAREER_WORKSPACE_OWNER")
                    or "",
                    control_db_id=str(
                        options.control_db_id
                        or os.environ.get("CAREER_CONTROL_DB_ID")
                        or ""
                    ),
                )
            except Exception as exc:
                reason = f"analyze_request_preparation_failed:{type(exc).__name__}:{exc}"
                executor.defer_prepared_attempt(prepared, reason=reason)
                return [
                    {
                        "status": "awaiting_agent",
                        "application_id": paths.application_id,
                        "run_id": run_id,
                        "node_id": "analyze_fit",
                        "manifest_path": str(prepared.manifest_path),
                        "artifact_paths": [],
                        "blocker": reason,
                    }
                ]
            if not _cellular_analyze_dispatch_allowed(
                plan=plan,
                statuses=dispatch_statuses,
                ready_nodes=ready_before_analyze,
                request_json=request_json,
                request_md=request_md,
            ):
                executor.defer_prepared_attempt(
                    prepared, reason="cellular_analyze_dispatch_gate_not_satisfied"
                )
                return [
                    {
                        "status": "awaiting_agent",
                        "application_id": paths.application_id,
                        "run_id": run_id,
                        "node_id": "analyze_fit",
                        "manifest_path": str(prepared.manifest_path),
                        "artifact_paths": [],
                        "blocker": "cellular_analyze_dispatch_gate_not_satisfied",
                    }
                ]
            with executor.keep_prepared_attempt_alive(prepared) as keepalive:
                agent_result = _run_cellular_analyze_agent(
                    paths,
                    prepared,
                    options=options,
                    config=config,
                    request_paths=(request_json, request_md),
                )
            agent_ok = (
                agent_result.get("returncode") == 0
                and (agent_result.get("isolation") or {}).get("status") == "ok"
                and paths.fit_map_draft.is_file()
                and not keepalive.get("failure")
            )
            if not agent_ok:
                agent_stderr = str(agent_result.get("stderr") or "").strip()
                if "no usable credentials found for provider 'ollama-cloud'" in agent_stderr.casefold():
                    agent_failure = "missing_ollama_cloud_credentials"
                elif agent_stderr:
                    agent_failure = "agent_returned_nonzero:" + " ".join(agent_stderr.split())[-500:]
                else:
                    agent_failure = "agent_returned_nonzero"
                reason = (
                    str(keepalive.get("failure") or "")
                    or str(agent_result.get("blocker_reason") or "")
                    or (agent_failure if agent_result.get("returncode") != 0 else "agent_output_not_available")
                )
                failed_dir = (
                    paths.requests_dir
                    / "cellular"
                    / prepared.run_id
                    / prepared.node_id
                    / str(prepared.attempt)
                )
                _quarantine_cellular_draft(
                    paths, reason="failed", target_dir=failed_dir
                )
                executor.defer_prepared_attempt(prepared, reason=reason)
                manifest = read_json(prepared.manifest_path)
                capabilities = manifest.get("capabilities") or {}
                return [
                    {
                        "status": "awaiting_agent",
                        "application_id": paths.application_id,
                        "run_id": run_id,
                        "node_id": "analyze_fit",
                        "manifest_path": str(prepared.manifest_path),
                        "read_allowlist": list(capabilities.get("read_paths") or []),
                        "write_allowlist": list(capabilities.get("write_paths") or []),
                        "artifact_paths": [],
                        "blocker": reason,
                    }
                ]
            write_json(
                _draft_binding_path(paths),
                {
                    "kind": "cellular_fit_map_draft_binding",
                    "application_id": paths.application_id,
                    "run_id": prepared.run_id,
                    "node_id": prepared.node_id,
                    "attempt": prepared.attempt,
                    "job_fingerprint": sha256_file(paths.job_description),
                    "draft_sha256": sha256_file(paths.fit_map_draft),
                    "manifest_path": str(prepared.manifest_path),
                },
            )

        existing_blocked_review = _existing_blocked_cellular_review(
            executor, paths, run_id
        ) or _pending_cellular_cv_repair(executor, paths, run_id)
        if existing_blocked_review is not None:
            executed = [existing_blocked_review]
        else:
            executed = _execute_cellular_ready(executor, run_id)
        repair_round = 0
        processed_review_attempts: set[tuple[int, str]] = set()
        max_repair_rounds = max(0, int(config.get("repair_max_attempts") or 0))
        while repair_round < max_repair_rounds:
            blocked_review = next(
                (
                    item
                    for item in reversed(executed)
                    if item.node_id == "review_cv" and item.status == "blocked"
                ),
                None,
            )
            if blocked_review is None:
                break
            review_report_path = (
                Path(blocked_review.manifest_path).parent
                / "staging"
                / "cv_review.json"
            )
            review_key = (int(blocked_review.attempt), str(blocked_review.manifest_path))
            if review_key in processed_review_attempts:
                break
            processed_review_attempts.add(review_key)
            review_report = read_json(review_report_path) if review_report_path.is_file() else {}
            polish_report_path = review_report_path.parent / "polish_review.json"
            polish_report = (
                read_json(polish_report_path) if polish_report_path.is_file() else {}
            )
            blockers = {
                str(item.get("id"))
                for item in review_report.get("blockers", [])
                if isinstance(item, dict)
            }
            repairable = {
                "ats_top8_minimum_score",
                "ats_top8_no_missing_unexplained",
                "pt_cv_keyword_shotgun_control",
                "summary_keyword_coverage",
                "summary_support",
            }
            if not blockers or not blockers.issubset(repairable):
                break

            current_cv_hash = _latest_cellular_cv_content_sha256(
                executor, paths, run_id
            )
            previous_progress = _latest_cellular_repair_progress(
                executor, paths, run_id
            )
            progress_decision = inspect_repair_progress(
                review_report=review_report,
                cv_content_sha256=current_cv_hash,
                previous_progress=previous_progress,
                polish_report=polish_report,
            )
            if progress_decision["status"] == "changed" and previous_progress is None:
                _persist_cellular_repair_progress(
                    paths, run_id, int(blocked_review.attempt), progress_decision
                )
            if progress_decision["status"] == "no_progress":
                _persist_cellular_repair_progress(
                    paths, run_id, int(blocked_review.attempt), progress_decision
                )
                results = [
                    _cell_execution_payload(item, application_id=paths.application_id)
                    for item in executed
                ]
                results.append(
                    {
                        "status": "blocked",
                        "application_id": paths.application_id,
                        "run_id": run_id,
                        "node_id": "review_cv",
                        "attempt": blocked_review.attempt,
                        "manifest_path": str(blocked_review.manifest_path),
                        "artifact_paths": [],
                        "blocker": "cv_repair_no_progress",
                        "progress": progress_decision,
                    }
                )
                return results

            repair_round += 1
            reason = blocked_review.blocker or ",".join(sorted(blockers))
            repair_result = executor.repair(run_id, "compose_cv", reason)
            prepared = PreparedCellAttempt(
                run_id=repair_result.run_id,
                application_id=paths.application_id,
                node_id=repair_result.node_id,
                attempt=repair_result.attempt,
                worker_id=executor.worker_id,
                manifest_path=repair_result.manifest_path,
            )
            try:
                agent_result, candidate_path = _cellular_cv_repair_agent(
                    paths=paths,
                    repair_result=repair_result,
                    review_report_path=review_report_path,
                    options=options,
                    config=config,
                )
                if candidate_path.is_file():
                    _bind_cellular_cv_repair_candidate(
                        candidate_path,
                        application_id=paths.application_id,
                        run_id=run_id,
                        attempt=repair_result.attempt,
                    )
                agent_ok = (
                    agent_result.get("returncode") == 0
                    and (agent_result.get("isolation") or {}).get("status") == "ok"
                    and candidate_path.is_file()
                )
            except Exception as exc:
                agent_result = {
                    "returncode": 1,
                    "isolation": {"status": "blocked"},
                    "blocker_reason": f"repair_agent_exception:{type(exc).__name__}:{exc}",
                }
                candidate_path = _cellular_cv_repair_candidate_path(
                    paths, repair_result.run_id, repair_result.attempt
                )
                agent_ok = False
            if not agent_ok:
                reason = str(
                    agent_result.get("blocker_reason")
                    or agent_result.get("stderr")
                    or "cellular_cv_repair_agent_failed"
                )
                executor.defer_prepared_attempt(prepared, reason=reason)
                results = [
                    _cell_execution_payload(item, application_id=paths.application_id)
                    for item in executed
                ]
                results.append(
                    {
                        "status": "awaiting_agent",
                        "application_id": paths.application_id,
                        "run_id": run_id,
                        "node_id": "compose_cv",
                        "manifest_path": str(repair_result.manifest_path),
                        "artifact_paths": [],
                        "blocker": reason,
                    }
                )
                return results

            executed.extend(_execute_cellular_ready(executor, run_id))
            latest_blocked_review = next(
                (
                    item
                    for item in reversed(executed)
                    if item.node_id == "review_cv" and item.status == "blocked"
                ),
                None,
            )
            if latest_blocked_review is not None:
                latest_report_path = (
                    Path(latest_blocked_review.manifest_path).parent
                    / "staging"
                    / "cv_review.json"
                )
                if latest_report_path.is_file():
                    latest_report = read_json(latest_report_path)
                    latest_polish_path = latest_report_path.parent / "polish_review.json"
                    latest_polish = (
                        read_json(latest_polish_path)
                        if latest_polish_path.is_file()
                        else {}
                    )
                    latest_evidence = inspect_repair_progress(
                        review_report=latest_report,
                        cv_content_sha256=_latest_cellular_cv_content_sha256(
                            executor, paths, run_id
                        ),
                        polish_report=latest_polish,
                    )
                    _persist_cellular_repair_progress(
                        paths,
                        run_id,
                        int(repair_result.attempt),
                        latest_evidence,
                    )

        results = [
            _cell_execution_payload(item, application_id=paths.application_id)
            for item in executed
        ]
        if executor.is_terminal(run_id):
            completion = executor.finalize(run_id)
            if completion.manifest.get("status") == "completed":
                delivery_artifact = next(
                    (
                        item
                        for item in completion.manifest.get("validated_artifacts", [])
                        if item.get("artifact_name") == "cv_delivery_receipt.json"
                    ),
                    None,
                )
                if delivery_artifact is None:
                    raise ValidationFailure(
                        "completed cellular CV run is missing delivery receipt"
                    )
                persisted_delivery = read_json(Path(delivery_artifact["path"]))
                _complete_cellular_application_once(
                    application,
                    paths=paths,
                    run_id=run_id,
                    job_fingerprint=job_fingerprint,
                    delivery=lambda: {"status": "delivered", **persisted_delivery},
                    update_tracker=lambda status: _update_notion_status(
                        application, status, dry_run=False
                    ),
                    success_status=str(config["success_status"]),
                )
        return results
    finally:
        if options.release_workspace_lease:
            executor.release_workspace_lease()
        database.close()


def _load_explicit_cellular_application(application_id: str) -> dict[str, Any]:
    paths = paths_for(application_id, root=V2_DIR)
    if not paths.job_description.is_file():
        raise ValidationFailure(
            f"cellular application has no persisted job description: {application_id}"
        )
    identity = read_json(paths.identity) if paths.identity.is_file() else {}
    aliases = identity.get("aliases") if isinstance(identity.get("aliases"), dict) else {}
    record_id = str(aliases.get("notion_record_id") or "").strip()
    page_id = _valid_notion_page_id(aliases.get("notion_page_id"))
    return {
        "application_id": application_id,
        "record_id": int(record_id) if record_id.isdigit() else None,
        "page_id": page_id or None,
        "company": str(identity.get("company") or ""),
        "role": str(identity.get("role") or ""),
        "title": str(identity.get("role") or ""),
        "status": "Fila Agente",
        "description": paths.job_description.read_text(encoding="utf-8"),
        "source_type": str(identity.get("source_type") or "local"),
        "source_id": str(identity.get("source_id") or application_id),
        "source_url": str(identity.get("source_url") or ""),
        "delivery_profile": str(identity.get("delivery_profile") or "standard_cv"),
        "_cellular_run_id": "",
        "_explicit_cellular": True,
    }


def run_explicit_cellular(
    *, application_id: str, run_id: str, options: HeartbeatV2Options
) -> dict[str, Any]:
    """Execute one locally persisted cellular run, including agent nodes."""
    from career.cells.executor import CellExecutor

    control_db_id = str(
        options.control_db_id or os.environ.get("CAREER_CONTROL_DB_ID") or ""
    ).strip()
    if not control_db_id:
        raise ValidationFailure("CAREER_CONTROL_DB_ID is required for cellular execution")
    database_path = canonical_database().db_path
    database = Database(database_path)
    try:
        database.init_schema()
        row = database.fetch_one(
            "SELECT application_id FROM application_runs WHERE run_id = ?",
            (run_id,),
        )
        if row is None:
            raise KeyError(f"unknown application run: {run_id}")
        if str(row["application_id"]) != application_id:
            raise ValueError(f"run does not belong to application: {application_id}")
        actual_control_db_id = database.control_db_identity()
        if actual_control_db_id != control_db_id:
            raise ValueError(
                "configured authoritative control database identity does not match "
                f"this database: expected={control_db_id} actual={actual_control_db_id}"
            )
    finally:
        database.close()

    application = _load_explicit_cellular_application(application_id)
    application["_cellular_run_id"] = run_id
    effective_options = replace(
        options,
        run_agent=True,
        dry_run=False,
        cellular=True,
        control_db_id=control_db_id,
        release_workspace_lease=True,
    )
    results = _process_cellular_application(
        application,
        options=effective_options,
        config=_load_config(),
        database_path=database_path,
    )
    inspection = Database(database_path)
    try:
        statuses = inspection.fetch_all(
            "SELECT node_id, status FROM cell_nodes WHERE run_id = ? ORDER BY node_id",
            (run_id,),
        )
        run_row = inspection.fetch_one(
            "SELECT status FROM application_runs WHERE run_id = ?", (run_id,)
        )
        ready = [
            str(item["node_id"])
            for item in CellStore(inspection).list_ready_nodes(run_id)
        ]
        status_map = {
            str(item["node_id"]): str(item["status"]) for item in statuses
        }
        persisted_plan, _persisted_paths = CellExecutor(
            inspection,
            applications_root=V2_DIR,
            worker_id="applications-cellular-status",
        )._load_run(run_id)
        stage_report = (
            serial_stage_report(persisted_plan, status_map)
            if persisted_plan.execution_mode == "serial"
            else None
        )
    finally:
        inspection.close()
    blocked = [str(item["node_id"]) for item in statuses if item["status"] == "blocked"]
    if any(item.get("status") == "awaiting_agent" for item in results):
        status = "awaiting_agent"
    elif stage_report and stage_report.status in {
        "awaiting_agent",
        "awaiting_approval",
        "blocked",
    }:
        status = stage_report.status
    elif blocked:
        status = "blocked"
    elif run_row and run_row["status"] == "completed":
        status = "completed"
    elif ready or stage_report and stage_report.status == "ready":
        status = "ready"
    else:
        status = "running"
    return {
        "status": status,
        "mode": "cellular",
        "run_agent": True,
        "application_id": application_id,
        "run_id": run_id,
        "results": results,
        "ready_nodes": ready,
        "blocked_nodes": blocked,
        "execution_mode": persisted_plan.execution_mode,
        "serial_stage": (
            {
                "stage": stage_report.stage,
                "status": stage_report.status,
                "allowed_nodes": list(stage_report.allowed_nodes),
                "completed_nodes": list(stage_report.completed_nodes),
                "next_stage": stage_report.next_stage,
                "blocked_nodes": list(stage_report.blocked_nodes),
            }
            if stage_report
            else None
        ),
    }


def _run_heartbeat_unlocked(options: HeartbeatV2Options) -> dict[str, Any]:
    V2_DIR.mkdir(parents=True, exist_ok=True)
    V2_LOG_DIR.mkdir(parents=True, exist_ok=True)
    started_at = utc_now_iso()
    config = _load_config()
    maintenance_report = _run_maintenance_sync(config, options)
    token, database_id = notion_service.notion_config()
    applications = _load_queue(token, database_id)
    effective_max = options.max_per_run if options.max_per_run is not None else int(config["max_per_run"])
    selected = _eligible(applications, config, effective_max)
    _emit(f"selected {len(selected)} application(s) directly from Notion")
    if selected:
        ordered = ", ".join(f"{_record_key(item)}:{item.get('status')}" for item in selected)
        _emit(f"selection order -> {ordered}")
    results: list[dict[str, Any]] = []
    skipped_locked: list[dict[str, Any]] = []
    for index, application in enumerate(selected, start=1):
        record_key = _record_key(application)
        lock_path = _app_dir(record_key) / ".lock"
        if lock_path.exists():
            lock = read_json(lock_path)
            skipped = {
                "record_key": record_key,
                "record_id": application.get("record_id"),
                "status": "skipped_locked",
                "lock": lock,
            }
            skipped_locked.append(skipped)
            results.append(skipped)
            _emit(f"queue item {index}/{len(selected)} -> {record_key} skipped because application lock exists")
            continue
        _emit(f"queue item {index}/{len(selected)} -> {record_key}: {application.get('title') or application.get('role')}")
        app_dir, paths = _write_package(application, reset=_is_reprocess_requested(application, config))
        if _is_reprocess_requested(application, config):
            _append_event(paths, "package_reset_for_reprocess", record_id=application.get("record_id"))
        _append_event(
            paths,
            "package_prepared",
            record_id=application.get("record_id"),
            title=application.get("title"),
            status=application.get("status"),
            description_chars=application.get("description_chars"),
        )
        state = _read_state(paths, record_key, application)
        stage, score = _derive_stage(paths, config)
        _set_stage(state, stage)
        _set_service_status(state)
        state["score"] = score
        state["status"] = application.get("status")
        state["notion_status"] = application.get("status")
        _write_state(paths, state)
        if stage == "analyze_pending":
            _write_request(paths, "analyze", _analysis_request(application, paths))
        elif stage == "generate_pending":
            _write_request(paths, "generate", _generation_request(application, paths))
        _write_context(application, paths, state)
        try:
            if stage == "no_description":
                if not options.dry_run:
                    _update_notion_status(application, str(config["no_description_status"]), dry_run=False)
                    _append_event(paths, "notion_status_updated", status=str(config["no_description_status"]))
                state["notion_status"] = str(config["no_description_status"])
                _write_state(paths, state)
            elif options.run_agent and not options.dry_run:
                _update_notion_status(application, str(config["running_status"]), dry_run=False)
                state["notion_status"] = str(config["running_status"])
                _append_event(paths, "notion_status_updated", status=str(config["running_status"]))
                if stage == "analyze_pending":
                    _set_stage(state, "analyze_running")
                    _set_service_status(state)
                    _write_state(paths, state)
                    _write_context(application, paths, state)
                    score = _run_analyze_with_retry(application, paths, config, options, state)
                    state["score"] = score
                    state["last_error"] = None
                    if score < float(config["score_threshold"]):
                        _set_stage(state, "low_fit")
                        _set_service_status(state)
                        _publish_notion_service_state(application, paths, state, status=str(config["low_fit_status"]))
                    else:
                        _set_stage(state, "generate_pending")
                        _set_service_status(state)
                if state["stage"] == "generate_pending":
                    _set_stage(state, "generate_running")
                    _set_service_status(state)
                    _write_state(paths, state)
                    _write_request(paths, "generate", _generation_request(application, paths))
                    _write_context(application, paths, state)
                    _run_agent("generate", application, paths, config, options, state)
                    generate_result = _postprocess_generate(paths)
                    _set_stage(state, str(generate_result["stage"]))
                    _set_service_status(state)
                    state["output_docx"] = generate_result.get("output_docx")
                    state["review_status"] = generate_result.get("review_status", state.get("review_status"))
                    state["polish_status"] = generate_result.get("polish_status", state.get("polish_status"))
                    state["last_error"] = generate_result.get("message") if state["stage"] == "blocked_review" else None
                    if state["stage"] == "done":
                        _publish_notion_service_state(application, paths, state, status=str(config["success_status"]))
                    elif state["stage"] == "blocked_review":
                        _write_repair_request(
                            paths,
                            state,
                            generate_result.get("review_report", {}) if isinstance(generate_result.get("review_report"), dict) else {},
                            generate_result.get("polish_report", {}) if isinstance(generate_result.get("polish_report"), dict) else {},
                        )
                        _publish_notion_service_state(
                            application,
                            paths,
                            state,
                            status=str(config["blocked_review_status"]),
                            review_report=generate_result.get("review_report", {}) if isinstance(generate_result.get("review_report"), dict) else {},
                            polish_report=generate_result.get("polish_report", {}) if isinstance(generate_result.get("polish_report"), dict) else {},
                        )
                        repair_allowed, repair_reason = _repair_decision(
                            generate_result.get("review_report", {}) if isinstance(generate_result.get("review_report"), dict) else {},
                            generate_result.get("polish_report", {}) if isinstance(generate_result.get("polish_report"), dict) else {},
                            state,
                            config,
                        )
                        _append_event(
                            paths,
                            "repair_cycle_evaluated",
                            repair_allowed=repair_allowed,
                            repair_reason=repair_reason,
                            llm_session_count=_current_llm_session_count(state),
                            llm_session_budget=_llm_session_budget(config),
                            llm_session_remaining=_remaining_llm_sessions(state, config),
                        )
                        if repair_allowed:
                            generate_result = _run_repair_cycle(application, paths, config, options, state, generate_result)
                            if state["stage"] == "done":
                                _set_service_status(state, "done")
                            elif state["stage"] == "blocked_review_exhausted":
                                state["last_error"] = state.get("last_error") or generate_result.get("message")
                        else:
                            _set_stage(state, "blocked_review_exhausted")
                            _set_service_status(state, "blocked_review_exhausted")
                            state["last_error"] = state.get("last_error") or repair_reason or generate_result.get("message")
                _write_state(paths, state)
                _write_context(application, paths, state)
            result = _result_payload(application, paths, state)
            write_json(paths["run_result"], result)
            _append_event(paths, "run_result_written", result=result)
            results.append(result)
            _write_index([result])
            _emit(
                f"result {record_key} -> status={result['status']}; "
                f"score={result['score']}; output={result.get('output_docx') or '-'}"
            )
            _emit(f"completed queue item {index}/{len(selected)}")
        except BaseException as exc:
            _set_stage(state, "error")
            state["last_error"] = str(exc)
            if not options.dry_run and application.get("page_id"):
                try:
                    _update_notion_status(application, str(config["error_status"]), dry_run=False)
                    state["notion_status"] = str(config["error_status"])
                    _append_event(paths, "notion_status_updated", status=str(config["error_status"]))
                except BaseException as notion_exc:
                    _append_event(paths, "notion_status_update_failed", status=str(config["error_status"]), message=str(notion_exc))
            _write_state(paths, state)
            error = {
                "record_key": record_key,
                "record_id": application.get("record_id"),
                "status": "error",
                "message": str(exc),
                "application_dir": str(app_dir.relative_to(ROOT)),
                "updated_at": utc_now_iso(),
            }
            write_json(paths["error_report"], error)
            _append_event(paths, "error", message=str(exc))
            results.append(error)
            _write_index([error])
            _emit(f"result {record_key} -> status=error; message={str(exc)}")
    summary = {
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "dry_run": options.dry_run,
        "run_agent": options.run_agent,
        "maintenance": maintenance_report,
        "max_per_run": effective_max,
        "selected": len(selected),
        "skipped_locked": skipped_locked,
        "results": results,
        "index": str(V2_INDEX.relative_to(ROOT)),
    }
    log_path = V2_LOG_DIR / (started_at.replace(":", "").replace("+", "Z") + ".json")
    write_json(log_path, summary)
    summary["log"] = str(log_path.relative_to(ROOT))
    return summary


def heartbeat_status() -> dict[str, Any]:
    config = _load_config()
    queue_aliases = {_normalize_status(item) for item in config.get("queue_status_aliases", [])}
    reprocess_aliases = {_normalize_status(item) for item in config.get("reprocess_status_aliases", [])}
    cache = read_json(NOTION_CACHE) if NOTION_CACHE.exists() else {"applications": []}
    applications = cache.get("applications", []) if isinstance(cache, dict) else []
    active_applications = [item for item in applications if not item.get("is_archived")]
    queue_items = []
    no_description = 0
    for item in active_applications:
        status_norm = _normalize_status(str(item.get("status") or ""))
        description_chars = int(item.get("description_chars") or 0)
        if description_chars <= 0:
            no_description += 1
        if status_norm in queue_aliases or status_norm in reprocess_aliases:
            queue_items.append(item)

    notion_status_counts: dict[str, int] = {}
    for item in active_applications:
        status = str(item.get("status") or "Sem status").strip() or "Sem status"
        notion_status_counts[status] = notion_status_counts.get(status, 0) + 1

    index_payload = read_json(V2_INDEX) if V2_INDEX.exists() else {"applications": []}
    indexed = index_payload.get("applications", []) if isinstance(index_payload, dict) else []
    stage_counts: dict[str, int] = {}
    retryable = 0
    errors = 0
    for item in indexed:
        stage = str(item.get("status") or "unknown")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        if item.get("retryable"):
            retryable += 1
        if stage == "error":
            errors += 1

    maintenance_state = _read_maintenance_state()
    payload = {
        "generated_at": utc_now_iso(),
        "maintenance": {
            **maintenance_state,
            "hours_since_full": _hours_since(maintenance_state.get("last_full_sync_at")),
        },
        "queue": {
            "eligible_now": len(queue_items),
            "reprocess_now": sum(1 for item in queue_items if _normalize_status(str(item.get("status") or "")) in reprocess_aliases),
            "missing_description_now": no_description,
            "top_candidates": [
                {
                    "record_id": item.get("record_id"),
                    "title": item.get("title"),
                    "status": item.get("status"),
                    "description_chars": item.get("description_chars"),
                }
                for item in queue_items[:5]
            ],
        },
        "notion": {
            "total_active": len(active_applications),
            "status_counts": dict(sorted(notion_status_counts.items(), key=lambda entry: (-entry[1], entry[0]))[:10]),
        },
        "local_runtime": {
            "tracked_applications": len(indexed),
            "stage_counts": stage_counts,
            "retryable_count": retryable,
            "error_count": errors,
        },
    }
    return payload


def _parallel_fixture_job(application_id: str) -> str:
    focus = "regional capacity planning" if application_id.endswith("a") else "national logistics governance"
    return (
        f"# Operations Lead {application_id}\n\n"
        f"Company: Fixture {application_id}\n"
        f"Responsibilities: lead {focus}, indicators, and continuous improvement.\n"
        "Requirements: operations leadership, planning, and data analysis.\n"
        + (f"Distinct context for {application_id}. " * 24)
    )


def _run_parallel_fixture_worker(
    fixture_dir: Path,
    application_id: str,
    result_path: Path,
) -> int:
    """Subprocess-only worker used by the real parallel acceptance harness."""
    from career.cells.capabilities import recorded_capability_violations
    from career.cells.contracts import CELL_CONTRACTS
    from career.cells.executor import CellExecutor
    from career.cells.handlers import (
        CellOutput,
        ValidatorResult,
        production_handler_registry,
        production_validator_registry,
    )

    fixture_dir = fixture_dir.resolve()
    applications_root = fixture_dir / "applications"
    database = Database(fixture_dir / "career.db")
    database.init_schema()
    paths = paths_for(application_id, root=applications_root)
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        paths.identity,
        {
            "kind": "application_identity",
            "application_id": application_id,
            "source_type": "parallel_fixture",
            "source_id": application_id,
            "company": f"Fixture {application_id}",
            "role": "Operations Lead",
        },
    )
    write_text(paths.job_description, _parallel_fixture_job(application_id))
    worker_id = f"parallel-{application_id}-{os.getpid()}"
    interval: dict[str, int] = {}

    def notion_handler(_context):
        interval["entered_at"] = time.time_ns()
        time.sleep(0.2)
        interval["released_at"] = time.time_ns()
        return CellOutput(
            artifacts={
                "notion_initial_receipt.json": json.dumps(
                    {"status": "ok", "application_id": application_id}
                ).encode("utf-8")
            }
        )

    def notion_validator(context, _output):
        report = context.paths.reviews_dir / (
            f"{context.node_id}-{context.attempt}-parallel-lock.json"
        )
        write_json(report, {"result": "passed"})
        return ValidatorResult.passed(context.validator_command, report)

    handlers = production_handler_registry()
    validators = production_validator_registry()
    handlers["sync_notion_initial"] = notion_handler
    validators["validate-notion-receipt"] = notion_validator
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers=handlers,
        validators=validators,
        worker_id=worker_id,
        workspace_owner=os.environ.get("CAREER_WORKSPACE_OWNER") or "parallel-fixture",
        workspace_control_db_id=os.environ.get("CAREER_CONTROL_DB_ID"),
        require_authoritative_workspace=True,
        lease_seconds=30,
    )
    plan = executor.plan(application_id, {"notion"})
    results = executor.run_ready(plan.run_id)
    normalized = next(
        (item for item in results if item.node_id == "normalize_job"), None
    )
    if normalized is None or normalized.status != "validated":
        database.close()
        raise RuntimeError("parallel fixture normalization did not validate")
    executor.mark_validated(plan.run_id, "analyze_fit")
    ready_marker = fixture_dir / f"{application_id}-ready"
    ready_marker.write_text(str(os.getpid()), encoding="utf-8")
    ready_deadline = time.monotonic() + 10
    while time.monotonic() < ready_deadline:
        if len(list(fixture_dir.glob("*-ready"))) >= 2:
            break
        time.sleep(0.01)
    else:
        database.close()
        raise RuntimeError("parallel fixture workers did not reach the contention barrier")
    contention_count = 0
    external = None
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        batch = executor.run_ready(plan.run_id)
        external = next(
            (item for item in batch if item.node_id == "sync_notion_initial"),
            None,
        )
        if external is not None and external.status == "validated":
            break
        if external is not None and external.status == "deferred":
            contention_count += 1
        time.sleep(0.02)
    if external is None or external.status != "validated":
        database.close()
        raise RuntimeError("executor-managed declared resource did not validate")
    handover = read_json(normalized.manifest_path.parent / "handover_summary.json")
    manifest = read_json(normalized.manifest_path)
    payload = {
        "status": normalized.status,
        "pid": os.getpid(),
        "application_id": application_id,
        "run_id": plan.run_id,
        "node_id": normalized.node_id,
        "manifest_path": str(normalized.manifest_path),
        "artifact_paths": [str(item["path"]) for item in manifest["outputs"]],
        "job_fingerprint": handover["job_fingerprint"],
        "external_resource": "notion-write",
        "external_lock_entered_at": interval["entered_at"],
        "external_lock_released_at": interval["released_at"],
        "external_lock_contention_count": contention_count,
        "external_lock_node_id": "sync_notion_initial",
        "external_resource_declared_by_contract": (
            "notion-write" in CELL_CONTRACTS["sync_notion_initial"].resources
        ),
        "capability_violations": [
            item["target"] for item in recorded_capability_violations()
        ],
    }
    write_json(result_path, payload)
    database.close()
    return 0


def run_parallel_fixture_workers(
    fixture_dir: str | Path,
    *,
    applications: tuple[str, str] = ("app-a", "app-b"),
) -> list[dict[str, Any]]:
    """Run two real processes on one workspace/database and assert isolation."""
    if len(applications) != 2 or len(set(applications)) != 2:
        raise ValueError("parallel verification requires two distinct applications")
    fixture = Path(fixture_dir).resolve()
    fixture.mkdir(parents=True, exist_ok=True)
    database = Database(fixture / "career.db")
    database.init_schema()
    control_db_id = database.control_db_identity()
    database.close()
    env = os.environ.copy()
    env["CAREER_WORKSPACE_OWNER"] = "parallel-fixture"
    env["CAREER_CONTROL_DB_ID"] = control_db_id
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    processes: list[tuple[str, Path, subprocess.Popen[str]]] = []
    for application_id in applications:
        result_path = fixture / f"{application_id}-result.json"
        command = [
            sys.executable,
            "-m",
            "career.services.applications_v2",
            "--parallel-fixture-worker",
            "--fixture-dir",
            str(fixture),
            "--application-id",
            application_id,
            "--result-path",
            str(result_path),
        ]
        processes.append(
            (
                application_id,
                result_path,
                subprocess.Popen(
                    command,
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                ),
            )
        )
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for application_id, result_path, process in processes:
        stdout, stderr = process.communicate(timeout=30)
        if process.returncode != 0 or not result_path.is_file():
            errors.append(
                f"{application_id}:returncode={process.returncode};stdout={stdout[-1000:]};stderr={stderr[-2000:]}"
            )
            continue
        results.append(read_json(result_path))
    if errors:
        raise RuntimeError("parallel fixture worker failed: " + " | ".join(errors))
    results.sort(key=lambda item: str(item["application_id"]))
    allowed_top_level = {
        "career.db",
        "career.db-wal",
        "career.db-shm",
        *(f"{application_id}-ready" for application_id in applications),
        *(f"{application_id}-result.json" for application_id in applications),
    }
    unexpected = sorted(
        str(path.relative_to(fixture))
        for path in fixture.rglob("*")
        if path.is_file()
        and not path.is_relative_to(fixture / "applications")
        and path.name not in allowed_top_level
    )
    for item in results:
        item["unexpected_writes"] = unexpected
    return results


def parallel_verification_report(fixture_dir: str | Path) -> dict[str, Any]:
    results = run_parallel_fixture_workers(fixture_dir)
    fingerprints = {str(item["job_fingerprint"]) for item in results}
    manifests = {str(item["manifest_path"]) for item in results}
    crossed_paths: list[str] = []
    for item in results:
        crossed_paths.extend(
            str(path) for path in item.get("capability_violations", [])
        )
        own_root = (Path(fixture_dir) / "applications" / item["application_id"]).resolve()
        for path in [item["manifest_path"], *item["artifact_paths"]]:
            resolved = Path(path).resolve()
            if not resolved.is_relative_to(own_root):
                crossed_paths.append(str(resolved))
        other_roots = [
            (Path(fixture_dir) / "applications" / other["application_id"]).resolve()
            for other in results
            if other["application_id"] != item["application_id"]
        ]
        for file_path in own_root.rglob("*"):
            if not file_path.is_file():
                continue
            resolved_file = file_path.resolve()
            if not resolved_file.is_relative_to(own_root):
                crossed_paths.append(str(resolved_file))
                continue
            if file_path.stat().st_size > 1_000_000:
                continue
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if any(str(other_root) in content for other_root in other_roots):
                crossed_paths.append(str(file_path))
    ordered = sorted(results, key=lambda item: item["external_lock_entered_at"])
    serialized = bool(
        len(ordered) == 2
        and ordered[0]["external_lock_released_at"]
        <= ordered[1]["external_lock_entered_at"]
    )
    contention_observed = sum(
        int(item.get("external_lock_contention_count") or 0) for item in results
    ) >= 1
    valid = (
        len(results) == 2
        and {item["status"] for item in results} == {"validated"}
        and len(fingerprints) == 2
        and len(manifests) == 2
        and not crossed_paths
        and serialized
        and contention_observed
        and all(
            item.get("external_lock_node_id") == "sync_notion_initial"
            and item.get("external_resource_declared_by_contract") is True
            and not item.get("unexpected_writes")
            for item in results
        )
    )
    return {
        "status": "validated" if valid else "blocked",
        "subprocess_count": len(results),
        "distinct_fingerprints": len(fingerprints) == 2,
        "distinct_manifests": len(manifests) == 2,
        "crossed_paths": crossed_paths,
        "external_locks_serialized": serialized,
        "external_lock_contention_observed": contention_observed,
        "results": results,
    }


def _parallel_worker_main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--parallel-fixture-worker", action="store_true")
    parser.add_argument("--fixture-dir", required=True)
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--result-path", required=True)
    args = parser.parse_args(argv)
    if not args.parallel_fixture_worker:
        parser.error("--parallel-fixture-worker is required")
    return _run_parallel_fixture_worker(
        Path(args.fixture_dir), args.application_id, Path(args.result_path)
    )


if __name__ == "__main__":
    raise SystemExit(_parallel_worker_main(sys.argv[1:]))
