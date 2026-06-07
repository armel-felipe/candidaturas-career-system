# Claude Bridge

Este arquivo existe para adaptar o projeto ao runtime do Claude sem duplicar a governança operacional.

## Fonte Canônica

O ponto de entrada oficial deste repositório continua sendo [AGENTS.md](/Users/mac/llm%20server/projetos/candidaturas/AGENTS.md).

Se houver qualquer conflito entre este arquivo e `AGENTS.md`, siga `AGENTS.md`.

Ordem obrigatória de leitura para Claude:

1. Ler `AGENTS.md`
2. Ler `.opencode/skills/career-system/SKILL.md`
3. Ler `.opencode/skills/{skill}/SKILL.md` antes de executar a skill pedida

## Onde Estão As Skills

As skills canônicas ficam em `.opencode/skills/`.

Cada skill deve ser lida no próprio arquivo:

- `.opencode/skills/intake-orchestrator/SKILL.md`
- `.opencode/skills/career-fit-analysis/SKILL.md`
- `.opencode/skills/cv-generator/SKILL.md`
- `.opencode/skills/feras-pitch/SKILL.md`
- `.opencode/skills/cover-letter/SKILL.md`
- `.opencode/skills/habilidades-chave/SKILL.md`
- `.opencode/skills/networking-message/SKILL.md`
- `.opencode/skills/linkedin-job-extractor/SKILL.md`
- `.opencode/skills/linkedin-saved-jobs/SKILL.md`
- `.opencode/skills/notion-transactions/SKILL.md`
- `.opencode/skills/notion-xlsx-export/SKILL.md`
- `.opencode/skills/self-email-draft/SKILL.md`
- `.opencode/skills/output-reviewer/SKILL.md`
- `.opencode/skills/unified-job-analysis/SKILL.md`
- `.opencode/skills/general-cv-optimizer/SKILL.md`

Nao execute skills de memoria. Ler `SKILL.md` e obrigatorio, mas nao conta como execucao.

## Onde Rodar

Rode o Claude Code na raiz do projeto:

```bash
cd "/Users/mac/llm server/projetos/candidaturas"
claude
```

Todos os comandos do projeto assumem esse diretório como `cwd`.

## Como Executar As Skills

Claude nao "chama" skills por nome nativamente neste projeto. A execucao acontece lendo a skill certa e rodando os comandos locais definidos nela, quase sempre via `npm run ...` ou `python3 scripts/...`.

Fluxo minimo esperado:

1. Identificar a intenção do usuário
2. Mapear para a skill correta usando `AGENTS.md`
3. Ler `.opencode/skills/career-system/SKILL.md`
4. Ler `.opencode/skills/{skill}/SKILL.md`
5. Executar os comandos obrigatórios da skill
6. Persistir artefatos e validar o resultado antes de encerrar

## Comandos Mais Comuns

Analisar vaga do Notion:

```bash
npm run agent:evaluate-notion -- <id_unico>
```

Analisar vaga colada:

```bash
cat <arquivo> | npm run intake:paste -- --company "<empresa>" --role "<cargo>" --stdin
```

Analisar vaga do LinkedIn:

```bash
npm run intake:linkedin-job -- --url "<url-da-vaga>"
```

Retomar trabalho interrompido:

```bash
npm run intake:resume
npm run agent:guard
```

Checar estado do FIT_MAP:

```bash
npm run fit-map:status
npm run fit-map:guard
```

Finalizar FIT_MAP já preenchido:

```bash
npm run fit-map:finalize
```

Gerar CV:

```bash
npm run cv:docx
npm run cv:approve -- --artifact outputs/<cv>.docx
```

Entregar CV aprovado:

```bash
npm run cv:deliver -- --artifact outputs/<cv>.docx
```

## Regras Importantes Para Claude

- Nao substituir scripts obrigatórios por explicação textual
- Nao declarar skill concluída sem artefato persistido e validado
- Nao usar navegador genérico ou busca web para vagas do LinkedIn; usar os scripts locais do projeto
- Nao reutilizar `FIT_MAP` antigo para uma vaga nova
- Em caso de dúvida sobre o próximo passo, usar `npm run intake:resume`, `npm run agent:guard` ou `npm run fit-map:status`

## Resumo Operacional

Para Claude, este arquivo é apenas uma ponte. A verdade operacional continua em:

- [AGENTS.md](/Users/mac/llm%20server/projetos/candidaturas/AGENTS.md)
- `.opencode/skills/career-system/SKILL.md`
- `.opencode/skills/{skill}/SKILL.md`
