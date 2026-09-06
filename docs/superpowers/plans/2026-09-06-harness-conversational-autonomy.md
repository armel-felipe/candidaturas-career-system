# HARNESS-036 Conversational Autonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow natural-language conversation to advance unambiguous, scoped internal career work while keeping canonical identity resolution and external-action authorization deterministic.

**Architecture:** Preserve the deterministic classifier as the fast path and extract the existing model-based application interpreter into a validated contextual planner. The planner emits only intent and user-visible hints; a canonical SQLite resolver supplies `application_id`, a pure policy service decides autonomy versus approval, and the existing scoped executor performs the work. Conversation history and audit records remain session/profile scoped.

**Tech Stack:** Python 3, dataclasses, JSON validation, SQLite-backed `HarnessSupervisor`, Hermes safe-mode subprocess, pytest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-06-harness-conversational-autonomy-design.md`

## Global Constraints

- The planner must never emit or select an internal `application_id`, filesystem path, artifact path, approval ID, or tool command.
- SQLite `control-plane/career.db` is the authority for candidate identity, fingerprints, next step, approvals, and delivery receipts.
- A unique canonical match may proceed; multiple, weak, stale, or conflicting matches must ask or block.
- Internal scoped intake, analysis, FIT_MAP finalization, validation, and requested document generation may advance autonomously when intent is clear.
- Notion, Gmail, OneDrive, overwrite, destructive cleanup, and cross-bot handoff retain approval/confirmation boundaries.
- `/new`, pending input, conversation history, and pipeline intent remain isolated by runtime/profile/session.
- Use TDD for every behavior change: write one failing test, run it, implement the smallest change, rerun the test, then run the relevant regression suite.
- Do not modify `RUNTIME-030`, bot profile configuration, credentials, or specialist contracts as part of this plan.
- Every operational execution must record the interpreted request and the resolved canonical application without using the audit record as future authority.

---

### Task 1: Add validated contextual-plan and authorization contracts

**Files:**
- Create: `src/career/services/harness_conversation.py`
- Create: `tests/test_harness_conversation.py`
- Reference: `docs/superpowers/specs/2026-09-06-harness-conversational-autonomy-design.md`

**Interfaces:**
- `ContextualPlan.from_payload(payload: Mapping[str, Any]) -> ContextualPlan`.
- `parse_contextual_plan(output: str) -> ContextualPlan | None`.
- `PolicyDecision` and `evaluate_action_policy(plan: ContextualPlan, *, target_status: str, next_step: str, target_unique: bool) -> PolicyDecision`.
- `ContextualPlan` fields: `intent`, `target_hints`, `requested_steps`, `authorization`, `confidence`.
- Allowed target hints: `notion_id`, `company`, `role`, `url`, and `menu_index` only.

- [ ] **Step 1: Write failing parser tests.**

Cover plain JSON, fenced JSON, invalid internal `application_id`, invalid filesystem path, unknown intent, missing confidence, and invalid authorization.

```python
def test_contextual_plan_rejects_internal_scope_fields():
    with pytest.raises(ValueError, match="application_id"):
        ContextualPlan.from_payload({
            "intent": "resume",
            "target_hints": {"application_id": "notion_625"},
            "requested_steps": [],
            "authorization": "user_request",
            "confidence": "high",
        })
```

- [ ] **Step 2: Verify RED.**

Run: `./scripts/python.sh -m pytest tests/test_harness_conversation.py -q`  
Expected: collection or assertion failure because the contract module does not exist.

- [ ] **Step 3: Implement the strict contract.**

Use frozen dataclasses and explicit allowlists. Strip one optional JSON fence, parse one object, normalize whitespace, cap hint lengths at 160 characters, reject extra keys and internal-scope fields, and return `None` for malformed output in `parse_contextual_plan`.

- [ ] **Step 4: Write failing policy tests.**

Cover free chat, autonomous unique `analyze`/`resume`, approval-gated Notion/OneDrive/email, ambiguous/stale states, and low-confidence plans.

- [ ] **Step 5: Implement the pure policy function.**

Return `PolicyDecision(mode, reason, requires_approval)` without filesystem access or tool calls. Map external intents to approval and stale/ambiguous/low-confidence states to clarification or blocking.

- [ ] **Step 6: Verify GREEN and commit.**

Run: `./scripts/python.sh -m pytest tests/test_harness_conversation.py -q`  
Expected: all contract and policy tests pass.

```bash
git add src/career/services/harness_conversation.py tests/test_harness_conversation.py
git commit -m "feat: add safe conversational plan contract"
```

### Task 2: Extract the natural-language interpreter into a contextual planner

**Files:**
- Modify: `src/career/services/harness_supervisor.py:2990-3220`
- Modify: `src/career/services/harness_conversation.py`
- Modify: `tests/test_harness_conversation.py`
- Modify: `tests/test_harness_dispatch.py`

**Interfaces:**
- `ContextualPlanner.plan(message: str, *, history: list[dict[str, str]], last_result: dict[str, Any] | None, menu_context: dict[str, Any] | None, profile_name: str | None, model: str | None) -> ContextualPlan | None`.
- `_model_natural_application_interpretation()` remains a compatibility adapter and may return only `intent`, `company`, `role`, and a message-derived `record_id`.

- [ ] **Step 1: Write failing planner tests.**

Inject a response for `"faz o próximo passo desta candidatura"`; assert `intent="resume"`, no internal ID, no path, and no command. Add invalid-output, timeout, and ordinary `"olá"` cases that return `None`.

- [ ] **Step 2: Verify RED.**

Run: `./scripts/python.sh -m pytest tests/test_harness_conversation.py tests/test_harness_dispatch.py -q`  
Expected: the new planner interface tests fail before extraction.

- [ ] **Step 3: Implement the safe-mode planner runner.**

Reuse `resolve_hermes_command`, `--safe-mode`, empty toolsets, profile selection, `CAREER_HARNESS_SUBAGENT=1`, the existing bounded timeout environment variable, and normalized bounded history. Parse only through `parse_contextual_plan`; never pass planner output directly to a specialist.

- [ ] **Step 4: Preserve the deterministic fast path.**

Run the planner only after exact routing fails and only for an operational candidate or bound-session continuation. Keep deterministic natural extraction first, preserve negation handling, and retain canonical-catalog fallback when the model is unavailable.

- [ ] **Step 5: Verify GREEN and commit.**

Run: `./scripts/python.sh -m pytest tests/test_harness_conversation.py tests/test_harness_dispatch.py -q`  
Expected: planner tests and the existing dispatcher regressions pass.

```bash
git add src/career/services/harness_conversation.py src/career/services/harness_supervisor.py tests/test_harness_conversation.py tests/test_harness_dispatch.py
git commit -m "feat: add contextual planner for natural career requests"
```

### Task 3: Integrate planner, resolver, policy, and the single execution trunk

**Files:**
- Modify: `src/career/services/harness_supervisor.py:1585-2220, 3258-3395, 3740-3795, 4549-4595`
- Modify: `tests/test_harness_dispatch.py`
- Modify: `tests/test_harness_continuity.py`
- Modify: `tests/test_harness_pending_confirmation.py`

**Interfaces:**
- `handle_message()` keeps deterministic routes and invokes the planner only for unresolved contextual turns.
- Planner target hints call `_resolve_natural_application(..., interpreted_parameters=...)`; only the resolver produces internal `application_id`.
- Planner continuation without hints uses the exact session-bound application only for an explicit continuation intent.
- Planner-driven operational results include compact `plan`/`policy` projections and a `harness_conversational_plan` workflow event.

- [ ] **Step 1: Write failing natural-continuation tests.**

With a bound application and injected plan for `"faz o próximo passo"`, assert the canonical `next_required_step` executes through the existing executor. Add unique company/role and multiple-candidate cases; the latter must show options and execute nothing.

- [ ] **Step 2: Write failing authorization tests.**

Assert natural Notion-update language creates the existing approval request without calling the specialist. Assert `"sim"` without a preceding offer remains generic; after the offer it uses the persisted session target.

- [ ] **Step 3: Implement planner handoff.**

Load session history, obtain a validated plan after deterministic classification, keep `chat` on `_run_generic_message`, and convert only operational plan intents into existing resolver/workflow paths.

- [ ] **Step 4: Enforce policy at execution.**

Before specialist or delivery calls, evaluate uniqueness, canonical next step, fingerprint freshness, and authorization. Return `awaiting_approval`, `awaiting_input`, or `blocked` without invoking a specialist when denied.

- [ ] **Step 5: Add the audit projection.**

Record runtime, profile, session, turn, intent, hints, resolver outcome, canonical fingerprint, next step, authorization, policy, execution status, and bounded `understood_as`. Do not make model output an authority.

- [ ] **Step 6: Verify GREEN and commit.**

Run: `./scripts/python.sh -m pytest tests/test_harness_conversation.py tests/test_harness_dispatch.py tests/test_harness_continuity.py tests/test_harness_pending_confirmation.py -q`  
Expected: natural-routing, ambiguity, stale-state, context, and approval tests pass.

```bash
git add src/career/services/harness_supervisor.py tests/test_harness_dispatch.py tests/test_harness_continuity.py tests/test_harness_pending_confirmation.py
git commit -m "feat: integrate safe conversational autonomy"
```

### Task 4: Verify transport, `/new`, and cross-bot isolation

**Files:**
- Modify: `scripts/telegram_harness_adapter.py` only if plan/policy fields are stripped.
- Modify: `scripts/hermes_harness_dispatch_worker.py` only if a plan result loses its reply.
- Modify: `tests/test_harness_async_dispatch_worker_reply.py`
- Modify: `tests/test_harness_live_regressions.py`
- Modify: `tests/test_harness_dispatch.py`

**Interfaces:**
- Adapter/worker preserve `status`, `display_text`, `application_id`, plan/policy, and blocker/approval details.
- New sessions cannot consume old session plan, pending input, pipeline intent, or approval.

- [ ] **Step 1: Write failing transport/isolation tests.**

Replay a planner result through the adapter and require a non-empty reply. Use the same chat ID with two profiles and assert no state crosses. Send `/new` and assert a vague continuation requests fresh identity.

- [ ] **Step 2: Verify RED.**

Run: `./scripts/python.sh -m pytest tests/test_harness_async_dispatch_worker_reply.py tests/test_harness_live_regressions.py tests/test_harness_dispatch.py -q`  
Expected: the new propagation or `/new` assertion fails before any needed transport change.

- [ ] **Step 3: Implement only required propagation.**

Preserve terminal statuses and the existing missing-reply fallback. Add compact plan/policy fields only where the adapter strips nested data; the worker must not infer identity or authorize actions.

- [ ] **Step 4: Verify GREEN.**

Run: `./scripts/python.sh -m pytest tests/test_harness_async_dispatch_worker_reply.py tests/test_harness_live_regressions.py tests/test_harness_dispatch.py -q`  
Expected: worker, adapter, `/new`, profile-isolation, and no-reply regressions pass.

- [ ] **Step 5: Verify both containers.**

```bash
docker compose -f compose.yaml ps --format '{{.Service}} {{.State}}'
docker compose -f compose.yaml exec -T vagas_bot_01 sh -lc 'PYTHONPATH=/workspace/candidaturas/src /opt/hermes/.venv/bin/python -m pytest tests/test_harness_conversation.py tests/test_harness_dispatch.py -q'
docker compose -f compose.yaml exec -T vagas_bot_02 sh -lc 'PYTHONPATH=/workspace/candidaturas/src /opt/hermes/.venv/bin/python -m pytest tests/test_harness_conversation.py tests/test_harness_dispatch.py -q'
```

Expected: both services remain running and report the same focused result; this verification performs no external delivery or Notion write.

- [ ] **Step 6: Commit transport changes if any.**

```bash
git add scripts/telegram_harness_adapter.py scripts/hermes_harness_dispatch_worker.py tests/test_harness_async_dispatch_worker_reply.py tests/test_harness_live_regressions.py tests/test_harness_dispatch.py
git commit -m "test: verify conversational autonomy across bot transport"
```

### Task 5: Run completion gates and close the roadmap item

**Files:**
- Modify: `docs/roadmap.md`
- Reference: `docs/superpowers/specs/2026-09-06-harness-conversational-autonomy-design.md`

- [ ] **Step 1: Run the complete harness regression group.**

Run: `./scripts/python.sh -m pytest tests/test_harness_conversation.py tests/test_harness_dispatch.py tests/test_harness_continuity.py tests/test_harness_pending_confirmation.py tests/test_harness_async_dispatch.py tests/test_harness_async_dispatch_worker_reply.py tests/test_harness_live_regressions.py tests/test_harness_serial_pipeline.py tests/test_runtime_repairs.py -q`  
Expected: all selected harness and continuity tests pass.

- [ ] **Step 2: Run project validation gates.**

```bash
npm run validate:structure
npm run runtime:verify -- --strict
git diff --check
```

Expected: structure passes, strict runtime reports `blockers: []`, and diff check is clean.

- [ ] **Step 3: Inspect two-bot evidence.**

Record container status, route-only natural-paraphrase probes, and the absence of unauthorized filesystem changes. Never claim an external action without its receipt.

- [ ] **Step 4: Update the roadmap with evidence.**

Keep `HARNESS-036` `IN_PROGRESS` if any acceptance criterion is unproven. Set it to `DONE` only after planner, resolver/policy, transport, both-container, and gate evidence is present; record exact counts, commands, status, and non-blocking warnings.

- [ ] **Step 5: Commit the evidence update.**

```bash
git add docs/roadmap.md
git commit -m "docs: record HARNESS-036 verification evidence"
```

