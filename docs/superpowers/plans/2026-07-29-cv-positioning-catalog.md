# CV Positioning Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select an auditable, job-specific CV positioning case from the canonical results catalog and use it to compose the personalized CV summary without publishing catalog results as candidate claims.

**Architecture:** A new `cv_positioning` service owns catalog validation, deterministic relevance scoring and selection. `cv_content` invokes it with the FIT_MAP and persisted job-description text, renders the selected case into the summary, and binds the decision to the existing provenance system. The existing `summary_support` contract continues to authorize only the two experience-backed candidate claims.

**Tech Stack:** Python 3, pytest, JSON, existing `career.services.cv_content` and `career.services.applications_v2` validation contracts.

## Global Constraints

- Move `resultados.json` unchanged to `.agents/skills/career-system/references/catalogo_resultados_chave.json`; do not leave a second copy at the repository root.
- Treat `resultado_chave` as a ranking-only signal. It must never be emitted as a CV bullet, `summary_fragment`, `defensible_evidence`, or any candidate claim.
- Select only when at least one normalized token from `area` or `casos` matches the FIT_MAP/job context; otherwise retain the legacy summary opening and write `positioning: null`.
- Use deterministic ordering: score first, result-key signal only as a tiebreaker among equally matching area/case records, then the lower numeric `id`.
- Keep the current two real CV-experience entries in `summary_support`; add catalog provenance separately as `positioning_support`.
- Do not change the FIT_MAP schema, generate text through an LLM, or use the catalog in cover letters, pitch, skills, or generic CV flows.

---

## File Structure

- Create: `src/career/services/cv_positioning.py` — catalog model validation, normalized context extraction, deterministic entry scoring and selection.
- Create: `tests/test_cv_positioning.py` — isolated catalog/selector tests using a temporary JSON catalog.
- Modify: `src/career/services/cv_content.py` — invoke the selector, compose the positioning summary, emit/validate catalog provenance and recompute it during trusted-value validation.
- Modify: `src/career/services/applications_v2.py` — enforce the `positioning`/`positioning_support` contract before artifacts are accepted.
- Modify: `tests/test_candidate_cv_facts.py` — cover provenance source membership and catalog binding at the content layer.
- Modify: `tests/test_cell_cv_pipeline.py` — cover tamper rejection through the application/cell validation path.
- Modify: `.agents/skills/career-system/SKILL.md` — list the catalog as a canonical positioning reference and state its ranking-only constraint.
- Move: `resultados.json` → `.agents/skills/career-system/references/catalogo_resultados_chave.json`.

### Task 1: Canonical catalog loader and deterministic selector

**Files:**
- Create: `src/career/services/cv_positioning.py`
- Create: `tests/test_cv_positioning.py`
- Move: `resultados.json` → `.agents/skills/career-system/references/catalogo_resultados_chave.json`

**Interfaces:**
- Consumes: `fit_map: dict[str, Any]`, `job_description: str`, and the immutable catalog JSON.
- Produces: `load_catalog(path: Path | None = None) -> list[dict[str, Any]]` and `select_positioning(fit_map: dict[str, Any], job_description: str, *, catalog_path: Path | None = None) -> dict[str, Any] | None`.
- Selection result: `{"catalog_entry_id": int, "area": str, "caso": str, "score": int, "matched_signals": list[str], "catalog_sha256": str}`.

- [ ] **Step 1: Write failing catalog-validation and selection tests**

```python
def test_select_positioning_prefers_planning_case_from_full_fit_context(tmp_path):
    catalog = _write_catalog(tmp_path, [
        _entry(1, "Planejamento integrado e S&OP", "Equilibrar demanda, capacidade e nível de serviço.", "Governança de orçamento e cenários."),
        _entry(2, "Customer success", "Reduzir churn e ampliar adoção.", "Aumentei retenção."),
    ])
    fit_map = {
        "cargo": "Head de Planejamento",
        "dor_central": "Equilibrar capacidade e nível de serviço",
        "keywords_habilidade_ats": [{"keyword": "S&OP", "prioridade": 1}],
        "keywords_vaga": ["forecast"],
        "competencias_vaga": ["planejamento de demanda"],
        "historias_selecionadas": {"principal": {"empresa": "iFood", "resultado": "cenários"}},
        "objecoes": ["experiência setorial"],
    }

    selected = select_positioning(fit_map, "Responsável por forecast, demanda e capacidade.", catalog_path=catalog)

    assert selected["catalog_entry_id"] == 1
    assert selected["caso"] == "Equilibrar demanda, capacidade e nível de serviço."
    assert selected["matched_signals"]


def test_load_catalog_rejects_duplicate_id_and_blank_case(tmp_path):
    catalog = _write_catalog(tmp_path, [_entry(1, "Planejamento", "", "cenários"), _entry(1, "Operações", "Escalar operação", "eficiência")])

    with pytest.raises(ValidationFailure, match="catalog"):
        load_catalog(catalog)
```

- [ ] **Step 2: Run tests to verify they fail for missing module**

Run: `pytest tests/test_cv_positioning.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'career.services.cv_positioning'`.

- [ ] **Step 3: Move the source and implement the minimal selector**

Run `git mv resultados.json .agents/skills/career-system/references/catalogo_resultados_chave.json`. In `cv_positioning.py`, define `CATALOG_PATH`, a `CatalogEntry` typed dictionary, `normalize_tokens`, `load_catalog`, `_context_signals`, `_score_entry`, and `select_positioning`.

Use these precise rules in `_context_signals`:

```python
return [
    ("cargo", str(fit_map.get("cargo") or ""), 5),
    ("dor_central", str(fit_map.get("dor_central") or ""), 4),
    ("keywords_ats", _keywords(fit_map.get("keywords_habilidade_ats")), 3),
    ("keywords_vaga", _strings(fit_map.get("keywords_vaga")), 2),
    ("competencias_vaga", _strings(fit_map.get("competencias_vaga")), 2),
    ("historias_objecoes", _nested_strings(fit_map, ("historias_selecionadas", "objecoes")), 1),
    ("descricao_vaga", job_description, 1),
]
```

Score intersections against `area` and `casos`. Only after equal primary scores, count matches against `resultado_chave`; do not include its text in the returned mapping. Return `None` if no area/case intersection exists.

- [ ] **Step 4: Run focused tests to verify catalog behavior**

Run: `pytest tests/test_cv_positioning.py -v`

Expected: PASS, including selection, no-match fallback, duplicate/empty-field rejection, result-key tiebreaking, and lower-ID final tiebreaking.

- [ ] **Step 5: Commit the isolated selector**

```bash
git add src/career/services/cv_positioning.py tests/test_cv_positioning.py .agents/skills/career-system/references/catalogo_resultados_chave.json
git commit -m "feat: add deterministic CV positioning selector"
```

### Task 2: Use the positioning case in generated summaries and provenance

**Files:**
- Modify: `src/career/services/cv_content.py`
- Modify: `tests/test_candidate_cv_facts.py`

**Interfaces:**
- Consumes: `cv_positioning.select_positioning(fit_map, job_description)` from Task 1.
- Produces: `_build_summary(selected, fit_map, *, positioning: dict[str, Any] | None, language: str) -> tuple[str, list[dict[str, Any]]]` and `positioning_support` in `cv_content.json`.
- Provenance source name: `positioning_catalog`; provenance kind: `positioning_catalog`; claim key: `claim_provenance["positioning"]`.

- [ ] **Step 1: Write failing CV-content tests for the new output contract**

```python
def test_cv_payload_emits_catalog_case_but_not_catalog_result_key(monkeypatch, tmp_path):
    monkeypatch.setattr(cv_positioning, "CATALOG_PATH", _catalog_with_distinctive_result_key(tmp_path))
    payload = _build_payload_for_planning_job()

    assert payload["positioning"]["caso"] in payload["summary"]
    assert payload["positioning_support"]["catalog_entry_id"] == payload["positioning"]["catalog_entry_id"]
    assert "R$ 999 milhões inventados" not in payload["summary"]
    assert all("R$ 999 milhões inventados" not in item["summary_fragment"] for item in payload["summary_support"])
    assert payload["claim_provenance"]["positioning"] == payload["positioning_support"]["evidence_id"]
```

Also add a no-match test that asserts `positioning is None` and that the legacy opening is retained.

- [ ] **Step 2: Run the new tests to verify the generated payload lacks positioning**

Run: `pytest tests/test_candidate_cv_facts.py -v`

Expected: FAIL because `cv_content.json` has no `positioning` and `_build_summary` has no `positioning` parameter.

- [ ] **Step 3: Integrate selection, summary text, and canonical evidence**

In `_build_cv_payload`, read `active.job_description_path` as UTF-8 and call `select_positioning(fit_map, job_description)`. Pass the selection to `_build_summary` and write `positioning` plus `positioning_support` into the payload.

For Portuguese, when selection exists, compose the opening exactly as:

```python
opening = f"Busco posição de {cargo} para {positioning['caso']}"
summary = f"{opening}, apoiado por {first} e {second}."
```

For English, preserve the current localized template until a separately approved English positioning copy exists; still emit the selection and provenance but do not inject Portuguese text into an English CV.

Extend `_attach_canonical_provenance` with `POSITIONING_CATALOG_PATH`. Add it to `metadata.candidate_facts.sources` only for payloads containing a selection, bind the selected `caso` to the catalog entry ID, and write that evidence ID to both `positioning_support.evidence_id` and `claim_provenance.positioning`. Do not change `provenance.candidate_facts_revision()`: the catalog affects CV positioning, not FIT_MAP facts.

- [ ] **Step 4: Run focused provenance and regression tests**

Run: `pytest tests/test_candidate_cv_facts.py tests/test_cv_positioning.py -v`

Expected: PASS. Confirm the catalog's result-key phrase is absent from `summary`, `summary_support`, and all experience bullets.

- [ ] **Step 5: Commit summary integration**

```bash
git add src/career/services/cv_content.py tests/test_candidate_cv_facts.py
git commit -m "feat: compose CV summary from positioning case"
```

### Task 3: Enforce positioning integrity through application validation

**Files:**
- Modify: `src/career/services/cv_content.py`
- Modify: `src/career/services/applications_v2.py`
- Modify: `tests/test_cell_cv_pipeline.py`

**Interfaces:**
- Consumes: `positioning`, `positioning_support`, and `claim_provenance.positioning` emitted in Task 2.
- Produces: `validate_positioning_contract(payload: dict[str, Any]) -> None` in `cv_content.py`, invoked by both `validate_canonical_provenance` and `_validate_cv_content_contract`.

- [ ] **Step 1: Write failing tamper and contract tests**

```python
def test_cell_cv_provenance_rejects_tampered_positioning_case(cell_context, valid_cv_content):
    valid_cv_content["positioning"]["caso"] = "Caso adulterado"

    with pytest.raises(ValidationFailure, match="positioning"):
        cv_content.validate_canonical_provenance(
            valid_cv_content,
            fit_map=cell_context.fit_map,
            fit_map_path=cell_context.fit_map_path,
            fit_map_sha256=cell_context.fit_map_sha256,
        )
```

Add cases that remove `positioning_support`, alter `catalog_sha256`, omit the case from the Portuguese summary, and put the catalog result-key phrase in a summary fragment. Retain a legacy fixture with `positioning: null` as valid.

- [ ] **Step 2: Run tests to prove current validators accept the invalid artifact**

Run: `pytest tests/test_cell_cv_pipeline.py -k positioning -v`

Expected: FAIL because the new assertions do not yet find a positioning validation error.

- [ ] **Step 3: Implement shared contract and provenance validation**

Implement `validate_positioning_contract` to reload `cv_positioning.load_catalog()`, require the selected ID/area/caso/hash to exactly match the canonical entry, require a matching `positioning_support` and `claim_provenance.positioning`, and require the case in `summary`/`resumo` for Portuguese selections.

In `validate_canonical_provenance`, accept exactly the base canonical sources for `positioning is None`, and the base sources plus `positioning_catalog` otherwise. Verify the hash/path of every declared source and call `require` for the `positioning_catalog` evidence. In `_validate_trusted_renderer_values`, recompute selection using `metadata.job_description_path`, verify it equals the persisted positioning, and recompute the expected summary with the same positioning.

Call `cv_content.validate_positioning_contract(payload)` in `applications_v2._validate_cv_content_contract` immediately after non-empty summary validation, so both legacy and cellular application paths block corrupted payloads.

- [ ] **Step 4: Run positioning, CV-pipeline, and full relevant regression tests**

Run: `pytest tests/test_cv_positioning.py tests/test_candidate_cv_facts.py tests/test_cell_cv_pipeline.py tests/test_custom_cv_generation.py -v`

Expected: PASS. Then run `npm run cv:validate-content` against a generated active CV only if an active FIT_MAP exists; otherwise skip that command without creating state.

- [ ] **Step 5: Commit validation coverage**

```bash
git add src/career/services/cv_content.py src/career/services/applications_v2.py tests/test_cell_cv_pipeline.py
git commit -m "feat: validate CV positioning provenance"
```

### Task 4: Document the canonical reference and verify repository behavior

**Files:**
- Modify: `.agents/skills/career-system/SKILL.md`
- Modify: `docs/superpowers/specs/2026-07-29-cv-positioning-catalog-design.md` only if implementation discovers a design discrepancy.

**Interfaces:**
- Consumes: canonical file and behavior completed by Tasks 1–3.
- Produces: an operational rule that future CV agents load the positioning catalog only for customized CV summaries and never treat `resultado_chave` as a candidate assertion.

- [ ] **Step 1: Write a documentation-oriented test assertion**

```python
def test_positioning_catalog_is_a_declared_canonical_reference():
    skill = Path(".agents/skills/career-system/SKILL.md").read_text(encoding="utf-8")

    assert "catalogo_resultados_chave.json" in skill
    assert "não é fonte de alegação" in skill
```

Place this in `tests/test_cv_positioning.py` so the operational contract cannot silently drift.

- [ ] **Step 2: Run the test to verify the rule is not documented yet**

Run: `pytest tests/test_cv_positioning.py::test_positioning_catalog_is_a_declared_canonical_reference -v`

Expected: FAIL because `SKILL.md` does not yet name the catalog.

- [ ] **Step 3: Add the canonical-reference instruction**

Add the catalog after the existing candidate evidence references in `.agents/skills/career-system/SKILL.md`, stating that customized CV generation uses it to select the positioning case from FIT_MAP and job context; `resultado_chave` is only a ranking signal and cannot be emitted as a candidate result.

- [ ] **Step 4: Run final verification**

Run: `pytest tests/test_cv_positioning.py tests/test_candidate_cv_facts.py tests/test_cell_cv_pipeline.py tests/test_custom_cv_generation.py -v`

Expected: PASS. Also run `git diff --check` and `git status --short` to confirm the root-level `resultados.json` is absent and only intended files changed.

- [ ] **Step 5: Commit documentation and review the branch**

```bash
git add .agents/skills/career-system/SKILL.md tests/test_cv_positioning.py
git commit -m "docs: document CV positioning catalog"
```

If repository identity is still unconfigured, leave the changes unstaged, report the precise Git error, and do not configure an identity without the user's authorization.

## Plan Self-Review

- Source placement, validation, deterministic selection, summary composition, provenance, fallback, and documentation each map to Tasks 1–4.
- The tests explicitly cover invalid schema, selection, result-key tiebreaking, no-match fallback, catalog leakage, and tampered provenance.
- Interfaces are consistent: `select_positioning` produces the `positioning` object consumed by `_build_summary`, `validate_positioning_contract`, and the cell/application validators.
- The plan does not modify FIT_MAP, unrelated deliverables, or the catalog content.
