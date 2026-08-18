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
