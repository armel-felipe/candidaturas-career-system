from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Any

from career.paths import CAREER_STATE, INBOX, OUTPUTS, ROOT
from career.services import fit_map as fit_map_service
from career.services import memory as memory_service
from career.services import notion as notion_service
from career.services import project as project_service
from career.services import review as review_service
from career.utils import json_fingerprint, sha256_file, utc_now_iso
from career.workflow.state_machine import WorkflowStateMachine
from career.workflow.state_store import WorkflowStateStore


@dataclass(slots=True)
class TaskContext:
    arguments: dict[str, Any]
    state_store: WorkflowStateStore


@dataclass(slots=True)
class Task:
    name: str
    runner: Callable[[TaskContext], Any]


def _state_machine(state_store: WorkflowStateStore) -> WorkflowStateMachine:
    payload = state_store.load()
    active_job = _infer_active_job(state_store) or {}
    return WorkflowStateMachine(
        set(payload.get("completed_states", [])),
        payload.get("fingerprints", {}),
        active_job.get("fingerprint"),
    )


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _infer_active_job(state_store: WorkflowStateStore) -> dict[str, Any] | None:
    payload = state_store.load()
    active = payload.get("active_job")
    if isinstance(active, dict) and active.get("path") and active.get("fingerprint"):
        path = ROOT / active["path"]
        if path.exists() and sha256_file(path) == active["fingerprint"]:
            return active
    job_dir = INBOX / "job_descriptions"
    if not job_dir.exists():
        return None
    candidates = [path for path in job_dir.glob("*.md") if path.is_file()]
    if not candidates:
        return None
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    return {
        "path": _relative(latest),
        "fingerprint": sha256_file(latest),
        "source": "latest_job_description",
    }


def _set_active_job(state_store: WorkflowStateStore, path: Path, *, company: str | None = None, role: str | None = None) -> dict[str, Any]:
    active_job = {
        "path": _relative(path),
        "fingerprint": sha256_file(path),
        "company": company,
        "role": role,
        "source": "project.save_job_description",
    }
    payload = state_store.load()
    payload["active_job"] = active_job
    state_store.payload = payload
    state_store.save()
    return active_job


def _result_summary(task_name: str, result: Any) -> dict[str, Any]:
    if isinstance(result, Path):
        return {"summary": f"{task_name} wrote {result}", "artifact_paths": [str(result)]}
    if task_name.startswith("notion.") and isinstance(result, dict):
        return {
            "summary": f"{task_name} completed",
            "artifact_paths": [str(value) for value in result.get("outputs", {}).values() if isinstance(value, str)],
        }
    if task_name.startswith("fit_map.") and isinstance(result, dict):
        return {"summary": f"{task_name} validated payload", "artifact_paths": []}
    if task_name.startswith("cv.") and isinstance(result, dict):
        approved = result.get("approved")
        return {"summary": f"{task_name} approved={approved}", "artifact_paths": [str(result.get("artifact", ""))]}
    if isinstance(result, dict):
        return {"summary": f"{task_name} completed", "artifact_paths": []}
    return {"summary": f"{task_name} completed", "artifact_paths": []}


def _task_input_payload(task_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    payload = dict(arguments)
    active_job = _infer_active_job(WorkflowStateStore())
    if active_job:
        payload["_active_job_fingerprint"] = active_job.get("fingerprint")
        payload["_active_job_path"] = active_job.get("path")
    if task_name in {"fit_map.validate_draft", "fit_map.build"}:
        path = Path(arguments.get("path") or arguments.get("draft") or CAREER_STATE / "fit_map.draft.json")
        payload["_draft_sha256"] = sha256_file(path) if path.exists() else None
    if task_name in {"fit_map.score", "fit_map.validate"}:
        path = Path(arguments.get("path", CAREER_STATE / "fit_map.json"))
        payload["_fit_map_sha256"] = sha256_file(path) if path.exists() else None
    if task_name in {"cv.review", "cv.approve"}:
        artifact = Path(arguments["artifact"])
        fit_map = Path(arguments.get("fit_map", CAREER_STATE / "fit_map.json"))
        registry = Path(arguments["registry"])
        payload["_artifact_sha256"] = sha256_file(artifact) if artifact.exists() else None
        payload["_fit_map_sha256"] = sha256_file(fit_map) if fit_map.exists() else None
        payload["_registry_sha256"] = sha256_file(registry) if registry.exists() else None
        payload["_polish_report_path"] = arguments.get("polish_report")
    return payload


def _fingerprints(task_name: str, arguments: dict[str, Any], result: Any) -> tuple[str | None, str | None]:
    normalized_input = _task_input_payload(task_name, arguments)
    input_fingerprint = json_fingerprint(normalized_input) if normalized_input else None
    output_fingerprint: str | None = None
    if isinstance(result, Path) and result.exists():
        output_fingerprint = sha256_file(result)
    elif task_name in {"fit_map.validate_draft", "fit_map.validate", "cv.review", "cv.approve"} and isinstance(result, dict):
        output_fingerprint = json_fingerprint(result)
    return input_fingerprint, output_fingerprint


def _record_task_completion(
    state_store: WorkflowStateStore,
    task_name: str,
    state_name: str | None,
    result: Any,
    *,
    arguments: dict[str, Any],
    status: str,
    started_at: str,
    finished_at: str,
    duration_ms: int,
) -> None:
    payload = state_store.load()
    completed = set(payload.get("completed_states", []))
    if state_name:
        completed.add(state_name)
    payload["completed_states"] = sorted(completed)
    summary = _result_summary(task_name, result)
    input_fingerprint, output_fingerprint = _fingerprints(task_name, arguments, result)
    entry = {
        "task": task_name,
        "state": state_name,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "summary": summary["summary"],
        "artifact_paths": summary["artifact_paths"],
        "input_fingerprint": input_fingerprint,
        "output_fingerprint": output_fingerprint,
    }
    payload.setdefault("task_history", []).append(entry)
    payload.setdefault("fingerprints", {})[task_name] = {
        "input": input_fingerprint,
        "output": output_fingerprint,
        "status": status,
        "state": state_name,
        "active_job_fingerprint": _infer_active_job(state_store).get("fingerprint") if _infer_active_job(state_store) else None,
    }
    state_store.payload = payload
    state_store.save()


def _run_task(task_name: str, runner: Callable[[TaskContext], Any], context: TaskContext) -> Any:
    machine = _state_machine(context.state_store)
    machine.ensure_task_allowed(task_name)
    started_at = utc_now_iso()
    started_clock = perf_counter()
    prior = context.state_store.load().get("fingerprints", {}).get(task_name, {})
    current_payload = _task_input_payload(task_name, context.arguments)
    current_input = json_fingerprint(current_payload) if current_payload else None
    reusable_tasks = {
        "fit_map.validate_draft",
        "fit_map.build",
        "fit_map.score",
        "fit_map.validate",
        "cv.review",
        "cv.approve",
    }
    if task_name in reusable_tasks and prior.get("input") == current_input and prior.get("status") in {"ok", "reused"}:
        finished_at = utc_now_iso()
        reused_result = {"reused": True, "task": task_name}
        state_name = machine.complete_task(task_name)
        _record_task_completion(
            context.state_store,
            task_name,
            state_name,
            reused_result,
            arguments=context.arguments,
            status="reused",
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=round((perf_counter() - started_clock) * 1000),
        )
        return reused_result
    result = runner(context)
    state_name = machine.complete_task(task_name)
    _record_task_completion(
        context.state_store,
        task_name,
        state_name,
        result,
        arguments=context.arguments,
        status="ok",
        started_at=started_at,
        finished_at=utc_now_iso(),
        duration_ms=round((perf_counter() - started_clock) * 1000),
    )
    return result


def _notion_refresh(context: TaskContext) -> Any:
    token, database_id = notion_service.notion_config()
    return notion_service.refresh_cache(token, database_id, refresh=context.arguments.get("refresh", "missing"))


def _notion_build_cache(context: TaskContext) -> Any:
    token, database_id = notion_service.notion_config()
    return notion_service.build_cache(database_id=database_id)


def _save_job_description(context: TaskContext) -> Any:
    output_path = project_service.save_job_description(
        company=context.arguments["company"],
        role=context.arguments["role"],
        text=context.arguments["text"],
        output_dir=Path(context.arguments.get("output_dir", INBOX / "job_descriptions")),
    )
    _set_active_job(context.state_store, output_path, company=context.arguments["company"], role=context.arguments["role"])
    return output_path


def _fit_map_template(context: TaskContext) -> Any:
    return fit_map_service.write_template(Path(context.arguments.get("output", CAREER_STATE / "fit_map.draft.json")))


def _fit_map_validate_draft(context: TaskContext) -> Any:
    return fit_map_service.validate_draft(Path(context.arguments.get("path", CAREER_STATE / "fit_map.draft.json")))


def _fit_map_build(context: TaskContext) -> Any:
    return fit_map_service.build_fit_map(
        Path(context.arguments.get("draft", CAREER_STATE / "fit_map.draft.json")),
        Path(context.arguments.get("output", CAREER_STATE / "fit_map.json")),
    )


def _fit_map_score(context: TaskContext) -> Any:
    return fit_map_service.score_fit_map(Path(context.arguments.get("path", CAREER_STATE / "fit_map.json")))


def _fit_map_validate(context: TaskContext) -> Any:
    return fit_map_service.validate_fit_map(Path(context.arguments.get("path", CAREER_STATE / "fit_map.json")))


def _cv_review(context: TaskContext) -> Any:
    return review_service.review_cv(
        artifact=Path(context.arguments["artifact"]),
        fit_map_path=Path(context.arguments.get("fit_map", CAREER_STATE / "fit_map.json")),
        registry_path=Path(context.arguments["registry"]),
        report_path=Path(context.arguments["report"]),
    )


def _cv_approve(context: TaskContext) -> Any:
    return review_service.approve_cv(
        artifact=Path(context.arguments["artifact"]),
        fit_map_path=Path(context.arguments.get("fit_map", CAREER_STATE / "fit_map.json")),
        registry_path=Path(context.arguments["registry"]),
        report_path=Path(context.arguments["report"]),
        polish_report_path=Path(context.arguments["polish_report"]) if context.arguments.get("polish_report") else None,
    )


def _project_diagnose_runtime(context: TaskContext) -> Any:
    output = Path(context.arguments.get("output", OUTPUTS / "_tmp" / "runtime_diagnosis.json"))
    return project_service.write_runtime_diagnosis(output)


def _memory_build(context: TaskContext) -> Any:
    return memory_service.build_memory_bundle(Path(context.arguments.get("output_dir", CAREER_STATE / "memory")))


TASKS = {
    "notion.refresh_cache": Task("notion.refresh_cache", _notion_refresh),
    "notion.build_cache": Task("notion.build_cache", _notion_build_cache),
    "project.save_job_description": Task("project.save_job_description", _save_job_description),
    "fit_map.template": Task("fit_map.template", _fit_map_template),
    "fit_map.validate_draft": Task("fit_map.validate_draft", _fit_map_validate_draft),
    "fit_map.build": Task("fit_map.build", _fit_map_build),
    "fit_map.score": Task("fit_map.score", _fit_map_score),
    "fit_map.validate": Task("fit_map.validate", _fit_map_validate),
    "cv.review": Task("cv.review", _cv_review),
    "cv.approve": Task("cv.approve", _cv_approve),
    "project.diagnose_runtime": Task("project.diagnose_runtime", _project_diagnose_runtime),
    "memory.build": Task("memory.build", _memory_build),
}


def run_task(task_name: str, arguments: dict[str, Any] | None = None, state_store: WorkflowStateStore | None = None) -> Any:
    if task_name not in TASKS:
        raise KeyError(f"Unknown task: {task_name}")
    context = TaskContext(arguments=arguments or {}, state_store=state_store or WorkflowStateStore())
    task = TASKS[task_name]
    return _run_task(task.name, task.runner, context)


def run_pipeline(task_names: list[str], arguments: dict[str, Any] | None = None, state_store: WorkflowStateStore | None = None) -> list[Any]:
    results = []
    state_store = state_store or WorkflowStateStore()
    for task_name in task_names:
        results.append(run_task(task_name, arguments=arguments, state_store=state_store))
    return results
