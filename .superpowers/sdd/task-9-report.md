# Task 9 / Recovery Slice E report

## Status

Re-review independente não aprovada; correções adicionais estão em implementação e este relatório ainda não representa aprovação final.

## Implemented

- Added a SQLite-backed `WorkspaceLease` with acquire, heartbeat, owner-checked release, expiry takeover, and immutable takeover history recording prior owner/expiry.
- Added a persistent random `control_db_id` bound to the current physical DB storage; every production cellular entrypoint requires a matching `CAREER_CONTROL_DB_ID`, a byte-copied DB is rejected before maintenance/queue work, and an explicit audited `applications:authorize-handoff` is required after release/expiry to bind a destination copy.
- Fenced cellular `CellExecutor`, CLI migration, harness execution, and agent heartbeat work by workspace owner while allowing multiple applications under one shared effective owner; keepalive now spans validators, publication, and terminal commit.
- Made `applications:agent-heartbeat` cellular by default and concurrent through a bounded per-application worker pool; retained legacy non-cellular compatibility only through explicit `--legacy-non-cellular`.
- Added cellular `analyze_fit` preparation: the executor reserves an immutable attempt, the harness receives exact manifest allowlists and selected model/variant, stale/failed drafts are quarantined, successful drafts are bound to the current application/run/attempt/job hash, and transient runner failures return `awaiting_agent`.
- Made `Reprocessar` refresh the persisted job once and consume a durable reprocess marker; recovery detects a run created before a marker-link crash and attaches the marker instead of creating a duplicate.
- Added conservative legacy migration through `scripts/migrate_cellular_runs.py`; source artifacts are only inventoried/hashed, the real reviewer `artifact` + `_approval_meta`/polish/registry chain is recognized without inventing an approval schema, and atomic temp+fsync+replace receipts reconcile SQLite deterministically after crashes or truncated manifests.
- Added real two-subprocess verification on one temporary SQLite/workspace, including distinct fingerprints/runs/manifests/artifacts, expanded crossed-path/write detection, and serialized `notion-write` acquired by the real `sync_notion_initial` node from `CellContract.resources`.
- Added `applications:migrate-cellular`, `applications:authorize-handoff`, and `applications:verify-parallel` CLI/npm aliases.
- Enforced complete cellular request identity/capability envelopes across multiagent and harness paths; request allowlists must be exact subsets of immutable manifest capabilities, and cellular harness outputs never union legacy/global output fields.
- Made the executor consume the FIT_MAP draft binding before the handler and quarantine mismatched application/run/node/attempt/job/draft/manifest data; workspace fence ownership is rechecked through validators, publication rollback, and the terminal SQLite transaction.
- Expanded harness isolation to immutable request-control files and semantic snapshots of authoritative SQLite tables, including fail-closed reporting when the DB is corrupted.
- Updated only canonical operational instruction files (`AGENTS.md` and `.agents/skills/career-system/SKILL.md`) after structural pressure tests demonstrated the missing rules.

## TDD evidence

- Initial focused RED: 3 collection errors (missing `WorkspaceLease`, migration module, and parallel harness).
- Heartbeat RED: 2 failures for missing cellular/default-vs-legacy behavior.
- Harness allowlist RED: 1 failure because cellular `write_allowlist` was not consumed.
- Documentation RED: canonical rule assertion failed before the docs were edited.
- Hardening RED: 6 failures covering same-owner expired takeover audit, long-handler keepalive, cellular-only rules/global postprocess, and observed external-lock contention.
- Consolidated review RED: 4 heartbeat/allowlist failures, 2 migration failures, 3 dry-run/authority failures, 1 schema failure, and 1 documentation contract failure.
- Re-review RED: `11 failed, 26 passed`, covering explicit control-DB authority, long-validator keepalive, migration reconciliation/crash retry/real legacy schema, draft freshness, harness scope, real executor-managed external locks, and truthful status.
- Full-suite compatibility RED: 7 old CLI tests omitted the now-required temporary control-DB identity; fixtures were corrected without relaxing production fencing.
- Additional reprocess RED: a persistent `Reprocessar` status created a fresh run on every heartbeat; the consumed marker now makes the second heartbeat resume the first new run.
- Final independent-review RED: `9 failed, 31 passed`, covering copied-DB fencing, pre-maintenance authority, distinct production owners, validator/commit lease loss, draft binding, reprocess crash recovery, DB/request-control writes, real review schema and truncated migration receipts.
- Additional REDs covered the explicit handoff CLI/npm alias, process-distinct default owner, terminal workspace-fence validation, and corrupted SQLite isolation reporting.
- Final focused GREEN: `52 passed`.

## Validation evidence

- `pytest -q tests/test_cell_workspace_safety.py tests/test_cell_migration.py tests/test_cell_parallel_integration.py tests/test_database.py` → `52 passed`.
- `pytest -q` → `251 passed`.
- `./scripts/python.sh scripts/career_cli.py project validate-structure` → `Project structure validation passed.`
- `applications verify-parallel --fixture-dir /tmp/cellular-final-review.VtW8Zg` → `status=validated`, 2 subprocesses, distinct fingerprints/manifests, no crossed paths or unexpected writes, contention observed (`8` deferred acquisitions), and executor-managed `notion-write` intervals serialized.
- `npm run runtime:diagnose` → exit 0 and report at `outputs/_tmp/runtime_diagnosis.json`; no cellular blocker. Environment inventory still reports LibreOffice unavailable and two pre-existing large reference files.
- No real Notion, Gmail, LinkedIn, OneDrive, or other external writes were executed. `.inbox/` was not changed.

## Files and compatibility

Legacy non-cellular paths remain available only when explicitly selected. These are candidate gates pending a new independent re-review, not approval. The untracked `.inbox/` directory pre-existed this slice and was left untouched/uncommitted.
