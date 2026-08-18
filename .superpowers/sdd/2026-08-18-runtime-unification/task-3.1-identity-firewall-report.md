# Task 3.1 — final identity-firewall hardening report

## Root cause

The prior intake correction scoped the first persistence step, but several
later producers reconstructed their target from global compatibility state:
the supervisor finalizer used global FIT_MAP paths, derived context read the
last active workflow state, and CLI command defaults selected global files.
`Database()` also still pointed at the legacy state database.

## Boundary implemented

- `Database()` now resolves `control-plane/career.db`; explicit database paths
  remain valid for tests, migration and recovery work.
- FIT_MAP, CV, derived, FERAS and cover-letter runtime entrypoints require an
  `application_id`/`ApplicationPaths`; missing scope fails closed.
- The supervisor FIT_MAP auto-finalizer receives the specialist request's
  application ID, passes an application-scoped store to every gate, and uses
  only application-local draft/FIT_MAP/keyword-registry paths.
- JSON global state is not consulted to select a job. Compatibility files are
  materialized only after an application scope is fixed.
- CLI FIT_MAP and derived operations require `--application-id`; CV, FERAS
  and cover-letter production commands follow the same rule.
- The operational guidance in AGENTS, intake, fit-analysis, career-system and
  processe-a-vaga now documents scoped commands and removes the global-state
  synchronization snippet.

## TDD and verification evidence

1. `tests/test_identity_firewall.py` was added before the implementation.
   Its initial run failed because `Database()` resolved
   `.career-state/career.db`, the supervisor used global FIT_MAP paths, and
   unscoped derived/generator calls read global workflow state.
2. Final fresh verification:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_identity_firewall tests.test_intake_sqlite_scope \
  tests.test_intake_runtime_scope tests.test_workflow_gates \
  tests.test_application_repository tests.test_analysis_revisions \
  tests.test_application_projection tests.test_artifact_provenance \
  tests.test_sqlite_persistence tests.test_database \
  tests.test_linkedin_intake_metadata
```

Result: `Ran 105 tests ... OK`.

## Coverage added

- canonical default database;
- unscoped derived/post-processing rejection;
- explicit `ApplicationPaths` materialization;
- supervisor finalizer missing-scope block and application-local draft use in
  the presence of a poisoned global draft;
- CLI rejection of unscoped FIT_MAP/derive commands and application-local
  FIT_MAP status resolution.

## Deliberate boundary

This change does not implement Task 3.2's SQLite context materializer. The
existing application-local JSON packs remain compatibility materializations;
they are no longer allowed to choose an application. The pre-existing,
untracked `tests/test_intake_persistence.py` was preserved and excluded from
evidence because it asserts the retired legacy database location.
