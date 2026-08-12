# Slice A — Core Integration Gate

## RED

Added `tests/test_slice_a_core_integration.py` first. The test creates two
application-scoped plans in one temporary SQLite database, executes them with
deterministic handlers and validators, finalizes each, and inspects both runs
through the CLI.

The initial test setup needed the existing `scripts/` import bootstrap used by
the cellular CLI tests. After that correction, the required no-payload rule was
made explicit by putting an application-specific marker in fake handler
metadata. The focused test failed as intended:

```text
assert all(marker not in serialized_database_rows for marker in payload_markers.values())
E assert False
```

This showed that arbitrary handler metadata was being copied to
`cell_attempts.detail_json`.

## Changes

- Added the two-application integration regression test.
- Kept all test data under `tmp_path/applications/<application-id>` and used a
  single `tmp_path/career.db`.
- Added `CellExecutor._receipt_metadata`, which persists only a deterministic
  SHA-256 digest for handler metadata in SQLite receipts.
- The test verifies validated immutable artifact manifests, application-local
  artifact/attempt/completion paths, persisted completed status, CLI inspection
  output, meaningful inspect next actions, and absence of the fake payload in
  SQLite rows.

## Verification

Focused (GREEN):

```text
pytest -q tests/test_slice_a_core_integration.py
1 passed in 0.15s
```

Full suite:

```text
pytest -q
158 passed in 3.02s
```

`git diff --check` also passed.

## Self-review

- The test uses no repository `.career-state` paths and no global FIT_MAP, CV
  content, workflow state, or derived context.
- Both plans are independently compiled and run in an interleaved loop against
  the same SQLite workspace; both complete from validated artifacts.
- The production change is constrained to SQLite receipt metadata. Artifact
  contents and immutable publication remain unchanged.
- Existing receipt fields still provide status, paths, hashes, and a metadata
  integrity digest; arbitrary handler payload is not persisted in SQLite.

## Commit

Implementation commit SHA: e6e7a0a

## Important findings repair — 2026-07-20

### RED

The Slice A integration gate was extended before production changes. The
focused run failed in the two intended places:

```text
assert pre_finalize_inspection["status"] == persisted_before_finalize
E AssertionError: assert 'completed' == 'planned'

assert deferred[0].status == "deferred"
E AssertionError: assert 'blocked' == 'deferred'
```

This proved that CLI inspection could infer false completion before persisted
finalization, and that transient contention on the declared `notion-write`
resource was converted into a terminal blocker rather than serialization.

### Changes and coverage

- `inspect-run` now reports the authoritative persisted
  `application_runs.status`; node reservation persists `running`, terminal
  failure persists `blocked`, and only successful finalization persists
  `completed`.
- Resource contention now cancels the owned transient attempt with a bounded
  metadata-only receipt and returns the node to `planned`. Independent
  non-resource nodes for both applications continue while `notion-write` is
  held, and the Notion node retries after release.
- Finalization is tested negatively in both required modes: arbitrary files
  without persisted attempts are rejected, and a terminal failed validator
  produces a blocked completion rather than a completed run.
- A repaired `analyze_fit` publication is tested to produce a distinct
  revision and path while preserving the original artifact and manifest bytes.
- CLI inspection status is compared directly with the matching persisted
  `application_runs` row before and after finalization.
- All paths and payloads remain application-scoped. SQLite continues to store
  metadata/receipts only; artifact contents remain in the application data
  plane.

### Verification

Focused integration:

```text
pytest -q tests/test_slice_a_core_integration.py
3 passed in 0.31s
```

Related cellular suites:

```text
pytest -q tests/test_cell_store.py tests/test_cell_executor.py tests/test_cell_manifests.py tests/test_cell_cli.py tests/test_slice_a_core_integration.py
81 passed in 1.05s
```

Full suite:

```text
pytest -q
160 passed in 3.05s
```
