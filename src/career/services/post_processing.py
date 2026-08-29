"""Re-entrant, SQLite-backed post-processing for an analyzed application."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

from career.services import cover_letter, feras, habilidades_chave
from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import ApplicationRepository
from career.services.persistence.artifact_repository import (
    ArtifactRecord,
    ArtifactRepository,
)


POST_ARTIFACT_KINDS = frozenset({"feras", "gupy_skills", "cover_letter"})


def create_post_artifact(
    application_id: str,
    kind: str,
    source_positioning_revision: str | None = None,
    *,
    database: Database | None = None,
) -> ArtifactRecord:
    """Create one post-processing artifact from the current SQLite snapshot.

    This function never reads active-job pointers or compatibility JSON.  The
    FIT_MAP revision and optional positioning revision must belong to the
    resolved application and the FIT_MAP must already have passed validation.
    """
    kind = str(kind or "").strip()
    if kind not in POST_ARTIFACT_KINDS:
        raise ValueError(f"unsupported post-processing kind: {kind}")
    db = database or Database()
    applications = ApplicationRepository(db)
    application = applications.resolve(application_id=application_id)
    analysis = AnalysisRepository(db)
    revision = analysis.get_current(application.application_id)
    positioning_revision_id = _resolve_positioning_revision(
        db,
        application.application_id,
        revision.revision_id,
        source_positioning_revision,
    )
    content = _build_content(kind, revision.payload)
    artifacts = ArtifactRepository(db)
    return artifacts.register(
        application.application_id,
        kind,
        None,
        content,
        revision.revision_id,
        f"post-{uuid4().hex}",
        positioning_revision_id=positioning_revision_id,
    )


def list_post_artifacts(
    application_id: str,
    kind: str | None = None,
    *,
    database: Database | None = None,
) -> list[ArtifactRecord]:
    """List post-processing artifacts without consulting filesystem state."""
    db = database or Database()
    kinds = None if kind is None else {kind}
    if kind is not None and kind not in POST_ARTIFACT_KINDS:
        raise ValueError(f"unsupported post-processing kind: {kind}")
    return ArtifactRepository(db).list_for_application(
        application_id,
        kinds=kinds or POST_ARTIFACT_KINDS,
    )


def read_post_artifact(
    application_id: str,
    artifact_id: str,
    *,
    database: Database | None = None,
) -> str:
    """Read one textual post-processing artifact within its application scope."""
    db = database or Database()
    applications = ApplicationRepository(db)
    applications.resolve(application_id=application_id)
    row = db.fetch_one(
        """
        SELECT av.kind, ac.content
          FROM artifact_versions AS av
          JOIN artifact_contents AS ac ON ac.version_id = av.version_id
         WHERE av.version_id = ?
           AND av.application_id = ?
        """,
        (artifact_id, application_id),
    )
    if row is None:
        raise ValueError("post-processing artifact is unknown for this application")
    if str(row["kind"]) not in POST_ARTIFACT_KINDS:
        raise ValueError("artifact is not a post-processing artifact")
    return str(row["content"])


def revise_positioning(
    application_id: str,
    changes: Mapping[str, Any],
    *,
    database: Database | None = None,
) -> str:
    """Create a new positioning revision while preserving prior revisions."""
    if not isinstance(changes, Mapping):
        raise TypeError("positioning changes must be a mapping")
    db = database or Database()
    applications = ApplicationRepository(db)
    application = applications.resolve(application_id=application_id)
    revision = AnalysisRepository(db).get_current(application.application_id)
    base = dict(revision.positioning.snapshot) if revision.positioning else {}
    base.update(dict(changes))
    return AnalysisRepository(db).create_positioning_revision(
        application.application_id,
        revision.revision_id,
        base,
    )


def _resolve_positioning_revision(
    database: Database,
    application_id: str,
    source_revision_id: str,
    requested_revision_id: str | None,
) -> str | None:
    if requested_revision_id is None:
        return None
    row = database.fetch_one(
        """
        SELECT application_id, fit_map_revision_id
          FROM positioning_revisions
         WHERE revision_id = ?
        """,
        (requested_revision_id,),
    )
    if row is None:
        raise ValueError("positioning revision is unknown")
    if str(row["application_id"]) != application_id:
        raise ValueError("positioning revision must belong to the same application")
    if str(row["fit_map_revision_id"]) != source_revision_id:
        raise ValueError("positioning revision does not belong to the current FIT_MAP revision")
    return requested_revision_id


def _build_content(kind: str, fit_map: Mapping[str, Any]) -> str:
    payload = dict(fit_map)
    if kind == "feras":
        return feras.build_from_fit_map(payload)
    if kind == "gupy_skills":
        return habilidades_chave.build_from_fit_map(payload)
    return cover_letter.build_from_fit_map(payload)
