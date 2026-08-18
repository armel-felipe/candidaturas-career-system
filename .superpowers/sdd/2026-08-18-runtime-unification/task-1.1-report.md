# Task 1.1 Report — SQLite schema and migration foundation

## Scope executed

- Modified `src/career/services/database.py`
- Created `src/career/services/persistence/migrations/001_application_revisions.sql`
- Created `src/career/services/persistence/migrations/002_analysis_and_positioning.sql`
- Created `src/career/services/persistence/migrations/003_gates_artifacts_integrations.sql`
- Created `tests/test_sqlite_persistence.py`

No other task files were modified.

## Requirements covered

1. Added `Database.migrate() -> int`
   - Applies numbered SQL migrations in lexical order.
   - Creates and records `schema_migrations(version, checksum, applied_at)`.
   - Detects checksum drift on already-applied versions.

2. Added `Database.configure_for_runtime() -> None`
   - Enables `foreign_keys`.
   - Sets `journal_mode=WAL`.
   - Sets `busy_timeout=10000`.
   - Sets `synchronous=FULL`.

3. Preserved compatible cellular schema while adding unification tables
   - Preserved/created: `application_runs`, `artifacts`, `workflow_events`, `validation_receipts`, `cell_requests`, `cell_inputs`, `cell_handovers`, `runtime_workers`, `runtime_runs`, `runtime_observations`, `profile_application_bindings`, and existing authority/lease tables.
   - Added foundation tables for unification: `application_aliases`, `application_revisions`, `job_sources`, `job_descriptions`, `job_sections`, `fit_map_revisions`, `positioning_revisions`, `gate_dependencies`, `artifact_versions`, `artifact_contents`, `notion_records`, `notion_syncs`, `deliveries`, plus related normalized tables.

4. Preserved atomic transaction behavior
   - Focused test verifies rollback removes both application and alias rows on exception.
   - Focused test verifies foreign key enforcement rejects alias insertion without the parent application.

## TDD evidence

### Red

Command:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_sqlite_persistence.py
```

Observed failure:

- `AttributeError: 'Database' object has no attribute 'migrate'`

This confirmed the new API and schema contract were missing before implementation.

### Green

Command:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_sqlite_persistence.py
```

Observed result:

```text
Ran 3 tests in 0.060s
OK
```

## Verification run

### Temporary database integrity check

Command:

```bash
tmp_db=$(mktemp /tmp/runtime-unification-task11-XXXXXX.db)
TASK11_DB="$tmp_db" PYTHONPATH=src ./scripts/python.sh - <<'PY'
import os
from career.services.database import Database

db = Database(db_path=os.environ["TASK11_DB"])
db.migrate()
db.close()
PY
TASK11_DB="$tmp_db" PYTHONPATH=src ./scripts/python.sh -c 'import os, sqlite3; c = sqlite3.connect(os.environ["TASK11_DB"]); print(c.execute("PRAGMA integrity_check").fetchone()[0]); print(c.execute("PRAGMA foreign_key_check").fetchall())'
```

Observed result:

```text
ok
[]
```

### Read-only validation against `control-plane/career.db`

Validation performed with a read-only SQLite connection (`mode=ro`) against the real control-plane DB. The check confirmed that each preserved compatibility table exists in the live schema and that every live column for those preserved tables is present in the migrated temporary database.

Observed result:

```text
read_only_schema_validation=ok
```

## Notes from self-review

- `init_schema()` now calls `migrate()` first so the consolidated schema becomes the runtime baseline instead of leaving migrations unused.
- Existing inline schema creation remains in place and is still idempotent because it uses `CREATE TABLE IF NOT EXISTS`; this keeps authority bootstrap behavior intact while moving the canonical contract into numbered migrations.
- The real `control-plane/career.db` was only opened in read-only mode during validation and was not migrated or mutated.

## Concerns

- There is at least one older repository test (`tests/test_database.py`) that hard-codes the pre-migration table list/count for `init_schema()`. It was intentionally not modified because it is outside Task 1.1 scope and was not part of the focused test command. If the broader suite is run later, that expectation likely needs to be updated to the consolidated schema contract.
