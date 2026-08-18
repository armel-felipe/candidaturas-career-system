from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from career.utils import ensure


@dataclass
class CvReviewReportSchema:
    payload: dict[str, Any]

    def validate(self) -> dict[str, Any]:
        ensure(isinstance(self.payload, dict), "CV review report must be an object")
        for key in ["kind", "artifact", "company", "role"]:
            ensure(isinstance(self.payload.get(key), str), f"{key} must be a string")
        if "artifact_sha256" in self.payload:
            ensure(
                isinstance(self.payload.get("artifact_sha256"), str),
                "artifact_sha256 must be a string",
            )
        ensure(isinstance(self.payload.get("approved"), bool), "approved must be boolean")
        ensure(isinstance(self.payload.get("approved_for_delivery"), bool), "approved_for_delivery must be boolean")
        ensure(isinstance(self.payload.get("ats_policy"), dict), "ats_policy must be an object")
        ensure(isinstance(self.payload.get("blockers"), list), "blockers must be an array")
        ensure(isinstance(self.payload.get("warnings"), list), "warnings must be an array")
        ensure(isinstance(self.payload.get("totals"), dict), "totals must be an object")
        ensure(isinstance(self.payload.get("weight_total_checks"), list), "weight_total_checks must be an array")
        ensure(isinstance(self.payload.get("minor_checks"), list), "minor_checks must be an array")
        return self.payload


@dataclass
class CvPolishReportSchema:
    payload: dict[str, Any]

    def validate(self) -> dict[str, Any]:
        ensure(isinstance(self.payload, dict), "CV polish report must be an object")
        for key in ["artifact_path", "language"]:
            ensure(isinstance(self.payload.get(key), str) and self.payload[key].strip(), f"{key} must be a non-empty string")
        for key in ["polish_executed", "changed", "rerun_required"]:
            ensure(isinstance(self.payload.get(key), bool), f"{key} must be boolean")
        for key in [
            "sections_reviewed",
            "english_terms_replaced",
            "english_terms_kept",
            "translation_registry_updates_required",
            "translation_registry_updates_applied",
            "approval_blockers",
            "notes",
        ]:
            ensure(isinstance(self.payload.get(key), list), f"{key} must be an array")
        return self.payload
