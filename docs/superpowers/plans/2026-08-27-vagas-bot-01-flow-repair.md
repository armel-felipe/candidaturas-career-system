# Vagas Bot 01 Flow Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent `analise a vaga N` from creating duplicate LinkedIn intakes or stopping on a non-authoritative JSON permission error in `vagas_bot_01`.

**Architecture:** Resolve an existing LinkedIn application by its canonical SQLite alias before calling the LinkedIn intake service, passing the explicit `application_id` when reusing the saved job. Treat the JSON alias index as a compatibility mirror: an `OSError` while updating it must not roll back or mask the canonical SQLite intake. Correct the bot01 state ownership and verify the behavior as UID 10000.

**Tech Stack:** Python, SQLite, pytest, Docker Compose, Node/npm harness.

**Spec:** `AGENTS.md` and `docs/roadmap.md` runtime/harness governance.

## Global Constraints

- Canonical execution identity is always an explicit `application_id` resolved from SQLite.
- `application_alias_index.json` is a compatibility mirror and never selects execution scope.
- Only `vagas_bot_01` may be restarted or have its mounted state permissions changed.
- Use the project intake/harness path; do not bypass it with ad hoc Notion, browser, or token commands.

---

### Task 1: Add regression tests

**Files:**
- Create: `tests/test_vagas_bot_01_flow_repair.py`

- [x] **Step 1: Write tests proving saved-job reuse and permission fail-open.**

  The first test creates a canonical SQLite application with the LinkedIn source alias, invokes the supervisor with the saved-job selection, and asserts that `from_linkedin_job` receives that application's ID. The second test makes the compatibility mirror writer raise `PermissionError` and asserts that `_update_alias_index` returns without raising.

- [x] **Step 2: Run the focused tests and confirm they fail against the current implementation.**

  Run: `./scripts/python.sh -m pytest -q tests/test_vagas_bot_01_flow_repair.py`

  Expected: at least the saved-job reuse test fails because the supervisor currently calls intake without `application_id`; the permission test fails because the mirror exception currently escapes.

### Task 2: Implement scoped reuse and permission isolation

**Files:**
- Modify: `src/career/services/persistence/application_repository.py`
- Modify: `src/career/services/harness_supervisor.py`
- Modify: `src/career/services/application_context.py`

- [x] **Step 1: Add `ApplicationRepository.resolve_by_alias(alias_type, alias_value)`.**

  Query `application_aliases` in the canonical database, raise `ApplicationNotFoundError` for no match and `AmbiguousApplicationError` for more than one application, then load the single record through the existing repository path.

- [x] **Step 2: Resolve LinkedIn aliases in the supervisor and pass `application_id`.**

  Try the exact selected URL and a normalized LinkedIn URL against SQLite. If an existing application is found, call `from_linkedin_job(..., application_id=existing_id, database=self.db)`; otherwise preserve the new-intake path.

- [x] **Step 3: Make `_update_alias_index` return a degraded result on `OSError`.**

  Keep SQLite persistence authoritative and catch only filesystem `OSError` around the compatibility mirror update, returning `False` for the degraded mirror and `True` on a successful write.

### Task 3: Verify runtime permissions and deployment

**Files:**
- Modify: `docs/roadmap.md`
- Runtime state: `workspaces/vagas_bot_01/state/application_alias_index.json` and the explicitly affected bot01 application state paths

- [x] **Step 1: Make the bot01 state writable by UID/GID 10000.**

  Inspect exact ownership first, then repair only the bot01 mounted state needed by this flow; keep the alias index private (`0600`) while owned by UID/GID 10000.

- [x] **Step 2: Run focused, harness, and structure/runtime verification.**

  Run the regression tests, the relevant existing harness tests, `npm run validate:structure`, and `npm run runtime:verify -- --strict` where available. Prove the mounted alias index is writable as UID 10000 without touching bot02.

- [x] **Step 3: Restart only `hermes-vagas-bot-01` and run a smoke test.**

  Confirm the container reloads the patched source, then exercise the saved-job route and verify no duplicate-alias or permission traceback is emitted.

- [x] **Step 4: Update `docs/roadmap.md` with evidence.**

  Mark `HARNESS-010` and `RUNTIME-011` complete only after the red/green tests, permission proof, and bot01 smoke command have fresh successful output.
