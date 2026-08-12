# Bug de seleção de experiências no CV — composição por cota fixa em vez de aderência

**Data:** 2026-08-05
**Autor:** Hermes Agent (profile `vagas_bot_02`)
**Contexto:** análise da vaga **Vero Internet — Gerente de experiência do cliente** (perfil CX / `cx_saas_operations`)

---

## 1. O problema

Ao gerar o CV para uma vaga, o seletor de experiências do pipeline (`src/career/services/cv_content.py` → `_select_experiences`) deve montar uma lista de 4 a 8 experiências que façam sentido para a vaga. Ele **não faz isso** de forma aderente — e isso se manifestou claramente na vaga da Vero.

### Sintoma observado

Para a Vero (perfil **Customer Experience**), o CV inicial trouxe como 5ª experiência o cargo **Coordenador de Expedição (Trifil)** — logística de armazém, totalmente fora da dor central da vaga — enquanto deixava de fora a **Renault — Gerente de Customer Success** (experiência claramente mais aderente a CX, e que estava disponível na base).

### Causa raiz no código

Em `src/career/services/cv_content.py`, `_select_experiences()` faz o seguinte:

```python
def _select_experiences(fit_map):
    selected_ids = []
    story_companies = []   # empresas das 3 histórias selecionadas no FIT_MAP
    targets = [experiencia_alvo das top8 keywords]
    # 1. seleciona por match de história (FIT_MAP) ou target de keyword
    for entry in _facts_experiences():
        if match(story_companies) or match(targets):
            selected_ids.append(entry["id"])
    # 2. SE não atingiu a cota de 5, preenche com uma LISTA FIXA e chumbada
    fallback_priority = load_canonical_cv_facts()["selectors"]["fallback_experience_priority"]
    for item_id in fallback_priority:
        if item_id not in selected_ids:
            selected_ids.append(item_id)
        if len(selected_ids) >= 5:
            break
    ...
```

O problema está na **etapa 2**: quando a vaga não produz 5 matchs naturais (histórias + targets), o código **ignora totalmente a aderência à vaga** e apenas sobe uma lista fixa e hardcoded, em ordem rígida, até completar a cota de 5.

### A lista chumbada (em `candidate_cv_facts.json` → `selectors.fallback_experience_priority`)

```
1. ifood_diretor_operacoes
2. ifood_head_operacoes
3. vivareal_planejamento_operacoes
4. trifil_expedicao          ← vem AQUI (logística de armazém)
5. trifil_sop
6. trifil_inteligencia_comercial
7. wehandle_head_operacoes
8. renault_cs                ← a mais aderente a CX vem POR ÚLTIMO
```

**Detalhe revelador:** para um perfil de CX, o fallback "pega" a Trifil Expedição (4ª posição) e **deixa a Renault — Gerente de Customer Success (8ª posição, a mais aderente) de fora**, simplesmente por causa da ordem fixa.

---

## 2. Por que isso é um bug (e não "só não ideal")

1. **É chumbado** — não há lógica de "encontrar a experiência que faz sentido". A ordem é fixa e independente do `job_family`, da `dor_central` ou das keywords da vaga.

2. **Não compila por relevância** — o código não avalia qual das experiências restantes melhor cobre as top8 keywords / a dor central. Ele só preenche a cota numérica de 5 na ordem fixa.

3. **Prova empírica do defeito** — a Renault *estava disponível* e *era a mais aderente a CX*, mas ficou em 8º no fallback. Na vaga da Vero, o seletor só incluiu a Renault porque **eu forcei manualmente** (adicionei uma keyword ATS top8 com `experiencia_alvo: "Renault do Brasil"` no fit_map). Sem esse hack manual, o bug teria escolhido a Trifil Expedição e ignorado a Renault para sempre.

4. **Custo de manutenção** — toda nova vaga exige esse contorno manual por vaga (editar o fit_map). Não escala e é frágil.

---

## 3. Visão de solução (caminho A — correção de raiz)

O seletor deveria **completar a cota com base em aderência à vaga**, não numa lista fixa. Proposta:

### 3.1. Pontuar cada experiência restante por aderência

Para cada experiência **não** já selecionada pelas histórias/targets, calcular um score de aderência usando os dados que já existem na base:

- **`focus_terms`** de cada experiência (já presente em `candidate_cv_facts.json` — hoje **subutilizado**);
- sobreposição com as **top8 keywords ATS** da vaga;
- sobreposição com a **`dor_central`** da vaga;
- bônus quando o **`job_family`** da vaga (ex: `cx_saas_operations`) casa com o foco natural da experiência (ex: Renault = Customer Success).

### 3.2. Completar a cota pela aderência, não pela ordem fixa

```python
# pseudocódigo do novo fluxo
selected = match_por_historias_e_targets(...)   # etapa atual 1
if len(selected) < 5:
    candidates = [exp for exp in _facts_experiences() if exp["id"] not in selected]
    candidates.sort(key=lambda exp: score_aderencia(exp, fit_map), reverse=True)
    for exp in candidates:
        selected.append(exp["id"])
        if len(selected) >= 5:
            break
```

Assim, um CV de CX pegaria: **Renault CS** (focus: conversão, leads, Customer Success) → depois VivaReal/WeHandle/iFood → e **nunca** uma Trifil Expedição antes da Renault, para um perfil de CX.

### 3.3. Fallback fixo vira só "último recurso"

A lista `fallback_experience_priority` poderia permanecer apenas como desempate final, **depois** da seleção por aderência — não como a mecânica principal de completar a cota.

### 3.4. Dados necessários já existem

`candidate_cv_facts.json` já tem, por experiência:
- `id`, `company`, `role`, `period`, `order`
- `focus_terms` (lista de termos de foco)
- `scope_bullet`, `result_bullet`, `leverage.{default, project_management, cx_saas_operations, ...}`

Portanto, a correção é **majoritariamente no código** (`_select_experiences`), sem exigir novos dados.

---

## 4. Bloqueador de implementação (ambiental)

Ao tentar implementar, descobri que o **mount raiz do projeto `/workspace/candidaturas` está read-only (ro)** — e isso inclui:
- `src/` (onde fica `cv_content.py` → `_select_experiences`)
- `.agents/` (onde fica `candidate_cv_facts.json`)

Só estes sub-mounts são graváveis: `.career-state`, `outputs`, `inbox`.

Confirmação:
```
touch src/career/services/.write_test  → Read-only file system
touch .agents/skills/.write_test       → Read-only file system
```
- Usuário atual: `hermes` (uid 10000), **sem sudo** (`sudo: command not found`).
- Não é repositório git (sem `.git`), então não há origem rw óbvia sincronizada.

**Por isso este documento está em `outputs/` (sub-mount gravável)** e não em `docs/` ou raiz.

---

## 5. Como destravar (decisão necessária)

Para aplicar o caminho A de forma durável (vale para os 2 agentes), é preciso tornar `src/` (e idealmente `.agents/`) graváveis. Opções:

1. **Remontar o volume como rw** no host (ex: `mount -o remount,rw /workspace/candidaturas`, ou ajustar o `docker run -v ... -o rw` / `--read-write` que monta o projeto).
2. **Indicar a origem rw** — se houver outra cópia gravável do projeto (MacBook, repositório, outro path), aplicar a mudança lá e sincronizar.
3. **Aplicar o patch manualmente** — eu entrego o diff pronto de `_select_experiences`, e a pessoa aplica quando o mount estiver rw.

---

## 6. Escopo da correção (o que mudar de fato)

**Arquivo:** `src/career/services/cv_content.py` → função `_select_experiences()`.

**Mudança:** substituir o preenchimento por lista fixa (etapa 2) por preenchimento por score de aderência (focus_terms × top8 keywords + dor_central + job_family), mantendo o fallback fixo apenas como desempate final.

**Opcional (dados):** reordenar `fallback_experience_priority` para refletir foco setorial (ex: Renault antes de Trifil em contextos de CX) — mas isso é um paliativo; o caminho A resolve a raiz sem depender da ordem.

**Validação:** regenerar o CV da Vero e confirmar que a Renault aparece (não a Trifil) sem hack manual no fit_map; e garantir que as outras vagas continuem passando no gate ATS (top8 ≥ 5,2, zero `missing_unexplained`).

---

## 7. Resumo

| Aspecto | Status |
|---|---|
| Bug identificado | Seletor completa cota de 5 por **lista fixa**, ignorando aderência à vaga |
| Prova | Vaga CX da Vero → escolheu Trifil Expedição, ignorou Renault CS (mais aderente) |
| Correção | Selecionar por **score de aderência** (focus_terms × keywords + dor_central + job_family) |
| Vale para os 2 agentes? | Sim — código e dados são compartilhados (fonte única `/workspace/candidaturas`) |
| Bloqueador | Mount de `src/` e `.agents/` está **read-only**; sem sudo; sem git |
| Ação necessária | Tornar `src/` gravável OU indicar origem rw OU aplicar patch manual |

---

*Documento gerado automaticamente pelo agente. Caminho de escrita em `outputs/` por ser sub-mount gravável.*
