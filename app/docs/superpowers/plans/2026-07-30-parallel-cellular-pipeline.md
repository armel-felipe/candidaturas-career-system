# Parallel Cellular Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make two Hermes profiles safely process different Notion applications concurrently in the single RPi5 workspace.

**Architecture:** Use the existing `CellExecutor` as the sole production path. SQLite stays authoritative for leases, locks and audits; candidate knowledge remains shared, while every job artifact stays under `.career-state/applications_v2/<application_id>/`.

**Tech Stack:** Python 3.12, SQLite, pytest, `career_cli.py`, cellular executor, Hermes runner.

## Global Constraints

- The RPi5 has one authoritative workspace; no cross-host ledger is added.
- Concurrent capacity is exactly two applications.
- `CAREER_CONTROL_DB_ID` must match `.career-state/career.db` before work begins.
- Candidate facts, rules, keyword registry and Notion cache are shared; job source, FIT_MAP, content, reviews, DOCX and receipts are isolated.
- Notion writes and OneDrive delivery remain serialized by cellular resource locks.
- Parallel mode cannot select a legacy non-cellular heartbeat.

---

## File Structure

- `src/career/services/applications_v2.py`: local activation, diagnosis and cellular precondition guard.
- `src/career/cli.py`: `applications` activation/status actions and legacy heartbeat rejection.
- `tests/test_applications_v2.py`: activation and heartbeat preconditions.
- `tests/test_cell_cli.py`: CLI and npm interface contracts.
- `tests/test_cell_cv_pipeline.py`: two-application artifact isolation proof.
- `package.json`, `.agents/skills/career-system/SKILL.md`: safe operator entrypoints and Hermes contract.

### Task 1: Activate an explicit local two-worker mode

**Files:**
- Modify: `src/career/services/applications_v2.py`
- Modify: `src/career/cli.py`
- Test: `tests/test_applications_v2.py`
- Test: `tests/test_cell_cli.py`

**Interfaces:**
- Produces `activate_local_parallel_mode(*, max_workers: int = 2) -> dict[str, Any]`.
- Produces `parallel_mode_status() -> dict[str, Any]` with `ready`, `blocker`, `pipeline_mode`, capacity and control database identity.
- Persists `pipeline_mode: "cellular"`, `max_per_run: 2`, `cellular_max_workers: 2` in `V2_CONFIG`.

- [ ] **Step 1: Write failing service tests**

```python
def test_activate_local_parallel_mode_sets_two_cellular_workers(tmp_path, monkeypatch):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    monkeypatch.setattr(applications_v2, "V2_DIR", tmp_path / "applications_v2")
    monkeypatch.setattr(applications_v2, "Database", lambda *_a, **_k: database)
    result = applications_v2.activate_local_parallel_mode(max_workers=2)
    assert result == {
        "status": "activated", "pipeline_mode": "cellular",
        "max_per_run": 2, "cellular_max_workers": 2,
        "control_db_id": database.control_db_identity(),
    }

def test_activate_local_parallel_mode_rejects_other_capacity():
    with pytest.raises(ValueError, match="exactly 2"):
        applications_v2.activate_local_parallel_mode(max_workers=3)
```

- [ ] **Step 2: Verify the tests fail**

Run: `pytest tests/test_applications_v2.py -k 'activate_local_parallel_mode' -v`

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement minimal activation and inspection**

```python
def activate_local_parallel_mode(*, max_workers: int = 2) -> dict[str, Any]:
    if max_workers != 2:
        raise ValueError("local parallel mode requires exactly 2 workers")
    database = Database(V2_DIR.parent / "career.db")
    try:
        database.init_schema()
        control_db_id = database.control_db_identity()
    finally:
        database.close()
    config = _load_config()
    config.update({"pipeline_mode": "cellular", "max_per_run": 2, "cellular_max_workers": 2})
    write_json(V2_CONFIG, config)
    return {"status": "activated", "pipeline_mode": "cellular", "max_per_run": 2,
            "cellular_max_workers": 2, "control_db_id": control_db_id}
```

`parallel_mode_status()` reads config and database, compares the environment
value with `control_db_identity()`, and returns one of
`parallel_mode_not_activated`, `career_control_db_id_missing`, or
`career_control_db_id_mismatch` without mutating anything.

- [ ] **Step 4: Expose CLI actions and test them**

Add `applications activate-local-parallel --max-workers 2` and
`applications parallel-status`. Status returns nonzero unless `ready` is true.

Run: `pytest tests/test_applications_v2.py -k 'activate_local_parallel_mode or parallel_mode_status' tests/test_cell_cli.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/career/services/applications_v2.py src/career/cli.py tests/test_applications_v2.py tests/test_cell_cli.py
git commit -m "feat: activate local cellular parallel mode"
```

### Task 2: Fail closed outside the cellular path

**Files:**
- Modify: `src/career/services/applications_v2.py`
- Modify: `src/career/cli.py`
- Test: `tests/test_applications_v2.py`
- Test: `tests/test_cell_cli.py`

**Interfaces:**
- Consumes `parallel_mode_status()` and `HeartbeatV2Options`.
- Produces an actionable `ValidationFailure` before a Hermes subprocess starts.

- [ ] **Step 1: Write failing guard tests**

```python
def test_cellular_heartbeat_requires_ready_parallel_runtime(monkeypatch):
    monkeypatch.setattr(applications_v2, "parallel_mode_status", lambda: {
        "ready": False, "blocker": "career_control_db_id_missing"
    })
    with pytest.raises(ValidationFailure, match="career_control_db_id_missing"):
        applications_v2.run_heartbeat(HeartbeatV2Options(
            max_per_run=2, run_agent=True, dry_run=False, cellular=True
        ))

def test_cli_rejects_legacy_heartbeat_when_parallel_mode_is_active(monkeypatch, capsys):
    monkeypatch.setattr(cli.applications_v2_service, "parallel_mode_status", lambda: {
        "ready": True, "pipeline_mode": "cellular"
    })
    assert cli.main(["applications", "heartbeat", "--run-agent", "--legacy-non-cellular"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "legacy_heartbeat_disabled_in_parallel_mode"
```

- [ ] **Step 2: Verify failures**

Run: `pytest tests/test_applications_v2.py -k 'requires_ready_parallel_runtime' tests/test_cell_cli.py -k 'legacy_heartbeat_when_parallel_mode' -v`

Expected: FAIL.

- [ ] **Step 3: Add the guards**

At `_run_cellular_heartbeat` entry call `parallel_mode_status()` and raise
`ValidationFailure` with its blocker when `ready` is false. In the CLI reject
`--legacy-non-cellular` whenever configured `pipeline_mode` is `cellular`.
Keep dry-run inspection non-mutating and unable to start Hermes.

- [ ] **Step 4: Prove two workers remain app-scoped**

Add a test with two eligible applications asserting `worker_count == 2`, two
distinct `application_id` and `run_id` values, and no global fallback.

Run: `pytest tests/test_applications_v2.py -k 'parallel or cellular_heartbeat' tests/test_cell_cli.py -k 'heartbeat' -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/career/services/applications_v2.py src/career/cli.py tests/test_applications_v2.py tests/test_cell_cli.py
git commit -m "fix: require cellular runtime for parallel heartbeat"
```

### Task 3: Extend the isolation regression

**Files:**
- Modify: `tests/test_cell_cv_pipeline.py`
- Modify: `tests/test_slice_a_core_integration.py`
- Modify only if a regression fails: `src/career/cells/handlers.py`, `src/career/cells/contracts.py`, or `src/career/cells/executor.py`

**Interfaces:**
- Consumes `CellExecutor`, `paths_for` and production handler registries.
- Produces proof of separate artifact trees and mutually exclusive external effects.

- [ ] **Step 1: Add global-artifact assertions to the existing two-CV test**

```python
assert not (tmp_path / ".career-state" / "fit_map.json").exists()
assert not (tmp_path / ".career-state" / "cv_content.json").exists()
assert first_artifact != second_artifact
assert first.app_dir in first_artifact.parents
assert second.app_dir in second_artifact.parents
```

- [ ] **Step 2: Add a declared-resource contention test**

Reserve `notion-write` for application A. Advance both executors and assert
application B completes non-Notion nodes but cannot run `sync_notion_initial`
until the A reservation releases.

- [ ] **Step 3: Run the tests**

Run: `pytest tests/test_cell_cv_pipeline.py -k 'two_application_scoped or notion_write' tests/test_slice_a_core_integration.py -k 'resource' -v`

Expected: PASS. If it fails, replace only the global adapter or missing resource
reservation identified by the failure with the corresponding `context.paths`
or `CellContract.resources` implementation.

- [ ] **Step 4: Run full cellular tests and commit**

Run: `pytest tests/test_cell_cli.py tests/test_cell_cv_pipeline.py tests/test_slice_a_core_integration.py tests/test_cell_final_security.py -v`

Expected: PASS.

```bash
git add tests/test_cell_cv_pipeline.py tests/test_slice_a_core_integration.py src/career/cells
git commit -m "test: prove concurrent cellular application isolation"
```

### Task 4: Publish safe commands for the two Hermes profiles

**Files:**
- Modify: `package.json`
- Modify: `.agents/skills/career-system/SKILL.md`
- Test: `tests/test_cell_cli.py`

**Interfaces:**
- Produces `applications:activate-parallel`, `applications:parallel-status`, and `applications:agent-heartbeat:parallel`.

- [ ] **Step 1: Write failing npm-contract test**

```python
def test_package_exposes_only_cellular_parallel_entrypoints():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert "applications:activate-parallel" in package["scripts"]
    assert "applications:parallel-status" in package["scripts"]
    command = package["scripts"]["applications:agent-heartbeat:parallel"]
    assert "heartbeat --run-agent --max-per-run 2" in command
    assert "legacy-non-cellular" not in command
```

- [ ] **Step 2: Verify failure and add aliases**

Run: `pytest tests/test_cell_cli.py -k 'parallel_entrypoints' -v`

Expected: FAIL.

Add aliases equivalent to:

```json
"applications:activate-parallel": "./scripts/python.sh scripts/career_cli.py applications activate-local-parallel --max-workers 2",
"applications:parallel-status": "./scripts/python.sh scripts/career_cli.py applications parallel-status",
"applications:agent-heartbeat:parallel": "./scripts/python.sh scripts/career_cli.py applications heartbeat --run-agent --max-per-run 2 --format both"
```

Update the skill with activation, status and one permitted runtime command. It
must tell each Hermes profile to act only from its app-scoped request and never
execute global FIT_MAP/CV commands or write to `outputs/`.

- [ ] **Step 3: Verify and commit**

Run: `pytest tests/test_cell_cli.py -k 'parallel_entrypoints or heartbeat' -v`

Expected: PASS.

```bash
git add package.json .agents/skills/career-system/SKILL.md tests/test_cell_cli.py
git commit -m "docs: add two-agent cellular operation commands"
```

### Task 5: Activate and prove the RPi5 runtime before a live run

**Files:**
- Modify: `.env` only for `CAREER_CONTROL_DB_ID` (ignored and never committed).
- Verify: `.career-state/applications_v2/config.json`, `.career-state/career.db`.

- [ ] **Step 1: Configure authority identity**

Run `npm run applications:activate-parallel`; place the returned non-secret
ID in the ignored environment file as:

```dotenv
CAREER_CONTROL_DB_ID=control_<value-returned-by-activation>
```

Do not print unrelated environment values.

- [ ] **Step 2: Check ready state**

Run: `npm run applications:parallel-status && npm run applications:doctor-concurrency`

Expected: `ready: true`, cellular mode, capacity two, matching control IDs.

- [ ] **Step 3: Run fixture concurrency proof**

Run: `fixture_dir=$(mktemp -d) && npm run applications:verify-parallel -- --fixture-dir "$fixture_dir"`

Expected: `status: validated`, distinct runs/fingerprints and no unexpected
writes. Inspect then remove only that explicit fixture directory.

- [ ] **Step 4: Do a no-write live preflight**

Run: `./scripts/python.sh scripts/career_cli.py applications heartbeat --run-agent --max-per-run 2 --dry-run --format both`

Expected: entry conditions are checked without creating a Hermes job or
altering Notion.

- [ ] **Step 5: Do not commit runtime state**

Run: `git status --short`

Expected: `.env`, SQLite databases, generated state and test fixtures are not
staged or committed.
