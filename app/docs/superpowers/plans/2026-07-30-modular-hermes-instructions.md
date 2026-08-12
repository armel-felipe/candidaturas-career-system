# Modular Hermes Instructions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace monolithic always-loaded career instructions with automatic, task-specific instruction modules while preserving every current career pipeline behavior.

**Architecture:** `AGENTS.md` becomes a compact router and `career-system/SKILL.md` becomes a compact composition contract. Five Markdown modules own runtime, intake/FIT_MAP, CV delivery, Notion/email and cellular concerns; routed skills declare their required modules in YAML front matter, and structural validation enforces the declaration and size limits.

**Tech Stack:** Markdown, YAML front matter parsed with Python standard library regexes, Python 3.12, pytest, existing `scripts/validate_project_structure.py`.

## Global Constraints

- Keep the profile Hermes -> candidatura binding, app-scoped paths and no-global-state rule intact.
- Do not alter application commands, SQLite schema, runtime hooks, artifacts or cellular behavior.
- `AGENTS.md` must be at most 15 KB and `career-system/SKILL.md` at most 10 KB.
- Do not require any routed career skill to read all of `career-system/SKILL.md`.
- A missing or unknown instruction module must fail validation; agents must not silently fall back to legacy global instructions.
- Preserve the user’s unrelated local CV changes; use an isolated worktree for implementation.

---

## File structure

| Path | Responsibility |
|---|---|
| `AGENTS.md` | Compact entrypoint: universal safety, profile binding and router only. |
| `.agents/skills/career-system/SKILL.md` | Compact module-composition contract and module inventory. |
| `.agents/skills/career-system/modules/runtime-core.md` | Hermes identity, active binding, app-scoped paths and state safety. |
| `.agents/skills/career-system/modules/intake-fit-map.md` | Job sources, intake, FIT_MAP, validation and recovery. |
| `.agents/skills/career-system/modules/cv-delivery.md` | CV production, objective review, approval and OneDrive delivery. |
| `.agents/skills/career-system/modules/notion-email.md` | Notion, Gmail, approval and external-write rules. |
| `.agents/skills/career-system/modules/cellular-runtime.md` | Cellular execution, locks, authority, runs and maintenance. |
| `.agents/skills/career-system/references/routing-table.md` | Single compact task -> skill -> modules table. |
| `scripts/validate_project_structure.py` | Size, module registry and declared-dependency checks. |
| `tests/test_project_structure.py` | Structural validation regression tests. |
| `tests/test_cell_workspace_safety.py` | Regression test for mandatory Hermes profile-binding instructions. |

## Module declaration contract

Every routed career skill uses its existing YAML front matter and adds an
`instruction_modules` list. Example:

```yaml
---
name: cv-generator
instruction_modules:
  - runtime-core
  - cv-delivery
---
```

The allowed module names are exactly `runtime-core`, `intake-fit-map`,
`cv-delivery`, `notion-email`, and `cellular-runtime`. The validator reads the
front matter from each routed career skill and rejects a missing, duplicate or
unknown name.

### Task 1: Add a tested module registry to structural validation

**Files:**
- Modify: `scripts/validate_project_structure.py`
- Modify: `tests/test_project_structure.py`

**Interfaces:**
- `INSTRUCTION_MODULES: frozenset[str]` is the allowed registry.
- `ROUTED_CAREER_SKILLS: dict[str, frozenset[str]]` maps each routed skill to its required modules.
- `validate_instruction_architecture(errors: list[str]) -> None` appends actionable validation errors.

- [ ] **Step 1: Write failing structural tests**

Add tests that create a temporary skill file and assert that the validator reports:

```python
assert "missing instruction_modules" in output
assert "unknown instruction module: missing-module" in output
assert "AGENTS.md exceeds 15360 bytes" in output
assert "career-system/SKILL.md exceeds 10240 bytes" in output
```

Add one passing fixture using:

```yaml
instruction_modules:
  - runtime-core
  - cv-delivery
```

- [ ] **Step 2: Run the new tests red**

Run: `uv run --with pytest pytest tests/test_project_structure.py -k instruction_architecture -q`

Expected: FAIL because the registry and checks do not exist.

- [ ] **Step 3: Implement the validator**

In `scripts/validate_project_structure.py`:

```python
INSTRUCTION_MODULES = frozenset({
    "runtime-core", "intake-fit-map", "cv-delivery", "notion-email", "cellular-runtime",
})

ROUTED_CAREER_SKILLS = {
    "intake-orchestrator": frozenset({"runtime-core", "intake-fit-map"}),
    "career-fit-analysis": frozenset({"runtime-core", "intake-fit-map"}),
    "cv-generator": frozenset({"runtime-core", "cv-delivery"}),
    "cover-letter": frozenset({"runtime-core", "intake-fit-map"}),
    "feras-pitch": frozenset({"runtime-core", "intake-fit-map"}),
    "habilidades-chave": frozenset({"runtime-core", "intake-fit-map"}),
    "notion-transactions": frozenset({"runtime-core", "notion-email"}),
    "self-email-draft": frozenset({"runtime-core", "notion-email"}),
}
```

Parse only the opening `---` front-matter block with `re`, collect the indented
values below `instruction_modules:`, compare them to the expected set and append
an error naming the file and invalid value. Assert module files exist under
`career-system/modules/`; enforce byte limits with `path.stat().st_size`.

- [ ] **Step 4: Run tests green**

Run: `uv run --with pytest pytest tests/test_project_structure.py -k instruction_architecture -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_project_structure.py tests/test_project_structure.py
git commit -m "test: enforce modular instruction architecture"
```

### Task 2: Create the five canonical instruction modules

**Files:**
- Create: `.agents/skills/career-system/modules/runtime-core.md`
- Create: `.agents/skills/career-system/modules/intake-fit-map.md`
- Create: `.agents/skills/career-system/modules/cv-delivery.md`
- Create: `.agents/skills/career-system/modules/notion-email.md`
- Create: `.agents/skills/career-system/modules/cellular-runtime.md`
- Modify: `tests/test_cell_workspace_safety.py`

**Interfaces:**
- Each module begins with `# <module-name>` and has a `## Mandatory rules` section.
- `runtime-core.md` is mandatory for every routed task.

- [ ] **Step 1: Write failing module-contract tests**

Add a parameterized test for all five module paths. Assert each exists, has the
expected H1 and required canonical phrases. In particular assert `runtime-core.md`
contains `profile Hermes → candidatura`, `não usar estado global`,
`profile-status` and `profile-release`; assert `cv-delivery.md` contains
`cv:approve` and `cv:deliver`; assert `cellular-runtime.md` contains
`CAREER_CONTROL_DB_ID` and `notion-write`.

- [ ] **Step 2: Run red**

Run: `uv run --with pytest pytest tests/test_cell_workspace_safety.py -k instruction_modules -q`

Expected: FAIL because `modules/` does not exist.

- [ ] **Step 3: Extract canonical rules into modules**

Move, without weakening, the authoritative rules currently distributed across
`AGENTS.md` and `career-system/SKILL.md`:

- `runtime-core.md`: direct Hermes profile binding, release/switch behavior,
  app-scoped state, active-app resolution, context compactness and universal
  recovery rules.
- `intake-fit-map.md`: Notion/LinkedIn/paste/URL intake, persisted description,
  draft/final FIT_MAP gates, incremental checks, quality validation and reset.
- `cv-delivery.md`: language, narrative, keyword evidence, DOCX output,
  objective review, approval, filename constraints and OneDrive delivery.
- `notion-email.md`: Notion write approval, Notion description safeguards,
  Gmail drafts/send authorization and external resource locking.
- `cellular-runtime.md`: authority ledger, `CAREER_CONTROL_DB_ID`, manifests,
  application isolation, run/repair commands, resource locks and maintenance.

Keep long examples and troubleshooting in `references/` and link to them from
the owning module rather than copying them.

- [ ] **Step 4: Run green**

Run: `uv run --with pytest pytest tests/test_cell_workspace_safety.py -k instruction_modules -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .agents/skills/career-system/modules tests/test_cell_workspace_safety.py
git commit -m "docs: add canonical career instruction modules"
```

### Task 3: Replace the monolithic entrypoint and umbrella skill

**Files:**
- Modify: `AGENTS.md`
- Modify: `.agents/skills/career-system/SKILL.md`
- Modify: `.agents/skills/career-system/references/routing-table.md`
- Modify: `scripts/validate_project_structure.py`
- Modify: `tests/test_project_structure.py`

**Interfaces:**
- `AGENTS.md` identifies a task and directs loading `runtime-core`, the routed
  skill’s declared modules, then the routed skill.
- `career-system/SKILL.md` describes the declaration contract and links to the
  five modules; it contains no task-specific operational command sequence.

- [ ] **Step 1: Write failing compact-entrypoint tests**

Assert that `AGENTS.md` includes `Carregamento automático por tarefa`,
`runtime-core`, `instruction_modules`, `profile Hermes → candidatura` and the
five module names; assert it does not include legacy phrases such as
`Ler .agents/skills/career-system/SKILL.md` as a prerequisite for every task.
Assert the routing table has columns `Skill` and `Módulos`.

- [ ] **Step 2: Run red**

Run: `uv run --with pytest pytest tests/test_project_structure.py -k compact_entrypoint -q`

Expected: FAIL because the current entrypoint remains monolithic.

- [ ] **Step 3: Rewrite the three documents**

Write a compact `AGENTS.md` with only project identity, canonical paths,
universal prohibitions, profile binding, the loading algorithm, the compact
routing table and `validate:structure`. Replace the large `career-system`
content with the module registry, front-matter contract, module-loading order
and references index. Rewrite `routing-table.md` as the single source for
trigger -> skill -> modules; remove the claim that it must be synchronized with
a duplicated table in `AGENTS.md`.

Move detailed commands to the relevant module or existing reference. Update
`DOC_EXPECTATIONS` so it asserts universal entrypoint phrases in `AGENTS.md`
and task-specific commands in the relevant module, rather than forcing all
commands into both monoliths.

- [ ] **Step 4: Run green and check limits**

Run: `uv run --with pytest pytest tests/test_project_structure.py -k 'compact_entrypoint or instruction_architecture' -q`

Run: `./scripts/python.sh scripts/career_cli.py project validate-structure`

Expected: PASS; `wc -c AGENTS.md .agents/skills/career-system/SKILL.md` reports
at most `15360` and `10240` bytes respectively.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md .agents/skills/career-system/SKILL.md .agents/skills/career-system/references/routing-table.md scripts/validate_project_structure.py tests/test_project_structure.py
git commit -m "refactor: make career instructions task-modular"
```

### Task 4: Declare module dependencies for every routed career skill

**Files:**
- Modify: `.agents/skills/intake-orchestrator/SKILL.md`
- Modify: `.agents/skills/career-fit-analysis/SKILL.md`
- Modify: `.agents/skills/cv-generator/SKILL.md`
- Modify: `.agents/skills/cover-letter/SKILL.md`
- Modify: `.agents/skills/feras-pitch/SKILL.md`
- Modify: `.agents/skills/habilidades-chave/SKILL.md`
- Modify: `.agents/skills/notion-transactions/SKILL.md`
- Modify: `.agents/skills/self-email-draft/SKILL.md`
- Modify: `.agents/skills/linkedin-job-extractor/SKILL.md`
- Modify: `.agents/skills/linkedin-saved-jobs/SKILL.md`
- Modify: `.agents/skills/networking-message/SKILL.md`
- Modify: `.agents/skills/application-keyword-table/SKILL.md`
- Modify: `.agents/skills/notion-xlsx-export/SKILL.md`
- Modify: `.agents/skills/general-cv-optimizer/SKILL.md`
- Modify: `.agents/skills/output-reviewer/SKILL.md`
- Modify: `.agents/skills/unified-job-analysis/SKILL.md`
- Modify: `.agents/skills/processe-a-vaga/SKILL.md`
- Modify: `tests/test_project_structure.py`

**Interfaces:**
- Every skill named in the routing table has front-matter `instruction_modules`.
- No listed skill includes a prose prerequisite to read all of
  `../career-system/SKILL.md`.

- [ ] **Step 1: Write failing dependency inventory test**

Add a parameterized test mapping every routed skill to the exact module set in
the routing table. The test reads the YAML front matter and asserts equality,
then asserts the body does not match
`(?:Leia|Ler).*career-system/SKILL\.md`.

- [ ] **Step 2: Run red**

Run: `uv run --with pytest pytest tests/test_project_structure.py -k routed_skill_modules -q`

Expected: FAIL because skills currently request the full umbrella skill or have
no module declaration.

- [ ] **Step 3: Update front matter and prerequisites**

Add `instruction_modules` to each listed skill. Use `runtime-core` plus:

| Skill family | Additional module |
|---|---|
| intake, fit analysis, LinkedIn extraction/saved jobs, cover, FERAS, skills, networking, keyword table, unified analysis | `intake-fit-map` |
| CV generator, general CV, output reviewer | `cv-delivery` |
| Notion transaction/export and email draft | `notion-email` |
| `processe-a-vaga` | `intake-fit-map`, `notion-email` |

Replace prose requiring the full umbrella file with: “Carregue os módulos
declarados no front matter conforme `career-system/SKILL.md`.” Preserve any
skill-specific commands and gates in that skill.

- [ ] **Step 4: Run green**

Run: `uv run --with pytest pytest tests/test_project_structure.py -k routed_skill_modules -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .agents/skills tests/test_project_structure.py
git commit -m "docs: declare task-specific instruction modules"
```

### Task 5: Preserve behavioral safety and complete verification

**Files:**
- Modify: `tests/test_cell_workspace_safety.py`
- Modify: `tests/test_cv_positioning.py`
- Modify: `scripts/validate_project_structure.py`

**Interfaces:**
- Safety tests read the appropriate module instead of requiring duplicated
  strings in `AGENTS.md` or the umbrella skill.

- [ ] **Step 1: Write failing migration-safety tests**

Update existing tests that inspect `AGENTS.md` or `career-system/SKILL.md` so
they assert the canonical owner module. Add a test proving a direct Hermes
profile can find profile binding requirements through `AGENTS.md` ->
`runtime-core.md`, and a test proving CV approval requirements are reachable
through `cv-generator` -> `cv-delivery.md`.

- [ ] **Step 2: Run red**

Run: `uv run --with pytest pytest tests/test_cell_workspace_safety.py tests/test_cv_positioning.py -k 'hermes or instruction or cv' -q`

Expected: FAIL until the test expectations point to the new canonical owners.

- [ ] **Step 3: Remove only verified duplicates**

Use `rg` to locate remaining references that force full `career-system` loading
or duplicate module-owned commands. Remove them only after the receiving module
contains the rule and the relevant test covers reachability. Keep links, not
copied instructions.

- [ ] **Step 4: Run focused verification**

Run: `uv run --with pytest pytest tests/test_cell_workspace_safety.py tests/test_cv_positioning.py tests/test_project_structure.py -q`

Run: `./scripts/python.sh scripts/career_cli.py project validate-structure`

Expected: all focused tests and structure validation pass.

- [ ] **Step 5: Run full verification and commit**

Run: `uv run --with pytest pytest -q`

Run: `git diff --check`

Expected: full suite passes with no whitespace errors.

```bash
git add tests/test_cell_workspace_safety.py tests/test_cv_positioning.py scripts/validate_project_structure.py
git commit -m "test: preserve modular instruction safety"
```
