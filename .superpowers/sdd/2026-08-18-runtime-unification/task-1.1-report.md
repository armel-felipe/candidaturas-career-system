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

## Fix Round 1

### Reviewer findings addressed

1. `Database.migrate()` previously ledgered only `001-003`, while `_initialize_schema()` still performed untracked compatibility `ALTER TABLE` upgrades for:
   - `resource_locks.lease_id`
   - `workspace_leases.lease_epoch`
   - `workspace_authority.storage_identity`
   - `workspace_authority.authority_epoch`
   - `workspace_authority.authority_ledger_id`
   - `workspace_authority.lease_epoch_counter`
   - `workspace_authority_handoffs.prior_authority_epoch`
   - `workspace_authority_handoffs.new_authority_epoch`
2. `tests/test_database.py` still encoded the pre-migration exact table list/count and was not executable by the required `unittest` runner because it depended on `pytest`.

### Changes made

- Added versioned Python migration `src/career/services/persistence/migrations/004_legacy_compatibility.py`.
- Extended `Database.migrate()` to:
  - discover both `.sql` and `.py` migrations by numbered filename;
  - checksum and ledger Python migrations exactly like SQL migrations;
  - dispatch Python handlers via `apply(conn)`.
- Removed the hidden compatibility `ALTER TABLE` block from `_initialize_schema()`.
- Added a legacy-schema regression in `tests/test_sqlite_persistence.py` that seeds pre-compatibility tables, runs only `migrate()`, verifies the compatibility columns exist, verifies `004_legacy_compatibility.py` is recorded in `schema_migrations`, and verifies the second `migrate()` call is idempotent.
- Reworked `tests/test_database.py` into `unittest.TestCase` form so the exact runner command executes it, and updated it to assert the consolidated required table set instead of the stale pre-migration list/count.

### Verification

Commands run:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_sqlite_persistence.py tests/test_database.py
```

Observed result:

```text
Ran 8 tests in 0.201s
OK
```

```bash
tmp_db=$(mktemp /tmp/runtime-unification-task11-fix1-XXXXXX.db)
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

### Self-review notes

- The compatibility upgrade path is now explicit and versioned in `schema_migrations`; `migrate()` alone is sufficient to materialize those legacy columns.
- `_initialize_schema()` still contains inline `CREATE TABLE IF NOT EXISTS` statements for authority/bootstrap compatibility, but it no longer hides schema evolution behind unledgered `ALTER TABLE` calls.
- `control-plane/career.db` was not migrated or mutated during this fix round.

## Fix Round 2

### Reviewer finding addressed

- `Database.migrate()` was hashing raw migration bytes, so identical migration content checked out with `LF` versus `CRLF` line endings could trigger a false `migration checksum mismatch`.

### Changes made

- Added `Database._migration_checksum(path)` and routed `migrate()` through it.
- Normalized migration bytes from `CRLF` to `LF` before computing the checksum for both `.sql` and `.py` migrations.
- Kept migration execution unchanged: SQL still executes from the file text as read, and Python migrations still load and execute the file module itself.
- Added focused regressions in `tests/test_sqlite_persistence.py` for:
  - equal checksums across LF/CRLF variants of `.sql` and `.py` migration files;
  - no false drift when an already-applied SQL migration file is rewritten with CRLF-only line-ending changes.

### Verification

Commands run:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_sqlite_persistence.py tests/test_database.py
```

Observed result:

```text
Ran 10 tests in 0.281s
OK
```

```bash
tmp_db=$(mktemp /tmp/runtime-unification-task11-fix2-XXXXXX.db)
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

### Self-review notes

- The checksum normalization is deliberately limited to line-ending normalization (`CRLF -> LF`), so it removes checkout-style portability drift without weakening checksum sensitivity to substantive content changes.
- `control-plane/career.db` was not opened for migration or mutated during this fix round.
