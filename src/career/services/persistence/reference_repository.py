from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from uuid import uuid4

from career.services.database import Database
from career.utils import sha256_text, utc_now_iso


@dataclass(frozen=True)
class ReferenceVersion:
    reference_id: str
    kind: str
    logical_key: str
    reference_key: str
    content_hash: str
    source_hash: str
    content: str
    created_at: str
    updated_at: str


class ReferenceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database
        self._schema_ready = False

    def upsert_version(
        self, kind: str, key: str, content: str, source_hash: str
    ) -> str:
        self._ensure_schema()
        content_hash = sha256_text(content)
        storage_key = f"{key}#{content_hash}"
        with self.database.transaction(immediate=True) as conn:
            existing = conn.execute(
                """SELECT reference_id FROM reference_documents
                   WHERE kind = ? AND logical_key = ? AND content_hash = ?
                   ORDER BY created_at DESC, reference_id DESC
                   LIMIT 1""",
                (kind, key, content_hash),
            ).fetchone()
            if existing is not None:
                return str(existing["reference_id"])

            reference_id = f"ref_{uuid4().hex}"
            created_at = utc_now_iso()
            parsed_json = _parse_json(content)
            conn.execute(
                """INSERT INTO reference_documents
                   (reference_id, kind, logical_key, reference_key, content_hash,
                    content, source_hash, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    reference_id,
                    kind,
                    key,
                    storage_key,
                    content_hash,
                    content,
                    source_hash,
                    created_at,
                    created_at,
                ),
            )
            if _looks_like_candidate_reference(kind, parsed_json):
                self._insert_candidate_facts(
                    conn,
                    reference_id=reference_id,
                    source_hash=source_hash,
                    payload=parsed_json if isinstance(parsed_json, Mapping) else {},
                    created_at=created_at,
                )
            if _looks_like_keyword_registry(kind, parsed_json):
                self._insert_keyword_translations(
                    conn,
                    reference_id=reference_id,
                    source_hash=source_hash,
                    content_hash=content_hash,
                    payload=parsed_json if isinstance(parsed_json, Mapping) else {},
                    created_at=created_at,
                )
        return reference_id

    def get_current(self, kind: str, key: str) -> ReferenceVersion:
        self._ensure_schema()
        row = self.database.fetch_one(
            """SELECT reference_id, kind, logical_key, reference_key, content_hash,
                      source_hash, content, created_at, updated_at
               FROM reference_documents
               WHERE kind = ? AND logical_key = ?
               ORDER BY created_at DESC, reference_id DESC
               LIMIT 1""",
            (kind, key),
        )
        if row is None:
            raise ValueError(f"no reference version found for {kind}/{key}")
        return _reference_version_from_row(row)

    def get_version(self, reference_id: str) -> ReferenceVersion:
        self._ensure_schema()
        row = self.database.fetch_one(
            """SELECT reference_id, kind, logical_key, reference_key, content_hash,
                      source_hash, content, created_at, updated_at
               FROM reference_documents
               WHERE reference_id = ?""",
            (reference_id,),
        )
        if row is None:
            raise ValueError(f"no reference version found for {reference_id}")
        return _reference_version_from_row(row)

    def list_versions(self, kind: str, key: str) -> tuple[ReferenceVersion, ...]:
        self._ensure_schema()
        rows = self.database.fetch_all(
            """SELECT reference_id, kind, logical_key, reference_key, content_hash,
                      source_hash, content, created_at, updated_at
               FROM reference_documents
               WHERE kind = ? AND logical_key = ?
               ORDER BY created_at DESC, reference_id DESC""",
            (kind, key),
        )
        return tuple(_reference_version_from_row(row) for row in rows)

    def list_current_versions(self) -> tuple[ReferenceVersion, ...]:
        """Return the latest immutable version for each reference logical key."""
        self._ensure_schema()
        rows = self.database.fetch_all(
            """SELECT current.reference_id, current.kind, current.logical_key,
                      current.reference_key, current.content_hash, current.source_hash,
                      current.content, current.created_at, current.updated_at
               FROM reference_documents AS current
               WHERE NOT EXISTS (
                   SELECT 1 FROM reference_documents AS newer
                   WHERE newer.kind = current.kind
                     AND newer.logical_key = current.logical_key
                     AND (newer.created_at > current.created_at
                          OR (newer.created_at = current.created_at
                              AND newer.reference_id > current.reference_id))
               )
               ORDER BY current.kind ASC, current.logical_key ASC"""
        )
        return tuple(_reference_version_from_row(row) for row in rows)

    def resolve_linked_versions(
        self, links: Sequence[Mapping[str, Any]]
    ) -> tuple[ReferenceVersion, ...]:
        """Resolve immutable references declared by an analysis snapshot.

        A historical materialization must name the exact reference version it
        consumed.  This API deliberately has no "current" fallback: a missing
        or malformed link is a provenance failure, not an invitation to use a
        newer candidate reference.
        """
        self._ensure_schema()
        if not links:
            raise ValueError("pinned revision has no reference linkage")

        resolved: list[ReferenceVersion] = []
        seen: set[str] = set()
        for link in links:
            if not isinstance(link, Mapping):
                raise ValueError("reference linkage entries must be mappings")
            reference_id = _link_text(link, "reference_id")
            if reference_id:
                version = self.get_version(reference_id)
            else:
                kind = _link_text(link, "kind")
                logical_key = _link_text(link, "logical_key")
                content_hash = _link_text(link, "content_hash")
                if not (kind and logical_key and content_hash):
                    raise ValueError(
                        "reference linkage requires reference_id or kind, logical_key and content_hash"
                    )
                row = self.database.fetch_one(
                    """SELECT reference_id, kind, logical_key, reference_key, content_hash,
                              source_hash, content, created_at, updated_at
                       FROM reference_documents
                       WHERE kind = ? AND logical_key = ? AND content_hash = ?""",
                    (kind, logical_key, content_hash),
                )
                if row is None:
                    raise ValueError("reference linkage does not resolve to a stored version")
                version = _reference_version_from_row(row)

            _assert_link_matches(link, version)
            if version.reference_id not in seen:
                resolved.append(version)
                seen.add(version.reference_id)
        return tuple(resolved)

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        self.database.migrate()
        self._schema_ready = True

    def _insert_candidate_facts(
        self,
        conn: Any,
        *,
        reference_id: str,
        source_hash: str,
        payload: Mapping[str, Any],
        created_at: str,
    ) -> None:
        facts = _candidate_facts(payload)
        evidence = _candidate_evidence(payload)
        for fact_key, fact_value, fact_payload in facts:
            conn.execute(
                """INSERT INTO candidate_facts
                   (reference_id, fact_key, fact_value, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    reference_id,
                    fact_key,
                    fact_value,
                    _to_json({"source_hash": source_hash, "payload": fact_payload}),
                    created_at,
                ),
            )
        for evidence_key, evidence_text, evidence_payload in evidence:
            conn.execute(
                """INSERT INTO candidate_evidence
                   (reference_id, evidence_key, evidence_text, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    reference_id,
                    evidence_key,
                    evidence_text,
                    _to_json({"source_hash": source_hash, "payload": evidence_payload}),
                    created_at,
                ),
            )

    def _insert_keyword_translations(
        self,
        conn: Any,
        *,
        reference_id: str,
        source_hash: str,
        content_hash: str,
        payload: Mapping[str, Any],
        created_at: str,
    ) -> None:
        entries = payload.get("entries")
        if not isinstance(entries, Mapping):
            return
        for entry_payload in entries.values():
            if not isinstance(entry_payload, Mapping):
                continue
            canonical = str(entry_payload.get("canonical_keyword") or "").strip()
            if not canonical:
                continue
            rows: list[tuple[str, str]] = [("canonical", canonical)]
            pt_value = entry_payload.get("pt_br_preferred")
            if isinstance(pt_value, str) and pt_value:
                rows.append(("pt-BR", pt_value))
            en_value = entry_payload.get("en_cv_preferred")
            if isinstance(en_value, str) and en_value:
                rows.append(("en", en_value))
            for locale, translation in rows:
                conn.execute(
                    """INSERT OR IGNORE INTO keyword_translation_versions
                       (reference_id, keyword, locale, translation, source_hash, content_hash, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        reference_id,
                        canonical,
                        locale,
                        translation,
                        source_hash,
                        content_hash,
                        created_at,
                    ),
                )
                conn.execute(
                    """INSERT INTO keyword_translations
                       (keyword, locale, translation, source_hash, created_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(keyword, locale) DO UPDATE SET
                         translation = excluded.translation,
                         source_hash = excluded.source_hash,
                         created_at = excluded.created_at
                    """,
                    (
                        canonical,
                        locale,
                        translation,
                        source_hash,
                        created_at,
                    ),
                )


def _looks_like_candidate_reference(kind: str, payload: Any) -> bool:
    return kind == "candidate_facts" or (
        isinstance(payload, Mapping)
        and any(key in payload for key in ("candidate", "experiences", "stack"))
    )


def _link_text(link: Mapping[str, Any], key: str) -> str | None:
    value = link.get(key)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _assert_link_matches(link: Mapping[str, Any], version: ReferenceVersion) -> None:
    expected_values = {
        "reference_id": version.reference_id,
        "kind": version.kind,
        "logical_key": version.logical_key,
        "content_hash": version.content_hash,
        "source_hash": version.source_hash,
    }
    for key, actual in expected_values.items():
        expected = _link_text(link, key)
        if expected is not None and expected != actual:
            raise ValueError(f"reference linkage {key} does not match stored version")


def _looks_like_keyword_registry(kind: str, payload: Any) -> bool:
    return kind == "keyword_translation_registry" or (
        isinstance(payload, Mapping) and isinstance(payload.get("entries"), Mapping)
    )


def _parse_json(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def _candidate_facts(payload: Mapping[str, Any]) -> list[tuple[str, str, Any]]:
    facts: list[tuple[str, str, Any]] = []
    candidate = payload.get("candidate")
    if isinstance(candidate, Mapping):
        for key, value in candidate.items():
            if _is_scalar(value):
                facts.append((f"candidate.{key}", str(value), value))
    stack = payload.get("stack")
    if _is_scalar(stack):
        facts.append(("stack", str(stack), stack))
    for group_name in ("education", "languages"):
        group = payload.get(group_name)
        facts.extend(_flatten_group(group_name, group))
    experiences = payload.get("experiences")
    if isinstance(experiences, list):
        for item in experiences:
            if not isinstance(item, Mapping):
                continue
            experience_id = str(item.get("id") or item.get("company") or f"experience_{len(facts)}")
            for field in ("company", "role", "period"):
                value = item.get(field)
                if _is_scalar(value):
                    facts.append((f"experience.{experience_id}.{field}", str(value), value))
    return facts


def _candidate_evidence(payload: Mapping[str, Any]) -> list[tuple[str, str, Any]]:
    evidence: list[tuple[str, str, Any]] = []
    experiences = payload.get("experiences")
    if not isinstance(experiences, list):
        return evidence
    for item in experiences:
        if not isinstance(item, Mapping):
            continue
        experience_id = str(item.get("id") or item.get("company") or f"experience_{len(evidence)}")
        for field in ("scope_bullet", "result_bullet"):
            value = item.get(field)
            if isinstance(value, str) and value:
                evidence.append((f"experience.{experience_id}.{field}", value, value))
        leverage = item.get("leverage")
        if isinstance(leverage, Mapping):
            for leverage_key, leverage_value in leverage.items():
                if isinstance(leverage_value, str) and leverage_value:
                    evidence.append(
                        (
                            f"experience.{experience_id}.leverage.{leverage_key}",
                            leverage_value,
                            leverage_value,
                        )
                    )
    return evidence


def _flatten_group(prefix: str, value: Any) -> list[tuple[str, str, Any]]:
    rows: list[tuple[str, str, Any]] = []
    if isinstance(value, Mapping):
        for locale, entries in value.items():
            if isinstance(entries, list):
                for index, entry in enumerate(entries):
                    if _is_scalar(entry):
                        rows.append((f"{prefix}.{locale}.{index}", str(entry), entry))
            elif _is_scalar(entries):
                rows.append((f"{prefix}.{locale}", str(entries), entries))
        return rows
    if isinstance(value, list):
        for index, entry in enumerate(value):
            if _is_scalar(entry):
                rows.append((f"{prefix}.{index}", str(entry), entry))
    return rows


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _reference_version_from_row(row: Mapping[str, Any]) -> ReferenceVersion:
    return ReferenceVersion(
        reference_id=str(row["reference_id"]),
        kind=str(row["kind"]),
        logical_key=str(row["logical_key"]),
        reference_key=str(row["reference_key"]),
        content_hash=str(row["content_hash"]),
        source_hash=str(row["source_hash"]),
        content=str(row["content"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
