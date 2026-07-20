from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeAlias

from career.cells.capabilities import CapabilitySet
from career.services.application_context import ApplicationPaths


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
