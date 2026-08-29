"""Safe Phase 7 canary over the SQLite application projection.

The offline canary exercises stage derivation and provenance without starting
containers, invoking an agent, or writing candidature state.  ``live`` is a
deliberate preflight mode until a deployment operator explicitly enables a
real rollout target.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4
from typing import Any

from career.paths import ROOT
from career.services.applications_v2 import build_sqlite_application_projection
from career.services.database import Database
from career.services.persistence.application_repository import ApplicationNotFoundError, ApplicationRepository
from career.services.persistence.artifact_repository import ArtifactRepository
from career.services.runtime_verifier import verify_runtime


ALLOWED_BOTS = frozenset({"vagas_bot_01", "vagas_bot_02"})
ALLOWED_MODES = frozenset({"offline", "live"})


@dataclass(frozen=True)
class CanaryReport:
    status: str
    run_id: str
    application_id: str
    bot_id: str
    mode: str
    gates: dict[str, Any]
    artifacts: dict[str, Any]
    database_checks: dict[str, Any]
    rollback_checkpoint: dict[str, Any]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["warnings"] = list(self.warnings)
        return payload


def run_canary(
    application_id: str,
    bot_id: str,
    *,
    mode: str = "offline",
    root: Path | None = None,
    database_path: Path | None = None,
) -> CanaryReport:
    root = Path(root or ROOT).resolve()
    application_id = str(application_id or "").strip()
    bot_id = str(bot_id or "").strip()
    mode = str(mode or "").strip().lower()
    run_id = f"canary_{uuid4().hex}"
    db_path = Path(database_path or root / "control-plane" / "career.db").resolve()
    blockers: list[str] = []
    warnings: list[str] = []

    if not application_id:
        blockers.append("application_id_required")
    if bot_id not in ALLOWED_BOTS:
        blockers.append("unsupported_bot_id")
    if mode not in ALLOWED_MODES:
        blockers.append("unsupported_canary_mode")

    runtime = verify_runtime(root, strict=True, database_path=db_path)
    database_checks = {
        "runtime_verifier": runtime.status,
        "integrity": None,
        "foreign_key_errors": None,
        "database_path": str(db_path),
    }
    if runtime.blockers:
        blockers.append("runtime_verifier_blocked")

    if db_path.is_file():
        try:
            connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            database_checks["integrity"] = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            database_checks["foreign_key_errors"] = [
                dict(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()
            ]
        except sqlite3.Error:
            blockers.append("database_read_failed")
        finally:
            try:
                connection.close()
            except UnboundLocalError:
                pass
    else:
        blockers.append("database_missing")

    gates: dict[str, Any] = {
        "stage": None,
        "next_required_step": None,
        "base_package_sealed": False,
        "delivery_profile": None,
    }
    artifacts: dict[str, Any] = {"count": 0, "cv": [], "invalid": []}

    if not blockers:
        database = Database(db_path=db_path)
        try:
            try:
                projection = build_sqlite_application_projection(application_id, database)
            except (ApplicationNotFoundError, ValueError) as exc:
                blockers.append("application_not_in_sqlite")
                gates["error"] = str(exc)
            else:
                gates.update(
                    {
                        "stage": projection.stage.value,
                        "next_required_step": projection.next_required_step,
                        "base_package_sealed": projection.base_package_sealed,
                        "delivery_profile": projection.delivery_profile,
                        "fit_map_revision_id": projection.fit_map_revision_id,
                    }
                )
                repository = ArtifactRepository(database)
                all_artifacts = repository.list_for_application(application_id)
                artifacts["count"] = len(all_artifacts)
                for artifact in all_artifacts:
                    item = {"artifact_id": artifact.artifact_id, "kind": artifact.kind, "status": artifact.status}
                    if artifact.kind == "cv":
                        validation = repository.validate_path(artifact.artifact_id)
                        item["valid"] = validation.valid
                        item["reason"] = validation.reason
                        artifacts["cv"].append(item)
                    if item.get("valid") is False:
                        artifacts["invalid"].append(item)
                if not projection.base_package_sealed:
                    blockers.append("core_package_not_sealed")
                if artifacts["invalid"]:
                    blockers.append("artifact_provenance_invalid")
        finally:
            database.close()

    if database_checks["integrity"] != "ok" or database_checks["foreign_key_errors"]:
        blockers.append("database_integrity_failed")
    if mode == "live":
        blockers.append("live_canary_requires_explicit_deployment")
        warnings.append("live_mode_is_preflight_only_and_does_not_start_containers")

    rollback_checkpoint = {
        "verified": db_path.is_file(),
        "database_path": str(db_path),
        "source_mutation": False,
        "run_id": run_id,
    }
    return CanaryReport(
        status="passed" if not blockers else "blocked",
        run_id=run_id,
        application_id=application_id,
        bot_id=bot_id,
        mode=mode,
        gates=gates,
        artifacts=artifacts,
        database_checks=database_checks,
        rollback_checkpoint=rollback_checkpoint,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def write_report(report: CanaryReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
