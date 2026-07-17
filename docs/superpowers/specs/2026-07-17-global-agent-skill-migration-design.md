# Skill Global de Migração de Skills — Design

## Objetivo

Criar uma skill global chamada `migrate-agent-skills` para transformar com segurança projetos que usam `.opencode/skills` em `.agents/skills`, atualizando referências internas e removendo caminhos absolutos específicos de máquina.

## Distribuição e descoberta

O conteúdo canônico fica em:

```text
/Users/mac/.agents/skills/migrate-agent-skills/
```

OpenCode descobre essa localização globalmente. Codex descobre a mesma skill por um symlink:

```text
/Users/mac/.codex/skills/migrate-agent-skills
  -> /Users/mac/.agents/skills/migrate-agent-skills
```

Assim existe uma única fonte de conteúdo e não há risco de versões divergentes.

## Fluxo operacional

1. Descobrir a raiz Git e inspecionar a estrutura atual sem alterações.
2. Produzir uma prévia contendo diretórios, referências, caminhos absolutos e arquivos não rastreados que seriam afetados.
3. Parar e pedir confirmação explícita.
4. Após confirmação, mover `.opencode` para `.agents` com Git quando aplicável.
5. Atualizar referências ativas em instruções, documentação, código, scripts e validações.
6. Substituir paths específicos de máquina por paths derivados da raiz do repositório.
7. Rodar validações disponíveis e reportar arquivos modificados, resíduos e bloqueios reais.

## Segurança

- O modo padrão é somente prévia; a skill não altera arquivos sem confirmação.
- Arquivos não rastreados não são removidos automaticamente.
- Nenhuma credencial, `.env`, token, configuração de rclone ou artefato final é alterado.
- Referências históricas ficam fora da busca de conformidade quando forem documentação de plano/spec explicitamente arquivada.

## Critérios de aceitação

- `SKILL.md` válido, com frontmatter `name` e `description`.
- OpenCode pode descobrir a skill em `~/.agents/skills`.
- Codex pode descobri-la através do symlink sob `~/.codex/skills`.
- Três prompts de avaliação cobrem prévia, aplicação confirmada e bloqueio por resíduo não rastreado.
