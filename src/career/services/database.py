from __future__ import annotations

import os
import hashlib
import json
import platform
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from career.paths import CAREER_STATE


class Database:
    AUTHORITY_LEDGER_KIND = "career_workspace_authority"
    AUTHORITY_LEDGER_VERSION = 1

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        authority_ledger_path: str | Path | None = None,
    ):
        self.db_path = Path(db_path or os.path.join(CAREER_STATE, "career.db"))
        configured_ledger = authority_ledger_path or os.environ.get(
            "CAREER_AUTHORITY_LEDGER_PATH"
        )
        self.authority_ledger_path = (
            Path(configured_ledger).expanduser().resolve()
            if configured_ledger
            else None
        )
        self._conn: sqlite3.Connection | None = None
        self._authority_lock_state = threading.local()

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_schema(self) -> None:
        self._initialize_schema(verify_authority_ledger=True)

    def prepare_authority_ledger_provisioning(self) -> None:
        """Upgrade the local schema without fabricating or verifying a ledger.

        The explicit provisioning command uses this migration path before it
        creates the one shared authority ledger. Normal schema initialization
        continues to fail closed when a configured ledger is absent.
        """
        self._initialize_schema(verify_authority_ledger=False)

    def _initialize_schema(self, *, verify_authority_ledger: bool) -> None:
        conn = self.get_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                notion_id TEXT,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                source_type TEXT DEFAULT 'paste',
                source_url TEXT,
                stage TEXT DEFAULT 'analyze_pending',
                funil_stage TEXT DEFAULT 'Fila Agente',
                score REAL,
                cv_language TEXT DEFAULT 'pt',
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                job_description_path TEXT,
                fit_map_path TEXT,
                cv_path TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_applications_funil_status
                ON applications(funil_stage, status);
            CREATE INDEX IF NOT EXISTS idx_applications_notion_id
                ON applications(notion_id);
            CREATE INDEX IF NOT EXISTS idx_applications_company_role
                ON applications(company, role);
            CREATE INDEX IF NOT EXISTS idx_applications_stage_status
                ON applications(stage, status);

            CREATE TABLE IF NOT EXISTS workflow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id TEXT NOT NULL REFERENCES applications(id),
                event TEXT NOT NULL,
                fingerprint TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_workflow_events_app_event
                ON workflow_events(application_id, event);

            CREATE TABLE IF NOT EXISTS notion_cache (
                id TEXT PRIMARY KEY,
                raw_json TEXT,
                company TEXT,
                role TEXT,
                funil_stage TEXT,
                canal_aplicacao TEXT,
                tipo_empresa TEXT,
                status TEXT,
                url TEXT,
                last_synced TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_notion_cache_funil_stage
                ON notion_cache(funil_stage);
            CREATE INDEX IF NOT EXISTS idx_notion_cache_company
                ON notion_cache(company);
            CREATE INDEX IF NOT EXISTS idx_notion_cache_tipo_empresa
                ON notion_cache(tipo_empresa);
            CREATE INDEX IF NOT EXISTS idx_notion_cache_canal_aplicacao
                ON notion_cache(canal_aplicacao);

            CREATE TABLE IF NOT EXISTS keyword_registry (
                keyword TEXT NOT NULL,
                application_id TEXT NOT NULL,
                coverage TEXT NOT NULL DEFAULT 'missing',
                evidence TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (keyword, application_id)
            );

            CREATE INDEX IF NOT EXISTS idx_keyword_registry_application
                ON keyword_registry(application_id);

            CREATE TABLE IF NOT EXISTS session_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                created_at TEXT NOT NULL,
                ttl_seconds INTEGER DEFAULT 3600
            );

            CREATE INDEX IF NOT EXISTS idx_session_memory_session_key
                ON session_memory(session_id, key);

            CREATE TABLE IF NOT EXISTS application_runs (
                run_id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                graph_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned',
                contract_version TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_application_runs_application_created
                ON application_runs(application_id, created_at);

            CREATE TABLE IF NOT EXISTS cell_nodes (
                run_id TEXT NOT NULL REFERENCES application_runs(run_id),
                node_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned',
                requires_json TEXT NOT NULL DEFAULT '[]',
                reserved_by TEXT,
                reservation_expires_at TEXT,
                latest_attempt INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (run_id, node_id)
            );

            CREATE INDEX IF NOT EXISTS idx_cell_nodes_run_status
                ON cell_nodes(run_id, status);

            CREATE TABLE IF NOT EXISTS cell_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                worker_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                finished_at TEXT,
                detail_json TEXT,
                UNIQUE (run_id, node_id, attempt),
                FOREIGN KEY (run_id, node_id) REFERENCES cell_nodes(run_id, node_id)
            );

            CREATE INDEX IF NOT EXISTS idx_cell_attempts_run_node
                ON cell_attempts(run_id, node_id);

            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES application_runs(run_id),
                node_id TEXT NOT NULL,
                artifact_name TEXT NOT NULL,
                path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                input_hash TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_artifacts_run_node
                ON artifacts(run_id, node_id);

            CREATE TABLE IF NOT EXISTS resource_locks (
                resource_name TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                lease_id TEXT,
                acquired_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_resource_locks_resource_expires
                ON resource_locks(resource_name, expires_at);

            CREATE TABLE IF NOT EXISTS workspace_leases (
                lease_name TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                run_id TEXT REFERENCES application_runs(run_id),
                lease_epoch INTEGER NOT NULL DEFAULT 1,
                acquired_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_workspace_leases_expires
                ON workspace_leases(expires_at);

            CREATE TABLE IF NOT EXISTS workspace_lease_takeovers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lease_name TEXT NOT NULL,
                prior_owner TEXT NOT NULL,
                prior_expires_at TEXT NOT NULL,
                new_owner TEXT NOT NULL,
                taken_over_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_workspace_lease_takeovers_name_time
                ON workspace_lease_takeovers(lease_name, taken_over_at);

            CREATE TABLE IF NOT EXISTS workspace_authority (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                control_db_id TEXT NOT NULL UNIQUE,
                storage_identity TEXT,
                authority_ledger_id TEXT,
                authority_epoch INTEGER NOT NULL DEFAULT 1,
                lease_epoch_counter INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspace_authority_handoffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                control_db_id TEXT NOT NULL,
                prior_storage_identity TEXT NOT NULL,
                new_storage_identity TEXT NOT NULL,
                new_owner TEXT NOT NULL,
                prior_authority_epoch INTEGER NOT NULL DEFAULT 1,
                new_authority_epoch INTEGER NOT NULL DEFAULT 1,
                authorized_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS artifact_dependencies (
                artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                input_hash TEXT NOT NULL,
                input_path TEXT,
                source_kind TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (artifact_id, input_hash)
            );

            CREATE INDEX IF NOT EXISTS idx_artifact_dependencies_artifact_input
                ON artifact_dependencies(artifact_id, input_hash);
        """)
        resource_lock_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(resource_locks)")
        }
        if "lease_id" not in resource_lock_columns:
            conn.execute("ALTER TABLE resource_locks ADD COLUMN lease_id TEXT")
        workspace_lease_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(workspace_leases)")
        }
        if "lease_epoch" not in workspace_lease_columns:
            conn.execute(
                "ALTER TABLE workspace_leases "
                "ADD COLUMN lease_epoch INTEGER NOT NULL DEFAULT 1"
            )
        authority_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(workspace_authority)")
        }
        if "storage_identity" not in authority_columns:
            conn.execute("ALTER TABLE workspace_authority ADD COLUMN storage_identity TEXT")
        if "authority_epoch" not in authority_columns:
            conn.execute(
                "ALTER TABLE workspace_authority "
                "ADD COLUMN authority_epoch INTEGER NOT NULL DEFAULT 1"
            )
        if "authority_ledger_id" not in authority_columns:
            conn.execute(
                "ALTER TABLE workspace_authority ADD COLUMN authority_ledger_id TEXT"
            )
        if "lease_epoch_counter" not in authority_columns:
            conn.execute(
                "ALTER TABLE workspace_authority "
                "ADD COLUMN lease_epoch_counter INTEGER NOT NULL DEFAULT 0"
            )
        handoff_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(workspace_authority_handoffs)")
        }
        if "prior_authority_epoch" not in handoff_columns:
            conn.execute(
                "ALTER TABLE workspace_authority_handoffs "
                "ADD COLUMN prior_authority_epoch INTEGER NOT NULL DEFAULT 1"
            )
        if "new_authority_epoch" not in handoff_columns:
            conn.execute(
                "ALTER TABLE workspace_authority_handoffs "
                "ADD COLUMN new_authority_epoch INTEGER NOT NULL DEFAULT 1"
            )
        storage_identity = self.physical_storage_identity()
        conn.execute(
            """INSERT OR IGNORE INTO workspace_authority
               (singleton_id, control_db_id, storage_identity, created_at)
               VALUES (1, ?, ?, ?)""",
            (
                f"control_{uuid4().hex}",
                storage_identity,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.execute(
            """UPDATE workspace_authority SET storage_identity = ?
               WHERE singleton_id = 1
                 AND (storage_identity IS NULL OR storage_identity = '')""",
            (storage_identity,),
        )
        conn.commit()
        if verify_authority_ledger:
            self._verify_configured_authority_ledger()

    def control_db_identity(self) -> str:
        row = self.fetch_one(
            "SELECT control_db_id FROM workspace_authority WHERE singleton_id = 1"
        )
        if row is None or not row.get("control_db_id"):
            raise RuntimeError("authoritative control database identity is missing")
        return str(row["control_db_id"])

    def physical_storage_identity(self) -> str:
        """Bind authority to this physical DB copy, not only copied bytes."""
        if str(self.db_path) == ":memory:":
            return hashlib.sha256(f"memory:{id(self)}".encode("utf-8")).hexdigest()
        path = self.db_path.resolve()
        stat = path.stat()
        machine = platform.node() or "unknown-host"
        machine_id = Path("/etc/machine-id")
        if machine_id.is_file():
            try:
                machine = machine_id.read_text(encoding="utf-8").strip() or machine
            except OSError:
                pass
        raw = f"{machine}\0{path}\0{stat.st_dev}\0{stat.st_ino}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def assert_authoritative_storage(self) -> str:
        row = self.fetch_one(
            """SELECT control_db_id, storage_identity, authority_ledger_id,
                      authority_epoch
               FROM workspace_authority
               WHERE singleton_id = 1"""
        )
        if row is None or not row.get("storage_identity"):
            raise ValueError("authoritative control database storage identity is missing")
        actual = self.physical_storage_identity()
        if str(row["storage_identity"]) != actual:
            raise ValueError(
                "physical control database copy is not authoritative; "
                "an explicit storage handoff is required"
            )
        if self.authority_ledger_path is not None:
            ledger = self._read_authority_ledger()
            if str(ledger.get("control_db_id") or "") != str(row["control_db_id"]):
                raise ValueError("shared authority ledger control database mismatch")
            if str(ledger.get("ledger_id") or "") != str(
                row.get("authority_ledger_id") or ""
            ):
                raise ValueError("shared authority ledger provenance mismatch")
            local_epoch = int(row.get("authority_epoch") or 0)
            ledger_epoch = int(ledger.get("authority_epoch") or 0)
            if local_epoch != ledger_epoch:
                raise ValueError(
                    "authority epoch revoked for this physical control database copy"
                )
            if str(ledger.get("storage_identity") or "") != actual:
                raise ValueError(
                    "shared authority ledger designates another physical control database copy"
                )
        return actual

    def authorize_storage_handoff(
        self, *, expected_control_db_id: str, new_owner: str
    ) -> str:
        """Explicitly bind a stopped/expired copied DB to its new storage."""
        expected = str(expected_control_db_id or "").strip()
        owner = str(new_owner or "").strip()
        if not expected or not owner:
            raise ValueError("control database identity and new owner are required")
        if self.authority_ledger_path is None:
            raise ValueError(
                "CAREER_AUTHORITY_LEDGER_PATH is required for cross-storage handoff"
            )
        actual = self.physical_storage_identity()
        now = datetime.now(UTC).isoformat()
        with self.authority_ledger_lock():
            ledger = self._read_authority_ledger()
            with self.transaction(immediate=True) as conn:
                authority = conn.execute(
                    """SELECT control_db_id, storage_identity, authority_ledger_id,
                              authority_epoch
                       FROM workspace_authority WHERE singleton_id = 1"""
                ).fetchone()
                if authority is None or str(authority["control_db_id"]) != expected:
                    raise ValueError(
                        "authoritative control database identity does not match"
                    )
                if str(ledger.get("control_db_id") or "") != expected:
                    raise ValueError("shared authority ledger identity does not match")
                if str(ledger.get("ledger_id") or "") != str(
                    authority["authority_ledger_id"] or ""
                ):
                    raise ValueError("shared authority ledger provenance mismatch")
                local_epoch = int(authority["authority_epoch"] or 0)
                ledger_epoch = int(ledger.get("authority_epoch") or 0)
                if local_epoch != ledger_epoch:
                    raise ValueError("handoff source authority epoch is stale")
                prior = str(authority["storage_identity"] or "")
                if str(ledger.get("storage_identity") or "") != prior:
                    raise ValueError("handoff source storage authority is stale")
                active = conn.execute(
                    """SELECT worker_id, expires_at FROM workspace_leases
                       WHERE lease_name = 'authoritative-workspace'"""
                ).fetchone()
                if active is not None and str(active["expires_at"]) > now:
                    raise RuntimeError(
                        "cannot authorize storage handoff while workspace lease is active"
                    )
                new_epoch = local_epoch + 1
                if prior != actual:
                    conn.execute(
                        """INSERT INTO workspace_authority_handoffs
                           (control_db_id, prior_storage_identity,
                            new_storage_identity, new_owner,
                            prior_authority_epoch, new_authority_epoch,
                            authorized_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            expected,
                            prior,
                            actual,
                            owner,
                            local_epoch,
                            new_epoch,
                            now,
                        ),
                    )
                    conn.execute(
                        """UPDATE workspace_authority
                           SET storage_identity = ?, authority_epoch = ?
                           WHERE singleton_id = 1""",
                        (actual, new_epoch),
                    )
                else:
                    new_epoch = local_epoch
            self._write_authority_ledger(
                {
                    **ledger,
                    "control_db_id": expected,
                    "authority_epoch": new_epoch,
                    "storage_identity": actual,
                    "owner": owner,
                    "updated_at": now,
                }
            )
        return actual

    def provision_authority_ledger(
        self, *, expected_control_db_id: str, provisioned_by: str
    ) -> dict:
        """Explicitly bind an unbound authoritative DB to one shared ledger.

        Provisioning is deliberately separate from ``init_schema`` so a copied
        SQLite database cannot silently create an independent authority plane.
        Once the ledger id is persisted in SQLite, another ledger cannot be
        provisioned from a byte copy of that database.
        """
        if self.authority_ledger_path is None:
            raise ValueError("CAREER_AUTHORITY_LEDGER_PATH is required for provisioning")
        expected = str(expected_control_db_id or "").strip()
        actor = str(provisioned_by or "").strip()
        if not expected or not actor:
            raise ValueError("control database identity and provisioner are required")
        with self.authority_ledger_lock():
            if self.authority_ledger_path.exists():
                raise ValueError("shared authority ledger already exists")
            row = self.fetch_one(
                """SELECT control_db_id, storage_identity, authority_ledger_id,
                          authority_epoch
                   FROM workspace_authority WHERE singleton_id = 1"""
            )
            if row is None or str(row.get("control_db_id") or "") != expected:
                raise ValueError("authoritative control database identity does not match")
            if str(row.get("authority_ledger_id") or ""):
                raise ValueError(
                    "database is already bound to a pre-provisioned shared authority ledger"
                )
            actual = self.physical_storage_identity()
            if str(row.get("storage_identity") or "") != actual:
                raise ValueError("physical control database copy is not authoritative")
            now = datetime.now(UTC).isoformat()
            ledger_id = f"ledger_{uuid4().hex}"
            payload = {
                "kind": self.AUTHORITY_LEDGER_KIND,
                "schema_version": self.AUTHORITY_LEDGER_VERSION,
                "ledger_id": ledger_id,
                "control_db_id": expected,
                "authority_epoch": int(row.get("authority_epoch") or 1),
                "storage_identity": actual,
                "owner": actor,
                "provisioned_by": actor,
                "provisioned_at": now,
                "updated_at": now,
            }
            self._write_authority_ledger(payload)
            with self.transaction(immediate=True) as conn:
                updated = conn.execute(
                    """UPDATE workspace_authority SET authority_ledger_id = ?
                       WHERE singleton_id = 1
                         AND control_db_id = ?
                         AND (authority_ledger_id IS NULL OR authority_ledger_id = '')""",
                    (ledger_id, expected),
                ).rowcount
                if updated != 1:
                    raise RuntimeError("authority ledger binding raced with another provisioner")
            return dict(payload)

    def _verify_configured_authority_ledger(self) -> None:
        if self.authority_ledger_path is None:
            return
        with self.authority_ledger_lock():
            if not self.authority_ledger_path.is_file():
                raise ValueError(
                    "shared authority ledger is missing; it must be pre-provisioned"
                )
            ledger = self._read_authority_ledger()
            row = self.fetch_one(
                """SELECT control_db_id, authority_ledger_id
                   FROM workspace_authority WHERE singleton_id = 1"""
            )
            if row is None:
                raise RuntimeError("workspace authority row is missing")
            if str(row.get("authority_ledger_id") or "") != str(
                ledger.get("ledger_id") or ""
            ):
                raise ValueError("shared authority ledger provenance mismatch")
            if str(row.get("control_db_id") or "") != str(
                ledger.get("control_db_id") or ""
            ):
                raise ValueError("shared authority ledger control database mismatch")

    @contextmanager
    def authority_ledger_lock(self) -> Iterator[None]:
        """Serialize shared-ledger handoff/finalization across workspace copies."""
        if self.authority_ledger_path is None:
            yield
            return
        depth = int(getattr(self._authority_lock_state, "depth", 0))
        if depth:
            self._authority_lock_state.depth = depth + 1
            try:
                yield
            finally:
                self._authority_lock_state.depth -= 1
            return
        import fcntl

        lock_path = self.authority_ledger_path.with_suffix(
            self.authority_ledger_path.suffix + ".lock"
        )
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            self._authority_lock_state.depth = 1
            try:
                yield
            finally:
                self._authority_lock_state.depth = 0
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _read_authority_ledger(self) -> dict:
        if self.authority_ledger_path is None:
            raise ValueError("shared authority ledger is not configured")
        try:
            payload = json.loads(
                self.authority_ledger_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("shared authority ledger is missing or invalid") from exc
        if not isinstance(payload, dict):
            raise ValueError("shared authority ledger is invalid")
        if (
            payload.get("kind") != self.AUTHORITY_LEDGER_KIND
            or payload.get("schema_version") != self.AUTHORITY_LEDGER_VERSION
            or not str(payload.get("ledger_id") or "").startswith("ledger_")
            or not str(payload.get("control_db_id") or "").startswith("control_")
            or int(payload.get("authority_epoch") or 0) <= 0
            or not str(payload.get("storage_identity") or "")
            or not str(payload.get("provisioned_by") or "")
            or not str(payload.get("provisioned_at") or "")
        ):
            raise ValueError("shared authority ledger provenance is invalid")
        return payload

    def _write_authority_ledger(self, payload: dict) -> None:
        if self.authority_ledger_path is None:
            raise ValueError("shared authority ledger is not configured")
        self.authority_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_temp = tempfile.mkstemp(
            prefix=f".{self.authority_ledger_path.name}.",
            dir=self.authority_ledger_path.parent,
        )
        temp_path = Path(raw_temp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.authority_ledger_path)
            directory_fd = os.open(self.authority_ledger_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temp_path.unlink(missing_ok=True)

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        conn = self.get_connection()
        conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        try:
            yield conn
        except BaseException:
            conn.rollback()
            raise
        else:
            conn.commit()

    def execute(self, sql: str, params: tuple | None = None) -> sqlite3.Cursor:
        conn = self.get_connection()
        cursor = conn.execute(sql, params or ())
        conn.commit()
        return cursor

    def fetch_all(self, sql: str, params: tuple | None = None) -> list[dict]:
        conn = self.get_connection()
        rows = conn.execute(sql, params or ()).fetchall()
        return [dict(row) for row in rows]

    def fetch_one(self, sql: str, params: tuple | None = None) -> dict | None:
        conn = self.get_connection()
        row = conn.execute(sql, params or ()).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
