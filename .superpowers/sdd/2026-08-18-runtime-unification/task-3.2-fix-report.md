# Task 3.2 correction — authority and historical-revision leaks

## Scope

Implemented only the Task 3.2 correction in the isolated worktree. Task 3.3
(supervisor contracts) was not started.

## TDD evidence

Before changing production code, added `tests/test_task_3_2_correction.py` and
ran:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_task_3_2_correction
```

Result: 3 expected failures:

1. A pinned v1 FIT_MAP materialization returned the latest v2 description.
2. An external lookalike `applications_v2/<id>` tree was accepted as an export destination.
3. A real FERAS request exposed a local JSON/FIT_MAP input path.

## Changed files

- `src/career/services/context_materializer.py`
  - Pins a requested FIT_MAP revision to its linked application revision and job description.
  - Projects the linked revision fingerprint, rather than a later application fingerprint.
  - Permits exports only under the database workspace's canonical application tree, or under an explicitly declared temporary root.
- `src/career/services/persistence/application_repository.py`
  - Adds scoped immutable application-revision lookup and linked job-description lookup.
  - Rejects malformed, foreign, absent, or unlinked revision evidence.
- `src/career/services/multiagent.py`
  - Embeds the SQLite materialization directly in the request.
  - Removes derived exports and local FIT_MAP files from request allowlists and primary-context instructions.
  - Derives FIT_MAP summaries from the embedded canonical analysis, never by reading local FIT_MAP JSON.
- `tests/test_task_3_2_correction.py`
  - New real regressions for v1/v2 pinning, export containment, and contaminated JSON in a scoped request.
- `tests/test_context_materialization.py`
  - Links fixture job descriptions to immutable application revisions so its pinning contract is explicit.
- `tests/test_identity_firewall_request_and_habilidades.py`
  - Updates the prior firewall expectation to verify the real SQLite request path instead of a mocked/local FIT_MAP path.

## Verification

Focused green cycle:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_task_3_2_correction tests.test_context_materialization
```

Result: `Ran 8 tests ... OK`.

Neighboring runtime/persistence suite:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_task_3_2_correction tests.test_context_materialization tests.test_task_3_1_final_scope tests.test_identity_firewall_request_and_habilidades tests.test_identity_firewall tests.test_intake_runtime_scope tests.test_intake_sqlite_scope tests.test_workflow_gates tests.test_application_projection tests.test_sqlite_persistence tests.test_database tests.test_application_repository tests.test_analysis_revisions tests.test_artifact_provenance
PYTHONPATH=src ./scripts/python.sh -m py_compile src/career/services/context_materializer.py src/career/services/persistence/application_repository.py src/career/services/multiagent.py
git diff --check
```

Result: `Ran 117 tests ... OK`; Python compilation and diff check passed.

The two argparse usage lines emitted by neighboring firewall tests are expected
fail-closed checks for missing `--application-id`; they do not indicate suite
failures.

Full `unittest discover` was also attempted. It reached 152 discovered tests
but stopped during collection because this worktree's project interpreter does
not have `pytest`, causing import failures in 26 pre-existing pytest modules.
That is an environment/dependency limitation, not a failure in the focused
unittest suite above.

## Residual concerns

- Compatibility JSON exports remain intentionally materialized for older tools, but are no longer an input to scoped multiagent requests.
- Historical analysis revisions whose application revision has no `job_description_id` link now fail closed only when callers explicitly pin that FIT_MAP revision. Legacy reconciliation/backfill is outside Task 3.2.
- Supervisor completion contracts, migration/backfill, and runtime cutover remain in later planned tasks.
