# Task 9 / Recovery Slice E report

## Status

Implementation, consolidated broad-review hardening, and objective validation complete; final integration remains with the controller.

## Implemented

- Added a SQLite-backed `WorkspaceLease` with acquire, heartbeat, owner-checked release, expiry takeover, and immutable takeover history recording prior owner/expiry.
- Added a persistent random `control_db_id`; cross-owner expired takeover requires matching `CAREER_CONTROL_DB_ID`, while a different physical SQLite copy is rejected by identity.
- Fenced cellular `CellExecutor`, CLI migration, harness execution, and agent heartbeat work by workspace owner while allowing multiple applications under one owner.
- Made `applications:agent-heartbeat` cellular by default and concurrent through a bounded per-application worker pool; retained legacy non-cellular compatibility only through explicit `--legacy-non-cellular`.
- Added cellular `analyze_fit` preparation: the executor reserves an immutable attempt, the harness receives exact manifest allowlists and selected model/variant, and transient runner failures return `awaiting_agent` instead of blocking on a missing draft.
- Added conservative legacy migration through `scripts/migrate_cellular_runs.py`; source artifacts are only inventoried/hashed, actual DOCX plus reviewer/polish/approval/registry hashes are required, and imported runs/nodes/attempts/artifacts/manifests are resumable by the executor.
- Added real two-subprocess verification on one temporary SQLite/workspace, including distinct fingerprints/runs/manifests/artifacts, crossed-path detection, and serialized declared `notion-write` locks.
- Added `applications:migrate-cellular` and `applications:verify-parallel` CLI/npm aliases.
- Enforced complete cellular request identity/capability envelopes across multiagent and harness paths; request allowlists must be exact subsets of immutable manifest capabilities, and cellular harness outputs never union legacy/global output fields.
- Updated only canonical operational instruction files (`AGENTS.md` and `.agents/skills/career-system/SKILL.md`) after structural pressure tests demonstrated the missing rules.

## TDD evidence

- Initial focused RED: 3 collection errors (missing `WorkspaceLease`, migration module, and parallel harness).
- Heartbeat RED: 2 failures for missing cellular/default-vs-legacy behavior.
- Harness allowlist RED: 1 failure because cellular `write_allowlist` was not consumed.
- Documentation RED: canonical rule assertion failed before the docs were edited.
- Hardening RED: 6 failures covering same-owner expired takeover audit, long-handler keepalive, cellular-only rules/global postprocess, and observed external-lock contention.
- Consolidated review RED: 4 heartbeat/allowlist failures, 2 migration failures, 3 dry-run/authority failures, 1 schema failure, and 1 documentation contract failure.
- Final focused GREEN: `29 passed`.

## Validation evidence

- `pytest -q tests/test_cell_workspace_safety.py tests/test_cell_migration.py tests/test_cell_parallel_integration.py tests/test_database.py` → `29 passed`.
- `pytest -q` → `228 passed`.
- `./scripts/python.sh scripts/career_cli.py project validate-structure` → `Project structure validation passed.`
- `applications verify-parallel --fixture-dir /tmp/cellular-verify.VT1ffU` → `status=validated`, 2 subprocesses, distinct fingerprints/manifests, no crossed paths, contention observed (`8` failed acquisitions), external `notion-write` intervals serialized.
- `npm run runtime:diagnose` → exit 0 and report at `outputs/_tmp/runtime_diagnosis.json`; no cellular blocker. Environment inventory still reports LibreOffice unavailable and two pre-existing large reference files.
- No real Notion, Gmail, LinkedIn, OneDrive, or other external writes were executed. `.inbox/` was not changed.

## Files and compatibility

Legacy non-cellular paths remain available only when explicitly selected. The untracked `.inbox/` directory pre-existed this slice and was left untouched/uncommitted.
