# CV Generation Contract Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` when delegating implementation. This repair is being executed inline in the current workspace with the same checkpoints.

**Goal:** Make the “criar CV” request complete through the canonical CV artifact contract for both vagas bots, with truthful blocker propagation and no latent `KeyError` from canonical candidate facts.

**Architecture:** Keep the SQLite-backed supervisor contract authoritative. Repair the legacy/manual CV path so an approved DOCX is registered with immutable provenance before the contract is evaluated; add an idempotent reconciliation path for already-approved local reports created before registration existed. Keep cellular runs unchanged except for shared helper behavior. Treat an agent-declared blocked result as a real blocker before the no-output fallback.

**Tech Stack:** Python 3, SQLite repositories, pytest, existing HarnessSupervisor/WorkflowStateStore, canonical `candidate_cv_facts.json`, Docker Compose runtime.

## Global Constraints

- Do not weaken application scope, artifact hashes, review gates, or output allowlists.
- Do not accept a stale or foreign CV merely because a file exists in `outputs/`.
- Do not alter Notion, LinkedIn, OneDrive, or user candidature data during tests.
- Update `docs/roadmap.md` with evidence before closing the work.

## Task 1: Reproduce the three defects with focused tests

**Files:** `tests/test_cv_experience_selection.py`, `tests/test_supervisor_contracts.py`, `tests/test_harness_live_regressions.py`.

- Add a regression proving every canonical experience selectable by gap filling has a source locator and that the two historical experiences selected by the Rappy run do not raise `KeyError`.
- Add a regression proving the manual `cv.approve` task publishes an approved DOCX provenance record and `cv_review_passed` receipt in the canonical database.
- Add a regression proving a specialist stdout that explicitly reports a blocked execution is classified with that blocker, not `specialist_produced_no_allowed_output`.
- Run only these tests and confirm the new tests fail for the current implementation.

## Task 2: Preserve canonical candidate-facts locator compatibility

**Files:** `.agents/skills/career-system/references/candidate_cv_facts.json`, `tests/test_cv_experience_selection.py`.

- Resolve missing locators deterministically from the immutable experience record, using the company token already present in `candidate_cv_facts.json`; do not mutate the catalog and invalidate every existing FIT_MAP revision merely to add compatibility metadata.
- Add an invariant test that every selectable experience resolves to a locator and that the fallback remains bounded to the canonical record.
- Validate JSON and run the focused CV selection/build-content tests.

## Task 3: Register and reconcile manual CV provenance

**Files:** `src/career/tasks/registry.py`, `src/career/services/harness_supervisor.py`, tests for task/supervisor contracts.

- After `cv.approve` passes, register the exact reviewed DOCX through `record_approved_cv_provenance` using the current application FIT_MAP revision and scoped task run ID.
- Make the registration idempotent and preserve the existing review gate semantics.
- Before evaluating the post-run manual CV contract, reconcile a valid approved report/artifact pair left by a legacy manual run, only when application, current FIT_MAP revision, artifact path/hash, and report metadata all match.
- Keep the contract fail-closed when any provenance/hash/review condition is absent.

## Task 4: Preserve truthful specialist failure reasons

**Files:** `src/career/services/harness_supervisor.py`, `tests/test_harness_live_regressions.py`.

- Detect the structured/semantic blocked envelope emitted by the specialist runner when the process returns code 0.
- Preserve the specialist blocker and stdout/stderr in the execution envelope.
- Use `specialist_produced_no_allowed_output` only when there is no declared blocker and no allowed output.

## Task 5: Verify, deploy, and synchronize

**Commands:** focused pytest, full pytest, `npm run validate:structure`, `npm run runtime:verify -- --strict`, `git diff --check`, Docker Compose recreation and runtime probes.

- Re-run the bot01 CV-content path and verify the locator failure is gone without external delivery.
- Verify bot02’s manual CV contract sees a registered artifact or a safely reconciled approved artifact.
- Commit only the canonical code/tests/plan/roadmap files, recreate both bot services, and record the final evidence in the roadmap.
