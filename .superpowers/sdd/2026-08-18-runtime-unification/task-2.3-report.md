# Task 2.3 — Application stage projection

## TDD red phase

Before production changes, I added `tests/test_application_projection.py`, which
exercises intake, FIT_MAP, CV review, delivery, Notion closure, legacy-state
divergence, missing applications, and cross-application isolation using a real
temporary SQLite database.

Command run:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_application_projection.py
```

Expected result observed: failure during test discovery because
`career.services.application_context.build_application_projection` does not yet
exist. This proves the tests target the new public projection boundary rather
than existing legacy stage-file behavior.

## Implementation

- Added `ApplicationStage`, `derive_application_stage()` and the immutable
  SQLite projection in `career.services.applications_v2`.
- Added the public `build_application_projection()` boundary to
  `career.services.application_context`. Its local import avoids the existing
  path-helper import cycle.
- The stage is derived only from `ApplicationRepository`,
  `AnalysisRepository`, `GateRepository`, `ArtifactRepository`, `deliveries`
  and `notion_syncs`. A CV path alone never advances a stage: it must be an
  approved artifact with a valid review receipt, current bytes and matching
  FIT_MAP provenance.
- The delivery must belong to that approved CV and use the `onedrive` channel.
  A successful Notion sync must have a matching canonical Notion record before
  the base package is sealed.
- A contradictory legacy `state.json` can only produce an idempotent
  `workflow_events.application_projection_divergence` observation. It does not
  overwrite application rows or alter the SQLite-derived stage.

## Verification

Focused projection and neighboring persistence/application suites:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests/test_application_projection.py \
  tests/test_workflow_gates.py \
  tests/test_artifact_provenance.py \
  tests/test_application_repository.py \
  tests/test_analysis_revisions.py \
  tests/test_sqlite_persistence.py \
  tests/test_database.py
```

Observed: `Ran 73 tests ... OK`.

Syntax check:

```bash
PYTHONPATH=src ./scripts/python.sh -m py_compile \
  src/career/services/applications_v2.py \
  src/career/services/application_context.py \
  tests/test_application_projection.py
```

Observed: success with no output.

Diff review used `git diff --check` and searched the new projection functions
for global `workflow_state.json` authority. The only legacy state read is the
explicit optional observation input; no stage/next-action decision is read from
JSON.

## Fix round 1 — receipt integrity

Independent review found that the first implementation still accepted a
`deliveries` row with `channel=onedrive`, `status=delivered` and null report
fields, plus any successful Notion sync. The root cause was status-only SQL
queries with no proof of receipt bytes or current-artifact linkage.

The fix keeps the existing tables and treats their receipt fields as
fail-closed contracts:

- OneDrive requires non-empty `report_path` and a valid SHA-256
  `report_hash`; the report file must exist and hash identically.
- Delivery payloads must bind `artifact_version_id`, `artifact_hash`,
  `source_revision_id` and `positioning_revision_id` to the current approved CV
  version.
- Notion sync payloads must bind the same artifact/revision fields and include
  a receipt path/hash whose bytes verify. The sync must also join its canonical
  `notion_records` row for the same application.
- Status-only, null-hash, stale-artifact and stale-sync rows remain pending and
  cannot seal the base package. No legacy JSON field is consulted.

New regressions cover status-only delivery, a sync receipt for a previous CV,
and a delivery receipt for a previous CV. The helper for the healthy package
now writes valid delivery and Notion receipt files with hashes and explicit
revision bindings.

Focused verification after the fix:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_application_projection.py
```

Observed: `Ran 11 tests ... OK`.

Neighboring persistence/application verification:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests/test_application_projection.py \
  tests/test_workflow_gates.py \
  tests/test_artifact_provenance.py \
  tests/test_application_repository.py \
  tests/test_analysis_revisions.py \
  tests/test_sqlite_persistence.py \
  tests/test_database.py
```

Observed: `Ran 76 tests ... OK`.
