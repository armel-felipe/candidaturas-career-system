from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from career.services.database import Database
from career.services.persistence.application_repository import (
    ApplicationNotFoundError,
    ApplicationRepository,
)
from career.utils import utc_now_iso


VALIDATOR_TO_GATE = {
    "project.save_job_description": "job_description_saved",
    "fit_map.template": "fit_map_template_ready",
    "fit_map.validate_draft": "fit_map_draft_valid",
    "fit_map.build": "fit_map_built",
    "fit_map.score": "fit_map_scored",
    "fit_map.validate": "fit_map_validated",
    "cv.review": "cv_review_passed",
    "cv.approve": "cv_review_passed",
    "project.diagnose_runtime": "runtime_diagnosed",
    "memory.build": "memory_bundle_ready",
    "registry.rebuild": "keyword_registry_ready",
}

GATE_PREREQUISITES = {
    "fit_map_built": ("fit_map_draft_valid", False),
    "fit_map_scored": ("fit_map_built", True),
    "fit_map_validated": ("fit_map_scored", True),
    "cv_review_passed": ("fit_map_validated", True),
}

REVISION_BOUND_GATES = {
    "fit_map_built",
    "fit_map_scored",
    "fit_map_validated",
    "cv_review_passed",
}


@dataclass(frozen=True)
class GateReceipt:
    application_id: str
    application_fingerprint: str
    run_id: str
    gate: str
    validator: str
    input_hash: str
    output_hash: str
    revision_id: str | None = None


class GateRepository:
    def __init__(self, database: Database) -> None:
        self.database = database
        self._schema_ready = False
        self._applications = ApplicationRepository(database)

    def record(
        self,
        receipt: GateReceipt,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        self._ensure_schema()
        application_id = self._required_text(receipt.application_id, "application_id")
        application_fingerprint = self._required_text(
            receipt.application_fingerprint, "application_fingerprint"
        )
        run_id = self._required_text(receipt.run_id, "run_id")
        gate = self._required_text(receipt.gate, "gate")
        validator = self._required_text(receipt.validator, "validator")
        input_hash = self._required_text(receipt.input_hash, "input_hash")
        output_hash = self._required_text(receipt.output_hash, "output_hash")
        expected_gate = VALIDATOR_TO_GATE.get(validator)
        if expected_gate is None:
            raise ValueError(f"unknown validator: {validator}")
        if gate != expected_gate:
            raise ValueError(
                f"validator {validator} can only record gate {expected_gate}"
            )
        application = self._resolve_application(application_id)
        if not application.fingerprint:
            raise ValueError(
                f"application {application_id} does not have a current fingerprint"
            )
        if application.fingerprint != application_fingerprint:
            raise ValueError(
                "application fingerprint mismatch for recorded gate receipt"
            )
        revision_id = receipt.revision_id
        if gate in REVISION_BOUND_GATES:
            revision_id = self._required_text(revision_id, "revision_id")
            self._ensure_revision_matches_application(
                application_id, revision_id, conn=conn
            )
        elif revision_id:
            raise ValueError(f"gate {gate} does not accept a revision binding")

        prerequisite = GATE_PREREQUISITES.get(gate)
        if prerequisite is not None:
            required_gate, bind_revision = prerequisite
            required_revision = revision_id if bind_revision else None
            if not self.is_satisfied(
                application_id,
                required_gate,
                revision_id=required_revision,
                conn=conn,
            ):
                raise ValueError(
                    f"gate {gate} is missing prerequisite receipt {required_gate}"
                )

        existing_query, existing_parameters = self._existing_receipt_query(
            application_id=application_id,
            gate=gate,
            input_hash=input_hash,
            output_hash=output_hash,
            application_fingerprint=application_fingerprint,
            revision_id=revision_id,
        )
        created_at = utc_now_iso()
        receipt_id = f"gate_{uuid4().hex}"
        node_id = gate
        details_json = json.dumps(
            {
                "gate": gate,
                "application_fingerprint": application_fingerprint,
                "input_hash": input_hash,
                "output_hash": output_hash,
                "revision_id": revision_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        def persist(target: sqlite3.Connection) -> str:
            existing = target.execute(
                existing_query, existing_parameters
            ).fetchone()
            if existing is not None:
                return str(existing["receipt_id"])

            self._ensure_run(target, application_id, run_id, created_at)
            attempt = self._ensure_node_and_next_attempt(
                target, run_id, node_id, created_at
            )
            target.execute(
                """
                INSERT INTO validation_receipts
                    (receipt_id, application_id, run_id, node_id, attempt, validator,
                     gate, result, report_path, report_sha256, details_json, created_at,
                     input_hash, output_hash, application_fingerprint, revision_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    application_id,
                    run_id,
                    node_id,
                    attempt,
                    validator,
                    gate,
                    "passed",
                    details_json,
                    created_at,
                    input_hash,
                    output_hash,
                    application_fingerprint,
                    revision_id,
                ),
            )
            if revision_id:
                target.execute(
                    """
                    INSERT INTO gate_dependencies
                        (receipt_id, dependency_type, dependency_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (receipt_id, "fit_map_revision", revision_id, created_at),
                )
            return receipt_id

        if conn is not None:
            return persist(conn)
        with self.database.transaction(immediate=True) as transaction:
            return persist(transaction)

    def is_satisfied(
        self,
        application_id: str,
        gate: str,
        revision_id: str | None = None,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> bool:
        self._ensure_schema()
        application_id = self._required_text(application_id, "application_id")
        gate = self._required_text(gate, "gate")
        application = self._resolve_application(application_id)
        if not application.fingerprint:
            return False
        if revision_id:
            row = self._fetch_one(
                conn,
                """
                SELECT vr.receipt_id
                  FROM validation_receipts AS vr
                 WHERE vr.application_id = ?
                   AND vr.gate = ?
                   AND vr.result = 'passed'
                   AND vr.application_fingerprint = ?
                   AND vr.revision_id = ?
                 ORDER BY vr.created_at DESC, vr.receipt_id DESC
                 LIMIT 1
                """,
                (application_id, gate, application.fingerprint, revision_id),
            )
            return row is not None
        row = self._fetch_one(
            conn,
            """
            SELECT receipt_id
              FROM validation_receipts
             WHERE application_id = ?
               AND gate = ?
               AND result = 'passed'
               AND application_fingerprint = ?
             ORDER BY created_at DESC, receipt_id DESC
             LIMIT 1
            """,
            (application_id, gate, application.fingerprint),
        )
        return row is not None

    def next_required_step(self, application_id: str) -> str:
        self._ensure_schema()
        application_id = self._required_text(application_id, "application_id")
        self._resolve_application(application_id)
        if not self.is_satisfied(application_id, "fit_map_draft_valid"):
            return "fill_fit_map_draft"
        current_revision = self._latest_fit_map_revision_id(application_id)
        if current_revision is None:
            return "build_fit_map"
        if not self.is_satisfied(
            application_id, "fit_map_built", revision_id=current_revision
        ):
            return "build_fit_map"
        if not self.is_satisfied(
            application_id, "fit_map_scored", revision_id=current_revision
        ):
            return "score_fit_map"
        if not self.is_satisfied(
            application_id, "fit_map_validated", revision_id=current_revision
        ):
            return "validate_fit_map"
        return "build_cv"

    def compatibility_payload(self, application_id: str) -> dict[str, Any]:
        self._ensure_schema()
        application = self._resolve_application(application_id)
        rows = self._list_receipts(application_id)
        completed_states = sorted({str(row["gate"]) for row in rows if row.get("gate")})
        task_history = []
        fingerprints: dict[str, dict[str, Any]] = {}
        for row in rows:
            validator = str(row["validator"])
            state = str(row["gate"])
            entry = {
                "task": validator,
                "state": state,
                "status": "ok",
                "started_at": str(row["created_at"]),
                "finished_at": str(row["created_at"]),
                "duration_ms": 0,
                "summary": f"{validator} recorded gate {state}",
                "artifact_paths": [],
                "input_fingerprint": str(row["input_hash"]),
                "output_fingerprint": str(row["output_hash"]),
                "revision_id": row.get("revision_id"),
                "receipt_id": str(row["receipt_id"]),
            }
            task_history.append(entry)
            fingerprints[validator] = {
                "input": str(row["input_hash"]),
                "output": str(row["output_hash"]),
                "status": "ok",
                "state": state,
                "active_job_fingerprint": str(row["application_fingerprint"]),
                "receipt_id": str(row["receipt_id"]),
            }
        active_intake = None
        if application.job_description_path:
            source_id = application.notion_id or application.aliases.get(
                f"{application.source_type}_source_id"
            )
            active_intake = {
                "application_id": application.application_id,
                "source_type": application.source_type,
                "source_id": source_id,
                "company": application.company,
                "role": application.role,
                "job_description_path": application.job_description_path,
                "fingerprint": application.fingerprint,
                "status": "job_description_saved",
                "next_required_step": self.next_required_step(application_id),
            }
        return {
            "application_id": application.application_id,
            "completed_states": completed_states,
            "task_history": task_history,
            "fingerprints": fingerprints,
            "active_job": {
                "application_id": application.application_id,
                "fingerprint": application.fingerprint,
                "company": application.company,
                "role": application.role,
                "source": "sqlite_projection",
            },
            "active_intake": active_intake,
            "next_required_step": self.next_required_step(application_id),
        }

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        self._applications.ensure_schema()
        self._schema_ready = True

    def ensure_schema(self) -> None:
        self._ensure_schema()

    def _resolve_application(self, application_id: str):
        try:
            return self._applications.resolve(application_id=application_id)
        except ApplicationNotFoundError as exc:
            raise ValueError(f"unknown application: {application_id}") from exc

    def _ensure_revision_matches_application(
        self,
        application_id: str,
        revision_id: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        row = self._fetch_one(
            conn,
            """
            SELECT revision_id, application_revision_id, fingerprint
              FROM fit_map_revisions
             WHERE revision_id = ? AND application_id = ?
            """,
            (revision_id, application_id),
        )
        if row is None:
            raise ValueError(
                f"revision {revision_id} does not belong to application {application_id}"
            )
        application = self._resolve_application(application_id)
        current_application_revision_id = self._applications.get_current_revision_id(
            application_id
        )
        if (
            not current_application_revision_id
            or str(row["application_revision_id"] or "")
            != current_application_revision_id
            or str(row["fingerprint"] or "") != str(application.fingerprint or "")
        ):
            raise ValueError(
                "revision does not belong to the current application source revision"
            )

    def _ensure_run(
        self, conn, application_id: str, run_id: str, created_at: str
    ) -> None:
        existing = conn.execute(
            "SELECT application_id FROM application_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if existing is not None:
            if str(existing["application_id"]) != application_id:
                raise ValueError(
                    f"run_id {run_id} already belongs to another application"
                )
            conn.execute(
                "UPDATE application_runs SET updated_at = ? WHERE run_id = ?",
                (created_at, run_id),
            )
            return
        conn.execute(
            """
            INSERT INTO application_runs
                (run_id, application_id, graph_json, status, contract_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                application_id,
                "{}",
                "completed",
                "gate-receipt-v1",
                created_at,
                created_at,
            ),
        )

    @staticmethod
    def _existing_receipt_query(
        *,
        application_id: str,
        gate: str,
        input_hash: str,
        output_hash: str,
        application_fingerprint: str,
        revision_id: str | None,
    ) -> tuple[str, tuple[str, ...]]:
        parameters = (
            application_id,
            gate,
            input_hash,
            output_hash,
            application_fingerprint,
        )
        if revision_id:
            return (
                """SELECT vr.receipt_id
                     FROM validation_receipts AS vr
                    WHERE vr.application_id = ?
                      AND vr.gate = ?
                      AND vr.input_hash = ?
                      AND vr.output_hash = ?
                      AND vr.application_fingerprint = ?
                      AND vr.revision_id = ?
                    LIMIT 1""",
                (*parameters, revision_id),
            )
        return (
            """SELECT receipt_id
                 FROM validation_receipts
                WHERE application_id = ?
                  AND gate = ?
                  AND input_hash = ?
                  AND output_hash = ?
                  AND application_fingerprint = ?
                  AND revision_id IS NULL
                LIMIT 1""",
            parameters,
        )

    def _ensure_node_and_next_attempt(
        self, conn, run_id: str, node_id: str, created_at: str
    ) -> int:
        existing = conn.execute(
            "SELECT latest_attempt FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (run_id, node_id),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO cell_nodes
                    (run_id, node_id, status, requires_json, latest_attempt, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, node_id, "completed", "[]", 1, created_at, created_at),
            )
            return 1
        attempt = int(existing["latest_attempt"] or 0) + 1
        conn.execute(
            """
            UPDATE cell_nodes
               SET latest_attempt = ?, status = ?, updated_at = ?
             WHERE run_id = ? AND node_id = ?
            """,
            (attempt, "completed", created_at, run_id, node_id),
        )
        return attempt

    def _latest_fit_map_revision_id(self, application_id: str) -> str | None:
        row = self.database.fetch_one(
            """
            SELECT fit.revision_id
              FROM fit_map_revisions AS fit
              JOIN application_revisions AS app_revision
                ON app_revision.revision_id = fit.application_revision_id
             WHERE fit.application_id = ?
               AND app_revision.revision_id = (
                   SELECT current_revision.revision_id
                     FROM application_revisions AS current_revision
                    WHERE current_revision.application_id = ?
                    ORDER BY current_revision.created_at DESC,
                             current_revision.revision_id DESC
                    LIMIT 1
               )
             ORDER BY fit.created_at DESC, fit.revision_id DESC
             LIMIT 1
            """,
            (application_id, application_id),
        )
        if row is None:
            return None
        return str(row["revision_id"])

    def receipt_for_revision(
        self, application_id: str, gate: str, revision_id: str
    ) -> GateReceipt:
        self._ensure_schema()
        row = self.database.fetch_one(
            """SELECT application_id, application_fingerprint, run_id, gate,
                      validator, input_hash, output_hash, revision_id
                 FROM validation_receipts
                WHERE application_id = ? AND gate = ? AND revision_id = ?
                  AND result = 'passed'
                ORDER BY created_at DESC, receipt_id DESC
                LIMIT 1""",
            (application_id, gate, revision_id),
        )
        if row is None:
            raise ValueError(
                f"revision {revision_id} has no passed receipt for {gate}"
            )
        return GateReceipt(**row)

    def _list_receipts(self, application_id: str) -> list[dict[str, Any]]:
        return self.database.fetch_all(
            """
            SELECT vr.receipt_id, vr.validator, vr.gate, vr.created_at,
                   vr.input_hash, vr.output_hash, vr.application_fingerprint,
                   MAX(CASE WHEN gd.dependency_type = 'fit_map_revision' THEN gd.dependency_id END) AS revision_id
              FROM validation_receipts AS vr
              LEFT JOIN gate_dependencies AS gd
                ON gd.receipt_id = vr.receipt_id
             WHERE vr.application_id = ?
               AND vr.result = 'passed'
             GROUP BY vr.receipt_id, vr.validator, vr.gate, vr.created_at,
                      vr.input_hash, vr.output_hash, vr.application_fingerprint
             ORDER BY vr.created_at ASC, vr.receipt_id ASC
            """,
            (application_id,),
        )

    @staticmethod
    def _required_text(value: str | None, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name} is required")
        return text

    def _fetch_one(
        self,
        conn: sqlite3.Connection | None,
        sql: str,
        parameters: tuple[Any, ...],
    ) -> dict[str, Any] | sqlite3.Row | None:
        if conn is not None:
            return conn.execute(sql, parameters).fetchone()
        return self.database.fetch_one(sql, parameters)
