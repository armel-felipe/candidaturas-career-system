from __future__ import annotations

import json
import sqlite3
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import uuid4

from career.services.database import Database
from career.services.persistence.application_repository import ApplicationRepository
from career.utils import json_fingerprint, sha256_text, utc_now_iso


@dataclass(frozen=True)
class AnalysisDimension:
    dimension_key: str
    score: float | None
    evidence_summary: str | None
    gap_summary: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class AnalysisKeyword:
    keyword: str
    coverage: str
    importance: float | None
    evidence: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class AnalysisStory:
    story_key: str
    title: str | None
    narrative: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class AnalysisEvidence:
    evidence_key: str
    evidence_text: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class AnalysisScore:
    score_key: str
    score: float
    rationale: str | None


@dataclass(frozen=True)
class AnalysisPrinciple:
    principle_key: str
    content: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class AnalysisObjection:
    objection_key: str
    objection_text: str
    response_text: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class PositioningRevision:
    revision_id: str
    application_id: str
    source_revision_id: str
    source_hash: str
    payload_hash: str
    snapshot: dict[str, Any]
    stories: tuple[AnalysisStory, ...]
    principles: tuple[AnalysisPrinciple, ...]
    created_at: str


@dataclass(frozen=True)
class AnalysisRevision:
    revision_id: str
    application_id: str
    application_revision_id: str | None
    fingerprint: str | None
    source_hash: str
    payload_hash: str
    score_final: float | None
    payload: dict[str, Any]
    dimensions: tuple[AnalysisDimension, ...]
    keywords: tuple[AnalysisKeyword, ...]
    objections: tuple[AnalysisObjection, ...]
    stories: tuple[AnalysisStory, ...]
    evidence: tuple[AnalysisEvidence, ...]
    scores: tuple[AnalysisScore, ...]
    positioning: PositioningRevision | None
    created_at: str


class StaleAnalysisError(ValueError):
    """Raised when historical analysis exists but none belongs to current intake."""


class AnalysisRepository:
    def __init__(self, database: Database) -> None:
        self.database = database
        self._schema_ready = False

    def create_revision(
        self,
        application_id: str,
        fit_map: Mapping[str, Any],
        source_hash: str,
        *,
        application_revision_id: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        self._ensure_schema()
        source_hash = str(source_hash or "").strip()
        if not source_hash:
            raise ValueError("fit_map revision source_hash is required")
        explicit_application_revision = application_revision_id is not None
        application_revision_id = (
            str(application_revision_id or "").strip()
            if explicit_application_revision
            else self._latest_application_revision_id(application_id)
        )
        fit_map_payload = _as_payload(fit_map)
        if explicit_application_revision:
            if not application_revision_id:
                raise ValueError("application_revision_id is required")
            applications = ApplicationRepository(self.database)
            current_application_revision_id = applications.get_current_revision_id(
                application_id
            )
            if application_revision_id != current_application_revision_id:
                raise ValueError(
                    "fit_map finalization requires the current application revision"
                )
            application_revision = applications.get_application_revision(
                application_id, application_revision_id
            )
            job_description = applications.get_job_description_for_application_revision(
                application_id, application_revision_id
            )
            if (
                application_revision.fingerprint != job_description.content_hash
                or application_revision.source_hash != job_description.content_hash
            ):
                raise ValueError(
                    "application revision does not match its linked job description"
                )
            payload_fingerprint = _extract_fingerprint(fit_map_payload)
            if payload_fingerprint and payload_fingerprint != job_description.content_hash:
                raise ValueError(
                    "fit_map fingerprint does not match current job description"
                )
            metadata = fit_map_payload.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
                fit_map_payload["metadata"] = metadata
            metadata["job_fingerprint"] = job_description.content_hash
            metadata["application_revision_id"] = application_revision_id
            metadata["job_description_id"] = job_description.description_id
        payload, payload_hash = _canonicalize_payload(fit_map_payload)
        payload_json = _to_json(payload)
        created_at = utc_now_iso()
        revision_id = f"fit_{uuid4().hex}"
        fingerprint = _extract_fingerprint(payload)
        score_final = _extract_final_score(payload)
        revision_clause = (
            "application_revision_id = ?"
            if application_revision_id is not None
            else "application_revision_id IS NULL"
        )
        existing_parameters: tuple[Any, ...] = (
            (application_id, application_revision_id, source_hash, payload_hash)
            if application_revision_id is not None
            else (application_id, source_hash, payload_hash)
        )
        existing = self.database.fetch_one(
            f"""SELECT revision_id FROM fit_map_revisions
                WHERE application_id = ?
                  AND {revision_clause}
                  AND source_hash = ?
                  AND payload_hash = ?
                ORDER BY created_at DESC, revision_id DESC
                LIMIT 1""",
            existing_parameters,
        )
        if existing is not None:
            return str(existing["revision_id"])
        dimensions = _normalize_dimensions(payload.get("dimensions"))
        keywords = _normalize_keywords(payload.get("keywords"))
        evidence_items = _normalize_evidence(payload.get("evidence"))
        objections = _normalize_objections(payload.get("objections"))
        stories = _normalize_stories(payload.get("stories"))
        scores = _normalize_scores(payload.get("scores"))

        transaction = (
            self.database.transaction(immediate=True)
            if conn is None
            else nullcontext(conn)
        )
        with transaction as conn:
            conn.execute(
                """INSERT INTO fit_map_revisions
                   (revision_id, application_id, application_revision_id,
                    fingerprint, source_hash, payload_hash, payload_json, score_final, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    revision_id,
                    application_id,
                    application_revision_id,
                    fingerprint,
                    source_hash,
                    payload_hash,
                    payload_json,
                    score_final,
                    created_at,
                ),
            )
            for dimension in dimensions:
                conn.execute(
                    """INSERT INTO fit_map_dimensions
                       (revision_id, dimension_key, score, evidence_summary,
                        gap_summary, payload_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        revision_id,
                        dimension["dimension_key"],
                        dimension["score"],
                        dimension["evidence_summary"],
                        dimension["gap_summary"],
                        _to_json(dimension["payload"]),
                    ),
                )
            for keyword in keywords:
                conn.execute(
                    """INSERT INTO fit_map_keywords
                       (revision_id, keyword, coverage, importance, evidence)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        revision_id,
                        keyword["keyword"],
                        keyword["coverage"],
                        keyword["importance"],
                        keyword["evidence"],
                    ),
                )
            for item in evidence_items:
                conn.execute(
                    """INSERT INTO fit_map_evidence
                       (revision_id, evidence_key, evidence_text, payload_json)
                       VALUES (?, ?, ?, ?)""",
                    (
                        revision_id,
                        item["evidence_key"],
                        item["evidence_text"],
                        _to_json(item["payload"]),
                    ),
                )
            for item in objections:
                conn.execute(
                    """INSERT INTO fit_map_objections
                       (revision_id, objection_key, objection_text, response_text, payload_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        revision_id,
                        item["objection_key"],
                        item["objection_text"],
                        item["response_text"],
                        _to_json(item["payload"]),
                    ),
                )
            for story in stories:
                conn.execute(
                    """INSERT INTO fit_map_stories
                       (revision_id, story_key, title, narrative, payload_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        revision_id,
                        story["story_key"],
                        story["title"],
                        story["narrative"],
                        _to_json(story["payload"]),
                    ),
                )
            for score in scores:
                conn.execute(
                    """INSERT INTO fit_map_scores
                       (revision_id, score_key, score, rationale)
                       VALUES (?, ?, ?, ?)""",
                    (
                        revision_id,
                        score["score_key"],
                        score["score"],
                        score["rationale"],
                    ),
                )
        return revision_id

    def get_current(self, application_id: str) -> AnalysisRevision:
        self._ensure_schema()
        application_revision_id = self._latest_application_revision_id(application_id)
        if application_revision_id is None:
            row = self.database.fetch_one(
                """SELECT revision_id, application_id, application_revision_id,
                          fingerprint, source_hash, payload_hash, payload_json,
                          score_final, created_at
                     FROM fit_map_revisions
                    WHERE application_id = ? AND application_revision_id IS NULL
                    ORDER BY created_at DESC, revision_id DESC
                    LIMIT 1""",
                (application_id,),
            )
        else:
            row = self.database.fetch_one(
                """SELECT revision_id, application_id, application_revision_id,
                          fingerprint, source_hash, payload_hash, payload_json,
                          score_final, created_at
                     FROM fit_map_revisions
                    WHERE application_id = ? AND application_revision_id = ?
                    ORDER BY created_at DESC, revision_id DESC
                    LIMIT 1""",
                (application_id, application_revision_id),
            )
        if row is None:
            historical = self.database.fetch_one(
                "SELECT revision_id FROM fit_map_revisions WHERE application_id = ? LIMIT 1",
                (application_id,),
            )
            if historical is not None:
                raise StaleAnalysisError(
                    "stale analysis for current application revision"
                )
            raise ValueError(f"no fit_map revision found for {application_id}")
        return self._analysis_revision_from_row(row)

    def get_revision(self, application_id: str, revision_id: str) -> AnalysisRevision:
        """Load one immutable FIT_MAP revision, rejecting foreign revision IDs."""
        self._ensure_schema()
        row = self.database.fetch_one(
            """SELECT revision_id, application_id, application_revision_id, fingerprint,
                      source_hash, payload_hash, payload_json, score_final, created_at
               FROM fit_map_revisions
               WHERE revision_id = ? AND application_id = ?""",
            (revision_id, application_id),
        )
        if row is None:
            owner = self.database.fetch_one(
                "SELECT application_id FROM fit_map_revisions WHERE revision_id = ?",
                (revision_id,),
            )
            if owner is not None:
                raise ValueError("fit_map revision must belong to the same application")
            raise ValueError(f"no fit_map revision found for {application_id}")
        return self._analysis_revision_from_row(row)

    def _analysis_revision_from_row(self, row: Mapping[str, Any]) -> AnalysisRevision:
        revision_id = str(row["revision_id"])
        application_id = str(row["application_id"])
        positioning_row = self.database.fetch_one(
            """SELECT revision_id, application_id, fit_map_revision_id,
                      source_hash, payload_hash, payload_json, created_at
               FROM positioning_revisions
               WHERE application_id = ? AND fit_map_revision_id = ?
               ORDER BY created_at DESC, revision_id DESC
               LIMIT 1""",
            (application_id, revision_id),
        )
        positioning = (
            self._load_positioning_revision(positioning_row)
            if positioning_row is not None
            else None
        )
        return AnalysisRevision(
            revision_id=revision_id,
            application_id=application_id,
            application_revision_id=_optional_str(row["application_revision_id"]),
            fingerprint=_optional_str(row["fingerprint"]),
            source_hash=str(row["source_hash"]),
            payload_hash=str(row["payload_hash"]),
            score_final=_optional_float(row["score_final"]),
            payload=_from_json(str(row["payload_json"])),
            dimensions=self._load_dimensions(revision_id),
            keywords=self._load_keywords(revision_id),
            objections=self._load_objections(revision_id),
            stories=self._load_fit_map_stories(revision_id),
            evidence=self._load_evidence(revision_id),
            scores=self._load_scores(revision_id),
            positioning=positioning,
            created_at=str(row["created_at"]),
        )

    def create_positioning_revision(
        self, application_id: str, source_revision_id: str, snapshot: Mapping[str, Any]
    ) -> str:
        self._ensure_schema()
        source_row = self.database.fetch_one(
            """SELECT revision_id FROM fit_map_revisions
               WHERE revision_id = ? AND application_id = ?""",
            (source_revision_id, application_id),
        )
        if source_row is None:
            raise ValueError(
                "positioning revision requires a fit_map revision for the same application"
            )
        payload, payload_hash = _canonicalize_payload(snapshot)
        payload_json = _to_json(payload)
        created_at = utc_now_iso()
        revision_id = f"pos_{uuid4().hex}"
        source_hash = json_fingerprint(payload)
        stories = _normalize_stories(payload.get("stories"))
        principles = _normalize_principles(payload.get("principles"))

        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                """INSERT INTO positioning_revisions
                   (revision_id, application_id, fit_map_revision_id,
                    source_hash, payload_hash, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    revision_id,
                    application_id,
                    source_revision_id,
                    source_hash,
                    payload_hash,
                    payload_json,
                    created_at,
                ),
            )
            for story in stories:
                conn.execute(
                    """INSERT INTO positioning_stories
                       (revision_id, story_key, title, narrative, payload_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        revision_id,
                        story["story_key"],
                        story["title"],
                        story["narrative"],
                        _to_json(story["payload"]),
                    ),
                )
            for principle in principles:
                conn.execute(
                    """INSERT INTO positioning_principles
                       (revision_id, principle_key, content, payload_json)
                       VALUES (?, ?, ?, ?)""",
                    (
                        revision_id,
                        principle["principle_key"],
                        principle["content"],
                        _to_json(principle["payload"]),
                    ),
                )
        return revision_id

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        self.database.migrate()
        self._schema_ready = True

    def ensure_schema(self) -> None:
        self._ensure_schema()

    def _latest_application_revision_id(self, application_id: str) -> str | None:
        row = self.database.fetch_one(
            """SELECT revision_id FROM application_revisions
               WHERE application_id = ?
               ORDER BY created_at DESC, revision_id DESC
               LIMIT 1""",
            (application_id,),
        )
        if row is None:
            return None
        return str(row["revision_id"])

    def _load_dimensions(self, revision_id: str) -> tuple[AnalysisDimension, ...]:
        rows = self.database.fetch_all(
            """SELECT dimension_key, score, evidence_summary, gap_summary, payload_json
               FROM fit_map_dimensions
               WHERE revision_id = ?
               ORDER BY dimension_key ASC""",
            (revision_id,),
        )
        return tuple(
            AnalysisDimension(
                dimension_key=str(row["dimension_key"]),
                score=_optional_float(row["score"]),
                evidence_summary=_optional_str(row["evidence_summary"]),
                gap_summary=_optional_str(row["gap_summary"]),
                payload=_from_json(str(row["payload_json"])),
            )
            for row in rows
        )

    def _load_keywords(self, revision_id: str) -> tuple[AnalysisKeyword, ...]:
        rows = self.database.fetch_all(
            """SELECT keyword, coverage, importance, evidence
               FROM fit_map_keywords
               WHERE revision_id = ?
               ORDER BY importance DESC, keyword ASC""",
            (revision_id,),
        )
        return tuple(
            AnalysisKeyword(
                keyword=str(row["keyword"]),
                coverage=str(row["coverage"]),
                importance=_optional_float(row["importance"]),
                evidence=_optional_str(row["evidence"]),
                payload={},
            )
            for row in rows
        )

    def _load_objections(self, revision_id: str) -> tuple[AnalysisObjection, ...]:
        rows = self.database.fetch_all(
            """SELECT objection_key, objection_text, response_text, payload_json
               FROM fit_map_objections
               WHERE revision_id = ?
               ORDER BY objection_key ASC""",
            (revision_id,),
        )
        return tuple(
            AnalysisObjection(
                objection_key=str(row["objection_key"]),
                objection_text=str(row["objection_text"]),
                response_text=_optional_str(row["response_text"]),
                payload=_from_json(str(row["payload_json"])),
            )
            for row in rows
        )

    def _load_fit_map_stories(self, revision_id: str) -> tuple[AnalysisStory, ...]:
        rows = self.database.fetch_all(
            """SELECT story_key, title, narrative, payload_json
               FROM fit_map_stories
               WHERE revision_id = ?
               ORDER BY story_key ASC""",
            (revision_id,),
        )
        return tuple(
            AnalysisStory(
                story_key=str(row["story_key"]),
                title=_optional_str(row["title"]),
                narrative=str(row["narrative"]),
                payload=_from_json(str(row["payload_json"])),
            )
            for row in rows
        )

    def _load_evidence(self, revision_id: str) -> tuple[AnalysisEvidence, ...]:
        rows = self.database.fetch_all(
            """SELECT evidence_key, evidence_text, payload_json
               FROM fit_map_evidence
               WHERE revision_id = ?
               ORDER BY evidence_key ASC""",
            (revision_id,),
        )
        return tuple(
            AnalysisEvidence(
                evidence_key=str(row["evidence_key"]),
                evidence_text=str(row["evidence_text"]),
                payload=_from_json(str(row["payload_json"])),
            )
            for row in rows
        )

    def _load_scores(self, revision_id: str) -> tuple[AnalysisScore, ...]:
        rows = self.database.fetch_all(
            """SELECT score_key, score, rationale
               FROM fit_map_scores
               WHERE revision_id = ?
               ORDER BY score_key ASC""",
            (revision_id,),
        )
        return tuple(
            AnalysisScore(
                score_key=str(row["score_key"]),
                score=float(row["score"]),
                rationale=_optional_str(row["rationale"]),
            )
            for row in rows
        )

    def _load_positioning_revision(self, row: Mapping[str, Any]) -> PositioningRevision:
        revision_id = str(row["revision_id"])
        stories = self.database.fetch_all(
            """SELECT story_key, title, narrative, payload_json
               FROM positioning_stories
               WHERE revision_id = ?
               ORDER BY story_key ASC""",
            (revision_id,),
        )
        principles = self.database.fetch_all(
            """SELECT principle_key, content, payload_json
               FROM positioning_principles
               WHERE revision_id = ?
               ORDER BY principle_key ASC""",
            (revision_id,),
        )
        return PositioningRevision(
            revision_id=revision_id,
            application_id=str(row["application_id"]),
            source_revision_id=str(row["fit_map_revision_id"]),
            source_hash=str(row["source_hash"]),
            payload_hash=str(row["payload_hash"]),
            snapshot=_from_json(str(row["payload_json"])),
            stories=tuple(
                AnalysisStory(
                    story_key=str(item["story_key"]),
                    title=_optional_str(item["title"]),
                    narrative=str(item["narrative"]),
                    payload=_from_json(str(item["payload_json"])),
                )
                for item in stories
            ),
            principles=tuple(
                AnalysisPrinciple(
                    principle_key=str(item["principle_key"]),
                    content=str(item["content"]),
                    payload=_from_json(str(item["payload_json"])),
                )
                for item in principles
            ),
            created_at=str(row["created_at"]),
        )


def _as_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(value), ensure_ascii=False))


def _canonicalize_payload(value: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    payload = _as_payload(value)
    supplied_hashes: list[str] = []
    for container_key in ("metadata", "provenance"):
        nested = payload.get(container_key)
        if isinstance(nested, dict) and "payload_hash" in nested:
            nested_hash = nested.pop("payload_hash")
            if not isinstance(nested_hash, str) or not nested_hash:
                raise ValueError("payload_hash does not match canonical payload")
            supplied_hashes.append(nested_hash)
    if "payload_hash" in payload:
        root_hash = payload.pop("payload_hash")
        if not isinstance(root_hash, str) or not root_hash:
            raise ValueError("payload_hash does not match canonical payload")
        supplied_hashes.append(root_hash)
    payload_json = _to_json(payload)
    payload_hash = sha256_text(payload_json)
    if any(value != payload_hash for value in supplied_hashes):
        raise ValueError("payload_hash does not match canonical payload")
    return payload, payload_hash


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _from_json(value: str) -> dict[str, Any]:
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {"value": loaded}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _extract_fingerprint(payload: Mapping[str, Any]) -> str | None:
    metadata = payload.get("metadata")
    if isinstance(metadata, Mapping):
        for key in ("job_fingerprint", "fingerprint", "source_fingerprint"):
            value = metadata.get(key)
            if value:
                return str(value)
    for key in ("job_fingerprint", "fingerprint"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _extract_final_score(payload: Mapping[str, Any]) -> float | None:
    scores = payload.get("scores")
    if isinstance(scores, Mapping):
        final = scores.get("final")
        if isinstance(final, Mapping):
            score = final.get("score")
            if score is not None:
                return float(score)
        if isinstance(final, (int, float)):
            return float(final)
    for key in ("score_final", "nota_aderencia", "aderencia_score"):
        value = payload.get(key)
        if isinstance(value, Mapping) and isinstance(value.get("final"), (int, float)):
            return float(value["final"])
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _normalize_dimensions(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    items: list[tuple[str, Any]]
    if isinstance(raw, Mapping):
        items = [(str(key), value) for key, value in raw.items()]
    elif isinstance(raw, list):
        items = [
            (str(item.get("dimension_key") or item.get("key") or item.get("id") or f"dimension_{index}"), item)
            for index, item in enumerate(raw)
            if isinstance(item, Mapping)
        ]
    else:
        return []
    normalized: list[dict[str, Any]] = []
    for dimension_key, item in items:
        payload = item if isinstance(item, Mapping) else {"value": item}
        score = payload.get("score")
        normalized.append(
            {
                "dimension_key": dimension_key,
                "score": float(score) if isinstance(score, (int, float)) else None,
                "evidence_summary": _first_text(
                    payload, "evidence_summary", "summary", "evidence"
                ),
                "gap_summary": _first_text(payload, "gap_summary", "gap"),
                "payload": dict(payload) if isinstance(payload, Mapping) else payload,
            }
        )
    return normalized


def _normalize_keywords(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if isinstance(item, str):
            normalized.append(
                {
                    "keyword": item,
                    "coverage": "unknown",
                    "importance": None,
                    "evidence": None,
                }
            )
            continue
        if not isinstance(item, Mapping):
            continue
        keyword = str(item.get("keyword") or item.get("term") or item.get("name") or f"keyword_{index}")
        importance = item.get("importance")
        normalized.append(
            {
                "keyword": keyword,
                "coverage": str(item.get("coverage") or item.get("status") or "unknown"),
                "importance": float(importance) if isinstance(importance, (int, float)) else None,
                "evidence": _first_text(item, "evidence", "reason", "summary"),
            }
        )
    return normalized


def _normalize_evidence(raw: Any) -> list[dict[str, Any]]:
    items = _iter_normalized_items(raw, "evidence_key", "evidence")
    normalized: list[dict[str, Any]] = []
    for evidence_key, item, context in items:
        normalized.append(
            {
                "evidence_key": evidence_key,
                "evidence_text": _required_text(
                    item,
                    context,
                    "evidence_text",
                    "text",
                    "content",
                    "narrative",
                    "summary",
                ),
                "payload": dict(item),
            }
        )
    return normalized


def _normalize_objections(raw: Any) -> list[dict[str, Any]]:
    items = _iter_normalized_items(raw, "objection_key", "objections")
    normalized: list[dict[str, Any]] = []
    for objection_key, item, context in items:
        normalized.append(
            {
                "objection_key": objection_key,
                "objection_text": _required_text(
                    item, context, "objection_text", "text", "content", "summary"
                ),
                "response_text": _first_text(item, "response_text", "response", "answer"),
                "payload": dict(item),
            }
        )
    return normalized


def _normalize_stories(raw: Any) -> list[dict[str, Any]]:
    items = _iter_normalized_items(raw, "story_key", "stories")
    normalized: list[dict[str, Any]] = []
    for story_key, item, context in items:
        normalized.append(
            {
                "story_key": story_key,
                "title": _first_text(item, "title", "headline", "name"),
                "narrative": _required_text(
                    item,
                    context,
                    "narrative",
                    "story",
                    "content",
                    "text",
                    "summary",
                ),
                "payload": dict(item),
            }
        )
    return normalized


def _normalize_principles(raw: Any) -> list[dict[str, Any]]:
    items = _iter_normalized_items(raw, "principle_key", "principles")
    normalized: list[dict[str, Any]] = []
    for principle_key, item, context in items:
        normalized.append(
            {
                "principle_key": principle_key,
                "content": _required_text(item, context, "content", "text", "principle"),
                "payload": dict(item),
            }
        )
    return normalized


def _normalize_scores(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, Mapping):
        return []
    normalized: list[dict[str, Any]] = []
    for score_key, item in raw.items():
        if isinstance(item, Mapping):
            score = item.get("score")
            rationale = _first_text(item, "rationale", "reason", "summary")
        else:
            score = item
            rationale = None
        if not isinstance(score, (int, float)):
            continue
        normalized.append(
            {
                "score_key": str(score_key),
                "score": float(score),
                "rationale": rationale,
            }
        )
    return normalized


def _iter_normalized_items(
    raw: Any, preferred_key_field: str, collection_name: str
) -> list[tuple[str, dict[str, Any], str]]:
    if isinstance(raw, Mapping):
        items: list[tuple[str, dict[str, Any], str]] = []
        for key, value in raw.items():
            if isinstance(value, Mapping):
                payload = dict(value)
            else:
                payload = {"value": value}
            payload.setdefault(preferred_key_field, str(key))
            items.append((str(key), payload, f"{collection_name}.{key}"))
        return items
    if isinstance(raw, list):
        items: list[tuple[str, dict[str, Any], str]] = []
        for index, value in enumerate(raw):
            if isinstance(value, Mapping):
                payload = dict(value)
            else:
                payload = {"value": value}
            normalized_key = str(
                payload.get(preferred_key_field)
                or payload.get("key")
                or payload.get("id")
                or payload.get("name")
                or f"item_{index}"
            )
            payload.setdefault(preferred_key_field, normalized_key)
            items.append((normalized_key, payload, f"{collection_name}[{index}]"))
        return items
    return []


def _first_text(mapping: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _required_text(mapping: Mapping[str, Any], context: str, *keys: str) -> str:
    for key in keys:
        if key not in mapping:
            continue
        value = mapping.get(key)
        if isinstance(value, str) and value:
            return value
        raise ValueError(f"{context} requires text field {key}")
    raw = mapping.get("value")
    if isinstance(raw, str) and raw:
        return raw
    raise ValueError(f"{context} requires text field")
