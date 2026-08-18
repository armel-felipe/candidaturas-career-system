from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import uuid4

from career.schemas.review import CvReviewReportSchema
from career.services.database import Database
from career.services.persistence.application_repository import (
    ApplicationNotFoundError,
    ApplicationRepository,
)
from career.utils import sha256_file, sha256_text, utc_now_iso


DOCX_MIME: Final[str] = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
SUPPORTED_ARTIFACT_KINDS: Final[dict[str, dict[str, object]]] = {
    "cv": {"requires_path": True, "default_mime": DOCX_MIME},
    "cover_letter": {"requires_path": False, "default_mime": "text/markdown"},
    "feras": {"requires_path": False, "default_mime": "text/markdown"},
    "gupy_skills": {"requires_path": False, "default_mime": "text/markdown"},
    "interview_answers": {"requires_path": False, "default_mime": "text/markdown"},
    "networking_message": {"requires_path": False, "default_mime": "text/plain"},
    "presentation": {"requires_path": False, "default_mime": "text/markdown"},
    "story_review": {"requires_path": False, "default_mime": "text/markdown"},
}


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    application_id: str
    kind: str
    run_id: str | None
    path: str | None
    content_hash: str
    mime_type: str | None
    size_bytes: int
    text_content_hash: str | None
    source_revision_id: str
    positioning_revision_id: str | None
    review_receipt_id: str | None
    review_report_path: str | None
    review_report_hash: str | None
    status: str
    created_at: str
    reviewed_at: str | None


@dataclass(frozen=True)
class ValidationResult:
    artifact_id: str
    valid: bool
    reason: str
    path: str | None
    stored_hash: str
    current_hash: str | None


class ArtifactRepository:
    def __init__(self, database: Database) -> None:
        self.database = database
        self._schema_ready = False
        self._applications = ApplicationRepository(database)

    def register(
        self,
        application_id: str,
        kind: str,
        path: Path | None,
        content: str | None,
        source_revision_id: str,
        run_id: str,
    ) -> ArtifactRecord:
        self._ensure_schema()
        application_id = self._required_text(application_id, "application_id")
        kind = self._validate_kind(kind)
        source_revision_id = self._required_text(source_revision_id, "source_revision_id")
        run_id = self._required_text(run_id, "run_id")
        self._resolve_application(application_id)
        self._ensure_source_revision(application_id, source_revision_id)
        self._ensure_validated_source(application_id, source_revision_id)

        kind_config = SUPPORTED_ARTIFACT_KINDS[kind]
        resolved_path = self._normalize_path(
            path,
            require_path=bool(kind_config["requires_path"]),
        )
        if resolved_path is None and content is None:
            raise ValueError("artifact registration requires a path or textual content")

        content_hash = (
            sha256_file(resolved_path)
            if resolved_path is not None
            else sha256_text(self._required_text(content, "content"))
        )
        if content is not None:
            content = self._required_text(content, "content")
        size_bytes = (
            resolved_path.stat().st_size
            if resolved_path is not None
            else len(self._required_text(content, "content").encode("utf-8"))
        )
        text_content_hash = sha256_text(content) if content is not None else None
        mime_type = self._resolve_mime_type(resolved_path, str(kind_config["default_mime"]))
        positioning_revision_id = self._latest_positioning_revision_id(
            application_id,
            source_revision_id,
        )
        path_text = str(resolved_path) if resolved_path is not None else None

        existing = self._find_existing(
            application_id=application_id,
            kind=kind,
            path_text=path_text,
            content_hash=content_hash,
            text_content_hash=text_content_hash,
            source_revision_id=source_revision_id,
            positioning_revision_id=positioning_revision_id,
            run_id=run_id,
        )
        if existing is not None:
            return existing

        created_at = utc_now_iso()
        artifact_id = f"artv_{uuid4().hex}"
        with self.database.transaction(immediate=True) as conn:
            existing_row = self._find_existing_row(
                conn,
                application_id=application_id,
                kind=kind,
                path_text=path_text,
                content_hash=content_hash,
                text_content_hash=text_content_hash,
                source_revision_id=source_revision_id,
                positioning_revision_id=positioning_revision_id,
                run_id=run_id,
            )
            if existing_row is not None:
                return self._row_to_record(existing_row)
            self._ensure_run(conn, application_id, run_id, created_at)
            conn.execute(
                """
                INSERT INTO artifact_versions
                    (version_id, application_id, artifact_id, run_id, kind,
                     source_revision_id, positioning_revision_id, path, content_hash,
                     mime_type, status, created_at, size_bytes, text_content_hash)
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    application_id,
                    run_id,
                    kind,
                    source_revision_id,
                    positioning_revision_id,
                    path_text,
                    content_hash,
                    mime_type,
                    "draft",
                    created_at,
                    size_bytes,
                    text_content_hash,
                ),
            )
            if content is not None:
                conn.execute(
                    """
                    INSERT INTO artifact_contents (version_id, content, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (artifact_id, content, created_at),
                )
            self._attach_dependency_txn(
                conn,
                artifact_id,
                application_id,
                "fit_map_revision",
                source_revision_id,
                created_at,
            )
            if positioning_revision_id is not None:
                self._attach_dependency_txn(
                    conn,
                    artifact_id,
                    application_id,
                    "positioning_revision",
                    positioning_revision_id,
                    created_at,
                )
        return self._load_record(artifact_id)

    def attach_dependency(
        self, artifact_id: str, dependency_type: str, dependency_id: str
    ) -> None:
        self._ensure_schema()
        artifact = self._load_record(artifact_id)
        if artifact.status != "draft":
            raise ValueError("artifact provenance is immutable after review approval")
        created_at = utc_now_iso()
        with self.database.transaction(immediate=True) as conn:
            self._attach_dependency_txn(
                conn,
                artifact.artifact_id,
                artifact.application_id,
                dependency_type,
                dependency_id,
                created_at,
            )

    def validate_path(self, artifact_id: str) -> ValidationResult:
        self._ensure_schema()
        artifact = self._load_record(artifact_id)
        return self._validate_integrity(artifact, require_approved=True)

    def _validate_integrity(
        self,
        artifact: ArtifactRecord,
        *,
        require_approved: bool,
    ) -> ValidationResult:
        provenance_error = self._provenance_error(artifact, require_approved=require_approved)
        if provenance_error is not None:
            return ValidationResult(
                artifact_id=artifact.artifact_id,
                valid=False,
                reason=provenance_error,
                path=artifact.path,
                stored_hash=artifact.content_hash,
                current_hash=None,
            )
        if artifact.path is None:
            review_error = self._review_error(artifact) if require_approved else None
            if review_error is not None:
                return ValidationResult(
                    artifact_id=artifact.artifact_id,
                    valid=False,
                    reason=review_error,
                    path=None,
                    stored_hash=artifact.content_hash,
                    current_hash=None,
                )
            return ValidationResult(
                artifact_id=artifact.artifact_id,
                valid=True,
                reason="no_path",
                path=None,
                stored_hash=artifact.content_hash,
                current_hash=None,
            )
        path = Path(artifact.path)
        if not path.is_file():
            return ValidationResult(
                artifact_id=artifact.artifact_id,
                valid=False,
                reason="artifact_missing",
                path=artifact.path,
                stored_hash=artifact.content_hash,
                current_hash=None,
            )
        current_hash = sha256_file(path)
        if current_hash != artifact.content_hash:
            return ValidationResult(
                artifact_id=artifact.artifact_id,
                valid=False,
                reason="content_hash_mismatch",
                path=artifact.path,
                stored_hash=artifact.content_hash,
                current_hash=current_hash,
            )
        review_error = self._review_error(artifact) if require_approved else None
        if review_error is not None:
            return ValidationResult(
                artifact_id=artifact.artifact_id,
                valid=False,
                reason=review_error,
                path=artifact.path,
                stored_hash=artifact.content_hash,
                current_hash=current_hash,
            )
        return ValidationResult(
            artifact_id=artifact.artifact_id,
            valid=True,
            reason="ok",
            path=artifact.path,
            stored_hash=artifact.content_hash,
            current_hash=current_hash,
        )

    def mark_review_passed(
        self,
        artifact_id: str,
        *,
        receipt_id: str,
        report_path: Path,
    ) -> ArtifactRecord:
        self._ensure_schema()
        artifact = self._load_record(artifact_id)
        validation = self._validate_integrity(artifact, require_approved=False)
        if not validation.valid:
            raise ValueError(
                f"artifact path is no longer valid: {validation.reason}"
            )
        report_path = report_path.resolve()
        if not report_path.is_file():
            raise ValueError("approved review report path does not exist")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        CvReviewReportSchema(report).validate()
        if report.get("approved_for_delivery") is not True:
            raise ValueError("approved review report is required before publishing artifact")
        artifact_path = str(Path(str(report["artifact"])).resolve())
        if artifact.path != artifact_path:
            raise ValueError("approved review report points to a different artifact path")
        report_hash = sha256_file(report_path)
        receipt = self.database.fetch_one(
            """
            SELECT receipt_id, application_id, gate, result, output_hash
              FROM validation_receipts
             WHERE receipt_id = ?
            """,
            (self._required_text(receipt_id, "receipt_id"),),
        )
        if receipt is None:
            raise ValueError("validation receipt does not exist")
        if str(receipt["application_id"]) != artifact.application_id:
            raise ValueError("validation receipt belongs to a different application")
        if str(receipt["gate"]) != "cv_review_passed" or str(receipt["result"]) != "passed":
            raise ValueError("validation receipt is not a passed cv review receipt")
        if str(receipt["output_hash"]) != report_hash:
            raise ValueError("validation receipt output hash does not match review report")
        revision_dependency = self.database.fetch_one(
            """
            SELECT 1
              FROM gate_dependencies
             WHERE receipt_id = ?
               AND dependency_type = 'fit_map_revision'
               AND dependency_id = ?
            """,
            (receipt_id, artifact.source_revision_id),
        )
        if revision_dependency is None:
            raise ValueError("validation receipt is missing the artifact source revision dependency")

        created_at = utc_now_iso()
        with self.database.transaction(immediate=True) as conn:
            self._attach_dependency_txn(
                conn,
                artifact.artifact_id,
                artifact.application_id,
                "validation_receipt",
                receipt_id,
                created_at,
            )
            conn.execute(
                """
                UPDATE artifact_versions
                   SET status = 'review_passed',
                       review_receipt_id = ?,
                       review_report_path = ?,
                       review_report_hash = ?,
                       reviewed_at = ?
                 WHERE version_id = ?
                """,
                (
                    receipt_id,
                    str(report_path),
                    report_hash,
                    created_at,
                    artifact.artifact_id,
                ),
            )
        return self._load_record(artifact.artifact_id)

    def _provenance_error(
        self,
        artifact: ArtifactRecord,
        *,
        require_approved: bool,
    ) -> str | None:
        try:
            self._validate_kind(artifact.kind)
            self._resolve_application(artifact.application_id)
            self._ensure_source_revision(artifact.application_id, artifact.source_revision_id)
        except ValueError as exc:
            return str(exc).replace(" ", "_")

        dependencies = self.database.fetch_all(
            """SELECT dependency_type, dependency_id
                 FROM artifact_version_dependencies
                WHERE version_id = ?""",
            (artifact.artifact_id,),
        )
        dependency_pairs = {
            (str(row["dependency_type"]), str(row["dependency_id"]))
            for row in dependencies
        }
        if ("fit_map_revision", artifact.source_revision_id) not in dependency_pairs:
            return "missing_source_revision_dependency"
        if not self._has_validated_source(
            artifact.application_id, artifact.source_revision_id
        ):
            return "missing_validated_source_receipt"
        if artifact.positioning_revision_id is not None:
            if (
                "positioning_revision",
                artifact.positioning_revision_id,
            ) not in dependency_pairs:
                return "missing_positioning_revision_dependency"
            row = self.database.fetch_one(
                """SELECT 1 FROM positioning_revisions
                     WHERE revision_id = ? AND application_id = ?
                       AND fit_map_revision_id = ?""",
                (
                    artifact.positioning_revision_id,
                    artifact.application_id,
                    artifact.source_revision_id,
                ),
            )
            if row is None:
                return "invalid_positioning_revision_dependency"
        return None

    def _review_error(self, artifact: ArtifactRecord) -> str | None:
        dependencies = self.database.fetch_all(
            """SELECT dependency_type, dependency_id
                 FROM artifact_version_dependencies
                WHERE version_id = ?""",
            (artifact.artifact_id,),
        )
        dependency_pairs = {
            (str(row["dependency_type"]), str(row["dependency_id"]))
            for row in dependencies
        }
        if artifact.status != "review_passed":
            return "unapproved_review"
        if not artifact.review_receipt_id or not artifact.review_report_path or not artifact.review_report_hash:
            return "missing_review_provenance"
        if ("validation_receipt", artifact.review_receipt_id) not in dependency_pairs:
            return "missing_review_receipt_dependency"
        report_path = Path(artifact.review_report_path)
        if not report_path.is_file():
            return "review_report_missing"
        if sha256_file(report_path) != artifact.review_report_hash:
            return "review_report_hash_mismatch"
        receipt = self.database.fetch_one(
            """SELECT gate, result, application_id, output_hash
                 FROM validation_receipts
                WHERE receipt_id = ?""",
            (artifact.review_receipt_id,),
        )
        if receipt is None:
            return "review_receipt_missing"
        if (
            str(receipt["application_id"]) != artifact.application_id
            or str(receipt["gate"]) != "cv_review_passed"
            or str(receipt["result"]) != "passed"
            or str(receipt["output_hash"]) != artifact.review_report_hash
        ):
            return "invalid_review_receipt"
        return None

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        self.database.migrate()
        self._schema_ready = True

    def _resolve_application(self, application_id: str) -> None:
        try:
            self._applications.resolve(application_id=application_id)
        except ApplicationNotFoundError as exc:
            raise ValueError(f"unknown application: {application_id}") from exc

    def _ensure_source_revision(self, application_id: str, source_revision_id: str) -> None:
        row = self.database.fetch_one(
            """
            SELECT revision_id
              FROM fit_map_revisions
             WHERE revision_id = ? AND application_id = ?
            """,
            (source_revision_id, application_id),
        )
        if row is None:
            raise ValueError("source revision is unknown for this application")

    def _ensure_validated_source(self, application_id: str, source_revision_id: str) -> None:
        row = self.database.fetch_one(
            """
            SELECT vr.receipt_id
              FROM validation_receipts AS vr
              JOIN gate_dependencies AS gd
                ON gd.receipt_id = vr.receipt_id
             WHERE vr.application_id = ?
               AND vr.gate = 'fit_map_validated'
               AND vr.result = 'passed'
               AND gd.dependency_type = 'fit_map_revision'
               AND gd.dependency_id = ?
             ORDER BY vr.created_at DESC, vr.receipt_id DESC
             LIMIT 1
            """,
            (application_id, source_revision_id),
        )
        if row is None:
            raise ValueError(
                "artifact registration requires a passed fit_map_validated receipt for the source revision"
            )

    def _has_validated_source(self, application_id: str, source_revision_id: str) -> bool:
        row = self.database.fetch_one(
            """
            SELECT 1
              FROM validation_receipts AS vr
              JOIN gate_dependencies AS gd
                ON gd.receipt_id = vr.receipt_id
             WHERE vr.application_id = ?
               AND vr.gate = 'fit_map_validated'
               AND vr.result = 'passed'
               AND gd.dependency_type = 'fit_map_revision'
               AND gd.dependency_id = ?
             LIMIT 1
            """,
            (application_id, source_revision_id),
        )
        return row is not None

    def _ensure_run(
        self,
        conn,
        application_id: str,
        run_id: str,
        created_at: str,
    ) -> None:
        existing = conn.execute(
            "SELECT application_id FROM application_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if existing is not None:
            if str(existing["application_id"]) != application_id:
                raise ValueError(f"run_id {run_id} already belongs to another application")
            return
        conn.execute(
            """INSERT INTO application_runs
                   (run_id, application_id, graph_json, status, contract_version, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                application_id,
                "{}",
                "completed",
                "artifact-provenance-v1",
                created_at,
                created_at,
            ),
        )

    def _latest_positioning_revision_id(
        self,
        application_id: str,
        source_revision_id: str,
    ) -> str | None:
        row = self.database.fetch_one(
            """
            SELECT revision_id
              FROM positioning_revisions
             WHERE application_id = ? AND fit_map_revision_id = ?
             ORDER BY created_at DESC, revision_id DESC
             LIMIT 1
            """,
            (application_id, source_revision_id),
        )
        if row is None:
            return None
        return str(row["revision_id"])

    def _normalize_path(self, path: Path | None, *, require_path: bool) -> Path | None:
        if path is None:
            if require_path:
                raise ValueError("artifact kind requires a materialized file path")
            return None
        resolved = path.resolve()
        if not resolved.is_file():
            raise ValueError("artifact path must exist and be a file")
        return resolved

    def _resolve_mime_type(self, path: Path | None, default_mime: str) -> str:
        if path is None:
            return default_mime
        guessed, _encoding = mimetypes.guess_type(str(path))
        return guessed or default_mime

    def _find_existing(
        self,
        *,
        application_id: str,
        kind: str,
        path_text: str | None,
        content_hash: str,
        text_content_hash: str | None,
        source_revision_id: str,
        positioning_revision_id: str | None,
        run_id: str,
    ) -> ArtifactRecord | None:
        row = self._find_existing_row(
            self.database.get_connection(),
            application_id=application_id,
            kind=kind,
            path_text=path_text,
            content_hash=content_hash,
            text_content_hash=text_content_hash,
            source_revision_id=source_revision_id,
            positioning_revision_id=positioning_revision_id,
            run_id=run_id,
        )
        if row is None:
            return None
        return self._row_to_record(row)

    def _find_existing_row(
        self,
        conn,
        *,
        application_id: str,
        kind: str,
        path_text: str | None,
        content_hash: str,
        text_content_hash: str | None,
        source_revision_id: str,
        positioning_revision_id: str | None,
        run_id: str,
    ):
        return conn.execute(
            """
            SELECT version_id, application_id, run_id, kind, path, content_hash,
                   mime_type, COALESCE(size_bytes, 0) AS size_bytes,
                   text_content_hash, source_revision_id, positioning_revision_id,
                   review_receipt_id, review_report_path, review_report_hash, status,
                   created_at, reviewed_at
              FROM artifact_versions
             WHERE application_id = ?
               AND kind = ?
               AND source_revision_id = ?
               AND COALESCE(positioning_revision_id, '') = COALESCE(?, '')
               AND COALESCE(path, '') = COALESCE(?, '')
               AND run_id = ?
               AND content_hash = ?
               AND COALESCE(text_content_hash, '') = COALESCE(?, '')
             ORDER BY created_at DESC, version_id DESC
             LIMIT 1
            """,
            (
                application_id,
                kind,
                source_revision_id,
                positioning_revision_id,
                path_text,
                run_id,
                content_hash,
                text_content_hash,
            ),
        ).fetchone()

    def _load_record(self, artifact_id: str) -> ArtifactRecord:
        row = self.database.fetch_one(
            """
            SELECT version_id, application_id, run_id, kind, path, content_hash,
                   mime_type, COALESCE(size_bytes, 0) AS size_bytes,
                   text_content_hash, source_revision_id, positioning_revision_id,
                   review_receipt_id, review_report_path, review_report_hash, status,
                   created_at, reviewed_at
              FROM artifact_versions
             WHERE version_id = ?
            """,
            (self._required_text(artifact_id, "artifact_id"),),
        )
        if row is None:
            raise ValueError("unknown artifact")
        return self._row_to_record(row)

    def _row_to_record(self, row) -> ArtifactRecord:
        data = dict(row)
        return ArtifactRecord(
            artifact_id=str(data["version_id"]),
            application_id=str(data["application_id"]),
            kind=str(data["kind"]),
            run_id=_optional_str(data.get("run_id")),
            path=_optional_str(data.get("path")),
            content_hash=str(data["content_hash"]),
            mime_type=_optional_str(data.get("mime_type")),
            size_bytes=int(data.get("size_bytes") or 0),
            text_content_hash=_optional_str(data.get("text_content_hash")),
            source_revision_id=str(data["source_revision_id"]),
            positioning_revision_id=_optional_str(data.get("positioning_revision_id")),
            review_receipt_id=_optional_str(data.get("review_receipt_id")),
            review_report_path=_optional_str(data.get("review_report_path")),
            review_report_hash=_optional_str(data.get("review_report_hash")),
            status=str(data["status"]),
            created_at=str(data["created_at"]),
            reviewed_at=_optional_str(data.get("reviewed_at")),
        )

    def _attach_dependency_txn(
        self,
        conn,
        artifact_id: str,
        application_id: str,
        dependency_type: str,
        dependency_id: str,
        created_at: str,
    ) -> None:
        dependency_type = self._required_text(dependency_type, "dependency_type")
        dependency_id = self._required_text(dependency_id, "dependency_id")
        if dependency_type == "fit_map_revision":
            row = conn.execute(
                """
                SELECT 1
                  FROM fit_map_revisions
                 WHERE revision_id = ? AND application_id = ?
                """,
                (dependency_id, application_id),
            ).fetchone()
            if row is None:
                raise ValueError("fit_map dependency is unknown for this application")
        elif dependency_type == "positioning_revision":
            row = conn.execute(
                """
                SELECT 1
                  FROM positioning_revisions
                 WHERE revision_id = ? AND application_id = ?
                """,
                (dependency_id, application_id),
            ).fetchone()
            if row is None:
                raise ValueError("positioning dependency is unknown for this application")
        elif dependency_type == "validation_receipt":
            row = conn.execute(
                """
                SELECT 1
                  FROM validation_receipts
                 WHERE receipt_id = ? AND application_id = ?
                """,
                (dependency_id, application_id),
            ).fetchone()
            if row is None:
                raise ValueError("validation receipt dependency is unknown for this application")
        else:
            raise ValueError(f"unsupported dependency type: {dependency_type}")

        conn.execute(
            """
            INSERT OR IGNORE INTO artifact_version_dependencies
                (version_id, dependency_type, dependency_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (artifact_id, dependency_type, dependency_id, created_at),
        )

    def _validate_kind(self, kind: str) -> str:
        value = self._required_text(kind, "kind")
        if value not in SUPPORTED_ARTIFACT_KINDS:
            raise ValueError(f"unsupported artifact kind: {value}")
        return value

    def _required_text(self, value: str | None, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required")
        return value.strip()


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
