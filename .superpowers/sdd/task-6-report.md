# Task 6 / Recovery Slice B — Implementation Report

Date: 2026-07-20
Implementation commit: `7a7b551` (`feat: scope intake and FIT_MAP to cells`)

## Outcome

Implemented application-scoped production cells for `capture_source`, `normalize_job`, and `analyze_fit`. Source descriptions, source metadata, normalized packs, handovers, evidence indexes, FIT_MAP inputs, FIT_MAP provenance, validation reports, and immutable published revisions stay under the authoritative `ApplicationPaths` for each application/run.

The implementation gate is green. The separate reviewer was dispatched read-only but did not return a verdict before the controller's deadline; the controller explicitly requested commit/report and will run the independent gate above this task. Therefore this report does not claim the recovery slice's independent-review acceptance gate is complete.

## RED evidence

Initial collection exposed a test-harness import issue (`scripts/` was not on `sys.path` in the two new tests). After correcting only that harness issue, the authoritative RED run was:

```text
$ pytest tests/test_cell_intake.py tests/test_fit_map_provenance.py -q
FFFFFFF                                                                  [100%]
7 failed in 0.28s
```

Expected failures were missing `intake.capture_source`, `derived_context.normalize_job`, application FIT_MAP/provenance APIs, and `production_handler_registry` / `production_validator_registry`.

## GREEN evidence

First feature GREEN:

```text
$ pytest tests/test_cell_intake.py tests/test_fit_map_provenance.py -q
.......                                                                  [100%]
7 passed in 0.29s
```

Required focused gate, after added capture and source-repair coverage:

```text
$ pytest tests/test_cell_intake.py tests/test_fit_map_provenance.py tests/test_packs.py -q
..............                                                           [100%]
14 passed in 0.62s
```

Fresh full-suite gate immediately before the implementation commit:

```text
$ pytest -q
........................................................................ [ 42%]
........................................................................ [ 84%]
..........................                                               [100%]
170 passed in 3.78s
```

Additional gates passed:

- `python3 -m py_compile` for every changed production Python module.
- `git diff --check` and `git diff --cached --check`.
- No tracked or untracked `.inbox/` content was staged or modified.

## Requirement coverage

- `capture_source` consumes an application-local source input, persists `job_description.md` and `source_metadata.json`, publishes an immutable source revision, and writes an attempt-scoped handover.
- `normalize_job` accepts immutable `ApplicationPaths`, rejects cross-application description paths, builds 14 application-local derived JSON artifacts plus `derived/manifest.json`, and publishes normalized job, handover, and evidence index artifacts.
- `analyze_fit` receives the exact draft as a hash-recorded cell input, consumes only validated normalization artifacts, builds/scores/validates the application FIT_MAP, and publishes it through the existing immutable manifest store.
- FIT_MAP provenance contains and validates `job_fingerprint`, `candidate_facts_revision`, `draft_sha256`, `contract_version`, and `produced_by_attempt`.
- Candidate facts revision is a deterministic SHA-256 over the canonical candidate-fact sources; the evidence index records every source hash.
- Production cell code calls no `configure_derived_dir`, `configure_state_store_path`, or `configure_paths`. Those functions remain deprecated legacy adapters.
- `cv_content.build_cv_content(application_paths, fit_map_path, candidate_facts_revision)` is explicit and validates FIT_MAP provenance without global path configuration.
- Two applications run through normalize/analyze in the same SQLite database with distinct descriptions, derived manifests, input hashes, FIT_MAP revisions, and publication paths.
- Repairing application A's source or FIT_MAP invalidates only A's declared contract descendants; application B's validated statuses and files remain unchanged.

## Files

Created:

- `src/career/services/provenance.py`
- `tests/test_cell_intake.py`
- `tests/test_fit_map_provenance.py`

Modified:

- `src/career/services/intake.py`
- `src/career/services/derived_context.py`
- `src/career/services/fit_map.py`
- `src/career/services/cv_content.py`
- `src/career/services/application_context.py`
- `src/career/cells/handlers.py`
- `src/career/cells/executor.py`
- `src/career/cli.py`

## Self-review

- Verified all new cell inputs are materialized in attempt manifests with a path and SHA-256, including `fit_map_draft` and capture identity/source inputs.
- Verified all writable paths added to cell capabilities remain inside the application root.
- Verified normalized and FIT_MAP artifact payloads carry application identity and lineage, while SQLite receipts remain metadata-only.
- Verified fingerprint mismatch, candidate-facts revision tampering, and draft-hash tampering are rejected.
- Verified prior immutable FIT_MAP bytes remain unchanged after a revised attempt publishes a new revision.
- Verified backward compatibility: old production registry function names remain adapters; the CLI uses the canonical registry names; the full pre-existing suite remains green.
- Reviewed the diff for accidental global configurator calls from `career.cells`; none exist.

## Independent review status

A read-only reviewer agent was dispatched with the exact brief and full changed-file list. It was still running without findings when the controller instructed this task to proceed to commit/report and stated that the controller would run the mandated independent gate. No Critical, Important, Minor, or approval verdict was returned by that reviewer, so independent approval remains explicitly pending at this report commit.
