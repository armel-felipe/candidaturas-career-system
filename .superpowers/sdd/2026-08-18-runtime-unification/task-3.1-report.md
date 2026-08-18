# Task 3.1 — intake and guard SQLite scope report

## RED: focused regressions before implementation

Command:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_intake_sqlite_scope
```

Result: failed as expected (5 errors).

- `career.services.intake.JobSource` and `start_intake` do not exist, so an intake cannot atomically persist its source description with identity.
- `agent_guard.guard` accepts neither `database` nor explicit `application_id`/`fingerprint`; it still derives agent scope from state/global pointer.

No production code was changed before this red run.

## GREEN: implementation verification

Focused and neighboring validation passed:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_intake_sqlite_scope tests.test_intake_persistence \
  tests.test_application_repository tests.test_application_projection
# Ran 37 tests: OK

PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_workflow_gates tests.test_linkedin_intake_metadata
# Ran 24 tests: OK
```

The implementation commits identity, source, job description, and fingerprint
inside one SQLite transaction before compatibility source/draft/context files
are materialized. Guards reject absent scope, unknown applications, and
fingerprint mismatches before consulting the FIT_MAP guard. Active pointers
remain discovery-only and `resolve_active_application()` fails closed.

## Follow-up scope hardening

An additional regression verifies that a caller which supplies both an explicit
`application_id` and a legacy global `WorkflowStateStore` cannot smuggle that
global pointer into agent execution. The guard discards the unscoped store and
loads the declared application's SQLite-backed projection instead.

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_intake_persistence tests.test_intake_sqlite_scope \
  tests.test_application_repository tests.test_application_projection \
  tests.test_workflow_gates tests.test_linkedin_intake_metadata
# Ran 62 tests: OK
```

## Correction round: canonical database and explicit execution scope

Independent review rejected the initial Task 3.1 implementation because the
operational intake repository still defaulted to `.career-state/career.db`,
and `resume`, request bundles, supervisor execution and CLI entry points could
select a vacancy through a global pointer.

### RED

Focused tests were added to `tests/test_intake_sqlite_scope.py` and run before
the correction. They failed as expected: the default intake had no tables in
`control-plane/career.db`; unscoped resume and request bundle proceeded; the
CLI rejected guard scope arguments; the supervisor had no explicit scope
contract; and a same-fingerprint foreign `active_intake` was accepted.

### GREEN

- Operational identity/source/description persistence now resolves through
  `control-plane/career.db`; explicitly injected `Database` instances remain
  available to isolated tests and migrations.
- `resume`, `write_request_bundle`, `_run_ready_pipeline`, supervisor resume
  and specialist execution fail closed without an explicit application ID.
- `agent guard` accepts and propagates required `--application-id` and
  `--fingerprint` arguments.
- Guard rejects an absent or foreign `active_intake.application_id` before it
  reads FIT_MAP context.
- The documented commands now include the explicit scope and fingerprint.

Reproducible tracked-test evidence:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_intake_sqlite_scope tests.test_application_repository \
  tests.test_application_projection tests.test_workflow_gates \
  tests.test_linkedin_intake_metadata
# Ran 63 tests: OK
```

`tests/test_intake_persistence.py` is a user-owned untracked legacy test and
still asserts the retired `.career-state/career.db` destination. It was not
modified or used as correction evidence; it must be migrated separately to
the control-plane contract.
