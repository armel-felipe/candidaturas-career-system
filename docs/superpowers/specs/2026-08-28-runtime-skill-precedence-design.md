# Runtime Skill Precedence Design

## Objetivo

Garantir que os bots Telegram resolvam as instruções de carreira de forma
determinística, usando a fonte canônica do projeto antes de skills externas ou
skills instaladas no profile.

## Escopo

Esta decisão se aplica ao runtime Hermes dos perfis `vagas_bot_01` e
`vagas_bot_02`, incluindo o índice de skills do prompt, `skills_list`,
`skill_view` e o resolver usado por `skill_manage`.

A skill global do Codex (`/root/.codex/skills`) não participa da resolução do
Hermes Telegram. Dentro do Hermes, `external_dirs` representa a camada externa
/global de apoio.

## Precedência

Para tarefas do projeto, a ordem é:

1. `project`: `.agents/skills/`, configurado explicitamente em `project_dirs`;
2. `global`: diretórios externos configurados em `external_dirs`;
3. `profile`: `<HERMES_HOME>/skills`, mantido para integrações e skills
   específicas do bot.

`AGENTS.md` e `career-system` continuam sendo a governança acima das três
camadas. Uma skill global pode complementar a canônica, mas não substituí-la;
uma skill local do profile nunca pode sobrescrever uma skill do projeto.

## Regras de colisão

- Os diretórios são percorridos na ordem acima.
- O primeiro nome resolvido vence apenas para descoberta/indexação; não há
  fallback silencioso para uma camada inferior.
- Se uma skill com nome canônico do projeto também existir no profile, o
  runtime acusa colisão de origem e bloqueia a descoberta até a cópia local
  ser removida.
- Skills locais sem colisão continuam disponíveis para integrações específicas
  do profile.
- O runtime deve preservar a distinção entre a origem da skill e o caminho
  relativo exibido ao agente.

## Configuração dos bots

Cada profile declara:

```yaml
skills:
  project_dirs:
    - /workspace/candidaturas/.agents/skills
  external_dirs: []
  source_precedence:
    - project
    - global
    - profile
```

`external_dirs` permanece como nome compatível da configuração Hermes para a
camada global/externa. A lista pode receber diretórios externos adicionais no
futuro, sempre depois de `project_dirs`.

## Critérios de aceite

- Os dois profiles expõem `project_dirs` e `source_precedence` idênticos.
- Um nome presente no projeto e no profile resolve para o projeto; a presença
  simultânea é reportada pelo guard.
- `skills_list`, `skill_view`, o prompt e `skill_manage` usam a mesma ordem.
- Skills locais legítimas sem colisão continuam descobertas.
- Os perfis não carregam as duplicatas legadas de carreira identificadas no
  inventário atual.
- Testes regressivos comprovam precedência, colisão e preservação de skills
  locais não conflitantes.
