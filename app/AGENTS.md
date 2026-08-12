# Career Job Application System

## Carregamento automático por tarefa

1. Leia este arquivo e `.agents/skills/career-system/SKILL.md`.
2. Identifique a tarefa em `references/routing-table.md`.
3. Carregue `runtime-core`, os módulos em `instruction_modules` da skill e então a skill.
4. Execute o workflow persistido; leitura não é conclusão.

## Regras universais

- **profile Hermes → candidatura**: use exclusivamente a candidatura vinculada ao `HERMES_HOME`.
- Em Hermes direto, **não usar estado global**. Use `.career-state/applications_v2/<ID>/`.
- Nova vaga no mesmo profile exige `career applications profile-release --application-id <ID>`; consulte `career applications profile-status`.
- Não inventar resultado nem afirmar conclusão sem os artefatos e gates exigidos.
- Nunca expor segredos, tokens ou `.env`.

## Módulos

| Tipo | Módulos | Skill |
|---|---|---|
| Vaga/FIT_MAP | runtime-core, intake-fit-map | intake-orchestrator, career-fit-analysis |
| CV | runtime-core, cv-delivery | cv-generator |
| Notion/email | runtime-core, notion-email | notion-transactions, self-email-draft |
| Células/concorrência | runtime-core, cellular-runtime | applications runtime |

Valide a estrutura com `npm run validate:structure` após manutenção da biblioteca.
