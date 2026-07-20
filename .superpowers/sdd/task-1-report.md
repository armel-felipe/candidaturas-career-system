# Task 1 — SQLite cellular control plane report

## Scope completed

Implementation commit: `c076405 feat: add transactional cellular run store`.

- Added an additive, idempotent SQLite migration for `application_runs`,
  `cell_nodes`, `cell_attempts`, `artifacts`, `resource_locks`,
  `workspace_leases`, and `artifact_dependencies`.
- Preserved every pre-existing table and index. The new control-plane indices
  cover `(run_id, status)`, `(application_id, created_at)`,
  `(resource_name, expires_at)`, and `(artifact_id, input_hash)`.
- Added `Database.transaction(immediate=False)`, committing on normal exit and
  rolling back on any exception.
- Added `CellStore` with application-scoped run creation, immediate node
  reservation, attempt completion, expiring exclusive resource locks, lock
  release, and dependency-aware ready-node discovery.
- Added tests for the new schema, rollback behavior, independent application
  reservations, busy reservations, lock exclusivity/expiry, completion state,
  and dependency readiness.

## TDD evidence

1. Wrote `tests/test_cell_store.py` and expanded `tests/test_database.py`
   before creating either production interface.
2. RED command:

   ```text
   pytest tests/test_cell_store.py -q
   ```

   Result: expected collection failure, `ModuleNotFoundError: No module named
   'career.services.cell_store'` (1 collection error). This demonstrated the
   requested `CellStore` API did not yet exist.
3. Implemented the minimum database schema/transaction support and
   `CellStore` needed by those contracts.
4. First GREEN attempt exposed two test-fixture/assertion issues, not product
   behavior: the expected alphabetical table order placed `workspace_leases`
   before `workflow_events`, and direct lock setup omitted mandatory
   `acquired_at`. Corrected the tests to match the explicit schema contract.

## Verification commands and results

| Command | Result |
| --- | --- |
| `pytest tests/test_cell_store.py -q` (RED) | 1 expected collection error: missing `CellStore` |
| `pytest tests/test_database.py tests/test_cell_store.py -q` (first GREEN) | 2 test-contract setup/order failures; corrected |
| `pytest tests/test_database.py tests/test_cell_store.py -q` | `10 passed in 0.07s` |
| `pytest -q` | `72 passed in 2.19s` |
| `python -m py_compile src/career/services/database.py src/career/services/cell_store.py` | exit 0 |
| `git diff --check` | exit 0 |

## Self-review

- Reservation and lock acquisition each use `Database.transaction(immediate=True)`
  so read/check/write occur in one SQLite write transaction.
- A live reservation returns exactly `{"status": "busy"}` rather than raising;
  an expired reservation can be reclaimed with a new immutable attempt number.
- Locks are scoped only by resource name, so application nodes remain
  independent unless a later contract intentionally requests a workspace
  resource.
- `list_ready_nodes` only returns `planned`/`repairing` nodes after every
  declared requirement is `validated`.
- JSON graph payloads and dependencies are persisted as metadata; job/CV
  content is not stored in SQLite.

## Concerns / follow-up boundaries

- This task intentionally does not execute cells or extend a reservation while
  a worker is running. The executor/repair task will own the `running` state
  and lease-renewal policy.
- The tables include flexible status text rather than a database `CHECK` so all
  statuses reserved for later tasks (`planned`, `reserved`, `running`,
  `repairing`, `validated`, `blocked`, `superseded`, `cancelled`) remain
  forward-compatible.
- `create_run` accepts simple graph dictionaries now and also tolerates future
  node objects exposing `node_id`/`requires`; graph compilation/validation
  belongs to Task 2.

## Important review fixes

Follow-up commit: `fix: harden cellular attempt completion`.

- `finish_attempt` now accepts only a validated, bounded receipt containing
  `status`, `paths`, SHA-256 `hashes`, and small scalar `metadata`. It rejects
  unknown fields, unbounded collections/strings, invalid hashes, mismatched
  status, and receipts over 4 KiB before opening its write transaction.
- Completion is monotonic and ownership-bound. In one immediate transaction,
  the node update requires the current `latest_attempt`, active node status,
  and matching `reserved_by`; the attempt update also requires the matching
  owner and an unfinished active status. Both updates check `rowcount == 1`.
  A stale or unowned completion raises and rolls back rather than returning a
  false success.
- `resource_locks` were intentionally not changed: resources remain globally
  exclusive across the workspace, including LinkedIn, Notion, delivery, Git,
  and candidate facts.

### Regression tests and verification

- `test_finish_attempt_rejects_oversized_receipt_before_writing` proves a
  4 KiB-plus agent payload is rejected and leaves the node/attempt unchanged.
- `test_finish_attempt_rejects_stale_attempt_without_mutating_current_node`
  proves an expired attempt cannot finish after a new reservation; the old
  implementation would persist it and report success while silently failing
  to update the current node.

| Command | Result |
| --- | --- |
| `pytest tests/test_cell_store.py -q` (RED) | `4 failed, 4 passed`: `receipt` API absent as expected before the fix |
| `pytest tests/test_cell_store.py -q` | `8 passed in 0.05s` |
| `pytest tests/test_database.py tests/test_cell_store.py -q` | `12 passed in 0.07s` |
| `pytest -q` | `74 passed in 1.93s` |
| `python -m py_compile src/career/services/cell_store.py src/career/services/database.py` | exit 0 |
| `git diff --check` | exit 0 |
