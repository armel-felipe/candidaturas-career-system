# Controlled application handoff

Status: approved and implemented on 2026-08-14.

## Purpose

Move a canonical application from the operator intake state into one Hermes bot workspace so the next agent session can work from persisted files and a bounded SQLite cell request. The handoff is operational continuity; it is not conversational continuity.

## Source and target authority

- Source of truth: operator `.career-state/applications_v2/<application_id>/`.
- Target: only `vagas_bot_01` or `vagas_bot_02`, resolved from `deploy/hermes/compose.yaml`.
- Control plane: the shared `.career-control/career.db` resolved from that compose service.
- Ownership: the target service's `CAREER_HERMES_PROFILE_ID` is bound to the application with source `controlled_handoff`.
- An arbitrary target state path is not accepted by the command.

## Command contract

```bash
npm run applications:handoff -- \
  --application-id <id> \
  --target-bot vagas_bot_01 \
  --dry-run

npm run applications:handoff -- \
  --application-id <id> \
  --target-bot vagas_bot_01 \
  --apply
```

The default is dry-run. Apply is explicit. The command validates identity, LinkedIn job ID, required compact inputs, source fingerprint, target liveness, profile ownership, and control-plane consistency before projecting files.

## Projection boundary

The target receives only:

- `job_description.md`;
- `identity.json`;
- `fit_map.draft.json`;
- `derived/job_normalized.json`;
- `derived/handover_summary.json`;
- `derived/evidence_index.json`;
- generated `state.json`, `handoff_manifest.json`, one run plan, one cell manifest, and one bounded request.

The source is never modified. A stale target is moved to `.handoff_quarantine/` and is never deleted. Existing `fit_map.json`, old requests, old plans, CV artifacts, and unrelated outputs are not reused.

## Cell boundary

Apply registers one fresh `analyze_fit` cell as `reserved` for the selected bot, with all input hashes recorded in `cell_inputs` before execution. The request has explicit read/write allowlists and a 12,000-token target / 32,000-token hard context limit. It contains references and hashes, not the conversation transcript.

No model is called by the handoff. CV generation, Notion updates, Gmail, OneDrive, and external delivery are outside this change.

## Failure and recovery

- `dry-run`: no target file or control-plane row is written.
- identity/fingerprint mismatch: fail closed; inspect the operator source and rerun dry-run.
- stale target: inspect the timestamped quarantine directory; apply can be retried.
- live target attempt or active profile binding: stop and resolve ownership through the control-plane; do not use `chmod`, `chown`, or a private database as a workaround.
- repeated same fingerprint and bot: idempotent result; no duplicate run or cell.
- different bot or different fingerprint: conflict; requires an explicit operator decision and cleanup through the control-plane.
- SQLite permission/lock error: fix ownership or release the authoritative lease, then rerun dry-run.
