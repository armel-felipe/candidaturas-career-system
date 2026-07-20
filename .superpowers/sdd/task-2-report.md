# Task 2 Report — Versioned cell contracts and immutable DAG compilation

## Status

Complete. Task 2 was implemented in the commit `feat: compile application cell graphs`.

## Important review findings remediated

- Registry integrity is now validated before any graph selection or persistence: every mapping key must equal its contract's `node_id`, and every `requires` or `invalidates` reference must name a known contract. An inconsistent registry is rejected before the plans directory is created.
- Compiled output paths are now resolved through an application-directory containment check. Paths that resolve outside `application_paths.app_dir` (including `../escape`) or to the application directory itself are rejected before persistence.
- Regression coverage adds red/green tests for key/contract mismatches, unknown `requires`, unknown `invalidates`, and an escaping output path.

## Scope delivered

- Added frozen `CellContract`, `NodePlan`, and `RunPlan` dataclasses.
- Added versioned `CELL_CONTRACTS` entries for all 15 required node IDs.
- Added `compile_run_plan(application_id, requested_deliverables, application_paths)`.
- Compiled application-local output paths and persisted validated plans to `app_dir/plans/<run_id>.json`.
- Added DAG helpers `dependencies_of`, `ready_after`, and `is_acyclic`.
- Added validation before persistence for unknown deliverables, missing contracts, duplicate node IDs, output-path collisions, and cycles.
- Added conditional `capture_source`: present only when `job_description.md` does not exist.
- Extended `paths_for(application_id, root: Path | None = None)` while preserving `APPLICATIONS_DIR` as the default root.
- Kept the Task 1 `CellStore` and database/schema invariants unchanged.

## TDD evidence

### RED

Command:

```bash
pytest tests/test_cell_planner.py -q
```

Result before production code:

```text
ModuleNotFoundError: No module named 'career.cells'
1 error in 0.05s
exit code 2
```

The failure was the expected missing compiler/module failure from the brief.

### GREEN — focused tests

Command:

```bash
pytest tests/test_cell_planner.py -q
```

Result:

```text
13 passed in 0.04s
exit code 0
```

Coverage includes the two required graph behaviors plus frozen/persisted plans, conditional source capture, every required pre-persistence rejection, registry-reference integrity, and application-local output containment.

### Full regression suite

Command:

```bash
pytest -q
```

Result:

```text
88 passed in 1.96s
exit code 0
```

### Additional verification

Commands:

```bash
python3 -m compileall -q src/career/cells src/career/services/application_context.py tests/test_cell_planner.py
git diff --check
git diff --cached --check
```

Results: all exited `0` with no diagnostics.

## Files changed

- `src/career/cells/__init__.py`
- `src/career/cells/contracts.py`
- `src/career/cells/planner.py`
- `src/career/services/application_context.py`
- `tests/test_cell_planner.py`

## Self-review

- Requirements: all interfaces, required fields, required node IDs, validation gates, conditional capture behavior, persistence, and temporary-root support from the brief are represented in code and tests.
- Isolation: compiled output paths are resolved below the supplied application's `app_dir`; the default path behavior remains unchanged.
- Persistence safety: invalid registries/graphs fail before the `plans/` directory or plan JSON is created, as asserted by tests.
- Immutability/determinism: dataclasses are frozen; node order is topological with lexical tie-breaking; edges and resource locks are sorted tuples.
- Branching: CV and FERAS become independently ready after `analyze_fit`; final Notion sync depends on the requested reviewed deliverable branches.
- Scope discipline: no changes were made to `CellStore`, the SQLite schema, or unrelated application behavior. Existing untracked `.inbox/` content was left untouched and excluded from the commit.
- Review findings: only import ordering and one long conditional were adjusted after inspection; behavior stayed unchanged and all verification was rerun afterward.
- Important review remediation: planner registry and output-path containment checks were added with regression tests; all validations still run before a plan is persisted.

## Commit

```text
feat: compile application cell graphs
```

The final hash is reported by the executing agent after the commit is created.
