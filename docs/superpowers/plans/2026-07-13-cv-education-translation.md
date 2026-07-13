# CV Education Translation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix English CV education entries — MBA → Specialization Certificate, Engenharia Química → B.Sc.

**Architecture:** Single change in `src/career/services/cv_content.py`: split `DEFAULT_EDUCATION` into PT/EN lists, detect language from `fit_map.idioma`, populate `education` and `formacao` with correct list per language.

**Tech Stack:** Python 3.11+, no new dependencies

## Global Constraints

- `education` key in `cv_content.json` gets English entries only when `fit_map.idioma` starts with "en"
- `formacao` key always gets Portuguese entries (backward-compatible for PT-BR renderer)
- Six Sigma Green Belt entry is identical in PT and EN (no translation needed)
- Contract `["string"]` preserved — no schema changes

---

### Task 1: Refactor `DEFAULT_EDUCATION` and language-aware build

**Files:**
- Modify: `src/career/services/cv_content.py:198-258`

**Interfaces:**
- Consumes: `fit_map` dict (already loaded in `build_current_cv_content`)
- Produces: `cv_content.json` with `education` populated per language

- [ ] **Step 1: Replace `DEFAULT_EDUCATION` with two lists**

Replace lines 198-202:

```python
DEFAULT_EDUCATION_PT = [
    "MBA Corporate Strategy — BSP Business School São Paulo (2017)",
    "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)",
    "Six Sigma Green Belt — Setec Consulting (2020)",
]

DEFAULT_EDUCATION_EN = [
    "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)",
    "B.Sc. Chemical Engineering — Faculdades Oswaldo Cruz (2014)",
    "Six Sigma Green Belt — Setec Consulting (2020)",
]
```

- [ ] **Step 2: Add language detection and conditional assignment**

Replace lines 257-258:

```python
        is_en = str(fit_map.get("idioma") or "").strip().lower().startswith("en")
        education_list = DEFAULT_EDUCATION_EN if is_en else DEFAULT_EDUCATION_PT
        "education": list(education_list),
        "formacao": list(DEFAULT_EDUCATION_PT),
```

- [ ] **Step 3: Verify the change builds**

Run: `python3 -c "import sys; sys.path.insert(0,'src'); from career.services.cv_content import *; print('OK')"`

Expected: no import errors, OK printed.

- [ ] **Step 4: Run existing validation suite**

Run: `python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30`

Expected: all existing tests pass (no regressions since contract shape is unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/career/services/cv_content.py
git commit -m "fix: correct education entries for English CVs

- Split DEFAULT_EDUCATION into PT/EN lists
- Detect language from fit_map.idioma to populate education key
- MBA Corporate Strategy -> Specialization Certificate in Corporate Strategies
- Engenheiro Químico -> B.Sc. Chemical Engineering
- formacao always gets Portuguese entries (backward compatible)"
```

---

### Task 2: Validate with a real English CV build

**Files:**
- Execute: existing `npm run cv:build-content` on an English job

**Interfaces:**
- Consumes: existing `.career-state/fit_map.json` (should have an active English job or be set up for one)

- [ ] **Step 1: Check if there's an active English job**

Run: `npm run fit-map:status`

If there's an active English job, proceed. If not, verify manually by inspecting `cv_content.json` output.

- [ ] **Step 2: Rebuild CV content**

Run: `npm run cv:build-content`

Expected: command succeeds.

- [ ] **Step 3: Check education entries in output**

Run: `python3 -c "import json; d=json.load(open('.career-state/cv_content.json')); print('EDUCATION:', d.get('education')); print('FORMACAO:', d.get('formacao'))"`

Expected:
- If active job is English: `education` contains "Specialization Certificate..." and "B.Sc. Chemical Engineering..."
- If active job is Portuguese: `education` and `formacao` both contain the Portuguese entries (same as before)
- `formacao` always shows Portuguese entries regardless of language
