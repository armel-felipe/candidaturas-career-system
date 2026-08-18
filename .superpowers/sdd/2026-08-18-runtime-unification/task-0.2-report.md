# Task 0.2 Report

## Scope

Implemented the restorable persistence backup baseline required by Task 0.2:

- Added `scripts/backup_persistence.py`
- Added `tests/test_persistence_backup.py`

The script now:

- exposes `create_backup(root: Path, destination: Path) -> dict`
- discovers career-runtime SQLite databases by `career.db` filename
- backs up each discovered SQLite database with the SQLite backup API
- preserves legacy runtime directories as copied files with SHA-256 entries in a manifest
- writes `manifest.json` in the backup destination with database hashes, copied file hashes, and preserved directory summaries
- supports `--dry-run` preview without writing the destination

## TDD Notes

Red:

- Created `tests/test_persistence_backup.py` before the helper existed.
- Initial focused test run failed because `scripts/backup_persistence.py` did not exist.

Green:

- Implemented the backup helper and CLI with the smallest behavior needed for the test:
  - SQLite backup API usage
  - preserved `.career-state` and `outputs` copies
  - manifest writing
  - dry-run preview

Runtime debug adjustment:

- The first live dry-run against the real repository failed with `sqlite3.DatabaseError: file is not a database`.
- Root cause: the initial implementation scanned every `*.db` file in the repo, but the runtime includes unrelated browser/cache/NSS databases outside the career persistence contract.
- Corrected the backup discovery to only include `career.db` files, which aligns with the migration design (`control-plane` plus legacy career-state databases) and avoids folding unrelated runtime caches into the baseline.

## Verification Commands

Executed exactly:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_persistence_backup.py
python3 scripts/backup_persistence.py --root . --destination /opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2 --dry-run
python3 scripts/backup_persistence.py --root . --destination /opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2
```

Observed results:

- Focused unit test command: `OK` with 2 tests
- Dry-run output:

```json
{"destination": "/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2", "preserved_directory_count": 6, "preserved_file_count": 43092, "sqlite_database_count": 6, "status": "dry_run"}
```

- Real backup output:

```json
{"destination": "/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2", "manifest": "/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2/manifest.json", "preserved_directory_count": 6, "preserved_file_count": 43092, "sqlite_database_count": 6, "status": "created"}
```

## Backup Status

Registered the backup path in `.superpowers/sdd/2026-08-18-runtime-unification/progress.md`.

Created baseline backup:

- `/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2`

Validated from the generated manifest:

- `manifest.json` exists
- `sqlite_database_count=6`
- `preserved_directory_count=6`
- `preserved_file_count=43092`
- first backed-up database in the live manifest: `.career-state/career.db`

## Self-Review

Reviewed the task diff for:

- read-only behavior against source databases and files
- use of the SQLite backup API instead of file copy for databases
- manifest completeness for source/backup hashes and preserved file hashes
- dry-run behavior that does not create the destination
- live-runtime safety after discovering unrelated `.db` files

No further code changes were required after the final verification run.

## Concerns

1. The baseline intentionally copies a large legacy footprint (`43092` preserved files), so the real backup command is materially slower than the focused test. That is acceptable for a one-time migration baseline, but later phases may want narrower operational snapshots on top of this full backup.
2. The scope currently treats `career.db` as the canonical SQLite naming convention for migration sources. If another legacy runtime stores career persistence in a differently named SQLite file, a later migration task will need to extend discovery explicitly rather than broadening back to arbitrary `*.db`.

## Fix Round 1

### Reviewer Finding

The backup scope was too broad because `PRESERVED_DIRECTORIES` included the entire `workspaces/` tree. In practice that pulled in non-career runtime files such as browser state and cache/home content. The original tests also did not prove that excluded paths stayed out of the backup or that copied file hashes matched destination bytes.

### Root Cause

The preservation policy was directory-root based instead of recovery-data based. Once `workspaces/` was treated as a preserved root, `_iter_preserved_files()` accepted any non-SQLite file beneath it. That allowed `state/browser/.../Cookies` and similar files to enter the manifest simply because they were regular files under the workspace tree.

### Fix Applied

- Removed broad `workspaces/` and `.career-control` preservation from the default preserved roots.
- Added an explicit include-only workspace policy for:
  - `workspaces/<bot>/inbox`
  - `workspaces/<bot>/outputs`
  - `workspaces/<bot>/state/applications_v2`
  - `workspaces/<bot>/state/applications`
  - `workspaces/<bot>/state/derived`
  - `workspaces/<bot>/state/memory`
  - `workspaces/<bot>/state/agent_requests`
  - `workspaces/<bot>/state/approvals`
  - `workspaces/<bot>/state/phase_d_gates`
  - `workspaces/<bot>/state/pending_actions`
  - `workspaces/<bot>/state/telegram`
- Added fixture coverage for a workspace recovery file plus excluded browser/cache paths.
- Added assertions that:
  - the recovery file is preserved,
  - the browser/cache paths are absent from the manifest,
  - copied destination files hash to the same SHA-256 recorded in the manifest.

### Fix-Round Verification

Executed exactly:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_persistence_backup.py
python3 scripts/backup_persistence.py --root . --destination /opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow --dry-run
python3 scripts/backup_persistence.py --root . --destination /opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow
```

Observed results:

- Focused unit test command: `OK` with 2 tests
- Narrow dry-run output:

```json
{"destination": "/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow", "preserved_directory_count": 26, "preserved_file_count": 13838, "sqlite_database_count": 6, "status": "dry_run"}
```

- Narrow real backup output:

```json
{"destination": "/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow", "manifest": "/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow/manifest.json", "preserved_directory_count": 26, "preserved_file_count": 13838, "sqlite_database_count": 6, "status": "created"}
```

- Manifest spot-check:

```json
{"manifest_exists": true, "preserved_directory_count": 26, "preserved_file_count": 13838, "sqlite_database_count": 6, "workspace_application_present": false, "workspace_browser_present": false}
```

### Outcome

The corrected backup no longer copies the whole workspace tree. It preserves only the explicitly allowed career recovery roots, keeps SQLite discovery restricted to `career.db`, leaves the prior broad backup untouched, and records hashes that match the copied destination bytes for preserved files covered by the focused test.

## Fix Round 2

### Reviewer Finding

The include-only workspace policy was accepted, but the copied-file hash verification was still incomplete in production. `create_backup()` recorded only the source-side hash for preserved files and relied on `copy2()` without recomputing destination bytes, so the manifest could report success without proving the copied file matched the source. The fix-round-1 report also included a manifest spot-check claiming `workspace_application_present=false`, which did not match the intended evidence path.

### Root Cause

The production copy path treated preserved files as a planning artifact rather than a verified backup artifact. `_build_report()` computed a single source hash before any copy, and `_copy_preserved_files()` never updated the entry with a destination hash or compared the copied bytes back to the recorded source hash. Separately, the fix-round-1 spot-check mixed fixture expectations with live-manifest evidence instead of reading an actual preserved workspace application path from the generated backup.

### Fix Applied

- Changed preserved-file manifest entries from a single `sha256` field to explicit `source_sha256`.
- Updated `_copy_preserved_files()` to recompute `backup_sha256` from the copied destination file after `copy2()`.
- Added a fail-closed guard: if `backup_sha256 != source_sha256`, the backup raises `ValueError` and does not write `manifest.json`.
- Extended the focused suite to assert:
  - manifest entries include `source_sha256` and `backup_sha256`,
  - source/destination hashes are equal for copied preserved files,
  - a deliberately corrupted copied file causes `create_backup()` to fail with `Copied file hash mismatch`.
- Re-ran the manifest spot-check against the real `narrow-v2` backup using an actual workspace application file present in the live manifest.

### Fix-Round Verification

Executed exactly:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_persistence_backup.py
python3 scripts/backup_persistence.py --root . --destination /opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow-v2 --dry-run
python3 scripts/backup_persistence.py --root . --destination /opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow-v2
python3 - <<'PY'
import json
from pathlib import Path
path = Path('/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow-v2/manifest.json')
payload = json.loads(path.read_text(encoding='utf-8'))
paths = {entry['path']: entry for entry in payload['preserved_files']}
workspace_candidates = [
    entry['path'] for entry in payload['preserved_files']
    if '/state/applications_v2/' in entry['path'] and not entry['path'].endswith('/.heartbeat.lock')
]
workspace_example = workspace_candidates[0] if workspace_candidates else None
root_example = '.career-state/application_alias_index.json'
print(json.dumps({
    'manifest_exists': path.exists(),
    'preserved_directory_count': payload['summary']['preserved_directory_count'],
    'preserved_file_count': payload['summary']['preserved_file_count'],
    'sqlite_database_count': payload['summary']['sqlite_database_count'],
    'workspace_application_example': workspace_example,
    'workspace_application_present': workspace_example in paths if workspace_example else False,
    'workspace_browser_present': 'workspaces/vagas_bot_01/state/browser/linkedin/Default/Cookies' in paths,
    'root_example_hash_pair_equal': paths[root_example]['source_sha256'] == paths[root_example]['backup_sha256'],
    'workspace_example_hash_pair_equal': paths[workspace_example]['source_sha256'] == paths[workspace_example]['backup_sha256'] if workspace_example else None,
}, ensure_ascii=False, sort_keys=True))
PY
```

Observed results:

- Focused unit test command: `OK` with 3 tests
- Narrow-v2 dry-run output:

```json
{"destination": "/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow-v2", "preserved_directory_count": 26, "preserved_file_count": 13841, "sqlite_database_count": 6, "status": "dry_run"}
```

- Narrow-v2 real backup output:

```json
{"destination": "/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow-v2", "manifest": "/opt/agent-projects/candidaturas-backups/runtime-unification-baseline-20260818-task-0.2-narrow-v2/manifest.json", "preserved_directory_count": 26, "preserved_file_count": 13841, "sqlite_database_count": 6, "status": "created"}
```

- Live manifest spot-check:

```json
{"manifest_exists": true, "preserved_directory_count": 26, "preserved_file_count": 13841, "root_example_hash_pair_equal": true, "sqlite_database_count": 6, "workspace_application_example": "workspaces/vagas_bot_01/state/applications_v2/256/fit_map.json", "workspace_application_present": true, "workspace_browser_present": false, "workspace_example_hash_pair_equal": true}
```

### Outcome

The backup now proves preserved-file integrity in production instead of only in tests: every copied preserved file recorded in the manifest has both source and destination hashes, and a mismatch aborts the backup before success is reported. The fix-round-1 evidence claim about workspace application presence is superseded by the live `narrow-v2` manifest check above, which uses a real preserved application file from the generated backup.
