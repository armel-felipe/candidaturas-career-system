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
