from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from career.paths import CAREER_STATE, ROOT
from career.services.database import Database, RuntimePersistenceMode
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationNotFoundError,
    ApplicationRecord,
    ApplicationRepository,
)
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.services.session_memory import SessionMemoryService
from career.utils import read_json, utc_now_iso, write_json, write_text


APPLICATIONS_DIR = CAREER_STATE / "applications_v2"
SESSION_REGISTRY = CAREER_STATE / "session_registry.json"
ALIAS_INDEX = CAREER_STATE / "application_alias_index.json"
SESSION_APPLICATION_KEY = "active_application_id"
SESSION_APPLICATION_TTL_SECONDS = 30 * 24 * 60 * 60


def canonical_database(*, root: Path | None = None) -> Database:
    """Return the one runtime control-plane database.

    Callers that inject a ``Database`` remain supported for migrations and
    isolated tests.  Operational callers must use this resolver instead of
    recreating the deprecated ``.career-state/career.db`` default.
    """
    workspace_root = (root or ROOT).resolve()
    configured_path = str(os.environ.get("CAREER_CONTROL_DB_PATH") or "").strip()
    if configured_path:
        configured = Path(configured_path).expanduser()
        db_path = (
            configured.resolve()
            if configured.is_absolute()
            else (workspace_root / configured).resolve()
        )
    else:
        db_path = workspace_root / "control-plane" / "career.db"
    return Database(db_path=db_path)


def build_application_projection(
    application_id: str,
    db: Database,
    *,
    legacy_state_path: Path | None = None,
):
    """Return the read-only SQLite projection for one application.

    The import is local because ``applications_v2`` still uses the path helpers
    in this module.  This boundary deliberately accepts a legacy state path
    only for divergence observation; it cannot influence the resulting stage.
    """

    from career.services.applications_v2 import build_sqlite_application_projection

    return build_sqlite_application_projection(
        application_id,
        db,
        legacy_state_path=legacy_state_path,
    )


def workspace_owner_from_env(env: dict[str, str] | None = None) -> str:
    """Return an explicit pool owner or a process-distinct default owner."""
    values = env or os.environ
    explicit = str(values.get("CAREER_WORKSPACE_OWNER") or "").strip()
    return explicit or f"{socket.gethostname()}:{os.getpid()}"


class WorkspaceLease:
    """SQLite fencing lease for the one authoritative workspace copy."""

    LEASE_NAME = "authoritative-workspace"

    def __init__(
        self,
        database: Database,
        *,
        lease_name: str = LEASE_NAME,
        default_ttl_seconds: int = 300,
        expected_control_db_id: str | None = None,
        require_authority: bool = False,
    ) -> None:
        if not lease_name:
            raise ValueError("lease_name is required")
        if default_ttl_seconds <= 0:
            raise ValueError("default_ttl_seconds must be positive")
        self.database = database
        self.lease_name = lease_name
        self.default_ttl_seconds = default_ttl_seconds
        self.control_db_id = database.control_db_identity()
        self.expected_control_db_id = str(
            expected_control_db_id
            or os.environ.get("CAREER_CONTROL_DB_ID")
            or ""
        ).strip()
        if require_authority and not self.expected_control_db_id:
            raise ValueError(
                "CAREER_CONTROL_DB_ID is required for an authoritative workspace entry point"
            )
        if (
            self.expected_control_db_id
            and self.expected_control_db_id != self.control_db_id
        ):
            raise ValueError(
                "configured authoritative control database identity does not match "
                f"this database: expected={self.expected_control_db_id} "
                f"actual={self.control_db_id}"
            )
        if require_authority:
            database.assert_authoritative_storage()
        self._fence_token: int | None = None

    def acquire(self, owner: str, ttl_seconds: int = 300) -> bool:
        owner = self._owner(owner)
        ttl_seconds = self._ttl(ttl_seconds)
        now = datetime.now(UTC).isoformat()
        expires_at = (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat()
        with self.database.authority_ledger_lock():
            if self.database.authority_ledger_path is not None:
                self.database.assert_authoritative_storage()
            with self.database.transaction(immediate=True) as conn:
                current = conn.execute(
                    """SELECT worker_id, expires_at, lease_epoch
                       FROM workspace_leases WHERE lease_name = ?""",
                    (self.lease_name,),
                ).fetchone()
                if current is None:
                    epoch = self._next_epoch(conn)
                    conn.execute(
                        """INSERT INTO workspace_leases
                           (lease_name, worker_id, run_id, lease_epoch,
                            acquired_at, expires_at)
                           VALUES (?, ?, NULL, ?, ?, ?)""",
                        (self.lease_name, owner, epoch, now, expires_at),
                    )
                    self._fence_token = epoch
                    return True
                current_owner = str(current["worker_id"])
                current_expiry = str(current["expires_at"])
                current_epoch = int(current["lease_epoch"])
                if current_owner == owner and current_expiry > now:
                    conn.execute(
                        "UPDATE workspace_leases SET expires_at = ? WHERE lease_name = ?",
                        (expires_at, self.lease_name),
                    )
                    self._fence_token = current_epoch
                    return True
                if current_expiry > now:
                    return False
                if current_owner != owner and not self.expected_control_db_id:
                    return False
                epoch = self._next_epoch(conn)
                conn.execute(
                    """INSERT INTO workspace_lease_takeovers
                       (lease_name, prior_owner, prior_expires_at, new_owner, taken_over_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        self.lease_name,
                        current_owner,
                        current_expiry,
                        owner,
                        now,
                    ),
                )
                conn.execute(
                    """UPDATE workspace_leases
                       SET worker_id = ?, run_id = NULL, lease_epoch = ?,
                           acquired_at = ?, expires_at = ?
                       WHERE lease_name = ?""",
                    (owner, epoch, now, expires_at, self.lease_name),
                )
                self._fence_token = epoch
                return True

    def heartbeat(
        self,
        owner: str,
        ttl_seconds: int | None = None,
        *,
        fence_token: int | None = None,
    ) -> bool:
        owner = self._owner(owner)
        ttl = self._ttl(ttl_seconds or self.default_ttl_seconds)
        now = datetime.now(UTC).isoformat()
        expires_at = (datetime.now(UTC) + timedelta(seconds=ttl)).isoformat()
        with self.database.authority_ledger_lock():
            if self.database.authority_ledger_path is not None:
                self.database.assert_authoritative_storage()
            with self.database.transaction(immediate=True) as conn:
                params: list[Any] = [expires_at, self.lease_name, owner, now]
                epoch_clause = ""
                expected_token = (
                    int(fence_token)
                    if fence_token is not None
                    else self._fence_token
                )
                if expected_token is not None:
                    epoch_clause = " AND lease_epoch = ?"
                    params.append(expected_token)
                renewed = conn.execute(
                    """UPDATE workspace_leases SET expires_at = ?
                       WHERE lease_name = ? AND worker_id = ? AND expires_at > ?"""
                    + epoch_clause,
                    tuple(params),
                ).rowcount == 1
        return renewed

    def release(self, owner: str) -> bool:
        owner = self._owner(owner)
        with self.database.authority_ledger_lock():
            if self.database.authority_ledger_path is not None:
                self.database.assert_authoritative_storage()
            with self.database.transaction(immediate=True) as conn:
                params: list[Any] = [self.lease_name, owner]
                epoch_clause = ""
                if self._fence_token is not None:
                    epoch_clause = " AND lease_epoch = ?"
                    params.append(self._fence_token)
                released = conn.execute(
                    "DELETE FROM workspace_leases "
                    "WHERE lease_name = ? AND worker_id = ?" + epoch_clause,
                    tuple(params),
                ).rowcount == 1
        if released:
            self._fence_token = None
        return released

    def inspect(self) -> dict[str, Any] | None:
        current = self.database.fetch_one(
            """SELECT lease_name, worker_id AS owner, lease_epoch,
                      acquired_at, expires_at
               FROM workspace_leases WHERE lease_name = ?""",
            (self.lease_name,),
        )
        if current is not None:
            current["control_db_id"] = self.control_db_id
            current["handoff_authorized"] = bool(self.expected_control_db_id)
        return current

    @property
    def fence_token(self) -> int | None:
        return self._fence_token

    @staticmethod
    def _next_epoch(conn) -> int:
        conn.execute(
            """UPDATE workspace_authority
               SET lease_epoch_counter = lease_epoch_counter + 1
               WHERE singleton_id = 1"""
        )
        row = conn.execute(
            "SELECT lease_epoch_counter FROM workspace_authority WHERE singleton_id = 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("workspace authority epoch counter is missing")
        return int(row["lease_epoch_counter"])

    @staticmethod
    def _owner(owner: str) -> str:
        value = str(owner or "").strip()
        if not value:
            raise ValueError("workspace lease owner is required")
        return value

    @staticmethod
    def _ttl(ttl_seconds: int) -> int:
        ttl = int(ttl_seconds)
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        return ttl


def validate_application_id(application_id: str) -> str:
    """Return a single safe application path segment or reject the identifier."""
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


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "vaga"


def _short_hash(value: str, length: int = 8) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:length]


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _delivery_profile_for_source(
    source_type: str,
    source_url: str | None,
    source_metadata: dict[str, Any] | None,
) -> str:
    metadata = source_metadata if isinstance(source_metadata, dict) else {}
    explicit = str(metadata.get("delivery_profile") or "").strip().lower()
    if explicit in {"standard_cv", "gupy_registration"}:
        return explicit
    url = str(source_url or metadata.get("source_url") or metadata.get("url") or "").lower()
    canal = str(metadata.get("canal_aplicacao") or metadata.get("application_channel") or "").lower()
    if "gupy" in url or "gupy" in canal:
        return "gupy_registration"
    return "standard_cv"


def profile_id_from_env(env: dict[str, str] | None = None) -> str:
    env = env or os.environ
    explicit_profile_id = str(env.get("CAREER_HERMES_PROFILE_ID") or "").strip()
    if explicit_profile_id:
        return explicit_profile_id
    hermes_home = env.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return _short_hash(str(Path(hermes_home).expanduser()), 12)


def session_key(*, runtime: str, profile_id: str, session_id: str) -> str:
    return f"{runtime}:{profile_id}:{session_id}"


@dataclass(frozen=True)
class ApplicationPaths:
    application_id: str
    app_dir: Path
    plans_dir: Path
    cells_dir: Path
    artifacts_dir: Path
    reviews_dir: Path
    run_completion_manifest: Path
    identity: Path
    state: Path
    workflow_state: Path
    source_metadata: Path
    job_description: Path
    saved_job_description: Path
    conversation_context: Path
    fit_map_draft: Path
    fit_map: Path
    derived_dir: Path
    cv_content: Path
    cv_review_report: Path
    polish_review: Path
    lock: Path
    requests_dir: Path


def paths_for(application_id: str, root: Path | None = None) -> ApplicationPaths:
    application_id = validate_application_id(application_id)
    app_dir = (Path(root) if root is not None else APPLICATIONS_DIR) / application_id
    return ApplicationPaths(
        application_id=application_id,
        app_dir=app_dir,
        plans_dir=app_dir / "plans",
        cells_dir=app_dir / "cells",
        artifacts_dir=app_dir / "artifacts",
        reviews_dir=app_dir / "reviews",
        run_completion_manifest=app_dir / "run_completion_manifest.json",
        identity=app_dir / "identity.json",
        state=app_dir / "state.json",
        workflow_state=app_dir / "workflow_state.json",
        source_metadata=app_dir / "source_metadata.json",
        job_description=app_dir / "job_description.md",
        saved_job_description=app_dir / "saved_job_description_path.txt",
        conversation_context=app_dir / "conversation_context.md",
        fit_map_draft=app_dir / "fit_map.draft.json",
        fit_map=app_dir / "fit_map.json",
        derived_dir=app_dir / "derived",
        cv_content=app_dir / "cv_content.json",
        cv_review_report=app_dir / "cv_review_report.json",
        polish_review=app_dir / "polish_review.json",
        lock=app_dir / ".lock",
        requests_dir=app_dir / "requests",
    )


def application_id_for(
    *,
    source_type: str,
    source_id: str | None = None,
    company: str | None = None,
    role: str | None = None,
    record_id: int | str | None = None,
    preferred_id: str | None = None,
) -> str:
    """Build an application id without persisting state or compatibility files."""
    if preferred_id:
        validate_application_id(preferred_id)
        # Explicit IDs are already canonical SQLite keys.  Slugging here
        # changes case-sensitive IDs (for example the timestamp ``T``) and
        # makes a planned run impossible to resume under the requested ID.
        return str(preferred_id).strip()
    if record_id is not None:
        return f"notion_{_slug(str(record_id))}"
    basis = "|".join([source_type, source_id or "", company or "", role or ""])
    stamp = utc_now_iso().replace("-", "").replace(":", "").replace(".", "_").split("+")[0]
    return f"local_{stamp}_{_slug(company or source_type)}_{_short_hash(basis)}"


def materialize_compatibility_identity(
    paths: ApplicationPaths,
    *,
    source_type: str,
    source_id: str | None = None,
    company: str | None = None,
    role: str | None = None,
    record_id: int | str | None = None,
    source_url: str | None = None,
) -> None:
    """Write non-authoritative path mirrors after canonical SQLite persistence."""
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    for directory in (
        paths.plans_dir,
        paths.cells_dir,
        paths.artifacts_dir,
        paths.reviews_dir,
        paths.derived_dir,
        paths.requests_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    existing_identity = read_json(paths.identity) if paths.identity.exists() else {}
    aliases = (
        dict(existing_identity.get("aliases"))
        if isinstance(existing_identity.get("aliases"), dict)
        else {}
    )
    if record_id is not None:
        aliases["notion_record_id"] = str(record_id)
    if source_id:
        aliases[f"{source_type}_source_id"] = source_id
    identity = {
        "kind": "application_identity",
        "application_id": paths.application_id,
        "created_at": existing_identity.get("created_at") or utc_now_iso(),
        "updated_at": utc_now_iso(),
        "source_type": source_type,
        "source_id": source_id,
        "source_url": source_url or existing_identity.get("source_url") or "",
        "company": company or existing_identity.get("company") or "",
        "role": role or existing_identity.get("role") or "",
        "aliases": aliases,
    }
    write_json(paths.identity, identity)
    _update_alias_index(paths.application_id, aliases)
    if not paths.state.exists():
        write_json(
            paths.state,
            {
                "kind": "application_state",
                "application_id": paths.application_id,
                "stage": "created",
                "stage_status": "pending",
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "last_execution": None,
            },
        )


def ensure_application(
    *,
    source_type: str,
    source_id: str | None = None,
    company: str | None = None,
    role: str | None = None,
    record_id: int | str | None = None,
    preferred_id: str | None = None,
) -> ApplicationPaths:
    application_id = application_id_for(
        source_type=source_type,
        source_id=source_id,
        company=company,
        role=role,
        record_id=record_id,
        preferred_id=preferred_id,
    )
    paths = paths_for(application_id)
    existing_identity = read_json(paths.identity) if paths.identity.exists() else {}
    aliases = dict(existing_identity.get("aliases")) if isinstance(existing_identity.get("aliases"), dict) else {}
    if record_id is not None:
        aliases["notion_record_id"] = str(record_id)
    if source_id:
        aliases[f"{source_type}_source_id"] = source_id
    _repository().create_application(
        ApplicationIdentity(
            application_id=application_id,
            company=str(company or existing_identity.get("company") or ""),
            role=str(role or existing_identity.get("role") or ""),
            notion_id=str(aliases.get("notion_record_id"))
            if aliases.get("notion_record_id")
            else None,
            source_type=source_type,
            source_url=str(existing_identity.get("source_url"))
            if existing_identity.get("source_url")
            else None,
            delivery_profile=_delivery_profile_for_source(
                source_type,
                str(existing_identity.get("source_url") or "") or None,
                existing_identity,
            ),
            aliases={
                ("notion_id" if key == "notion_record_id" else str(key)): str(value)
                for key, value in aliases.items()
                if value
            },
        )
    )
    materialize_compatibility_identity(
        paths,
        source_type=source_type,
        source_id=source_id,
        company=company,
        role=role,
        record_id=record_id,
        source_url=str(existing_identity.get("source_url")) if existing_identity.get("source_url") else None,
    )
    return paths


def persist_intake(
    *,
    source_type: str,
    source_id: str | None,
    company: str,
    role: str,
    source_text: str,
    fingerprint: str,
    record_id: int | str | None = None,
    preferred_id: str | None = None,
    source_url: str | None = None,
    source_metadata: dict[str, Any] | None = None,
    database: Database | None = None,
) -> tuple[ApplicationPaths, ApplicationRecord]:
    """Commit canonical intake identity and description before file mirrors.

    Application directories and JSON files are compatibility materializations.
    They are deliberately written only after the SQLite transaction succeeds.
    """
    company = str(company or "").strip()
    role = str(role or "").strip()
    source_text = str(source_text or "")
    fingerprint = str(fingerprint or "").strip()
    if not company or not role:
        raise ValueError("intake requires company and role")
    if not source_text.strip():
        raise ValueError("intake source_text must be non-empty")
    expected_fingerprint = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if fingerprint != expected_fingerprint:
        raise ValueError("intake fingerprint does not match source_text")

    if preferred_id:
        # An explicit ID is already canonical. Slugging it here can change
        # case (for example ``...T...`` to ``...t...``), causing a retry to
        # miss the existing SQLite application and collide on its aliases.
        application_id = validate_application_id(str(preferred_id).strip())
    elif record_id is not None:
        application_id = f"notion_{_slug(str(record_id))}"
    else:
        basis = "|".join([source_type, source_id or "", company, role])
        stamp = utc_now_iso().replace("-", "").replace(":", "").replace(".", "_").split("+")[0]
        application_id = f"local_{stamp}_{_slug(company or source_type)}_{_short_hash(basis)}"

    paths = paths_for(application_id)
    repository_database = database or canonical_database()
    repository_database.migrate()
    now = utc_now_iso()
    aliases: dict[str, str] = {}
    if record_id is not None:
        aliases["notion_id"] = str(record_id)
    if source_id:
        aliases[f"{source_type}_source_id"] = str(source_id)
    metadata = dict(source_metadata or {})
    source_row_id = f"source_{uuid4().hex}"
    description_id = f"job_{uuid4().hex}"
    application_revision_id = f"rev_{uuid4().hex}"
    source_url = str(source_url or "").strip() or None
    delivery_profile = _delivery_profile_for_source(source_type, source_url, metadata)
    description_path = _relative(paths.job_description)
    source_metadata_json = json.dumps(
        metadata, sort_keys=True, separators=(",", ":"), default=str
    )
    source_metadata_hash = hashlib.sha256(
        source_metadata_json.encode("utf-8")
    ).hexdigest()
    revision_payload = {
        "job_description_id": description_id,
        "job_source_id": source_row_id,
        "job_description_hash": fingerprint,
        "job_description_path": description_path,
        "source_type": source_type,
        "source_url": source_url,
        "source_metadata_hash": source_metadata_hash,
    }

    with repository_database.transaction(immediate=True) as conn:
        existing = conn.execute(
            "SELECT created_at FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        created_at = str(existing["created_at"]) if existing is not None else now
        conn.execute(
            """INSERT INTO applications
               (id, notion_id, company, role, source_type, source_url, stage,
                funil_stage, cv_language, status, delivery_profile, created_at, updated_at,
                job_description_path)
               VALUES (?, ?, ?, ?, ?, ?, 'analyze_pending', 'Fila Agente',
                       'pt', 'active', ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 notion_id = COALESCE(excluded.notion_id, applications.notion_id),
                 company = excluded.company,
                 role = excluded.role,
                 source_type = excluded.source_type,
                 source_url = COALESCE(excluded.source_url, applications.source_url),
                 delivery_profile = excluded.delivery_profile,
                 job_description_path = excluded.job_description_path,
                 updated_at = excluded.updated_at""",
            (
                application_id,
                str(record_id) if record_id is not None else None,
                company,
                role,
                source_type,
                source_url,
                delivery_profile,
                created_at,
                now,
                description_path,
            ),
        )
        for alias_type, alias_value in aliases.items():
            alias_owner = conn.execute(
                """SELECT application_id FROM application_aliases
                   WHERE alias_type = ? AND alias_value = ?""",
                (alias_type, alias_value),
            ).fetchone()
            if alias_owner is not None and str(alias_owner["application_id"]) != application_id:
                raise ValueError(
                    f"alias {alias_type}={alias_value} already belongs to {alias_owner['application_id']}"
                )
            conn.execute(
                """INSERT INTO application_aliases
                   (application_id, alias_type, alias_value, is_primary, created_at)
                   VALUES (?, ?, ?, 1, ?)
                   ON CONFLICT(alias_type, alias_value) DO UPDATE SET is_primary = 1""",
                (application_id, alias_type, alias_value, now),
            )
        conn.execute(
            """INSERT INTO job_sources
               (source_id, application_id, source_type, source_url, fingerprint,
                metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                source_row_id,
                application_id,
                source_type,
                source_url,
                fingerprint,
                source_metadata_json,
                now,
            ),
        )
        conn.execute(
            """INSERT INTO job_descriptions
               (description_id, application_id, source_id, language, content,
                content_hash, created_at)
               VALUES (?, ?, ?, NULL, ?, ?, ?)""",
            (description_id, application_id, source_row_id, source_text, fingerprint, now),
        )
        conn.execute(
            """INSERT OR IGNORE INTO application_revisions
               (revision_id, application_id, revision_kind, fingerprint, source_hash,
                payload_json, created_at)
               VALUES (?, ?, 'job_description', ?, ?, ?, ?)""",
            (
                application_revision_id,
                application_id,
                fingerprint,
                fingerprint,
                json.dumps(
                    revision_payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
                now,
            ),
        )

    for directory in (
        paths.app_dir,
        paths.plans_dir,
        paths.cells_dir,
        paths.artifacts_dir,
        paths.reviews_dir,
        paths.derived_dir,
        paths.requests_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    existing_identity = read_json(paths.identity) if paths.identity.exists() else {}
    identity_aliases = (
        dict(existing_identity.get("aliases"))
        if isinstance(existing_identity.get("aliases"), dict)
        else {}
    )
    if record_id is not None:
        identity_aliases["notion_record_id"] = str(record_id)
    if source_id:
        identity_aliases[f"{source_type}_source_id"] = str(source_id)
    write_json(
        paths.identity,
        {
            "kind": "application_identity",
            "application_id": application_id,
            "created_at": existing_identity.get("created_at") or now,
            "updated_at": now,
            "source_type": source_type,
            "source_id": source_id,
            "source_url": source_url or "",
            "delivery_profile": delivery_profile,
            "company": company,
            "role": role,
            "aliases": identity_aliases,
        },
    )
    write_text(paths.job_description, source_text)
    GateRepository(repository_database).record(
        GateReceipt(
            application_id=application_id,
            application_fingerprint=fingerprint,
            run_id=f"intake_{application_id}_{fingerprint[:16]}",
            gate="job_description_saved",
            validator="project.save_job_description",
            input_hash=fingerprint,
            output_hash=fingerprint,
        )
    )
    _update_alias_index(application_id, identity_aliases)
    if not paths.state.exists():
        write_json(
            paths.state,
            {
                "kind": "application_state",
                "application_id": application_id,
                "stage": "created",
                "stage_status": "pending",
                "created_at": now,
                "updated_at": now,
                "last_execution": None,
            },
        )
    return paths, ApplicationRepository(repository_database).resolve(application_id=application_id)


def resolve_active_application() -> ApplicationRecord:
    """Reject legacy active-pointer resolution in agent execution paths."""
    raise RuntimeError(
        "active application pointers are discovery metadata only; agent execution requires explicit application_id"
    )


def _update_alias_index(application_id: str, aliases: dict[str, Any]) -> bool:
    """Best-effort update of the legacy mirror; SQLite remains authoritative."""
    try:
        payload = read_json(ALIAS_INDEX) if ALIAS_INDEX.exists() else {"aliases": {}}
        index = payload.setdefault("aliases", {})
        for key, value in aliases.items():
            if value:
                index[f"{key}:{value}"] = application_id
        write_json(ALIAS_INDEX, payload)
    except OSError:
        return False
    return True


def _repository(database: Database | None = None) -> ApplicationRepository:
    repository_database = database or canonical_database()
    return ApplicationRepository(repository_database)


def _legacy_record_from_files(application_id: str) -> ApplicationRecord:
    paths = paths_for(application_id)
    if not paths.identity.exists():
        raise ApplicationNotFoundError(
            f"no application matched application_id={application_id}"
        )
    identity = read_json(paths.identity)
    aliases = identity.get("aliases") if isinstance(identity.get("aliases"), dict) else {}
    source_metadata = (
        read_json(paths.source_metadata) if paths.source_metadata.exists() else {}
    )
    notion_id = None
    if aliases.get("notion_id"):
        notion_id = str(aliases["notion_id"])
    elif aliases.get("notion_record_id"):
        notion_id = str(aliases["notion_record_id"])
    return ApplicationRecord(
        application_id=application_id,
        company=str(identity.get("company") or ""),
        role=str(identity.get("role") or ""),
        notion_id=notion_id,
        fingerprint=str(source_metadata.get("job_fingerprint"))
        if source_metadata.get("job_fingerprint")
        else None,
        source_type=str(identity.get("source_type") or "legacy"),
        source_url=str(identity.get("source_url"))
        if identity.get("source_url")
        else None,
        stage="legacy_file_projection",
        funil_stage="legacy_file_projection",
        score=None,
        cv_language="pt",
        status="legacy",
        created_at=str(identity.get("created_at") or ""),
        updated_at=str(identity.get("updated_at") or ""),
        job_description_path=_relative(paths.job_description)
        if paths.job_description.exists()
        else None,
        fit_map_path=_relative(paths.fit_map) if paths.fit_map.exists() else None,
        cv_path=None,
        delivery_profile="standard_cv",
        aliases={str(key): str(value) for key, value in aliases.items() if value},
    )


def resolve_application(
    *,
    application_id: str | None = None,
    notion_id: str | None = None,
    fingerprint: str | None = None,
    company: str | None = None,
    role: str | None = None,
    database: Database | None = None,
    allow_legacy: bool = True,
) -> ApplicationRecord:
    explicit_application_id = str(application_id or "").strip()
    sole_application_selector = bool(explicit_application_id) and not any(
        (
            str(notion_id or "").strip(),
            str(fingerprint or "").strip(),
            str(company or "").strip(),
            str(role or "").strip(),
        )
    )
    try:
        return _repository(database).resolve(
            application_id=application_id,
            notion_id=notion_id,
            fingerprint=fingerprint,
            company=company,
            role=role,
        )
    except ApplicationNotFoundError:
        if allow_legacy and sole_application_selector:
            return _legacy_record_from_files(
                validate_application_id(explicit_application_id)
            )
        raise


def register_session(
    *,
    runtime: str,
    session_id: str,
    application_id: str,
    profile_id: str | None = None,
    channel: str | None = None,
    database: Database | None = None,
) -> dict[str, Any]:
    application_id = validate_application_id(application_id)
    profile_id = profile_id or ("default" if runtime != "hermes" else profile_id_from_env())
    key = session_key(runtime=runtime, profile_id=profile_id, session_id=session_id)
    session_database = database or canonical_database()
    session_memory = SessionMemoryService(session_database)
    session_memory.reset(key)
    session_memory.set(
        key,
        SESSION_APPLICATION_KEY,
        application_id,
        ttl_seconds=SESSION_APPLICATION_TTL_SECONDS,
    )
    registry = read_json(SESSION_REGISTRY) if SESSION_REGISTRY.exists() else {"sessions": {}}
    sessions = registry.setdefault("sessions", {})
    sessions[key] = {
        "runtime": runtime,
        "profile_id": profile_id,
        "session_id": session_id,
        "application_id": application_id,
        "channel": channel or "",
        "last_seen_at": utc_now_iso(),
    }
    write_json(SESSION_REGISTRY, registry)
    return sessions[key]


def resolve_session(
    *,
    runtime: str,
    session_id: str,
    profile_id: str | None = None,
    database: Database | None = None,
) -> str | None:
    profile_id = profile_id or ("default" if runtime != "hermes" else profile_id_from_env())
    key = session_key(runtime=runtime, profile_id=profile_id, session_id=session_id)
    session_database = database or canonical_database()
    session_memory = SessionMemoryService(session_database)
    application_id = session_memory.get(key, SESSION_APPLICATION_KEY)
    if application_id:
        return validate_application_id(application_id)
    if session_database.persistence_mode == RuntimePersistenceMode.SQLITE_ONLY:
        return None
    if not SESSION_REGISTRY.exists():
        return None
    registry = read_json(SESSION_REGISTRY)
    item = registry.get("sessions", {}).get(key)
    if isinstance(item, dict) and item.get("application_id"):
        return validate_application_id(str(item["application_id"]))
    return None


def acquire_lock(paths: ApplicationPaths, *, owner: dict[str, Any], stage: str, force: bool = False) -> dict[str, Any]:
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    if paths.lock.exists() and not force:
        current = read_json(paths.lock)
        return {"status": "blocked", "reason": "application_locked", "lock": current, "path": _relative(paths.lock)}
    payload = {
        "kind": "application_lock",
        "application_id": paths.application_id,
        "owner": owner,
        "stage": stage,
        "pid": os.getpid(),
        "acquired_at": utc_now_iso(),
    }
    write_json(paths.lock, payload)
    return {"status": "ok", "lock": payload, "path": _relative(paths.lock)}


def release_lock(paths: ApplicationPaths, *, dry_run: bool = False) -> dict[str, Any]:
    if not paths.lock.exists():
        return {"status": "ok", "released": False, "reason": "no_lock", "path": _relative(paths.lock)}
    current = read_json(paths.lock)
    if not dry_run:
        paths.lock.unlink()
    return {"status": "ok", "released": not dry_run, "dry_run": dry_run, "lock": current, "path": _relative(paths.lock)}


def list_active() -> dict[str, Any]:
    applications = []
    APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    for identity_path in sorted(APPLICATIONS_DIR.glob("*/identity.json")):
        app_dir = identity_path.parent
        identity = read_json(identity_path)
        lock_path = app_dir / ".lock"
        applications.append(
            {
                "application_id": app_dir.name,
                "company": identity.get("company"),
                "role": identity.get("role"),
                "source_type": identity.get("source_type"),
                "source_id": identity.get("source_id"),
                "locked": lock_path.exists(),
                "lock_path": _relative(lock_path) if lock_path.exists() else None,
                "updated_at": identity.get("updated_at"),
            }
        )
    return {"status": "ok", "count": len(applications), "applications": applications}


def inspect(application_id: str) -> dict[str, Any]:
    paths = paths_for(application_id)
    identity = read_json(paths.identity) if paths.identity.exists() else {}
    state = read_json(paths.state) if paths.state.exists() else {}
    lock = read_json(paths.lock) if paths.lock.exists() else None
    return {
        "status": "ok" if paths.app_dir.exists() else "blocked",
        "application_id": application_id,
        "app_dir": _relative(paths.app_dir),
        "identity": identity,
        "state": state,
        "lock": lock,
        "files": {
            "workflow_state": paths.workflow_state.exists(),
            "job_description": paths.job_description.exists(),
            "fit_map_draft": paths.fit_map_draft.exists(),
            "fit_map": paths.fit_map.exists(),
            "derived_dir": paths.derived_dir.exists(),
            "cv_content": paths.cv_content.exists(),
        },
    }


def migrate_global_state(*, application_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    state_path = CAREER_STATE / "workflow_state.json"
    state = read_json(state_path) if state_path.exists() else {}
    active = state.get("active_intake") if isinstance(state.get("active_intake"), dict) else {}
    legacy_fit_map = read_json(CAREER_STATE / "fit_map.json") if (CAREER_STATE / "fit_map.json").exists() else {}
    company = str(active.get("company") or legacy_fit_map.get("empresa") or "legacy")
    role = str(active.get("role") or legacy_fit_map.get("cargo") or "active")
    preferred = application_id or f"legacy_{_slug(company)}_{_slug(role)}"
    if dry_run:
        paths = paths_for(_slug(preferred))
    else:
        paths = ensure_application(
            source_type=str(active.get("source_type") or "legacy_global_state"),
            source_id=str(active.get("source_id") or "") or None,
            company=company,
            role=role,
            preferred_id=preferred,
        )
    copies = [
        (CAREER_STATE / "workflow_state.json", paths.workflow_state),
        (CAREER_STATE / "fit_map.draft.json", paths.fit_map_draft),
        (CAREER_STATE / "fit_map.json", paths.fit_map),
        (CAREER_STATE / "cv_content.json", paths.cv_content),
    ]
    copied: list[dict[str, Any]] = []
    for source, destination in copies:
        if source.exists():
            copied.append({"source": _relative(source), "destination": _relative(destination)})
            if not dry_run:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    derived_source = CAREER_STATE / "derived"
    if derived_source.exists():
        copied.append({"source": _relative(derived_source), "destination": _relative(paths.derived_dir)})
        if not dry_run:
            if paths.derived_dir.exists():
                shutil.rmtree(paths.derived_dir)
            shutil.copytree(derived_source, paths.derived_dir)
    job_rel = active.get("job_description_path")
    job_path = ROOT / str(job_rel) if isinstance(job_rel, str) and job_rel else None
    if job_path and job_path.exists():
        copied.append({"source": _relative(job_path), "destination": _relative(paths.job_description)})
        if not dry_run:
            shutil.copy2(job_path, paths.job_description)
            paths.saved_job_description.write_text(_relative(job_path) + "\n", encoding="utf-8")
    if not dry_run and paths.workflow_state.exists():
        application_payload = read_json(paths.workflow_state)
        active_intake = application_payload.get("active_intake")
        if isinstance(active_intake, dict):
            active_intake["application_id"] = paths.application_id
            active_intake["application_dir"] = _relative(paths.app_dir)
            if paths.job_description.exists():
                active_intake["job_description_path"] = _relative(paths.job_description)
            if paths.fit_map_draft.exists():
                active_intake["draft_path"] = _relative(paths.fit_map_draft)
            if paths.fit_map.exists():
                active_intake["fit_map_path"] = _relative(paths.fit_map)
            application_payload["active_intake"] = active_intake
            active_job = application_payload.get("active_job")
            if isinstance(active_job, dict) and paths.job_description.exists():
                active_job["path"] = _relative(paths.job_description)
                application_payload["active_job"] = active_job
            application_payload["active_application_id"] = paths.application_id
            write_json(paths.workflow_state, application_payload)
    return {
        "status": "ok",
        "dry_run": dry_run,
        "application_id": paths.application_id,
        "application_dir": _relative(paths.app_dir),
        "copied": copied,
        "preserved_global_state": True,
    }
