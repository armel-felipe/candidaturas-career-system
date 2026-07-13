from __future__ import annotations

import os
import sqlite3
from pathlib import Path

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
        """)
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
