from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "validation_receipts"):
        return

    _add_column_if_missing(
        conn,
        "validation_receipts",
        "application_id",
        "TEXT REFERENCES applications(id) ON DELETE CASCADE",
    )
    _add_column_if_missing(conn, "validation_receipts", "gate", "TEXT")
    _add_column_if_missing(conn, "validation_receipts", "input_hash", "TEXT")
    _add_column_if_missing(conn, "validation_receipts", "output_hash", "TEXT")
    _add_column_if_missing(
        conn, "validation_receipts", "application_fingerprint", "TEXT"
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_validation_receipts_application_gate_created
            ON validation_receipts(application_id, gate, created_at)
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_validation_receipts_idempotency
            ON validation_receipts(application_id, gate, input_hash, output_hash)
            WHERE application_id IS NOT NULL
              AND gate IS NOT NULL
              AND input_hash IS NOT NULL
              AND output_hash IS NOT NULL
        """
    )
    if _table_exists(conn, "gate_dependencies"):
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gate_dependencies_type_id
                ON gate_dependencies(dependency_type, dependency_id)
            """
        )

    conn.execute(
        """
        UPDATE validation_receipts
           SET application_id = COALESCE(
               application_id,
               (SELECT application_id
                  FROM application_runs
                 WHERE application_runs.run_id = validation_receipts.run_id)
           )
         WHERE application_id IS NULL
        """
    )
    conn.execute(
        """
        UPDATE validation_receipts
           SET gate = COALESCE(gate, node_id)
         WHERE gate IS NULL OR gate = ''
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
