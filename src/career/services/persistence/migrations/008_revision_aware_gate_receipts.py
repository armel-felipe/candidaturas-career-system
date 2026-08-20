from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "validation_receipts"):
        return

    _add_column_if_missing(
        conn,
        "validation_receipts",
        "revision_id",
        "TEXT REFERENCES fit_map_revisions(revision_id) ON DELETE CASCADE",
    )
    if _table_exists(conn, "gate_dependencies"):
        conn.execute(
            """
            UPDATE validation_receipts
               SET revision_id = (
                   SELECT gd.dependency_id
                     FROM gate_dependencies AS gd
                    WHERE gd.receipt_id = validation_receipts.receipt_id
                      AND gd.dependency_type = 'fit_map_revision'
                    ORDER BY gd.id DESC
                    LIMIT 1
               )
             WHERE revision_id IS NULL
            """
        )

    conn.execute("DROP INDEX IF EXISTS idx_validation_receipts_idempotency")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_validation_receipts_idempotency_unbound
            ON validation_receipts(application_id, gate, input_hash, output_hash)
            WHERE application_id IS NOT NULL
              AND gate IS NOT NULL
              AND input_hash IS NOT NULL
              AND output_hash IS NOT NULL
              AND revision_id IS NULL
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_validation_receipts_idempotency_revision
            ON validation_receipts(
                application_id, gate, input_hash, output_hash, revision_id
            )
            WHERE application_id IS NOT NULL
              AND gate IS NOT NULL
              AND input_hash IS NOT NULL
              AND output_hash IS NOT NULL
              AND revision_id IS NOT NULL
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_validation_receipts_revision_gate
            ON validation_receipts(revision_id, gate, created_at)
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
