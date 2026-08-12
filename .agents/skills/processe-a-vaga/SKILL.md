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

Após o intake, **sincronizar estado global**:

```bash
python3 << 'PY'
import json, shutil
from pathlib import Path
ROOT = Path(".")
APP_ID = "<application_id do output do intake>"
APP_DIR = ROOT / f".career-state/applications_v2/{APP_ID}"
g = json.loads((ROOT / ".career-state/workflow_state.json").read_text())
app_wf = json.loads((APP_DIR / "workflow_state.json").read_text())
ai = app_wf["active_intake"]
g["active_job"] = app_wf["active_job"]
g["active_intake"] = ai
g["application_id"] = ai["application_id"]
g["application_dir"] = str(APP_DIR)
g["source_type"] = ai["source_type"]
g["source_id"] = ai["source_id"]
g["company"] = ai["company"]
g["role"] = ai["role"]
g["job_description_path"] = ai["job_description_path"]
g["fingerprint"] = ai["fingerprint"]
g["status"] = "ready_for_model_analysis"
g["next_required_step"] = "fill_fit_map_draft"
g["completed_states"] = sorted(set(g.get("completed_states", []))
    - {"fit_map_built","fit_map_scored","fit_map_validated","fit_map_draft_valid","cv_review_passed"})
for k in list(g.get("fingerprints", {}).keys()):
    del g["fingerprints"][k]
(ROOT / ".career-state/workflow_state.json").write_text(json.dumps(g, indent=2, ensure_ascii=False))
print("✅ synced:", ai["company"], "|", ai["role"])
PY
```

### Fase 2 — FIT_MAP

1. **Ler referências obrigatórias:**
   - `.agents/skills/career-system/references/candidate_cv_facts.json`
   - `.agents/skills/career-system/references/perfil_restricoes.md`
   - `.agents/skills/career-system/references/autoconhecimento.md`

2. **Preencher `.career-state/fit_map.draft.json`** com análise de aderência:
   - `cargo`, `empresa`, `dor_central`
   - `keywords_vaga` (extraídas da descrição)
   - `competencias_vaga`
   - `mapa_ajuste` (DIRETO / REPOSICIONAMENTO / GAP)
   - `objecoes` (do recrutador)
   - `nota_aderencia` (dimensões com itens, notas, evidências)
   - `historias_selecionadas` (principal, secundária, terceira)
   - `keywords_habilidade_ats` (15 itens, prioridades únicas 1-15)

3. **Copiar draft para app dir e validar:**
   ```bash
   cp .career-state/fit_map.draft.json .career-state/applications_v2/<APP_ID>/fit_map.draft.json
   npm run validate:fit-map:draft
   ```
   Se falhar, corrigir placeholders e prioridades duplicadas, depois revalidar.

4. **Finalizar FIT_MAP:**
   ```bash
   npm run fit-map:finalize
   npm run validate:fit-map:quality
   npm run fit-map:summary
   ```

5. **Copiar FIT_MAP para app dir e registrar keywords:**
   ```bash
   cp .career-state/fit_map.json .career-state/applications_v2/<APP_ID>/fit_map.json
   python3 scripts/register_keywords.py --fit-map .career-state/fit_map.json \
     --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json
   ```

### Fase 3 — CV DOCX

```bash
# Sincronizar estado global (se não estiver na vaga correta)
# Limpar cv_content stale
rm -f .career-state/cv_content.json

# Pipeline CV
npm run cv:build-content
npm run cv:validate-content
npm run cv:docx
npm run validate:docx

# Registrar keywords com CV
python3 scripts/register_keywords.py --fit-map .career-state/fit_map.json \
  --cv outputs/<cv_filename>.docx \
  --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json

# Revisar
python3 scripts/review_output.py --kind cv \
  --artifact outputs/<cv_filename>.docx \
  --fit-map .career-state/fit_map.json \
  --registry .career-state/derived/keyword_ats_registry.json \
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

1. **Estado global stale:** Após `intake:linkedin-job`, o `workflow_state.json` global pode ainda apontar para vaga anterior. Sempre sincronizar antes de `fit-map:finalize` ou `cv:build-content`.

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
