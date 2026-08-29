# Routing Table — Career System

Mapeamento de gatilhos do usuário para skills do projeto em `.agents/skills/`.

Fonte canônica: `AGENTS.md` na raiz do projeto. Mantenha sincronizada com a tabela em AGENTS.md.

## Tabela de Roteamento

| O usuário pede | Skill a executar (`.agents/skills/{skill}/SKILL.md`) |
|---|---|
| Analisar vaga / "como me encaixo" / colar anúncio | `intake-orchestrator` → `career-fit-analysis` |
| "Avalie a vaga em <URL>" / "analise a vaga em <URL>" com URL `linkedin.com/jobs/view/...`, `linkedin.com/jobs/...` ou `linkedin.com/job/...` | `intake-orchestrator` → `career-fit-analysis` |
| "Avalie a vaga em <URL>" / "analise a postagem" com URL `linkedin.com/feed/update/...`, `linkedin.com/posts/...` ou `linkedin.com/pulse/...` | `intake-orchestrator` → `career-fit-analysis` |
| Gerar CV / currículo / adaptar CV | `intake-orchestrator` (se vaga não ativa) → `career-fit-analysis` → `cv-generator` |
| CV geral / currículo geral / CV para sites de emprego / LinkedIn para busca ativa / competências gerais | `general-cv-optimizer` |
| Pitch / FERAS / "me fale sobre você" / resumo Gupy | `career-fit-analysis` → `feras-pitch` |
| Carta de apresentação / cover letter | `career-fit-analysis` → `cover-letter` |
| Habilidades Mercado Livre / habilidades Gupy / resumo ATS / aplicar pelo sistema | `career-fit-analysis` → `habilidades-chave` |
| Mensagem LinkedIn / networking / contato recrutador | `networking-message` |
| Link de vaga do LinkedIn / extrair descrição completa do LinkedIn / URL `linkedin.com/jobs/view/` | `linkedin-job-extractor` |
| Link de postagem do LinkedIn divulgando vaga / URL `linkedin.com/feed/update/`, `linkedin.com/posts/` ou `linkedin.com/pulse/` | `linkedin-job-extractor` |
| Pesquisar/listar/ler vaga no Notion / consultar `Notion <número>` | `notion-transactions` (para avaliar/analisar usar `intake-orchestrator`) |
| Gerar planilha `.xlsx` do Notion / exportar vagas filtradas do Notion | `notion-xlsx-export` |
| Listar vagas salvas do LinkedIn / Rastreador de vagas / minhas vagas / saved jobs | `linkedin-saved-jobs` |
| Atualizar vaga ID/Notion `<número>` com descrição extraída / preencher `Descrição da Vaga` | `linkedin-job-extractor` (se URL pendente) → `notion-transactions` |
| Criar/registrar vaga no Notion a partir de descrição extraída, antes de análise/FIT_MAP | `linkedin-job-extractor` (se URL pendente) → `notion-transactions` |
| Mandar algo para o próprio email / deixar em draft / enviar arquivo / email de candidatura por Gmail | `self-email-draft` |
| Tabela de keywords cobertas / resumo de aderência por keyword / formulário de candidatura / Gupy / ATS | `application-keyword-table` |
| Vaga já identificada + "processe a vaga" / "faz tudo" / pedido end-to-end | `processe-a-vaga` |
| Colar vaga + ID Notion + URL / "analisa e registra no Notion" / "analisa e salva" como análise de entrada | `unified-job-analysis` |
| Revisar documento / "está bom?" / conferir | `output-reviewer` |
| Quais cargos combinam comigo | `career-fit-analysis` (Modo 2) |
| Posicionamento para cargo novo | `career-fit-analysis` (Modo 3) |

## Skills do Projeto (`.agents/skills/`)

Skills operacionais roteadas pelo sistema:

- `application-keyword-table` — tabela de keywords por aplicação
- `career-fit-analysis` — análise de aderência, FIT_MAP, nota
- `cover-letter` — carta de apresentação
- `cv-generator` — CV orientado por vaga
- `feras-pitch` — pitch FERAS / resumo Gupy
- `general-cv-optimizer` — CV geral / LinkedIn
- `habilidades-chave` — habilidades Gupy / Mercado Livre / ATS
- `intake-orchestrator` — intake de vaga (ponto de entrada obrigatório)
- `linkedin-job-extractor` — extração de descrição do LinkedIn
- `linkedin-saved-jobs` — listagem de vagas salvas do LinkedIn
- `networking-message` — mensagem de networking
- `notion-transactions` — CRUD no Notion
- `notion-xlsx-export` — exportação de planilha do Notion
- `output-reviewer` — revisão de artefatos
- `processe-a-vaga` — pacote-base end-to-end conforme `delivery_profile`
- `self-email-draft` — draft de email por Gmail
- `unified-job-analysis` — pipeline completo (intake + análise + Notion)

Skills auxiliares (não roteadas diretamente, mas usadas como suporte):

- `brand-guidelines` — diretrizes de marca para documentos
- `docx` — geração de DOCX
- `pdf` — conversão para PDF
- `pptx` — criação e edição de apresentações
- `xlsx` — geração de planilhas

## Regra de Execução

1. Identificar o gatilho na tabela acima
2. Carregar o `SKILL.md` correspondente em `.agents/skills/{skill}/SKILL.md`
3. Executar o workflow completo descrito na skill (não apenas ler)
4. Se a skill falhar ou não puder ser executada, declarar bloqueio objetivo

## Skills que NÃO têm Hermes skill própria

Skills do projeto em `.agents/skills/` NÃO têm Hermes skills correspondentes. O Hermes `career-system` umbrella é o único ponto de entrada. Para carregar uma skill do projeto, use `skill_view(name='career-system')` e depois leia o `SKILL.md` canônico em `.agents/skills/{skill}/SKILL.md` via `read_file` ou `search_files`.
