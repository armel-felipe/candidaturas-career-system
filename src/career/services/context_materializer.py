"""SQLite-backed, application-scoped context materialization.

The payload returned here is the runtime authority for specialist inputs. JSON
exports are compatibility copies only and are deliberately never read here.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from career.services.database import Database
from career.services.persistence.analysis_repository import (
    AnalysisRepository,
    AnalysisRevision,
)
from career.services.persistence.application_repository import ApplicationRepository
from career.services.persistence.reference_repository import ReferenceRepository
from career.services.positioning_pack import build_positioning_pack
from career.utils import sha256_file, sha256_text, utc_now_iso


SUPPORTED_CONTEXT_KINDS = frozenset(
    {
        "fit_map_seed",
        "cv_input",
        "feras_input",
        "habilidades_input",
        "cover_letter_input",
    }
)


@dataclass(frozen=True)
class ExportReceipt:
    path: Path
    content_hash: str
    application_id: str
    revision_id: str | None
    kind: str
    created_at: str
    expires_at: str


class ContextMaterializer:
    """Build compact specialist inputs from canonical SQLite records only."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.applications = ApplicationRepository(database)
        self.analysis = AnalysisRepository(database)
        self.references = ReferenceRepository(database)

    def build(
        self,
        application_id: str,
        kind: str,
        revision_id: str | None = None,
    ) -> Mapping[str, Any]:
        if kind not in SUPPORTED_CONTEXT_KINDS:
            raise ValueError(f"unsupported context kind: {kind}")
        application = self.applications.resolve(application_id=application_id)
        analysis_revision = self._analysis_for(
            application.application_id,
            kind=kind,
            revision_id=revision_id,
        )
        application_revision_id = (
            analysis_revision.application_revision_id if analysis_revision else None
        )
        application_fingerprint = application.fingerprint
        if analysis_revision is not None:
            if not application_revision_id:
                raise ValueError(
                    "fit_map revision does not prove an application revision"
                )
            linked_revision = self.applications.get_application_revision(
                application.application_id, application_revision_id
            )
            job_description = self.applications.get_job_description_for_application_revision(
                application.application_id, application_revision_id
            )
            application_fingerprint = linked_revision.fingerprint
        else:
            application_revision_id = self.applications.get_current_revision_id(
                application.application_id
            )
            if not application_revision_id:
                raise ValueError("application has no current source revision")
            linked_revision = self.applications.get_application_revision(
                application.application_id, application_revision_id
            )
            job_description = self.applications.get_job_description_for_application_revision(
                application.application_id, application_revision_id
            )
            application_fingerprint = linked_revision.fingerprint
        references = self._references_for(analysis_revision, pinned=revision_id is not None)
        positioning_pack = self._positioning_pack_for(
            analysis_revision,
            allow_historical=revision_id is not None,
        )
        context = self._context(
            kind=kind,
            application=application,
            application_fingerprint=application_fingerprint,
            job_description=job_description,
            analysis_revision=analysis_revision,
            references=references,
            positioning_pack=positioning_pack,
        )
        canonical_payload_hash = _canonical_hash(context)
        return {
            "kind": kind,
            "application_id": application.application_id,
            "source_revision_ids": {
                "application_revision_id": application_revision_id
                or self.applications.get_current_revision_id(application.application_id),
                "job_description_id": job_description.description_id,
                "fit_map_revision_id": (
                    analysis_revision.revision_id if analysis_revision else None
                ),
                "positioning_revision_id": (
                    analysis_revision.positioning.revision_id
                    if analysis_revision and analysis_revision.positioning
                    else None
                ),
                "candidate_evidence_revision_id": (
                    positioning_pack["candidate_evidence_revision_id"]
                    if positioning_pack
                    else None
                ),
            },
            "source_hashes": {
                "job_description_hash": job_description.content_hash,
                "fit_map_payload_hash": (
                    analysis_revision.payload_hash if analysis_revision else None
                ),
                "fit_map_source_hash": (
                    analysis_revision.source_hash if analysis_revision else None
                ),
            },
            "canonical_payload_hash": canonical_payload_hash,
            "generated_at": utc_now_iso(),
            "context": context,
        }

    def export_json(
        self,
        application_id: str,
        kind: str,
        destination: Path,
        *,
        temporary_root: Path | None = None,
    ) -> ExportReceipt:
        payload = self.build(application_id, kind)
        target = Path(destination).resolve()
        if not _is_export_destination_allowed(
            target,
            application_id,
            workspace_root=self.database.db_path.resolve().parent.parent,
            temporary_root=temporary_root,
        ):
            raise ValueError(
                "export destination must be application-scoped or temporary"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_canonical_json(payload) + "\n", encoding="utf-8")
        created_at = utc_now_iso()
        expires_at = (datetime.now(UTC) + timedelta(hours=24)).isoformat()
        return ExportReceipt(
            path=target,
            content_hash=sha256_file(target),
            application_id=str(payload["application_id"]),
            revision_id=str(payload["source_revision_ids"]["fit_map_revision_id"])
            if payload["source_revision_ids"]["fit_map_revision_id"]
            else None,
            kind=kind,
            created_at=created_at,
            expires_at=expires_at,
        )

    def _analysis_for(
        self, application_id: str, *, kind: str, revision_id: str | None
    ) -> AnalysisRevision | None:
        if revision_id:
            return self.analysis.get_revision(application_id, revision_id)
        try:
            return self.analysis.get_current(application_id)
        except ValueError:
            if kind == "fit_map_seed":
                return None
            raise

    def _context(
        self,
        *,
        kind: str,
        application,
        application_fingerprint: str | None,
        job_description,
        analysis_revision,
        references,
        positioning_pack,
    ) -> dict[str, Any]:
        serialized_references = [
            {
                "reference_id": item.reference_id,
                "kind": item.kind,
                "logical_key": item.logical_key,
                "content_hash": item.content_hash,
                "source_hash": item.source_hash,
                "content": item.content,
            }
            for item in references
        ]
        context: dict[str, Any] = {
            "application": {
                "application_id": application.application_id,
                "company": application.company,
                "role": application.role,
                "notion_id": application.notion_id,
                "fingerprint": application_fingerprint,
                "source_type": application.source_type,
                "source_url": application.source_url,
                "cv_language": application.cv_language,
            },
            "job_description": {
                "description_id": job_description.description_id,
                "language": job_description.language,
                "content": job_description.content,
                "content_hash": job_description.content_hash,
            },
            "references": serialized_references,
        }
        if positioning_pack is not None:
            context["positioning_pack"] = positioning_pack
        if analysis_revision is not None:
            context["analysis"] = _analysis_payload(analysis_revision)
        if kind == "fit_map_seed":
            context["purpose"] = "fit_map_analysis"
        elif kind == "cv_input":
            context["purpose"] = "cv_generation"
        elif kind == "feras_input":
            context["purpose"] = "feras_generation"
        elif kind == "habilidades_input":
            context["purpose"] = "habilidades_ranking"
        else:
            context["purpose"] = "cover_letter_generation"
        return context

    def _positioning_pack_for(
        self,
        analysis_revision: AnalysisRevision | None,
        *,
        allow_historical: bool = False,
    ) -> dict[str, Any] | None:
        if analysis_revision is None or analysis_revision.positioning is None:
            return None
        try:
            self.references.get_current("candidate_evidence", "candidate")
        except ValueError:
            # Older persisted analyses may predate the structured evidence
            # reference. Keep their context backward-compatible until the
            # reference is explicitly registered.
            return None
        pack = build_positioning_pack(
            analysis_revision.application_id,
            self.database,
            positioning_revision_id=analysis_revision.positioning.revision_id,
        )
        if not allow_historical:
            current_evidence = self.references.get_current(
                "candidate_evidence", "candidate"
            )
            if pack["candidate_evidence_revision_id"] != current_evidence.reference_id:
                raise ValueError("stale positioning candidate evidence reference")
        return pack

    def _references_for(
        self, analysis_revision: AnalysisRevision | None, *, pinned: bool
    ) -> tuple:
        if not pinned:
            return self.references.list_current_versions()
        if analysis_revision is None:
            raise ValueError("pinned revision has no reference linkage")
        links = _reference_links_for_revision(analysis_revision)
        return self.references.resolve_linked_versions(links)


def _analysis_payload(revision: AnalysisRevision) -> dict[str, Any]:
    return {
        "revision_id": revision.revision_id,
        "fingerprint": revision.fingerprint,
        "source_hash": revision.source_hash,
        "payload_hash": revision.payload_hash,
        "score_final": revision.score_final,
        "payload": revision.payload,
        "dimensions": [
            {
                "dimension_key": item.dimension_key,
                "score": item.score,
                "evidence_summary": item.evidence_summary,
                "gap_summary": item.gap_summary,
                "payload": item.payload,
            }
            for item in revision.dimensions
        ],
        "keywords": [
            {
                "keyword": item.keyword,
                "coverage": item.coverage,
                "importance": item.importance,
                "evidence": item.evidence,
            }
            for item in revision.keywords
        ],
        "stories": [
            {
                "story_key": item.story_key,
                "title": item.title,
                "narrative": item.narrative,
                "payload": item.payload,
            }
            for item in revision.stories
        ],
        "evidence": [
            {
                "evidence_key": item.evidence_key,
                "evidence_text": item.evidence_text,
                "payload": item.payload,
            }
            for item in revision.evidence
        ],
        "objections": [
            {
                "objection_key": item.objection_key,
                "objection_text": item.objection_text,
                "response_text": item.response_text,
                "payload": item.payload,
            }
            for item in revision.objections
        ],
        "positioning": (
            {
                "revision_id": revision.positioning.revision_id,
                "source_revision_id": revision.positioning.source_revision_id,
                "payload_hash": revision.positioning.payload_hash,
                "snapshot": revision.positioning.snapshot,
                "stories": [
                    {
                        "story_key": item.story_key,
                        "title": item.title,
                        "narrative": item.narrative,
                        "payload": item.payload,
                    }
                    for item in revision.positioning.stories
                ],
                "principles": [
                    {
                        "principle_key": item.principle_key,
                        "content": item.content,
                        "payload": item.payload,
                    }
                    for item in revision.positioning.principles
                ],
            }
            if revision.positioning
            else None
        ),
    }


def _reference_links_for_revision(revision: AnalysisRevision) -> tuple[Mapping[str, Any], ...]:
    """Read immutable reference links from the pinned analysis/positioning snapshot."""
    links: list[Mapping[str, Any]] = []
    for snapshot in (revision.payload, revision.positioning.snapshot if revision.positioning else None):
        if not isinstance(snapshot, Mapping):
            continue
        declared = snapshot.get("reference_versions", snapshot.get("reference_links"))
        if declared is None:
            continue
        if not isinstance(declared, list):
            raise ValueError("reference linkage must be a list")
        for link in declared:
            if not isinstance(link, Mapping):
                raise ValueError("reference linkage entries must be mappings")
            links.append(link)
    if not links:
        raise ValueError("pinned revision has no reference linkage")
    return tuple(links)


def _is_export_destination_allowed(
    destination: Path,
    application_id: str,
    *,
    workspace_root: Path,
    temporary_root: Path | None,
) -> bool:
    canonical_application_root = (
        workspace_root.resolve()
        / ".career-state"
        / "applications_v2"
        / application_id
    )
    try:
        destination.relative_to(canonical_application_root)
        return True
    except ValueError:
        pass
    if temporary_root is None:
        return False
    declared_temporary_root = Path(temporary_root).resolve()
    try:
        declared_temporary_root.relative_to(Path(tempfile.gettempdir()).resolve())
        destination.relative_to(declared_temporary_root)
        return True
    except ValueError:
        return False


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_hash(value: Mapping[str, Any]) -> str:
    return sha256_text(_canonical_json(value))
