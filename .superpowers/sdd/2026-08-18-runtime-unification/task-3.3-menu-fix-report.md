# Task 3.3 — final menu-scope fix

## Scope

This final Task 3.3 correction changes only the scoped post-FIT_MAP menu in
`HarnessSupervisor` and its tracked contract regression. It does not start
Phase 4 or change migration, runtime deployment, or controller-worktree files.

## Root cause

The prior FIT_MAP summary fix correctly obtained company, role, score and
counts from the resolved application's SQLite materialization. The same menu
still added `active_intake` from the root compatibility
`.career-state/workflow_state.json`, however. A scoped Conexa completion could
therefore present an Instaleap active pointer and omit its own
`application_id`.

## TDD evidence

Before production edits, added the real regression
`test_scoped_fit_map_menu_ignores_contaminated_root_active_intake`. It creates
an isolated canonical SQLite snapshot for `notion_578` / Conexa, then writes a
root `workflow_state.json` whose `active_intake` names `notion_579` /
Instaleap. The regression executes the real scoped pipeline decoration.

The first run failed as expected:

```text
AssertionError: None != 'notion_578'
Ran 1 test ... FAILED (failures=1)
```

The missing value was the resolved `application_id`; before this assertion,
the same response also contained the global `active_intake` payload.

## Implementation

- The scoped `agent_menu` now records the resolved `application_id`.
- It no longer reads or returns `active_intake` (or stale intake) from root
  `workflow_state.json`.
- Existing menu summary fields remain sourced from the same SQLite
  `ContextMaterializer` snapshot introduced in the prior correction.

Thus a scoped response contains only the resolved application identity and
SQLite-derived FIT_MAP summary; it cannot present a global pointer from another
vacancy.

## Verification

Focused menu regressions:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_supervisor_contracts.SupervisorContractTests.test_scoped_fit_map_menu_ignores_contaminated_root_active_intake \
  tests.test_supervisor_contracts.SupervisorContractTests.test_scoped_fit_map_menu_uses_sqlite_snapshot_not_contaminated_root_json \
  tests.test_supervisor_contracts.SupervisorContractTests.test_completed_fit_map_menu_without_scope_is_blocked

Ran 3 tests in 0.195s
OK
```

Focused and neighboring Phase 1–3 suites:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_supervisor_contracts tests.test_harness_notion_filters \
  tests.test_context_materialization tests.test_task_3_2_correction \
  tests.test_artifact_provenance tests.test_workflow_gates \
  tests.test_application_projection tests.test_intake_sqlite_scope \
  tests.test_intake_runtime_scope tests.test_task_3_1_final_scope \
  tests.test_identity_firewall tests.test_identity_firewall_request_and_habilidades \
  tests.test_sqlite_persistence tests.test_database \
  tests.test_application_repository tests.test_analysis_revisions

Ran 129 tests in 8.231s
OK
```

Also passed:

```text
PYTHONPATH=src ./scripts/python.sh -m py_compile \
  src/career/services/harness_supervisor.py tests/test_supervisor_contracts.py
git diff --check
```

The two `argparse` messages during the neighboring suite are expected negative
identity-firewall tests; the unittest process exited successfully.
