# Task 3.1 final fix — request and Gupy identity firewall

## Scope completed

- Scoped multiagent requests now serialize application-local FIT_MAP and
  derived paths, and every emitted CLI instruction for the scoped workflow
  carries `--application-id <id>`.
- The FIT_MAP expected output for `fit-map` requests is application-local.
- `habilidades-chave` resolves the requested application through
  `ApplicationRepository` in canonical SQLite with `allow_legacy=False`
  before it accepts or opens the application FIT_MAP. Unknown IDs and foreign
  path overrides fail closed.
- The two remaining operational documentation sections now prescribe
  application-scoped derived paths and commands.

## TDD evidence

1. Added `tests/test_task_3_1_final_scope.py` before production changes.
2. Initial red run:

   ```bash
   PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_task_3_1_final_scope
   ```

   Result: 3 tests, 2 failures. The real request serialized
   `.career-state/fit_map.json`, `.career-state/derived/`, and unscoped
   `npm run` commands; an unknown Gupy application reached the FIT_MAP reader.
3. After the implementation, the same test command passed: 3 tests, 0
   failures. The request assertion invokes the real CLI/supervisor/request
   path and does not mock the compact-input helper.

## Final verification

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_task_3_1_final_scope \
  tests.test_identity_firewall_request_and_habilidades \
  tests.test_identity_firewall \
  tests.test_intake_sqlite_scope \
  tests.test_intake_runtime_scope \
  tests.test_workflow_gates \
  tests.test_application_repository \
  tests.test_analysis_revisions \
  tests.test_application_projection \
  tests.test_artifact_provenance \
  tests.test_sqlite_persistence \
  tests.test_database \
  tests.test_linkedin_intake_metadata
python3 -m py_compile src/career/services/multiagent.py src/career/cli.py \
  tests/test_task_3_1_final_scope.py
```

Result: `Ran 112 tests ... OK`; compilation exited successfully. The two
argparse messages in the output are expected assertions that unscoped
FIT_MAP/derived commands are rejected.

## Incidental test correction

`test_update_projection_returns_latest_fingerprint` used a fixed 2026-08-19
timestamp. With the current runtime date after that value, its supposedly
latest revision was legitimately older than the record created by the test.
The test now creates its explicit newer revision one minute after the current
time; no production repository behavior changed.

## Residual concerns

- This task intentionally does not materialize derived packs from SQLite;
  that remains Task 3.2. Application-local JSON continues as a compatibility
  artifact, never identity authority for these request/Gupy paths.
- Legacy root compatibility files and the local-model map still exist for
  migration compatibility. They are not serialized into a scoped request and
  do not select the target application.
