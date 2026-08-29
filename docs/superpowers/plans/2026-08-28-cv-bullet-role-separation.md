# CV Bullet Role Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Garantir que todo CV em modo `concise` use o bullet 2 para posicionamento/mecanismo/caso e reserve o bullet 3 para o resultado quantitativo canônico.

**Architecture:** A materialização dos fatos canônicos vai sanitizar o texto de `leverage` antes de usá-lo no bullet 2, removendo cláusulas de resultado quantitativo ou de consequência que repetem o bullet 3. As cláusulas ATS controladas continuarão sendo adicionadas somente quando houver evidência e não conterão métricas no bullet 2. O contrato do pacote `cv_content` também validará os papéis dos três bullets, para impedir que agentes ou reparos publiquem conteúdo fora da regra.

**Tech Stack:** Python, pytest, `candidate_cv_facts.json`, FIT_MAP por candidatura e validação existente de `cv_content`.

**Spec:** `docs/roadmap.md`, item `CV-016`, e as regras de experiência em `.agents/skills/cv-generator/SKILL.md`.

## Global Constraints

- A fonte factual continua sendo `.agents/skills/career-system/references/candidate_cv_facts.json`.
- Bullet 2 deve permanecer ligado à experiência e às keywords-alvo; não criar resultado, número ou experiência.
- Bullet 3 deve preservar `result_bullet` canônico e conter pelo menos uma métrica defensável.
- O modo `concise` continua usando exatamente três bullets por experiência.
- O texto ATS não pode relaxar `missing_unexplained`, nem transformar catálogo de posicionamento em fonte factual.
- Não editar DOCX ou `cv_content.json` gerado manualmente; testar a fonte e regenerar somente por application_id quando houver candidatura-alvo.

---

### Task 1: Reproduzir a duplicação com testes regressivos

**Files:**
- Modify: `tests/test_cv_experience_selection.py`
- Read: `.agents/skills/career-system/references/candidate_cv_facts.json`

**Interfaces:**
- Consumes: `cv_content._materialize_experience` e os oito registros de experiência canônicos.
- Produces: testes que falham quando o bullet 2 contém uma faixa/impacto quantitativo ou repete o resultado, e quando o bullet 3 não tem métrica.

- [x] **Step 1: Write the failing test**

Adicionar uma regressão para `ifood_diretor_operacoes` em português e uma verificação parametrizada para experiências canônicas, usando estas asserções:

```python
result = cv_content._materialize_experience(experience, "operations", language="pt-BR")
assert "400 para 800" not in result["bullets"][1]
assert "400 para 800" in result["bullets"][2]
assert result["bullets"][1].casefold() != result["bullets"][2].casefold()
```

Adicionar também uma regressão para a cláusula ATS `Multi-location Operations`, exigindo que a keyword apareça sem copiar a faixa `400 to 800` para o bullet 2.

- [x] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_cv_experience_selection.py -k 'bullet or materialize'`

Expected: FAIL porque a seleção atual usa `leverage` integralmente e porque as cláusulas inglesas com faixa/percentual são anexadas ao bullet 2.

### Task 2: Corrigir a materialização dos papéis dos bullets

**Files:**
- Modify: `src/career/services/cv_content.py:679-850`
- Test: `tests/test_cv_experience_selection.py`

**Interfaces:**
- Consumes: `entry.leverage`, `entry.result_bullet`, `job_family` e `ats_keywords`.
- Produces: `_positioning_bullet(...)`, `_contains_quantitative_result(...)` e materialização com bullet 2 não quantitativo e bullet 3 canônico.

- [x] **Step 1: Write the minimal implementation**

Implementar a seleção da variante `leverage[job_family]`/`default`, recortando cláusulas após conectores de consequência (`— o que`, `gerando`, `resultando`) e descartando trechos com moeda, percentual ou faixa `de X para Y`/`from X to Y`. Falhar com `ValidationFailure` se `result_bullet` não contiver métrica.

Alterar `_apply_defensible_portuguese_ats_keywords` e `_apply_defensible_english_ats_keywords` para inserir somente texto sem métrica no bullet 2. As cláusulas ATS devem conter a keyword e descrever método/caso; cláusulas com número não podem ser anexadas ao bullet 2.

- [x] **Step 2: Run focused tests**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_cv_experience_selection.py -k 'bullet or materialize'`

Expected: PASS.

### Task 3: Fechar o contrato no validador e na documentação

**Files:**
- Modify: `src/career/services/applications_v2.py:1859-1918`
- Modify: `.agents/skills/cv-generator/SKILL.md`
- Modify: `.agents/skills/career-system/SKILL.md`
- Test: `tests/test_cv_experience_selection.py`

**Interfaces:**
- Consumes: os três bullets já materializados no `cv_content.json`.
- Produces: bloqueio explícito para bullet 2 quantitativo, bullet 3 sem métrica e duplicação literal entre bullets 2 e 3.

- [x] **Step 1: Add validator coverage**

Estender `_validate_concise_bullet2` com a mesma detecção de métrica usada pelo contrato: bullet 2 não pode conter resultado quantitativo, bullet 3 precisa conter métrica e os textos normalizados não podem ser iguais.

- [x] **Step 2: Document the rule**

Registrar na skill canônica que, no modo conciso, bullet 2 é posicionamento/mecanismo/caso derivado da evidência e keywords da experiência, enquanto o resultado `ação → resultado → de → para` fica no bullet 3.

- [x] **Step 3: Run contract tests**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_cv_experience_selection.py tests/test_cv_language_and_repair_hardening.py tests/test_review_language.py`

Expected: PASS sem alterar os gates de idioma, proveniência ou ATS.

### Task 4: Verificar a suíte e encerrar o item do roadmap

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `docs/superpowers/plans/2026-08-28-cv-bullet-role-separation.md`

- [x] **Step 1: Run the focused CV suite**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_cv_experience_selection.py tests/test_review_language.py tests/test_cell_final_review_regressions.py tests/test_cellular_persistence.py tests/test_reconciliation.py`

Expected: exit code 0, com os testes de separação dos bullets aprovados.

- [x] **Step 2: Run repository checks**

Run: `npm run validate:structure`, `npm run runtime:verify -- --strict` e `git diff --check`.

Expected: exit code 0 e nenhuma mudança fora do código, testes, skills, plano e roadmap listados.

- [x] **Step 3: Close roadmap evidence**

Atualizar `CV-016` e o registro deste plano para `DONE` somente com os comandos acima aprovados. Registrar que nenhuma candidatura viva foi regenerada neste plano por não haver `application_id` solicitado; a correção entra nas próximas gerações dos dois bots.

**Execution evidence (2026-08-28):** the regression tests first failed on the
duplicated `400 para 800`/`400 to 800` range and on a result without a metric.
After the source fix, the focused CV/cellular/reconciliation suite passed
45/45. All eight canonical experiences passed the bullet-role invariant in
PT-BR and English. `npm run validate:structure`,
`npm run runtime:verify -- --strict`, and `git diff --check` also passed.
