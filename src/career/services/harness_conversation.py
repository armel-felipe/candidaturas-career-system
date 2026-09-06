from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping


_INTENTS = frozenset(
    {
        "chat",
        "inspect",
        "intake",
        "analyze",
        "resume",
        "generate_cv",
        "generate_cover_letter",
        "update_notion",
        "deliver_onedrive",
        "email_draft",
        "process_package",
    }
)
_AUTHORIZATIONS = frozenset(
    {"none", "user_request", "confirmation", "pending_approval"}
)
_CONFIDENCE = frozenset({"high", "medium", "low"})
_TARGET_HINTS = frozenset({"notion_id", "company", "role", "url", "menu_index"})
_INTERNAL_FIELDS = frozenset(
    {"application_id", "path", "artifact_path", "approval_id", "command"}
)
_EXTERNAL_INTENTS = frozenset(
    {"update_notion", "deliver_onedrive", "email_draft"}
)
_TARGETED_INTENTS = frozenset(
    {
        "intake",
        "analyze",
        "resume",
        "generate_cv",
        "generate_cover_letter",
        "update_notion",
        "deliver_onedrive",
        "email_draft",
        "process_package",
    }
)


@dataclass(frozen=True)
class ContextualPlan:
    """Validated language-level proposal; never an execution scope."""

    intent: str
    target_hints: dict[str, str | int]
    requested_steps: tuple[str, ...]
    authorization: str
    confidence: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ContextualPlan":
        if not isinstance(payload, Mapping):
            raise ValueError("contextual plan must be an object")
        unexpected = set(payload) - {
            "intent",
            "target_hints",
            "requested_steps",
            "authorization",
            "confidence",
        }
        if unexpected:
            raise ValueError(f"unexpected contextual plan fields: {sorted(unexpected)}")

        intent = str(payload.get("intent") or "").strip().casefold()
        if intent not in _INTENTS:
            raise ValueError(f"invalid contextual intent: {intent or 'missing'}")
        authorization = str(payload.get("authorization") or "").strip().casefold()
        if authorization not in _AUTHORIZATIONS:
            raise ValueError(
                f"invalid contextual authorization: {authorization or 'missing'}"
            )
        confidence = str(payload.get("confidence") or "").strip().casefold()
        if confidence not in _CONFIDENCE:
            raise ValueError(f"invalid contextual confidence: {confidence or 'missing'}")

        raw_hints = payload.get("target_hints")
        if not isinstance(raw_hints, Mapping):
            raise ValueError("target_hints must be an object")
        unexpected_hints = set(raw_hints) - _TARGET_HINTS
        internal_hints = unexpected_hints & _INTERNAL_FIELDS
        if internal_hints:
            raise ValueError(f"internal scope field is forbidden: {sorted(internal_hints)[0]}")
        if unexpected_hints:
            raise ValueError(f"unexpected target hint: {sorted(unexpected_hints)[0]}")

        hints: dict[str, str | int] = {}
        for key, raw_value in raw_hints.items():
            if raw_value is None:
                continue
            if key == "menu_index":
                if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value < 1:
                    raise ValueError("menu_index must be a positive integer")
                hints[key] = raw_value
                continue
            value = " ".join(str(raw_value).split()).strip()
            if not value:
                continue
            if len(value) > 160:
                raise ValueError(f"contextual hint too long: {key}")
            if any(marker in value.casefold() for marker in (".career-state", "outputs/", "/", "\\")):
                raise ValueError(f"filesystem path is forbidden in contextual hint: {key}")
            hints[key] = value

        raw_steps = payload.get("requested_steps")
        if not isinstance(raw_steps, list) or any(not isinstance(step, str) for step in raw_steps):
            raise ValueError("requested_steps must be a list of strings")
        requested_steps: list[str] = []
        for raw_step in raw_steps:
            step = " ".join(raw_step.split()).strip().casefold()
            if not step:
                continue
            if len(step) > 80 or not re.fullmatch(r"[a-z][a-z0-9_-]*", step):
                raise ValueError(f"invalid requested step: {step}")
            if step not in requested_steps:
                requested_steps.append(step)

        return cls(
            intent=intent,
            target_hints=hints,
            requested_steps=tuple(requested_steps),
            authorization=authorization,
            confidence=confidence,
        )


def parse_contextual_plan(output: str) -> ContextualPlan | None:
    """Parse one strict JSON plan and discard malformed model output."""
    text = str(output or "").strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(text)
        return ContextualPlan.from_payload(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


@dataclass(frozen=True)
class PolicyDecision:
    mode: str
    reason: str
    requires_approval: bool = False


def evaluate_action_policy(
    plan: ContextualPlan,
    *,
    target_status: str,
    next_step: str,
    target_unique: bool,
) -> PolicyDecision:
    """Decide whether a validated proposal may advance, without side effects."""
    if plan.intent == "chat":
        return PolicyDecision("autonomous", "conversation")
    if plan.confidence != "high":
        return PolicyDecision("clarify", "low_or_medium_confidence")
    normalized_status = str(target_status or "").strip().casefold()
    if normalized_status in {"stale", "stale_or_conflicting", "conflicting"}:
        return PolicyDecision("blocked", "stale_or_conflicting_target")
    if plan.intent in _TARGETED_INTENTS and not target_unique:
        return PolicyDecision("clarify", "target_not_unique")
    if plan.intent in _EXTERNAL_INTENTS:
        return PolicyDecision("approval", "external_side_effect", True)
    if plan.intent in _TARGETED_INTENTS and not str(next_step or "").strip():
        return PolicyDecision("blocked", "canonical_next_step_missing")
    return PolicyDecision("autonomous", "scoped_internal_action")
