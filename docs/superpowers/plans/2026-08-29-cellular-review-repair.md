# Cellular Review Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure a cellular CV run automatically enters the canonical repair cycle when `review_cv` finds repairable ATS blockers, instead of stopping at review.

**Architecture:** Keep the immutable cell DAG as the source of run state, but add an application-scoped repair handoff from a blocked `review_cv` attempt to the existing repair-agent workflow. The repair agent writes only a new scoped CV-content candidate; deterministic validation then republishes the content through `compose_cv`, invalidates render/review/delivery descendants, and resumes the same run.

**Tech Stack:** Python, SQLite-backed cell executor, pytest, Hermes/HarnessSupervisor, application-scoped JSON artifacts.

**Spec:** `.agents/skills/processe-a-vaga/SKILL.md` and `.agents/skills/output-reviewer/SKILL.md`.

## Global Constraints

- Use the SQLite control plane and explicit `application_id`/`run_id` for every operation.
- Repair only defensible CV content; never invent facts or force unsupported keywords.
- Keep 4–8 experiences and exactly 3 concise bullets per experience unless explicitly changed by the user.
- Re-render, register ATS keywords, and rerun the objective review after every repair.
- Do not deliver unless `approved_for_delivery=true` and the delivery receipt is verified.
- Preserve unrelated existing worktree changes.

### Task 1: Make the blocked review produce an application-scoped repair handoff

**Files:**
- Modify: `src/career/services/applications_v2.py`
- Modify: `src/career/services/harness_supervisor.py`
- Test: `tests/test_cellular_cv_repair.py`

- [x] Write a failing test proving that a repairable `review_cv` blocker creates a scoped repair request with the exact missing top-eight keywords and no global paths.
- [x] Run the focused test and verify it fails because cellular review currently returns only `blocked`.
- [x] Implement the smallest scoped handoff that writes the request and dispatches the repair stage without asking for a new internal application ID.
- [x] Run the focused test and verify it passes.

### Task 2: Re-enter the same run through CV composition and review

**Files:**
- Modify: `src/career/cells/contracts.py`
- Modify: `src/career/cells/executor.py`
- Modify: `src/career/cells/handlers.py`
- Modify: `src/career/services/applications_v2.py`
- Test: `tests/test_cellular_cv_repair.py`

- [x] Write a failing test proving that a successful repaired content candidate invalidates stale render/review/delivery attempts and makes `render_cv` ready in the same run.
- [x] Run the focused test and verify it fails because `review_cv` repair currently retries the unchanged artifact.
- [x] Implement external repaired-content publication with immutable attempt provenance and existing validators.
- [x] Run the focused test and the existing cellular CV tests.

### Task 3: Correct scoped keyword registry resolution and validate the runtime

**Files:**
- Modify: `src/career/services/fit_map.py`
- Modify: `src/career/services/intake.py`
- Modify: `src/career/cli.py`
- Test: `tests/test_fit_map_application_scope.py`
- Modify: `docs/roadmap.md`

- [x] Write a failing test proving status/resume/progress use the application registry rather than `.career-state/derived/keyword_ats_registry.json`.
- [x] Run the focused test and verify it fails with the global registry path.
- [x] Add explicit registry-path propagation from `ApplicationPaths` through status and guard calls.
- [x] Run focused tests, structural validation, runtime verification, and `git diff --check`.
- [x] Record evidence and move `CELLULAR-009` to `DONE` only after the bot-01 canary reaches review and repair without a false ID/registry block.

## Evidence

- `run_b750a8f962a8428a99b6611f347dbd76` reached `review_cv` with a real ATS blocker and created the scoped repair handoff; its candidate was rejected by canonical provenance validation and was not delivered.
- `run_c3a26b408d264e278eceaee094820929` completed the same application DAG through `sync_notion_final`: CV review 7.8/8, zero unexplained top-eight gaps, OneDrive `delivered`, and Notion final sync `succeeded`.
- Official reconciliation sealed the SQLite projection as `core_package_sealed`; an independent `review_output.py` rerun passed 12/12 blockers.
- Focused suite: 34 passed; `validate:structure`, `runtime:verify -- --strict`, `py_compile`, and `git diff --check` passed.
