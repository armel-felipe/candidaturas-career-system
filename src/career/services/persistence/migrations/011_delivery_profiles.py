from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "applications"):
        return
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(applications)").fetchall()
    }
    if "delivery_profile" not in columns:
        conn.execute(
            "ALTER TABLE applications ADD COLUMN delivery_profile TEXT NOT NULL DEFAULT 'standard_cv'"
        )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_applications_delivery_profile
           ON applications(delivery_profile)"""
    )


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None
