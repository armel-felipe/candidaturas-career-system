from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from career.utils import ensure


@dataclass(slots=True)
class NotionApplicationRecordSchema:
    payload: dict[str, Any]

    def validate(self) -> dict[str, Any]:
        ensure(isinstance(self.payload, dict), "Notion application record must be an object")
        for key in ["page_id", "title", "role", "source_file", "search_text"]:
            ensure(isinstance(self.payload.get(key), str) and self.payload[key].strip(), f"{key} must be a non-empty string")
        for key in ["keywords", "gaps"]:
            ensure(isinstance(self.payload.get(key), list), f"{key} must be an array")
        return self.payload


@dataclass(slots=True)
class NotionApplicationsCacheSchema:
    payload: dict[str, Any]

    def validate(self) -> dict[str, Any]:
        ensure(isinstance(self.payload, dict), "Notion applications cache must be an object")
        ensure(isinstance(self.payload.get("version"), int), "cache.version must be an integer")
        ensure(isinstance(self.payload.get("generated_at"), str) and self.payload["generated_at"].strip(), "cache.generated_at must be a non-empty string")
        ensure(isinstance(self.payload.get("source"), dict), "cache.source must be an object")
        coverage = self.payload.get("coverage")
        ensure(isinstance(coverage, dict), "cache.coverage must be an object")
        applications = self.payload.get("applications")
        ensure(isinstance(applications, list), "cache.applications must be an array")
        for item in applications:
            NotionApplicationRecordSchema(item).validate()
        return self.payload

