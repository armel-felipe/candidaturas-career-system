---
name: unified-job-analysis
description: >
  Fluxo unificado de análise de vaga e registro no Notion. Acionar quando o usuário colar uma vaga (texto, URL da vaga, ou link do LinkedIn),
  mencionar um ID do Notion, ou pedir para analisar e registrar no Notion em uma única execução.
  Esta skill usa o orquestrador `intake:*` para normalizar a origem da vaga antes de career-fit-analysis e Notion.
  Quando acionada, executa o intake, análise, score, keywords e, quando pedido explicitamente, Notion.
---

# Unified Job Analysis

## Gatilhos de ativação

Ativar SEMPRE que o usuário:
- Colar uma descrição de vaga no chat
- Colar um link de vaga (LinkedIn, site da empresa, etc.)
- Dizer "analisa essa vaga" + texto ou link
- Dizer "Notion <ID>" (ex: "Notion 247") ou "vaga Notion <ID>"
- Dizer URL + "registra no Notion" ou "atualiza Notion"
- Dar um link de vaga + "faz a análise e salva no Notion"
- Qualquer combinação que envolva analisar vaga E persistir resultado

## Fluxo completo — executar em ordem, sem pular passos

### Passo 1 — Identificar origem da vaga

| Origem | Ação |
|--------|------|
| Texto colado no chat | Executar `npm run intake:paste -- --company "<empresa>" --role "<cargo>" --text-file <arquivo>` ou `--stdin` |
| URL da vaga do LinkedIn | Executar `npm run intake:linkedin-job -- --url "<url>"` |
| URL de postagem do LinkedIn divulgando vaga | Executar `npm run intake:linkedin-post -- --url "<url>" --company "<empresa>" --role "<cargo>"` |
| Notion ID (ex: "Notion 248") | Executar `npm run intake:notion-record -- <ID>` |
| URL externa não-LinkedIn | Executar `npm run intake:url -- --url "<url>" --company "<empresa>" --role "<cargo>"`; `--company/--role` são fallback. Se a extração falhar por página ruim, descrição curta ou metadado fraco, pedir texto bruto |

Notion usa a skill operacional `.agents/skills/notion-transactions/SKILL.md`, mas a implementação continua nos scripts locais. Não procurar `notion-query`, `notion-cli-fallback` ou qualquer skill `notion-*` inventada; não ler `.env`, não extrair token e não fazer `curl` direto na API do Notion.

Após qualquer intake:
- Se `status = ready_for_model_analysis`, usar `job_description_path` e preencher `.career-state/fit_map.draft.json`.
- Se `next_required_step = fill_fit_map_draft`, não entregar análise textual; editar o draft.
- Se houver bloqueio por descrição curta, sessão LinkedIn expirada ou URL sem extrator, declarar o bloqueio e pedir a entrada necessária.

### Passo 2 — Confirmar estado de intake

```bash
npm run intake:resume
```

### Passo 3 — Ler as 4 referências obrigatórias (se ainda não lidas nesta sessão)

1. `.agents/skills/career-system/references/dicionario_palavras_chave_mercado.md`
2. `.agents/skills/career-system/references/palavras_chave_carreira.md`
3. `.agents/skills/career-system/references/autoconhecimento.md`
4. `.agents/skills/career-system/references/perfil_restricoes.md`

### Passo 4 — Gerar template e montar draft FIT_MAP

```bash
# O intake já recria o template. Se for retomada antiga, use:
npm run intake:resume
```

Preencher o `.career-state/fit_map.draft.json` com a análise completa seguindo o schema do career-fit-analysis:

**Campos obrigatórios:**
- cargo, empresa, modo ("Modo 1 - vaga especifica")
- dor_central (1-2 frases)
- keywords_vaga (cada item com termo + origem válida: titulo, requisitos, responsabilidades, diferenciais)
- competencias_vaga (cada item com competencia + tipo válido: hard skill, soft skill, ferramenta, setor)
- mapa_ajuste (cada item com termo_vaga + tipo_ajuste DIRETO/REPOSICIONAMENTO/GAP + evidencia + empresa_origem + resultado_numero + angulo_sugerido + ajustes_feitos + defensavel)
- objecoes (3-5, cada com objecao + classificacao forte/media/fraca + origem + mitigacao + evidencia_real)
- nota_aderencia (com dimensoes: requisitos_obrigatorios, responsabilidades_principais, ausencia_gaps_criticos, diferenciais_desejaveis)
- gaps_sem_cobertura (array de strings)
- historias_selecionadas (principal + secundaria + terceira)
- keywords_habilidade_ats (15 keywords com prioridade, experiencia_alvo, bullet_sugerido, origem)

**Regras de nota:**
- `final: null` no draft (o script calcula)
- DIRETO → nota 1.0, REPOSICIONAMENTO → nota 0.5, GAP → nota 0.0
- Cada item com prova_literal (true/false) e fonte_base

### Passo 5 — Pipeline de validação

```bash
python3 scripts/validate_fit_map_draft.py
python3 scripts/build_fit_map.py --draft .career-state/fit_map.draft.json
python3 scripts/score_fit_map.py --input .career-state/fit_map.json --output .career-state/fit_map.json
python3 scripts/validate_fit_map.py
python3 scripts/register_keywords.py --fit-map .career-state/fit_map.json
```

Se qualquer passo falhar: corrigir o draft e reexecutar a partir do passo que falhou.

### Passo 6 — Notion (se aplicável)

**Se o usuário pediu apenas para atualizar/criar o registro com a descrição extraída, antes de análise/FIT_MAP**:

```bash
python3 scripts/notion_sync.py update-description-record <ID> --job-description <caminho_da_descricao>.md --source-url "<url>" --dry-run
python3 scripts/notion_sync.py create-description-record --job-description <caminho_da_descricao>.md --company "<empresa>" --role "<cargo>" --source-url "<url>" --dry-run
```

Usar `update-description-record` quando houver `ID`/`Notion <número>` existente. Usar `create-description-record` quando
o usuário pedir para criar/registrar uma nova vaga no Notion. Executar a escrita real somente após aprovação explícita
do dry-run.

**Se o usuário veio de um Notion ID** → atualizar o mesmo registro:

```bash
python3 scripts/notion_sync.py update-from-fit-map-record <ID> --fit-map .career-state/fit_map.json --job-description <caminho_da_descricao>.md
```

Nunca usar `--allow-mismatch` para contornar descrição errada. Se o dry-run indicar mismatch, corrigir a descrição
salva, o FIT_MAP ativo ou a origem da página antes de atualizar o Notion.

Regra dura: a nota de aderência não muda a decisão entre criar e atualizar. Se a origem foi Notion (`page_id` ou `ID` único), `create-from-fit-map` é proibido mesmo quando a nota for alta; a única saída correta é atualizar a mesma página/registro.
Regra dura adicional: ao criar/atualizar no Notion depois da análise ou do CV, o pipeline nunca deve subir `Etapa Funil` acima de `Aplicação andamento`; `Aplicação Feita` não é status automático.

**Se o usuário não veio do Notion mas pediu para registrar** → criar novo:

```bash
python3 scripts/notion_sync.py create-from-fit-map --fit-map .career-state/fit_map.json --job-description <caminho_da_descricao>.md
```

**Se o Notion não foi mencionado** → pular este passo e apresentar a análise textualmente.

### Passo 7 — Apresentar resultado

Exibir:
- Nota final e breakdown por dimensão
- Dor central
- Objeções principais
- Gaps abertos
- Status do Notion (atualizado / criado / não aplicável)

### Regras de progressão

- Não gastar mais de 1 bloco de resposta analisando texto da vaga sem executar o próximo comando
- Referências uma vez lidas na sessão não precisam ser relidas
- A nota final oficial é a do `score_fit_map.py` — não estimar antes
- Depois de qualquer falha de validação, corrigir o draft imediatamente e reexecutar
- Se a vaga veio de URL do LinkedIn, inclusive postagem, a extração autenticada local é obrigatória antes de salvar; para outras URLs, usar o extrator específico da origem ou pedir o texto bruto ao usuário
