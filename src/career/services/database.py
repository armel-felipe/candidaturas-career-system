from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from career.paths import CAREER_STATE


class Database:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or os.path.join(CAREER_STATE, "career.db"))
        self._conn: sqlite3.Connection | None = None

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_schema(self) -> None:
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
                created_at TEXT NOT NULL
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
        conn.execute(
            """INSERT OR IGNORE INTO workspace_authority
               (singleton_id, control_db_id, created_at) VALUES (1, ?, ?)""",
            (f"control_{uuid4().hex}", datetime.now(UTC).isoformat()),
        )
        conn.commit()

    def control_db_identity(self) -> str:
        row = self.fetch_one(
            "SELECT control_db_id FROM workspace_authority WHERE singleton_id = 1"
        )
        if row is None or not row.get("control_db_id"):
            raise RuntimeError("authoritative control database identity is missing")
        return str(row["control_db_id"])

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
