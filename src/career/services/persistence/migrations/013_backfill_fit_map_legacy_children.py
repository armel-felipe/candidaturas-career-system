"""Backfill relational FIT_MAP projections from legacy full payloads."""

from __future__ import annotations

import json
from collections.abc import Mapping


def _text(item: Mapping, *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _dimensions(payload: Mapping) -> dict[str, Mapping]:
    score = payload.get("nota_aderencia")
    raw = score.get("dimensoes") if isinstance(score, Mapping) else None
    return {
        str(key): value
        for key, value in (raw.items() if isinstance(raw, Mapping) else [])
        if isinstance(value, Mapping)
    }


def _objections(payload: Mapping) -> list[Mapping]:
    raw = payload.get("objections") or payload.get("objecoes")
    return [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def _keywords(payload: Mapping) -> list[Mapping]:
    raw = payload.get("keywords") or payload.get("keywords_habilidade_ats")
    return [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def apply(conn) -> None:
    rows = conn.execute(
        "SELECT revision_id, payload_json FROM fit_map_revisions"
    ).fetchall()
    for row in rows:
        revision_id = str(row[0])
        payload = json.loads(str(row[1]))
        if not isinstance(payload, Mapping):
            continue
        for key, item in _dimensions(payload).items():
            gaps = item.get("gaps")
            gap_summary = None
            if isinstance(gaps, list):
                texts = []
                for gap in gaps:
                    value = gap.get("gap") if isinstance(gap, Mapping) else gap
                    if value:
                        texts.append(str(value))
                gap_summary = "; ".join(texts) or None
            score = item.get("score", item.get("pontos"))
            conn.execute(
                """INSERT OR IGNORE INTO fit_map_dimensions
                   (revision_id, dimension_key, score, evidence_summary,
                    gap_summary, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    revision_id,
                    key,
                    float(score) if isinstance(score, (int, float)) else None,
                    _text(item, "evidence_summary", "summary", "evidence"),
                    _text(item, "gap_summary") or gap_summary,
                    json.dumps(dict(item), ensure_ascii=False, sort_keys=True),
                ),
            )
        for index, item in enumerate(_objections(payload)):
            key = str(item.get("objection_key") or item.get("key") or f"item_{index}")
            text = _text(item, "objection_text", "objecao", "text", "content", "summary")
            if not text:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO fit_map_objections
                   (revision_id, objection_key, objection_text, response_text, payload_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    revision_id,
                    key,
                    text,
                    _text(item, "response_text", "response", "answer", "mitigacao"),
                    json.dumps(dict(item), ensure_ascii=False, sort_keys=True),
                ),
            )
        for index, item in enumerate(_keywords(payload)):
            keyword = _text(item, "keyword", "term", "name")
            if not keyword:
                continue
            importance = item.get("importance", item.get("prioridade"))
            conn.execute(
                """INSERT OR IGNORE INTO fit_map_keywords
                   (revision_id, keyword, coverage, importance, evidence)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    revision_id,
                    keyword,
                    str(item.get("coverage") or item.get("status") or "unknown"),
                    float(importance) if isinstance(importance, (int, float)) else None,
                    _text(item, "evidence", "reason", "summary"),
                ),
            )
