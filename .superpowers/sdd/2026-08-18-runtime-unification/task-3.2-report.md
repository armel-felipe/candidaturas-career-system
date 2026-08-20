# Task 3.2 — SQLite context materializers

## Scope delivered

- Added `src/career/services/context_materializer.py` with
  `ContextMaterializer.build(application_id, kind, revision_id=None)` and
  `export_json(application_id, kind, destination)`.
- Added canonical repository readers instead of introducing a new schema:
  `ApplicationRepository.get_latest_job_description`,
  `ApplicationRepository.get_current_revision_id`,
  `AnalysisRepository.get_revision`, and
  `ReferenceRepository.list_current_versions`.
- Added `derived_context.materialize_context` and
  `derived_context.export_materialized_context` as SQLite-only runtime
  boundaries.
- Updated `multiagent.write_request` for `fit-map`, `cv`, `feras`, and
  `habilidades` to construct a scoped in-memory materialization and write a
  one-way application-local JSON compatibility copy. The request consumes the
  in-memory value; it does not read the export back.
- Added tracked coverage in `tests/test_context_materialization.py`.

## TDD evidence

The new focused test was run before production implementation:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_context_materialization
ModuleNotFoundError: No module named 'career.services.context_materializer'
```

That is the expected RED state: the requested public module did not exist.

## Acceptance evidence

`tests/test_context_materialization.py` verifies:

- all four kinds: `fit_map_seed`, `cv_input`, `feras_input`, and
  `habilidades_input`;
- current and pinned FIT_MAP revisions, including foreign/unknown failures;
- source revision identifiers, deterministic canonical content hash and
  generated metadata;
- one-way hashable export, scoped destination enforcement and export mutation
  not affecting a rebuilt canonical context;
- isolation for two applications using the same kind.

The existing real scoped request tests exercise the `multiagent` consumer
without using a global FIT_MAP or derived path as the selector.

## Verification

Focused and request scope regression suite:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_context_materialization \
  tests.test_identity_firewall_request_and_habilidades \
  tests.test_task_3_1_final_scope

Ran 12 tests ... OK
```

Neighboring Task 1–3 suite:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_context_materialization \
  tests.test_task_3_1_final_scope \
  tests.test_identity_firewall_request_and_habilidades \
  tests.test_intake_runtime_scope \
  tests.test_intake_sqlite_scope \
  tests.test_workflow_gates \
  tests.test_sqlite_persistence \
  tests.test_database \
  tests.test_application_repository \
  tests.test_analysis_revisions \
  tests.test_artifact_provenance \
  tests.test_application_projection

Ran 106 tests ... OK
```

No migration, supervisor-contract, reconciliation, or cutover work was
included.
