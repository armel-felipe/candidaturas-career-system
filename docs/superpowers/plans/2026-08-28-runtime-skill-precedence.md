# Runtime Skill Precedence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Hermes resolve project skills before global/external and profile-local skills, while blocking canonical project-name collisions.

**Architecture:** Add an explicit `project_dirs` layer to the existing external skill resolver. A shared ordered resolver returns project, external/global, and profile roots; all discovery and lookup paths consume it. A project-shadowing guard reports a canonical project skill duplicated in a profile, while unrelated profile skills remain available.

**Tech Stack:** Python, YAML profile configuration, pytest, Docker Compose smoke checks.

**Spec:** `docs/superpowers/specs/2026-08-28-runtime-skill-precedence-design.md`

## Global Constraints

- `AGENTS.md` remains the project entry point and `.agents/skills/` remains the canonical maintenance source.
- Project skills have priority over external/global and profile-local skills.
- Do not expose or change provider credentials.
- Do not delete unrelated generic profile skills only because they are large.
- Delete only confirmed career duplicates/legacy skills listed in the inventory task.

### Task 1: Add failing resolver and collision tests

**Files:**
- Modify: `hermes-src/tests/agent/test_external_skills.py`
- Create: `tests/test_runtime_skill_precedence.py`

**Interfaces:**
- Consumes: temporary project, external, and profile skill roots.
- Produces: executable tests for ordered roots, canonical resolution, collision guard, and both profile configuration contracts.

- [x] **Step 1: Write the failing tests**

Add tests that configure `project_dirs` plus `external_dirs`, create the same
skill name in project and profile roots, and assert:

```python
def test_project_roots_precede_external_and_profile(hermes_home, tmp_path):
    project = tmp_path / "project"
    external = tmp_path / "external"
    project.mkdir()
    external.mkdir()
    local = hermes_home / "skills"
    _make_skill(project, "shared", body="PROJECT")
    _make_skill(external, "shared", body="GLOBAL")
    _make_skill(local, "shared", body="PROFILE")
    (hermes_home / "config.yaml").write_text(
        f"skills:\n  project_dirs:\n    - {project}\n  external_dirs:\n    - {external}\n"
    )
    with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
        from agent.skill_utils import get_skill_search_dirs
        assert get_skill_search_dirs() == [project.resolve(), external.resolve(), local]


def test_project_shadowing_is_reported(hermes_home, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    local = hermes_home / "skills"
    _make_skill(project, "shared")
    _make_skill(local, "shared")
    (hermes_home / "config.yaml").write_text(
        f"skills:\n  project_dirs:\n    - {project}\n"
    )
    with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
        from agent.skill_utils import validate_project_skill_sources
        with pytest.raises(RuntimeError, match="shared"):
            validate_project_skill_sources()
```

The profile contract test must initially fail because `project_dirs` and
`source_precedence` do not yet exist in both configs. The resolver test must
fail because no ordered project-aware resolver exists.

- [x] **Step 2: Run the tests to verify the expected failures**

Run:

```bash
PYTHONPATH=hermes-src .venv/bin/pytest -q hermes-src/tests/agent/test_external_skills.py tests/test_runtime_skill_precedence.py
```

Expected: FAIL with missing `get_skill_search_dirs`/`validate_project_skill_sources` and missing profile configuration keys.

### Task 2: Implement the shared precedence resolver

**Files:**
- Modify: `hermes-src/agent/skill_utils.py`
- Modify: `hermes-src/tools/skill_manager_tool.py`
- Modify: `hermes-src/tools/skills_tool.py`
- Modify: `hermes-src/agent/prompt_builder.py`
- Modify: `hermes-src/gateway/run.py`

**Interfaces:**
- Consumes: `skills.project_dirs`, `skills.external_dirs`, and the active profile skills directory.
- Produces: `get_project_skills_dirs()`, `get_skill_search_dirs()`, and `validate_project_skill_sources()`; all skill discovery paths use the same order.

- [x] **Step 1: Implement project directory parsing and ordered search**

Factor the existing path expansion/validation logic so `project_dirs` is read
with the same safety rules as `external_dirs`. Implement:

```python
def get_project_skills_dirs() -> list[Path]: ...
def get_skill_search_dirs() -> list[Path]: ...
```

`get_skill_search_dirs()` must return project roots in declaration order,
external roots in declaration order, then the active profile root, with
duplicates removed. Keep `get_all_skills_dirs()` backward compatible for
callers that explicitly need the old inventory shape; migrate active lookup
callers to the new function.

- [x] **Step 2: Implement the project-shadowing guard**

Add `validate_project_skill_sources()` that indexes skill directory names and
frontmatter names in project roots, searches the profile root, and raises a
clear `RuntimeError` listing each conflicting name and both paths. No generic
external/profile collision is blocked by this guard.

- [x] **Step 3: Migrate lookup and prompt discovery**

Use `get_skill_search_dirs()` in `_find_skill`, `_find_all_skills`, category
resolution, `skill_view` trusted-root checks, prompt index construction, and
gateway availability scans. Remove assumptions that index zero is the local
profile root. Keep `skill_view`'s existing refusal for ambiguous bare names;
the new guard handles only project-vs-profile collisions.

- [x] **Step 4: Run focused tests**

Run:

```bash
PYTHONPATH=hermes-src .venv/bin/pytest -q hermes-src/tests/agent/test_external_skills.py hermes-src/tests/tools/test_skills_tool.py hermes-src/tests/tools/test_skill_manager_tool.py tests/test_runtime_skill_precedence.py
```

Expected: PASS, including the new project-first tests and existing external-skill behavior.

### Task 3: Configure profiles and remove confirmed career duplicates

**Files:**
- Modify: `hermes/vagas_bot_01/config.yaml`
- Modify: `hermes/vagas_bot_02/config.yaml`
- Modify: `hermes/runtime/vagas_bot_01/config.yaml`
- Modify: `hermes/runtime/vagas_bot_02/config.yaml`
- Delete: `hermes/vagas_bot_01/skills/software-development/career-system-workflow/`
- Delete: `hermes/vagas_bot_02/skills/software-development/candidaturas-operational-patterns/`
- Delete: `hermes/vagas_bot_02/skills/career/cv-generator/`
- Delete: `hermes/vagas_bot_02/skills/software-development/enquadramento-posicionamento/`
- Delete: `hermes/vagas_bot_02/skills/software-development/linkedin-saved-jobs/`
- Delete: `hermes/vagas_bot_02/skills/creative/feras-pitch/`

**Interfaces:**
- Consumes: canonical `/workspace/candidaturas/.agents/skills` and existing profile integrations.
- Produces: two profiles with identical precedence declarations and no confirmed project/career duplicates.

- [x] **Step 1: Add explicit precedence configuration**

In both configs, replace the current canonical entry under `external_dirs`
with:

```yaml
skills:
  project_dirs:
    - /workspace/candidaturas/.agents/skills
  external_dirs: []
  source_precedence:
    - project
    - global
    - profile
```

- [x] **Step 2: Remove only confirmed duplicates**

Delete the six listed profile-local career/project copies. Preserve generic
skills such as `research-paper-writing`, and preserve profile-only integrations
such as Telegram/Google Workspace helpers.

- [x] **Step 3: Run configuration and inventory tests**

Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_runtime_skill_precedence.py tests/test_bot02_profile_context.py
```

Expected: PASS, with both profiles declaring the same precedence and no listed
legacy path present.

### Task 4: Restart and verify runtime behavior

**Files:**
- Modify: `docs/roadmap.md`

**Interfaces:**
- Consumes: updated Hermes source, profile configs, and cleaned skill trees.
- Produces: rebuilt containers, discovery smoke evidence, and a synchronized `RUNTIME-013` roadmap entry.

- [x] **Step 1: Rebuild and recreate both containers**

Run:

```bash
docker compose build vagas_bot_01 vagas_bot_02
docker compose up -d --force-recreate vagas_bot_01 vagas_bot_02
```

- [x] **Step 2: Verify source resolution and logs**

Run:

```bash
docker compose exec -T vagas_bot_01 hermes skills list
docker compose exec -T vagas_bot_02 hermes skills list
docker compose logs --since=2m vagas_bot_01 vagas_bot_02
```

Expected: project career skills resolve under `/workspace/candidaturas/.agents/skills`, both profiles retain `150/80000`, and no new `skill_manage` over-limit, truncation, or legacy career path errors appear.

- [x] **Step 3: Run final validation**

Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_runtime_skill_precedence.py tests/test_bot02_profile_context.py tests/test_runtime_provider_config.py tests/test_harness_dispatch.py
npm run validate:structure
npm run runtime:verify -- --strict
git diff --check
```

- [x] **Step 4: Synchronize the roadmap**

Change `RUNTIME-013` to `DONE` only after the source-resolution smoke and all
tests pass. Record the explicit three-tier precedence, the exact deleted
legacy paths, container restart, and command evidence. If an unremoved
project duplicate or runtime error remains, keep the item `IN_PROGRESS` and
record that path as the remaining blocker.

## Execution evidence (2026-08-28)

- Initial RED run confirmed the missing project-aware resolver and configuration
  contract.
- The focused Hermes suite passed with `459 passed`; the project regression
  suite passed with `13 passed`.
- `npm run validate:structure`, `npm run runtime:verify -- --strict` and
  `git diff --check` passed.
- `docker compose build vagas_bot_01 vagas_bot_02` and
  `docker compose up -d --force-recreate vagas_bot_01 vagas_bot_02` completed;
  both services are running from `candidaturas/hermes-agent:0.18.2`.
- In both containers, the ordered resolver returned the canonical project
  root before the profile root, the project/profile collision guard passed,
  and the supervised identity is `uid=10000(hermes)`.
- Recent container logs showed no permission, truncation, architecture or
  legacy-career-skill errors.
- The canonical project-wide suite (`PYTHONPATH=src .venv/bin/pytest -q
  tests --import-mode=importlib`) completed with `576 passed` and four
  failures outside this plan: one stale planner expectation and the three
  already tracked legacy intake-persistence cases (`TEST-005`, `TEST-007` and
  `TEST-008`). Those failures do not exercise the skill-resolution changes.
