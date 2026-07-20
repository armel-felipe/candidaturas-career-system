# CV Generation Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make job-specific CVs complete and internally consistent in their declared language.

**Architecture:** `cv_content.py` creates explicit locale-tagged content. The content contract validates locale, chronology, degree wording, and mandatory values before `generate_custom_cv.js` renders. `review_output.py` independently verifies the final DOCX.

**Tech Stack:** Python 3, pytest, Node.js, `docx`, DOCX XML extraction.

## Global Constraints

- Do not modify legacy generated CV scripts or current CV artifacts.
- `metadata.language` is the sole locale source and is either `pt-BR` or `en`.
- English degree wording is `Bachelor's Degree in Chemical Engineering — Faculdades Oswaldo Cruz (2014)`.
- Experience order is reverse chronological by normalized period end date.
- Education, Technical Stack, and Languages must have visible nonblank content.

---

### Task 1: Create renderer regression fixtures

**Files:**
- Create: `tests/test_custom_cv_generation.py`
- Test: `tests/test_custom_cv_generation.py`

**Interfaces:** The tests invoke `node scripts/docx/generate_custom_cv.js` with `CAREER_CV_CONTENT` and `CAREER_OUTPUTS`; they extract `word/document.xml` from the output DOCX.

- [ ] Write a valid English and a valid Portuguese payload fixture, each with four reverse-ordered experiences and three populated mandatory sections.
- [ ] Add tests that require English labels `Education`, `Technical Stack`, and `Languages`; require the exact Bachelor's text; and reject `B.Sc.`.
- [ ] Add a Portuguese test proving labels remain `Formação`, `Stack técnica`, and `Idiomas`.
- [ ] Add negative payload cases for invalid language, blank education, blank stack, blank languages, and ascending experience dates.
- [ ] Run `pytest tests/test_custom_cv_generation.py -v`; the initial run must fail due to the current language heuristic and missing contract checks.

### Task 2: Localize generated CV content

**Files:**
- Modify: `src/career/services/cv_content.py`
- Test: `tests/test_custom_cv_generation.py`

**Interfaces:** Consumes `fit_map["idioma"]`, selected catalog experiences, and job family. Produces locale-specific summary, experiences, education, languages, output name, and `metadata.language`.

- [ ] Write a focused failing test showing that content generated from an English FIT_MAP has `metadata.language == "en"`, an `_en.docx` name, English roles and bullets, and the canonical Bachelor's text.
- [ ] Implement `_cv_language(fit_map: dict[str, Any]) -> str`, returning `en` only for English job language and `pt-BR` otherwise.
- [ ] Add the complete English translation map for every selectable experience's role, scope, leverage, and result. The producer must never fall back to Portuguese text for an English payload.
- [ ] Replace `DEFAULT_EDUCATION_EN` B.Sc. text with the exact canonical Bachelor's wording and use English language values (`Portuguese — Native`, `English — Advanced`) for English CVs.
- [ ] Add `metadata.language`, locale-specific experience keys/content, and English filename suffix while preserving PT-BR behavior.
- [ ] Run `pytest tests/test_custom_cv_generation.py -v` and confirm producer tests pass before moving to the contract.

### Task 3: Validate the content contract and renderer inputs

**Files:**
- Modify: `src/career/services/applications_v2.py`
- Modify: `scripts/docx/generate_custom_cv.js`
- Test: `tests/test_custom_cv_generation.py`

**Interfaces:** `_validate_cv_content_contract(paths: dict[str, Path]) -> None` accepts only complete valid content. The Node renderer consumes the validated `metadata.language` and exits nonzero for invalid direct input.

- [ ] Run `pytest tests/test_custom_cv_generation.py -k contract -v` and observe all new invalid cases fail before implementation.
- [ ] Add language-field selection, nonempty-section, degree-wording, and reverse-chronology helpers to `_validate_cv_content_contract` while retaining existing bullet, anti-consolidation, and ATS validation.
- [ ] Parse English and Portuguese month names/abbreviations; treat `Present` and `Atual` as current; reject unparseable periods and ascending end dates.
- [ ] Replace `hasEnglishContent` with direct assertion that `cv.metadata.language` is `pt-BR` or `en`.
- [ ] Add JavaScript assertions for the locale-appropriate education list, stack string, and locale-appropriate language list before DOCX writing.
- [ ] Run `pytest tests/test_custom_cv_generation.py -v`; expected result: all renderer and contract tests pass.
- [ ] Commit: `git add src/career/services/cv_content.py src/career/services/applications_v2.py scripts/docx/generate_custom_cv.js tests/test_custom_cv_generation.py` then `git commit -m "fix: enforce CV language and required sections"`.

### Task 4: Make final DOCX review locale-aware

**Files:**
- Modify: `scripts/review_output.py`
- Modify: `tests/test_custom_cv_generation.py`

**Interfaces:** The reviewer consumes extracted DOCX text and artifact locale, emitting blockers for mixed language, bad English degree, blank mandatory content, or chronology failure.

- [ ] Write failing reviewer tests for a valid English DOCX containing `Technical Stack` and a corrupted mixed-language or blank-section English DOCX.
- [ ] Run `pytest tests/test_custom_cv_generation.py -k reviewer -v`; expect failure because `Technical Stack` is not currently recognized and no structural locale blockers exist.
- [ ] Recognize `Technical Stack` in all section-boundary extractors.
- [ ] Implement section-content checks for Education/Formação, Technical Stack/Stack técnica, and Languages/Idiomas.
- [ ] Apply Portuguese lexical and keyword-naturalness rules only to PT-BR artifacts; the English branch validates English visible content, canonical degree, and chronology without requiring Portuguese connectors.
- [ ] Run `pytest tests/test_custom_cv_generation.py -k reviewer -v`; expected result: all reviewer tests pass.
- [ ] Commit: `git add scripts/review_output.py tests/test_custom_cv_generation.py` then `git commit -m "fix: review English CV structure independently"`.

### Task 5: Verify and publish

**Files:**
- Verify: `src/career/services/cv_content.py`, `src/career/services/applications_v2.py`, `scripts/docx/generate_custom_cv.js`, `scripts/review_output.py`, and `tests/test_custom_cv_generation.py`

- [ ] Run `pytest tests/test_custom_cv_generation.py -v && pytest -q`; expected exit code 0.
- [ ] Generate an English fixture DOCX and run `python3 scripts/docx/validate_docx.py <artifact>`; verify its extracted text has the exact degree and populated sections.
- [ ] Run final ATS/reviewer commands against a final `outputs/*_en.docx`: `register_keywords.py` first, then `review_output.py`; expect `approved_for_delivery=true` with zero blockers.
- [ ] Inspect `git status --short`, commit remaining verified changes, inspect `git remote -v`, push the configured GitHub remote, and run the repository's configured RPi5 sync command.
- [ ] If either remote is absent or fails, retain the local verified commit and report its exact command failure; do not claim remote synchronization.
