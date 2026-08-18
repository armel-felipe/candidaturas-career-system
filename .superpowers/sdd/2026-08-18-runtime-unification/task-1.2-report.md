# Task 1.2 Report

## Scope

Implemented the SQLite-backed application repository and explicit canonical resolver for Task 1.2 without touching the live `control-plane/career.db`.

Files changed for the task:

- `src/career/services/persistence/application_repository.py`
- `src/career/services/application_context.py`
- `tests/test_application_repository.py`

Report artifact:

- `.superpowers/sdd/2026-08-18-runtime-unification/task-1.2-report.md`

## What Was Implemented

### 1. SQLite application repository

Added `ApplicationRepository` with the interfaces required by the brief:

- `create_application(identity: ApplicationIdentity) -> ApplicationRecord`
- `resolve(...) -> ApplicationRecord`
- `update_projection(application_id: str) -> ApplicationProjection`

Behavior implemented:

- explicit resolution by `application_id`
- explicit resolution by Notion ID
- explicit resolution by fingerprint
- explicit resolution by `company` + `role` only when unambiguous
- clear errors for missing selector, missing record, and ambiguous company/role matches
- alias integrity protection so a `notion_id` cannot be silently reassigned to another application

### 2. Canonical resolver in `application_context`

Added `resolve_application(...)` to route candidate lookup through the repository.

Compatibility preserved during migration:

- if the repository does not know the application yet and the caller passes an explicit `application_id`, `application_context` can synthesize a read-only legacy record from `identity.json` and `source_metadata.json`
- there is no fallback to `active_job` or `workflow_state.json`

Also wired `ensure_application(...)` to register/update the SQLite identity record when an application directory is created or refreshed.

## TDD Evidence

Red:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_application_repository.py
```

Initial failure:

- `ModuleNotFoundError: No module named 'career.services.persistence.application_repository'`

Green:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_application_repository.py
```

Result:

- `Ran 9 tests ... OK`

Compatibility verification:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_application_repository.py tests/test_intake_persistence.py
```

Result:

- `Ran 15 tests ... OK`

## Test Coverage Added

`tests/test_application_repository.py` covers:

- resolve by `application_id`
- resolve by Notion ID
- resolve by fingerprint
- ambiguous `company` + `role`
- missing explicit selector
- projection using latest fingerprint revision
- alias conflict rejection across applications
- `application_context.resolve_application(...)` ignoring invalid `workflow_state.json`
- explicit `application_id` legacy-read fallback during migration

## Notes

- The legacy compatibility path is intentionally narrow: it only falls back for explicit `application_id`, not for inferred/implicit active job state.
- This task does not introduce stage derivation from receipts/artifacts; that remains for Task 2.3.

## Fix Round 1

Reviewer concerns addressed:

1. `create_application` no longer resets progressed workflow fields on refresh. The upsert now preserves `stage`, `funil_stage`, `cv_language`, and `status` for existing rows while still refreshing identity fields.
2. `resolve_application(...)` legacy fallback is now allowed only when `application_id` is the sole explicit selector. Any combined selector set must resolve through SQLite and fail closed if not found.
3. `ensure_application(...)` now registers in SQLite before writing compatibility files. Registration uses `Database.transaction(immediate=True)` through `ApplicationRepository.create_application(...)`, and a duplicate Notion alias failure leaves no new `identity.json`.

Additional tests added in this round:

- refresh of an existing row preserves progressed workflow fields
- legacy fallback is rejected for `application_id + notion_id`
- legacy fallback is rejected for `application_id + fingerprint`
- deterministic duplicate Notion ID conflict in `ensure_application(...)` leaves the conflicting compatibility identity file absent

Fix Round 1 verification:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_application_repository.py
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_application_repository.py tests/test_intake_persistence.py
```

Results:

- `Ran 13 tests ... OK`
- `Ran 19 tests ... OK`
