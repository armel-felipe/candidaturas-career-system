from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from career.schemas.candidate_evidence import validate_candidate_evidence
from career.services import provenance
from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository, AnalysisRevision
from career.services.persistence.application_repository import ApplicationRepository
from career.services.persistence.reference_repository import ReferenceRepository, ReferenceVersion
from career.utils import read_json, sha256_file


CANDIDATE_EVIDENCE_PATH = provenance.CANDIDATE_EVIDENCE_PATH
DEFAULT_ARTIFACT_TARGETS = ("cv", "feras", "cover_letter", "habilidades")
REQUIRED_FIELDS = (
    "application_id",
    "fit_map_revision_id",
    "positioning_revision_id",
    "candidate_evidence_revision_id",
    "thesis",
    "persona",
    "stories",
    "claims",
    "keywords",
    "gaps",
    "artifact_targets",
)


def validate_positioning_pack(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("positioning pack must be an object")
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError("positioning pack missing fields: " + ", ".join(missing))
    for field in REQUIRED_FIELDS[:5]:
        if not isinstance(payload.get(field), str) or not str(payload[field]).strip():
            raise ValueError(f"positioning pack {field} must be a non-empty string")
    stories = payload["stories"]
    if not isinstance(stories, list):
        raise ValueError("positioning pack stories must be an array")
    seen: set[str] = set()
    for index, story in enumerate(stories):
        if not isinstance(story, Mapping):
            raise ValueError(f"positioning pack stories[{index}] must be an object")
        story_id = str(story.get("story_id") or "").strip()
        if not story_id:
            raise ValueError(f"positioning pack stories[{index}].story_id is required")
        if story_id in seen:
            raise ValueError(f"duplicate positioning story_id: {story_id}")
        seen.add(story_id)
        source_refs = story.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            raise ValueError(f"positioning pack stories[{index}].source_refs is required")
    for field in ("claims", "keywords", "gaps"):
        if not isinstance(payload[field], list):
            raise ValueError(f"positioning pack {field} must be an array")
    targets = payload["artifact_targets"]
    if not isinstance(targets, (list, dict)):
        raise ValueError("positioning pack artifact_targets must be an array or object")
    return dict(payload)


def artifact_provenance(pack: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_positioning_pack(pack)
    stories = validated["stories"]
    return {
        "positioning_revision_id": validated["positioning_revision_id"],
        "candidate_evidence_revision_id": validated["candidate_evidence_revision_id"],
        "story_ids": [str(story["story_id"]) for story in stories],
        "claim_ids": list(validated["claims"]),
    }


def artifact_claim_text(pack: Mapping[str, Any]) -> str:
    validated = validate_positioning_pack(pack)
    return " ".join(str(claim).strip() for claim in validated["claims"] if str(claim).strip())


def build_positioning_pack(
    application_id: str,
    database: Database,
    positioning_revision_id: str | None = None,
) -> dict[str, Any]:
    applications = ApplicationRepository(database)
    analysis = AnalysisRepository(database)
    references = ReferenceRepository(database)
    application = applications.resolve(application_id=application_id)
    revision = (
        analysis.get_current_for_positioning(application_id, positioning_revision_id)
        if positioning_revision_id
        else analysis.get_current(application_id)
    )
    positioning = revision.positioning
    if positioning is None:
        raise ValueError("application has no positioning revision")

    evidence_reference = _resolve_evidence_reference(revision, positioning, references)
    evidence = validate_candidate_evidence(json.loads(evidence_reference.content))
    selected_ids = _selected_story_ids(positioning.snapshot, positioning.stories, revision.payload)
    stories = _resolve_stories(evidence["stories"], selected_ids)
    snapshot = positioning.snapshot
    claims = _string_list(snapshot.get("claims")) or _claims_from_stories(stories)
    keywords = _keywords(snapshot.get("keywords"), revision)
    gaps = _string_list(snapshot.get("gaps")) or _gaps_from_revision(revision)
    pack = {
        "application_id": application.application_id,
        "fit_map_revision_id": revision.revision_id,
        "positioning_revision_id": positioning.revision_id,
        "candidate_evidence_revision_id": evidence_reference.reference_id,
        "thesis": _first_text(snapshot, "thesis", "headline")
        or "Posicionamento orientado à necessidade da candidatura.",
        "persona": _first_text(snapshot, "persona", "target_persona")
        or "Executivo orientado a impacto e execução",
        "stories": stories,
        "claims": claims,
        "keywords": keywords,
        "gaps": gaps,
        "artifact_targets": snapshot.get("artifact_targets") or list(DEFAULT_ARTIFACT_TARGETS),
        "source": {
            "candidate_evidence_path": str(CANDIDATE_EVIDENCE_PATH),
            "candidate_evidence_sha256": evidence_reference.content_hash,
            "application_fingerprint": application.fingerprint,
        },
    }
    return validate_positioning_pack(pack)


def _resolve_evidence_reference(
    revision: AnalysisRevision,
    positioning: Any,
    references: ReferenceRepository,
) -> ReferenceVersion:
    links: list[Mapping[str, Any]] = []
    for snapshot in (revision.payload, positioning.snapshot):
        declared = snapshot.get("reference_versions", snapshot.get("reference_links"))
        if isinstance(declared, list):
            links.extend(item for item in declared if isinstance(item, Mapping))
    if links:
        try:
            versions = references.resolve_linked_versions(links)
        except ValueError as exc:
            if any(
                str(link.get("kind") or "") == "candidate_evidence"
                for link in links
            ):
                raise ValueError("candidate evidence reference linkage is invalid") from exc
            versions = ()
        for version in versions:
            if version.kind == "candidate_evidence":
                return version
    try:
        return references.get_current("candidate_evidence", "candidate")
    except ValueError as exc:
        raise ValueError("candidate evidence reference is missing") from exc


def _selected_story_ids(
    snapshot: Mapping[str, Any], positioning_stories: Sequence[Mapping[str, Any]], fit_map: Mapping[str, Any]
) -> list[str]:
    raw = snapshot.get("stories")
    candidates = raw if isinstance(raw, list) else list(positioning_stories)
    selected: list[str] = []
    for item in candidates:
        if not isinstance(item, Mapping):
            continue
        value = item.get("story_id") or item.get("experience_id") or item.get("story_key")
        nested = item.get("payload")
        if not value and isinstance(nested, Mapping):
            value = nested.get("story_id") or nested.get("experience_id")
        if value and str(value).strip() not in selected:
            selected.append(str(value).strip())
    if selected:
        return selected
    selected_map = fit_map.get("historias_selecionadas")
    if isinstance(selected_map, Mapping):
        for item in selected_map.values():
            if not isinstance(item, Mapping):
                continue
            value = item.get("story_id") or item.get("experience_id")
            if value and str(value).strip() not in selected:
                selected.append(str(value).strip())
    return selected


def _resolve_stories(stories: Sequence[Mapping[str, Any]], selected_ids: Sequence[str]) -> list[dict[str, Any]]:
    if not selected_ids:
        return []
    by_id = {
        str(item.get("story_id") or item.get("experience_id") or "").strip(): item
        for item in stories
        if isinstance(item, Mapping)
    }
    missing = [story_id for story_id in selected_ids if story_id not in by_id]
    if missing:
        raise ValueError("positioning stories missing from candidate evidence: " + ", ".join(missing))
    return [dict(by_id[story_id]) for story_id in selected_ids]


def _claims_from_stories(stories: Sequence[Mapping[str, Any]]) -> list[str]:
    return _string_list([claim for story in stories for claim in (story.get("allowed_claims") or [])])


def _keywords(raw: Any, revision: AnalysisRevision) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [dict(item) if isinstance(item, Mapping) else {"keyword": str(item)} for item in raw]
    return [
        {
            "keyword": item.keyword,
            "coverage": item.coverage,
            "importance": item.importance,
            "evidence": item.evidence,
        }
        for item in revision.keywords
    ]


def _gaps_from_revision(revision: AnalysisRevision) -> list[str]:
    raw = revision.payload.get("gaps_sem_cobertura")
    return _string_list(raw)


def _first_text(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]
