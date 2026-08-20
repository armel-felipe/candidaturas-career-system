# Task 3.2 — reference-version fix report

## Scope

Close the final historical-context leak in `ContextMaterializer`: a pinned
FIT_MAP revision must never receive the latest reference document merely
because it has the same logical key.

## Root cause

`ContextMaterializer._context()` always called
`ReferenceRepository.list_current_versions()`. That query is correct for a
new, unpinned materialization, but it is not a provenance query. Therefore a
payload pinned to analysis v1 could contain the FIT_MAP, description and
positioning of v1 together with candidate/reference content from v2.

## TDD evidence

Before production edits, added two real SQLite regressions and ran:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_context_materialization.ContextMaterializerTests.test_pinned_revision_uses_only_its_linked_reference_versions \
  tests.test_context_materialization.ContextMaterializerTests.test_pinned_revision_without_reference_linkage_fails_closed
```

Result: 2 failures as expected.

- A v1 `cv_input` request contained `REFERENCE V2` and not `REFERENCE V1`.
- A pinned revision without declared reference linkage materialized instead of
  failing closed.

## Implementation

- Added `ReferenceRepository.resolve_linked_versions(links)`.
  It resolves immutable records only by `reference_id` or by the exact
  `kind`, `logical_key`, and `content_hash` tuple, and validates optional
  fields against the stored version.
- Pinned materialization now reads `reference_versions` (or the compatibility
  alias `reference_links`) from the linked analysis and positioning snapshots,
  then resolves only those immutable records.
- Missing, malformed, mismatched, or unresolved linkage fails closed.
  The API never calls `list_current_versions()` on a pinned path.
- Unpinned materialization continues to use the current reference snapshot,
  preserving the normal creation flow.
- Updated existing historical fixtures to declare their immutable reference
  dependency explicitly.

## Verification

Focused regression after the implementation:

```text
Ran 2 tests in 0.115s
OK
```

Focused and neighboring suites:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_context_materialization tests.test_task_3_2_correction \
  tests.test_analysis_revisions tests.test_sqlite_persistence tests.test_database \
  tests.test_application_repository tests.test_workflow_gates \
  tests.test_artifact_provenance tests.test_application_projection \
  tests.test_intake_sqlite_scope tests.test_intake_runtime_scope \
  tests.test_identity_firewall tests.test_identity_firewall_request_and_habilidades \
  tests.test_task_3_1_final_scope

Ran 119 tests in 7.611s
OK
```

The test process prints two expected argparse usage messages from existing
identity-firewall negative-path tests; the suite exits successfully.

Also passed:

```text
PYTHONPATH=src ./scripts/python.sh -m py_compile \
  src/career/services/context_materializer.py \
  src/career/services/persistence/reference_repository.py
git diff --check
```

## Residuals

- Historical materializations created before reference snapshots were recorded
  now fail closed. They must be reconciled or regenerated; current reference
  data is intentionally not substituted.
- This task does not implement supervisor contracts or start Task 3.3.
