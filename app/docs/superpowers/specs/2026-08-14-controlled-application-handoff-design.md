# Controlled Application Handoff Design

**Date:** 2026-08-14  
**Status:** approved for implementation  
**Baseline:** `ARCH-DATA-ANCHORED-2026-08-13`

## Goal

Provide one canonical, auditable operation that transfers a locally captured
application from the operator-owned read-only state into one worker's writable
workspace and creates the first eligible cellular stage. The operation must
work for both `vagas_bot_01` and `vagas_bot_02` without manual file copying or
conversation-dependent steering.

## Problem

The iFood intake exists in the operator state, while the worker state contains a
same-named synthetic `Operations Lead` fixture. The shared SQLite control plane
is now writable, but no current command projects a canonical intake into a
worker state, records the handoff, and creates `analyze_fit`. Starting a fresh
chat session alone would therefore preserve the state mismatch.

## Decision

Add a canonical `applications:handoff` command with a mandatory dry-run/apply
boundary. The operator supplies an application ID and a target bot. The command
resolves the target state root from the canonical Compose configuration and
never accepts an arbitrary worker path.

The handoff will:

1. read the source application directory without modifying it;
2. validate the application identity, source URL, source fingerprint and
   required input files;
3. reject a target directory whose source fingerprint does not match, unless it
   is first quarantined as stale;
4. project only the inputs required by `analyze_fit` (`job_description.md`,
   `identity.json`, `fit_map.draft.json` and compact `derived/` inputs);
5. preserve any stale target directory under a timestamped quarantine path;
6. register the application, run, input manifest, cell request and handoff event
   in the shared control plane;
7. assign the first cell to the selected worker and leave it ready for a fresh
   runner session.

The bot consumes the persisted cell request. It does not choose the source,
copy files, repair permissions, or create its own handoff.

## Safety and failure behavior

- `--dry-run` performs all identity, path, permission, fingerprint, lease and
  stale-target checks without changing source, target or SQLite state.
- `--apply` refuses to proceed if the source fingerprint changes after the
  dry-run, if a live lease/attempt exists, or if the target cannot be written by
  the worker UID.
- A stale target is moved to quarantine, never deleted.
- The source root remains read-only to workers.
- The command fails closed on missing input, identity mismatch, duplicate active
  handoff, or control-plane write failure.
- No Notion, CV, Gmail, OneDrive or external side effect is part of this first
  handoff. Only the `analyze_fit` cell is prepared.

## Data contract

The handoff identity contains:

```json
{
  "application_id": "...",
  "source_fingerprint": "sha256:...",
  "source_url": "...",
  "target_bot": "vagas_bot_01",
  "target_state_root": "...",
  "node_id": "analyze_fit",
  "contract_version": "1"
}
```

The SQLite record is authoritative for the handoff. The projected files are
content-addressed inputs referenced by `cell_inputs`; the generated request is
a bounded projection, not a replacement for the database record.

## Alternatives rejected

### New conversation session

Rejected because it removes conversational history but does not repair the
source/state mismatch or create an authorized cell.

### Manual file copy

Rejected because it bypasses fingerprints, quarantine, SQLite input registration
and worker authority.

### Notion queue insertion

Rejected for this operation because it adds an external side effect and does not
solve local intake handoffs between arbitrary worker state roots.

## Verification

The implementation must prove:

- dry-run is mutation-free;
- a valid iFood handoff projects the canonical fingerprint, not the fixture;
- stale `Operations Lead` state is quarantined and never reused;
- duplicate/live handoffs are rejected;
- both bot targets resolve to their own writable state roots;
- the shared SQLite contains inputs and an eligible `analyze_fit` cell before
  any agent process starts;
- the resulting request is bounded and passes the existing request guards;
- the existing cellular and Phase D regression suites remain green.

