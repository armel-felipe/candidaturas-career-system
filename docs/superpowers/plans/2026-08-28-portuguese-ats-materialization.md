# Portuguese ATS Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize supported Portuguese ATS keywords in the canonical CV content so the DOCX review reflects evidence already selected by the FIT_MAP.

**Architecture:** Keep the FIT_MAP as the source of keyword-to-experience targeting. Add a small allowlist of Portuguese clauses in `cv_content.py`; clauses are appended only to the targeted canonical experience and are then measured by the existing text-based coverage gate. Regenerate the Tempo cellular artifacts through `compose_cv`, `render_cv`, and `review_cv`; never patch JSON or DOCX artifacts manually.

**Tech Stack:** Python, pytest, existing cellular application CLI, canonical candidate facts, DOCX review gate.

**Spec:** `docs/roadmap.md` items `CV-015`, `CELLULAR-007`, and `RUNTIME-014`, plus the Portuguese ATS policy in `AGENTS.md`.

## Global Constraints

- The canonical source for code is `src/career/`; profile copies are runtime artifacts only.
- Portuguese ATS wording must be defensible from canonical candidate facts and the application FIT_MAP.
- `missing_unexplained` remains a blocker; do not relax ATS thresholds or edit generated artifacts by hand.
- Every cellular command must include the explicit `application_id` and `run_id`.

### Task 1: Add the failing regression for the Tempo keywords

**Files:**
- Modify: `tests/test_cv_experience_selection.py`
- Read: `.agents/skills/career-system/references/candidate_cv_facts.json`

**Interfaces:**
- Consumes: `cv_content._materialize_experience` and the canonical experience records.
- Produces: a regression proving that the eight Tempo top-eight keywords are literal in targeted Portuguese bullets.

- [x] **Step 1: Write the failing test**

Add a test that calls `_materialize_experience` for the canonical iFood Director, Renault Customer Success, iFood Head, and WeHandle Head experiences with these target mappings:

```python
targets = {
    "planejamento estratégico": "iFood — Diretor de Operações",
    "planejamento orçamentário": "iFood — Diretor de Operações",
    "forecast": "iFood — Diretor de Operações",
    "análise de investimentos": "Renault do Brasil — Gerente de Customer Success",
    "matemática financeira": "Renault do Brasil — Gerente de Customer Success",
    "indicadores de negócio": "iFood — Diretor de Operações",
    "precificação": "iFood — Head de Operações",
    "margens": "WeHandle — Head de Operações",
}
```

Pass each applicable keyword as `ats_keywords` with its target, join the returned bullets, and assert every keyword appears case-insensitively. Also assert the existing canonical result metrics remain present.

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_cv_experience_selection.py -k portuguese`

Expected: FAIL because `_PORTUGUESE_ATS_CLAUSES` contains only `Customer Experience` and `Zendesk`.

### Task 2: Implement the controlled Portuguese clauses

**Files:**
- Modify: `src/career/services/cv_content.py` near `_PORTUGUESE_ATS_CLAUSES`

**Interfaces:**
- Consumes: targeted top-eight entries and `_experience_matches_target`.
- Produces: Portuguese bullets containing only supported literal keywords.

- [x] **Step 1: Add the minimal allowlist**

Extend `_PORTUGUESE_ATS_CLAUSES` with:

```python
"planejamento estratégico": "Conduzi ciclos de planejamento estratégico, conectando cenários operacionais, alocação de recursos e execução.",
"planejamento orçamentário": "Conduzi planejamento orçamentário com acompanhamento de budget e cenários de execução.",
"forecast": "Usei forecast e cenários para alinhar demanda, capacidade e nível de serviço.",
"análise de investimentos": "Apoiei análise de investimentos com modelagem de ROI para decisões de transformação.",
"matemática financeira": "Apliquei conceitos de matemática financeira na análise de ROI e viabilidade econômica.",
"indicadores de negócio": "Acompanhei indicadores de negócio e desempenho para orientar decisões operacionais e financeiras.",
"precificação": "Conduzi análises de precificação para calibrar oferta, demanda e alocação de recursos.",
"margens": "Acompanhei margens e indicadores financeiros para orientar decisões de eficiência operacional.",
```

Keep the existing target check and the single insertion point in bullet 2. Do not add generic keyword text outside a targeted experience.

- [x] **Step 2: Run the focused test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_cv_experience_selection.py -k portuguese`

Expected: PASS, including the existing Customer Experience/Zendesk test and the new Tempo regression.

### Task 3: Regenerate and review the Tempo cellular run

**Files:**
- Application: `local_20260828T030638_322764_tempo_c9561fed`
- Run: `run_5d3a95f1b9074ea9844198db4c51fdc8`

- [x] **Step 1: Repair `compose_cv` in the same run**

Run:

```bash
docker compose exec -T --user 10000:10000 vagas_bot_02 npm run applications:repair -- --application-id local_20260828T030638_322764_tempo_c9561fed --run-id run_5d3a95f1b9074ea9844198db4c51fdc8 --node compose_cv --reason "Materializar keywords ATS portuguesas com clausulas controladas e evidencia canonica."
```

Expected: the repair invalidates CV descendants and regenerates a hashed `cv_content.json`.

- [x] **Step 2: Execute descendants through the cellular runner**

Run:

```bash
docker compose exec -T --user 10000:10000 vagas_bot_02 npm run applications:run -- --application-id local_20260828T030638_322764_tempo_c9561fed --run-id run_5d3a95f1b9074ea9844198db4c51fdc8 --run-agent
```

Expected: `render_cv` and `review_cv` execute from the regenerated content; no direct JSON/DOCX edit is performed.

- [x] **Step 3: Verify the objective review**

Run the same `applications:inspect-run` command with the explicit IDs and inspect the persisted review report. Acceptance requires `review_cv=validated`, `approved_for_delivery=true`, ATS top8 at least `5.2/8`, and zero `missing_unexplained`.

### Task 4: Complete roadmap evidence

- [x] **Step 1: Update `docs/roadmap.md`**

Mark `CV-015` `DONE` only after the focused test, cellular regeneration, and objective review all pass. Record the run ID, review score, and absence of unexplained gaps in the criterion and plan register. The same execution also fixed the registry association and language projection discovered during reconciliation under `CELLULAR-007`.

- [x] **Step 2: Run repository checks**

Run: `git diff --check` and `PYTHONPATH=src .venv/bin/pytest -q tests/test_cv_experience_selection.py tests/test_review_language.py tests/test_cell_final_review_regressions.py`

Expected: exit code 0 and no failures.

**Execution evidence (2026-08-28):** run
`run_5d3a95f1b9074ea9844198db4c51fdc8` for application
`local_20260828T030638_322764_tempo_c9561fed` was repaired at `compose_cv`,
rendered and reviewed again, then delivered. The final review reports
`approved_for_delivery=true`, ATS top8 `8.0/8`, and zero
`missing_unexplained`. Notion page ID `3ca0003f-9481-8124-b1cc-e9fbd801993d`
was created and the official cellular reconciliation returned
`core_package_sealed`. The focused suites passed 38/38.

The same bridge was hardened after an execution-only failure: the cellular
reconciliation script now respects `CAREER_CONTROL_DB_PATH` when `--db` is
omitted. Its regression passed, and the full Tempo reconciliation was rerun
without `--db`, returning `core_package_sealed`.
