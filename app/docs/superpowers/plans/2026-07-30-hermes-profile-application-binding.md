# Hermes Profile Application Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind one delegated job application to one Hermes profile from intake through every requested deliverable.

**Architecture:** SQLite becomes the authority for active profile ownership. Intake claims the current Hermes profile before any job work; AGENTS.md makes all direct Hermes work resume that binding and forbids global compatibility state.

**Tech Stack:** Python 3.12, SQLite, pytest, existing application context, intake and Hermes hook.

## Global Constraints

- Felipe delegates a job to a chosen profile; there is no automatic queue choice.
- One active application per profile and one owner per application.
- Job artifacts stay under `.career-state/applications_v2/<application_id>/`.
- New job for an occupied profile requires explicit release/switch.
- Notion and OneDrive retain existing resource locks.

---

### Task 1: Add atomic profile ownership

**Files:**
- Modify: `src/career/services/database.py`
- Modify: `src/career/services/application_context.py`
- Create: `tests/test_application_context.py`

**Interfaces:**
- `claim_profile_application(database, *, profile_id, application_id, source) -> dict`
- `active_profile_application(database, profile_id) -> dict | None`
- `release_profile_application(database, *, profile_id, application_id) -> dict`

- [ ] **Step 1: Write failing tests**

```python
def test_profile_claim_is_exclusive_and_releasable(database):
    claim = application_context.claim_profile_application(
        database, profile_id="hermes-a", application_id="notion_515", source="notion"
    )
    assert claim["status"] == "active"
    with pytest.raises(ValueError, match="profile_has_active_application"):
        application_context.claim_profile_application(
            database, profile_id="hermes-a", application_id="notion_516", source="notion"
        )
    application_context.release_profile_application(
        database, profile_id="hermes-a", application_id="notion_515"
    )
    assert application_context.active_profile_application(database, "hermes-a") is None

def test_second_profile_cannot_claim_owned_application(database):
    application_context.claim_profile_application(
        database, profile_id="hermes-a", application_id="notion_515", source="notion"
    )
    with pytest.raises(ValueError, match="application_owned_by_another_profile"):
        application_context.claim_profile_application(
            database, profile_id="hermes-b", application_id="notion_515", source="notion"
        )
```

- [ ] **Step 2: Run red**

Run: `uv run --with pytest pytest tests/test_application_context.py -q`

Expected: FAIL because the API and table do not exist.

- [ ] **Step 3: Implement transactional ownership**

Add `profile_application_bindings` with `profile_id` primary key and unique
`application_id`. In one SQLite transaction reject an active conflicting
profile/application, return matching claims idempotently, or insert a claim.
Release updates only the matching active row and otherwise raises
`profile_does_not_own_application`.

- [ ] **Step 4: Run green and commit**

Run: `uv run --with pytest pytest tests/test_application_context.py -q`

```bash
git add src/career/services/database.py src/career/services/application_context.py tests/test_application_context.py
git commit -m "feat: bind Hermes profiles to applications"
```

### Task 2: Claim binding during delegated intake

**Files:**
- Modify: `src/career/services/intake.py`
- Modify: `src/career/cli.py`
- Modify: `scripts/hermes_harness_context_hook.py`
- Test: `tests/test_intake.py`
- Test: `tests/test_cell_cli.py`

**Interfaces:**
- Intake returns `profile_binding` with `profile_id` and `application_id`.
- CLI adds `applications profile-status` and `applications profile-release --application-id <id>`.

- [ ] **Step 1: Write failing intake tests**

```python
def test_hermes_intake_claims_current_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "agent-a"))
    result = intake.from_paste(company="Acme", role="Ops", text="job text")
    assert result["profile_binding"]["application_id"] == result["application_id"]

def test_new_job_for_bound_profile_requires_explicit_release(monkeypatch):
    monkeypatch.setenv("HERMES_HOME", "/tmp/hermes-a")
    intake.from_paste(company="A", role="A", text="job a")
    with pytest.raises(ValueError, match="profile_has_active_application"):
        intake.from_paste(company="B", role="B", text="job b")
```

- [ ] **Step 2: Run red**

Run: `uv run --with pytest pytest tests/test_intake.py -k 'hermes or bound_profile' -q`

Expected: FAIL because intake has no profile claim.

- [ ] **Step 3: Implement app-scoped intake ownership**

After each intake source creates `ApplicationPaths`, claim the binding using
`profile_id_from_env()` when runtime is Hermes. Claim before any global
compatibility state is written. The hook resolves only the active binding for
its current `HERMES_HOME`; it must never infer another profile's context.

- [ ] **Step 4: Verify and commit**

Run: `uv run --with pytest pytest tests/test_intake.py tests/test_cell_cli.py tests/test_hermes_harness_context_hook.py -q`

```bash
git add src/career/services/intake.py src/career/cli.py scripts/hermes_harness_context_hook.py tests/test_intake.py tests/test_cell_cli.py tests/test_hermes_harness_context_hook.py
git commit -m "feat: claim delegated jobs for Hermes profiles"
```

### Task 3: Make binding mandatory in AGENTS.md

**Files:**
- Modify: `AGENTS.md`
- Modify: `.agents/skills/career-system/SKILL.md`
- Modify: `tests/test_cell_workspace_safety.py`

- [ ] **Step 1: Write failing documentation contract test**

```python
def test_agents_document_profile_bound_hermes_default():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "profile Hermes → candidatura" in agents
    assert "profile-status" in agents
    assert "profile-release" in agents
    assert "não usar estado global" in agents
```

- [ ] **Step 2: Run red**

Run: `uv run --with pytest pytest tests/test_cell_workspace_safety.py -k 'profile_bound_hermes_default' -q`

Expected: FAIL because the mandatory profile contract is absent.

- [ ] **Step 3: Document default behavior**

Add a short Hermes section to `AGENTS.md`: new delegated job first claims the
profile; later messages resume it; new job while bound requires explicit
release/switch; only app-scoped paths are allowed. Mirror exact commands and
failure behavior in the career-system skill.

- [ ] **Step 4: Verify and commit**

Run: `uv run --with pytest pytest tests/test_cell_workspace_safety.py tests/test_cell_cli.py -k 'profile or hermes' -q`

```bash
git add AGENTS.md .agents/skills/career-system/SKILL.md tests/test_cell_workspace_safety.py tests/test_cell_cli.py
git commit -m "docs: make Hermes profiles application-bound by default"
```

### Task 4: Prove two delegated profile flows are isolated

**Files:**
- Modify: `tests/test_cell_parallel_integration.py`
- Modify: `tests/test_cell_workspace_safety.py`

- [ ] **Step 1: Write two-profile regression**

```python
def test_two_hermes_profiles_keep_delegated_flows_isolated(tmp_path):
    first = delegate_with_home(tmp_path / "hermes-a", notion_record="515")
    second = delegate_with_home(tmp_path / "hermes-b", pasted_job="job b")
    assert first["application_id"] != second["application_id"]
    assert first["profile_binding"]["profile_id"] != second["profile_binding"]["profile_id"]
```

Advance both through cellular FIT_MAP/CV branches. Assert distinct runs,
fingerprints, manifests and artifact paths. Assert profile A cannot release or
read profile B's application.

- [ ] **Step 2: Run red, repair only identity leaks, then run full verification**

Run: `uv run --with pytest pytest tests/test_cell_parallel_integration.py tests/test_cell_workspace_safety.py -k 'two_hermes_profiles' -q`

Expected: FAIL until profile identity reaches the cellular flow.

Run: `uv run --with pytest pytest -q && ./scripts/python.sh scripts/career_cli.py project validate-structure && git diff --check`

Expected: complete suite and structure validation pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cell_parallel_integration.py tests/test_cell_workspace_safety.py src/career/services/application_context.py src/career/services/intake.py scripts/hermes_harness_context_hook.py
git commit -m "test: prove Hermes profile flow isolation"
```
