from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from career.services.database import Database
from career.utils import sha256_file, utc_now_iso


def _validate_application_id(application_id: str) -> str:
    if (
        not isinstance(application_id, str)
        or not application_id
        or application_id in {".", ".."}
        or "/" in application_id
        or "\\" in application_id
        or "\x00" in application_id
        or Path(application_id).is_absolute()
    ):
        raise ValueError("application_id must be a non-empty relative path segment")
    return application_id


class ApplicationResolutionError(ValueError):
    """Base error for explicit application resolution failures."""


class ApplicationNotFoundError(ApplicationResolutionError):
    """Raised when no application matches the explicit selector(s)."""


class AmbiguousApplicationError(ApplicationResolutionError):
    """Raised when an explicit selector matches more than one application."""


@dataclass(frozen=True)
class ApplicationIdentity:
    application_id: str
    company: str
    role: str
    notion_id: str | None = None
    fingerprint: str | None = None
    source_type: str = "paste"
    source_url: str | None = None
    stage: str = "analyze_pending"
    funil_stage: str = "Fila Agente"
    cv_language: str = "pt"
    status: str = "active"
    delivery_profile: str = "standard_cv"
    aliases: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ApplicationRecord:
    application_id: str
    company: str
    role: str
    notion_id: str | None
    fingerprint: str | None
    source_type: str
    source_url: str | None
    stage: str
    funil_stage: str
    score: float | None
    cv_language: str
    status: str
    delivery_profile: str
    created_at: str
    updated_at: str
    job_description_path: str | None
    fit_map_path: str | None
    cv_path: str | None
    aliases: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ApplicationProjection:
    application_id: str
    company: str
    role: str
    notion_id: str | None
    fingerprint: str | None
    stage: str
    funil_stage: str
    status: str
    updated_at: str


@dataclass(frozen=True)
class JobDescriptionRecord:
    description_id: str
    application_id: str
    source_id: str | None
    language: str | None
    content: str
    content_hash: str
    created_at: str


@dataclass(frozen=True)
class ApplicationRevisionRecord:
    revision_id: str
    application_id: str
    revision_kind: str
    fingerprint: str | None
    source_hash: str | None
    payload: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class ReindexReport:
    locations: tuple[dict[str, str], ...]
    conflicts: tuple[dict[str, str], ...]


class ApplicationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database
        self._schema_ready = False

    def create_application(self, identity: ApplicationIdentity) -> ApplicationRecord:
        self._ensure_schema()
        application_id = _validate_application_id(identity.application_id)
        now = utc_now_iso()
        aliases = dict(identity.aliases)
        if identity.notion_id:
            aliases.setdefault("notion_id", str(identity.notion_id))
        with self.database.transaction(immediate=True) as conn:
            existing = conn.execute(
                "SELECT created_at FROM applications WHERE id = ?",
                (application_id,),
            ).fetchone()
            created_at = (
                str(existing["created_at"])
                if existing is not None and existing["created_at"]
                else now
            )
            conn.execute(
                """INSERT INTO applications
                   (id, notion_id, company, role, source_type, source_url,
                    stage, funil_stage, cv_language, status, delivery_profile,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     notion_id = COALESCE(excluded.notion_id, applications.notion_id),
                     company = excluded.company,
                     role = excluded.role,
                     source_type = excluded.source_type,
                     source_url = COALESCE(excluded.source_url, applications.source_url),
                     delivery_profile = excluded.delivery_profile,
                     updated_at = excluded.updated_at""",
                (
                    application_id,
                    str(identity.notion_id) if identity.notion_id else None,
                    identity.company,
                    identity.role,
                    identity.source_type,
                    identity.source_url,
                    identity.stage,
                    identity.funil_stage,
                    identity.cv_language,
                    identity.status,
                    identity.delivery_profile,
                    created_at,
                    now,
                ),
            )
            for alias_type, alias_value in aliases.items():
                self._upsert_alias(
                    conn,
                    application_id=application_id,
                    alias_type=alias_type,
                    alias_value=str(alias_value),
                    created_at=now,
                )
            if identity.fingerprint:
                conn.execute(
                    """INSERT OR IGNORE INTO application_revisions
                       (revision_id, application_id, revision_kind, fingerprint, source_hash, payload_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"rev_{uuid4().hex}",
                        application_id,
                        "intake_identity",
                        identity.fingerprint,
                        identity.fingerprint,
                        "{}",
                        now,
                    ),
                )
        return self.resolve(application_id=application_id)

    def resolve(
        self,
        *,
        application_id: str | None = None,
        notion_id: str | None = None,
        fingerprint: str | None = None,
        company: str | None = None,
        role: str | None = None,
    ) -> ApplicationRecord:
        self._ensure_schema()
        selectors: list[tuple[str, set[str]]] = []
        application_value = str(application_id or "").strip()
        notion_value = str(notion_id or "").strip()
        fingerprint_value = str(fingerprint or "").strip()
        company_value = str(company or "").strip()
        role_value = str(role or "").strip()

        if application_value:
            selectors.append(
                (
                    "application_id",
                    {self._candidate_for_application_id(application_value)},
                )
            )
        if notion_value:
            selectors.append(("notion_id", self._candidate_ids_for_notion_id(notion_value)))
        if fingerprint_value:
            selectors.append(
                ("fingerprint", self._candidate_ids_for_fingerprint(fingerprint_value))
            )
        if company_value or role_value:
            if not (company_value and role_value):
                raise ApplicationNotFoundError(
                    "resolver requires company and role together when using company/role resolution"
                )
            selectors.append(
                (
                    "company/role",
                    self._candidate_ids_for_company_role(company_value, role_value),
                )
            )
        if not selectors:
            raise ApplicationNotFoundError(
                "resolver requires application_id, notion_id, fingerprint, or company and role"
            )

        candidate_ids: set[str] | None = None
        for label, ids in selectors:
            if not ids:
                raise ApplicationNotFoundError(
                    f"no application matched {label}"
                )
            candidate_ids = set(ids) if candidate_ids is None else candidate_ids & ids

        if not candidate_ids:
            raise ApplicationNotFoundError("no application matched the provided selectors")
        if len(candidate_ids) > 1:
            labels = {label for label, _ids in selectors}
            if labels == {"company/role"}:
                raise AmbiguousApplicationError(
                    "company/role matched multiple applications"
                )
            raise AmbiguousApplicationError(
                "provided selectors matched multiple applications"
            )
        return self._load_record(next(iter(candidate_ids)))

    def resolve_by_alias(self, *, alias_type: str, alias_value: str) -> ApplicationRecord:
        """Resolve one application through an authoritative alias."""
        self._ensure_schema()
        normalized_type = str(alias_type or "").strip()
        normalized_value = str(alias_value or "").strip()
        if not normalized_type or not normalized_value:
            raise ApplicationNotFoundError(
                "alias resolution requires alias_type and alias_value"
            )
        rows = self.database.fetch_all(
            """SELECT DISTINCT application_id
               FROM application_aliases
               WHERE alias_type = ? AND alias_value = ?""",
            (normalized_type, normalized_value),
        )
        candidate_ids = {str(row["application_id"]) for row in rows}
        if not candidate_ids:
            raise ApplicationNotFoundError(
                f"no application matched alias {normalized_type}={normalized_value}"
            )
        if len(candidate_ids) > 1:
            raise AmbiguousApplicationError(
                f"alias matched multiple applications: {normalized_type}={normalized_value}"
            )
        return self._load_record(next(iter(candidate_ids)))

    def update_projection(self, application_id: str) -> ApplicationProjection:
        record = self.resolve(application_id=application_id)
        return ApplicationProjection(
            application_id=record.application_id,
            company=record.company,
            role=record.role,
            notion_id=record.notion_id,
            fingerprint=record.fingerprint,
            stage=record.stage,
            funil_stage=record.funil_stage,
            status=record.status,
            updated_at=record.updated_at,
        )

    def get_latest_job_description(self, application_id: str) -> JobDescriptionRecord:
        """Load the authoritative intake description for an explicit application."""
        self.resolve(application_id=application_id)
        row = self.database.fetch_one(
            """SELECT description_id, application_id, source_id, language, content,
                      content_hash, created_at
               FROM job_descriptions
               WHERE application_id = ?
               ORDER BY created_at DESC, description_id DESC
               LIMIT 1""",
            (application_id,),
        )
        if row is None:
            raise ValueError(f"no job description found for {application_id}")
        return self._job_description_from_row(row)

    def get_application_revision(
        self, application_id: str, revision_id: str
    ) -> ApplicationRevisionRecord:
        """Load one immutable application revision within an explicit scope."""
        self.resolve(application_id=application_id)
        row = self.database.fetch_one(
            """SELECT revision_id, application_id, revision_kind, fingerprint,
                      source_hash, payload_json, created_at
               FROM application_revisions
               WHERE revision_id = ? AND application_id = ?""",
            (revision_id, application_id),
        )
        if row is None:
            raise ValueError("application revision must belong to the same application")
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError("application revision payload is invalid") from exc
        if not isinstance(payload, dict):
            raise ValueError("application revision payload must be an object")
        return ApplicationRevisionRecord(
            revision_id=str(row["revision_id"]),
            application_id=str(row["application_id"]),
            revision_kind=str(row["revision_kind"]),
            fingerprint=str(row["fingerprint"]) if row["fingerprint"] else None,
            source_hash=str(row["source_hash"]) if row["source_hash"] else None,
            payload=payload,
            created_at=str(row["created_at"]),
        )

    def get_job_description_for_application_revision(
        self, application_id: str, revision_id: str
    ) -> JobDescriptionRecord:
        """Load only the description explicitly linked by an application revision."""
        revision = self.get_application_revision(application_id, revision_id)
        description_id = str(revision.payload.get("job_description_id") or "").strip()
        if not description_id:
            raise ValueError(
                "application revision does not prove a linked job description"
            )
        row = self.database.fetch_one(
            """SELECT description_id, application_id, source_id, language, content,
                      content_hash, created_at
               FROM job_descriptions
               WHERE description_id = ? AND application_id = ?""",
            (description_id, application_id),
        )
        if row is None:
            raise ValueError(
                "application revision references a missing job description"
            )
        return self._job_description_from_row(row)

    def get_current_revision_id(self, application_id: str) -> str | None:
        """Return the latest canonical application revision without consulting JSON."""
        self.resolve(application_id=application_id)
        row = self.database.fetch_one(
            """SELECT revision_id FROM application_revisions
               WHERE application_id = ?
               ORDER BY created_at DESC, revision_id DESC
               LIMIT 1""",
            (application_id,),
        )
        return str(row["revision_id"]) if row is not None else None

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        self.database.migrate()
        self._schema_ready = True

    def ensure_schema(self) -> None:
        self._ensure_schema()

    def record_location(
        self,
        application_id: str,
        bot_id: str,
        location_path: str | Path,
        manifest_hash: str | None = None,
    ) -> None:
        """Register one physical bot location without duplicating identity."""
        self._ensure_schema()
        application = self.resolve(application_id=application_id)
        bot_id = str(bot_id or "").strip()
        location = str(Path(location_path).resolve())
        if not bot_id:
            raise ValueError("bot_id is required")
        now = utc_now_iso()
        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                """
                INSERT INTO application_locations
                    (location_id, application_id, bot_id, location_path,
                     manifest_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(application_id, bot_id, location_path) DO UPDATE SET
                    manifest_hash = COALESCE(excluded.manifest_hash, application_locations.manifest_hash)
                """,
                (
                    f"loc_{uuid4().hex}",
                    application.application_id,
                    bot_id,
                    location,
                    manifest_hash,
                    now,
                ),
            )

    def list_by_bot(self, bot_id: str | None = None) -> list[ApplicationRecord]:
        """Return canonical applications represented in one or more bot locations."""
        self._ensure_schema()
        if bot_id is None:
            rows = self.database.fetch_all(
                """
                SELECT DISTINCT application_id
                  FROM application_locations
                 ORDER BY application_id
                """
            )
        else:
            rows = self.database.fetch_all(
                """
                SELECT DISTINCT application_id
                  FROM application_locations
                 WHERE bot_id = ?
                 ORDER BY application_id
                """,
                (str(bot_id),),
            )
        return [self.resolve(application_id=str(row["application_id"])) for row in rows]

    def reindex_from_manifests(self, root: Path | None = None) -> ReindexReport:
        """Index application locations from manifests without importing gates."""
        self._ensure_schema()
        search_root = Path(root or self.database.db_path.parent.parent).resolve()
        locations: list[dict[str, str]] = []
        conflicts: list[dict[str, str]] = []
        manifest_paths = sorted(
            {
                *search_root.rglob("manifest.json"),
                *search_root.rglob("derived_manifest.json"),
            }
        )
        for manifest_path in manifest_paths:
            if not manifest_path.is_file() or "applications_v2" not in manifest_path.parts:
                continue
            index = manifest_path.parts.index("applications_v2")
            if index + 1 >= len(manifest_path.parts):
                continue
            path_application_id = manifest_path.parts[index + 1]
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                conflicts.append({"path": str(manifest_path), "reason": f"invalid_manifest:{type(exc).__name__}"})
                continue
            application_id = str(payload.get("application_id") or path_application_id).strip()
            bot_id = "root"
            if "workspaces" in manifest_path.parts:
                workspace_index = manifest_path.parts.index("workspaces")
                if workspace_index + 1 < len(manifest_path.parts):
                    bot_id = manifest_path.parts[workspace_index + 1]
            try:
                application = self.resolve(application_id=application_id)
            except ApplicationResolutionError:
                conflicts.append({"path": str(manifest_path), "reason": "unknown_application", "application_id": application_id})
                continue
            manifest_fingerprint = str(payload.get("fingerprint") or "").strip()
            if manifest_fingerprint and application.fingerprint and manifest_fingerprint != application.fingerprint:
                conflicts.append({"path": str(manifest_path), "reason": "fingerprint_mismatch", "application_id": application.application_id})
                continue
            app_dir = manifest_path.parent.parent if manifest_path.parent.name == "derived" else manifest_path.parent
            manifest_hash = sha256_file(manifest_path)
            self.record_location(application.application_id, bot_id, app_dir, manifest_hash)
            locations.append(
                {
                    "application_id": application.application_id,
                    "bot_id": bot_id,
                    "location_path": str(app_dir.resolve()),
                }
            )
        return ReindexReport(tuple(locations), tuple(conflicts))

    def _candidate_for_application_id(self, application_id: str) -> str:
        value = _validate_application_id(application_id)
        row = self.database.fetch_one("SELECT id FROM applications WHERE id = ?", (value,))
        if row is None:
            raise ApplicationNotFoundError(f"no application matched application_id={value}")
        return value

    def _candidate_ids_for_notion_id(self, notion_id: str) -> set[str]:
        rows = self.database.fetch_all(
            """SELECT DISTINCT application_id FROM application_aliases
               WHERE alias_type = ? AND alias_value = ?
               UNION
               SELECT DISTINCT id AS application_id FROM applications
               WHERE notion_id = ?""",
            ("notion_id", notion_id, notion_id),
        )
        return {str(row["application_id"]) for row in rows}

    def _candidate_ids_for_fingerprint(self, fingerprint: str) -> set[str]:
        rows = self.database.fetch_all(
            """SELECT DISTINCT application_id FROM application_revisions
               WHERE fingerprint = ?
               UNION
               SELECT DISTINCT application_id FROM job_sources
               WHERE fingerprint = ?""",
            (fingerprint, fingerprint),
        )
        return {str(row["application_id"]) for row in rows}

    def _candidate_ids_for_company_role(self, company: str, role: str) -> set[str]:
        rows = self.database.fetch_all(
            "SELECT id AS application_id FROM applications WHERE company = ? AND role = ?",
            (company, role),
        )
        return {str(row["application_id"]) for row in rows}

    def _load_record(self, application_id: str) -> ApplicationRecord:
        row = self.database.fetch_one(
            """SELECT id, notion_id, company, role, source_type, source_url, stage,
                      funil_stage, score, cv_language, status, delivery_profile,
                      created_at, updated_at,
                      job_description_path, fit_map_path, cv_path
               FROM applications WHERE id = ?""",
            (application_id,),
        )
        if row is None:
            raise ApplicationNotFoundError(
                f"no application matched application_id={application_id}"
            )
        aliases = self._aliases_for(application_id)
        notion_id = str(row["notion_id"]) if row["notion_id"] else aliases.get("notion_id")
        fingerprint = self._latest_fingerprint_for(application_id)
        return ApplicationRecord(
            application_id=str(row["id"]),
            company=str(row["company"]),
            role=str(row["role"]),
            notion_id=notion_id,
            fingerprint=fingerprint,
            source_type=str(row["source_type"] or "paste"),
            source_url=str(row["source_url"]) if row["source_url"] else None,
            stage=str(row["stage"] or "analyze_pending"),
            funil_stage=str(row["funil_stage"] or "Fila Agente"),
            score=float(row["score"]) if row["score"] is not None else None,
            cv_language=str(row["cv_language"] or "pt"),
            status=str(row["status"] or "active"),
            delivery_profile=str(row["delivery_profile"] or "standard_cv"),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            job_description_path=str(row["job_description_path"])
            if row["job_description_path"]
            else None,
            fit_map_path=str(row["fit_map_path"]) if row["fit_map_path"] else None,
            cv_path=str(row["cv_path"]) if row["cv_path"] else None,
            aliases=aliases,
        )

    @staticmethod
    def _job_description_from_row(row: sqlite3.Row | dict[str, Any]) -> JobDescriptionRecord:
        return JobDescriptionRecord(
            description_id=str(row["description_id"]),
            application_id=str(row["application_id"]),
            source_id=str(row["source_id"]) if row["source_id"] else None,
            language=str(row["language"]) if row["language"] else None,
            content=str(row["content"]),
            content_hash=str(row["content_hash"]),
            created_at=str(row["created_at"]),
        )

    def _aliases_for(self, application_id: str) -> dict[str, str]:
        rows = self.database.fetch_all(
            """SELECT alias_type, alias_value
               FROM application_aliases
               WHERE application_id = ?
               ORDER BY is_primary DESC, alias_id ASC""",
            (application_id,),
        )
        aliases: dict[str, str] = {}
        for row in rows:
            aliases.setdefault(str(row["alias_type"]), str(row["alias_value"]))
        return aliases

    def _latest_fingerprint_for(self, application_id: str) -> str | None:
        row = self.database.fetch_one(
            """SELECT fingerprint FROM application_revisions
               WHERE application_id = ? AND fingerprint IS NOT NULL AND fingerprint != ''
               ORDER BY created_at DESC, revision_id DESC
               LIMIT 1""",
            (application_id,),
        )
        if row is not None and row.get("fingerprint"):
            return str(row["fingerprint"])
        row = self.database.fetch_one(
            """SELECT fingerprint FROM job_sources
               WHERE application_id = ? AND fingerprint IS NOT NULL AND fingerprint != ''
               ORDER BY created_at DESC, source_id DESC
               LIMIT 1""",
            (application_id,),
        )
        if row is not None and row.get("fingerprint"):
            return str(row["fingerprint"])
        return None

    @staticmethod
    def _upsert_alias(
        conn: sqlite3.Connection,
        *,
        application_id: str,
        alias_type: str,
        alias_value: str,
        created_at: str,
    ) -> None:
        existing = conn.execute(
            """SELECT application_id FROM application_aliases
               WHERE alias_type = ? AND alias_value = ?""",
            (alias_type, alias_value),
        ).fetchone()
        if existing is not None and str(existing["application_id"]) != application_id:
            raise ApplicationResolutionError(
                f"alias {alias_type}={alias_value} already belongs to {existing['application_id']}"
            )
        try:
            conn.execute(
                """INSERT INTO application_aliases
                   (application_id, alias_type, alias_value, is_primary, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(alias_type, alias_value) DO UPDATE SET
                     is_primary = excluded.is_primary""",
                (application_id, alias_type, alias_value, 1, created_at),
            )
        except sqlite3.IntegrityError as exc:
            raise ApplicationResolutionError(
                f"failed to persist alias {alias_type}={alias_value}"
            ) from exc
