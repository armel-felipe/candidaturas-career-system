# Task 1.3 Report — Versioned Analysis, Positioning, and Reference Repositories

Date: 2026-08-18
Commit baseline: `3965afb`
Status: implemented and locally verified

## Scope executed

Implemented only the files requested by the brief:

- `src/career/services/persistence/analysis_repository.py`
- `src/career/services/persistence/reference_repository.py`
- `tests/test_analysis_revisions.py`

No migrations were changed. No writes were made to `control-plane/career.db`; all verification used temporary SQLite databases created by the tests.

## TDD record

### RED

Created `tests/test_analysis_revisions.py` first, covering:

1. two immutable FIT_MAP revisions for the same `application_id`
2. normalized stories/keywords/evidence with preserved payload snapshot
3. positioning snapshot versioned off a source FIT_MAP revision
4. reference versioning by content hash with raw content preserved
5. derived candidate facts/evidence and keyword translations populated from JSON references

Initial failing command:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_analysis_revisions.py
```

Observed failure:

- `ModuleNotFoundError: No module named 'career.services.persistence.analysis_repository'`

### GREEN

Implemented:

- `AnalysisRepository.create_revision(...)`
- `AnalysisRepository.get_current(...)`
- `AnalysisRepository.create_positioning_revision(...)`
- `ReferenceRepository.upsert_version(...)`

Key behaviors delivered:

- FIT_MAP revisions are append-only rows in `fit_map_revisions`
- normalized queryable rows are inserted into:
  - `fit_map_dimensions`
  - `fit_map_keywords`
  - `fit_map_evidence`
  - `fit_map_objections`
  - `fit_map_stories`
  - `fit_map_scores`
- positioning snapshots are append-only rows in `positioning_revisions`
- normalized positioning rows are inserted into:
  - `positioning_stories`
  - `positioning_principles`
- raw reference content is preserved in `reference_documents`
- reference version identity is derived from `key + sha256(content)`
- candidate JSON references populate `candidate_facts` and `candidate_evidence`
- keyword translation JSON references populate `keyword_translations`

### REFACTOR / review notes

- Kept the implementation repository-local and schema-compatible with migration `002_analysis_and_positioning.sql`
- Did not add a new migration even though `reference_documents` lacks a dedicated history table; versioning is encoded at repository level through `reference_key = <key>#<content_hash>`
- Used `reference_id` in derived translation rows (`<reference_id>:<canonical_keyword>`) to preserve version distinction without mutating schema

## Verification evidence

Focused Task 1.3 tests:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_analysis_revisions.py
```

Result:

```text
Ran 3 tests in 0.080s
OK
```

Relevant existing schema/resolver regressions:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_sqlite_persistence.py tests/test_application_repository.py
```

Result:

```text
Ran 19 tests in 0.756s
OK
```

## Files changed

- `src/career/services/persistence/analysis_repository.py`
- `src/career/services/persistence/reference_repository.py`
- `tests/test_analysis_revisions.py`

## Known limitations kept inside scope

- `ReferenceRepository` does not introduce a retrieval API because the brief only required `upsert_version(...)`
- `keyword_translations` stores a version-qualified keyword key to preserve multiple versions without a schema change
- candidate reference derivation intentionally keeps the full canonical JSON only in `reference_documents`; derived tables contain queryable subsets, not a lossless relational decomposition of every field

## Self-review outcome

Checked the new files directly after implementation and confirmed:

- scope stayed within the brief
- tests use temporary SQLite databases only
- previous FIT_MAP revision rows remain unchanged after a later revision is inserted
- current analysis resolution returns the latest FIT_MAP and its current positioning snapshot
- no unrelated project files were edited by this task

---

## Fix Round 1 — 2026-08-18

Status: implemented and locally verified

### Review gaps addressed

1. Added migration `005_reference_versioning_and_payload_hashes.py`
   - `reference_documents.logical_key`
   - `reference_documents.content_hash`
   - `fit_map_revisions.payload_hash`
   - `positioning_revisions.payload_hash`
   - `keyword_translation_versions` history table
   - indexes for queryable reference versioning and payload hashes
   - backfill for pre-005 rows in temporary legacy-schema tests

2. Made reference versioning first-class in `ReferenceRepository`
   - `upsert_version(...)` now resolves versions by `kind + logical_key + content_hash`
   - lookup and insert now happen inside one `transaction(immediate=True)`
   - added:
     - `get_current(kind, key)`
     - `get_version(reference_id)`
     - `list_versions(kind, key)`
   - `keyword_translations` now keeps current semantics with the canonical keyword stored as the actual keyword text
   - version history now persists in `keyword_translation_versions`

3. Added canonical payload hashing for analysis and positioning
   - stored `payload_hash` is derived from the canonical stored `payload_json`
   - caller `source_hash` remains preserved separately
   - stale/arbitrary supplied `payload_hash` is rejected

4. Extended loaded analysis shape
   - `AnalysisRevision` now includes normalized `dimensions` and `objections`
   - `PositioningRevision` now exposes `payload_hash`

5. Tightened normalization fail-closed behavior
   - `_required_text(...)` now raises `ValueError` for missing/non-text/malformed required fields
   - added malformed story regression coverage

### Additional files changed in fix round

- `src/career/services/persistence/migrations/005_reference_versioning_and_payload_hashes.py`
- `tests/test_sqlite_persistence.py`
- `tests/test_database.py`

### Fix Round 1 verification

Command:

```bash
PYTHONPATH=src ./scripts/python.sh -m unittest -q \
  tests/test_analysis_revisions.py \
  tests/test_sqlite_persistence.py \
  tests/test_database.py \
  tests/test_application_repository.py
```

Result:

```text
Ran 30 tests in 1.364s
OK
```

### Notes

- All verification continued to use temporary SQLite databases only
- No writes were made to `control-plane/career.db`
- Prior FIT_MAP and positioning immutability behavior remained covered after the hash/schema changes
