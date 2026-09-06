from __future__ import annotations

import pytest

from career.services.harness_conversation import (
    ContextualPlan,
    evaluate_action_policy,
    parse_contextual_plan,
)


def _plan_payload(**overrides):
    payload = {
        "intent": "resume",
        "target_hints": {"company": "Keeta", "role": "Sales Operations Manager"},
        "requested_steps": [],
        "authorization": "user_request",
        "confidence": "high",
    }
    payload.update(overrides)
    return payload


def test_contextual_plan_parses_plain_and_fenced_json():
    plain = parse_contextual_plan(
        '{"intent":"resume","target_hints":{"company":"Keeta"},'
        '"requested_steps":[],"authorization":"user_request","confidence":"high"}'
    )
    fenced = parse_contextual_plan(
        "```json\n"
        '{"intent":"analyze","target_hints":{"notion_id":"625"},'
        '"requested_steps":[],"authorization":"user_request","confidence":"high"}'
        "\n```"
    )

    assert plain is not None
    assert plain.intent == "resume"
    assert fenced is not None
    assert fenced.target_hints["notion_id"] == "625"


def test_contextual_plan_rejects_internal_scope_fields():
    with pytest.raises(ValueError, match="application_id"):
        ContextualPlan.from_payload(
            _plan_payload(target_hints={"application_id": "notion_625"})
        )

    with pytest.raises(ValueError, match="filesystem path"):
        ContextualPlan.from_payload(
            _plan_payload(target_hints={"company": ".career-state/applications_v2"})
        )


@pytest.mark.parametrize(
    "payload",
    [
        _plan_payload(intent="unknown"),
        _plan_payload(confidence=""),
        _plan_payload(authorization="maybe"),
        _plan_payload(extra="not allowed"),
    ],
)
def test_contextual_plan_rejects_invalid_contract(payload):
    with pytest.raises(ValueError):
        ContextualPlan.from_payload(payload)


def test_malformed_contextual_output_is_not_executable():
    assert parse_contextual_plan("not JSON") is None
    assert parse_contextual_plan('{"intent":"resume"}') is None


@pytest.mark.parametrize(
    ("plan", "target_status", "next_step", "target_unique", "mode", "approval"),
    [
        (_plan_payload(intent="chat", target_hints={}), "", "", True, "autonomous", False),
        (_plan_payload(intent="analyze"), "active", "fill_fit_map_draft", True, "autonomous", False),
        (_plan_payload(intent="resume"), "active", "build_fit_map", True, "autonomous", False),
        (_plan_payload(intent="update_notion"), "active", "sync_notion", True, "approval", True),
        (_plan_payload(intent="deliver_onedrive"), "active", "deliver_cv_onedrive", True, "approval", True),
        (_plan_payload(intent="email_draft"), "active", "email_draft", True, "approval", True),
        (_plan_payload(intent="resume"), "active", "build_fit_map", False, "clarify", False),
        (_plan_payload(intent="resume"), "stale", "build_fit_map", True, "blocked", False),
        (_plan_payload(intent="resume", confidence="low"), "active", "build_fit_map", True, "clarify", False),
    ],
)
def test_action_policy_separates_autonomy_from_external_effects(
    plan, target_status, next_step, target_unique, mode, approval
):
    decision = evaluate_action_policy(
        ContextualPlan.from_payload(plan),
        target_status=target_status,
        next_step=next_step,
        target_unique=target_unique,
    )

    assert decision.mode == mode
    assert decision.requires_approval is approval
