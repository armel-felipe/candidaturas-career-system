# Task 3.1 — final identity-firewall hardening

Base commit: `4945ad5`.

This remains Task 3.1. Do **not** implement Task 3.2's SQLite context materializer. The objective is to eliminate every remaining operational fallback that can select one application's execution context from global JSON, a global FIT_MAP path, or the deprecated local database.

## Contract

1. `control-plane/career.db` is the operational default database for the repository root. Explicitly injected `Database(temp_path)` remains valid for tests, migrations, backup, and controlled tools.
2. A runtime action that reads, writes, validates, scores, derives, or requests a job-specific artifact must require `application_id` (or an already-resolved `ApplicationPaths` that was derived from it). It must fail closed when missing; it must never use `workflow_state.json`, `active_intake`, `.career-state/fit_map*.json`, or a global derived directory to choose an application.
3. JSON files remain one-way compatibility mirrors/materialized artifacts. They may be written/read only after the SQLite/application scope is already fixed. They cannot authorize or choose scope.
4. Preserve user-owned unrelated changes, including untracked `tests/test_intake_persistence.py`; do not stage or modify it.

## Required changes

### A. Supervisor finalizer

- Change `HarnessSupervisor._finalize_fit_map_pipeline` to require explicit `application_id` and use `application_context.paths_for(application_id)`, a scoped `WorkflowStateStore`, and the canonical database.
- Its task calls must pass the scoped store; draft/FIT_MAP/registry inputs must come from that application's paths only.
- Pass the scoped application ID from the real specialist execution route. Missing scope must return a clear blocked result; no global fallback.

### B. Derived producers and downstream generators

- Remove unscoped global-state fallback from `derived_context.resolve_active_job_context` and `build_all_for_fit_map` for runtime/producer use. Require explicit `ApplicationPaths` or `application_id`; use application-local paths only.
- Update direct production callers in `feras.py`, `cover_letter.py`, `cv_content.py`, `intake.py`, `multiagent.py`, and CLI commands as necessary. Explicit existing application flows must continue working.
- Compatibility helpers may exist only if they reject operational unscoped use. Do not silently select the last active job.

### C. Database and operational CLI routes

- Make `Database()` resolve `ROOT/control-plane/career.db` by default (without changing explicit injected database paths).
- Ensure operational CLI applications/session/query and supervisor construction use canonical resolution; prove no `.career-state/career.db` is created or selected by those routes.
- FIT_MAP commands that execute or report application-specific data (`template`, validation, status/summary/draft-summary/quality/build/score/validate/finalize/registry and comparable request paths) must require `--application-id`, or fail closed before selecting any global path. Preserve explicit `--application-id` behavior.
- Multiagent request APIs and CLI must require scope for runtime request construction.

### D. Docs

- Correct remaining instructions in `AGENTS.md` and relevant career skills that tell agents to use global `workflow_state.json`, global `.career-state/fit_map*.json`, unscoped `multiagent:request`, or unscoped FIT_MAP/intake execution.
- Do not undertake a wholesale documentation rewrite; make the operational instructions accurate for this contract.

## Tests (TDD)

Write/extend tracked tests first and run them red before production implementation. Use real services/paths, not mocks that bypass the target code.

At a minimum cover:

1. supervisor auto-finalizer requires scope and does not use global FIT_MAP paths; explicit application scope reaches only that application's files/tasks;
2. `resolve_active_job_context` / `build_all_for_fit_map` rejects unscoped producer calls and explicit paths preserve isolation;
3. FERAS, cover letter, and CV context calls no longer select a global active job;
4. `Database()` defaults to `control-plane/career.db`, and operational CLI/session/query/application construction do not create/select the legacy default;
5. CLI FIT_MAP and request paths reject missing `--application-id`, and explicit scope routes to the application-local FIT_MAP;
6. public and current intake regressions remain green without using the untracked legacy test as evidence.

Run focused tests plus relevant neighboring Task 1–3 suites. Record exact commands and output counts in the report. Do not claim a clean full suite unless actually run.

## Deliverables

- Commit only task-owned tracked source/tests/docs and this task's report.
- Write `.superpowers/sdd/2026-08-18-runtime-unification/task-3.1-identity-firewall-report.md`, with root cause, TDD RED evidence, implemented boundaries, commands/counts, known limitations, and precise changed paths.
