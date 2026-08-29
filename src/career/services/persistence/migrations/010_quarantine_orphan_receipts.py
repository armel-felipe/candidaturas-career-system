"""Quarantine historical receipts that cannot prove their candidature scope."""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS quarantined_validation_receipts (
            receipt_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            attempt INTEGER NOT NULL,
            validator TEXT NOT NULL,
            result TEXT NOT NULL,
            report_path TEXT,
            report_sha256 TEXT,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            application_id TEXT,
            gate TEXT,
            input_hash TEXT,
            output_hash TEXT,
            application_fingerprint TEXT,
            revision_id TEXT,
            reason TEXT NOT NULL,
            quarantined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        """INSERT OR IGNORE INTO quarantined_validation_receipts
           (receipt_id, run_id, node_id, attempt, validator, result,
            report_path, report_sha256, details_json, created_at,
            application_id, gate, input_hash, output_hash,
            application_fingerprint, revision_id, reason)
           SELECT receipt_id, run_id, node_id, attempt, validator, result,
                  report_path, report_sha256, details_json, created_at,
                  application_id, gate, input_hash, output_hash,
                  application_fingerprint, revision_id,
                  CASE
                    WHEN application_id IS NULL OR trim(application_id) = ''
                      THEN 'missing_scope:application_id'
                    ELSE 'missing_scope:application_fingerprint'
                  END
             FROM validation_receipts
            WHERE application_id IS NULL
               OR trim(application_id) = ''
               OR application_fingerprint IS NULL
               OR trim(application_fingerprint) = ''"""
    )
    conn.execute(
        """DELETE FROM validation_receipts
            WHERE application_id IS NULL
               OR trim(application_id) = ''
               OR application_fingerprint IS NULL
               OR trim(application_fingerprint) = ''"""
    )
    conn.execute(
        """CREATE TRIGGER IF NOT EXISTS validation_receipts_require_scope_insert
           BEFORE INSERT ON validation_receipts
           WHEN NEW.application_id IS NULL
             OR trim(NEW.application_id) = ''
             OR NEW.application_fingerprint IS NULL
             OR trim(NEW.application_fingerprint) = ''
           BEGIN
             SELECT RAISE(ABORT, 'validation receipt requires application scope and fingerprint');
           END"""
    )
    conn.execute(
        """CREATE TRIGGER IF NOT EXISTS validation_receipts_require_scope_update
           BEFORE UPDATE OF application_id, application_fingerprint ON validation_receipts
           WHEN NEW.application_id IS NULL
             OR trim(NEW.application_id) = ''
             OR NEW.application_fingerprint IS NULL
             OR trim(NEW.application_fingerprint) = ''
           BEGIN
             SELECT RAISE(ABORT, 'validation receipt requires application scope and fingerprint');
           END"""
    )
