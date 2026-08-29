# Cellular Heartbeat Canonical Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the cellular heartbeat open the authoritative control-plane database configured by the runtime instead of the legacy database adjacent to `.career-state`.

**Architecture:** Keep database path resolution centralized in the existing `canonical_database()`/`Database` resolver. `_run_cellular_heartbeat` will obtain its path from that resolver, then retain the existing identity and authority checks before maintenance or queue processing. Tests that isolate `V2_DIR` will explicitly isolate `CAREER_CONTROL_DB_PATH` as well, so test paths mirror production configuration rather than relying on the deprecated layout.

**Tech Stack:** Python 3, SQLite, pytest, project CLI, Dockerized Hermes bot profiles.

**Spec:** `docs/roadmap.md`, item `RUNTIME-012`.

## Global Constraints

- SQLite `control-plane/career.db` or the explicit `CAREER_CONTROL_DB_PATH` remains the runtime authority.
- `.career-state/career.db` is legacy compatibility state and must not select execution.
- The heartbeat must validate `CAREER_CONTROL_DB_ID` against the selected database before maintenance or queue reads.
- No database copy, deletion, manual SQLite edit, or authority-ledger bypass is allowed.
- The fix must preserve `--run-agent`, cellular-only behavior, lease acquisition, and lease release.
- Production code must be preceded by a failing regression test.

### Task 1: Add the regression and isolate test database configuration

**Files:**
- Modify: `tests/test_cell_workspace_safety.py` near the cellular heartbeat tests.

**Interfaces:**
- Consumes: `applications_v2.run_heartbeat`, `CAREER_CONTROL_DB_PATH`, `HeartbeatV2Options`.
- Produces: A failing test proving a configured canonical database is selected even when a distinct legacy database exists beside `V2_DIR`.

- [x] **Step 1: Write the failing test**

  Create `test_cellular_heartbeat_uses_configured_control_database_path` with a temporary `V2_DIR`, a legacy database at `v2_dir.parent / "career.db"`, and a different configured database at `tmp_path / "control-plane" / "career.db"`. Initialize both, set `CAREER_CONTROL_DB_PATH` to the configured path, patch maintenance/Notion/queue to no-op, and call the cellular heartbeat using the configured database identity. Assert `result["mode"] == "cellular"`; the current hardcoded path must instead raise the identity mismatch.

- [x] **Step 2: Run the test and verify the failure is causal**

  Run:

  ```bash
  PYTHONPATH=src .venv/bin/pytest -q tests/test_cell_workspace_safety.py -k configured_control_database_path
  ```

  Expected: `FAIL` with the current legacy database identity mismatch, before maintenance and queue processing.

- [x] **Step 3: Update existing isolated heartbeat tests to set their configured path**

  In each test that replaces `applications_v2.V2_DIR` and invokes `run_heartbeat`, set:

  ```python
  monkeypatch.setenv("CAREER_CONTROL_DB_PATH", str(v2_dir.parent / "career.db"))
  ```

  This keeps those tests isolated while exercising the same resolver contract as production.

- [x] **Step 4: Align the pre-existing analyze-fit safety assertion**

  The current executor contract intentionally does not reserve `analyze_fit` when its external draft and binding are absent. Update the stale test `test_executor_requires_analyze_fit_draft_binding_even_when_both_are_missing` to assert `run_ready(...) == ()`, no handler invocation, and `cell_nodes.status == "planned"` with `latest_attempt == 0`. This is a test-only alignment with `CELLULAR-003`, not a new production behavior.

### Task 2: Use the canonical database resolver in the heartbeat

**Files:**
- Modify: `src/career/services/applications_v2.py` import block and `_run_cellular_heartbeat`.

**Interfaces:**
- Consumes: `canonical_database()` from `career.services.application_context`.
- Produces: `database_path` resolved from `CAREER_CONTROL_DB_PATH` when present, or the canonical `control-plane/career.db` default otherwise.

- [x] **Step 1: Import the canonical resolver**

  Add `canonical_database` to the existing `career.services.application_context` imports.

- [x] **Step 2: Replace the legacy path expression**

  Replace:

  ```python
  database_path = V2_DIR.parent / "career.db"
  ```

  with:

  ```python
  database_path = canonical_database().db_path
  ```

  Keep the following file existence, identity, authority lease, authorized heartbeat, and release logic unchanged.

- [x] **Step 3: Run the regression and focused heartbeat tests**

  Run:

  ```bash
  PYTHONPATH=src .venv/bin/pytest -q tests/test_cell_workspace_safety.py -k 'configured_control_database_path or heartbeat'
  ```

  Expected: all selected tests pass, including the new test and the existing authority/lease/queue behavior.

### Task 3: Validate the repository and both runtime profiles

**Files:**
- Modify: `docs/roadmap.md` to mark `RUNTIME-012` and its plan `DONE` only after evidence is collected.

**Interfaces:**
- Consumes: the corrected heartbeat and the bot profiles’ configured database paths.
- Produces: test, structure, strict-runtime, and bot01/bot02 smoke evidence.

- [x] **Step 1: Run the focused cellular safety suite**

  ```bash
  PYTHONPATH=src .venv/bin/pytest -q tests/test_cell_workspace_safety.py
  ```

- [x] **Step 2: Run project structural and strict runtime validation**

  ```bash
  npm run validate:structure
  npm run runtime:verify -- --strict
  ```

- [x] **Step 3: Confirm both containers expose the canonical configuration**

  ```bash
  docker exec hermes-vagas-bot-01 sh -lc 'set -a; . /opt/data/profiles/vagas_bot_01/.env; set +a; printf "%s\n" "$CAREER_CONTROL_DB_PATH"; cd /workspace/candidaturas; ./scripts/python.sh scripts/career_cli.py applications doctor-concurrency'
  docker exec hermes-vagas-bot-02 sh -lc 'set -a; . /opt/data/profiles/vagas_bot_02/.env; set +a; printf "%s\n" "$CAREER_CONTROL_DB_PATH"; cd /workspace/candidaturas; ./scripts/python.sh scripts/career_cli.py applications doctor-concurrency'
  ```

  Expected: both profiles report `.career-control/career.db` and the same authoritative `control_db_id`.

- [x] **Step 4: Re-run the bot01 heartbeat only after the regression is green**

  Use the official cellular command with `--run-agent` and `--max-per-run 1`; verify it no longer fails with a legacy database identity mismatch. Do not perform a new intake or alter the application’s FIT_MAP.

- [x] **Step 5: Update roadmap evidence**

  Change `RUNTIME-012` and the plan row to `DONE`, recording the exact focused test count, validation commands, and bot heartbeat result. Leave unrelated dirty-worktree changes untouched.

## Self-review checklist

- The test fails before the production edit for the exact identity mismatch.
- The production change has one responsibility: database path selection.
- Existing lease, authority, maintenance, and queue behavior remains covered.
- The default path no longer points to `.career-state/career.db`.
- The roadmap records both the bug and the verified resolution.
