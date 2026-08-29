# CV Target Coherence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Garantir que o CV gerado para uma vaga use somente experiências coerentes com o FIT_MAP, priorize no resumo as experiências-alvo e materialize keywords MIS sustentadas sem alterar a arquitetura celular.

**Architecture:** A correção permanece em `cv_content.py`, na seleção/materialização determinística do conteúdo. O seletor só usa fallback para completar uma lista curta; o matcher resolve empresa e cargo para não confundir experiências da mesma empresa; o resumo deriva a prioridade das experiências das keywords top8 do FIT_MAP e mantém `summary_fragments` como fonte factual. As cláusulas ATS continuam curadas no mesmo catálogo e são aplicadas apenas quando `experiencia_alvo` corresponde à experiência.

**Tech Stack:** Python 3, pytest, JSON canônico de fatos do candidato, `cv_content.py`, `review_output.py` e pipeline celular existente.

**Spec:** `docs/roadmap.md` — `CV-019`.

## Global Constraints

- Toda vaga continua com escopo explícito por `application_id`.
- FIT_MAP, conteúdo, DOCX, manifests e receipts continuam imutáveis e versionados por tentativa.
- O resumo não publica `dor_central`; ela apenas orienta posicionamento.
- Bullet 1 permanece responsabilidade, bullet 2 posicionamento/mecanismo/caso e bullet 3 resultado quantitativo.
- Cláusulas ATS só podem ser adicionadas quando a experiência-alvo e a evidência canônica sustentarem o termo.
- Nenhuma entrega OneDrive é válida sem `review_output.py` aprovado e `cv:deliver` retornando `status=delivered`.

---

### Task 1: Reproduzir as regressões do caso Vivo

**Files:**
- Modify: `tests/test_cv_experience_selection.py`

**Interfaces:**
- Consumes: `_select_experiences`, `_summary_support_pairs` e `_materialize_experience`.
- Produces: testes que falham no comportamento atual e protegem seleção, resumo e keywords MIS.

- [x] **Step 1: Write the failing tests**

Adicionar uma regressão com o FIT_MAP reduzido da Vivo:

```python
def test_vivo_fit_map_does_not_append_customer_success_when_targets_are_sufficient():
    fit_map = {
        "historias_selecionadas": {
            "principal": {"empresa": "WeHandle"},
            "secundaria": {"empresa": "iFood — Diretor de Operações"},
            "terceira": {"empresa": "Trifil — Coordenador de Inteligência Comercial"},
        },
        "keywords_habilidade_ats": [
            {"prioridade": 1, "keyword": "Gestão de MIS", "experiencia_alvo": "Trifil — Coordenador de Inteligência Comercial"},
            {"prioridade": 2, "keyword": "Inteligência Operacional", "experiencia_alvo": "iFood — Diretor de Operações"},
            {"prioridade": 3, "keyword": "Business Intelligence", "experiencia_alvo": "Trifil — Coordenador de Inteligência Comercial"},
            {"prioridade": 4, "keyword": "Dashboards Gerenciais", "experiencia_alvo": "iFood — Head de Operações"},
            {"prioridade": 5, "keyword": "Automação de Relatórios", "experiencia_alvo": "Trifil — Coordenador de Inteligência Comercial"},
            {"prioridade": 6, "keyword": "Governança de Dados", "experiencia_alvo": "WeHandle — Head de Operações"},
            {"prioridade": 7, "keyword": "Análise de Performance", "experiencia_alvo": "WeHandle — Head de Operações"},
            {"prioridade": 8, "keyword": "Indicadores de Contact Center", "experiencia_alvo": "WeHandle — Head de Operações"},
        ],
    }

    selected_ids = [item["id"] for item in _select_experiences(fit_map)]

    assert "renault_cs" not in selected_ids
    assert set(selected_ids) == {
        "wehandle_head_operacoes",
        "ifood_diretor_operacoes",
        "ifood_head_operacoes",
        "trifil_sop",
        "trifil_inteligencia_comercial",
        "trifil_expedicao",
    }
```

Adicionar também um teste que passe o mesmo FIT_MAP à priorização do resumo e exija `trifil_inteligencia_comercial` e `wehandle_head_operacoes` como os dois suportes:

```python
def test_summary_support_prefers_vivo_mis_target_experiences():
    selected = cv_content._select_experiences(_vivo_mis_fit_map())
    pairs = cv_content._summary_support_pairs(selected, fit_map=_vivo_mis_fit_map())

    assert [item[0] for item in pairs] == [
        "faturamento anual de R$80M para R$120M com algoritmo de alocação de estoque",
        "redução de 13% no custo por atendimento e impacto de 15% na margem bruta",
    ]
```

Adicionar uma regressão de materialização para as oito keywords top8 e exigir que cada termo apareça no texto da experiência-alvo e que nenhum termo seja injetado em `renault_cs`.

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest -q tests/test_cv_experience_selection.py tests/test_candidate_cv_facts.py
```

Expected: FAIL because `_select_experiences` appends `renault_cs` after six matches and `_summary_support_pairs` ignores `fit_map`.

### Task 2: Implement the minimal target-coherence fix

**Files:**
- Modify: `src/career/services/cv_content.py:543-585`
- Modify: `src/career/services/cv_content.py:927-1002`
- Modify: `src/career/services/cv_content.py:829-858`

**Interfaces:**
- Consumes: existing FIT_MAP target mappings and candidate facts.
- Produces: `_select_experiences(fit_map)` without an unnecessary fallback, `_experience_matches_target` sensitive to role when companies repeat, `_summary_support_pairs(..., fit_map=...)` target-aware, and MIS clauses in the existing Portuguese ATS catalog.

- [x] **Step 1: Stop fallback once the minimum is already met**

Envolver o laço de fallback com uma condição explícita:

```python
if len(selected_ids) < 5:
    for item in remaining:
        if item["id"] not in selected_ids:
            selected_ids.append(item["id"])
        if len(selected_ids) >= 5:
            break
```

- [x] **Step 2: Make company-and-role matching unambiguous**

When `experiencia_alvo` contains company and role, require role compatibility, accepting simple bilingual role equivalents already present in the text (for example, `S&OP Coordinator` and `Coordenador de S&OP`). Preserve company-only matching when the target contains only a company.

- [x] **Step 3: Make summary support rank target coverage first**

Adicionar `fit_map: dict[str, Any] | None = None` a `_summary_support_pairs`, contar quantas keywords top8 apontam para cada experiência, desempatar pela menor prioridade e só depois completar com `selectors.summary_priority`. Alterar `_build_summary` para chamar:

```python
support_pairs = _summary_support_pairs(
    selected,
    fit_map=fit_map,
    language=language,
)
```

Manter a assinatura compatível para chamadas legadas sem `fit_map`, preservando a prioridade existente nesse caso.

- [x] **Step 4: Add only evidence-backed MIS clauses**

Acrescentar ao `_PORTUGUESE_ATS_CLAUSES` as entradas para `gestão de MIS`, `inteligência operacional`, `business intelligence`, `dashboards gerenciais`, `automação de relatórios`, `governança de dados`, `análise de performance` e `indicadores de contact center`. As frases não podem conter métricas nem duplicar o resultado do bullet 3; a função existente continua restringindo a aplicação à experiência-alvo.

- [x] **Step 5: Run the focused tests**

Run:

```bash
pytest -q tests/test_cv_experience_selection.py tests/test_candidate_cv_facts.py tests/test_cv_positioning.py
```

Expected: PASS, incluindo as regressões novas e os testes de seleção/fatos existentes.

### Task 3: Validate project contracts and the Vivo artifact

**Files:**
- Modify: `docs/roadmap.md`
- Validate: `workspaces/vagas_bot_01/state/applications_v2/local_20260828T030856_526366_vivo_telef_nica_brasil_ddad743f/`

**Interfaces:**
- Consumes: código corrigido, FIT_MAP Vivo e run `run_0aaaaaba199c4124864c9073d22ee4d7`.
- Produces: evidência de que o CV regenerado é da Vivo, sem Customer Success indevido, com gate objetivo aprovado antes de qualquer entrega.

- [x] **Step 1: Run repository validation**

```bash
npm run validate:structure
npm run runtime:verify -- --strict
git diff --check
```

- [x] **Step 2: Regenerate the Vivo content and DOCX through the official scoped path**

Use the existing `application_id` and the official cellular commands, without a new intake. The original run was immutable against the current `candidate_facts_revision`; the first same-application replacement run reached the review gate but exposed a residual fallback issue. The final validation used fresh run `run_84637545b10946f29c463bbadcb4d2fc`, preserving all prior runs and rebinding current canonical facts. No `cv_content.json`, DOCX, manifest or database was edited manually.

- [x] **Step 3: Execute the mandatory final review**

```bash
python3 scripts/review_output.py --kind cv --artifact outputs/<cv>.docx --fit-map .career-state/applications_v2/<application_id>/fit_map.json --registry .career-state/applications_v2/<application_id>/derived/keyword_ats_registry.json --report outputs/_tmp/output_review_report.json
```

The cellular `review_cv`/`cv:approve` returned `approved_for_delivery=true`, ATS top8 `8.0/8`, zero blockers and zero `missing_unexplained`. The standalone `review_output.py` confirmed the same ATS result and no missing top8 terms; before delivery it reported only `artifact_exists_in_outputs` because the artifact remained in the immutable cell path. The official `deliver_cv` then returned `status=delivered`, with remote verification confirmed at `onedrive:01_armel/Curriculos/personalizados/felipe_armel_cv_gerente_mis_operacoes_vivo_telefonica_brasil.docx`.

- [x] **Step 4: Update roadmap evidence**

`CV-019` is now `DONE`; the roadmap records the exact final run, artifact revisions and verification commands.

## Execution evidence

- Focused and cellular regression suite: `82 passed`.
- Repository checks: `npm run validate:structure`, `npm run runtime:verify -- --strict` and `git diff --check` passed.
- Final same-application run: `run_84637545b10946f29c463bbadcb4d2fc`.
- Final artifacts: FIT_MAP `447ec0332bb1`, CV content `14152b7f690d`, DOCX `025414ffaa29`, review `db0516c30d93`.
- Final experience set excludes `renault_cs` and includes `trifil_inteligencia_comercial`; final cellular review is approved with ATS top8 `8.0/8`.
