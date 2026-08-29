"""Strict, read-only verification of runtime unification invariants."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from career.paths import ROOT


@dataclass(frozen=True)
class VerificationReport:
    status: str
    checks: tuple[dict[str, Any], ...]
    blockers: tuple[dict[str, Any], ...]
    warnings: tuple[dict[str, Any], ...]
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": list(self.checks),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "evidence": self.evidence,
        }


def verify_runtime(
    root: Path | None = None,
    strict: bool = True,
    *,
    database_path: Path | None = None,
) -> VerificationReport:
    """Run independent checks without changing source files or SQLite."""

    resolved_root = Path(root or ROOT).resolve()
    checks: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {"root": str(resolved_root), "strict": strict}

    def record(
        code: str,
        passed: bool,
        *,
        detail: str,
        evidence_item: Any = None,
        warning: bool = False,
    ) -> None:
        check = {"code": code, "status": "passed" if passed else ("warning" if warning else "blocked"), "detail": detail}
        if evidence_item is not None:
            check["evidence"] = evidence_item
            evidence[code] = evidence_item
        checks.append(check)
        if not passed:
            (warnings if warning else blockers).append(check)

    compose_payloads = _load_compose_payloads(resolved_root)
    runtime_ok, runtime_evidence, runtime_detail = _check_runtime_source(compose_payloads)
    record("RUNTIME_SOURCE", runtime_ok, detail=runtime_detail, evidence_item=runtime_evidence)

    db_path = Path(database_path or (resolved_root / "control-plane" / "career.db")).resolve()
    db_result = _check_database(db_path)
    record("DB_SCHEMA", db_result["passed"], detail=db_result["detail"], evidence_item=db_result["evidence"])
    if db_result["passed"]:
        gate_result = _check_gate_provenance(db_path)
        record("GATE_PROVENANCE", gate_result["passed"], detail=gate_result["detail"], evidence_item=gate_result["evidence"])
        artifact_result = _check_artifact_provenance(db_path)
        record("ARTIFACT_PROVENANCE", artifact_result["passed"], detail=artifact_result["detail"], evidence_item=artifact_result["evidence"])
        cross_bot_result = _check_cross_bot_catalog(db_path)
        record("CROSS_BOT", cross_bot_result["passed"], detail=cross_bot_result["detail"], evidence_item=cross_bot_result["evidence"], warning=True)
    else:
        for code in ("GATE_PROVENANCE", "ARTIFACT_PROVENANCE", "CROSS_BOT"):
            record(code, False, detail="not evaluated because DB_SCHEMA is blocked")

    process_ok, process_evidence = _check_process_scope(resolved_root)
    record("PROCESS_SCOPE", process_ok, detail="active Hermes profiles use the canonical workspace" if process_ok else "active Hermes profile points outside the canonical workspace", evidence_item=process_evidence)

    json_ok, json_evidence = _check_json_canonical_write(resolved_root)
    record("JSON_CANONICAL_WRITE", json_ok, detail="canonical skills do not use global JSON synchronization as authority" if json_ok else "canonical skill still contains a forbidden global JSON synchronization path", evidence_item=json_evidence)

    rollback_ok, rollback_evidence = _check_rollback(resolved_root)
    record("ROLLBACK", rollback_ok, detail="backup and rollback evidence paths are present" if rollback_ok else "backup/rollback evidence is incomplete", evidence_item=rollback_evidence)

    return VerificationReport(
        status="passed" if not blockers else "blocked",
        checks=tuple(checks),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        evidence=evidence,
    )


def _load_compose_payloads(root: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in (root / "compose.yaml", root / "app" / "deploy" / "hermes" / "compose.yaml"):
        if not path.is_file():
            continue
        try:
            payloads.append(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        except (OSError, yaml.YAMLError):
            payloads.append({"__invalid_path__": str(path)})
    return payloads


def _check_runtime_source(payloads: list[dict[str, Any]]) -> tuple[bool, dict[str, Any], str]:
    if len(payloads) < 2:
        return False, {"compose_files": len(payloads)}, "both canonical and reference Compose files are required"
    services_checked = 0
    failures: list[str] = []
    for payload in payloads:
        services = payload.get("services") if isinstance(payload, dict) else None
        if not isinstance(services, dict):
            failures.append("invalid_compose")
            continue
        for bot_id in ("vagas_bot_01", "vagas_bot_02"):
            service = services.get(bot_id) or {}
            volumes = {str(item) for item in service.get("volumes", [])}
            if "/opt/agent-projects/candidaturas:/workspace/candidaturas:ro" not in volumes:
                failures.append(f"{bot_id}:canonical_root_mount")
            if any("/opt/agent-projects/candidaturas/app" in item for item in volumes):
                failures.append(f"{bot_id}:app_mount")
            if "/opt/agent-projects/candidaturas/control-plane:/workspace/candidaturas/.career-control:rw" not in volumes:
                failures.append(f"{bot_id}:control_plane_mount")
            if service.get("working_dir") != "/workspace/candidaturas":
                failures.append(f"{bot_id}:working_dir")
            services_checked += 1
    evidence = {"compose_files": len(payloads), "services_checked": services_checked, "failures": failures}
    return not failures, evidence, "canonical root and isolated overlays are declared" if not failures else "Compose contains a non-canonical runtime mount"


def _check_database(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"passed": False, "detail": "canonical control database is missing", "evidence": {"path": str(path)}}
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = [dict(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()]
        versions = [str(row[0]) for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        required = "009_historical_reconciliation.sql"
        passed = integrity == "ok" and not foreign_keys and required in versions
        detail = "SQLite integrity and migration ledger are valid" if passed else "SQLite schema is incomplete or has integrity violations"
        return {"passed": passed, "detail": detail, "evidence": {"path": str(path), "integrity": integrity, "foreign_key_errors": foreign_keys, "migration_versions": versions}}
    except (sqlite3.Error, OSError) as exc:
        return {"passed": False, "detail": f"cannot inspect SQLite: {type(exc).__name__}", "evidence": {"path": str(path), "error": str(exc)}}
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def _check_gate_provenance(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        columns = _table_columns(connection, "validation_receipts")
        required = {"application_id", "gate", "input_hash", "output_hash", "application_fingerprint", "revision_id"}
        missing = sorted(required - columns)
        orphan_count = 0
        if not missing:
            orphan_count = int(connection.execute("SELECT COUNT(*) FROM validation_receipts WHERE application_id IS NULL OR application_fingerprint IS NULL").fetchone()[0])
        passed = not missing and orphan_count == 0
        return {"passed": passed, "detail": "gate receipts are application- and revision-scoped" if passed else "gate receipts lack required provenance", "evidence": {"missing_columns": missing, "orphan_receipts": orphan_count}}
    finally:
        connection.close()


def _check_artifact_provenance(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        columns = _table_columns(connection, "artifact_versions")
        required = {"application_id", "source_revision_id", "content_hash", "status"}
        missing = sorted(required - columns)
        invalid_count = 0
        if not missing:
            invalid_count = int(connection.execute("SELECT COUNT(*) FROM artifact_versions WHERE application_id IS NULL OR source_revision_id IS NULL OR content_hash IS NULL OR content_hash = ''").fetchone()[0])
        passed = not missing and invalid_count == 0
        return {"passed": passed, "detail": "artifacts are bound to source revisions and content hashes" if passed else "artifact provenance is incomplete", "evidence": {"missing_columns": missing, "invalid_artifacts": invalid_count}}
    finally:
        connection.close()


def _check_cross_bot_catalog(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='application_locations'").fetchone() is not None
        count = int(connection.execute("SELECT COUNT(*) FROM application_locations").fetchone()[0]) if exists else 0
        return {"passed": exists, "detail": "cross-bot application location catalog exists" if exists else "application location catalog is missing", "evidence": {"table_present": exists, "locations": count}}
    finally:
        connection.close()


def _check_process_scope(root: Path) -> tuple[bool, dict[str, Any]]:
    paths = [root / "hermes" / "vagas_bot_01" / "config.yaml", root / "hermes" / "vagas_bot_02" / "config.yaml"]
    missing = [str(path) for path in paths if not path.is_file()]
    wrong = [str(path) for path in paths if path.is_file() and "cwd: /workspace/candidaturas" not in path.read_text(encoding="utf-8")]
    evidence = {"profiles": [str(path) for path in paths], "missing": missing, "wrong_workspace": wrong}
    return not missing and not wrong, evidence


def _check_json_canonical_write(root: Path) -> tuple[bool, dict[str, Any]]:
    skill = root / ".agents" / "skills" / "processe-a-vaga" / "SKILL.md"
    if not skill.is_file():
        return False, {"skill": str(skill), "reason": "missing canonical skill"}
    content = skill.read_text(encoding="utf-8").lower()
    forbidden = [
        term
        for term in (
            "sincronizar estado global",
            "write_text(json.dumps(g",
            'g["active_job"]',
        )
        if term in content
    ]
    return not forbidden, {"skill": str(skill), "forbidden_terms": forbidden}


def _check_rollback(root: Path) -> tuple[bool, dict[str, Any]]:
    required = [root / "scripts" / "backup_persistence.py", root / "tests" / "test_persistence_backup.py", root / ".superpowers" / "sdd" / "2026-08-18-runtime-unification" / "progress.md"]
    missing = [str(path) for path in required if not path.is_file()]
    return not missing, {"required_paths": [str(path) for path in required], "missing": missing}


def write_report(report: VerificationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
