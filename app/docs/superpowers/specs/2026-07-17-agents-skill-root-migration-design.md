# Migração da Raiz de Skills para `.agents` — Design

## Objetivo

Migrar definitivamente a biblioteca canônica de skills de `.opencode/skills/` para `.agents/skills/`, para que o projeto use uma convenção mais portátil entre runtimes de agentes. A migração deve deixar um único caminho válido, sem atalho, cópia ou compatibilidade legada permanente.

## Decisão arquitetural

O ponto de entrada do projeto permanece `AGENTS.md`. A cadeia de descoberta passa a ser:

```text
AGENTS.md → .agents/skills/career-system/SKILL.md → .agents/skills/<skill>/SKILL.md
```

`opencode.json` continua no repositório exclusivamente como configuração do runtime OpenCode e mantém `AGENTS.md` em `instructions`; seu nome não define a localização das skills. Outros runtimes que obedecem a `AGENTS.md` podem usar a mesma cadeia sem configuração específica de OpenCode.

## Escopo

- Renomear o diretório `.opencode` para `.agents`, preservando integralmente a árvore `skills/`, referências e conteúdo.
- Atualizar cada referência ativa a `.opencode/skills` para `.agents/skills` em instruções, documentação, configuração, código, serviços, scripts e testes.
- Alterar a validação estrutural para exigir `.agents/skills`, verificar as skills obrigatórias no novo caminho e falhar quando uma referência ativa ao caminho legado for introduzida.
- Atualizar a variável de exemplo `CAREER_REFERENCES` para o novo caminho.
- Manter documentos históricos de planos e specs inalterados quando apenas registrarem a arquitetura anterior; a verificação de referências legadas deve excluí-los explicitamente para preservar a fidelidade histórica.

## Fora de escopo

- Não criar symlink, diretório espelho ou fallback em `.opencode`.
- Não alterar workflows de candidatura, contratos de estado, comandos npm, integrações ou conteúdo operacional das skills além de seus caminhos canônicos.
- Não renomear `opencode.json`, pois ele é uma configuração de integração, não uma raiz de skills.

## Componentes afetados

| Área | Responsabilidade após a migração |
| --- | --- |
| `.agents/skills/` | Fonte canônica e única da biblioteca de skills e referências compartilhadas. |
| `AGENTS.md` | Declara a governança, sequência de carregamento e caminhos canônicos sob `.agents/skills`. |
| `scripts/validate_project_structure.py` | Exige a nova raiz, proíbe `.opencode`, procura referências legadas somente no conteúdo ativo e conserva checagens documentais. |
| Serviços Python e scripts auxiliares | Resolvem referências compartilhadas e instruções de especialistas a partir de `.agents/skills`. |
| `COMO_USAR.md` e `.env.example` | Expõem a arquitetura atual para usuários e ambientes. |

## Comportamento e falhas

- Uma instalação sem `.agents/skills` falha na validação estrutural com diagnóstico explícito.
- A existência de `.opencode` falha na validação, impedindo coexistência ambígua.
- Referências legadas em arquivos operacionais falham na validação; registros históricos em `docs/superpowers/{plans,specs}` não são reescritos nem tratados como falha.
- O conteúdo e os nomes das skills obrigatórias permanecem iguais, para que os workflows continuem idênticos após a troca de raiz.

## Estratégia de testes

1. Executar a validação estrutural, confirmando a nova raiz e a ausência da antiga.
2. Executar a suíte de testes do projeto para cobrir serviços que constroem caminhos de referência ou requests de multiagentes.
3. Fazer busca de referências ativas a `.opencode/skills`, excluindo `.git` e documentação histórica, e exigir resultado vazio.
4. Verificar `git diff --check` e o estado do repositório para garantir que o rename foi preservado e não incluiu arquivos fora de escopo.

## Critérios de aceitação

- `.agents/skills` existe e contém a árvore antes localizada em `.opencode/skills`.
- `.opencode` não existe após a migração.
- Todo caminho operacional aponta para `.agents/skills`.
- `scripts/validate_project_structure.py` aprova a estrutura migrada e rejeita explicitamente o caminho legado.
- Configuração OpenCode continua carregando `AGENTS.md`.
- Os testes relevantes do projeto passam sem alterar workflows de carreira.
