# Task 2.2 Report — Artifact Provenance and Review Dependencies

Date: 2026-08-18
Commit baseline: `2b536f3`
Status: complete — ready for controller review
Workspace: `/opt/agent-projects/candidaturas`

## Scope executed

Bounded Task 2.2 scope only:

- `src/career/services/persistence/artifact_repository.py`
- `src/career/services/review.py`
- `scripts/review_output.py`
- `tests/test_artifact_provenance.py`
- one numbered migration if required by the implementation

No writes have been made to `control-plane/career.db`; verification uses temporary SQLite databases only.

## TDD record

### RED

Created `tests/test_artifact_provenance.py` first, covering:

1. DOCX registration with persisted hash, MIME, size, optional extracted text, and source FIT_MAP / positioning lineage
2. rejection when the source revision exists but its validated FIT_MAP dependency is missing
3. rejection of unsupported artifact kinds
4. path/content mutation invalidation after registration
5. duplicate registration idempotence
6. application isolation for otherwise identical artifacts
7. review receipt ordering: artifact stays non-publishable until a real passed receipt exists
8. rejection of unapproved review reports even when a receipt row exists

Initial failing command:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_artifact_provenance.py
```

Observed failure:

```text
======================================================================
ERROR: test_artifact_provenance (unittest.loader._FailedTest.test_artifact_provenance)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_artifact_provenance
Traceback (most recent call last):
  File "/usr/lib/python3.12/unittest/loader.py", line 137, in loadTestsFromName
    module = __import__(module_name)
             ^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/agent-projects/candidaturas/tests/test_artifact_provenance.py", line 15, in <module>
    from career.services.persistence.artifact_repository import ArtifactRepository
ModuleNotFoundError: No module named 'career.services.persistence.artifact_repository'

----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

### Partial-work assessment

An uncommitted partial implementation was present when the task resumed:
`artifact_repository.py`, migration `007`, and the focused test. It was kept
only after its scope and schema approach matched this task. It was not treated
as complete: the first real focused run failed with six foreign-key errors
because `artifact_versions.run_id` had no matching `application_runs` row, and
the script/review integration did not exist.

### Additional RED cycle

Before adding the review publication path, the focused suite failed with the
expected missing contract:

```text
ImportError: cannot import name 'record_approved_cv_provenance'
from 'career.services.review'
```

Before adding the script edge, the next focused cycle failed with:

```text
ImportError: cannot import name 'publish_approved_review_provenance'
from 'review_output'
```

The neighboring migration suite then exposed the expected schema-version
regression from adding `007`: its old migration counts and pre-005 fixture no
longer described the migration sequence. The fixture now starts at `004`, so
the test exercises `005`, `006`, and `007` in order.

### GREEN

Implemented and verified:

1. `ArtifactRepository.register()` creates or validates an application-scoped
   run in the same immediate transaction, records immutable file/text hashes,
   MIME, byte size, source FIT_MAP revision and optional positioning revision.
   Idempotence includes `run_id`; a distinct run is a distinct provenance
   version.
2. Artifact dependencies are validated against the same application. Public
   path validation checks source gate lineage, path mutation, review report
   hash, passed review receipt and approval status. A draft artifact is never
   publishable.
3. `record_approved_cv_provenance()` validates the final objective report and
   exact artifact path before creating the draft artifact, recording the
   `cv_review_passed` SQLite receipt, and binding that receipt to the artifact.
   An unapproved report raises before any artifact/receipt write.
4. `scripts/review_output.py` accepts the opt-in scoped arguments
   `--application-id`, `--source-revision-id`, `--run-id` and `--control-db`.
   Existing invocations without all four keep report-only compatibility; an
   unapproved report is explicitly not published as a receipt.
5. Migration `007_artifact_review_provenance.py` adds artifact-review fields
   and the `artifact_version_dependencies` relation without rewriting existing
   files or legacy JSON.

## Verification

Focused provenance suite:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_artifact_provenance.py
```

Result:

```text
Ran 9 tests in 0.651s
OK
```

Focused neighboring persistence suite:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests/test_artifact_provenance.py \
  tests/test_analysis_revisions.py \
  tests/test_workflow_gates.py \
  tests/test_application_repository.py \
  tests/test_sqlite_persistence.py \
  tests/test_database.py
```

Result:

```text
Ran 61 tests in 8.396s
OK
```

`git diff --check` was clean for all Task 2.2 files. The implementation writes
only the requested review report as an output; no Task 2.2 runtime path reads
or writes `workflow_state.json`, `active_application.json`, or another JSON
state authority. All test databases were temporary; `control-plane/career.db`
was not modified.
