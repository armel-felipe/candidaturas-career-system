# Harness Continuity and Approval Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Keep scoped application intent across messages, centralize authority approvals, and close the related roadmap evidence without weakening fail-closed storage controls.

**Architecture:** Add a small session-scoped pipeline-intent record at the harness boundary. Normalize authority-handoff failures into a structured approval/resume path owned by `HarnessSupervisor`; keep `Database.authorize_storage_handoff` as the only writer of authority state. Complete the pre-ledger migration fixture and document the observation decision without deleting compatibility artifacts.

**Tech Stack:** Python 3, SQLite, pytest, JSON state files, existing `ApprovalStore`, `HarnessSupervisor`, and database authority ledger.

**Spec:** `docs/superpowers/specs/2026-08-24-harness-continuity-approvals-design.md`

## Global Constraints

- Execution selection must use explicit or session-resolved `application_id`; global JSON pointers are discovery metadata only.
- Authority changes must use the official `Database.authorize_storage_handoff` path under the existing ledger lock.
- No pending approval or historical output may be deleted.
- Tests must exercise observable behavior and must be watched failing before production changes.
- `TEST-004` is an existing unrelated documentation failure and is not part of this implementation.

### Task 1: Roadmap and state contract

**Files:**
- Modify: `docs/roadmap.md`
- Test: `tests/test_operational_documentation.py` or a focused new roadmap test if the existing documentation suite has no suitable boundary.

**Interfaces:**
- Produces roadmap IDs `HARNESS-001` and `HARNESS-002`.
- Updates related evidence for `RUNTIME-006`, `TEST-003`, and `RUNTIME-OBS-001` without rewriting historical completion facts.

- [ ] **Step 1: Write the failing roadmap contract test** asserting the two new IDs, P1 priority, and criteria mentioning session continuity and structured authority approval.
- [ ] **Step 2: Run the focused test and verify it fails because the IDs are absent.**
- [ ] **Step 3: Add the two roadmap rows and update the related-item notes with the current scope and evidence policy.**
- [ ] **Step 4: Run the focused documentation test and verify it passes.**

### Task 2: Session-scoped compound intent

**Files:**
- Create: `src/career/services/pipeline_intent.py`
- Modify: `src/career/services/harness_supervisor.py:1188-1252, 993-1179`
- Modify: `scripts/telegram_harness_adapter.py:19-55` only if the regression proves direct adapter calls lose the runtime context.
- Test: `tests/test_harness_continuity.py`

**Interfaces:**
- `PipelineIntentStore(root).bind(application_id, session_key, requested_steps) -> dict`
- `PipelineIntentStore(root).resolve(session_key) -> dict | None`
- `HarnessSupervisor._session_application_id(...) -> str | None` remains the execution selector and may use only the registered session or the persisted session intent.

- [ ] **Step 1: Write a failing test for a bound intake followed by “sim, gere o CV e envie ao OneDrive” preserving the same `application_id`.**
- [ ] **Step 2: Run that test and confirm it fails with `explicit_application_scope_required` or no persisted intent.**
- [ ] **Step 3: Write a failing test proving a duplicate continuation does not create a second intent record.**
- [ ] **Step 4: Run the duplicate test and confirm it fails before the store exists.**
- [ ] **Step 5: Implement the minimal JSON-backed `PipelineIntentStore` with atomic writes and a session-key hash-safe filename.**
- [ ] **Step 6: Bind the intent whenever intake successfully registers a session and resolve it before routing ordinary CV/Notion/delivery continuations.**
- [ ] **Step 7: Run the two focused tests and verify they pass.**

### Task 3: Structured authority approval and resume

**Files:**
- Modify: `src/career/services/approvals.py`
- Modify: `src/career/services/harness_supervisor.py:461-501, 993-1179, 1324-1361`
- Modify: `src/career/services/applications_v2.py:2926-3050` only where the current cellular result loses the authority blocker code.
- Test: `tests/test_harness_authority_approval.py`

**Interfaces:**
- `ApprovalStore.create_idempotent(action, idempotency_key, payload) -> dict`
- `HarnessSupervisor.prepare_authority_handoff(...) -> dict`
- Structured result shape: `status="awaiting_approval"`, `approval.action="storage-handoff"`, `approval.approval_id`, `blocker_reason="storage_handoff_required"`, and resumable application metadata.

- [ ] **Step 1: Write a failing test for repeated storage-handoff detection returning one approval ID.**
- [ ] **Step 2: Run it and verify two pending approval files are currently produced.**
- [ ] **Step 3: Write a failing test for an approved handoff result being resumable without a second approval.**
- [ ] **Step 4: Run it and verify the current supervisor has no structured storage-handoff path.**
- [ ] **Step 5: Implement idempotent approval creation using a stable hash key and preserve existing `approve`/`consume` behavior.**
- [ ] **Step 6: Normalize the cellular authority exception into the structured pending approval result without changing the database safety guard.**
- [ ] **Step 7: Add the official handoff execution/resume callback and verify repeated execution is idempotent.**
- [ ] **Step 8: Run the focused authority tests and verify they pass.**

### Task 4: Close the pre-ledger fixture gap

**Files:**
- Modify: `tests/test_cell_workspace_safety.py:383-416`
- Modify: `src/career/services/database.py` only if the failing fixture reveals a production migration ordering defect.
- Test: `tests/test_cell_workspace_safety.py::test_provision_authority_ledger_cli_upgrades_a_pre_ledger_database`

**Interfaces:**
- The CLI provisioning path must call schema migration before selecting `authority_ledger_id`.

- [ ] **Step 1: Isolate the failing pre-ledger test and capture the `no such column: authority_ledger_id` failure.**
- [ ] **Step 2: Add the smallest fixture/setup migration needed to represent a legacy database while allowing the production migration path to run.**
- [ ] **Step 3: Run the isolated test and verify it passes with the ledger column present and one provisioned ledger.**
- [ ] **Step 4: Run the authority recovery and workspace-safety subsets and verify no fail-closed safety test regresses.**

### Task 5: Close the observation window with evidence

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `docs/superpowers/status/runtime-unification-progress.md` if the evidence belongs in the existing status record.
- Test/command: `npm run runtime:verify -- --strict --report outputs/_tmp/runtime_verification.json` and the focused supervisor/authority suites.

**Interfaces:**
- `RUNTIME-OBS-001` may move to `DONE` only if the report explicitly records compatibility JSON preservation and current authority/session findings.

- [ ] **Step 1: Run the strict runtime verifier and record its actual status, blockers, and report path.**
- [ ] **Step 2: Update the observation item with the verified preservation decision and command evidence; do not delete JSON artifacts.**
- [ ] **Step 3: Run the final focused suite and verify the roadmap criteria match the produced evidence.**

## Final verification

- [ ] Run `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_continuity.py tests/test_harness_authority_approval.py tests/test_cell_authority_recovery.py tests/test_cell_workspace_safety.py tests/test_supervisor_contracts.py`.
- [ ] Run `npm run validate:structure`.
- [ ] Run `git diff --check`.
- [ ] Inspect `git diff -- docs/roadmap.md src/career/services/harness_supervisor.py src/career/services/approvals.py src/career/services/pipeline_intent.py tests/` and report any unrelated changes without modifying them.
