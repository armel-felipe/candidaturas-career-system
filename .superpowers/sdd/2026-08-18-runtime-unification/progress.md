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
