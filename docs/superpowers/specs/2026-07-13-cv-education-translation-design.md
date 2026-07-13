# CV Education Translation — Design Doc

## Problema

Ao gerar CVs em inglês, duas entradas de educação têm tradução incorreta:

1. `"MBA Corporate Strategy — BSP Business School São Paulo"` — deveria ser `"Specialization Certificate in Corporate Strategies — BSP Business School São Paulo"` em inglês (conforme regra em `perfil_restricoes.md:108-112`)
2. `"Engenheiro Químico — Faculdades Oswaldo Cruz"` — deveria ser `"B.Sc. Chemical Engineering — Faculdades Oswaldo Cruz"` (tradução literal incorreta)

## Causa raiz

`DEFAULT_EDUCATION` em `src/career/services/cv_content.py:198-202` é uma lista única, compartilhada entre as chaves `education` (EN) e `formacao` (PT) do `cv_content.json`. Não há diferenciação por idioma.

O renderizador DOCX (`generate_custom_cv.js:154`) já alterna entre `education` e `formacao` conforme o idioma, mas ambas recebem o mesmo dado.

## Abordagem escolhida

Listas separadas por idioma no código-fonte, com detecção de idioma no builder.

## O que muda

### 1. Constantes em `src/career/services/cv_content.py`

Substituir `DEFAULT_EDUCATION` por `DEFAULT_EDUCATION_PT` e `DEFAULT_EDUCATION_EN`:

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

### 2. Lógica em `build_current_cv_content()` (linhas 257-258)

Detectar idioma no `fit_map` e popular cada chave com a lista correta:

```python
is_en = str(fit_map.get("idioma") or "").strip().lower().startswith("en")
education_list = DEFAULT_EDUCATION_EN if is_en else DEFAULT_EDUCATION_PT

# ...
"education": list(education_list),
"formacao": list(DEFAULT_EDUCATION_PT),
```

O campo `fit_map.idioma` já é usado pela função `_output_name()` na linha 558 para decidir o sufixo `_en` do nome do arquivo.

## O que não muda

- Contrato: `cv_content.json.education` continua `["string"]`
- Renderizador DOCX: `generate_custom_cv.js` já lê `education` quando `lang === "en"` e `formacao` quando `pt-BR`
- CLI, validadores, registro ATS: nenhuma alteração
- CV geral (`general_cv_content.json`): não passa por este builder

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Vaga em português | `education = formacao = PT` (idêntico ao hoje) |
| Vaga em inglês | `education = EN`, `formacao = PT` |
| `fit_map` sem `idioma` | Fallback para PT (seguro, mesma lógica de `_output_name`) |

## Risco

Mínimo. Troca de dado na fonte. Nenhuma mudança de fluxo, contrato ou dependência.
