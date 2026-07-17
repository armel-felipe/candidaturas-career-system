# `.agents` Skill Root Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `.opencode/skills` with the single canonical skill root `.agents/skills` while keeping all career workflows operational.

**Architecture:** `AGENTS.md` remains the runtime-neutral entry point; it directs agents to `.agents/skills/career-system/SKILL.md` and then to individual skills. `opencode.json` remains only the OpenCode integration config that loads `AGENTS.md`. Structural validation owns enforcement of the new root and blocks the deprecated directory and references in active project files.

**Tech Stack:** Python 3 standard library validator and pytest; Markdown documentation; JSON OpenCode configuration; Git directory rename.

## Global Constraints

- The only canonical skills path is `.agents/skills/`; do not create `.opencode`, a symlink, a copy, or a fallback.
- Preserve `opencode.json` and its `instructions: ["AGENTS.md"]` integration.
- Preserve skill names, internal files, reference content, npm commands, and career workflow behavior.
- Update all active references to `.opencode/skills` in source, scripts, configuration, instructions, and live documentation.
- Do not rewrite historical files in `docs/superpowers/plans/` or `docs/superpowers/specs/`; exclude them from legacy-reference enforcement.
- Use `apply_patch` for content edits and `git mv` for the directory rename.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `.agents/skills/` | Canonical moved skill library, including `career-system/references/`. |
| `AGENTS.md` | Runtime-neutral governance and canonical path instructions. |
| `COMO_USAR.md` | User-facing architecture and maintenance documentation. |
| `.env.example` | Default `CAREER_REFERENCES` path. |
| `src/career/services/{derived_context,habilidades_chave,memory,multiagent,project}.py` | Runtime resolution and agent instructions using the canonical path. |
| `scripts/{keyword_translation_utils,validate_project_structure}.py` | Reference registry lookup and structural enforcement. |
| `tests/test_project_structure.py` | Regression guard for the canonical directory and validator. |

### Task 1: Add the migration regression guard

**Files:**
- Create: `tests/test_project_structure.py`
- Read: `scripts/validate_project_structure.py`
- Read: `AGENTS.md`

**Interfaces:**
- Consumes: `scripts.validate_project_structure.main() -> int`.
- Produces: pytest coverage that requires `.agents/skills`, rejects `.opencode`, and requires the structure validator to return `0` in the migrated repository.

- [ ] **Step 1: Write the failing test**

Create `tests/test_project_structure.py` with:

```python
from pathlib import Path

from scripts import validate_project_structure


ROOT = Path(__file__).resolve().parent.parent


def test_agents_skill_root_is_canonical_and_valid(capsys):
    assert (ROOT / ".agents" / "skills" / "career-system" / "SKILL.md").is_file()
    assert not (ROOT / ".opencode").exists()
    assert validate_project_structure.main() == 0
    assert "Project structure validation passed." in capsys.readouterr().out
```

- [ ] **Step 2: Run the test to verify it fails before migration**

Run: `pytest tests/test_project_structure.py::test_agents_skill_root_is_canonical_and_valid -v`

Expected: FAIL because `.agents/skills/career-system/SKILL.md` does not exist and `.opencode` still exists.

- [ ] **Step 3: Commit the red test**

```bash
git add tests/test_project_structure.py
git commit -m "test: require agents skill root"
```

### Task 2: Move the skill library and migrate runtime path resolution

**Files:**
- Rename: `.opencode/` → `.agents/`
- Modify: `src/career/services/derived_context.py:18,449-452`
- Modify: `src/career/services/habilidades_chave.py:11-18`
- Modify: `src/career/services/memory.py:14`
- Modify: `src/career/services/multiagent.py:72,395-419`
- Modify: `src/career/services/project.py:106`
- Modify: `scripts/keyword_translation_utils.py:11`
- Modify: `.env.example:6`

**Interfaces:**
- Consumes: directory moved by `git mv`; existing `ROOT / ...` path construction and string paths in multiagent requests.
- Produces: the same reference files and SKILL paths, now resolving under `.agents/skills`.

- [ ] **Step 1: Rename the directory with Git**

Run:

```bash
git mv .opencode .agents
find .agents/skills -name SKILL.md -print | sort
```

Expected: every prior skill appears under `.agents/skills/<skill>/SKILL.md`; `.opencode` is absent.

- [ ] **Step 2: Update runtime path constants and user-facing guard strings**

Use `apply_patch` to replace only the following path segments:

```python
# src/career/services/derived_context.py and memory.py
ROOT / ".agents" / "skills" / "career-system" / "references"

# src/career/services/habilidades_chave.py
ROOT / ".agents" / "skills" / "career-system" / "references" / "habilidades_gupy.json"
ROOT / ".agents" / "skills" / "habilidades-chave" / "references" / "habilidades_mercado_livre.json"

# scripts/keyword_translation_utils.py
Path(".agents/skills/career-system/references/keyword_translation_registry.json")
```

Replace the four multiagent `SKILL.md` strings, derived-context fallback paths, and the narrow-search guard strings from `.opencode` to `.agents`. Set `.env.example` to:

```dotenv
CAREER_REFERENCES=.agents/skills/career-system/references
```

- [ ] **Step 3: Verify Python modules compile and path references are clean**

Run:

```bash
python3 -m compileall -q src/career/services scripts/keyword_translation_utils.py
rg -n --hidden --glob '!.git/**' --glob '!docs/superpowers/plans/**' --glob '!docs/superpowers/specs/**' '\\.opencode(?:/|\\b)|CAREER_REFERENCES=.opencode' src scripts .env.example
```

Expected: compilation succeeds and `rg` returns no matches.

- [ ] **Step 4: Commit the move and runtime migration**

```bash
git add .agents src/career/services scripts/keyword_translation_utils.py .env.example
git commit -m "refactor: move skill library to agents root"
```

### Task 3: Update agent instructions, skill-internal links, and live documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `COMO_USAR.md`
- Modify: `.agents/skills/**/*.md`
- Modify: `.agents/skills/**/*.json`

**Interfaces:**
- Consumes: canonical `.agents/skills` tree created in Task 2.
- Produces: a single discoverable path in all agent-facing instructions and skill references.

- [ ] **Step 1: Verify the current active legacy-reference inventory**

Run:

```bash
rg -l --hidden --glob '!.git/**' --glob '!docs/superpowers/plans/**' --glob '!docs/superpowers/specs/**' '\\.opencode/skills' AGENTS.md COMO_USAR.md .agents
```

Expected: `AGENTS.md`, `COMO_USAR.md`, and affected files in `.agents/skills/` are listed.

- [ ] **Step 2: Replace canonical path references without changing operational prose**

Use `apply_patch` across each file returned by Step 1. Every occurrence of `.opencode/skills` becomes `.agents/skills`; occurrences that say a broad search must avoid `.opencode` become `.agents`. Preserve command names, routing rules, policies, and non-path text unchanged.

The top governance blocks must read exactly:

```markdown
Fonte canônica de manutenção: `.agents/skills/{skill}/SKILL.md`.
```

and:

```markdown
AGENTS.md  →  .agents/skills/career-system/SKILL.md
```

- [ ] **Step 3: Check runtime-neutral OpenCode integration remains intact**

Run:

```bash
node -e 'const config=require("./opencode.json"); if (!Array.isArray(config.instructions) || !config.instructions.includes("AGENTS.md")) process.exit(1); console.log("opencode.json still loads AGENTS.md")'
rg -n --hidden --glob '!.git/**' --glob '!docs/superpowers/plans/**' --glob '!docs/superpowers/specs/**' '\\.opencode/skills|\.opencode/' AGENTS.md COMO_USAR.md .agents
```

Expected: Node prints `opencode.json still loads AGENTS.md`; `rg` returns no matches.

- [ ] **Step 4: Commit the instruction and documentation migration**

```bash
git add AGENTS.md COMO_USAR.md .agents
git commit -m "docs: point agent instructions to agents skills"
```

### Task 4: Enforce the new root in structural validation and complete verification

**Files:**
- Modify: `scripts/validate_project_structure.py:9-174`
- Test: `tests/test_project_structure.py`

**Interfaces:**
- Consumes: `ROOT`, `AGENT_SKILLS`, `FORBIDDEN_PATHS`, `SCAN_ROOTS`, `FORBIDDEN_TEXT`, and `DOC_EXPECTATIONS` in `scripts/validate_project_structure.py`.
- Produces: `main() -> 0` only when `.agents/skills` exists, all required skills exist there, `.opencode` is absent, and active files contain no `.opencode/skills` path.

- [ ] **Step 1: Update validator names, required paths, and active scan roots**

Use `apply_patch` to make these exact changes:

```python
AGENT_SKILLS = ROOT / ".agents" / "skills"

FORBIDDEN_PATHS = [
    "skills",
    ".claude",
    ".opencode",
    # keep every other existing forbidden legacy path
]

SCAN_ROOTS = [
    "AGENTS.md",
    "COMO_USAR.md",
    ".agents",
    ".env.example",
    ".vscode",
    "scripts",
    "src",
    "sessions",
    "inbox",
]

FORBIDDEN_TEXT = [
    ".opencode/skills",
    # keep every existing forbidden text pattern
]
```

Replace every `OPENCODE_SKILLS` use with `AGENT_SKILLS`, every key in `DOC_EXPECTATIONS` with its `.agents/skills/...` equivalent, and the missing-root diagnostic with `Missing canonical skill root: .agents/skills`.

- [ ] **Step 2: Run the focused regression test**

Run: `pytest tests/test_project_structure.py::test_agents_skill_root_is_canonical_and_valid -v`

Expected: PASS.

- [ ] **Step 3: Run project verification**

Run:

```bash
python3 scripts/validate_project_structure.py
pytest -q
rg -n --hidden --glob '!.git/**' --glob '!docs/superpowers/plans/**' --glob '!docs/superpowers/specs/**' --glob '!scripts/validate_project_structure.py' --glob '!tests/test_project_structure.py' '\\.opencode(?:/|\\b)' .
git diff --check
git status --short
```

Expected: structural validation prints `Project structure validation passed.`; pytest passes; legacy-reference search has no output outside `scripts/validate_project_structure.py` and `tests/test_project_structure.py`; those two files are excluded because their `.opencode` strings are enforcement literals, not active legacy references. Diff check is clean; status contains only the intentional migration changes before commit.

- [ ] **Step 4: Commit the enforcement and tests**

```bash
git add scripts/validate_project_structure.py tests/test_project_structure.py
git commit -m "test: enforce agents skill root"
```
