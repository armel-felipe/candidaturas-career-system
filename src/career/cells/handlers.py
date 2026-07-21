from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeAlias

from career.cells.capabilities import CapabilitySet
from career.services.application_context import ApplicationPaths
from career.utils import write_json


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


def production_handlers() -> dict[str, CellHandler]:
    """Return the application-scoped handlers available to the production CLI."""
    return {"normalize_job": _normalize_job}


def production_validators() -> dict[str, CellValidator]:
    """Return validators paired with the currently migrated production handlers."""
    return {"context:validate": _validate_normalized_job}


def _normalize_job(context: CellExecutionContext) -> CellOutput:
    source, source_path, source_hash = _read_input(context, "job_description")
    text = source.decode("utf-8")
    normalized = {
        "kind": "job_normalized",
        "application_id": context.application_id,
        "run_id": context.run_id,
        "source": {"path": str(source_path), "sha256": source_hash},
        "description_stats": {
            "chars": len(text),
            "lines": len([line for line in text.splitlines() if line.strip()]),
        },
    }
    handover = {
        "kind": "handover_summary",
        "application_id": context.application_id,
        "run_id": context.run_id,
        "job_fingerprint": source_hash,
    }
    evidence = {
        "kind": "evidence_index",
        "application_id": context.application_id,
        "run_id": context.run_id,
        "sources": [
            {
                "kind": "job_description",
                "path": str(source_path),
                "sha256": source_hash,
            }
        ],
    }
    return CellOutput(
        artifacts={
            "job_normalized.json": _json_bytes(normalized),
            "handover_summary.json": _json_bytes(handover),
            "evidence_index.json": _json_bytes(evidence),
        },
        handover=handover,
        metadata={"job_fingerprint": source_hash},
    )


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
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"

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


def _read_input(
    context: CellExecutionContext, input_name: str
) -> tuple[bytes, Path, str]:
    input_record = context.inputs.get(input_name)
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
