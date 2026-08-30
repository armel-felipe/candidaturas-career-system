from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


_DEPENDENCY_FIELDS = (
    "candidate_evidence_revision_id",
    "positioning_revision_id",
    "fit_map_revision_id",
)


def evaluate_positioning_coverage(
    pack: Mapping[str, Any], artifacts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Check that each selected artifact translates the stories it requires.

    Coverage is deliberately ID-based.  Textual similarity cannot prove that
    an artifact used a defensible story or claim from the selected pack.
    """
    stories = [
        story
        for story in pack.get("stories", [])
        if isinstance(story, Mapping) and _text(story.get("story_id"))
    ]
    story_ids = [_text(story["story_id"]) for story in stories]
    claims_by_story = {
        _text(story["story_id"]): {
            _text(claim)
            for claim in story.get("allowed_claims", [])
            if _text(claim)
        }
        for story in stories
    }
    supported_claims = {
        claim for claims in claims_by_story.values() for claim in claims
    }
    targets = pack.get("artifact_targets")
    required_by_kind = {
        kind: _required_story_ids(targets, kind, story_ids)
        for kind in _target_kinds(targets)
    }
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        kind = _text(artifact.get("kind"))
        if kind and kind not in required_by_kind:
            required_by_kind[kind] = _required_story_ids(targets, kind, story_ids)

    covered: dict[str, list[str]] = {}
    uncovered: dict[str, list[str] | str] = {}
    unsupported_claims: list[dict[str, Any]] = []
    stale_dependencies: list[dict[str, Any]] = []

    for kind, required in required_by_kind.items():
        matching = [
            artifact
            for artifact in artifacts
            if isinstance(artifact, Mapping) and _text(artifact.get("kind")) == kind
        ]
        if not required:
            covered[kind] = []
            uncovered[kind] = "not_required"
            continue
        selected_ids = {
            story_id
            for artifact in matching
            for story_id in _ids(artifact.get("positioning_story_ids"))
        }
        covered[kind] = [story_id for story_id in required if story_id in selected_ids]
        uncovered[kind] = [story_id for story_id in required if story_id not in selected_ids]

    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        artifact_id = _text(artifact.get("artifact_id")) or _text(artifact.get("id"))
        kind = _text(artifact.get("kind"))
        selected_story_ids = set(_ids(artifact.get("positioning_story_ids")))
        allowed_for_artifact = {
            claim
            for story_id in selected_story_ids
            for claim in claims_by_story.get(story_id, set())
        }
        for claim_id in _ids(artifact.get("positioning_claim_ids")):
            if claim_id not in supported_claims or claim_id not in allowed_for_artifact:
                unsupported_claims.append(
                    {"artifact_id": artifact_id, "claim_id": claim_id}
                )
        for field in _DEPENDENCY_FIELDS:
            expected = _text(pack.get(field))
            actual = _text(artifact.get(field))
            if expected and actual and expected != actual:
                stale_dependencies.append(
                    {
                        "artifact_id": artifact_id,
                        "dependency": field,
                        "expected": expected,
                        "actual": actual,
                    }
                )

    approved = not unsupported_claims and not stale_dependencies and all(
        value in ([], "not_required") for value in uncovered.values()
    )
    return {
        "covered": covered,
        "uncovered": uncovered,
        "unsupported_claims": unsupported_claims,
        "stale_dependencies": stale_dependencies,
        "approved": approved,
    }


def _target_kinds(targets: Any) -> list[str]:
    if isinstance(targets, Mapping):
        return [_text(key) for key in targets if _text(key)]
    if isinstance(targets, list):
        return [_text(item) for item in targets if _text(item)]
    return []


def _required_story_ids(targets: Any, kind: str, fallback: Sequence[str]) -> list[str]:
    if isinstance(targets, Mapping) and kind in targets:
        config = targets[kind]
        if isinstance(config, Mapping):
            values = config.get("required_story_ids", fallback)
        else:
            values = config
        if values is None or values is False:
            return []
        if isinstance(values, list):
            return _ids(values)
    if isinstance(targets, list) and kind in targets:
        return list(fallback)
    return []


def _ids(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in value:
        text = _text(item)
        if text and text not in result:
            result.append(text)
    return result


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""
