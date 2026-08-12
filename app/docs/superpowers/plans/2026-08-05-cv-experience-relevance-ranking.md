# CV Experience Relevance Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the CV's five-experience minimum with vacancy-relevant experiences before using the global fallback order.

**Architecture:** Keep story-company and `experiencia_alvo` matches as direct selections. For remaining experiences, rank normalized `focus_terms` and job-family signals against the top-eight ATS keywords; use recency as the first tie-breaker and the existing fallback order only as a deterministic final tie-breaker.

**Tech Stack:** Python 3, pytest.

## Global Constraints

- Preserve the existing 4–8 experience contract and chronological output order.
- Do not change canonical candidate facts.
- Treat direct story and target matches as higher priority than relevance-ranked candidates.

---

### Task 1: Relevance-ranking regression

**Files:**
- Modify: `tests/test_candidate_cv_facts.py`
- Modify: `src/career/services/cv_content.py:425-450`

**Interfaces:**
- Consumes: `_select_experiences(fit_map: dict[str, Any]) -> list[dict[str, Any]]`
- Produces: a selected experience list containing `renault_cs` before a fixed-priority logistics fallback for a CX FIT_MAP.

- [ ] **Step 1: Write the failing test**

```python
def test_select_experiences_ranks_cx_focus_terms_before_fixed_fallback():
    selected = cv_content._select_experiences({
        "historias_selecionadas": {},
        "keywords_habilidade_ats": [
            {"keyword": "Customer Success", "prioridade": 1, "experiencia_alvo": ""},
            {"keyword": "conversão", "prioridade": 2, "experiencia_alvo": ""},
            {"keyword": "pipeline", "prioridade": 3, "experiencia_alvo": ""},
        ],
    })

    selected_ids = [item["id"] for item in selected]
    assert "renault_cs" in selected_ids
    assert "trifil_expedicao" not in selected_ids
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest -q tests/test_candidate_cv_facts.py::test_select_experiences_ranks_cx_focus_terms_before_fixed_fallback`

Expected: failure because the current fallback includes `trifil_expedicao` and excludes `renault_cs`.

- [ ] **Step 3: Write minimal implementation**

```python
def _experience_relevance_score(entry, keywords):
    focus_terms = {_normalize(term) for term in entry.get("focus_terms", [])}
    return sum(term in focus_terms for term in keywords)
```

Rank unselected experiences by descending score and their position in `fallback_experience_priority`, then add enough to reach five.

- [ ] **Step 4: Run focused and related tests**

Run: `PYTHONPATH=src python3 -m pytest -q tests/test_candidate_cv_facts.py tests/test_cell_cv_pipeline.py`

Expected: all selected tests pass.
