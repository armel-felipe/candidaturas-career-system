# Compatibilidade histórica — não é runtime ativo

`app/` não é uma segunda implementação de produção. O runtime canônico está
na raiz do repositório:

- [AGENTS.md](../AGENTS.md)
- `.agents/skills/`
- `src/`
- `scripts/`
- `control-plane/career.db`

Use sempre os comandos a partir da raiz (`/opt/agent-projects/candidaturas`).
Os arquivos mantidos em `app/` servem apenas como referência histórica e
compatibilidade durante a observação. Não importe módulos de `app/src`, não
execute scripts de `app/scripts` e não trate o estado de `app/.career-state`
como autoridade.
