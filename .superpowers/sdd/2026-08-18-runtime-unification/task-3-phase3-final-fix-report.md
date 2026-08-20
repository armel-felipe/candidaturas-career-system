# Task 3 — Phase 3 final production-path fix report

Date: 2026-08-20
Branch: `fix/task-3-phase3-final-fix`
Base: `009e92e`

## Scope completed

- Routed the public individual `fit-map build`, `fit-map score`, and
  `fit-map validate` CLI paths through a revision-aware dispatcher.
- Added canonical lineage resolution before stage-specific FIT_MAP writes.
- Each mutating stage now persists an immutable analysis snapshot and binds its
  gate receipt to a valid `revision_id`. Later individual stages carry the
  prerequisite receipts onto the new immutable snapshot.
- Added migration `008_revision_aware_gate_receipts.py`, which backfills a
  direct receipt `revision_id`, preserves `gate_dependencies`, replaces the
  old global hash uniqueness constraint, and separates revision-bound from
  unbound idempotency.
- Added transaction-aware analysis revision and gate recording APIs. FIT_MAP
  revision creation plus initial build/score/validate receipts now run in one
  outer SQLite transaction and commit or roll back as one unit.
- Kept V1 analysis revisions explicitly addressable while current V2
  finalization succeeds with equal stage hashes.
- Preserved application scope, current-source fingerprint checks, pinned
  materialization, scoped local maps, supervisor behavior, and JSON mirror
  one-way authority.

## TDD evidence

The production-path test was added before runtime changes and executed RED:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -v tests.test_phase3_production_paths

Ran 3 tests in 0.923s
FAILED (failures=1, errors=5)
```

The failures reproduced all three defects:

- `ValueError: revision_id is required` from public `fit-map build`;
- `sqlite3.IntegrityError: UNIQUE constraint failed` during V2 re-intake with
  equal stage hashes;
- one orphan `fit_map_revisions` row after a forced scored-receipt failure.

After the fix, the same real CLI/re-intake/forced-failure tests passed. A fourth
regression also proves that an application without a current source revision
does not overwrite its FIT_MAP compatibility file.

## Final verification

Complete Phase 3 suite plus the new production-path E2E:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_sqlite_persistence tests.test_database \
  tests.test_application_repository tests.test_analysis_revisions \
  tests.test_workflow_gates tests.test_artifact_provenance \
  tests.test_application_projection tests.test_intake_sqlite_scope \
  tests.test_intake_runtime_scope tests.test_task_3_1_final_scope \
  tests.test_identity_firewall_request_and_habilidades \
  tests.test_context_materialization tests.test_task_3_2_correction \
  tests.test_supervisor_contracts tests.test_linkedin_intake_metadata \
  tests.test_phase3_integration_e2e tests.test_phase3_production_paths

Ran 132 tests in 13.104s
OK
```

Isolated identity firewall:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_identity_firewall

Ran 8 tests in 0.135s
OK
```

The argparse usage lines printed by that suite are expected assertions for
missing `--application-id`.

## Residuals and boundaries

- JSON FIT_MAP files remain compatibility mirrors; canonical selection and
  lineage authority remain in SQLite.
- The migration backfills `revision_id` only where a historical
  `gate_dependencies` link proves it. Unlinked historical receipts remain
  unbound and therefore cannot satisfy revision-bound gates.
- A database failure after a compatibility JSON stage write can leave that
  mirror ahead of SQLite, but it cannot create an authoritative orphan
  revision or partial receipt set. Canonical recovery continues to fail closed
  on SQLite state.
- No Phase 4/5 work was started.
- The dirty controller checkout and its unrelated modified/untracked files were
  not edited; all task work was performed in the isolated worktree.
