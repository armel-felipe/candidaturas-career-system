# Phase A Control Plane and Runtime Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one explicit SQLite control-plane path and produce runtime evidence about workers, runs, context pressure, and legacy Hermes routing without migrating application data or changing the production dispatcher yet.

**Architecture:** `Database` resolves `CAREER_CONTROL_DB_PATH` when configured and otherwise preserves the legacy app-scoped default. A small runtime-control service records workers, execution runs, and bounded context observations in the control database. `project.diagnose_runtime` reports the effective control database plus read-only snapshots of configured Hermes profiles. Compose points both bots at the same mounted control-plane directory, while their legacy per-profile state remains separate until Phase B.

**Tech Stack:** Python 3.11 standard library (`sqlite3`, `json`, `pathlib`, `platform`, `os`), existing career CLI and pytest, Docker Compose YAML, SQLite WAL.

## Global Constraints

- Do not alter or overwrite the user's existing dirty files: `app/scripts/docx/generate_custom_cv.js`, `app/scripts/linkedin_extract_job.js`, and `app/src/career/services/cv_content.py`.
- Do not migrate, merge, delete, or copy either existing profile database during Phase A.
- The control database path must be explicit in runtime configuration and remain backward-compatible when the environment variable is absent.
- Runtime diagnostics must use bounded metadata and read Hermes databases read-only; never load session message bodies into the report.
- A component is not marked `verificado` in the architecture matrix based on unit tests alone; runtime evidence must be recorded separately.
- Follow TDD: each production behavior starts with a failing focused test.

---

### Task 1: Make the control-plane database path explicit

**Files:**
- Modify: `app/src/career/services/database.py:__init__`
- Modify: `app/tests/test_database.py`
- Modify: `compose.yaml`
- Create: `control-plane/README.md`
- Modify: `.gitignore` only if needed for the control-plane marker

**Interfaces:**
- `Database(db_path=None)` uses `CAREER_CONTROL_DB_PATH` when set and non-empty; an explicit `db_path` argument remains highest priority.
- Compose exposes `CAREER_CONTROL_DB_PATH=/workspace/candidaturas/.career-control/career.db` to both bots and mounts the same host directory at `/workspace/candidaturas/.career-control`.

- [ ] **Step 1: Add the failing path-resolution tests**

Add tests proving explicit constructor paths win over the environment, the environment path is used when no constructor path is supplied, and the legacy `.career-state/career.db` fallback remains when the variable is absent.

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

Run: `cd app && pytest -q tests/test_database.py -k 'path or env'`

Expected: FAIL because `Database` currently ignores `CAREER_CONTROL_DB_PATH`.

- [ ] **Step 3: Implement the minimal path resolution**

Resolve the environment variable in `Database.__init__` before the existing `CAREER_STATE/career.db` fallback. Preserve `Path` normalization and existing `:memory:` test behavior.

- [ ] **Step 4: Run the focused tests**

Run: `cd app && pytest -q tests/test_database.py -k 'path or env'`

Expected: all selected tests PASS.

- [ ] **Step 5: Add the compose mount and local control-plane documentation**

Set the same environment variable and bind mount in both services. Document that the directory contains ignored runtime SQLite files, must be provisioned once, and must not receive profile session databases.

- [ ] **Step 6: Verify compose configuration without starting gateways**

Run: `docker compose config`

Expected: exit code 0; both services contain the same in-container control database path and the same host control-plane mount.

- [ ] **Step 7: Commit the isolated task**

Run: `git add app/src/career/services/database.py app/tests/test_database.py compose.yaml control-plane/README.md .gitignore && git commit -m "feat: make career control database path explicit"`

---

### Task 2: Add bounded worker, run, and context-observation records

**Files:**
- Modify: `app/src/career/services/database.py` schema initialization
- Create: `app/src/career/services/runtime_control.py`
- Create: `app/tests/test_runtime_control.py`
- Modify: `app/tests/test_database.py`

**Interfaces:**
- `RuntimeControl(database).register_worker(worker_id, runtime, profile_id=None, host=None, pid=None, metadata=None) -> dict`
- `RuntimeControl(database).start_run(worker_id, run_id=None, application_id=None, node_id=None, session_id=None, request_bytes=None, request_tokens=None, source="") -> dict`
- `RuntimeControl(database).record_context_observation(runtime_run_id, context_tokens=None, input_tokens=None, output_tokens=None, tool_calls=None, history_messages=None, request_bytes=None, source="", details=None) -> dict`
- `RuntimeControl(database).finish_run(runtime_run_id, status, error=None, output_bytes=None) -> dict`
- All JSON metadata is bounded to 4096 bytes; numeric metrics are non-negative integers or `None`.

- [ ] **Step 1: Write failing tests for worker registration**

Test first registration, idempotent re-registration updating `last_seen`, and bounded metadata rejection.

- [ ] **Step 2: Run worker tests and confirm failure**

Run: `cd app && pytest -q tests/test_runtime_control.py -k worker`

Expected: FAIL because the service and tables do not exist.

- [ ] **Step 3: Write failing tests for run lifecycle and observations**

Test that a run records its worker and identifiers, an observation is tied to that run, and finishing the run records terminal status and timestamp. Test rejection of an unknown run and negative metrics.

- [ ] **Step 4: Run lifecycle tests and confirm failure**

Run: `cd app && pytest -q tests/test_runtime_control.py`

Expected: FAIL because the lifecycle API does not exist.

- [ ] **Step 5: Add the minimal SQLite tables and service**

Add idempotent tables `runtime_workers`, `runtime_runs`, and `runtime_observations` with indexes on worker, run, and observation time. Use the existing `Database.transaction()` API and UTC timestamps. Do not store message content or prompts.

- [ ] **Step 6: Run the focused runtime-control tests**

Run: `cd app && pytest -q tests/test_runtime_control.py tests/test_database.py`

Expected: all focused tests PASS.

- [ ] **Step 7: Commit the task**

Run: `git add app/src/career/services/database.py app/src/career/services/runtime_control.py app/tests/test_runtime_control.py app/tests/test_database.py && git commit -m "feat: record runtime workers and context observations"`

---

### Task 3: Extend runtime diagnosis with control-plane and Hermes evidence

**Files:**
- Modify: `app/src/career/services/project.py`
- Modify: `app/tests/test_project_runtime.py`
- Modify: `app/tests/test_database.py` only if schema assertions require it

**Interfaces:**
- `diagnose_runtime()` adds `control_plane`, `runtime_observability`, and `hermes_profiles` fields without removing existing fields.
- `inspect_hermes_state_db(path: Path) -> dict` opens an existing Hermes database read-only and returns bounded counts and aggregate token/session metrics; inaccessible or incompatible files return a structured `status="unavailable"` result.

- [ ] **Step 1: Write failing diagnostic tests**

Create a temporary SQLite fixture with `sessions`, `messages`, and `session_model_usage`, call `inspect_hermes_state_db`, and assert it returns counts, maximum session message/tool counts, and aggregate token totals without returning message content. Add a test that `diagnose_runtime` reports the configured control database path and authority identity.

- [ ] **Step 2: Run diagnostic tests and confirm failure**

Run: `cd app && pytest -q tests/test_project_runtime.py`

Expected: FAIL because the new diagnostic fields and inspector do not exist.

- [ ] **Step 3: Implement read-only inspection and control-plane summary**

Use `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` with short bounded aggregate queries. Discover profile databases from `CAREER_HERMES_ROOT` when set, otherwise from `<project-parent>/hermes/vagas_bot_*`. Report configured path, resolved path, existence, schema status, database identity when initialized, worker/run counts, and whether the legacy per-profile databases differ.

- [ ] **Step 4: Run diagnostic tests**

Run: `cd app && pytest -q tests/test_project_runtime.py tests/test_database.py`

Expected: all selected tests PASS.

- [ ] **Step 5: Run the real diagnostic in the current workspace**

Run: `cd app && CAREER_HERMES_ROOT=/opt/agent-projects/candidaturas/hermes npm run runtime:diagnose`

Expected: exit code 0 and JSON output containing both `vagas_bot_01` and `vagas_bot_02` profile summaries, the effective legacy database path, and the control-plane status.

- [ ] **Step 6: Commit the task**

Run: `git add app/src/career/services/project.py app/tests/test_project_runtime.py && git commit -m "feat: diagnose control plane and Hermes context pressure"`

---

### Task 4: Provision the empty Phase A control plane and update governance evidence

**Files:**
- Modify: `app/docs/superpowers/status/architecture-implementation-control.md`
- Modify: `app/docs/superpowers/status/scope-change-log.md`
- Modify: `app/docs/superpowers/specs/2026-08-13-data-anchored-cellular-orchestration.md` only if implementation details require clarification
- Runtime only: `control-plane/career.db` (ignored, never committed)

**Interfaces:**
- The repository documents the exact one-time provisioning command and the fact that existing profile databases remain legacy during Phase A.
- The architecture matrix updates only `ARCH-02` and the observability portions of `ARCH-10`/`ARCH-12` when evidence supports the narrower claim; Telegram integration, input contracts, and cellular production routing remain unverified.

- [ ] **Step 1: Add a Phase A change-log entry**

Record `CHG-0003` as an implementation change under the approved baseline, with affected requirements `ARCH-02`, `ARCH-09`, `ARCH-10`, and `ARCH-12`, and status `em implementação`.

- [ ] **Step 2: Provision the empty control database explicitly**

Run: `mkdir -p control-plane && cd app && CAREER_CONTROL_DB_PATH=/opt/agent-projects/candidaturas/control-plane/career.db ./scripts/python.sh scripts/career_cli.py applications parallel-status`

If the command fails because the authority ledger is not provisioned, run only the existing explicit provisioning flow after inspecting its dry-run/status output; never copy either profile database automatically.

- [ ] **Step 3: Verify both configured profiles resolve the same control path**

Run a read-only Python/CLI check with `CAREER_CONTROL_DB_PATH` set and inspect `docker compose config`; assert identical path values and one control database identity.

- [ ] **Step 4: Run focused and full tests**

Run: `cd app && pytest -q tests/test_database.py tests/test_runtime_control.py tests/test_project_runtime.py tests/test_applications_v2.py`

Then run: `cd app && pytest -q`

Expected: exit code 0 with zero failures. Existing unrelated dirty files must remain unchanged.

- [ ] **Step 5: Update the architecture matrix with evidence**

Mark only the narrowly proven control-plane path and runtime-observability items as `em validação` or `verificado`; keep Telegram dispatcher integration and real cellular execution explicitly `divergente`/`implementado não integrado` as evidence dictates.

- [ ] **Step 6: Run final structural checks**

Run: `git diff --check`, `git status --short`, and `cd app && npm run validate:structure`.

Expected: no whitespace errors, the three pre-existing dirty files are preserved, new files are limited to Phase A scope, and structure validation passes.

---

## Plan self-review

- The plan does not copy or merge existing profile databases.
- The plan covers authority path, worker/run registration, context diagnosis, compose configuration, and governance evidence.
- No task claims that the Telegram gateway is cellular; that remains a later phase.
- The only production behavior added in Phase A is explicit database selection and observability; the executor path remains unchanged.

## Execution handoff

Phase A implementation is complete within this plan's scope. The current runtime
still has known blockers outside the Phase A files: Node.js is unavailable in this
shell, the structural validator rejects the existing `.venv-test` Windows helper
files, and some legacy CV/cellular tests require `enquadramento.json`. The next
phase must not mark Telegram cellular routing as verified until those baseline
issues and the runtime integration are separately addressed.
