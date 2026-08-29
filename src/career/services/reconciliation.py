"""Evidence-first migration and reconciliation of historical JSON state."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
    ApplicationResolutionError,
)
from career.services.persistence.gate_repository import GateRepository
from career.utils import sha256_file, sha256_text, utc_now_iso


LEGACY_KINDS = frozenset(
    {
        "identity",
        "job_description",
        "fit_map",
        "state",
        "workflow_state",
        "derived",
        "manifest",
        "request",
        "artifact_manifest",
    }
)


@dataclass(frozen=True)
class LegacyClassification:
    path: Path
    kind: str
    application_id: str
    bot_id: str
    source_hash: str
    payload: dict[str, Any]
    text: str | None = None


@dataclass(frozen=True)
class MigrationConflict:
    path: str
    reason: str
    application_id: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class MigrationReport:
    report_id: str
    status: str
    input_root: str
    sources: tuple[LegacyClassification, ...]
    conflicts: tuple[MigrationConflict, ...]
    applied_application_ids: tuple[str, ...] = ()
    blocked_application_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReconciliationReport:
    application_id: str
    status: str
    blockers: tuple[str, ...]
    applied_changes: int
    warnings: tuple[str, ...] = ()


class MigrationImporter:
    def __init__(self, database: Database, input_root: Path) -> None:
        self.database = database
        self.input_root = Path(input_root).resolve()
        self._reports: dict[str, MigrationReport] = {}

    def dry_run(
        self,
        paths: Iterable[Path] | None = None,
    ) -> MigrationReport:
        classifications: list[LegacyClassification] = []
        conflicts: list[MigrationConflict] = []
        candidates = list(paths) if paths is not None else _discover_paths(self.input_root)
        for path in sorted(Path(item).resolve() for item in candidates):
            classified, conflict = classify_legacy_record(path, self.input_root)
            if classified is not None:
                classifications.append(classified)
            if conflict is not None:
                conflicts.append(conflict)

        by_application: dict[str, list[LegacyClassification]] = {}
        for item in classifications:
            by_application.setdefault(item.application_id, []).append(item)
        for application_id, items in by_application.items():
            if not any(item.kind == "identity" for item in items):
                conflicts.append(
                    MigrationConflict(
                        path=str(items[0].path),
                        application_id=application_id,
                        reason="missing_identity",
                    )
                )
                continue
            identity_fingerprint = _fingerprint_from_items(items, "identity")
            fit_map_fingerprint = _fingerprint_from_items(items, "fit_map")
            if (
                identity_fingerprint
                and fit_map_fingerprint
                and identity_fingerprint != fit_map_fingerprint
            ):
                fit_map_item = next(item for item in items if item.kind == "fit_map")
                conflicts.append(
                    MigrationConflict(
                        path=str(fit_map_item.path),
                        application_id=application_id,
                        reason="fit_map_fingerprint_mismatch",
                        details={
                            "identity_fingerprint": identity_fingerprint,
                            "fit_map_fingerprint": fit_map_fingerprint,
                        },
                    )
                )

        report = MigrationReport(
            report_id=f"mig_{uuid4().hex}",
            status="dry_run",
            input_root=str(self.input_root),
            sources=tuple(classifications),
            conflicts=tuple(conflicts),
        )
        self._reports[report.report_id] = report
        self._persist_report(report)
        return report

    def apply(self, report_id: str) -> MigrationReport:
        report = self._reports.get(report_id) or self._load_report(report_id)
        if report.status in {"applied", "applied_with_conflicts"}:
            return report
        conflicts = list(report.conflicts)
        blocked_application_ids = {
            conflict.application_id
            for conflict in conflicts
            if conflict.application_id
        }
        if any(conflict.application_id is None for conflict in conflicts):
            return self._update_report_status(
                report,
                "blocked",
                conflicts=tuple(conflicts),
                blocked_application_ids=tuple(sorted(blocked_application_ids)),
            )
        for source in report.sources:
            if not source.path.is_file() or sha256_file(source.path) != source.source_hash:
                conflict = MigrationConflict(
                    path=str(source.path),
                    application_id=source.application_id,
                    reason="source_changed_after_dry_run",
                )
                conflicts.append(conflict)
                blocked_application_ids.add(source.application_id)

        self.database.migrate()
        grouped: dict[str, list[LegacyClassification]] = {}
        for source in report.sources:
            grouped.setdefault(source.application_id, []).append(source)
        applied_application_ids: list[str] = []
        for application_id, sources in grouped.items():
            if application_id in blocked_application_ids:
                continue
            try:
                self._apply_application(report, application_id, sources)
            except (ApplicationResolutionError, ValueError, KeyError, sqlite3.IntegrityError) as exc:
                conflicts.append(
                    MigrationConflict(
                        path=str(sources[0].path),
                        application_id=application_id,
                        reason=f"apply_error:{type(exc).__name__}",
                        details={"message": str(exc)},
                    )
                )
                blocked_application_ids.add(application_id)
                continue
            applied_application_ids.append(application_id)
        status = "applied_with_conflicts" if conflicts else "applied"
        return self._update_report_status(
            report,
            status,
            conflicts=tuple(conflicts),
            applied_application_ids=tuple(sorted(applied_application_ids)),
            blocked_application_ids=tuple(sorted(blocked_application_ids)),
        )

    def _apply_application(
        self,
        report: MigrationReport,
        application_id: str,
        sources: list[LegacyClassification],
    ) -> None:
        identity_item = next((item for item in sources if item.kind == "identity"), None)
        job_item = next((item for item in sources if item.kind == "job_description"), None)
        fit_map_item = next((item for item in sources if item.kind == "fit_map"), None)
        if identity_item is None:
            raise ValueError(f"legacy application {application_id} has no identity")
        identity = identity_item.payload
        company = str(identity.get("company") or "Empresa desconhecida")
        role = str(identity.get("role") or "Cargo desconhecido")
        notion_id = _optional_text(identity.get("notion_id"))
        fingerprint = _optional_text(identity.get("fingerprint"))
        source_type = str(identity.get("source_type") or "legacy_import")
        source_url = _optional_text(identity.get("source_url"))
        delivery_profile = "gupy_registration" if "gupy" in (source_url or "").lower() else "standard_cv"
        applications = ApplicationRepository(self.database)
        try:
            application = applications.resolve(application_id=application_id)
        except ApplicationResolutionError:
            if notion_id:
                try:
                    application = applications.resolve(notion_id=notion_id)
                except ApplicationResolutionError:
                    application = applications.create_application(
                        ApplicationIdentity(
                            application_id=application_id,
                            company=company,
                            role=role,
                            notion_id=notion_id,
                            fingerprint=fingerprint,
                            source_type=source_type,
                            source_url=source_url,
                            delivery_profile=delivery_profile,
                        )
                    )
            else:
                application = applications.create_application(
                    ApplicationIdentity(
                        application_id=application_id,
                        company=company,
                        role=role,
                        fingerprint=fingerprint,
                        source_type=source_type,
                        source_url=source_url,
                        delivery_profile=delivery_profile,
                    )
                )

        application_revision_id = _ensure_job_description(
            self.database,
            application.application_id,
            application,
            job_item,
            fingerprint,
        )
        if fit_map_item is not None and application_revision_id is not None:
            fit_map = dict(fit_map_item.payload)
            metadata = dict(fit_map.get("metadata") or {})
            metadata.setdefault("job_fingerprint", fingerprint)
            fit_map["metadata"] = metadata
            AnalysisRepository(self.database).create_revision(
                application.application_id,
                fit_map,
                source_hash=fit_map_item.source_hash,
                application_revision_id=application_revision_id,
            )
            analysis = AnalysisRepository(self.database).get_current(application.application_id)
            positioning_payload = _historical_positioning_payload(fit_map)
            if analysis.positioning is None and positioning_payload is not None:
                AnalysisRepository(self.database).create_positioning_revision(
                    application.application_id,
                    analysis.revision_id,
                    positioning_payload,
                )

        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                """
                UPDATE applications
                   SET job_description_path = COALESCE(?, job_description_path),
                       fit_map_path = COALESCE(?, fit_map_path),
                       updated_at = ?
                 WHERE id = ?
                """,
                (
                    str(job_item.path) if job_item is not None else None,
                    str(fit_map_item.path) if fit_map_item is not None else None,
                    utc_now_iso(),
                    application.application_id,
                ),
            )

        for source in sources:
            self._record_legacy_source(
                report.report_id,
                application.application_id,
                source,
            )
            if source.bot_id:
                app_dir = _application_directory(source.path)
                if app_dir is not None:
                    ApplicationRepository(self.database).record_location(
                        application.application_id,
                        source.bot_id,
                        app_dir,
                        source.source_hash if source.kind == "manifest" else None,
                    )

    def _record_legacy_source(
        self,
        report_id: str,
        application_id: str,
        source: LegacyClassification,
    ) -> None:
        now = utc_now_iso()
        payload = dict(source.payload)
        if source.text is not None:
            payload["text"] = source.text
        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO legacy_records
                    (record_id, migration_run_id, application_id, bot_id, kind,
                     path, source_hash, payload_json, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"legacy_{uuid4().hex}",
                    report_id,
                    application_id,
                    source.bot_id,
                    source.kind,
                    str(source.path),
                    source.source_hash,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    now,
                ),
            )

    def _persist_report(self, report: MigrationReport) -> None:
        self.database.migrate()
        now = utc_now_iso()
        serialized = _report_json(report)
        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                """
                INSERT INTO migration_runs
                    (run_id, status, input_root, report_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    report_json = excluded.report_json,
                    updated_at = excluded.updated_at
                """,
                (report.report_id, report.status, report.input_root, serialized, now, now),
            )
            for source in report.sources:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO migration_sources
                        (source_id, run_id, application_id, bot_id, kind, path,
                         source_hash, status, details_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"source_{uuid4().hex}",
                        report.report_id,
                        source.application_id,
                        source.bot_id,
                        source.kind,
                        str(source.path),
                        source.source_hash,
                        "classified",
                        json.dumps(source.payload, ensure_ascii=False, sort_keys=True),
                        now,
                    ),
                )
            for conflict in report.conflicts:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO migration_conflicts
                        (conflict_id, run_id, application_id, path, reason,
                         details_json, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'blocked', ?)
                    """,
                    (
                        f"conflict_{uuid4().hex}",
                        report.report_id,
                        conflict.application_id,
                        conflict.path,
                        conflict.reason,
                        json.dumps(conflict.details or {}, ensure_ascii=False, sort_keys=True),
                        now,
                    ),
                )

    def _load_report(self, report_id: str) -> MigrationReport:
        row = self.database.fetch_one(
            "SELECT report_json, status FROM migration_runs WHERE run_id = ?",
            (report_id,),
        )
        if row is None:
            raise ValueError(f"unknown migration report: {report_id}")
        report = _report_from_json(str(row["report_json"]))
        if str(row["status"]) in {"applied", "applied_with_conflicts"}:
            report = MigrationReport(
                report.report_id,
                str(row["status"]),
                report.input_root,
                report.sources,
                report.conflicts,
                report.applied_application_ids,
                report.blocked_application_ids,
            )
        self._reports[report.report_id] = report
        return report

    def _update_report_status(
        self,
        report: MigrationReport,
        status: str,
        *,
        conflicts: tuple[MigrationConflict, ...] | None = None,
        applied_application_ids: tuple[str, ...] | None = None,
        blocked_application_ids: tuple[str, ...] | None = None,
    ) -> MigrationReport:
        updated = MigrationReport(
            report.report_id,
            status,
            report.input_root,
            report.sources,
            conflicts if conflicts is not None else report.conflicts,
            applied_application_ids
            if applied_application_ids is not None
            else report.applied_application_ids,
            blocked_application_ids
            if blocked_application_ids is not None
            else report.blocked_application_ids,
        )
        self._reports[report.report_id] = updated
        self._persist_report(updated)
        return updated


class Reconciler:
    def __init__(self, database: Database, input_root: Path) -> None:
        self.database = database
        self.input_root = Path(input_root).resolve()

    def classify_legacy_record(self, path: Path) -> LegacyClassification | None:
        classified, _conflict = classify_legacy_record(path, self.input_root)
        return classified

    def reconcile(self, application_id: str, mode: str = "dry-run") -> ReconciliationReport:
        if mode not in {"dry-run", "apply"}:
            raise ValueError("mode must be dry-run or apply")
        applications = ApplicationRepository(self.database)
        application = applications.resolve(application_id=application_id)
        rows = self.database.fetch_all(
            "SELECT kind, source_hash, payload_json FROM legacy_records WHERE application_id = ?",
            (application.application_id,),
        )
        kinds = {str(row["kind"]) for row in rows}
        blockers: list[str] = []
        if "identity" not in kinds:
            blockers.append("missing_identity")
        if "job_description" not in kinds:
            blockers.append("missing_job_description")
        if "fit_map" not in kinds:
            blockers.append("missing_fit_map")
        warnings: list[str] = []
        try:
            revision_id = AnalysisRepository(self.database).get_current(application.application_id).revision_id
        except ValueError:
            revision_id = None
            blockers.append("missing_fit_map_revision")
        if revision_id is not None and not GateRepository(self.database).is_satisfied(
            application.application_id,
            "fit_map_validated",
            revision_id=revision_id,
        ):
            warnings.append("missing_verified_receipts")
        if blockers:
            return ReconciliationReport(
                application.application_id,
                "blocked_reconciliation",
                tuple(dict.fromkeys(blockers)),
                0,
                tuple(dict.fromkeys(warnings)),
            )
        if mode == "dry-run":
            return ReconciliationReport(
                application.application_id,
                "historical_unverified" if warnings else "ready",
                (),
                0,
                tuple(dict.fromkeys(warnings)),
            )
        now = utc_now_iso()
        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                "INSERT INTO workflow_events (application_id, event, fingerprint, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    application.application_id,
                    "legacy_reconciled",
                    application.fingerprint,
                    json.dumps(
                        {
                            "source": "phase5",
                            "verification_status": "historical_unverified"
                            if warnings
                            else "verified",
                        }
                    ),
                    now,
                ),
            )
        return ReconciliationReport(
            application.application_id,
            "historical_unverified" if warnings else "reconciled",
            (),
            1,
            tuple(dict.fromkeys(warnings)),
        )


def classify_legacy_record(path: Path, root: Path) -> tuple[LegacyClassification | None, MigrationConflict | None]:
    path = Path(path).resolve()
    try:
        relative = path.relative_to(Path(root).resolve())
    except ValueError:
        return None, MigrationConflict(str(path), "path_outside_input_root")
    parts = relative.parts
    if "applications_v2" not in parts:
        return None, None
    index = parts.index("applications_v2")
    if index + 1 >= len(parts):
        return None, None
    application_id = parts[index + 1]
    kind = _kind_for_path(parts, path)
    if kind is None:
        return None, None
    bot_id = "root"
    if "workspaces" in parts:
        workspace_index = parts.index("workspaces")
        if workspace_index + 1 < len(parts):
            bot_id = parts[workspace_index + 1]
    source_hash = sha256_file(path)
    payload: dict[str, Any] = {}
    text: str | None = None
    if path.suffix.lower() == ".json":
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return None, MigrationConflict(str(path), f"invalid_json:{type(exc).__name__}", application_id)
        if isinstance(loaded, dict):
            payload = loaded
        else:
            payload = {"value": loaded}
    else:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return None, MigrationConflict(str(path), f"unreadable_source:{type(exc).__name__}", application_id)
        payload = _job_metadata(text)
    return LegacyClassification(path, kind, application_id, bot_id, source_hash, payload, text), None


def _discover_paths(root: Path) -> list[Path]:
    """Discover only application trees, avoiding browser/node/cache forests."""
    application_roots: set[Path] = set()
    for candidate in (
        root / ".career-state" / "applications_v2",
        root / "app" / ".career-state" / "applications_v2",
    ):
        if candidate.is_dir():
            application_roots.add(candidate)
    workspaces = root / "workspaces"
    if workspaces.is_dir():
        for bot_dir in workspaces.iterdir():
            candidate = bot_dir / "state" / "applications_v2"
            if candidate.is_dir():
                application_roots.add(candidate)
    paths: list[Path] = []
    for application_root in sorted(application_roots):
        paths.extend(
            path
            for path in application_root.rglob("*")
            if path.is_file()
            and _kind_for_path(path.relative_to(root).parts, path) is not None
        )
    return paths


def _kind_for_path(parts: tuple[str, ...], path: Path) -> str | None:
    name = path.name
    if name == "identity.json":
        return "identity"
    if name == "job_description.md":
        return "job_description"
    if name == "fit_map.json" and "applications_v2" in parts:
        return "fit_map"
    if name == "state.json" and "applications_v2" in parts:
        return "state"
    if name == "workflow_state.json" and "applications_v2" in parts:
        return "workflow_state"
    if name in {"manifest.json", "derived_manifest.json"} and "applications_v2" in parts:
        return "manifest"
    if name == "artifacts_manifest.json":
        return "artifact_manifest"
    if "requests" in parts and path.suffix.lower() in {".json", ".md"}:
        return "request"
    if "derived" in parts and path.suffix.lower() == ".json":
        return "derived"
    return None


def _fingerprint_from_items(items: list[LegacyClassification], kind: str) -> str | None:
    for item in items:
        if item.kind != kind:
            continue
        metadata = item.payload.get("metadata") if isinstance(item.payload.get("metadata"), dict) else {}
        value = item.payload.get("fingerprint") or metadata.get("job_fingerprint")
        if value:
            return str(value)
    return None


def _job_metadata(text: str) -> dict[str, Any]:
    heading = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), "")
    role, separator, company = heading.partition(" — ")
    return {"role": role.strip() if separator else "", "company": company.strip() if separator else "", "content_hash": sha256_text(text)}


def _historical_positioning_payload(fit_map: dict[str, Any]) -> dict[str, Any] | None:
    positioning = fit_map.get("positioning")
    if isinstance(positioning, dict) and (
        isinstance(positioning.get("stories"), list)
        or isinstance(positioning.get("principles"), list)
    ):
        return positioning
    stories = fit_map.get("stories")
    principles = fit_map.get("principles")
    if isinstance(stories, list) or isinstance(principles, list):
        return {
            "stories": stories if isinstance(stories, list) else [],
            "principles": principles if isinstance(principles, list) else [],
        }
    return None


def _application_directory(path: Path) -> Path | None:
    parts = path.parts
    if "applications_v2" not in parts:
        return None
    index = parts.index("applications_v2")
    if index + 1 >= len(parts):
        return None
    return Path(*parts[: index + 2])


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _ensure_job_description(
    database: Database,
    application_id: str,
    application,
    job_item: LegacyClassification | None,
    identity_fingerprint: str | None,
) -> str | None:
    if job_item is None or job_item.text is None:
        return None
    content = job_item.text
    content_hash = sha256_text(content)
    if identity_fingerprint and len(identity_fingerprint) == 64 and identity_fingerprint != content_hash:
        raise ValueError(f"job description fingerprint mismatch for {application_id}")
    legacy_key = sha256_text(application_id)[:12]
    description_id = f"desc_legacy_{legacy_key}_{content_hash[:24]}"
    now = utc_now_iso()
    with database.transaction(immediate=True) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO job_descriptions
                (description_id, application_id, source_id, language, content, content_hash, created_at)
            VALUES (?, ?, NULL, 'pt-BR', ?, ?, ?)
            """,
            (description_id, application_id, content, content_hash, now),
        )
        current = conn.execute(
            """
            SELECT revision_id, payload_json FROM application_revisions
             WHERE application_id = ?
             ORDER BY created_at DESC, revision_id DESC LIMIT 1
            """,
            (application_id,),
        ).fetchone()
        if current is None:
            revision_id = f"rev_legacy_{legacy_key}_{content_hash[:24]}"
            conn.execute(
                """
                INSERT INTO application_revisions
                    (revision_id, application_id, revision_kind, fingerprint, source_hash, payload_json, created_at)
                VALUES (?, ?, 'legacy_import', ?, ?, ?, ?)
                """,
                (revision_id, application_id, content_hash, content_hash, json.dumps({"job_description_id": description_id}), now),
            )
            return revision_id
        payload = json.loads(str(current["payload_json"] or "{}"))
        if not payload.get("job_description_id"):
            payload["job_description_id"] = description_id
            conn.execute(
                "UPDATE application_revisions SET payload_json = ?, fingerprint = ?, source_hash = ? WHERE revision_id = ?",
                (json.dumps(payload, sort_keys=True), content_hash, content_hash, str(current["revision_id"])),
            )
        return str(current["revision_id"])


def _report_json(report: MigrationReport) -> str:
    payload = {
        "report_id": report.report_id,
        "status": report.status,
        "input_root": report.input_root,
        "applied_application_ids": list(report.applied_application_ids),
        "blocked_application_ids": list(report.blocked_application_ids),
        "sources": [
            {
                **asdict(item),
                "path": str(item.path),
            }
            for item in report.sources
        ],
        "conflicts": [asdict(item) for item in report.conflicts],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _report_from_json(raw: str) -> MigrationReport:
    payload = json.loads(raw)
    sources = tuple(
        LegacyClassification(
            Path(item["path"]),
            item["kind"],
            item["application_id"],
            item["bot_id"],
            item["source_hash"],
            dict(item.get("payload") or {}),
            item.get("text"),
        )
        for item in payload.get("sources", [])
    )
    conflicts = tuple(MigrationConflict(**item) for item in payload.get("conflicts", []))
    return MigrationReport(
        payload["report_id"],
        payload["status"],
        payload["input_root"],
        sources,
        conflicts,
        tuple(payload.get("applied_application_ids") or ()),
        tuple(payload.get("blocked_application_ids") or ()),
    )
