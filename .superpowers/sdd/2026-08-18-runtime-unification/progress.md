# SDD ledger — plan: docs/superpowers/plans/2026-08-18-runtime-unification.md

## Execution rules

- Work is delegated one task at a time; each implementer is followed by a task reviewer.
- The plan spec is authoritative when implementation details conflict with legacy behavior.
- Existing user changes in the checkout are preserved; no reset, checkout, or broad cleanup is permitted.
- A task is complete only after implementation tests and scoped review pass.

## Pre-flight scan

| Shared file/interface | Tasks | Finding | Ruling |
|---|---|---|---|
| `src/career/services/database.py` | 1.1, 8.1 | Task 8.1 consumes the schema/config created by 1.1. | Complete schema/pragmas in 1.1 first; 8.1 may only add runtime mode behavior and cannot fork the DB layer. |
| `application_id` resolution | 1.2, 2.3, 3.1, 5.3 | Projection and intake both depend on one resolver. | `ApplicationRepository.resolve` from 1.2 is the only resolver; later tasks must not add alternate path/name lookup. |
| `src/career/workflow/state_store.py` | 2.1, 8.2 | Compatibility projection is needed during migration, then fallback must be removed. | 2.1 makes reads projection-only; 8.2 changes the mode to explicit `application_not_in_sqlite` after cutover. |
| `src/career/services/application_context.py` | 1.2, 2.3, 3.1 | Context construction and stage projection share identity/fingerprint checks. | 1.2 defines resolution; 2.3 defines projection; 3.1 wires intake and must preserve both contracts. |
| `src/career/services/derived_context.py` | 3.2, 8.1, 8.2 | Materialization is introduced before JSON fallback is removed. | 3.2 owns materialization; 8.1 adds compatibility export; 8.2 removes read-back/fallback only. |
| `src/career/services/harness_supervisor.py` | 3.3, 8.1 | Required outputs/gates precede SQLite-primary cutover. | 3.3 owns fail-closed contracts; 8.1 only changes persistence mode and must retain contract checks. |
| `src/career/services/multiagent.py` | 3.2, 3.3 | Context materialization and specialist contract use the same request envelope. | 3.2 defines the payload source; 3.3 consumes it and cannot reintroduce global output matching. |
| `package.json` and `src/career/cli.py` | 5.1, 7.1 | Migration commands and verifier commands both extend the CLI. | Add distinct subcommands and scripts; do not replace existing commands or alter unrelated aliases. |
| `AGENTS.md` and career skills | 4.1, 6.2, 8.3 | Documentation is updated in multiple phases. | 4.1 defines the new contract; 6.2 marks `app/` compatibility; 8.3 removes obsolete references after verifier/canary evidence. |
| `control-plane/career.db` | 0.2, 1.1, 5.1, 7.2 | Backup, schema, migration and canary all touch the active DB. | All pre-cutover operations use snapshots or temporary DBs; no live migration until Phase 7 canary gate. |
| `application_runs`, `artifacts`, `validation_receipts` | 1.1, 2.1, 2.2, 7.1 | Existing cellular tables already carry related semantics. | Reuse compatible tables and add migrations; never create duplicate parallel tables with the same meaning. |

## Per-task consistency scan

| Task | Own files and test | Internal consistency check | Ruling |
|---|---|---|---|
| 0.1 | Inventory script/test | Test covers root/app divergence and Compose mounts produced by the script. | Proceed; report is read-only. |
| 0.2 | Backup script/test | Backup API and preserved legacy paths are independently verifiable. | Proceed; no delete operation allowed. |
| 1.1 | Database/migrations/test | Test exercises pragmas, migration version and rollback. | Proceed; migrations are additive. |
| 1.2 | Application repository/context/test | Resolver interface feeds context and rejects ambiguity. | Proceed; no active-job fallback. |
| 1.3 | Analysis/reference repositories/test | Revision APIs return immutable IDs and preserve source hashes. | Proceed; raw payload is audit-only. |
| 2.1 | Gate repository/registry/state store/test | Gate receipt and derived next step share application scope. | Proceed; global history cannot satisfy a scoped gate. |
| 2.2 | Artifact repository/review integration/test | Artifact publication requires dependencies and current hash. | Proceed; DOCX remains a file with DB provenance. |
| 2.3 | Applications projection/context/test | Stage is computed from receipts/artifacts, not mutable JSON. | Proceed; legacy mismatch is observation only. |
| 3.1 | Intake/guard/context/test | Intake persists before derived context and rejects fingerprint mismatch. | Proceed; application_id is explicit. |
| 3.2 | Materializer/derived/multiagent/test | Input packs are regenerated from DB and export is one-way. | Proceed; no JSON read-back. |
| 3.3 | Supervisor/multiagent/test | Required artifacts and gates are checked before success. | Proceed; “any allowed file changed” is removed. |
| 4.1 | Skills/docs/test | Main pipeline scope and forbidden sync are asserted textually. | Proceed; no inline state mutation. |
| 4.2 | Post-processing/skills/test | Post artifacts depend on positioning revisions and do not close core state. | Proceed; revisions are append-only. |
| 5.1 | Importer/CLI/test | Dry-run/apply are idempotent and record conflicts. | Proceed; no automatic approval from file existence. |
| 5.2 | Fixtures/reconciler/test | People Meet and Conexa are distinct conflict/recovery fixtures. | Proceed; unproven evidence remains blocked. |
| 5.3 | Reindex/repository/test | Multiple bot locations map to one application identity. | Proceed; alias table owns location mapping. |
| 6.1 | Compose/profiles/test | Mount check proves root code and shared control DB. | Proceed; state/output remain bot-scoped. |
| 6.2 | App compatibility/docs/test | Duplicate runtime is marked non-production without destructive removal. | Proceed; legacy files remain until observation ends. |
| 7.1 | Verifier/CLI/test | Every known diagnosis has an independent check and strict exit code. | Proceed; verifier is the final authority for rollout. |
| 7.2 | Canary/status/test | Healthy and blocked fixtures prove both success and fail-closed behavior. | Proceed; bot 02 precedes bot 01. |
| 8.1 | Persistence modes/test | SQLite-primary exports compatibility but never dual-writes. | Proceed; DB remains authoritative. |
| 8.2 | SQLite-only/state/context/test | Missing DB record produces explicit blocker rather than fallback. | Proceed; JSON becomes read-only backup. |
| 8.3 | Docs/status/test | Final docs and obsolete-command scan reflect verified runtime. | Proceed; archive only after observation. |

## Rulings

- Ruling: keep `control-plane/career.db` as the single career database — it already contains the cellular authority/run/artifact schema, while root `career.db` is empty and `app` has a duplicate schema with no operational rows; cost is a migration of legacy paths and Compose mounts.
- Ruling: preserve JSON files through migration and observation — current state is dirty and includes user-owned historical evidence; cost is temporary disk duplication, avoided by explicit backup retention rather than deletion.
- Ruling: port required cellular behavior into root before deprecating `app/` — the app copy contains newer cellular code in some areas; cost is extra comparison work, avoiding a regression hidden by mount unification.
- Ruling: use SQLite rows as canonical and permit `payload_json` only as immutable audit/context storage — FIT_MAP has variable nested shape, and forcing every LLM field into rigid columns before behavior is known would create schema churn; all gates and queries still use relational columns.

## Task status

### Task 0.1: in review — fix round 1

- Implementer commit: `d8d7905` (`feat: add persistence inventory baseline`).
- Reviewer verdict: rejected (`Spec Compliance: FAIL`, `Task quality: NEEDS REVISION`).
- Finding: `scripts/persistence_inventory.py` writes `migration_runs` from `build_inventory()`, violating the read-only inventory contract.
- Required fix: remove the SQLite write path and add a regression test proving a database with `migration_runs` is byte-for-byte/row-for-row unchanged after inventory; retain only the explicit temporary report output.
- Fix round 1 reviewer: pass; no new breakage.
- Plan correction: the Task 0.1 brief now states that `migration_runs` is written only by Task 5.1 importer, preserving the read-only baseline contract.

### Task 0.1: complete

- Final commit: `f552433` (`fix: keep persistence inventory read-only`).
- Evidence: focused suite `tests/test_persistence_inventory.py` passed 3/3; live inventory completed with `json_file_count=17806`, `root_app_divergence_count=134`, `hermes_service_count=2`.
- Task review: spec compliant after fix round; task quality approved.

### Task 0.2: in review — fix round 1

- Implementer commit: `8802137` (`feat: add restorable persistence backup baseline`).
- Reviewer verdict: rejected (`Spec Compliance: FAIL`, `Task quality: NEEDS REVISION`).
- Finding: backup hardcoded the entire `workspaces/` directory, copying 42,223 files including non-career caches; tests did not constrain the preservation scope or verify copied-file hashes.
- Ruling: preserve career recovery data under each bot's `inbox`, `outputs` and selected career state paths, but exclude browser/cache/runtime-only paths. Add a test proving excluded paths are absent and verify destination file hashes after copy. Retain the broad backup outside the worktree as a non-destructive historical snapshot; create a corrected narrow backup after the fix.
- Fix round 1 review: include-only policy and exclusion test passed, but production did not store/verify destination hashes and the report claimed `workspace_application_present=false` despite the intended fixture. Fix round 2 must add manifest-level source/destination hash verification and correct the evidence report.

### Task 0.2: complete

- Final commit: `ccc6716` (`fix: verify preserved backup file hashes`).
- Task review: fix round 2 passed; no new breakage.
- Evidence: `tests/test_persistence_backup.py` passed 3/3; corrected backup created at `/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow-v2` with 6 career databases, 26 included directories, 13,841 preserved files, and matching source/destination hashes.
- Excluded runtime browser/cache paths were verified absent; the earlier broad backup remains preserved and was not deleted.

### Task 1.1: in review — fix round 1

- Implementer commit: `32f1975` (`feat: add sqlite schema migration foundation`).
- Reviewer verdict: request changes (`Spec compliance: partial`).
- High finding: legacy `ALTER TABLE` compatibility upgrades remain inline in `_initialize_schema()` and are not represented by the versioned migration ledger; a caller of `migrate()` alone can report schema migrations current while missing required compatibility columns.
- Medium finding: existing `tests/test_database.py` asserts the pre-migration exact table list/count and is a likely suite regression after the new migrations.
- Ruling: add a versioned compatibility migration path with a legacy-database fixture, remove hidden upgrade behavior from `init_schema()`/`_initialize_schema()`, update the existing database tests to assert the consolidated contract and idempotence, and rerun focused plus legacy database tests.
- Fix round 1 review: prior findings passed, but migration checksums were calculated from raw bytes and can falsely drift between LF and CRLF checkouts. Fix round 2 must normalize line endings before hashing and test equivalent LF/CRLF migration content.

### Task 1.1: complete

- Final commit: `1090c01` (`fix: normalize migration checksum line endings`).
- Task review: fix round 2 passed; no new breakage.
- Evidence: `tests/test_sqlite_persistence.py tests/test_database.py` passed 10/10; legacy compatibility migration, integrity checks and LF/CRLF checksum regressions passed; live control DB remained read-only.

### Task 1.2: in review — fix round 1

- Implementer commit: `29f4721` (`feat: add canonical application resolver`).
- Reviewer verdict: request changes.
- High finding: `ensure_application()` can reset existing stage, funil stage, CV language and status because identity upsert writes dataclass defaults.
- High finding: explicit application_id legacy fallback can ignore conflicting Notion/fingerprint/company-role selectors.
- Medium finding: file identity is written before SQLite and alias writes are not serialized strongly enough for concurrent writers.
- Ruling: SQLite is canonical and must be written before compatibility files; existing non-identity state must be preserved; all supplied selectors must agree; use an immediate transaction/unique alias conflict path and add refresh, conflicting-selector, write-failure and concurrent-alias tests.
- Fix round 1 review: all three findings passed; no new blocker.

### Task 1.2: complete

- Final commit: `3965afb` (`fix: harden application resolver integrity`).
- Task review: fix round 1 passed.
- Evidence: repository/intake tests passed 19/19; refresh preserves workflow fields, conflicting selectors fail closed, SQLite registration precedes compatibility files, and duplicate alias conflict prevents identity file creation.

### Task 1.3: in review — fix round 1

- Implementer commit: `9f597b6` (`Add versioned analysis and reference repositories`).
- Reviewer verdict: request changes.
- High finding: reference versioning is not first-class queryable; synthetic `reference_key` and `keyword_translations.keyword` prefixes break logical-key retrieval.
- High finding: reference upsert has a read-before-write race under concurrent bots.
- Medium finding: FIT_MAP stores caller-provided hash rather than a derived payload hash.
- Medium finding: malformed structured entries become opaque JSON strings instead of failing closed.
- Open gap: `get_current()` writes dimensions/objections but does not expose/load them.
- Ruling: add additive migration for logical/content hashes and translation history, provide current/version retrieval APIs, make reference upsert immediate and idempotent, derive payload hashes in the database, reject malformed normalized text, and expose all normalized FIT_MAP fields needed for recovery.

### Task 1.3: complete

- Final commit: `e92535b` (`Fix versioned persistence integrity and retrieval`), after fix round 1.
- Task review: fix round 1 passed; no material regression found.
- Evidence: focused analysis, SQLite migration, database and application repository tests passed 30/30 in the controller run; reviewer independently ran the relevant subset (17/17) with `OK`.
- Verification: reference versions are queryable by kind/logical key/content hash; upsert uses an immediate transaction; FIT_MAP and positioning payload hashes are derived from canonical persisted payloads; malformed required entries fail closed; dimensions and objections are reloaded; migration 005 is idempotent and checksum-integrated with legacy backfill coverage.

### Task 2.1: in progress

- Implementer: `Nietzsche` (`01a01582-2687-7f71-9581-4bcbc8e17c3b`).
- Scope: transactional, application-scoped gate receipts; registry enforcement; read-only SQLite-derived workflow projection; focused regression suite.
- Acceptance gate: independent review must confirm identity/fingerprint/hash binding, idempotence, FK/transaction behavior, fail-closed transitions, and absence of global JSON authority.
- Initial review: rejected. Findings: the new `WorkflowStateStore` constructor broke existing application-scoped callers; remaining runtime paths still call mutable/unscoped JSON store methods; and the default `run_id` was not unique per execution/application.
- Fix ruling: preserve compatible application-scoped construction while removing global authority, replace or explicitly fence remaining mutable callers, generate a unique execution run_id when omitted, and add regression tests for each repro before re-review.
- Fix round 1 review: rejected. Remaining regressions: arbitrary legacy/temp store paths were inferred as application IDs and the explicit global mirror path was ignored; CLI `reset-state`/`run-task` still used an unscoped store; and `project.py` still treated global `workflow_state.json` as live state.
- Fix round 2 ruling: constrain application inference to canonical `applications_v2/<id>` paths or explicit IDs, honor caller-provided compatibility mirror paths without making them authoritative, route CLI commands through explicit application scope/pointer handling, and remove global JSON reads from runtime diagnostics. Add regressions for all three paths.
- Fix round 2 review: rejected on one blocker: `workflow reset-state --application-id` left the active pointer intact, so a subsequent unscoped pipeline still reused the reset application.
- Fix round 3 ruling: clear the active pointer when it targets the reset application and add a reset-then-unscoped-run regression; preserve all prior compatibility fixes.
- Controller integration check found two compatibility regressions not visible in the isolated reviewer suite: canonical-shaped temporary application stores without a SQLite row raised during metadata-only reads, breaking legacy intake tests.
- Additional fix: unknown application on metadata-only `WorkflowStateStore.load()` now returns a neutral gate projection plus local intake/job metadata; gate/task operations remain fail-closed. Implementer commit: `99b0718`.

### Task 2.1: complete

- Final controller commits: `27d58a7`, `170e335`, `271605c`, `a966dc3`, `34aa7fa`, `8d4b3df`, `497ba0f`, `2b536f3` (the first four are the reviewed implementation/fix sequence; the remaining commits integrate controller-only compatibility and evidence corrections without staging unrelated user changes).
- Task review: PASS after independent gate-core review, three compatibility fix rounds, controller integration regressions, and final evidence-report review.
- Evidence: controller-targeted suite passed 61/61:
  `PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_intake_persistence tests.test_workflow_gates tests.test_linkedin_intake_metadata tests.test_sqlite_persistence tests.test_database tests.test_application_repository tests.test_analysis_revisions`.
- Acceptance result: receipts are application-scoped, idempotent and fail-closed; registered application projections are SQLite-authoritative; legacy/global JSON is non-authoritative; active-pointer and temporary-store compatibility reads are metadata-only; unscoped CLI reset/run paths cannot reuse a reset application; request summaries do not weaken gate/task validation.

### Task 2.2: in progress

- Initial implementer `Kuhn` (`01a015d3-614c-7263-a82c-6a995254136f`) stopped at the usage limit before producing a commit; no partial commit was accepted.
- Replacement implementer: `Hume` (`01a01649-80c3-7ce0-9034-ffd5f9705a4c`).
- Scope: immutable artifact provenance, path/content hashes, source revision/dependency binding, and review-output integration.
- Acceptance gate: independent review must confirm artifacts cannot be publishable without a valid source revision/review dependency and become invalid after path mutation; no artifact file alone may satisfy a gate.
- Implementer commit awaiting review: `d0729d8` (`Implement artifact provenance and review receipts`).
- Initial review: rejected. Finding: approved review reports did not carry/verify the reviewed artifact SHA-256, so replacing a DOCX at the same path could still publish a receipt for unreviewed bytes.
- Fix ruling: objective review must emit the artifact digest; SQLite opt-in provenance publication must require and compare it before creating the review receipt, with a post-review mutation regression. Legacy report-only mode may remain compatible but cannot publish to SQLite without the digest.
- Fix round 1 review: rejected. `CvReviewReportSchema` made `artifact_sha256` mandatory for legacy report-only callers, breaking `scripts/selftest_phases.py --phase 12` before its expected validation behavior.
- Fix ruling: keep the field optional in the legacy report schema, but require a valid current digest inside `record_approved_cv_provenance` and `mark_review_passed` before any SQLite publication.
- Fix round 2 review: PASS. Digest binding, mutation invalidation, legacy report-only compatibility, dependency/isolation behavior and migration 007 were independently verified; focused artifact tests 13/13, phase-12 selftest passed, and persistence suite 65/65.

### Task 2.2: complete

- Final commits: `d0729d8` (`Implement artifact provenance and review receipts`), `2879339` (`Bind review receipts to reviewed artifact bytes`), `39e93a6` (`Preserve legacy review reports without digest`).
- Task review: PASS after two independent review/fix rounds; controller integration completed without staging the pre-existing `scripts/review_output.py` change.
- Evidence in controller checkout: combined suite passed 74/74:
  `PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_artifact_provenance tests.test_workflow_gates tests.test_sqlite_persistence tests.test_database tests.test_application_repository tests.test_analysis_revisions tests.test_intake_persistence tests.test_linkedin_intake_metadata`.
  `PYTHONPATH=src ./scripts/python.sh scripts/selftest_phases.py --phase 12` returned `{"phase": 12, "status": "ok"}`.
- Acceptance result: artifact registration, dependency completeness, review receipts and current-byte hash validation are SQLite-backed and fail-closed; stale or mutated files cannot publish; legacy report-only validation remains compatible but cannot create SQLite provenance without a digest.

### Task 2.3: in progress

- Implementer: `Ohm` (`01a0165f-07c7-7121-a2d8-4f556394634d`).
- Scope: derive application stage, next action and compatibility projection exclusively from SQLite applications, receipts, revisions and artifact provenance.
- Acceptance gate: independent review must confirm legacy stage/JSON contradictions cannot advance a projection, file existence alone cannot close a package, and projections remain isolated by application_id.
- Implementer commit awaiting review: `46e389f` (`Derive application stages from SQLite provenance`).
- Initial review: rejected. Findings: raw `deliveries`/`notion_syncs` status rows with null hashes or no artifact linkage could seal the base package; tests encoded this shortcut.
- Fix ruling: add/consume verifiable delivery and Notion-sync receipts bound to the current approved artifact/revision, require report/hash/dependency integrity, and add regressions for status-only, missing-hash and stale-sync cases.
- Fix round 1 review: rejected. OneDrive report path/hash integrity was checked, but report JSON content was not semantically validated; arbitrary JSON with an updated hash could still seal the package.
- Fix ruling: parse and validate OneDrive receipt content against the current artifact version/id/hash and FIT_MAP/positioning revision IDs; add an integrity-valid-but-unrelated report regression.

### Task 2.3: complete

- Final commits: `46e389f` (`Derive application stages from SQLite provenance`), `562e629` (`Require verified delivery and sync receipts`), `7f1e1cd` (`Validate delivery receipt semantics before sealing`).
- Task review: PASS after two independent review/fix rounds; the final review verified semantic OneDrive/Notion receipt linkage and no status-only shortcut.
- Evidence: controller combined suite passed 86/86:
  `PYTHONPATH=src ./scripts/python.sh -m unittest -q tests.test_application_projection tests.test_artifact_provenance tests.test_workflow_gates tests.test_sqlite_persistence tests.test_database tests.test_application_repository tests.test_analysis_revisions tests.test_intake_persistence tests.test_linkedin_intake_metadata`.
- Acceptance result: stage/next action is SQLite-derived and application-scoped; stale JSON is observation-only; CV file presence does not advance state; current approved artifact, verified OneDrive receipt and semantically linked Notion receipt are all required to seal the base package.

## Phase 2 gate

- [x] Transactional, application-scoped gate receipts implemented and reviewed.
- [x] Artifact provenance, dependency validation and mutation invalidation implemented and reviewed.
- [x] SQLite-derived application projection implemented and reviewed.
- [x] Controller integration suite passed 86/86 without changing user-owned unrelated files.

### Task 3.1: in progress

- Scope: make intake and guard identity-first and SQLite-scoped, with explicit application/fingerprint validation before draft or derived-context writes.
- Acceptance gate: focused intake regressions, neighboring application/projection tests, independent review, and diff inspection must prove that global active pointers and JSON mirrors cannot select or authorize agent execution.
- Initial implementation `4938b59` and hardening `978c015` were independently reviewed and rejected. Required fixes: route operational persistence to `control-plane/career.db`; remove global-pointer fallback from resume/request/supervisor/CLI execution paths; add explicit CLI application/fingerprint propagation; validate active-intake identity; cover public intake entrypoints and make the evidence reproducible from tracked files.

### Task 3.1: correction round complete, awaiting independent re-review

- Correction commit: `def2e60` (`Fix task 3.1 canonical intake scope`).
- TDD evidence: seven focused regressions were run red before the correction (canonical database, public paste routing, unscoped resume/request, foreign active intake, CLI guard propagation, and supervisor resume/execution). The tracked controller subset then passed 63/63.
- Implementation: operational intake identity/source/description now uses `control-plane/career.db`; injected test/migration databases remain explicit exceptions. Agent execution now requires an application ID; guard also requires the matching fingerprint. Global pointers are discovery/display metadata only.
- Residual: the user-owned, untracked `tests/test_intake_persistence.py` still asserts the retired `.career-state/career.db` destination and therefore is intentionally excluded from correction evidence. It requires a separately authorized test migration, not a compatibility fallback in production code.

## Phase 0 gate

- [x] Read-only persistence inventory completed and reviewed.
- [x] Restorable backup created, narrowed to career recovery data, hash-verified and reviewed.
- [ ] Phase 0 full-suite/operational verification remains to be run after later code phases; no cutover is authorized yet.
- Additional observation: raw `-uu` inventory is broad but acceptable for Task 0.1 and remains documented as a later filtering concern.

### Task 0.2: complete

- Scope: created `scripts/backup_persistence.py` and `tests/test_persistence_backup.py` for a restorable baseline backup that uses the SQLite backup API and preserves legacy directories via hashed manifest entries.
- Evidence: focused suite `tests/test_persistence_backup.py` passed 2/2; dry-run reported `sqlite_database_count=6`, `preserved_directory_count=6`, `preserved_file_count=43092`; real backup completed with manifest at `/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2/manifest.json`.
- Backup path: `/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2`
- Ruling: the baseline scopes SQLite backup to `career.db` files in the career-state/control-plane domains, excluding unrelated browser/cache `.db` files discovered during the first live dry-run.

### Task 0.2: fix round 1 complete

- Scope correction: replaced broad `workspaces/` preservation with explicit include-only workspace roots (`inbox`, `outputs`, and selected `state/*` recovery directories) so browser/cache/home trees are not copied.
- Evidence: focused suite `tests/test_persistence_backup.py` passed 2/2 after the scope change; dry-run for the corrected backup reported `sqlite_database_count=6`, `preserved_directory_count=26`, `preserved_file_count=13838`; real narrow backup completed with manifest at `/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow/manifest.json`.
- Backup path: `/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow`
- Validation: the narrow manifest excludes `workspaces/vagas_bot_01/state/browser/linkedin/Default/Cookies`; the previous broad backup remains preserved and untouched.

### Task 0.2: fix round 2 complete

- Scope correction: preserved-file entries now record both `source_sha256` and `backup_sha256`, and the copy step aborts immediately if destination bytes diverge from the source hash.
- Evidence: focused suite `tests/test_persistence_backup.py` passed 3/3 after the hash-verification change; dry-run for the corrected backup reported `sqlite_database_count=6`, `preserved_directory_count=26`, `preserved_file_count=13841`; real narrow-v2 backup completed with manifest at `/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow-v2/manifest.json`.
- Backup path: `/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow-v2`
- Validation: live manifest spot-check confirmed `workspaces/vagas_bot_01/state/applications_v2/256/fit_map.json` is present, `workspaces/vagas_bot_01/state/browser/linkedin/Default/Cookies` is absent, and the checked root/workspace files both have matching source/destination hash pairs.
