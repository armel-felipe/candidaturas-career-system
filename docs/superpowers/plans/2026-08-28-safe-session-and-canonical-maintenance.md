# Safe Session Resolution and Canonical Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `vagas_bot_01` resolve the current candidature internally from SQLite and escalate legitimate canonical-code repairs through a controlled maintenance patch path.

**Architecture:** Normal candidature runs remain scoped to `.career-state/applications_v2/<application_id>` and keep the project source mounted read-only. Session bindings are persisted in SQLite and resolved before JSON compatibility mirrors. Canonical repairs are proposed as allowlisted patches and applied only by an explicit host-side maintenance command after validation.

**Tech Stack:** Python 3.12, SQLite, existing `HarnessSupervisor`, Hermes shell hooks, unittest/pytest-compatible project tests, Docker Compose.

**Spec:** `AGENTS.md`, `.agents/skills/career-system/SKILL.md`, and `docs/roadmap.md`.

## Global Constraints

- SQLite `control-plane/career.db` is the authoritative runtime store.
- The normal bot container must not gain general write access to the project source.
- Every candidature artifact remains scoped by `application_id`.
- Canonical maintenance must use an explicit allowlist, patch validation, and test evidence.
- No CV gate, provenance, or Notion write may be bypassed.

### Task 1: SQLite-backed session binding

**Files:**
- Modify: `src/career/services/application_context.py:881-914`
- Modify: `src/career/services/harness_supervisor.py:1726-1749,1888-1907`
- Test: `tests/test_harness_continuity.py`

**Interfaces:**
- `register_session(..., database: Database | None = None)` writes `active_application_id` to SQLite and keeps the JSON mirror best-effort.
- `resolve_session(..., database: Database | None = None)` reads SQLite first and uses the JSON mirror only as compatibility fallback.

- [x] Write a failing test proving a session binding survives without `session_registry.json`.
- [x] Run the focused test and observe the expected failure.
- [x] Implement SQLite persistence using the existing `session_memory` table and explicit database injection from `HarnessSupervisor`.
- [x] Run the focused test and the existing continuity tests.

### Task 2: Conversation routing and truthful pipeline state

**Files:**
- Modify: `src/career/services/harness_supervisor.py:395-461,1356-1477`
- Test: `tests/test_harness_dispatch.py`, `tests/test_harness_continuity.py`, `tests/test_harness_scoped_status.py`

**Interfaces:**
- Queries that request a Notion duplicate precheck route deterministically before any write.
- Generic continuation messages use the SQLite-resolved candidature and pending pipeline intent.
- `_execute_pipeline_request` returns `blocked` with `no_pipeline_stage_executed` when no stage actually ran.

- [x] Write failing tests for the Notion precheck route, session-bound continuation, and empty-stage result.
- [x] Run them and verify they fail for the current generic/falso-completed behavior.
- [x] Implement the smallest routing and result-state changes.
- [x] Run the focused harness suite.

### Task 3: Controlled canonical maintenance patch path

**Files:**
- Create: `src/career/services/maintenance.py`
- Modify: `src/career/cli.py`, `src/career/services/harness_supervisor.py`, `package.json`
- Modify: `scripts/hermes_harness_context_hook.py`
- Test: `tests/test_canonical_maintenance.py`

**Interfaces:**
- `create_maintenance_request(objective, allowed_paths)` persists a request under `.career-state/maintenance/`.
- `apply_maintenance_patch(patch_path, request_path, dry_run=True)` accepts only unified diffs touching explicitly allowlisted canonical files and rejects candidature/output/state paths.
- The normal Hermes hook can return a structured maintenance request instead of pretending to apply a source edit inside the read-only container.

- [x] Write failing tests for rejecting unallowlisted paths and accepting a patch limited to `src/career/services/cv_content.py`.
- [x] Run them and observe the expected failure.
- [x] Implement patch validation and dry-run application without changing source in normal bot mode.
- [x] Add an explicit host command for reviewed application of the patch and test it with a temporary repository.
- [x] Run maintenance tests and `validate:structure`.

### Task 4: Runtime hook containment and regression verification

**Files:**
- Modify: `hermes-src/agent/shell_hooks.py:509-514` or the narrow hook contract boundary selected by the failing test
- Modify: `scripts/hermes_harness_context_hook.py`
- Test: `hermes-src/tests/agent/` hook tests and focused project tests

**Interfaces:**
- A timed-out pre-LLM harness hook must not silently hand the user message to an unconstrained candidature agent.
- The runtime returns a visible structured block or retryable continuation state.

- [x] Write a failing timeout regression test.
- [x] Run it and verify the current timeout behavior.
- [x] Implement fail-closed timeout handling.
- [x] Run the Hermes hook tests, project focused tests, structural validation, and the bot route/health smoke check. The visible response path after a real timeout remains an open integration check.

### Task 5: Reconcile documentation and live evidence

**Files:**
- Modify: `docs/roadmap.md`
- Test: commands from the verification checklist below

- [x] Reopen or add roadmap items for the session-memory and maintenance regressions with evidence paths.
- [x] Run `npm run validate:structure`.
- [x] Run focused continuity, routing, maintenance, and hook tests.
- [x] Run the applicable runtime verification using the container's injected SQLite path.
