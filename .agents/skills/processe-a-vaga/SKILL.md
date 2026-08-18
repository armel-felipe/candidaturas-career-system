---
name: processe-a-vaga
description: >
  Pipeline completo de processamento de vaga: intake → FIT_MAP → CV DOCX → OneDrive → Notion.
  Acionar quando o usuário disser "processe a vaga", "faz tudo", "combo completo" ou similar,
  após a vaga já ter sido identificada (URL LinkedIn, texto colado, ID do Notion).
  Este workflow respeita AGENTS.md, skills e scripts do projeto candidaturas.
---

# Processe a Vaga — Pipeline Completo

## Gatilho

Usuário diz "processe a vaga", "faz tudo", "combo completo", "analisa e registra" ou similar,
**desde que a vaga já tenha sido identificada** (URL colada, texto colado, ID do Notion escolhido).

## Pré-requisitos

Antes de iniciar, a vaga deve estar identificada:
- URL do LinkedIn (`linkedin.com/jobs/view/...`)
- Texto colado no chat
- ID do Notion (ex: `Notion 42`)
- Número de vaga salva do LinkedIn (ex: `#4` da lista de saved jobs)

## Workflow

### Fase 1 — Intake

```bash
# Se for URL do LinkedIn
npm run intake:linkedin-job -- --url "<url>"

# Se for texto colado — salvar em arquivo primeiro, depois:
npm run intake:paste -- --company "<empresa>" --role "<cargo>" --text-file <arquivo>

# Se for ID do Notion
npm run agent:evaluate-notion -- <id_unico>
```

Anote o `application_id` retornado pelo intake. Ele é obrigatório em todas as
etapas seguintes. Não sincronize, copie, leia ou escreva o estado global:
`control-plane/career.db` é canônico e os JSONs globais são apenas espelhos.

### Fase 2 — FIT_MAP

1. **Ler referências obrigatórias:**
   - `.agents/skills/career-system/references/candidate_cv_facts.json`
   - `.agents/skills/career-system/references/perfil_restricoes.md`
   - `.agents/skills/career-system/references/autoconhecimento.md`

2. **Preencher `.career-state/applications_v2/<APP_ID>/fit_map.draft.json`** com análise de aderência:
   - `cargo`, `empresa`, `dor_central`
   - `keywords_vaga` (extraídas da descrição)
   - `competencias_vaga`
   - `mapa_ajuste` (DIRETO / REPOSICIONAMENTO / GAP)
   - `objecoes` (do recrutador)
   - `nota_aderencia` (dimensões com itens, notas, evidências)
   - `historias_selecionadas` (principal, secundária, terceira)
   - `keywords_habilidade_ats` (15 itens, prioridades únicas 1-15)

3. **Validar o draft no próprio app dir:**
   ```bash
   npm run validate:fit-map:draft -- --application-id "<APP_ID>"
   ```
   Se falhar, corrigir placeholders e prioridades duplicadas, depois revalidar.

4. **Finalizar FIT_MAP:**
   ```bash
   npm run fit-map:finalize -- --application-id "<APP_ID>"
   npm run validate:fit-map:quality -- --application-id "<APP_ID>"
   npm run fit-map:summary -- --application-id "<APP_ID>"
   ```

5. **Registrar keywords no próprio app dir:**
   ```bash
   python3 scripts/register_keywords.py --fit-map .career-state/applications_v2/<APP_ID>/fit_map.json \
     --registry .career-state/applications_v2/<APP_ID>/derived/keyword_ats_registry.json \
     --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json
   ```

### Fase 3 — CV DOCX

```bash
# Pipeline CV
npm run cv:build-content -- --application-id "<APP_ID>"
npm run cv:validate-content -- --application-id "<APP_ID>"
npm run cv:docx
npm run validate:docx

# Registrar keywords com CV
python3 scripts/register_keywords.py --fit-map .career-state/applications_v2/<APP_ID>/fit_map.json \
  --cv outputs/<cv_filename>.docx \
  --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json

# Revisar
python3 scripts/review_output.py --kind cv \
  --artifact outputs/<cv_filename>.docx \
  --fit-map .career-state/applications_v2/<APP_ID>/fit_map.json \
  --registry .career-state/applications_v2/<APP_ID>/derived/keyword_ats_registry.json \
  --report outputs/_tmp/output_review_report.json
```

**Se o review falhar por ATS top8 com missing_unexplained:**
- Editar `candidate_cv_facts.json` nos campos `leverage.project_management` (ou o job_family usado)
- Adicionar os termos faltantes naturalmente nos bullets
- Regenerar: `rm -f .career-state/cv_content.json && npm run cv:build-content && npm run cv:validate-content && npm run cv:docx && npm run validate:docx`
- Re-rodar register_keywords e review_output
- Repetir até `approved_for_delivery: yes`

### Fase 4 — Aprovação e Entrega OneDrive

```bash
npm run cv:approve -- --artifact outputs/<cv_filename>.docx
npm run cv:deliver -- --artifact outputs/<cv_filename>.docx
```

Verificar se `delivery_status: delivered` no output.

### Fase 5 — Notion

1. **Corrigir job_description.md** se necessário (empresa, heading):
   - `Empresa: <nome>` no lugar de "Empresa LinkedIn"
   - Heading: `# <cargo> — <empresa>`

2. **Dry-run:**
   ```bash
   npm run notion:create-current -- \
     --job-description inbox/job_descriptions/<arquivo>.md \
     --dry-run
   ```

3. **Criar página no Notion:**
   ```bash
   npm run notion:create-current -- \
     --job-description inbox/job_descriptions/<arquivo>.md \
     --extra-note "CV aprovado e entregue no OneDrive. ATS top8: X.X/8."
   ```

## Armadilhas conhecidas

1. **Escopo obrigatório:** Após o intake, usar sempre o `application_id` retornado. `workflow_state.json` global não pode selecionar nem autorizar `fit-map:finalize` ou `cv:build-content`.

2. **FIT_MAP mismatch com job_description:** O script `notion:create-current` valida que o heading do arquivo .md contém o cargo e a empresa do FIT_MAP. Corrigir o .md antes.

3. **ATS top8 blockers:** Se `review_output.py` retornar `missing_unexplained`, editar `candidate_cv_facts.json` nos bullets de alavanca (`leverage.project_management` ou job_family equivalente) para incluir os termos faltantes.

4. **Prioridades duplicadas em keywords_habilidade_ats:** O validador exige prioridades únicas 1-15. Usar sequência contínua.

5. **Notion extra-artifact só aceita .md/.txt/.json:** Não anexar .docx como extra-artifact.

## Arquivos de referência

- `AGENTS.md` — regras de governança do projeto
- `.agents/skills/career-system/SKILL.md` — orquestração global
- `.agents/skills/career-system/references/candidate_cv_facts.json` — dados canônicos do candidato
- `.agents/skills/career-system/references/perfil_restricoes.md` — perfil e restrições
- `.agents/skills/career-system/references/autoconhecimento.md` — autoconhecimento
- `.agents/skills/career-system/references/keyword_translation_registry.json` — tradução de keywords
