# CV Summary Narrative Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a personalized, first-person CV summary while retaining the catalog case as a non-redundant career-direction sentence.

**Architecture:** `cv_content._build_summary` will keep existing evidence selection but compose a Portuguese three-sentence narrative: first-person positioning, two supported stories, and an optional paraphrased direction derived from `positioning.caso`. Small pure helpers will normalize focus terms, select distinct story fragments, and omit redundant direction text.

**Tech Stack:** Python 3.12, pytest, existing `cv_content` provenance and application contracts.

## Global Constraints

- Keep `resultado_chave` out of rendered text, bullets and `summary_support`.
- Keep `summary_support` bound to two distinct canonical experience bullets.
- Portuguese summaries use first person; English output remains unchanged.
- Do not modify FIT_MAP or the positioning catalog schema.

### Task 1: Narrative composition helpers

**Files:**
- Modify: `src/career/services/cv_content.py`
- Modify: `tests/test_cv_positioning.py`

**Interfaces:**
- Add `_compose_positioning_opening(fit_map: dict[str, Any]) -> str`.
- Add `_compose_direction(positioning: dict[str, Any] | None, used_terms: set[str]) -> str | None`.

- [ ] **Step 1: Write failing tests**

```python
def test_portuguese_summary_keeps_first_person_presentation_and_case_direction():
    summary, support = cv_content._build_summary(selected, fit_map, positioning=positioning)
    assert summary.startswith("Atuo ")
    assert "Na trajetória recente, liderei" in summary
    assert "Busco uma posição em que eu possa" in summary
    assert len({item["experience_id"] for item in support}) == 2
```

Add a duplicate case test where `caso` repeats all focus terms in the opening and assert that the direction is omitted.

- [ ] **Step 2: Verify RED**

Run: `/home/ubuntu/.local/bin/uv run --python 3.12 --with pytest pytest tests/test_cv_positioning.py -k summary -v`

Expected: FAIL because the current Portuguese summary begins with `Busco posição` and has no presentation sentence.

- [ ] **Step 3: Implement minimal composer**

Use the following shape in `_build_summary` for `pt-BR`:

```python
opening = _compose_positioning_opening(fit_map)
proof = f"Na trajetória recente, liderei {first}. Também conduzi {second}."
direction = _compose_direction(positioning, normalize_tokens(f"{opening} {proof}"))
summary = " ".join(part for part in (opening, proof, direction) if part)
```

`_compose_direction` must return `Busco uma posição em que eu possa {caso_sem_ponto}.` only when its meaningful tokens are not already contained by `used_terms`.

- [ ] **Step 4: Verify GREEN**

Run: `/home/ubuntu/.local/bin/uv run --python 3.12 --with pytest pytest tests/test_cv_positioning.py -k summary -v`

Expected: PASS.

### Task 2: Evidence and provenance regression coverage

**Files:**
- Modify: `tests/test_cv_positioning.py`
- Modify: `src/career/services/cv_content.py`

- [ ] **Step 1: Add failing integrity tests**

```python
def test_summary_never_uses_same_experience_or_catalog_result_as_two_stories():
    payload = build_positioned_payload()
    assert len({item["experience_id"] for item in payload["summary_support"]}) == 2
    assert payload["positioning"]["caso"] in payload["summary"] or "Busco uma posição" not in payload["summary"]
    assert catalog_result_key not in payload["summary"]
```

- [ ] **Step 2: Verify RED and implement**

Run the test, then make `_summary_support_pairs` skip a second fragment from the same experience and make the direction omit repeated content rather than copying it.

- [ ] **Step 3: Verify full CV regression**

Run: `/home/ubuntu/.local/bin/uv run --python 3.12 --with pytest pytest tests/test_cv_positioning.py tests/test_candidate_cv_facts.py tests/test_custom_cv_generation.py -v`

Expected: PASS.

### Task 3: Application-pipeline verification

**Files:**
- Modify: `tests/test_cell_cv_pipeline.py`

- [ ] **Step 1: Add a PT-BR pipeline assertion**

Assert generated `cv_content.json` begins in first person, retains two different summary-support experiences, and does not contain a catalog `resultado_chave`.

- [ ] **Step 2: Run the cell test and correct only a demonstrated integration issue**

Run: `/home/ubuntu/.local/bin/uv run --python 3.12 --with pytest pytest tests/test_cell_cv_pipeline.py -v`

- [ ] **Step 3: Final verification**

Run: `/home/ubuntu/.local/bin/uv run --python 3.12 --with pytest pytest tests/test_cv_positioning.py tests/test_candidate_cv_facts.py tests/test_cell_cv_pipeline.py tests/test_custom_cv_generation.py -v`

Run: `git diff --check`

Expected: all selected tests pass and the diff has no whitespace errors.
