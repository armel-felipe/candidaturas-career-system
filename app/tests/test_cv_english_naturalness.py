from __future__ import annotations

import pytest

from career.services import cv_content
from career.utils import ValidationFailure


def _english_payload(*, summary: str, bullet: str) -> dict:
    return {
        "metadata": {"language": "en"},
        "summary": summary,
        "experiences": [{"bullets": [bullet]}],
    }


def test_english_editorial_guard_rejects_literal_and_autobiographical_copy():
    payload = _english_payload(
        summary="Operations executive. I have delivered expansion. I am pursuing a Director role.",
        bullet=(
            "I led FieldOps, managing 240 direct and indirect people with full scope autonomy, "
            "which allowed me to deliver expansion through a correctly modeled ROI."
        ),
    )

    with pytest.raises(ValidationFailure, match="english_editorial_guard"):
        cv_content.validate_english_editorial_quality(payload)


def test_english_editorial_guard_accepts_natural_executive_copy():
    payload = _english_payload(
        summary=(
            "Operations executive with 20+ years of experience across operations and planning. "
            "Track record of scaling coverage and improving cost and service performance."
        ),
        bullet=(
            "Led FieldOps across geographic expansion and budget allocation for a 240-person "
            "organization, using executive S&OP scenarios to scale coverage and improve fleet utilization."
        ),
    )

    result = cv_content.validate_english_editorial_quality(payload)

    assert result["status"] == "ok"
    assert result["violations"] == []


def test_canonical_english_render_values_pass_editorial_guard_after_rewrite():
    facts = cv_content.load_canonical_cv_facts()
    experiences = [
        cv_content._materialize_experience(entry, "operations", language="en")
        for entry in cv_content._facts_experiences()
    ]
    summary, _support = cv_content._build_summary(
        experiences[:5],
        {"cargo": "Operations Director"},
        language="en",
    )

    result = cv_content.validate_english_editorial_quality(
        {
            "metadata": {"language": "en"},
            "summary": summary,
            "experiences": [{"bullets": item["bullets"]} for item in experiences],
            "facts_revision": facts["schema_version"],
        }
    )

    assert result["status"] == "ok"
