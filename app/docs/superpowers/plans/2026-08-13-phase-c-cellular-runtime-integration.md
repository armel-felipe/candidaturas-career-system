# Phase C Cellular Runtime Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the production cellular heartbeat with the Phase B SQLite request/control plane and prove one end-to-end run using a fresh-process controlled runner.

**Architecture:** `CellRequestBuilder` becomes the only source for the cellular request projection. `HarnessSupervisor` validates that projection against the authoritative SQLite row, records a bounded `runtime_run`, starts a fresh subprocess, and reports the result. The heartbeat keeps its existing queue and `CellExecutor` orchestration, but the pilot uses a deterministic runner because Hermes and opencode are unavailable in this environment.

**Tech Stack:** Python 3.12 standard library (`sqlite3`, `subprocess`, `sys`, `json`, `hashlib`), existing SQLite control plane, existing `HarnessSupervisor`, `CellExecutor`, pytest, temporary workspaces.

## Global Constraints

- Preserve the three pre-existing dirty files: `app/scripts/docx/generate_custom_cv.js`, `app/scripts/linkedin_extract_job.js`, and `app/src/career/services/cv_content.py`.
- Do not migrate, merge, delete, or write to Hermes profile databases.
- Do not connect or alter the Telegram gateway in this phase.
- Do not use `processe-a-vaga` as a fallback when a cellular runner is unavailable.
- Large candidate/job payloads remain filesystem artifacts referenced by hash; SQLite stores bounded metadata and pointers only.
- Runner commands must start a new process and must not contain `resume`.
- All authoritative production entrypoints continue to require the configured control database identity and workspace lease.
- Use `PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest` from `app/` for tests in this workspace.

---

### Task 1: Make the SQLite request the cellular request authority

**Files:**
- Modify: `app/src/career/services/agent_requests.py`
- Modify: `app/src/career/cells/executor.py`
- Modify: `app/src/career/services/applications_v2.py`
- Create: `app/tests/test_phase_c_request_bridge.py`

**Interfaces:**
- `CellRequestBuilder.build(..., cellular_context: Mapping[str, Any] | None = None) -> dict[str, Any]` adds the validated cellular envelope before persisting the payload hash.
- `CellRequestBuilder.load(run_id, node_id, attempt) -> dict[str, Any]` loads and hash-validates the persisted request.
- `CellRequestBuilder.materialize(payload, target_dir) -> tuple[Path, Path]` materializes the SQLite projection without adding unpersisted JSON fields.
- `_write_cellular_analyze_request(...)` returns files materialized from `cell_requests`, not a separately assembled payload.

- [ ] **Step 1: Write the failing request-bridge tests**

Add tests proving a cellular request contains `cellular`, `application_id`, `run_id`, `node_id`, `attempt`, `manifest_path`, `read_allowlist`, and `write_allowlist`; the database payload hash matches the materialized JSON; and changing the JSON causes `load`/validation to fail.

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

Run:

```bash
PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_c_request_bridge.py
```

Expected: FAIL because the builder has no cellular envelope/load contract and the heartbeat still assembles a parallel payload.

- [ ] **Step 3: Implement the minimal builder and executor bridge**

Extend the builder with a bounded cellular context, canonical JSON hashing, and `load`. During attempt materialization, pass the manifest-derived allowlists into the builder. Reject paths outside the workspace and reject cellular context that does not match the attempt identity.

Change `_write_cellular_analyze_request` to open the authoritative control database, call `CellRequestBuilder.load`, materialize that payload, and render only textual operational guidance in Markdown. Do not mutate the persisted JSON after hashing.

- [ ] **Step 4: Run the request-bridge tests and existing Phase B tests**

Run:

```bash
PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_c_request_bridge.py tests/test_cell_contract_persistence.py tests/test_cell_executor.py
```

Expected: all selected tests PASS.

- [ ] **Step 5: Commit the request authority task**

```bash
git add app/src/career/services/agent_requests.py app/src/career/cells/executor.py app/src/career/services/applications_v2.py app/tests/test_phase_c_request_bridge.py
git commit -m "feat: route cellular requests through sqlite projection"
```

---

### Task 2: Record and validate real Harness runtime sessions

**Files:**
- Create: `app/src/career/services/cellular_runtime.py`
- Modify: `app/src/career/services/harness_supervisor.py`
- Modify: `app/src/career/services/agent_runner.py`
- Create: `app/tests/test_cellular_runtime.py`

**Interfaces:**
- `CellularRuntime(database, root, worker_id, runtime="harness")` validates a persisted cellular request and owns one bounded `RuntimeControl` lifecycle.
- `CellularRuntime.begin(request_payload) -> dict[str, Any]` returns `runtime_run_id`, `request_hash`, and `request_tokens`.
- `CellularRuntime.observe(runtime_run_id, result, isolation) -> dict[str, Any]` records bounded metrics and no raw stdout.
- `CellularRuntime.finish(runtime_run_id, status, error=None, output_bytes=None) -> dict[str, Any]` closes the runtime row.

- [ ] **Step 1: Write failing runtime-session tests**

Test that a valid persisted request starts one `runtime_runs` row, a request hash mismatch is rejected before the runner, the result creates one bounded observation, and a nonzero runner result finishes as `failed` without changing the cellular node status.

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```bash
PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_cellular_runtime.py
```

Expected: FAIL because the runtime bridge and Harness integration do not exist.

- [ ] **Step 3: Implement the runtime bridge**

Use the existing `RuntimeControl` APIs. Derive request bytes from the persisted request file, estimate request tokens conservatively as `ceil(bytes / 4)`, register a worker with bounded metadata, record one pre-run observation and one post-run observation, and map statuses to `completed`, `failed`, or `blocked`. Never store stdout/stderr bodies in SQLite.

- [ ] **Step 4: Integrate validation into `HarnessSupervisor.run_application_stage`**

Before constructing or running the subprocess, open the authoritative `.career-state/career.db`, validate the request against `cell_requests`, validate the application/run/node/attempt identity and allowlists, and call `CellularRuntime.begin`. After `HarnessRun.inspect`, record isolation and finish the runtime row. If validation fails, do not invoke `runner.run`.

- [ ] **Step 5: Run runtime, Harness, and regression tests**

Run:

```bash
PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_cellular_runtime.py tests/test_cell_workspace_safety.py tests/test_runtime_control.py
```

Expected: all selected tests PASS; known environment-only failures must remain outside this focused command.

- [ ] **Step 6: Commit the runtime integration task**

```bash
git add app/src/career/services/cellular_runtime.py app/src/career/services/harness_supervisor.py app/src/career/services/agent_runner.py app/tests/test_cellular_runtime.py
git commit -m "feat: record cellular harness runtime sessions"
```

---

### Task 3: Add the controlled fresh-process runner

**Files:**
- Modify: `app/src/career/services/agent_runner.py`
- Create: `app/scripts/controlled_agent_worker.py`
- Create: `app/tests/test_controlled_agent_runner.py`

**Interfaces:**
- `SubprocessAgentRunner.build_command` accepts `kind=controlled` and returns `[sys.executable, <worker>, "--request", <request.md>, "--operation", "fit-map"]`.
- `ControlledAgentRunner` is the test configuration adapter used by `analysis_runner.kind=controlled`; it has no resume/session continuation option.
- `controlled_agent_worker.py` reads only the request JSON, writes the declared FIT_MAP draft path, and exits nonzero for a missing/invalid allowlist.

- [ ] **Step 1: Write failing runner tests**

Test the command has a new Python process and no `resume`; the worker writes a deterministic draft to the declared application-scoped path; and a request containing an unauthorized output is rejected without writing it.

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```bash
PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_controlled_agent_runner.py
```

Expected: FAIL because `kind=controlled` and the worker script do not exist.

- [ ] **Step 3: Implement the controlled worker and command adapter**

Use `sys.executable`, pass the request path only, and derive the output from the request's `write_allowlist`. The worker must reject paths outside the workspace and must not read or print the job description. The output draft must include only deterministic fixture data and the request identity.

- [ ] **Step 4: Run runner and Harness isolation tests**

Run:

```bash
PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_controlled_agent_runner.py tests/test_cellular_runtime.py tests/test_cell_workspace_safety.py -k 'controlled or cellular or harness'
```

Expected: all selected tests PASS.

- [ ] **Step 5: Commit the controlled runner task**

```bash
git add app/src/career/services/agent_runner.py app/scripts/controlled_agent_worker.py app/tests/test_controlled_agent_runner.py
git commit -m "feat: add controlled fresh-process cellular runner"
```

---

### Task 4: Execute the end-to-end cellular pilot

**Files:**
- Modify: `app/src/career/services/applications_v2.py`
- Create: `app/tests/test_phase_c_pilot.py`
- Create: `app/scripts/run_phase_c_pilot.py`

**Interfaces:**
- `run_phase_c_pilot.py --fixture-dir <path>` creates an isolated control DB and one application, runs the cellular analyze path with `analysis_runner.kind=controlled`, and emits a bounded JSON report.
- The pilot report includes `run_id`, `runtime_run_id`, request path/hash, subprocess command, isolation status, SQLite counts, handover status, and terminal node status.

- [ ] **Step 1: Write the failing pilot test**

Create a temporary fixture with one application and a valid authority identity. Assert that the pilot executes a fresh controlled subprocess, writes the draft, validates `analyze_fit`, records `cell_inputs`, `cell_requests`, `runtime_runs`, `runtime_observations`, `cell_handovers`, `validation_receipts`, and leaves no unauthorized workspace changes.

- [ ] **Step 2: Run the pilot test and verify the expected failure**

Run:

```bash
PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_c_pilot.py
```

Expected: FAIL until the request bridge, runtime bridge, and controlled runner are connected.

- [ ] **Step 3: Implement the isolated pilot command**

Use the existing `CellExecutor` and `HarnessSupervisor` path; do not call Telegram, Notion, OneDrive, Gmail, or `processe-a-vaga`. Provision the fixture authority ledger explicitly, run only the analyze cell, and serialize counts rather than payload bodies.

- [ ] **Step 4: Run the pilot and inspect its report**

Run:

```bash
tmp_phase_c=$(mktemp -d)
PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python scripts/run_phase_c_pilot.py --fixture-dir "$tmp_phase_c"
```

Expected: exit code 0, `status=completed`, one fresh controlled subprocess, `isolation.status=ok`, and SQLite rows for request/runtime/input/handover/receipt.

- [ ] **Step 5: Run concurrent pilot coverage**

Run:

```bash
PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_c_pilot.py tests/test_slice_a_core_integration.py
```

Expected: distinct applications share the control DB without cross-application artifact or request writes.

- [ ] **Step 6: Commit the pilot task**

```bash
git add app/src/career/services/applications_v2.py app/tests/test_phase_c_pilot.py app/scripts/run_phase_c_pilot.py
git commit -m "test: prove phase C cellular pilot end to end"
```

---

### Task 5: Close the Phase C gates and document evidence

**Files:**
- Modify: `app/docs/superpowers/status/architecture-implementation-control.md`
- Modify: `app/docs/superpowers/status/scope-change-log.md`
- Modify: `app/docs/superpowers/specs/2026-08-13-phase-c-cellular-runtime-integration-design.md` only if implementation clarifies a contract

- [ ] **Step 1: Run focused and full verification**

Run the Phase C focused suite, the relevant cellular regression suite, `git diff --check`, Python compilation, and the complete pytest suite with `--tb=no`. Record exact counts and known environmental failures separately.

- [ ] **Step 2: Inspect the pilot evidence**

Verify the report and SQLite queries contain no full job description, prompt, stdout, or conversation history. Confirm the request hash, runtime row, isolation result, handover, receipts, and terminal node are mutually consistent.

- [ ] **Step 3: Update governance**

Mark only the requirements proven by the pilot as `em validação` or `verificado`. Keep `ARCH-06` (Telegram dispatcher) outside verified status. Change `CHG-0005` to `concluído` only if the pilot and focused gates pass; otherwise record the exact blocker.

- [ ] **Step 4: Commit evidence and final status**

```bash
git add app/docs/superpowers/status/architecture-implementation-control.md app/docs/superpowers/status/scope-change-log.md
git commit -m "docs: record phase C pilot evidence"
```
