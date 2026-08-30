from __future__ import annotations

from career.services.positioning_coverage import evaluate_positioning_coverage


def _pack() -> dict:
    return {
        "candidate_evidence_revision_id": "evidence-v2",
        "positioning_revision_id": "positioning-v2",
        "fit_map_revision_id": "fit-v2",
        "stories": [
            {"story_id": "story_a", "allowed_claims": ["claim_a"]},
            {"story_id": "story_b", "allowed_claims": ["claim_b"]},
        ],
        "claims": ["claim_a", "claim_b"],
        "artifact_targets": {
            "cv": {"required_story_ids": ["story_a", "story_b"]},
            "feras": {"required_story_ids": ["story_a", "story_b"]},
            "networking_message": {"required_story_ids": []},
        },
    }


def test_identifies_story_missing_from_cv_but_not_from_feras() -> None:
    result = evaluate_positioning_coverage(
        _pack(),
        [
            {
                "artifact_id": "cv-v1",
                "kind": "cv",
                "positioning_story_ids": ["story_a"],
                "positioning_claim_ids": ["claim_a"],
                "candidate_evidence_revision_id": "evidence-v2",
                "positioning_revision_id": "positioning-v2",
            },
            {
                "artifact_id": "feras-v1",
                "kind": "feras",
                "positioning_story_ids": ["story_a", "story_b"],
                "positioning_claim_ids": ["claim_a", "claim_b"],
                "candidate_evidence_revision_id": "evidence-v2",
                "positioning_revision_id": "positioning-v2",
            },
        ],
    )

    assert result["covered"]["cv"] == ["story_a"]
    assert result["uncovered"]["cv"] == ["story_b"]
    assert result["uncovered"]["feras"] == []
    assert result["unsupported_claims"] == []
    assert result["approved"] is False


def test_marks_stale_dependencies_and_optional_unused_format_as_not_required() -> None:
    result = evaluate_positioning_coverage(
        _pack(),
        [
            {
                "artifact_id": "cv-v1",
                "kind": "cv",
                "positioning_story_ids": ["story_a", "story_b"],
                "positioning_claim_ids": ["claim_a", "claim_b"],
                "candidate_evidence_revision_id": "evidence-v1",
                "positioning_revision_id": "positioning-v2",
            }
        ],
    )

    assert result["uncovered"]["networking_message"] == "not_required"
    assert result["stale_dependencies"] == [
        {
            "artifact_id": "cv-v1",
            "dependency": "candidate_evidence_revision_id",
            "expected": "evidence-v2",
            "actual": "evidence-v1",
        }
    ]
    assert result["approved"] is False


def test_claim_not_allowed_by_any_evidence_story_is_unsupported() -> None:
    pack = _pack()
    pack["claims"] = ["claim_a", "claim_without_evidence"]

    result = evaluate_positioning_coverage(
        pack,
        [
            {
                "artifact_id": "feras-v1",
                "kind": "feras",
                "positioning_story_ids": ["story_a", "story_b"],
                "positioning_claim_ids": ["claim_a", "claim_without_evidence"],
                "candidate_evidence_revision_id": "evidence-v2",
                "positioning_revision_id": "positioning-v2",
            }
        ],
    )

    assert result["unsupported_claims"] == [
        {"artifact_id": "feras-v1", "claim_id": "claim_without_evidence"}
    ]
    assert result["approved"] is False
