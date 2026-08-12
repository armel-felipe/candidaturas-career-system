# CV Summary Quality Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PT-BR CV summaries concise, story-led and safe against raw job-description or weak catalog-direction copy.

**Architecture:** Add pure summary helpers in `cv_content` for compact opening and FIT_MAP story order. Add a publication-confidence flag to the positioning selection based on high-priority signals; retain full catalog provenance regardless of whether the direction renders.

**Tech Stack:** Python 3.12, pytest, existing CV provenance contracts.

## Global Constraints

- Never render `resultado_chave`.
- Keep exactly two distinct, canonical summary supports.
- Do not alter FIT_MAP, catalog schema, experience bullets or English summaries.
- Generate and review the real application 515 before claiming completion.

---

### Task 1: Capture the regression with tests

**Files:**
- Modify: `tests/test_cv_positioning.py`

- [x] Add a failing Salesforce-shaped FIT_MAP test asserting: no raw `dor_central` paragraph in the summary; support experience ids start with `vivareal` then `ifood`; and a Customer Support catalog case is omitted when it only matches low-priority operational terms.
- [x] Run the focused pytest test and confirm the failure is caused by the raw opening.

### Task 2: Make summary composition FIT_MAP-led

**Files:**
- Modify: `src/career/services/cv_content.py`
- Test: `tests/test_cv_positioning.py`

- [x] Add a compact-opening helper that chooses approved themes from structured keyword/competency fields and never reads `dor_central` as rendered copy.
- [x] Change `_summary_support_pairs` to accept `fit_map` and prioritize its `historias_selecionadas` by company/experience present in `selected`, then use the canonical static order only to fill a missing second proof.
- [x] Run the focused test and confirm it passes.

### Task 3: Gate publication of catalog direction

**Files:**
- Modify: `src/career/services/cv_positioning.py`
- Modify: `src/career/services/cv_content.py`
- Test: `tests/test_cv_positioning.py`

- [x] Add `summary_direction_eligible: bool` to the returned positioning based on matches from cargo, `keywords_habilidade_ats`, `keywords_vaga` or `competencias_vaga`.
- [x] Render direction only when eligible and nonredundant.
- [x] Update provenance validation to accept an omitted direction for ineligible positioning.
- [x] Run focused tests and validate catalog-result protections.

### Task 4: Regenerate and validate application 515

**Files:**
- Generated: `.career-state/cv_content.json`
- Generated: `outputs/<application-515-cv>.docx`

- [ ] Integrate the reviewed implementation into `main`.
- [ ] Run `npm run context:assert-active`, `npm run cv:build-content`, `npm run cv:validate-content` and inspect the compact summary projection.
- [ ] Run `npm run cv:docx`, keyword registration and `scripts/review_output.py` on the final DOCX as required by the project skill.
- [ ] Read the final rendered summary and confirm it passes the acceptance criteria above.
- [ ] Run focused regression tests and `git diff --check`.
