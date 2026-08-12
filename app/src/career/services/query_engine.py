from __future__ import annotations

import json
import re
from typing import Any

from career.services.database import Database


class FilterParser:
    ALLOWED_COLUMNS = {
        "applications": [
            "id",
            "notion_id",
            "company",
            "role",
            "source_type",
            "source_url",
            "stage",
            "funil_stage",
            "score",
            "cv_language",
            "status",
            "created_at",
            "updated_at",
            "job_description_path",
            "fit_map_path",
            "cv_path",
        ],
        "notion_cache": [
            "id",
            "company",
            "role",
            "funil_stage",
            "canal_aplicacao",
            "tipo_empresa",
            "status",
            "url",
            "last_synced",
        ],
    }

    _CONDITION_RE = re.compile(
        r"(\w+)\s*(>=|<=|!=|<>|=|>|<|LIKE|IN)\s*(.+)",
        re.IGNORECASE | re.DOTALL,
    )

    def parse(self, filter_str: str, source: str = "applications") -> tuple[str, tuple]:
        if not filter_str or not filter_str.strip():
            return "1=1", ()

        allowed = self.ALLOWED_COLUMNS.get(source)
        if allowed is None:
            raise ValueError(
                f"Unknown source: {source}. Allowed: {list(self.ALLOWED_COLUMNS.keys())}"
            )

        tokens = re.split(r"(\s+(?:AND|OR)\s+)", filter_str, flags=re.IGNORECASE)
        tokens = [t.strip() for t in tokens if t.strip()]

        where_parts = []
        params = []

        for token in tokens:
            if token.upper() in ("AND", "OR"):
                where_parts.append(token.upper())
                continue

            col, op, raw_val = self._parse_single(token, allowed)

            if op.upper() == "IN":
                values = self._parse_in_values(raw_val)
                placeholders = ", ".join(["?" for _ in values])
                where_parts.append(f"{col} IN ({placeholders})")
                params.extend(values)
            elif op.upper() == "LIKE":
                where_parts.append(f"{col} LIKE ?")
                params.append(self._clean_value(raw_val))
            else:
                where_parts.append(f"{col} {op} ?")
                params.append(self._coerce_value(self._clean_value(raw_val)))

        return " ".join(where_parts), tuple(params)

    def _parse_single(self, text: str, allowed: list[str]) -> tuple[str, str, str]:
        m = self._CONDITION_RE.match(text)
        if not m:
            raise ValueError(f"Could not parse condition: {text!r}")
        col, op, val = m.group(1), m.group(2), m.group(3).strip()
        if col not in allowed:
            raise ValueError(f"Unknown column '{col}'. Allowed: {allowed}")
        return col, op, val

    def _parse_in_values(self, text: str) -> list:
        text = text.strip()
        if not (text.startswith("(") and text.endswith(")")):
            raise ValueError(f"Invalid IN values: {text!r}")
        inner = text[1:-1]
        return [
            self._coerce_value(self._clean_value(v.strip())) for v in inner.split(",")
        ]

    def _clean_value(self, val: str) -> str:
        val = val.strip()
        if val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        return val

    def _coerce_value(self, val: str) -> Any:
        try:
            if "." in val:
                return float(val)
            return int(val)
        except (ValueError, TypeError):
            return val


class QueryEngine:
    def __init__(self, database: Database):
        self._db = database
        self._parser = FilterParser()

    def execute(
        self,
        filter_str: str,
        source: str = "applications",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        where_clause, params = self._parser.parse(filter_str, source)
        sql = f"SELECT * FROM {source} WHERE {where_clause}"
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"
        return self._db.fetch_all(sql, params)

    def count(self, filter_str: str, source: str = "applications") -> int:
        where_clause, params = self._parser.parse(filter_str, source)
        sql = f"SELECT COUNT(*) as cnt FROM {source} WHERE {where_clause}"
        row = self._db.fetch_one(sql, params)
        return row["cnt"] if row else 0

    def list_filters(self) -> dict:
        return dict(self._parser.ALLOWED_COLUMNS)

    def format_output(self, rows: list[dict], fmt: str = "table") -> str:
        if fmt == "json":
            return json.dumps(rows, ensure_ascii=False, indent=2, default=str)

        if fmt == "human":
            if not rows:
                return "0 result(s)."
            lines = [f"{len(rows)} result(s):"]
            for r in rows:
                score = r.get("score")
                score_str = f" ({score})" if score is not None else ""
                lines.append(
                    f"- {r.get('company', '-')} - {r.get('role', '-')}{score_str}"
                )
            return "\n".join(lines)

        if fmt == "ids":
            if not rows:
                return ""
            return "\n".join(r.get("id", "") for r in rows)

        if not rows:
            return "(empty)"

        headers = list(rows[0].keys())
        col_widths = {
            h: max(
                len(h),
                max((len(str(r.get(h, ""))) for r in rows), default=0),
            )
            for h in headers
        }
        sep = " | ".join("-" * col_widths[h] for h in headers)
        header_line = " | ".join(h.ljust(col_widths[h]) for h in headers)
        body_lines = [
            " | ".join(str(r.get(h, "")).ljust(col_widths[h]) for h in headers)
            for r in rows
        ]
        return "\n".join([header_line, sep] + body_lines)
