# Phase 3 integration fix report

Date: 2026-08-20
Branch: `fix/task-3-integration-final`
Base: `c35271a`
Scope: final bounded Phase 3 integration correction only. No Phase 4/5 work or runtime cutover was started.

## Diagnosis closed

1. Production finalization built/scored/validated the FIT_MAP through `run_task`, but never created an `AnalysisRepository` revision. Revision-bound gates therefore failed with `revision_id is required`.
2. Real intake inserted an `application_revisions` row with an empty payload before inserting its source and description. The pinned materializer could not prove which job description belonged to that intake.
3. `AnalysisRepository.get_current`, gate satisfaction, and the unpinned materializer selected latest records independently. After re-intake this could expose old analysis/gates beside the new description.
4. Emitted local-model instructions still contained root-level FIT_MAP/draft/request paths and unscoped FIT_MAP/guard commands.

## Implementation

- `persist_intake` now records source and description first, then creates a `job_description` application revision with `job_description_id`, `job_source_id`, description hash/path, source type/URL, and source-metadata hash.
- Added one shared production `finalize_fit_map` service in the existing task registry. Both the supervisor and CLI finalizer call it.
- Finalization validates the draft, builds/scores/validates the real FIT_MAP, snapshots current canonical reference versions, creates an immutable analysis revision tied to the current application revision/fingerprint/description, and records build/score/validate receipts with the same `revision_id`.
- Analysis creation validates explicit current lineage, records the canonical job fingerprint and source IDs, preserves the final score, and is idempotent for the same source/payload revision.
- Current analysis and gate lookup now require the current application revision/fingerprint. A new intake therefore invalidates old current gates and yields `fill_fit_map_draft`.
- The supervisor returns `stale_analysis_for_current_application_revision` when historical analysis exists but no analysis belongs to the current intake.
- Explicit historical `revision_id` materialization resolves the old analysis, its linked old job description, and its pinned reference versions.
- Emitted local maps, requests, and guard responses now use application-scoped paths and application-scoped FIT_MAP/guard commands.

## TDD evidence

RED was recorded before production changes:

- Initial E2E run: 3 tests, 3 failures (unscoped local map, production finalizer blocked, and stale re-intake setup blocked because finalization failed).
- Separate real-intake linkage regression: 1 test, 1 error with `application revision does not prove a linked job description`.

GREEN evidence:

- New real E2E module: 4 tests passed in 0.551s.
- Complete declared Phase 3 command: 133 tests passed in 11.018s with zero failures/errors.
- After the final lineage/idempotency hardening: 48 directly affected tests passed in 5.106s with zero failures/errors. This set included all 4 new E2E regressions plus supervisor contracts, workflow gates, analysis revisions, and context materialization.
- `py_compile` passed for all 9 changed production modules and the new E2E test module.
- `git diff --check` passed.

The final repeat of the complete 133-test command was interrupted by the user after 2.1s and produced no valid result; it is not claimed as evidence. `tests.test_harness_notion_filters` remains a zero-test `unittest` module and contributes zero to the counts above.

## Files changed

- `src/career/services/application_context.py`
- `src/career/services/persistence/analysis_repository.py`
- `src/career/services/persistence/gate_repository.py`
- `src/career/tasks/registry.py`
- `src/career/services/context_materializer.py`
- `src/career/services/harness_supervisor.py`
- `src/career/services/agent_guard.py`
- `src/career/services/multiagent.py`
- `src/career/cli.py`
- `tests/test_phase3_integration_e2e.py`
- this report

## Residuals

- Historical database rows created before canonical intake linkage may still lack `job_description_id`/reference links. They fail closed and require the later reconciliation/backfill phase; no compatibility fallback was added here.
- Root JSON files and other compatibility mirrors remain present by design, but they no longer select the application or current analysis in this path.
- No Phase 4/5 migration, cutover, or deletion of legacy persistence was performed.
