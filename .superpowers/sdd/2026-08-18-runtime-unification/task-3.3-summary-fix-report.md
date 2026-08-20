# Task 3.3 final summary-scope fix

## Scope

This correction closes the final response/menu leak found after the SQLite
specialist contract passed review. It changes only the supervisor summary path
and its tracked contract regressions. No Phase 4 work, migration, runtime
cutover, or controller checkout file is included.

## Root cause

After a scoped FIT_MAP run completed, `HarnessSupervisor` decorated the user
response by calling `fit_map.payload_summary()` with no path. That function's
default points to `.career-state/fit_map.json`, so the menu could describe a
different vacancy than the `application_id` that actually completed.

## TDD evidence

Before production edits, added two tracked regressions and executed:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_supervisor_contracts.SupervisorContractTests.test_scoped_fit_map_menu_uses_sqlite_snapshot_not_contaminated_root_json \
  tests.test_supervisor_contracts.SupervisorContractTests.test_completed_fit_map_menu_without_scope_is_blocked
```

Expected RED result: 2 failures.

- The scoped result rendered the planted root JSON: `Customer Success Manager |
  Instaleap`, `1.0/10`, and its global gaps/objections instead of the Conexa
  SQLite snapshot.
- A completed FIT_MAP result without `application_id` stayed `completed`
  instead of blocking.

The contaminated-root test writes the root FIT_MAP inside this isolated
worktree, restores its prior bytes (or removes the temporary file), builds the
normal nested pipeline result, and asserts that only the canonical Conexa
company, role, 8.7 score, and SQLite-derived gap/objection counts appear.

## Implementation

- The final menu resolves `application_id` from the scoped result, its
  specialist result, or its intake result.
- A missing scope returns a blocked `fit_map_summary_blocked` result with
  `explicit_application_scope_required`; no menu is produced from global
  state.
- The menu fields come from `ContextMaterializer(self.db).build(
  application_id, "fit_map_seed")`, which reads canonical SQLite
  application/analysis records. Gap and objection counts are derived from the
  materialized analysis, and keyword registration is counted in the canonical
  SQLite registry for that same application.
- If the canonical materialized snapshot cannot be resolved, the response
  fails closed as `fit_map_summary_context_unavailable`.
- `harness_supervisor.py` no longer calls unscoped `fit_map.payload_summary()`;
  the separate FIT_MAP finalizer keeps its existing explicit application-local
  path call.

## Verification

Focused red/green regressions after implementation:

```text
Ran 2 tests ... OK
```

Focused and neighboring suite:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_supervisor_contracts tests.test_harness_notion_filters \
  tests.test_context_materialization tests.test_artifact_provenance \
  tests.test_workflow_gates tests.test_application_projection \
  tests.test_intake_sqlite_scope tests.test_intake_runtime_scope \
  tests.test_task_3_1_final_scope tests.test_identity_firewall \
  tests.test_identity_firewall_request_and_habilidades

Ran 94 tests in 7.526s
OK
```

Also passed:

```text
PYTHONPATH=src ./scripts/python.sh -m py_compile \
  src/career/services/harness_supervisor.py tests/test_supervisor_contracts.py
git diff --check
```

The two `argparse` messages in the neighboring suite are expected negative
identity-firewall tests; the unittest process completed successfully.
