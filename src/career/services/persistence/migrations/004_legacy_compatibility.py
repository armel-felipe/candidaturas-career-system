from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "resource_locks", "lease_id", "TEXT")
    _add_column_if_missing(
        conn,
        "workspace_leases",
        "lease_epoch",
        "INTEGER NOT NULL DEFAULT 1",
    )
    _add_column_if_missing(conn, "workspace_authority", "storage_identity", "TEXT")
    _add_column_if_missing(
        conn,
        "workspace_authority",
        "authority_epoch",
        "INTEGER NOT NULL DEFAULT 1",
    )
    _add_column_if_missing(
        conn,
        "workspace_authority",
        "authority_ledger_id",
        "TEXT",
    )
    _add_column_if_missing(
        conn,
        "workspace_authority",
        "lease_epoch_counter",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        conn,
        "workspace_authority_handoffs",
        "prior_authority_epoch",
        "INTEGER NOT NULL DEFAULT 1",
    )
    _add_column_if_missing(
        conn,
        "workspace_authority_handoffs",
        "new_authority_epoch",
        "INTEGER NOT NULL DEFAULT 1",
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
