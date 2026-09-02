# Cellular Runtime Permission Repair Design

**Date:** 2026-09-02
**Roadmap:** `RUNTIME-023`, `RUNTIME-024`, `HARNESS-018`

## Problem

`vagas_bot_01` reaches a cellular continuation with a FIT_MAP but cannot
reliably hand the work to the CV/Notion pipeline. The active Hermes container
uses an older copy of `hermes-src`, where a shell-hook response with
`action=block` is treated as context-only. Independently, the mounted bot
state contains historical `root:root` files with mode `0600`; the global
Harness workspace snapshot reads those files and fails under UID `10000`.

The current compatibility pointer is also stale (`sqlite_only_restart` has no
application directory). A continuation without explicit application scope is
therefore blocked by design, but the old Hermes runtime does not enforce that
block and the model continues directly.

## Required outcomes

1. Every active bot container runs the current approved Hermes source.
2. `pre_llm_call` with `action=block` stops the model/tool turn.
3. Bot01 state needed by the runtime is owned and readable by `10000:10000`;
   content hashes remain unchanged.
4. Archival and ephemeral transport state cannot break a scoped preflight.
5. A continuation always carries explicit `application_id` and `run_id`.
6. The existing Rappi run is inspected and resumed through official commands;
   no SQLite, FIT_MAP, provenance, DOCX, or Notion record is edited manually.
7. CV approval and Notion synchronization are only reported after their
   existing objective gates pass.

## Non-goals

- Do not reset or delete the candidature history.
- Do not alter `.env` credentials or the read-only canonical source mount.
- Do not overwrite the user's uncommitted harness changes.
- Do not bypass the maintenance clean-checkout gate.
