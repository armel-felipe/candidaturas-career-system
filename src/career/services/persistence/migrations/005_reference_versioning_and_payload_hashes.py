from __future__ import annotations

import hashlib
import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "reference_documents", "logical_key", "TEXT")
    _add_column_if_missing(conn, "reference_documents", "content_hash", "TEXT")
    _add_column_if_missing(conn, "fit_map_revisions", "payload_hash", "TEXT")
    _add_column_if_missing(conn, "positioning_revisions", "payload_hash", "TEXT")

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_reference_documents_kind_logical_key_created
            ON reference_documents(kind, logical_key, created_at);

        CREATE INDEX IF NOT EXISTS idx_reference_documents_kind_logical_key_content_hash
            ON reference_documents(kind, logical_key, content_hash);

        CREATE INDEX IF NOT EXISTS idx_fit_map_revisions_payload_hash
            ON fit_map_revisions(payload_hash);

        CREATE INDEX IF NOT EXISTS idx_positioning_revisions_payload_hash
            ON positioning_revisions(payload_hash);

        CREATE TABLE IF NOT EXISTS keyword_translation_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_id TEXT REFERENCES reference_documents(reference_id) ON DELETE CASCADE,
            keyword TEXT NOT NULL,
            locale TEXT NOT NULL,
            translation TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(keyword, locale, content_hash, source_hash)
        );

        CREATE INDEX IF NOT EXISTS idx_keyword_translation_versions_reference
            ON keyword_translation_versions(reference_id, keyword, locale);

        CREATE INDEX IF NOT EXISTS idx_keyword_translation_versions_keyword_locale
            ON keyword_translation_versions(keyword, locale, created_at);
        """
    )

    for row in conn.execute(
        "SELECT reference_id, reference_key, content FROM reference_documents"
    ).fetchall():
        reference_key = str(row[1] or "")
        logical_key = _logical_key(reference_key)
        content_hash = _sha256_text(str(row[2] or ""))
        conn.execute(
            """UPDATE reference_documents
               SET logical_key = ?, content_hash = ?
               WHERE reference_id = ?""",
            (logical_key, content_hash, row[0]),
        )

    for row in conn.execute(
        "SELECT revision_id, payload_json FROM fit_map_revisions"
    ).fetchall():
        conn.execute(
            "UPDATE fit_map_revisions SET payload_hash = ? WHERE revision_id = ?",
            (_sha256_text(str(row[1] or "")), row[0]),
        )

    for row in conn.execute(
        "SELECT revision_id, payload_json FROM positioning_revisions"
    ).fetchall():
        conn.execute(
            "UPDATE positioning_revisions SET payload_hash = ? WHERE revision_id = ?",
            (_sha256_text(str(row[1] or "")), row[0]),
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
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
        )


def _logical_key(reference_key: str) -> str:
    if "#" not in reference_key:
        return reference_key
    return reference_key.rsplit("#", 1)[0]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
