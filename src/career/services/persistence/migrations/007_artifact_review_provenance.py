from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    if _table_exists(conn, "artifact_versions"):
        _add_column_if_missing(conn, "artifact_versions", "size_bytes", "INTEGER")
        _add_column_if_missing(conn, "artifact_versions", "text_content_hash", "TEXT")
        _add_column_if_missing(
            conn,
            "artifact_versions",
            "review_receipt_id",
            "TEXT REFERENCES validation_receipts(receipt_id) ON DELETE SET NULL",
        )
        _add_column_if_missing(conn, "artifact_versions", "review_report_path", "TEXT")
        _add_column_if_missing(conn, "artifact_versions", "review_report_hash", "TEXT")
        _add_column_if_missing(conn, "artifact_versions", "reviewed_at", "TEXT")

        conn.execute(
            """
            UPDATE artifact_versions
               SET size_bytes = COALESCE(size_bytes, 0)
             WHERE size_bytes IS NULL
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_artifact_versions_source_revision
                ON artifact_versions(application_id, source_revision_id, created_at)
            """
        )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS artifact_version_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id TEXT NOT NULL REFERENCES artifact_versions(version_id) ON DELETE CASCADE,
            dependency_type TEXT NOT NULL,
            dependency_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(version_id, dependency_type, dependency_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_artifact_version_dependencies_version
            ON artifact_version_dependencies(version_id, dependency_type)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_artifact_version_dependencies_type_id
            ON artifact_version_dependencies(dependency_type, dependency_id)
        """
    )


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    columns = {
        row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None
