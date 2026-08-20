# Task 3.3 — Supervisor fail-closed

## Scope

Implemented the Task 3.3 contract boundary only.  No post-processing service,
JSON migration, runtime cutover, or controller-worktree file was changed.

## Root cause

`HarnessSupervisor.execute_specialist` previously regarded an allowed changed
file as a sufficient completion signal.  That signal has no application,
revision, provenance, hash, or review-receipt proof, so it could report a
successful specialist run with an unreviewed, stale, or cross-application
artifact.

## TDD evidence

Before production changes, added the tracked
`tests/test_supervisor_contracts.py` and ran:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_supervisor_contracts
```

Result: expected RED import failure:

```text
ImportError: cannot import name 'SpecialistContract'
```

The failing suite specified these real SQLite behaviors:

- a DOCX without an approved review receipt is blocked and audited;
- a FERAS registered to another application cannot satisfy the current
  application;
- mutation after artifact registration/review invalidates the contract;
- a declared but absent gate blocks without partial success;
- matching application, current revisions, approved artifact and receipt
  gates complete successfully without altering the base-package stage;
- unscoped, unknown, and malformed identifiers fail closed, and the legacy explicit pipeline
  signature remains compatible.

## Implementation

- Added immutable `SpecialistContract` and `SpecialistResult` interfaces.
- Added the authoritative
  `HarnessSupervisor.execute_specialist(application_id, contract, ...)` path.
- Resolves the application, current FIT_MAP revision and current positioning
  revision exclusively through canonical SQLite repositories.
- Selects artifacts only by the exact `(application_id, kind,
  source_revision_id, positioning_revision_id)` tuple, then asks
  `ArtifactRepository.validate_path()` to prove dependencies, review receipt,
  path existence, and current content hash.
- Verifies every declared gate using `GateRepository`, binding revision-aware
  gates to the current FIT_MAP revision.
- Persists a `specialist_contract` validation receipt and a
  `specialist_contract_blocked` / `specialist_contract_completed` workflow
  event with application, run, validator, reason, revisions, missing
  requirements and a canonical result hash.
- Kept the pre-existing pipeline invocation shape as a compatibility adapter.
  Its allowed-file diff remains an isolation diagnostic only: when a default
  contract exists, the adapter validates the contract before returning
  `completed`.

## Verification

Focused supervisor suite:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_supervisor_contracts tests.test_harness_notion_filters

Ran 7 tests ... OK
```

Required focused and neighboring suites:

```text
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests.test_supervisor_contracts tests.test_harness_notion_filters \
  tests.test_context_materialization tests.test_artifact_provenance \
  tests.test_workflow_gates tests.test_application_projection \
  tests.test_intake_sqlite_scope tests.test_intake_runtime_scope \
  tests.test_task_3_1_final_scope tests.test_identity_firewall \
  tests.test_identity_firewall_request_and_habilidades

Ran 92 tests ... OK
```

Also passed:

```text
PYTHONPATH=src ./scripts/python.sh -m py_compile \
  src/career/services/harness_supervisor.py src/career/services/multiagent.py
git diff --check
```

The two argparse usage messages from existing identity-firewall negative-path
tests are expected; the unittest process exited successfully.

## Residuals

- A call without a resolvable application cannot be inserted into
  `workflow_events`, because the event table deliberately enforces the
  application foreign key.  Those calls return a blocked `SpecialistResult`
  containing its run and blocker reason; resolved applications always receive
  a durable workflow event.
- Generic reviewed post-processing artifact production remains Phase 4 work.
  The new default contracts therefore fail closed until a future producer
  registers the matching artifact and review provenance.
