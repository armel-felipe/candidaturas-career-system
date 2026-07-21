from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeAlias

from career.cells.capabilities import CapabilitySet
from career.services import derived_context as derived_context_service
from career.services import cv_content as cv_content_service
from career.services import fit_map as fit_map_service
from career.services import intake as intake_service
from career.services import review as review_service
from career.services.application_context import ApplicationPaths
from career.utils import read_json, write_json


@dataclass(frozen=True)
class CellExecutionContext:
    """The complete, application-scoped capability context given to one cell."""

    application_id: str
    run_id: str
    node_id: str
    attempt: int
    paths: ApplicationPaths
    manifest_path: Path
    staging_dir: Path
    inputs: Mapping[str, Mapping[str, Any]]
    output_paths: tuple[Path, ...]
    capabilities: CapabilitySet
    repair_scope: str
    repair_reason: str | None = None
    validator_command: str = ""
    control_db_path: Path | None = None


@dataclass(frozen=True)
class CellOutput:
    """Compact handler result. Artifact bytes remain in attempt-local staging."""

    artifacts: Mapping[str, bytes | str] = field(default_factory=dict)
    handover: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidatorResult:
    command: str
    result: str
    report_path: Path
    reason: str = ""

    @classmethod
    def passed(cls, command: str, report_path: Path) -> ValidatorResult:
        return cls(command=command, result="passed", report_path=Path(report_path))

    @classmethod
    def failed(
        cls, command: str, report_path: Path, reason: str
    ) -> ValidatorResult:
        return cls(
            command=command,
            result="failed",
            report_path=Path(report_path),
            reason=str(reason),
        )


CellHandler: TypeAlias = Callable[[CellExecutionContext], CellOutput]
CellValidator: TypeAlias = Callable[
    [CellExecutionContext, CellOutput], ValidatorResult | Mapping[str, Any]
]


def production_handler_registry() -> dict[str, CellHandler]:
    """Return the production handlers already migrated to application cells."""
    return {
        "capture_source": _capture_source,
        "normalize_job": _normalize_job,
        "analyze_fit": _analyze_fit,
        "compose_cv": _compose_cv,
        "render_cv": _render_cv,
        "review_cv": _review_cv,
    }


def production_validator_registry() -> dict[str, CellValidator]:
    """Return validators paired with the migrated production handlers."""
    return {
        "validate-job-description": _validate_captured_source,
        "context:validate": _validate_normalized_job,
        "validate:fit-map": _validate_fit_map,
        "validate:fit-map:quality": _validate_fit_map_quality,
        "validate-provenance": _validate_fit_map_provenance,
        "cv:validate-content": _validate_cv_content,
        "validate-cv-provenance": _validate_cv_provenance,
        "validate:docx": _validate_rendered_cv,
        "cv:approve": _validate_cv_review,
    }


def production_handlers() -> dict[str, CellHandler]:
    """Deprecated name retained for the production CLI compatibility adapter."""
    return production_handler_registry()


def production_validators() -> dict[str, CellValidator]:
    """Deprecated name retained for the production CLI compatibility adapter."""
    return production_validator_registry()


def _capture_source(context: CellExecutionContext) -> CellOutput:
    source, source_path, source_hash = _read_input(context, "source_description")
    source_text = source.decode("utf-8")
    identity_raw, _identity_path, _identity_hash = _read_input(
        context, "application_identity"
    )
    identity = json.loads(identity_raw.decode("utf-8"))
    if identity.get("application_id") != context.application_id:
        raise ValueError("application identity belongs to another application")
    context.capabilities.assert_writable(context.paths.job_description)
    context.capabilities.assert_writable(context.paths.source_metadata)
    metadata = intake_service.capture_source(
        context.paths,
        source_text=source_text,
        source_metadata={
            "source_type": identity.get("source_type") or "cell_input",
            "source_id": identity.get("source_id"),
        },
    )
    handover = {
        "kind": "source_capture_handover",
        "application_id": context.application_id,
        "run_id": context.run_id,
        "source_path": str(source_path),
        "source_sha256": source_hash,
        **metadata,
    }
    return CellOutput(
        artifacts={"job_description.md": source},
        handover=handover,
        metadata={"job_fingerprint": metadata["job_fingerprint"]},
    )


def _normalize_job(context: CellExecutionContext) -> CellOutput:
    source, source_path, source_hash = _read_input(context, "job_description")
    canonical_source = context.paths.job_description.resolve()
    if not canonical_source.is_file():
        raise ValueError("application job description was not captured")
    if hashlib.sha256(canonical_source.read_bytes()).hexdigest() != source_hash:
        raise ValueError("application job description does not match cell input")
    context.capabilities.assert_writable(context.paths.derived_dir)
    result = derived_context_service.normalize_job(
        context.paths,
        job_description_path=canonical_source,
    )
    normalized = {
        **result["job_normalized"],
        "run_id": context.run_id,
        "source": {"path": str(source_path), "sha256": source_hash},
    }
    handover = {**result["handover"], "run_id": context.run_id}
    evidence = {**result["evidence_index"], "run_id": context.run_id}
    return CellOutput(
        artifacts={
            "job_normalized.json": _json_bytes(normalized),
            "handover_summary.json": _json_bytes(handover),
            "evidence_index.json": _json_bytes(evidence),
        },
        handover=handover,
        metadata={"job_fingerprint": source_hash},
    )


def _analyze_fit(context: CellExecutionContext) -> CellOutput:
    _normalized_raw, _normalized_path, _normalized_hash = _read_input(
        context, "job_normalized.json"
    )
    handover_raw, _handover_path, _handover_hash = _read_input(
        context, "handover_summary.json"
    )
    _evidence_raw, _evidence_path, _evidence_hash = _read_input(
        context, "evidence_index.json"
    )
    _draft_raw, draft_path, _draft_hash = _read_input(context, "fit_map_draft")
    handover = json.loads(handover_raw.decode("utf-8"))
    if handover.get("application_id") != context.application_id:
        raise ValueError("normalized handover belongs to another application")
    payload = fit_map_service.build_application_fit_map(
        context.paths,
        draft_path=draft_path,
        expected_job_fingerprint=str(handover.get("job_fingerprint") or ""),
        candidate_facts_revision=str(handover.get("candidate_facts_revision") or ""),
        produced_by_attempt=context.attempt,
        contract_version=_attempt_contract_version(context),
    )
    provenance = payload["provenance"]
    return CellOutput(
        artifacts={"fit_map.json": _json_bytes(payload)},
        handover={
            "kind": "fit_map_handover",
            "application_id": context.application_id,
            "run_id": context.run_id,
            "job_fingerprint": provenance["job_fingerprint"],
            "candidate_facts_revision": provenance["candidate_facts_revision"],
            "draft_sha256": provenance["draft_sha256"],
        },
        metadata={
            "job_fingerprint": provenance["job_fingerprint"],
            "candidate_facts_revision": provenance["candidate_facts_revision"],
        },
    )


def _compose_cv(context: CellExecutionContext) -> CellOutput:
    fit_raw, fit_map_path, fit_hash = _read_input(context, "fit_map.json")
    fit_map = json.loads(fit_raw.decode("utf-8"))
    provenance = fit_map.get("provenance") if isinstance(fit_map.get("provenance"), dict) else {}
    candidate_revision = str(provenance.get("candidate_facts_revision") or "")
    if not candidate_revision:
        raise ValueError("FIT_MAP is missing candidate facts revision")
    payload = cv_content_service.build_cv_content(
        context.paths,
        fit_map_path,
        candidate_revision,
    )
    return CellOutput(
        artifacts={"cv_content.json": _json_bytes(payload)},
        handover={
            "kind": "cv_content_handover",
            "application_id": context.application_id,
            "run_id": context.run_id,
            "fit_map_sha256": fit_hash,
            "candidate_facts_revision": candidate_revision,
        },
        metadata={
            "fit_map_sha256": fit_hash,
            "candidate_facts_revision": candidate_revision,
        },
    )


def _render_cv(context: CellExecutionContext) -> CellOutput:
    _content_raw, content_path, content_hash = _read_input(context, "cv_content.json")
    context.capabilities.assert_writable(context.staging_dir)
    artifact = cv_content_service.render_cv(
        content_path,
        context.staging_dir,
        context.application_id,
    )
    content = artifact.read_bytes()
    return CellOutput(
        artifacts={"cv.docx": content},
        handover={
            "kind": "cv_render_handover",
            "application_id": context.application_id,
            "run_id": context.run_id,
            "cv_content_sha256": content_hash,
            "rendered_filename": artifact.name,
        },
        metadata={"cv_content_sha256": content_hash, "rendered_filename": artifact.name},
    )


def _review_cv(context: CellExecutionContext) -> CellOutput:
    _artifact_raw, artifact_path, artifact_hash = _read_input(context, "cv.docx")
    _fit_raw, fit_map_path, fit_map_hash = _read_input(context, "fit_map.json")
    registry_path = context.staging_dir / "keyword_ats_registry.json"
    # Review intermediates are attempt-local; immutable CellOutput bytes are
    # the only review/approval records published by this node.
    report_path = context.staging_dir / "cv_review.json"
    polish_path = context.staging_dir / "polish_review.json"
    for path in (registry_path, report_path, polish_path):
        context.capabilities.assert_writable(path)
    try:
        report = review_service.approve_cv(
            artifact_path,
            fit_map_path,
            registry_path,
            report_path,
            polish_path,
            control_db_path=context.control_db_path,
        )
    except SystemExit as exc:
        raise ValueError(f"objective CV review failed: {exc}") from exc
    report_bytes = _json_bytes(report)
    approval_manifest = {
        "kind": "approved_cv_artifact",
        "application_id": context.application_id,
        "artifact_path": str(artifact_path),
        "artifact_sha256": artifact_hash,
        "fit_map_path": str(fit_map_path),
        "fit_map_sha256": fit_map_hash,
        "review_report_artifact": "cv_review.json",
        "review_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "approved_for_delivery": bool(report.get("approved_for_delivery")),
    }
    return CellOutput(
        artifacts={
            "cv_review.json": report_bytes,
            "polish_review.json": polish_path.read_bytes(),
            "approved_cv_manifest.json": _json_bytes(approval_manifest),
            "keyword_ats_registry.json": registry_path.read_bytes(),
        },
        handover={"kind": "cv_review_handover", **approval_manifest},
        metadata={
            "artifact_sha256": artifact_hash,
            "fit_map_sha256": fit_map_hash,
            "approved_for_delivery": bool(report.get("approved_for_delivery")),
        },
    )
def _validate_captured_source(
    context: CellExecutionContext, output: CellOutput
) -> ValidatorResult:
    reason = ""
    try:
        raw = output.artifacts.get("job_description.md")
        if not isinstance(raw, (bytes, str)):
            raise ValueError("captured job description is missing")
        content = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        if not content.strip():
            raise ValueError("captured job description is empty")
        if not context.paths.job_description.is_file():
            raise ValueError("application job description was not persisted")
        if context.paths.job_description.read_bytes() != content:
            raise ValueError("persisted job description differs from captured source")
        metadata = read_json(context.paths.source_metadata)
        if metadata.get("application_id") != context.application_id:
            raise ValueError("captured source metadata belongs to another application")
        if metadata.get("job_fingerprint") != hashlib.sha256(content).hexdigest():
            raise ValueError("captured source metadata fingerprint mismatch")
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"
    return _persist_validator_result(context, reason)


def _validate_normalized_job(
    context: CellExecutionContext, output: CellOutput
) -> ValidatorResult:
    report_path = context.paths.reviews_dir / (
        f"{context.node_id}-{context.attempt}-context-validate.json"
    )
    context.capabilities.assert_writable(report_path)
    reason = ""
    try:
        _source, _source_path, source_hash = _read_input(context, "job_description")
        expected = {
            "job_normalized.json": "job_normalized",
            "handover_summary.json": "handover_summary",
            "evidence_index.json": "evidence_index",
        }
        if set(output.artifacts) != set(expected):
            raise ValueError("normalized job output set does not match its contract")
        for artifact_name, kind in expected.items():
            raw = output.artifacts[artifact_name]
            payload = json.loads(
                (raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            )
            if (
                payload.get("kind") != kind
                or payload.get("application_id") != context.application_id
                or payload.get("run_id") != context.run_id
            ):
                raise ValueError(f"invalid normalized job identity: {artifact_name}")
        normalized = json.loads(
            output.artifacts["job_normalized.json"].decode("utf-8")
            if isinstance(output.artifacts["job_normalized.json"], bytes)
            else output.artifacts["job_normalized.json"]
        )
        if normalized.get("source", {}).get("sha256") != source_hash:
            raise ValueError("normalized job source hash mismatch")
        manifest = read_json(context.paths.derived_dir / "manifest.json")
        if (
            manifest.get("application_id") != context.application_id
            or manifest.get("fingerprint") != source_hash
        ):
            raise ValueError("application derived manifest identity mismatch")
        if not str(manifest.get("candidate_facts_revision") or ""):
            raise ValueError("application derived manifest lacks candidate facts revision")
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"
    return _persist_validator_result(context, reason, report_path=report_path)


def _validate_fit_map(
    context: CellExecutionContext, output: CellOutput
) -> ValidatorResult:
    reason = ""
    try:
        fit_map_service.validate_application_fit_map(
            _artifact_json(output, "fit_map.json"),
            application_paths=context.paths,
            expected_candidate_facts_revision=_expected_candidate_revision(context),
            expected_draft_sha256=_expected_draft_sha256(context),
            expected_contract_version=_attempt_contract_version(context),
            expected_produced_by_attempt=context.attempt,
        )
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"
    return _persist_validator_result(context, reason)


def _validate_fit_map_quality(
    context: CellExecutionContext, output: CellOutput
) -> ValidatorResult:
    reason = ""
    try:
        payload = _artifact_json(output, "fit_map.json")
        hits = fit_map_service._string_hits(
            payload,
            fit_map_service.SUSPICIOUS_TEXT_MARKERS + fit_map_service.MOJIBAKE_MARKERS,
        )
        if hits:
            raise ValueError("FIT_MAP quality markers found")
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"
    return _persist_validator_result(context, reason)


def _validate_fit_map_provenance(
    context: CellExecutionContext, output: CellOutput
) -> ValidatorResult:
    reason = ""
    try:
        fit_map_service.validate_application_fit_map(
            _artifact_json(output, "fit_map.json"),
            application_paths=context.paths,
            expected_candidate_facts_revision=_expected_candidate_revision(context),
            expected_draft_sha256=_expected_draft_sha256(context),
            expected_contract_version=_attempt_contract_version(context),
            expected_produced_by_attempt=context.attempt,
        )
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"
    return _persist_validator_result(context, reason)


def _validate_cv_content(
    context: CellExecutionContext, output: CellOutput
) -> ValidatorResult:
    reason = ""
    try:
        payload = _artifact_json(output, "cv_content.json")
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        if metadata.get("application_id") != context.application_id:
            raise ValueError("cv content belongs to another application")
        if not str(metadata.get("candidate_facts_revision") or ""):
            raise ValueError("cv content is missing candidate facts revision")
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"
    return _persist_validator_result(context, reason)


def _validate_cv_provenance(
    context: CellExecutionContext, output: CellOutput
) -> ValidatorResult:
    reason = ""
    try:
        payload = _artifact_json(output, "cv_content.json")
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        fit_raw, _fit_path, fit_hash = _read_input(context, "fit_map.json")
        fit_map = json.loads(fit_raw.decode("utf-8"))
        fit_provenance = fit_map.get("provenance") if isinstance(fit_map.get("provenance"), dict) else {}
        if metadata.get("candidate_facts_revision") != fit_provenance.get("candidate_facts_revision"):
            raise ValueError("cv content candidate facts revision mismatch")
        if metadata.get("source_fit_map") != str(_fit_path):
            raise ValueError("cv content FIT_MAP path mismatch")
        if not fit_hash:
            raise ValueError("cv content FIT_MAP hash is missing")
        cv_content_service.validate_canonical_provenance(
            payload,
            fit_map=fit_map,
            fit_map_path=_fit_path,
            fit_map_sha256=fit_hash,
        )
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"
    return _persist_validator_result(context, reason)


def _validate_rendered_cv(
    context: CellExecutionContext, output: CellOutput
) -> ValidatorResult:
    report_path = context.paths.reviews_dir / (
        f"{context.node_id}-{context.attempt}-validate-docx.json"
    )
    context.capabilities.assert_writable(report_path)
    reason = ""
    artifact_path = ""
    artifact_sha256 = ""
    try:
        artifact = context.staging_dir / "cv.docx"
        if not artifact.is_file():
            raise ValueError("staged DOCX is missing")
        artifact_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
        artifact_path = str(
            context.paths.artifacts_dir
            / "cv.docx"
            / artifact_sha256[:12]
            / "cv.docx"
        )
        result = subprocess.run(
            [sys.executable, "scripts/docx/validate_docx.py", str(artifact)],
            cwd=Path(__file__).resolve().parents[3],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise ValueError(f"DOCX validation failed: {result.stdout}{result.stderr}")
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"
    write_json(
        report_path,
        {
            "command": context.validator_command,
            "result": "failed" if reason else "passed",
            "reason": reason,
            "application_id": context.application_id,
            "run_id": context.run_id,
            "node_id": context.node_id,
            "attempt": context.attempt,
            "artifact_path": artifact_path,
            "artifact_sha256": artifact_sha256,
        },
    )
    if reason:
        return ValidatorResult.failed(context.validator_command, report_path, reason)
    return ValidatorResult.passed(context.validator_command, report_path)


def _validate_cv_review(
    context: CellExecutionContext, output: CellOutput
) -> ValidatorResult:
    reason = ""
    try:
        report = _artifact_json(output, "cv_review.json")
        artifact_raw, artifact_path, artifact_hash = _read_input(context, "cv.docx")
        _fit_raw, fit_map_path, fit_map_hash = _read_input(context, "fit_map.json")
        approval = _artifact_json(output, "approved_cv_manifest.json")
        if not report.get("approved_for_delivery"):
            raise ValueError("objective review did not approve the DOCX")
        if approval.get("application_id") != context.application_id:
            raise ValueError("approved artifact manifest belongs to another application")
        if approval.get("artifact_path") != str(artifact_path) or approval.get("artifact_sha256") != artifact_hash:
            raise ValueError("approved artifact manifest does not reference exact DOCX")
        if approval.get("fit_map_path") != str(fit_map_path) or approval.get("fit_map_sha256") != fit_map_hash:
            raise ValueError("approved artifact manifest does not reference exact FIT_MAP")
        if approval.get("review_report_artifact") != "cv_review.json":
            raise ValueError("approved artifact manifest does not reference published review")
        if approval.get("review_report_sha256") != hashlib.sha256(_json_bytes(report)).hexdigest():
            raise ValueError("approved artifact manifest review hash mismatch")
        if hashlib.sha256(artifact_raw).hexdigest() != artifact_hash:
            raise ValueError("reviewed DOCX hash changed during review")
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"
    return _persist_validator_result(context, reason)


def _read_input(
    context: CellExecutionContext, input_name: str
) -> tuple[bytes, Path, str]:
    input_record = context.inputs.get(input_name)
    if not isinstance(input_record, Mapping):
        matching = [
            value
            for key, value in context.inputs.items()
            if key.endswith(f":{input_name}")
            or (
                input_name == "job_description"
                and key.endswith(":job_description.md")
            )
            or (
                input_name == "source_description"
                and key.endswith(":job_description.md")
            )
        ]
        input_record = matching[0] if len(matching) == 1 else None
    if not isinstance(input_record, Mapping):
        raise ValueError(f"missing required cell input: {input_name}")
    path = context.capabilities.assert_readable(Path(str(input_record.get("path", ""))))
    if not path.is_file():
        raise ValueError(f"cell input is not a file: {input_name}")
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != input_record.get("sha256"):
        raise ValueError(f"cell input hash mismatch: {input_name}")
    return content, path, digest


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def _artifact_json(output: CellOutput, artifact_name: str) -> dict[str, Any]:
    raw = output.artifacts.get(artifact_name)
    if not isinstance(raw, (bytes, str)):
        raise ValueError(f"missing cell artifact: {artifact_name}")
    payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    if not isinstance(payload, dict):
        raise ValueError(f"cell artifact is not an object: {artifact_name}")
    return payload


def _attempt_contract_version(context: CellExecutionContext) -> str:
    manifest = read_json(context.manifest_path)
    return str(manifest.get("contract_version") or "")


def _expected_candidate_revision(context: CellExecutionContext) -> str:
    raw, _path, _digest = _read_input(context, "handover_summary.json")
    payload = json.loads(raw.decode("utf-8"))
    return str(payload.get("candidate_facts_revision") or "")


def _expected_draft_sha256(context: CellExecutionContext) -> str:
    _raw, _path, digest = _read_input(context, "fit_map_draft")
    return digest


def _persist_validator_result(
    context: CellExecutionContext,
    reason: str,
    *,
    report_path: Path | None = None,
) -> ValidatorResult:
    safe_command = context.validator_command.replace(":", "-").replace("/", "-")
    report_path = report_path or context.paths.reviews_dir / (
        f"{context.node_id}-{context.attempt}-{safe_command}.json"
    )
    context.capabilities.assert_writable(report_path)
    write_json(
        report_path,
        {
            "command": context.validator_command,
            "result": "failed" if reason else "passed",
            "reason": reason,
        },
    )
    if reason:
        return ValidatorResult.failed(context.validator_command, report_path, reason)
    return ValidatorResult.passed(context.validator_command, report_path)
