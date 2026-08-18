# Task 2.1 Report — Transactional Gate Receipts

Date: 2026-08-18
Status: implemented and locally verified
Workspace: `/opt/agent-projects/candidaturas/.worktrees/task-2.1-runtime-unification`

## Scope executed

Implemented the bounded Task 2.1 scope only:

- `src/career/services/persistence/gate_repository.py`
- `src/career/services/persistence/migrations/006_gate_receipt_scope_and_idempotency.py`
- `src/career/tasks/registry.py`
- `src/career/workflow/state_store.py`
- `tests/test_workflow_gates.py`
- `tests/test_sqlite_persistence.py`

No broad runtime refactors were attempted beyond the task contract. No global or app-scoped
`workflow_state.json` files were written during verification.

## TDD record

### RED

Created `tests/test_workflow_gates.py` first, covering:

1. missing `application_id`
2. missing required hashes / validator
3. unknown application and wrong fingerprint
4. revision mismatch and invalid transitions
5. idempotent duplicate receipts
6. application-scoped satisfaction checks
7. next-step derivation from receipts only, ignoring stale compatibility JSON / file presence
8. `run_task` rejecting unscoped execution
9. `run_task` recording receipts without writing workflow JSON

Initial failing command:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_workflow_gates.py
```

Observed failure:

```text
ModuleNotFoundError: No module named 'career.services.persistence.gate_repository'
```

### GREEN

Implemented:

- `GateRepository.record(receipt)` with:
  - required `application_id`, fingerprint, `run_id`, gate, validator, input hash, output hash
  - validator-to-gate enforcement
  - application existence and fingerprint validation
  - fit-map revision binding validation where required
  - transition/prerequisite enforcement
  - idempotency on `(application_id, gate, input_hash, output_hash)`
  - atomic persistence through SQLite transactions
- migration `006_gate_receipt_scope_and_idempotency.py` to extend `validation_receipts`
  with application scope, gate metadata, idempotency index, and legacy backfill
- `WorkflowStateStore` as a read-only compatibility projection sourced from SQLite
- `tasks.registry.run_task/run_pipeline` refusal without explicit application-scoped store
- receipt persistence from `tasks.registry` through `GateRepository`

### Fix round 1

Resolved the independent review findings without widening Task 2.1:

1. Restored `WorkflowStateStore.for_application(application_id)` compatibility by making
   `database` optional again and resolving the canonical SQLite database by default.
2. Reworked `WorkflowStateStore.load/save` so application-scoped callers read SQLite
   projections plus lightweight intake metadata from companion application state, while
   global compatibility now uses an active-application pointer instead of writing
   `.career-state/workflow_state.json`.
3. Updated intake/runtime call paths to stop mutating the global workflow JSON and to
   re-scope unbound stores once the target application is known.
4. Changed implicit task `run_id` generation to produce a unique per-execution identifier,
   preserving explicit `run_id` values.

### Fix round 2

Resolved the second independent review round within the same bounded Task 2.1 scope:

1. Narrowed `WorkflowStateStore._resolved_application_id()` so only canonical
   `applications_v2/<id>/workflow_state.json` or `state.json` paths infer application scope.
   Arbitrary legacy/temp paths now remain file-backed compatibility stores.
2. Split `WorkflowStateStore` behavior into three explicit modes:
   - application-scoped SQLite projection
   - global compatibility projection via active pointer
   - explicit file-backed compatibility mirror for caller-supplied paths
3. Updated intake pointer sync to honor `global_state_store.path` when callers provide an
   explicit compatibility mirror path, while keeping gate authority out of JSON.
4. Routed CLI `workflow run-task`, `run-pipeline`, and `reset-state` through explicit
   application scope resolved from `--application-id` or the active pointer, with a clear
   validation error when neither is available.
5. Replaced runtime diagnosis reliance on global `workflow_state.json` history with active
   pointer + SQLite projection reporting, and marked the legacy global JSON as
   non-authoritative in diagnostics.
6. Added focused regressions for:
   - file-backed arbitrary-path compatibility stores
   - explicit global mirror path handling
   - CLI scope validation and active-pointer resolution
   - non-authoritative global workflow-state diagnostics

### Fix round 3

Resolved the final blocker in the same bounded Task 2.1 scope:

1. Updated CLI `workflow reset-state` so that when the reset application matches the
   current active pointer, the pointer is cleared before returning.
2. Added a focused CLI regression proving that after
   `workflow reset-state --application-id <id>`, subsequent unscoped `run-task` and
   `run-pipeline` calls do not reuse the reset application and instead require
   explicit scope / no active application resolution.

### Refactor / integration notes

- Reused the existing `validation_receipts`, `gate_dependencies`, `application_runs`, and
  `cell_nodes` tables instead of inventing a second receipt path.
- Revision binding is represented through `gate_dependencies(dependency_type='fit_map_revision')`.
- Compatibility reads now come from SQLite projection; `save()` and `reset()` are fail-closed.
- Explicit caller-supplied compatibility paths remain writable file-backed mirrors; only the
  default global workflow-state path stays read-only/non-authoritative.
- The bounded neighboring migration test required one fixture adjustment after adding migration 006:
  the legacy pre-005 seed now correctly leaves both 005 and 006 pending.
- Application-scoped metadata writes now target companion `state.json` files rather than
  `workflow_state.json`, keeping gate authority in SQLite while preserving intake/resume UX.
- The global compatibility pointer is now a dedicated lightweight JSON (`active_application.json`)
  instead of the old global workflow-state document.

## Verification evidence

Focused Task 2.1 suite after fix round 2:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_workflow_gates.py tests/test_linkedin_intake_metadata.py
```

Result:

```text
Ran 20 tests in 1.321s
OK
```

Focused Task 2.1 suite after fix round 3:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_workflow_gates.WorkflowGateTests.test_cli_workflow_reset_state_clears_active_pointer_before_unscoped_commands
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_workflow_gates.py tests/test_linkedin_intake_metadata.py
```

Result:

```text
Ran 1 test in 0.225s
OK

Ran 21 tests in 1.351s
OK
```

Bounded neighboring persistence/application verification:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_sqlite_persistence.py tests/test_database.py tests/test_application_repository.py
```

Result:

```text
Ran 25 tests in 1.263s
OK
```

## Files changed

- `src/career/services/persistence/gate_repository.py`
- `src/career/services/persistence/migrations/006_gate_receipt_scope_and_idempotency.py`
- `src/career/cli.py`
- `src/career/services/intake.py`
- `src/career/services/project.py`
- `src/career/tasks/registry.py`
- `src/career/workflow/state_store.py`
- `src/career/services/workflow_reset.py`
- `tests/test_linkedin_intake_metadata.py`
- `tests/test_workflow_gates.py`
- `tests/test_sqlite_persistence.py`

## Behavioral outcome

- Gate completion is now derived from valid SQLite receipts, not file existence.
- Duplicate equivalent receipts are reused instead of duplicated.
- Wrong application fingerprint, missing identity/hash fields, unknown application, unknown
  validator, revision mismatch, and invalid transitions now fail closed.
- `next_required_step` is application-scoped and ignores stale compatibility JSON.
- `run_task` no longer accepts implicit global workflow state for application processing.
- Existing application-scoped callers can construct `WorkflowStateStore.for_application(...)`
  without a `database=` keyword and no longer raise `TypeError`.
- Runtime compatibility no longer depends on writing the global `.career-state/workflow_state.json`.
- Arbitrary temp/legacy workflow-state paths no longer masquerade as application IDs.
- Intake/global pointer sync now writes to the caller-requested compatibility mirror path when
  one is provided, instead of always targeting `.career-state/active_application.json`.
- CLI workflow commands either resolve a concrete application scope or fail with a clear
  validation error before invoking task execution.
- `workflow reset-state` no longer leaves the reset application implicitly selected through
  the active pointer; the next unscoped workflow command must resolve a different active app
  or receive explicit `--application-id`.
- Runtime diagnosis reports the legacy global workflow-state JSON as non-authoritative and
  surfaces active-pointer/SQLite-derived status instead of stale `completed_states` history.
