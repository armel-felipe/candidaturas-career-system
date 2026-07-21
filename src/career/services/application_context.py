from __future__ import annotations

import hashlib
import os
import re
import shutil
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, ROOT
from career.services.database import Database
from career.utils import read_json, utc_now_iso, write_json


APPLICATIONS_DIR = CAREER_STATE / "applications_v2"
SESSION_REGISTRY = CAREER_STATE / "session_registry.json"
ALIAS_INDEX = CAREER_STATE / "application_alias_index.json"


def workspace_owner_from_env(env: dict[str, str] | None = None) -> str:
    """Return the stable owner shared by processes in one authoritative copy."""
    values = env or os.environ
    explicit = str(values.get("CAREER_WORKSPACE_OWNER") or "").strip()
    return explicit or socket.gethostname()


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

    def acquire(self, owner: str, ttl_seconds: int = 300) -> bool:
        owner = self._owner(owner)
        ttl_seconds = self._ttl(ttl_seconds)
        now = datetime.now(UTC).isoformat()
        expires_at = (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat()
        with self.database.transaction(immediate=True) as conn:
            current = conn.execute(
                "SELECT worker_id, expires_at FROM workspace_leases WHERE lease_name = ?",
                (self.lease_name,),
            ).fetchone()
            if current is None:
                conn.execute(
                    """INSERT INTO workspace_leases
                       (lease_name, worker_id, run_id, acquired_at, expires_at)
                       VALUES (?, ?, NULL, ?, ?)""",
                    (self.lease_name, owner, now, expires_at),
                )
                return True
            current_owner = str(current["worker_id"])
            current_expiry = str(current["expires_at"])
            if current_owner == owner and current_expiry > now:
                conn.execute(
                    "UPDATE workspace_leases SET expires_at = ? WHERE lease_name = ?",
                    (expires_at, self.lease_name),
                )
                return True
            if current_expiry > now:
                return False
            if current_owner != owner and not self.expected_control_db_id:
                return False
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
                   SET worker_id = ?, run_id = NULL, acquired_at = ?, expires_at = ?
                   WHERE lease_name = ?""",
                (owner, now, expires_at, self.lease_name),
            )
            return True

    def heartbeat(self, owner: str, ttl_seconds: int | None = None) -> bool:
        owner = self._owner(owner)
        ttl = self._ttl(ttl_seconds or self.default_ttl_seconds)
        now = datetime.now(UTC).isoformat()
        expires_at = (datetime.now(UTC) + timedelta(seconds=ttl)).isoformat()
        with self.database.transaction(immediate=True) as conn:
            renewed = conn.execute(
                """UPDATE workspace_leases SET expires_at = ?
                   WHERE lease_name = ? AND worker_id = ? AND expires_at > ?""",
                (expires_at, self.lease_name, owner, now),
            ).rowcount == 1
        return renewed

    def release(self, owner: str) -> bool:
        owner = self._owner(owner)
        with self.database.transaction(immediate=True) as conn:
            released = conn.execute(
                "DELETE FROM workspace_leases WHERE lease_name = ? AND worker_id = ?",
                (self.lease_name, owner),
            ).rowcount == 1
        return released

    def inspect(self) -> dict[str, Any] | None:
        current = self.database.fetch_one(
            """SELECT lease_name, worker_id AS owner, acquired_at, expires_at
               FROM workspace_leases WHERE lease_name = ?""",
            (self.lease_name,),
        )
        if current is not None:
            current["control_db_id"] = self.control_db_id
            current["handoff_authorized"] = bool(self.expected_control_db_id)
        return current

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


def profile_id_from_env(env: dict[str, str] | None = None) -> str:
    env = env or os.environ
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


def ensure_application(
    *,
    source_type: str,
    source_id: str | None = None,
    company: str | None = None,
    role: str | None = None,
    record_id: int | str | None = None,
    preferred_id: str | None = None,
) -> ApplicationPaths:
    if preferred_id:
        validate_application_id(preferred_id)
        application_id = _slug(preferred_id)
    elif record_id is not None:
        application_id = f"notion_{_slug(str(record_id))}"
    else:
        basis = "|".join([source_type, source_id or "", company or "", role or ""])
        stamp = utc_now_iso().replace("-", "").replace(":", "").replace(".", "_").split("+")[0]
        application_id = f"local_{stamp}_{_slug(company or source_type)}_{_short_hash(basis)}"

    paths = paths_for(application_id)
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

    identity = read_json(paths.identity) if paths.identity.exists() else {}
    aliases = identity.get("aliases") if isinstance(identity.get("aliases"), dict) else {}
    if record_id is not None:
        aliases["notion_record_id"] = str(record_id)
    if source_id:
        aliases[f"{source_type}_source_id"] = source_id
    identity.update(
        {
            "kind": "application_identity",
            "application_id": application_id,
            "created_at": identity.get("created_at") or utc_now_iso(),
            "updated_at": utc_now_iso(),
            "source_type": source_type,
            "source_id": source_id,
            "company": company or identity.get("company") or "",
            "role": role or identity.get("role") or "",
            "aliases": aliases,
        }
    )
    write_json(paths.identity, identity)
    _update_alias_index(application_id, aliases)
    if not paths.state.exists():
        write_json(
            paths.state,
            {
                "kind": "application_state",
                "application_id": application_id,
                "stage": "created",
                "stage_status": "pending",
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "last_execution": None,
            },
        )
    return paths


def _update_alias_index(application_id: str, aliases: dict[str, Any]) -> None:
    payload = read_json(ALIAS_INDEX) if ALIAS_INDEX.exists() else {"aliases": {}}
    index = payload.setdefault("aliases", {})
    for key, value in aliases.items():
        if value:
            index[f"{key}:{value}"] = application_id
    write_json(ALIAS_INDEX, payload)


def register_session(
    *,
    runtime: str,
    session_id: str,
    application_id: str,
    profile_id: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    application_id = validate_application_id(application_id)
    profile_id = profile_id or ("default" if runtime != "hermes" else profile_id_from_env())
    key = session_key(runtime=runtime, profile_id=profile_id, session_id=session_id)
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


def resolve_session(*, runtime: str, session_id: str, profile_id: str | None = None) -> str | None:
    if not SESSION_REGISTRY.exists():
        return None
    profile_id = profile_id or ("default" if runtime != "hermes" else profile_id_from_env())
    registry = read_json(SESSION_REGISTRY)
    item = registry.get("sessions", {}).get(session_key(runtime=runtime, profile_id=profile_id, session_id=session_id))
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
    company = str(active.get("company") or "legacy")
    role = str(active.get("role") or "active")
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
    return {
        "status": "ok",
        "dry_run": dry_run,
        "application_id": paths.application_id,
        "application_dir": _relative(paths.app_dir),
        "copied": copied,
        "preserved_global_state": True,
    }
