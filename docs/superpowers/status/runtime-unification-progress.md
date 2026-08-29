# Runtime unification — Phase 8 observation status

Status: Phase 8 cutover applied to both active bots; observation window is
open. JSON compatibility data remains preserved and is not yet archived.

## Delivered

- `npm run runtime:verify -- --strict --report outputs/_tmp/runtime_verification.json`
  runs a read-only verifier with independent checks for runtime source, SQLite
  schema, gate and artifact provenance, process scope, cross-bot catalog, JSON
  authority and rollback evidence.
- `npm run runtime:canary -- --application-id <id> --bot-id vagas_bot_02`
  runs the offline canary against the explicit SQLite application projection.
- `career project runtime-canary` exposes the same canary through the canonical
  CLI.
- `live` mode is a safe preflight and intentionally does not start containers;
  it blocks with `live_canary_requires_explicit_deployment`.
- The deployed-container canary is executed from inside each active Hermes
  container using its `/opt/hermes/.venv`, against the shared SQLite database.
- Application completion is profile-aware: `standard_cv` requires the reviewed
  CV, verified OneDrive delivery and verified Notion sync; `gupy_registration`
  seals the core package after FIT_MAP and verified Gupy/Notion registration,
  without requiring CV or OneDrive unless explicitly requested.

## Evidence

- Strict verifier tests: `tests/test_runtime_verifier.py` — 3/3 passed.
- Canary tests: `tests/test_runtime_canary.py` — 2/2 passed.
- The blocked fixture reaches `cv_review_pending` when a CV has no review receipt.
- The healthy `standard_cv` fixture reaches `core_package_sealed` only with
  FIT_MAP validation, CV review, verified OneDrive delivery and verified Notion
  sync.
- The Gupy fixture for `notion_578` reaches `core_package_sealed` on both bot
  projections without a CV or OneDrive artifact.
- No external candidature was submitted or changed by this rollout. The
  production containers were recreated from the canonical root Compose only.
- A pre-live backup was created at
  `/opt/agent-projects/candidaturas-backups/runtime-unification-phase8-pre-live-20260821`.
- Both active bots now use `/opt/agent-projects/candidaturas:ro`, the shared
  control-plane and `CAREER_RUNTIME_PERSISTENCE_MODE=sqlite_only`.
- Persisted canary reports are available in the per-bot state overlays as
  `.career-state/runtime_canary_phase8.json`.
- Canonical DB was backed up before and after schema cutover:
  `/opt/agent-projects/candidaturas-backups/runtime-unification-phase7-20260820`
  and
  `/opt/agent-projects/candidaturas-backups/runtime-unification-phase7-post-schema-20260820`.
- Migrations 006–011 were applied. The 12 pre-existing unscoped receipts were
  quarantined in `quarantined_validation_receipts`; no receipt was reassociated.
- The strict verifier now passes on the canonical database with zero blockers.
- The focused Phase 8 suite passed 41/41 tests. The broader `tests/` collection
  passed 485 tests but still reports 8 legacy/cellular/documentation failures;
  those are recorded as repository debt and are not on the runtime cutover path.
- Offline canary for `notion_578` passes on `vagas_bot_01` and `vagas_bot_02`.
  Its profile is `gupy_registration`, its stage is `core_package_sealed`, and
  the next action is `post_processing_available`; the absence of a CV is
  correct for this Gupy application.
- Notion ID `589` resolves to the canonical historical application by matching
  the official Notion description fingerprint. It remains
  `historical_unverified` because scoped historical receipts were not
  reconstructible; no gate was invented.
- The canonical database contains 214 applications after import. The
  reconciliation pass classified 128 as `historical_unverified`, one as
  reconciled and 85 as blocked because the available legacy evidence was not
  sufficient to prove identity or required source artifacts. The migration
  report retains 11 conflict groups for audit/review.
- SQLite is the runtime authority. Compatibility JSON remains available for
  export, backup and observation, but `sqlite_only` fails explicitly with
  `application_not_in_sqlite` instead of falling back silently.
- Recovery and post-processing now have explicit SQLite-scoped CLI entrypoints:
  `applications:resolve`, `applications:reconcile` and `applications:artifact`.
- The Notion intake adapter was corrected to prefer explicit company/role
  properties, and intake now records the `job_description_saved` receipt.

## Post-cutover corrections

- `RUNTIME-002`: the canonical workspace root was `700 root:root`, which
  blocked the non-root Hermes worker. It is now traversable and the context
  hook is executable; both bot containers pass the UID 10000 access check.
- `RUNTIME-003`: `canonical_database()` now honors
  `CAREER_CONTROL_DB_PATH`, so container writes use the writable control-plane
  overlay instead of the read-only source tree.
- `RUNTIME-004`: `sqlite_only` now reconstructs `active_intake` from the
  SQLite projection after a process restart, instead of depending on the JSON
  compatibility pointer.
- `RUNTIME-006`: the supervisor now propagates `application_id` from the
  scoped intake envelope into the specialist request.
- `RUNTIME-007`: the Hermes subprocess runner resolves the container binary at
  `/opt/hermes/bin/hermes` instead of relying on inherited `PATH`.
- `vagas_bot_01` successfully ingested Notion ID 591 as `notion_591`; its guard
  is healthy and `intake:resume` returns `active_intake_ready` with the next
  action `fill_draft`.
- `vagas_bot_02` successfully extracted and persisted 19 LinkedIn saved jobs
  to its isolated inbox overlay.
- The 591 specialist reached the Hermes runner with the correct scoped request,
  but the model execution is currently blocked by missing `ollama-cloud`
  credentials (`OLLAMA_API_KEY`); no secret was read or copied and no fallback
  provider was selected silently.

## Gate decision

- [x] Verifier returns a structured report and strict non-zero exit code.
- [x] Offline canary proves fail-closed and healthy behavior.
- [x] Canary includes run ID, application ID, gates, artifacts, database checks
  and rollback checkpoint.
- [x] Both bot IDs are accepted and remain explicitly scoped.
- [x] Deployed-container canary for `vagas_bot_02` passed before bot 01.
- [x] Deployed-container canary for `vagas_bot_01` passed after bot 02.

The remaining item is controlled observation, not missing code or test
coverage. The CLI flag `--mode live` remains a guarded preflight and was not
used to submit anything externally. Keep the JSON backup/export layer during
the observation window; archive it only after the window is explicitly closed.
