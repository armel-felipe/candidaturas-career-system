from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
import sys

from career.paths import CAREER_STATE, OUTPUTS
from career.services import agent_guard as agent_guard_service
from career.services import application_context as application_context_service
from career.services import applications_v2 as applications_v2_service
from career.services import cover_letter as cover_letter_service
from career.services import cv_content as cv_content_service
from career.services import derived_context as derived_context_service
from career.services import feras as feras_service
from career.services import fit_map as fit_map_service
from career.services import general_cv as general_cv_service
from career.services import habilidades_chave as habilidades_chave_service
from career.services.harness_supervisor import HarnessSupervisor
from career.services.approvals import ApprovalStore
from career.services import intake as intake_service
from career.services import multiagent as multiagent_service
from career.services import notion as notion_service
from career.services import project as project_service
from career.services import review as review_service
from career.services import workflow_reset as workflow_reset_service
from career.services.database import Database
from career.services.session_memory import SessionMemoryService
from career.cells.executor import CellExecutor
from career.cells.handlers import (
    production_handler_registry,
    production_validator_registry,
)
from career.tasks.registry import run_pipeline, run_task
from career.utils import CareerError
from career.workflow.state_store import WorkflowStateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="career")
    subparsers = parser.add_subparsers(dest="command", required=True)

    harness = subparsers.add_parser("harness")
    harness_sub = harness.add_subparsers(dest="action", required=True)
    for action in ("route", "handle"):
        harness_action = harness_sub.add_parser(action)
        harness_action.add_argument("--message", required=True)
        harness_action.add_argument("--channel", default="cli")
        harness_action.add_argument("--max-per-run", type=int, default=None)
        harness_action.add_argument("--model", default=None)
        harness_action.add_argument("--variant", default=None)
    harness_approve = harness_sub.add_parser("approve")
    harness_approve.add_argument("approval_id")
    harness_approval = harness_sub.add_parser("approval")
    harness_approval.add_argument("approval_id")
    harness_execute_approval = harness_sub.add_parser("execute-approval")
    harness_execute_approval.add_argument("approval_id")

    notion = subparsers.add_parser("notion")
    notion_sub = notion.add_subparsers(dest="action", required=True)
    notion_refresh = notion_sub.add_parser("refresh")
    notion_refresh.add_argument("--refresh", choices=["missing", "full"], default="missing")
    notion_sub.add_parser("build-cache")
    notion_sync_memory = notion_sub.add_parser("sync-memory")
    notion_sync_memory.add_argument("--refresh", choices=["missing", "full"], default="missing")

    agent = subparsers.add_parser("agent")
    agent_sub = agent.add_subparsers(dest="action", required=True)
    agent_eval_notion = agent_sub.add_parser("evaluate-notion")
    agent_eval_notion.add_argument("record_id", type=int)
    agent_eval_notion_local = agent_sub.add_parser("evaluate-notion-local")
    agent_eval_notion_local.add_argument("record_id", type=int)
    agent_sub.add_parser("guard")
    agent_maestro = agent_sub.add_parser("maestro")
    agent_maestro.add_argument("step", nargs="?", choices=["fit-map", "cv", "cover-letter", "feras", "habilidades", "notion-update", "email-draft", "linkedin"])
    agent_maestro.add_argument("--objective")
    agent_maestro.add_argument("--extras", default="{}")

    multiagent = subparsers.add_parser("multiagent")
    multiagent_sub = multiagent.add_subparsers(dest="action", required=True)
    multiagent_sub.add_parser("runbook")
    multiagent_sub.add_parser("local-model-map")
    multiagent_request = multiagent_sub.add_parser("request")
    multiagent_request.add_argument("step", choices=["fit-map", "cv", "cover-letter", "feras", "habilidades", "notion-update", "email-draft", "linkedin"])
    multiagent_request.add_argument("--objective")
    multiagent_request.add_argument("--extras", default="{}")
    multiagent_request.add_argument("--application-id")
    multiagent_validate_request = multiagent_sub.add_parser("validate-request")
    multiagent_validate_request.add_argument("step", choices=["fit-map", "cv", "cover-letter", "feras", "habilidades", "notion-update", "email-draft", "linkedin"])
    multiagent_validate_request.add_argument("--application-id")
    multiagent_sub.add_parser("validate-workspace-clean")

    intake = subparsers.add_parser("intake")
    intake_sub = intake.add_subparsers(dest="action", required=True)
    intake_notion = intake_sub.add_parser("notion-record")
    intake_notion.add_argument("record_id", type=int)
    intake_notion.add_argument("--application-id")
    intake_paste = intake_sub.add_parser("paste")
    intake_paste.add_argument("--company", required=True)
    intake_paste.add_argument("--role", required=True)
    intake_paste.add_argument("--text-file")
    intake_paste.add_argument("--stdin", action="store_true")
    intake_paste.add_argument("--application-id")
    intake_linkedin_job = intake_sub.add_parser("linkedin-job")
    intake_linkedin_job.add_argument("--url", required=True)
    intake_linkedin_job.add_argument("--company")
    intake_linkedin_job.add_argument("--role")
    intake_linkedin_job.add_argument("--application-id")
    intake_linkedin_post = intake_sub.add_parser("linkedin-post")
    intake_linkedin_post.add_argument("--url", required=True)
    intake_linkedin_post.add_argument("--company", required=True)
    intake_linkedin_post.add_argument("--role", required=True)
    intake_linkedin_post.add_argument("--application-id")
    intake_url = intake_sub.add_parser("url")
    intake_url.add_argument("--url", required=True)
    intake_url.add_argument("--company")
    intake_url.add_argument("--role")
    intake_url.add_argument("--application-id")
    intake_resume = intake_sub.add_parser("resume")
    intake_resume.add_argument("--application-id")

    fit_map = subparsers.add_parser("fit-map")
    fit_map_sub = fit_map.add_subparsers(dest="action", required=True)
    template = fit_map_sub.add_parser("template")
    template.add_argument("--output", default=str(CAREER_STATE / "fit_map.draft.json"))
    template.add_argument("--application-id")
    validate_draft = fit_map_sub.add_parser("validate-draft")
    validate_draft.add_argument("--path", default=str(CAREER_STATE / "fit_map.draft.json"))
    validate_draft.add_argument("--full", action="store_true", help="Print the full validated draft payload.")
    validate_draft.add_argument("--application-id")
    validate_stage = fit_map_sub.add_parser("validate-stage")
    validate_stage.add_argument("stage", choices=["extract", "map-evidence", "score-draft", "complete-draft"])
    validate_stage.add_argument("--path", default=str(CAREER_STATE / "fit_map.draft.json"))
    validate_stage.add_argument("--application-id")
    summary = fit_map_sub.add_parser("summary")
    summary.add_argument("--path", default=str(CAREER_STATE / "fit_map.json"))
    summary.add_argument("--application-id")
    draft_summary = fit_map_sub.add_parser("draft-summary")
    draft_summary.add_argument("--path", default=str(CAREER_STATE / "fit_map.draft.json"))
    draft_summary.add_argument("--application-id")
    quality = fit_map_sub.add_parser("quality")
    quality.add_argument("--path", default=str(CAREER_STATE / "fit_map.json"))
    quality.add_argument("--job-description")
    quality.add_argument("--application-id")
    registry_summary = fit_map_sub.add_parser("registry-summary")
    registry_summary.add_argument("--fit-map", default=str(CAREER_STATE / "fit_map.json"))
    registry_summary.add_argument("--registry", default=".career-state/derived/keyword_ats_registry.json")
    registry_summary.add_argument("--application-id")
    build = fit_map_sub.add_parser("build")
    build.add_argument("--draft", default=str(CAREER_STATE / "fit_map.draft.json"))
    build.add_argument("--output", default=str(CAREER_STATE / "fit_map.json"))
    build.add_argument("--application-id")
    score = fit_map_sub.add_parser("score")
    score.add_argument("--path", default=str(CAREER_STATE / "fit_map.json"))
    score.add_argument("--application-id")
    validate = fit_map_sub.add_parser("validate")
    validate.add_argument("--path", default=str(CAREER_STATE / "fit_map.json"))
    validate.add_argument("--full", action="store_true", help="Print the full validated FIT_MAP payload.")
    validate.add_argument("--application-id")
    finalize = fit_map_sub.add_parser("finalize")
    finalize.add_argument("--draft", default=str(CAREER_STATE / "fit_map.draft.json"))
    finalize.add_argument("--output", default=str(CAREER_STATE / "fit_map.json"))
    finalize.add_argument("--application-id")
    status = fit_map_sub.add_parser("status")
    status.add_argument("--draft", default=str(CAREER_STATE / "fit_map.draft.json"))
    status.add_argument("--fit-map", default=str(CAREER_STATE / "fit_map.json"))
    status.add_argument("--job-description")
    status.add_argument("--application-id")
    resume = fit_map_sub.add_parser("resume")
    resume.add_argument("--draft", default=str(CAREER_STATE / "fit_map.draft.json"))
    resume.add_argument("--fit-map", default=str(CAREER_STATE / "fit_map.json"))
    resume.add_argument("--job-description")
    resume.add_argument("--application-id")
    guard = fit_map_sub.add_parser("guard")
    guard.add_argument("--draft", default=str(CAREER_STATE / "fit_map.draft.json"))
    guard.add_argument("--fit-map", default=str(CAREER_STATE / "fit_map.json"))
    guard.add_argument("--job-description")
    guard.add_argument("--application-id")

    cv = subparsers.add_parser("cv")
    cv_sub = cv.add_subparsers(dest="action", required=True)
    cv_build_content = cv_sub.add_parser("build-content")
    cv_build_content.add_argument("--application-id")
    cv_validate_content = cv_sub.add_parser("validate-content")
    cv_validate_content.add_argument("--path", default=str(CAREER_STATE / "cv_content.json"))
    cv_validate_content.add_argument("--application-id")
    review = cv_sub.add_parser("review")
    review.add_argument("--artifact", required=True)
    review.add_argument("--fit-map", default=str(CAREER_STATE / "fit_map.json"))
    review.add_argument("--registry", required=True)
    review.add_argument("--report", default=str(OUTPUTS / "_tmp" / "output_review_report.json"))
    review.add_argument("--application-id")
    polish = cv_sub.add_parser("polish")
    polish.add_argument("--artifact", required=True)
    polish.add_argument("--review-report", default=str(OUTPUTS / "_tmp" / "output_review_report.json"))
    polish.add_argument("--report", default=str(OUTPUTS / "_tmp" / "polish_review.json"))
    polish.add_argument("--application-id")
    approve = cv_sub.add_parser("approve")
    approve.add_argument("--artifact", required=True)
    approve.add_argument("--fit-map", default=str(CAREER_STATE / "fit_map.json"))
    approve.add_argument("--registry", required=True)
    approve.add_argument("--report", default=str(OUTPUTS / "_tmp" / "output_review_report.json"))
    approve.add_argument("--polish-report", default=str(OUTPUTS / "_tmp" / "polish_review.json"))
    approve.add_argument("--application-id")

    general_cv = subparsers.add_parser("general-cv")
    general_cv_sub = general_cv.add_subparsers(dest="action", required=True)
    general_strategy = general_cv_sub.add_parser("strategy")
    general_strategy.add_argument("--mode", choices=["auto", "expanded", "concise"], default="auto")
    general_strategy.add_argument("--bullet-count", type=int)
    general_strategy.add_argument("--dominant-cluster")
    general_strategy.add_argument("--output", default=str(CAREER_STATE / "general_cv_strategy.json"))
    general_strategy.add_argument("--report", default=str(OUTPUTS / "general_cv_strategy.md"))
    general_validate = general_cv_sub.add_parser("validate-content")
    general_validate.add_argument("--path", required=True)

    habilidades = subparsers.add_parser("habilidades-chave")
    habilidades_sub = habilidades.add_subparsers(dest="action", required=True)
    habilidades_check = habilidades_sub.add_parser("check")
    habilidades_check.add_argument("--fit-map", default=str(CAREER_STATE / "fit_map.json"))
    habilidades_validate = habilidades_sub.add_parser("validate")
    habilidades_validate.add_argument("--artifact", required=True)
    habilidades_validate.add_argument("--mode", choices=["gupy", "mercado_livre"], required=True)
    habilidades_validate.add_argument("--expected-count", type=int)
    habilidades_validate.add_argument("--fit-map", default=str(CAREER_STATE / "fit_map.json"))

    project = subparsers.add_parser("project")
    project_sub = project.add_subparsers(dest="action", required=True)
    validate_structure = project_sub.add_parser("validate-structure")
    validate_structure.set_defaults(action="validate-structure")
    save_job = project_sub.add_parser("save-job-description")
    save_job.add_argument("--company", required=True)
    save_job.add_argument("--role", required=True)
    save_job.add_argument("--text-file", required=True)
    save_job.add_argument("--output-dir", default="inbox/job_descriptions")
    diagnose = project_sub.add_parser("diagnose-runtime")
    diagnose.add_argument("--output", default=str(OUTPUTS / "_tmp" / "runtime_diagnosis.json"))
    project_sub.add_parser("local-strict-status")
    project_sub.add_parser("local-strict-doctor")
    project_sub.add_parser("local-agent-benchmark")

    memory = subparsers.add_parser("memory")
    memory_sub = memory.add_subparsers(dest="action", required=True)
    memory_build = memory_sub.add_parser("build")
    memory_build.add_argument("--output-dir", default=str(CAREER_STATE / "memory"))

    applications = subparsers.add_parser("applications")
    applications_sub = applications.add_subparsers(dest="action", required=True)
    heartbeat = applications_sub.add_parser("heartbeat")
    heartbeat.add_argument("--max-per-run", type=int, default=None)
    heartbeat.add_argument("--dry-run", action="store_true")
    heartbeat.add_argument("--run-agent", action="store_true")
    heartbeat.add_argument("--model", default=None)
    heartbeat.add_argument("--variant", default=None)
    heartbeat.add_argument("--skip-maintenance", action="store_true")
    heartbeat.add_argument("--maintenance-refresh", choices=["missing", "full"], default=None)
    heartbeat.add_argument("--format", choices=["json", "human", "both"], default="both")
    status = applications_sub.add_parser("status")
    status.add_argument("--format", choices=["json", "human", "both"], default="both")
    applications_sub.add_parser("write-default-config")
    applications_sub.add_parser("list-active")
    applications_inspect = applications_sub.add_parser("inspect")
    applications_inspect.add_argument("application_id")
    applications_lock_status = applications_sub.add_parser("lock-status")
    applications_lock_status.add_argument("application_id")
    applications_release_lock = applications_sub.add_parser("release-lock")
    applications_release_lock.add_argument("application_id")
    applications_release_lock.add_argument("--dry-run", action="store_true")
    applications_sub.add_parser("doctor-concurrency")
    applications_migrate = applications_sub.add_parser("migrate-global-state")
    applications_migrate.add_argument("--application-id")
    applications_migrate.add_argument("--dry-run", action="store_true")
    applications_plan = applications_sub.add_parser("plan")
    applications_plan.add_argument("--application-id", required=True)
    applications_plan.add_argument(
        "--deliverable",
        action="append",
        required=True,
        choices=["cv", "notion", "feras", "cover_letter", "habilidades"],
    )
    applications_run = applications_sub.add_parser("run")
    applications_run.add_argument("--application-id", required=True)
    applications_run.add_argument("--run-id", required=True)
    applications_repair = applications_sub.add_parser("repair")
    applications_repair.add_argument("--application-id", required=True)
    applications_repair.add_argument("--run-id", required=True)
    applications_repair.add_argument("--node", required=True)
    applications_repair.add_argument("--reason", required=True)
    applications_inspect_run = applications_sub.add_parser("inspect-run")
    applications_inspect_run.add_argument("--application-id", required=True)
    applications_inspect_run.add_argument("--run-id", required=True)

    derive = subparsers.add_parser("derive")
    derive_sub = derive.add_subparsers(dest="action", required=True)
    for derive_action in [
        "job-pack",
        "job-sections",
        "job-keywords",
        "reference-digest",
        "evidence-pack",
        "fit-map-seed",
        "cv-input-pack",
        "cv-content-seed",
        "habilidades-input-pack",
        "feras-input-pack",
        "cover-letter-input-pack",
        "all-for-fit-map",
        "validate-manifest",
        "context-doctor",
        "assert-active",
        "invalidate-stale",
    ]:
        derive_parser = derive_sub.add_parser(derive_action)
        derive_parser.add_argument("--application-id")

    cover_letter = subparsers.add_parser("cover-letter")
    cover_letter_sub = cover_letter.add_subparsers(dest="action", required=True)
    cover_build = cover_letter_sub.add_parser("build")
    cover_build.add_argument("--output")

    feras = subparsers.add_parser("feras")
    feras_sub = feras.add_subparsers(dest="action", required=True)
    feras_build = feras_sub.add_parser("build")
    feras_build.add_argument("--output")

    workflow = subparsers.add_parser("workflow")
    workflow_sub = workflow.add_subparsers(dest="action", required=True)
    run_task_parser = workflow_sub.add_parser("run-task")
    run_task_parser.add_argument("task_name")
    run_task_parser.add_argument("--arguments", default="{}")
    pipeline_parser = workflow_sub.add_parser("run-pipeline")
    pipeline_parser.add_argument("task_names", nargs="+")
    pipeline_parser.add_argument("--arguments", default="{}")
    workflow_sub.add_parser("show-state")
    workflow_sub.add_parser("summary")
    workflow_sub.add_parser("explain-last-run")
    workflow_sub.add_parser("reset-state")
    workflow_reset = workflow_sub.add_parser("reset")
    workflow_reset.add_argument("--dry-run", action="store_true")
    workflow_reset.add_argument("--no-backup", action="store_true")

    session = subparsers.add_parser("session")
    session_sub = session.add_subparsers(dest="action", required=True)
    session_status = session_sub.add_parser("status")
    session_status.add_argument("--session-id")
    session_set = session_sub.add_parser("set")
    session_set.add_argument("key")
    session_set.add_argument("value")
    session_set.add_argument("--session-id")
    session_set.add_argument("--ttl", type=int, default=3600)
    session_get = session_sub.add_parser("get")
    session_get.add_argument("key")
    session_get.add_argument("--session-id")
    session_get_all = session_sub.add_parser("get-all")
    session_get_all.add_argument("--session-id")
    session_clean = session_sub.add_parser("clean")
    session_clean.add_argument("--session-id")
    session_reset = session_sub.add_parser("reset")
    session_reset.add_argument("--session-id")

    query = subparsers.add_parser("query")
    query.add_argument("--filter", default="")
    query.add_argument("--format", choices=["table", "json", "human", "ids"], default="table")
    query.add_argument("--source", choices=["applications", "notion"], default="applications")
    query.add_argument("--count", action="store_true")
    query.add_argument("--limit", type=int)
    query.add_argument("--offset", type=int, default=0)
    query.add_argument("--list-filters", action="store_true")
    return parser


def _dump(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _print_human(value: str) -> None:
    print(value, file=sys.stderr)


def _dump_error(exc: Exception) -> None:
    _dump({"status": "blocked", "error": str(exc)})


def _application_paths(application_id: str | None):
    return application_context_service.paths_for(application_id) if application_id else None


def _state_store_for_application(application_id: str | None) -> WorkflowStateStore:
    return WorkflowStateStore.for_application(application_id) if application_id else WorkflowStateStore()


def _task_cli_summary(task: str, result):
    if isinstance(result, dict) and result.get("reused"):
        return {"task": task, "status": "reused"}
    if task == "fit_map.validate_draft":
        return {"task": task, "status": "ok", "cargo": result.get("cargo"), "empresa": result.get("empresa")}
    if task == "fit_map.validate":
        score = result.get("nota_aderencia", {}) if isinstance(result, dict) else {}
        return {
            "task": task,
            "status": "ok",
            "cargo": result.get("cargo"),
            "empresa": result.get("empresa"),
            "nota_final": score.get("final"),
        }
    return {"task": task, "status": "ok", "result": str(result)}


def _fit_map_payload_summary(task: str, result):
    if isinstance(result, dict) and result.get("reused"):
        return {"task": task, "status": "reused"}
    if not isinstance(result, dict):
        return {"task": task, "status": "ok", "result": str(result)}

    score = result.get("nota_aderencia") if isinstance(result.get("nota_aderencia"), dict) else {}
    dimensions = score.get("dimensoes") if isinstance(score.get("dimensoes"), dict) else {}
    return {
        "task": task,
        "status": "ok",
        "cargo": result.get("cargo"),
        "empresa": result.get("empresa"),
        "nota_final": score.get("final"),
        "mapa_ajuste_count": len(result.get("mapa_ajuste", []) or []),
        "keywords_ats_count": len(result.get("keywords_habilidade_ats", []) or []),
        "gaps_count": len(result.get("gaps_sem_cobertura", []) or []),
        "dimension_points": {
            key: value.get("pontos")
            for key, value in dimensions.items()
            if isinstance(value, dict) and "pontos" in value
        },
    }


def _fit_map_draft_summary(result):
    if isinstance(result, dict) and result.get("reused"):
        return {"task": "fit_map.validate_draft", "status": "reused"}
    if not isinstance(result, dict):
        return {"task": "fit_map.validate_draft", "status": "ok", "result": str(result)}
    score = result.get("nota_aderencia") if isinstance(result.get("nota_aderencia"), dict) else {}
    return {
        "task": "fit_map.validate_draft",
        "status": "ok",
        "cargo": result.get("cargo"),
        "empresa": result.get("empresa"),
        "mapa_ajuste_count": len(result.get("mapa_ajuste", []) or []),
        "keywords_vaga_count": len(result.get("keywords_vaga", []) or []),
        "keywords_ats_count": len(result.get("keywords_habilidade_ats", []) or []),
        "has_nota_aderencia": bool(score),
    }


def _heartbeat_human_summary(result: dict) -> str:
    maintenance = result.get("maintenance") or {}
    lines = [
        f"Heartbeat: {result.get('selected', 0)} item(ns) selecionado(s); dry_run={bool(result.get('dry_run'))}; run_agent={bool(result.get('run_agent'))}",
    ]
    if maintenance.get("executed"):
        refresh = (maintenance.get("refresh") or {}).get("summary") or {}
        coverage = refresh.get("coverage") or {}
        registry = maintenance.get("registry") or {}
        lines.append(
            "Maintenance: "
            f"refresh={maintenance.get('refresh_mode') or '-'}; "
            f"pages={refresh.get('total_pages') or '-'}; "
            f"descricoes={refresh.get('applications_with_description') or '-'}; "
            f"registry_apps={registry.get('applications_exported') or '-'}; "
            f"keywords={registry.get('canonical_keywords') or '-'}; "
            f"complete={coverage.get('is_complete')}"
        )
    else:
        lines.append(f"Maintenance: skipped ({maintenance.get('reason') or 'unknown'})")
    for item in result.get("results", []) or []:
        lines.append(
            f"- {item.get('record_id') or item.get('record_key')}: "
            f"{item.get('status')} | score={item.get('score') if item.get('score') is not None else '-'} | "
            f"title={item.get('title') or item.get('role') or '-'}"
        )
    lines.append(f"Log: {result.get('log') or '-'}")
    return "\n".join(lines)


def _applications_status_human_summary(result: dict) -> str:
    maintenance = result.get("maintenance") or {}
    queue = result.get("queue") or {}
    notion = result.get("notion") or {}
    runtime = result.get("local_runtime") or {}
    lines = [
        "Applications status",
        (
            f"Maintenance: last={maintenance.get('last_refresh_mode') or '-'}; "
            f"runs_since_full={maintenance.get('runs_since_full') if maintenance.get('runs_since_full') is not None else '-'}; "
            f"hours_since_full={round(float(maintenance.get('hours_since_full') or 0), 1) if maintenance.get('hours_since_full') is not None else '-'}"
        ),
        (
            f"Queue: eligible={queue.get('eligible_now') or 0}; "
            f"reprocess={queue.get('reprocess_now') or 0}; "
            f"missing_description={queue.get('missing_description_now') or 0}"
        ),
        (
            f"Runtime: tracked={runtime.get('tracked_applications') or 0}; "
            f"retryable={runtime.get('retryable_count') or 0}; "
            f"errors={runtime.get('error_count') or 0}"
        ),
        f"Notion active: {notion.get('total_active') or 0}",
    ]
    top_candidates = queue.get("top_candidates") or []
    if top_candidates:
        lines.append("Top queue:")
        for item in top_candidates:
            lines.append(
                f"- {item.get('record_id')}: {item.get('status')} | chars={item.get('description_chars') or 0} | {item.get('title') or '-'}"
            )
    stage_counts = runtime.get("stage_counts") or {}
    if stage_counts:
        ordered = ", ".join(f"{key}={value}" for key, value in sorted(stage_counts.items()))
        lines.append(f"Stages: {ordered}")
    return "\n".join(lines)


def _cell_run_payload(executor: CellExecutor, run_id: str, *, status: str | None = None) -> dict:
    resumed = executor.resume(run_id)
    blocked_nodes = sorted(
        node_id for node_id, node_status in resumed.statuses.items() if node_status == "blocked"
    )
    ready_nodes = sorted(resumed.ready_nodes)
    artifact_paths = [
        str(row["path"])
        for row in executor.database.fetch_all(
            "SELECT path FROM artifacts WHERE run_id = ? ORDER BY path", (run_id,)
        )
    ]
    active_nodes = sorted(
        node_id
        for node_id, node_status in resumed.statuses.items()
        if node_status in {"reserved", "running"}
    )
    pending_nodes = sorted(
        node_id
        for node_id, node_status in resumed.statuses.items()
        if node_status not in {"validated", "blocked", "reserved", "running"}
    )
    if blocked_nodes:
        next_action = (
            "career applications repair "
            f"--application-id {resumed.application_id} --run-id {run_id} "
            f"--node {blocked_nodes[0]} --reason <reason>"
        )
    elif active_nodes:
        next_action = (
            "career applications inspect-run "
            f"--application-id {resumed.application_id} --run-id {run_id}"
        )
    elif ready_nodes or pending_nodes:
        next_action = (
            "career applications run "
            f"--application-id {resumed.application_id} --run-id {run_id}"
        )
    else:
        next_action = (
            "career applications inspect-run "
            f"--application-id {resumed.application_id} --run-id {run_id}"
        )
    resolved_status = status or (
        "blocked"
        if blocked_nodes
        else "running"
        if active_nodes
        else "ready"
        if ready_nodes
        else "pending"
        if pending_nodes
        else "completed"
    )
    return {
        "status": resolved_status,
        "run_id": run_id,
        "ready_nodes": ready_nodes,
        "blocked_nodes": blocked_nodes,
        "artifact_paths": artifact_paths,
        "next_action": next_action,
    }


def _scoped_cell_run(executor: CellExecutor, application_id: str, run_id: str):
    resumed = executor.resume(run_id)
    if resumed.application_id != application_id:
        raise ValueError(f"run does not belong to application: {application_id}")
    return resumed


def _harness_human_summary(result: dict) -> str | None:
    payload = result.get("result") if isinstance(result.get("result"), dict) else {}
    if not isinstance(payload, dict):
        return None
    display_text = payload.get("display_text")
    if isinstance(display_text, str) and display_text.strip():
        return display_text
    return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "application_id") and args.application_id is not None:
        try:
            application_context_service.validate_application_id(args.application_id)
        except ValueError as exc:
            parser.error(str(exc))

    if args.command == "harness":
        supervisor = HarnessSupervisor(Path.cwd())
        if args.action in {"route", "handle"}:
            result = supervisor.handle_message(
                args.message,
                channel=args.channel,
                execute=args.action == "handle",
                max_per_run=args.max_per_run,
                model=args.model,
                variant=args.variant,
            )
            if args.action == "handle":
                human = _harness_human_summary(result)
                if human:
                    _print_human(human)
            _dump(result)
            return 0 if result.get("status") != "blocked" else 1
        approvals = ApprovalStore(Path.cwd())
        if args.action == "approve":
            _dump(approvals.approve(args.approval_id))
            return 0
        if args.action == "approval":
            _dump(approvals.get(args.approval_id))
            return 0
        if args.action == "execute-approval":
            result = supervisor.execute_approved_action(args.approval_id)
            _dump(result)
            return 0 if result.get("status") == "completed" else 1

    if args.command == "notion":
        if args.action == "refresh":
            result = run_task("notion.refresh_cache", {"refresh": args.refresh})
            _dump(result)
            return 0
        if args.action == "build-cache":
            result = run_task("notion.build_cache")
            _dump(result)
            return 0
        if args.action == "sync-memory":
            token, database_id = notion_service.notion_config()
            refresh_result = run_task("notion.refresh_cache", {"refresh": args.refresh})
            registry_result = run_task("registry.rebuild")
            memory_result = run_task("memory.build")
            governance_result = notion_service.backfill_governance(token, database_id, dry_run=False)
            _dump({
                "refresh": refresh_result,
                "registry": registry_result,
                "memory": {key: str(value) for key, value in memory_result.items()},
                "governance_backfill": {
                    "generated_at": governance_result.get("generated_at"),
                    "dry_run": governance_result.get("dry_run"),
                    "totals": governance_result.get("totals"),
                },
            })
            return 0

    if args.command == "agent":
        try:
            if args.action == "evaluate-notion":
                result = HarnessSupervisor(Path.cwd()).handle_message(
                    f"Avalie vaga Notion {args.record_id}",
                    channel="cli-alias",
                    execute=True,
                )
                _dump(result)
                return 0 if result.get("status") != "blocked" else 1
            if args.action == "evaluate-notion-local":
                result = HarnessSupervisor(Path.cwd()).handle_message(
                    f"Avalie vaga Notion {args.record_id}",
                    channel="cli-alias",
                    execute=True,
                )
                _dump(result)
                return 0 if result.get("status") != "blocked" else 1
            if args.action == "guard":
                result = agent_guard_service.guard()
                _dump(result)
                return 0 if result.get("status") == "ok" else 1
            if args.action == "maestro":
                supervisor = HarnessSupervisor(Path.cwd())
                result = (
                    supervisor.prepare_specialist(
                        args.step,
                        objective=args.objective,
                        extras=json.loads(args.extras),
                    )
                    if args.step
                    else supervisor.prepare_all_specialists()
                )
                _dump(result)
                return 0 if result.get("status") != "blocked" else 1
        except CareerError as exc:
            _dump_error(exc)
            return 1

    if args.command == "multiagent":
        try:
            if args.action == "runbook":
                _dump(multiagent_service.write_runbook())
                return 0
            if args.action == "local-model-map":
                _dump(multiagent_service.write_local_model_map())
                return 0
            if args.action == "request":
                extras = json.loads(args.extras)
                if args.application_id:
                    extras["application_id"] = args.application_id
                _dump(
                    HarnessSupervisor(Path.cwd()).prepare_specialist(
                        args.step, objective=args.objective, extras=extras
                    )
                )
                return 0
            if args.action == "validate-request":
                request_path = None
                if args.application_id:
                    request_path = (
                        application_context_service.paths_for(args.application_id).requests_dir
                        / "manual_agent_requests"
                        / f"{args.step}_request.json"
                    )
                result = multiagent_service.validate_request(args.step, request_path=request_path)
                _dump(result)
                return 0 if result.get("status") == "ok" else 1
            if args.action == "validate-workspace-clean":
                result = multiagent_service.validate_workspace_clean()
                _dump(result)
                return 0 if result.get("status") == "ok" else 1
        except CareerError as exc:
            _dump_error(exc)
            return 1

    if args.command == "intake":
        try:
            if args.action == "notion-record":
                _dump(intake_service.from_notion_record(args.record_id, application_id=args.application_id))
                return 0
            if args.action == "paste":
                if args.stdin:
                    import sys

                    text = sys.stdin.read()
                elif args.text_file:
                    text = Path(args.text_file).read_text(encoding="utf-8")
                else:
                    raise SystemExit("intake paste requires --text-file or --stdin.")
                _dump(intake_service.from_paste(company=args.company, role=args.role, text=text, application_id=args.application_id))
                return 0
            if args.action == "linkedin-job":
                hints = {key: value for key, value in {"company": args.company, "role": args.role}.items() if value}
                _dump(intake_service.from_linkedin_job(args.url, metadata_hints=hints, application_id=args.application_id))
                return 0
            if args.action == "linkedin-post":
                _dump(intake_service.from_linkedin_post(url=args.url, company=args.company, role=args.role, application_id=args.application_id))
                return 0
            if args.action == "url":
                _dump(intake_service.from_url(url=args.url, company=args.company, role=args.role, application_id=args.application_id))
                return 0
            if args.action == "resume":
                _dump(intake_service.resume(application_id=args.application_id))
                return 0
        except CareerError as exc:
            _dump_error(exc)
            return 1

    if args.command == "fit-map":
        app_paths = _application_paths(getattr(args, "application_id", None))
        state_store = _state_store_for_application(getattr(args, "application_id", None))
        if args.action == "template":
            output = str(app_paths.fit_map_draft) if app_paths else args.output
            result = run_task("fit_map.template", {"output": output}, state_store=state_store)
            print(result)
            return 0
        if args.action == "validate-draft":
            path = str(app_paths.fit_map_draft) if app_paths else args.path
            result = run_task("fit_map.validate_draft", {"path": path}, state_store=state_store)
            _dump(result if args.full else _fit_map_draft_summary(result))
            return 0
        if args.action == "validate-stage":
            path = app_paths.fit_map_draft if app_paths else Path(args.path)
            result = fit_map_service.validate_draft_stage(path, args.stage)
            _dump(result)
            return 0
        if args.action == "summary":
            path = app_paths.fit_map if app_paths else Path(args.path)
            _dump(fit_map_service.payload_summary(path))
            return 0
        if args.action == "draft-summary":
            path = app_paths.fit_map_draft if app_paths else Path(args.path)
            _dump(fit_map_service.draft_summary(path))
            return 0
        if args.action == "quality":
            path = app_paths.fit_map if app_paths else Path(args.path)
            job_description = app_paths.job_description if app_paths else (Path(args.job_description) if args.job_description else None)
            result = fit_map_service.quality_report(
                path,
                job_description_path=job_description,
            )
            _dump(result)
            return 0 if result.get("status") == "ok" else 1
        if args.action == "registry-summary":
            fit_map_path = app_paths.fit_map if app_paths else Path(args.fit_map)
            result = fit_map_service.registry_summary(Path(args.registry), fit_map_path)
            _dump(result)
            return 0 if result.get("status") == "ok" else 1
        if args.action == "build":
            draft = str(app_paths.fit_map_draft) if app_paths else args.draft
            output = str(app_paths.fit_map) if app_paths else args.output
            result = run_task("fit_map.build", {"draft": draft, "output": output}, state_store=state_store)
            print(result)
            return 0
        if args.action == "score":
            path = str(app_paths.fit_map) if app_paths else args.path
            result = run_task("fit_map.score", {"path": path}, state_store=state_store)
            print(result)
            return 0
        if args.action == "validate":
            path = str(app_paths.fit_map) if app_paths else args.path
            result = run_task("fit_map.validate", {"path": path}, state_store=state_store)
            _dump(result if args.full else _fit_map_payload_summary("fit_map.validate", result))
            return 0
        if args.action == "finalize":
            draft = str(app_paths.fit_map_draft) if app_paths else args.draft
            output = str(app_paths.fit_map) if app_paths else args.output
            task_results = [
                ("fit_map.validate_draft", run_task("fit_map.validate_draft", {"path": draft}, state_store=state_store)),
                ("fit_map.build", run_task("fit_map.build", {"draft": draft, "output": output}, state_store=state_store)),
                ("fit_map.score", run_task("fit_map.score", {"path": output}, state_store=state_store)),
                ("fit_map.validate", run_task("fit_map.validate", {"path": output}, state_store=state_store)),
            ]
            _dump([_task_cli_summary(task, result) for task, result in task_results])
            return 0
        if args.action == "status":
            draft = app_paths.fit_map_draft if app_paths else Path(args.draft)
            fit_map = app_paths.fit_map if app_paths else Path(args.fit_map)
            job_description = app_paths.job_description if app_paths else (Path(args.job_description) if args.job_description else None)
            result = fit_map_service.status(
                draft_path=draft,
                fit_map_path=fit_map,
                job_description_path=job_description,
            )
            _dump(result)
            return 0
        if args.action == "resume":
            draft = app_paths.fit_map_draft if app_paths else Path(args.draft)
            fit_map = app_paths.fit_map if app_paths else Path(args.fit_map)
            job_description = app_paths.job_description if app_paths else (Path(args.job_description) if args.job_description else None)
            result = fit_map_service.resume_guidance(
                draft_path=draft,
                fit_map_path=fit_map,
                job_description_path=job_description,
            )
            _dump(result)
            return 0
        if args.action == "guard":
            draft = app_paths.fit_map_draft if app_paths else Path(args.draft)
            fit_map = app_paths.fit_map if app_paths else Path(args.fit_map)
            job_description = app_paths.job_description if app_paths else (Path(args.job_description) if args.job_description else None)
            result = fit_map_service.progress_guard(
                draft_path=draft,
                fit_map_path=fit_map,
                job_description_path=job_description,
            )
            _dump(result)
            return 1 if result.get("blocked") else 0

    if args.command == "cv":
        app_paths = _application_paths(getattr(args, "application_id", None))
        if app_paths:
            derived_context_service.configure_derived_dir(app_paths.derived_dir)
            derived_context_service.configure_state_store_path(app_paths.workflow_state)
            cv_content_service.configure_paths(cv_content_path=app_paths.cv_content, fit_map_path=app_paths.fit_map)
        if args.action == "build-content":
            _dump(cv_content_service.build_current_cv_content())
            return 0
        if args.action == "validate-content":
            path = app_paths.cv_content if app_paths else Path(args.path)
            result = cv_content_service.validate_cv_content(path)
            _dump(result)
            return 0
        if args.action == "review":
            fit_map_path = app_paths.fit_map if app_paths else Path(args.fit_map)
            report_path = app_paths.cv_review_report if app_paths else Path(args.report)
            result = run_task(
                "cv.review",
                {
                    "artifact": args.artifact,
                    "fit_map": str(fit_map_path),
                    "registry": args.registry,
                    "report": str(report_path),
                },
                state_store=_state_store_for_application(getattr(args, "application_id", None)),
            )
            _dump(result)
            return 0
        if args.action == "polish":
            review_report_path = app_paths.cv_review_report if app_paths else Path(args.review_report)
            report_path = app_paths.polish_review if app_paths else Path(args.report)
            review_report = json.loads(review_report_path.read_text(encoding="utf-8")) if review_report_path.exists() else None
            result = review_service.polish_cv(
                artifact=Path(args.artifact),
                report_path=report_path,
                review_report=review_report,
            )
            _dump(result)
            return 1 if result.get("approval_blockers") else 0
        if args.action == "approve":
            fit_map_path = app_paths.fit_map if app_paths else Path(args.fit_map)
            report_path = app_paths.cv_review_report if app_paths else Path(args.report)
            polish_report_path = app_paths.polish_review if app_paths else Path(args.polish_report)
            result = run_task(
                "cv.approve",
                {
                    "artifact": args.artifact,
                    "fit_map": str(fit_map_path),
                    "registry": args.registry,
                    "report": str(report_path),
                    "polish_report": str(polish_report_path),
                },
                state_store=_state_store_for_application(getattr(args, "application_id", None)),
            )
            if isinstance(result, dict) and result.get("reused"):
                _dump({"task": "cv.approve", "status": "reused"})
            else:
                _dump(
                    {
                        "task": "cv.approve",
                        "status": "ok",
                        "approved": result.get("approved"),
                        "approved_for_delivery": result.get("approved_for_delivery"),
                        "ats_top8": result.get("ats_policy", {}).get("top8"),
                        "blockers": result.get("blockers", []),
                        "warnings": result.get("warnings", []),
                        "artifact": result.get("artifact"),
                        "report": str(report_path),
                        "polish_report": str(polish_report_path),
                    }
                )
            return 0

    if args.command == "general-cv":
        if args.action == "strategy":
            request = general_cv_service.validate_request(args.mode, args.bullet_count, args.dominant_cluster)
            payload = general_cv_service.strategy_payload(request)
            general_cv_service.write_strategy(payload, Path(args.output), Path(args.report) if args.report else None)
            _dump(payload)
            return 0
        if args.action == "validate-content":
            payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
            _dump(general_cv_service.validate_content(payload))
            return 0

    if args.command == "habilidades-chave":
        if args.action == "check":
            _dump(habilidades_chave_service.check_environment(Path(args.fit_map)))
            return 0
        if args.action == "validate":
            _dump(
                habilidades_chave_service.validate_artifact(
                    artifact=Path(args.artifact),
                    mode=args.mode,
                    expected_count=args.expected_count,
                    fit_map_path=Path(args.fit_map),
                )
            )
            return 0

    if args.command == "project":
        if args.action == "validate-structure":
            project_service.validate_structure()
            return 0
        if args.action == "save-job-description":
            text = Path(args.text_file).read_text(encoding="utf-8")
            result = run_task(
                "project.save_job_description",
                {
                    "company": args.company,
                    "role": args.role,
                    "text": text,
                    "output_dir": args.output_dir,
                },
            )
            print(result)
            return 0
        if args.action == "diagnose-runtime":
            result = run_task("project.diagnose_runtime", {"output": args.output})
            print(result)
            return 0
        if args.action == "local-strict-status":
            result = project_service.local_strict_status()
            _dump(result)
            return 0 if result.get("status") == "ok" else 1
        if args.action == "local-strict-doctor":
            result = project_service.local_strict_doctor()
            _dump(result)
            return 0 if result.get("status") == "ok" else 1
        if args.action == "local-agent-benchmark":
            result = project_service.local_agent_benchmark()
            _dump(result)
            return 0 if result.get("status") == "ok" else 1

    if args.command == "memory" and args.action == "build":
        result = run_task("memory.build", {"output_dir": args.output_dir})
        _dump({key: str(value) for key, value in result.items()})
        return 0

    if args.command == "applications":
        if args.action in {"plan", "run", "repair", "inspect-run"}:
            database = Database()
            database.init_schema()
            executor = CellExecutor(
                database,
                handlers=production_handler_registry(),
                validators=production_validator_registry(),
                worker_id="career-applications-cli",
            )
            try:
                if args.action == "plan":
                    plan = executor.plan(args.application_id, args.deliverable)
                    _dump(_cell_run_payload(executor, plan.run_id, status="planned"))
                    return 0
                _scoped_cell_run(executor, args.application_id, args.run_id)
                if args.action == "run":
                    executor.run_ready(args.run_id)
                    if executor.is_terminal(args.run_id):
                        executor.finalize(args.run_id)
                    _dump(_cell_run_payload(executor, args.run_id))
                    return 0
                if args.action == "repair":
                    executor.repair(args.run_id, args.node, args.reason)
                    _dump(_cell_run_payload(executor, args.run_id, status="repairing"))
                    return 0
                persisted_run = database.fetch_one(
                    "SELECT status FROM application_runs WHERE run_id = ?",
                    (args.run_id,),
                )
                if persisted_run is None:
                    raise KeyError(f"unknown application run: {args.run_id}")
                _dump(
                    _cell_run_payload(
                        executor, args.run_id, status=str(persisted_run["status"])
                    )
                )
                return 0
            except (KeyError, RuntimeError, ValueError) as exc:
                _dump_error(exc)
                return 1
            finally:
                database.close()
        if args.action == "write-default-config":
            path = applications_v2_service.write_default_config()
            _dump({"config": str(path)})
            return 0
        if args.action == "list-active":
            _dump(application_context_service.list_active())
            return 0
        if args.action == "inspect":
            result = application_context_service.inspect(args.application_id)
            _dump(result)
            return 0 if result.get("status") == "ok" else 1
        if args.action == "lock-status":
            result = application_context_service.inspect(args.application_id)
            _dump({
                "status": "locked" if result.get("lock") else "unlocked",
                "application_id": args.application_id,
                "lock": result.get("lock"),
            })
            return 0
        if args.action == "release-lock":
            result = application_context_service.release_lock(
                application_context_service.paths_for(args.application_id),
                dry_run=args.dry_run,
            )
            _dump(result)
            return 0
        if args.action == "doctor-concurrency":
            active = application_context_service.list_active()
            _dump({
                "status": "ok",
                "tracked_applications": active.get("count", 0),
                "locked_applications": [
                    item for item in active.get("applications", []) if item.get("locked")
                ],
                "session_registry": str(application_context_service.SESSION_REGISTRY),
                "alias_index": str(application_context_service.ALIAS_INDEX),
            })
            return 0
        if args.action == "migrate-global-state":
            _dump(
                application_context_service.migrate_global_state(
                    application_id=args.application_id,
                    dry_run=args.dry_run,
                )
            )
            return 0
        if args.action == "status":
            envelope = HarnessSupervisor(Path.cwd()).handle_message(
                "status das candidaturas",
                channel="cli-alias",
                execute=True,
            )
            result = envelope["result"]
            if args.format in {"human", "both"}:
                _print_human(_applications_status_human_summary(result))
            if args.format in {"json", "both"}:
                _dump(result)
            return 0
        if args.action == "heartbeat":
            if args.max_per_run is not None and args.max_per_run < 1:
                raise SystemExit("--max-per-run must be a positive integer.")
            if args.dry_run or not args.run_agent or args.skip_maintenance or args.maintenance_refresh:
                result = applications_v2_service.run_heartbeat(
                    applications_v2_service.HeartbeatV2Options(
                        max_per_run=args.max_per_run,
                        run_agent=args.run_agent,
                        dry_run=args.dry_run,
                        model=args.model,
                        variant=args.variant,
                        skip_maintenance=args.skip_maintenance,
                        maintenance_refresh=args.maintenance_refresh,
                    )
                )
            else:
                envelope = HarnessSupervisor(Path.cwd()).handle_message(
                    "processar fila de candidaturas",
                    channel="cli-alias",
                    execute=True,
                    max_per_run=args.max_per_run,
                    model=args.model,
                    variant=args.variant,
                )
                result = envelope["result"]
            if args.format in {"human", "both"}:
                _print_human(_heartbeat_human_summary(result))
            if args.format in {"json", "both"}:
                _dump(result)
            return 0

    if args.command == "derive":
        try:
            app_paths = _application_paths(getattr(args, "application_id", None))
            if app_paths:
                derived_context_service.configure_derived_dir(app_paths.derived_dir)
                derived_context_service.configure_state_store_path(app_paths.workflow_state)
                cv_content_service.configure_paths(cv_content_path=app_paths.cv_content, fit_map_path=app_paths.fit_map)
            if args.action == "job-pack":
                _dump(derived_context_service.build_job_extract())
                return 0
            if args.action == "job-sections":
                _dump(derived_context_service.build_job_sections())
                return 0
            if args.action == "job-keywords":
                _dump(derived_context_service.build_job_keywords())
                return 0
            if args.action == "reference-digest":
                _dump(derived_context_service.build_reference_digest())
                return 0
            if args.action == "evidence-pack":
                _dump(derived_context_service.build_candidate_evidence_pack())
                return 0
            if args.action == "fit-map-seed":
                _dump(derived_context_service.build_fit_map_seed())
                return 0
            if args.action == "cv-input-pack":
                _dump(derived_context_service.build_cv_input_pack())
                return 0
            if args.action == "cv-content-seed":
                _dump(derived_context_service.build_cv_content_seed())
                return 0
            if args.action == "habilidades-input-pack":
                _dump(derived_context_service.build_habilidades_input_pack())
                return 0
            if args.action == "feras-input-pack":
                _dump(derived_context_service.build_feras_input_pack())
                return 0
            if args.action == "cover-letter-input-pack":
                _dump(derived_context_service.build_cover_letter_input_pack())
                return 0
            if args.action == "all-for-fit-map":
                _dump(derived_context_service.build_all_for_fit_map())
                return 0
            if args.action == "validate-manifest":
                result = derived_context_service.validate_manifest()
                _dump(result)
                return 0 if result.get("status") == "ok" else 1
            if args.action == "context-doctor":
                result = derived_context_service.context_doctor()
                _dump(result)
                return 0 if result.get("status") == "ok" else 1
            if args.action == "assert-active":
                result = cv_content_service.active_artifact_status()
                _dump(result)
                return 0 if result.get("status") == "ok" else 1
            if args.action == "invalidate-stale":
                _dump(cv_content_service.invalidate_stale_artifacts())
                return 0
        except CareerError as exc:
            _dump_error(exc)
            return 1

    if args.command == "cover-letter":
        result = cover_letter_service.build_current_cover_letter(Path(args.output) if args.output else None)
        _dump(result)
        return 0

    if args.command == "feras":
        result = feras_service.build_current_feras(Path(args.output) if args.output else None)
        _dump(result)
        return 0

    if args.command == "workflow":
        state_store = WorkflowStateStore()
        if args.action == "show-state":
            _dump(state_store.load())
            return 0
        if args.action == "summary":
            payload = state_store.load()
            active_intake = payload.get("active_intake") if isinstance(payload.get("active_intake"), dict) else {}
            active_job = payload.get("active_job") if isinstance(payload.get("active_job"), dict) else {}
            history = payload.get("task_history", [])
            _dump(
                {
                    "status": "ok",
                    "active_intake": {
                        "source_type": active_intake.get("source_type"),
                        "source_id": active_intake.get("source_id"),
                        "company": active_intake.get("company"),
                        "role": active_intake.get("role"),
                        "job_description_path": active_intake.get("job_description_path"),
                        "next_required_step": active_intake.get("next_required_step"),
                    },
                    "active_job": active_job,
                    "completed_states_count": len(payload.get("completed_states", [])),
                    "task_history_count": len(history),
                    "last_task": history[-1] if history else None,
                }
            )
            return 0
        if args.action == "explain-last-run":
            payload = state_store.load()
            history = payload.get("task_history", [])
            _dump(history[-1] if history else {})
            return 0
        if args.action == "reset-state":
            state_store.reset()
            _dump(state_store.load())
            return 0
        if args.action == "reset":
            result = workflow_reset_service.operational_reset(
                dry_run=args.dry_run,
                backup=not args.no_backup,
            )
            _dump(result)
            return 0
        if args.action == "run-task":
            result = run_task(args.task_name, json.loads(args.arguments), state_store=state_store)
            _dump(result)
            return 0
        if args.action == "run-pipeline":
            result = run_pipeline(args.task_names, json.loads(args.arguments), state_store=state_store)
            _dump(result)
            return 0

    if args.command == "session":
        session_id = args.session_id or str(uuid.uuid4())
        db = Database()
        db.init_schema()
        svc = SessionMemoryService(db)
        if args.action == "status":
            _dump({"session_id": session_id, "memory": svc.status(session_id)})
        elif args.action == "set":
            svc.set(session_id, args.key, args.value, ttl_seconds=args.ttl)
            _dump({"session_id": session_id, "key": args.key, "ttl": args.ttl, "status": "set"})
        elif args.action == "get":
            value = svc.get(session_id, args.key)
            _dump({"session_id": session_id, "key": args.key, "value": value})
        elif args.action == "get-all":
            _dump({"session_id": session_id, "memory": svc.get_all(session_id)})
        elif args.action == "clean":
            svc.clean(session_id)
            _dump({"session_id": session_id, "status": "cleaned"})
        elif args.action == "reset":
            svc.reset(session_id)
            _dump({"session_id": session_id, "status": "reset"})
        return 0

    if args.command == "query":
        from career.services.query_engine import QueryEngine

        db = Database()
        db.init_schema()
        engine = QueryEngine(db)

        if args.list_filters:
            _dump(engine.list_filters())
            return 0

        if args.count:
            result = engine.count(args.filter, source=args.source)
            _dump({"count": result, "filter": args.filter, "source": args.source})
            return 0

        rows = engine.execute(
            args.filter,
            source=args.source,
            limit=args.limit,
            offset=args.offset,
        )
        output = engine.format_output(rows, fmt=args.format)
        print(output)
        return 0

    parser.print_help()
    return 2
