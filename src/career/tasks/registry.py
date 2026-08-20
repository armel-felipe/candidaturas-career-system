from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any
from uuid import uuid4

from career.paths import CAREER_STATE, INBOX, OUTPUTS, ROOT
from career.services import fit_map as fit_map_service
from career.services import memory as memory_service
from career.services import notion as notion_service
from career.services import project as project_service
from career.services import review as review_service
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import ApplicationRepository
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.services.persistence.reference_repository import ReferenceRepository
from career.utils import json_fingerprint, read_json, sha256_file
from career.workflow.state_machine import TASK_TO_STATE, WorkflowStateMachine
from career.workflow.state_store import WorkflowStateStore


TRANSLATION_REGISTRY = (
    ROOT / ".agents/skills/career-system/references/keyword_translation_registry.json"
)


@dataclass
class TaskContext:
    arguments: dict[str, Any]
    state_store: WorkflowStateStore


@dataclass
class Task:
    name: str
    runner: Callable[[TaskContext], Any]


def _state_machine(state_store: WorkflowStateStore) -> WorkflowStateMachine:
    payload = state_store.load()
    active_job = payload.get("active_job") if isinstance(payload.get("active_job"), dict) else {}
    return WorkflowStateMachine(
        set(payload.get("completed_states", [])),
        payload.get("fingerprints", {}),
        active_job.get("fingerprint"),
    )


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


def _task_input_payload(task_name: str, arguments: dict[str, Any], state_store: WorkflowStateStore | None = None) -> dict[str, Any]:
    payload = dict(arguments)
    if state_store is not None:
        projected = state_store.load()
        active_job = projected.get("active_job")
        if isinstance(active_job, dict):
            payload["_active_job_fingerprint"] = active_job.get("fingerprint")
            payload["_application_id"] = active_job.get("application_id")
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


def _fingerprints(task_name: str, arguments: dict[str, Any], result: Any, state_store: WorkflowStateStore | None = None) -> tuple[str | None, str | None]:
    normalized_input = _task_input_payload(task_name, arguments, state_store=state_store)
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
    result: Any,
    *,
    arguments: dict[str, Any],
) -> None:
    state_name = TASK_TO_STATE.get(task_name)
    if state_name is None:
        return
    projected = state_store.load()
    active_job = projected.get("active_job")
    if not isinstance(active_job, dict):
        raise ValueError("application-scoped workflow projection is missing active_job")
    input_fingerprint, output_fingerprint = _fingerprints(
        task_name, arguments, result, state_store=state_store
    )
    if not input_fingerprint or not output_fingerprint:
        raise ValueError(
            f"task {task_name} did not produce the required gate input/output hashes"
        )
    GateRepository(state_store.database).record(
        GateReceipt(
            application_id=str(state_store.application_id or ""),
            application_fingerprint=str(active_job.get("fingerprint") or ""),
            run_id=str(arguments.get("run_id") or f"task-{task_name}-{uuid4().hex}"),
            gate=state_name,
            validator=task_name,
            input_hash=input_fingerprint,
            output_hash=output_fingerprint,
            revision_id=(
                str(arguments["revision_id"])
                if arguments.get("revision_id") is not None
                else None
            ),
        )
    )


def _run_task(task_name: str, runner: Callable[[TaskContext], Any], context: TaskContext) -> Any:
    machine = _state_machine(context.state_store)
    machine.ensure_task_allowed(task_name)
    result = runner(context)
    _record_task_completion(
        context.state_store,
        task_name,
        result,
        arguments=context.arguments,
    )
    machine.complete_task(task_name)
    return result


def _notion_refresh(context: TaskContext) -> Any:
    token, database_id = notion_service.notion_config()
    return notion_service.refresh_cache(token, database_id, refresh=context.arguments.get("refresh", "missing"))


def _notion_build_cache(context: TaskContext) -> Any:
    token, database_id = notion_service.notion_config()
    return notion_service.build_cache(database_id=database_id)


def _save_job_description(context: TaskContext) -> Any:
    return project_service.save_job_description(
        company=context.arguments["company"],
        role=context.arguments["role"],
        text=context.arguments["text"],
        output_dir=Path(context.arguments.get("output_dir", INBOX / "job_descriptions")),
    )


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
        translation_registry_path=Path(
            context.arguments.get("translation_registry", TRANSLATION_REGISTRY)
        ),
    )


def _cv_approve(context: TaskContext) -> Any:
    return review_service.approve_cv(
        artifact=Path(context.arguments["artifact"]),
        fit_map_path=Path(context.arguments.get("fit_map", CAREER_STATE / "fit_map.json")),
        registry_path=Path(context.arguments["registry"]),
        report_path=Path(context.arguments["report"]),
        polish_report_path=Path(context.arguments["polish_report"]) if context.arguments.get("polish_report") else None,
        translation_registry_path=Path(
            context.arguments.get("translation_registry", TRANSLATION_REGISTRY)
        ),
    )


def _project_diagnose_runtime(context: TaskContext) -> Any:
    output = Path(context.arguments.get("output", OUTPUTS / "_tmp" / "runtime_diagnosis.json"))
    return project_service.write_runtime_diagnosis(output)


def _memory_build(context: TaskContext) -> Any:
    return memory_service.build_memory_bundle(Path(context.arguments.get("output_dir", CAREER_STATE / "memory")))


def _registry_rebuild(context: TaskContext) -> Any:
    return memory_service.rebuild_keyword_registry_from_cache(
        cache_path=Path(context.arguments.get("cache_path", ROOT / "inbox" / "notion" / "applications_cache.json")),
        output_path=Path(context.arguments.get("output", CAREER_STATE / "derived" / "keyword_ats_registry.json")),
    )


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
    "registry.rebuild": Task("registry.rebuild", _registry_rebuild),
}


def run_task(task_name: str, arguments: dict[str, Any] | None = None, state_store: WorkflowStateStore | None = None) -> Any:
    if task_name not in TASKS:
        raise KeyError(f"Unknown task: {task_name}")
    if state_store is None or not state_store.application_id or state_store.database is None:
        raise ValueError("run_task requires an application-scoped WorkflowStateStore")
    context = TaskContext(arguments=arguments or {}, state_store=state_store)
    task = TASKS[task_name]
    return _run_task(task.name, task.runner, context)


def run_pipeline(task_names: list[str], arguments: dict[str, Any] | None = None, state_store: WorkflowStateStore | None = None) -> list[Any]:
    if state_store is None or not state_store.application_id or state_store.database is None:
        raise ValueError("run_pipeline requires an application-scoped WorkflowStateStore")
    results = []
    for task_name in task_names:
        results.append(run_task(task_name, arguments=arguments, state_store=state_store))
    return results


def _fit_map_lineage(
    state_store: WorkflowStateStore,
) -> tuple[str, Any, str, tuple[Any, ...]]:
    if not state_store.application_id or state_store.database is None:
        raise ValueError(
            "FIT_MAP operation requires an application-scoped WorkflowStateStore"
        )
    application_id = str(state_store.application_id)
    applications = ApplicationRepository(state_store.database)
    application = applications.resolve(application_id=application_id)
    application_revision_id = applications.get_current_revision_id(application_id)
    if not application_revision_id:
        raise ValueError(f"application {application_id} has no current source revision")
    source_revision = applications.get_application_revision(
        application_id, application_revision_id
    )
    job_description = applications.get_job_description_for_application_revision(
        application_id, application_revision_id
    )
    if (
        not application.fingerprint
        or application.fingerprint != source_revision.fingerprint
        or application.fingerprint != job_description.content_hash
    ):
        raise ValueError(
            "current application fingerprint does not match its source snapshot"
        )
    references = ReferenceRepository(state_store.database).list_current_versions()
    if not references:
        raise ValueError(
            "fit_map persistence requires at least one canonical reference version"
        )
    return application_id, application, application_revision_id, references


def _fit_map_snapshot(
    payload: dict[str, Any], references: tuple[Any, ...]
) -> dict[str, Any]:
    snapshot = dict(payload)
    snapshot["reference_versions"] = [
        {
            "reference_id": reference.reference_id,
            "kind": reference.kind,
            "logical_key": reference.logical_key,
            "content_hash": reference.content_hash,
            "source_hash": reference.source_hash,
        }
        for reference in references
    ]
    return snapshot


def run_fit_map_stage(
    action: str,
    *,
    state_store: WorkflowStateStore,
    draft_path: Path,
    output_path: Path,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run one public FIT_MAP stage and atomically bind it to SQLite lineage."""
    task_name = f"fit_map.{action}"
    if action not in {"build", "score", "validate"}:
        raise ValueError(f"unsupported FIT_MAP stage: {action}")
    application_id, application, application_revision_id, references = (
        _fit_map_lineage(state_store)
    )
    machine = _state_machine(state_store)
    machine.ensure_task_allowed(task_name)
    database = state_store.database
    assert database is not None
    analysis = AnalysisRepository(database)
    gates = GateRepository(database)
    analysis.ensure_schema()
    gates.ensure_schema()
    resolved_run_id = str(run_id or "").strip() or f"fit-map-{action}-{uuid4().hex}"
    carried: list[GateReceipt] = []

    if action != "build":
        current = analysis.get_current(application_id)
        required = ["fit_map_built"]
        if action == "validate":
            required.append("fit_map_scored")
        carried = [
            gates.receipt_for_revision(application_id, gate, current.revision_id)
            for gate in required
        ]

    if action == "build":
        input_hash = sha256_file(draft_path)
        result: Any = fit_map_service.build_fit_map(draft_path, output_path)
        output_hash = sha256_file(output_path)
    elif action == "score":
        input_hash = sha256_file(output_path)
        result = fit_map_service.score_fit_map(output_path)
        output_hash = sha256_file(output_path)
    else:
        input_hash = sha256_file(output_path)
        result = fit_map_service.validate_fit_map(output_path)
        output_hash = json_fingerprint(result)

    payload = read_json(output_path)
    snapshot = _fit_map_snapshot(payload, references)
    source_hash = sha256_file(output_path)
    validator = task_name
    gate = TASK_TO_STATE[task_name]
    with database.transaction(immediate=True) as conn:
        revision_id = analysis.create_revision(
            application_id,
            snapshot,
            source_hash=source_hash,
            application_revision_id=application_revision_id,
            conn=conn,
        )
        receipt_ids: dict[str, str] = {}
        for prior in carried:
            receipt_ids[prior.gate] = gates.record(
                GateReceipt(
                    application_id=application_id,
                    application_fingerprint=str(application.fingerprint),
                    run_id=resolved_run_id,
                    gate=prior.gate,
                    validator=prior.validator,
                    input_hash=prior.input_hash,
                    output_hash=prior.output_hash,
                    revision_id=revision_id,
                ),
                conn=conn,
            )
        receipt_ids[gate] = gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint=str(application.fingerprint),
                run_id=resolved_run_id,
                gate=gate,
                validator=validator,
                input_hash=input_hash,
                output_hash=output_hash,
                revision_id=revision_id,
            ),
            conn=conn,
        )
    machine.complete_task(task_name)
    return {
        "application_id": application_id,
        "application_revision_id": application_revision_id,
        "revision_id": revision_id,
        "run_id": resolved_run_id,
        "receipts": receipt_ids,
        "result": result,
    }


def finalize_fit_map(
    *,
    state_store: WorkflowStateStore,
    draft_path: Path,
    output_path: Path,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Finalize one scoped FIT_MAP and persist its immutable revision lineage.

    Build, score and validation operate on the compatibility file, but their
    authoritative completion receipts are recorded only after the resulting
    payload has been stored as an immutable SQLite analysis revision.
    """
    if not state_store.application_id or state_store.database is None:
        raise ValueError(
            "finalize_fit_map requires an application-scoped WorkflowStateStore"
        )
    resolved_run_id = str(run_id or "").strip() or f"fit-map-finalize-{uuid4().hex}"
    draft_path = Path(draft_path)
    output_path = Path(output_path)
    validate_draft_result = run_task(
        "fit_map.validate_draft",
        {"path": str(draft_path), "run_id": resolved_run_id},
        state_store=state_store,
    )
    application_id, application, application_revision_id, current_references = (
        _fit_map_lineage(state_store)
    )
    draft_hash = sha256_file(draft_path)
    fit_map_service.build_fit_map(draft_path, output_path)
    built_hash = sha256_file(output_path)
    fit_map_service.score_fit_map(output_path)
    scored_hash = sha256_file(output_path)
    validated_payload = fit_map_service.validate_fit_map(output_path)
    validation_hash = json_fingerprint(validated_payload)

    snapshot = _fit_map_snapshot(validated_payload, current_references)
    analysis = AnalysisRepository(state_store.database)
    gates = GateRepository(state_store.database)
    analysis.ensure_schema()
    gates.ensure_schema()
    with state_store.database.transaction(immediate=True) as conn:
        revision_id = analysis.create_revision(
            application_id,
            snapshot,
            source_hash=scored_hash,
            application_revision_id=application_revision_id,
            conn=conn,
        )
        receipt_ids = {
            "fit_map_built": gates.record(
                GateReceipt(
                    application_id=application_id,
                    application_fingerprint=application.fingerprint,
                    run_id=resolved_run_id,
                    gate="fit_map_built",
                    validator="fit_map.build",
                    input_hash=draft_hash,
                    output_hash=built_hash,
                    revision_id=revision_id,
                ),
                conn=conn,
            ),
            "fit_map_scored": gates.record(
                GateReceipt(
                    application_id=application_id,
                    application_fingerprint=application.fingerprint,
                    run_id=resolved_run_id,
                    gate="fit_map_scored",
                    validator="fit_map.score",
                    input_hash=built_hash,
                    output_hash=scored_hash,
                    revision_id=revision_id,
                ),
                conn=conn,
            ),
            "fit_map_validated": gates.record(
                GateReceipt(
                    application_id=application_id,
                    application_fingerprint=application.fingerprint,
                    run_id=resolved_run_id,
                    gate="fit_map_validated",
                    validator="fit_map.validate",
                    input_hash=scored_hash,
                    output_hash=validation_hash,
                    revision_id=revision_id,
                ),
                conn=conn,
            ),
        }
    return {
        "application_id": application_id,
        "application_revision_id": application_revision_id,
        "revision_id": revision_id,
        "run_id": resolved_run_id,
        "receipts": receipt_ids,
        "validate_draft": validate_draft_result,
        "build": str(output_path),
        "score": str(output_path),
        "validate": validated_payload,
    }
