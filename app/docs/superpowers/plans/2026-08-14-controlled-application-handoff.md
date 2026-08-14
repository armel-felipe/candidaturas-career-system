# Controlled Application Handoff Implementation Plan

> **Execution note:** This plan is intended to be executed with the `executing-plans` skill, one task at a time, with tests run at each checkpoint.

**Goal:** Create a canonical, auditable command that projects a validated operator-side application record into exactly one bot workspace and registers a bounded `analyze_fit` cell without relying on conversational context or triggering downstream side effects.

**Design:** Add an `ApplicationHandoffService` behind `applications:handoff`. It resolves the target bot from the canonical Hermes compose file, validates the source application and compact input contract, quarantines a stale target application directory when safe, copies only canonical inputs, registers the application/run/cell/input/event in the shared control-plane, and stops before model execution. `--dry-run` is mandatory unless `--apply` is explicit. The command never accepts an arbitrary target state path.

**Tech stack:** Python 3, existing `Database`, `CellStore`, `CellExecutor`/cell contracts, existing compose target resolver, pytest, npm wrappers.

## Global constraints

- Preserve unrelated pre-existing changes and runtime artifacts.
- Use the canonical source skill and project paths; do not create parallel skill directories.
- Never modify the operator/root source application during handoff.
- Never delete a stale target. Quarantine it under the target workspace with an application-specific timestamped directory.
- Do not read or copy `.env`, credentials, tokens, Notion data, CV output, Gmail data, or OneDrive data.
- Do not reuse `fit_map.json`, old run plans, old requests, or old artifacts from a stale target.
- A successful apply must be idempotent for the same source fingerprint and target bot, and must fail closed for a conflicting live handoff.
- Tests must use temporary source/target/control-plane directories and must not mutate the real iFood application before the final explicit apply checkpoint.

## Task 1: Add failing service-level tests for source validation and dry-run safety

**Files:**
- Create: `app/tests/test_application_handoff.py`

1. Add fixtures that create a minimal canonical application source with `identity.json`, `job_description.md`, `fit_map.draft.json`, and the required compact derived JSON files.
2. Add a test named `test_dry_run_reports_projection_without_mutating_target_or_control_db` that creates a stale target fixture, executes the not-yet-existing service in dry-run mode, and asserts:
   - result is dry-run;
   - source fingerprint and file manifest are reported;
   - target fixture remains byte-for-byte unchanged;
   - target control DB has no application, run, cell, input, or handoff event rows.
3. Add a test named `test_apply_quarantines_stale_target_and_projects_only_canonical_inputs` that initially fails because the service does not exist. Assert the stale target is moved to quarantine, canonical files are present, stale files are absent, source files are unchanged, and ownership/mode normalization is applied to the projected tree.
4. Add a test named `test_apply_rejects_identity_or_source_fingerprint_mismatch` covering an identity application-id mismatch and a source URL/job-id mismatch. Assert no target mutation and no DB mutation.
5. Run only this test file and confirm the failures are feature-missing failures rather than import or fixture errors.

## Task 2: Add failing tests for duplicate protection, bot resolution, and bounded cellular registration

**Files:**
- Modify: `app/tests/test_application_handoff.py`

1. Add a temporary compose fixture with both `vagas_bot_01` and `vagas_bot_02`, distinct state roots, profile IDs, and one shared control DB.
2. Add `test_target_bot_is_resolved_from_canonical_compose_and_arbitrary_state_path_is_not_allowed`.
   - Assert both approved bot names resolve through the existing compose resolver.
   - Assert an arbitrary `--target-state-root`-style input is not part of the service API.
3. Add `test_same_fingerprint_handoff_is_idempotent_and_conflicting_live_handoff_fails`.
   - First apply succeeds.
   - Repeating the same handoff does not duplicate the application/run/event or copy stale state over the target.
   - A live conflicting handoff for the same application to the other bot is rejected with a clear fail-closed error.
4. Add `test_apply_registers_input_manifest_and_one_analyze_fit_cell`.
   - Assert the DB has one application, one run, one `analyze_fit` node, one cell input manifest, one bounded cell request, and one `controlled_handoff_prepared` event.
   - Assert the request references the target application and canonical compact inputs, has explicit read/write allowlists, and contains no full conversation transcript.
   - Assert there are no rows or events for CV, Notion, Gmail, OneDrive, or downstream generation.
5. Run the focused test file and confirm all new tests fail for the intended missing behavior.

## Task 3: Implement the handoff service with explicit dry-run/apply boundaries

**Files:**
- Create: `app/src/career/services/application_handoff.py`
- Modify: `app/src/career/services/__init__.py` only if required by package conventions

1. Define typed result/error structures for `dry_run`, `applied`, `idempotent`, and `rejected` outcomes.
2. Resolve `CanaryTarget` exclusively from the canonical compose path and restrict target names to `vagas_bot_01` and `vagas_bot_02`.
3. Resolve the source application directory from the explicit application ID and source root, defaulting to the operator-side canonical `.career-state/applications_v2` location only when the caller does not supply a source root.
4. Validate:
   - exact application ID in directory, identity, and source metadata;
   - non-empty company, role, source URL, and LinkedIn job ID consistency;
   - required source files and JSON validity;
   - required compact derived files and bounded total projected payload;
   - job description SHA-256 fingerprint;
   - no active conflicting handoff, cell attempt, or workspace lease.
5. Build a projection manifest before any write. The manifest must list every copied path, source hash, target path, target bot, source fingerprint, and run ID.
6. For dry-run, return the manifest and planned quarantine path without changing files or the control-plane.
7. For apply:
   - acquire the shared DB transaction/lock before target mutation;
   - revalidate the source fingerprint and target state;
   - quarantine only a stale target fixture that is not live;
   - create the target application directory and copy only `job_description.md`, `identity.json`, `fit_map.draft.json`, and the explicit compact derived JSON allowlist;
   - normalize projected ownership/modes to the target state owner without touching unrelated files;
   - write a fresh `state.json`/manifest with source fingerprint and handoff metadata;
   - insert/update the application row, profile binding, run, one `analyze_fit` node, cell input manifest, bounded request, and workflow event atomically where the existing stores permit;
   - leave execution pending for the selected bot; do not call a model or downstream deliverable handler.
8. Use existing database/cell/request primitives instead of duplicate schemas. If an existing primitive requires a workspace lease for preparation, create only the short-lived preparation lease and release it before returning; do not leave the operator holding the bot’s runtime lease.
9. Ensure repeated apply with the same fingerprint returns idempotent success and does not duplicate rows or overwrite a live target.

## Task 4: Add the canonical CLI/npm entry point

**Files:**
- Modify: `app/src/career/cli.py`
- Modify: `app/package.json`
- Modify: `package.json`

1. Add `applications handoff` arguments:
   - required `--application-id`;
   - required `--target-bot` with the two approved bot names;
   - optional `--source-root` and `--compose` for controlled operator/test fixtures;
   - mutually exclusive `--dry-run` and `--apply`, defaulting to dry-run when neither is present;
   - JSON/human output selection consistent with existing applications commands.
2. Dispatch to `ApplicationHandoffService` using the shared control DB resolved from the compose target, not a target-private DB.
3. Return non-zero on validation, conflict, permission, or DB failure. Never silently fall back to a stale target, alternate DB, legacy non-cellular path, or arbitrary directory.
4. Add `applications:handoff` npm wrappers using the project’s existing Python launcher conventions.
5. Run the CLI help and dry-run fixture test before any real application.

## Task 5: Add architecture/governance records and scope-change control

**Files:**
- Create: `app/docs/architecture/controlled-application-handoff.md`
- Create: `app/docs/architecture/architecture-implementation-register.md`
- Create: `app/docs/architecture/scope-change-log.md`
- Modify: `app/docs/superpowers/specs/2026-08-14-controlled-application-handoff-design.md` only if implementation decisions differ materially

1. Document the approved architecture, command contract, source-of-truth boundaries, ownership model, no-side-effect boundary, and failure modes.
2. Add an implementation register mapping approved components to implementation status, file paths, tests, and commit identifiers.
3. Add a scope-change log entry for the handoff command, explicitly recording that model execution and downstream deliverables remain out of scope for this change.
4. Include operational recovery steps for stale target quarantine, duplicate handoff, permission failure, and DB lock failure.

## Task 6: Run verification in increasing scope

**Files:**
- No additional source files; test reports may be written under `outputs/_tmp/` only when existing project commands require them.

1. Run the new focused test file.
2. Run the existing Phase D/runtime/application tests and any CLI tests touched by the change.
3. Run the full relevant Python test suite from the project’s documented command, excluding unrelated known dirty artifacts only if the suite itself requires it.
4. Run `npm run applications:handoff -- --help`.
5. Run a real iFood dry-run against `local_20260814T140734_089948_ifood_f2c7bd48` targeting `vagas_bot_01`; verify no source, target, or DB mutation.
6. Apply the real iFood handoff only after the dry-run manifest matches the intended source and target. Verify target files, permissions, DB records, request bounds, and the absence of downstream side effects.
7. Run the existing control-plane and bot health checks from both containers, then report the exact handoff run/cell IDs and the next bot session action.

## Task 7: Review, commit, and hand off

1. Review the diff for accidental changes to pre-existing dirty files and runtime artifacts.
2. Run `git diff --check` and inspect the final status.
3. Commit only the handoff implementation, tests, documentation, and package/CLI changes; do not stage unrelated user changes or generated runtime artifacts.
4. Use the verification-before-completion skill before claiming the handoff is complete.
5. Report what was implemented, what was actually applied to iFood, exact verification evidence, and what the fresh bot session should do next.
