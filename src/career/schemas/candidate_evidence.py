from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from career.utils import ValidationFailure


REQUIRED_STORY_FIELDS = (
    "story_id",
    "title",
    "context",
    "actions",
    "results",
    "capabilities",
    "allowed_claims",
    "source_refs",
)


def validate_candidate_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValidationFailure("candidate evidence root must be an object")
    if payload.get("schema_version") != 1:
        raise ValidationFailure("schema_version must be 1")
    candidate = payload.get("candidate")
    if not isinstance(candidate, Mapping):
        raise ValidationFailure("candidate must be an object")
    stories = payload.get("stories")
    if not isinstance(stories, Sequence) or isinstance(stories, (str, bytes)):
        raise ValidationFailure("stories must be an array")
    if not stories:
        raise ValidationFailure("stories must not be empty")

    seen_ids: set[str] = set()
    for index, story in enumerate(stories):
        path = f"stories[{index}]"
        if not isinstance(story, Mapping):
            raise ValidationFailure(f"{path} must be an object")
        missing = [field for field in REQUIRED_STORY_FIELDS if field not in story]
        if missing:
            raise ValidationFailure(f"{path} missing fields: {', '.join(missing)}")

        story_id = _required_text(story.get("story_id"), f"{path}.story_id")
        if story_id in seen_ids:
            raise ValidationFailure(f"duplicate story_id: {story_id}")
        seen_ids.add(story_id)
        _required_text(story.get("title"), f"{path}.title")
        _required_text(story.get("context"), f"{path}.context")
        _string_list(story.get("actions"), f"{path}.actions")
        _string_list(story.get("results"), f"{path}.results")
        _string_list(story.get("capabilities"), f"{path}.capabilities")
        _string_list(story.get("allowed_claims"), f"{path}.allowed_claims")
        _source_refs(story.get("source_refs"), f"{path}.source_refs")

        metrics = story.get("metrics", [])
        _string_list(metrics, f"{path}.metrics", required=False)
        guidance = story.get("artifact_guidance", {})
        if not isinstance(guidance, Mapping):
            raise ValidationFailure(f"{path}.artifact_guidance must be an object")
        for key, value in guidance.items():
            _required_text(value, f"{path}.artifact_guidance.{key}")

    return dict(payload)


def _required_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationFailure(f"{path} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, path: str, *, required: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise ValidationFailure(f"{path} must be an array")
    if required and not value:
        raise ValidationFailure(f"{path} must not be empty")
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(_required_text(item, f"{path}[{index}]"))
    return normalized


def _source_refs(value: Any, path: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValidationFailure(f"{path} must be a non-empty array")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(item, Mapping):
            raise ValidationFailure(f"{item_path} must be an object")
        normalized.append(
            {
                "path": _required_text(item.get("path"), f"{item_path}.path"),
                "lines": _required_text(item.get("lines"), f"{item_path}.lines"),
            }
        )
    return normalized
