# Arquitetura modular de instruções para Hermes

## Objetivo

Reduzir o contexto carregado por profiles Hermes sem alterar o comportamento do
sistema de candidaturas. `AGENTS.md` deixa de ser um manual operacional completo
e a skill `career-system` deixa de ser uma dependência monolítica obrigatória.

O agente deverá carregar automaticamente apenas as instruções necessárias para o
tipo de tarefa e para a candidatura vinculada ao seu profile.

## Problema atual

- `AGENTS.md` tem cerca de 68 KB e é o ponto de entrada de todos os agents.
- `.agents/skills/career-system/SKILL.md` tem cerca de 66 KB.
- Skills de candidatura frequentemente exigem ler a skill central inteira, mesmo
  quando a tarefa é restrita a CV, Notion ou email.
- Regras de intake, FIT_MAP, estado global, entrega e concorrência estão
  duplicadas entre instruções de entrada e instruções operacionais.

Isso aumenta risco de truncamento, custo de contexto, instruções concorrentes e
perda de atenção para o contexto específico da vaga.

## Decisão

Adotar composição automática por módulos de instrução. Não haverá uma nova camada
de código no runtime nesta fase: a composição é declarada em arquivos e validada
por testes estruturais.

Fluxo:

```text
Mensagem do usuário
  -> AGENTS.md curto identifica intenção
  -> runtime-core (sempre)
  -> módulos requeridos pela tarefa
  -> skill específica
  -> contexto app-scoped da candidatura vinculada ao profile
```

## Estrutura de arquivos

```text
.agents/skills/career-system/
  SKILL.md
  modules/
    runtime-core.md
    intake-fit-map.md
    cv-delivery.md
    notion-email.md
    cellular-runtime.md
  references/
```

### Papel de cada artefato

| Artefato | Conteúdo permitido |
|---|---|
| `AGENTS.md` | identidade, caminhos canônicos, regras inegociáveis, roteamento curto e recuperação universal |
| `career-system/SKILL.md` | contrato de composição, inventário de módulos e regras que definem como uma skill declara dependências |
| `modules/runtime-core.md` | identidade Hermes, binding profile -> candidatura, isolamento app-scoped, segurança de estado |
| `modules/intake-fit-map.md` | fontes de vaga, intake, FIT_MAP, validação e retomada |
| `modules/cv-delivery.md` | geração de CV, revisão, DOCX, aprovação e OneDrive |
| `modules/notion-email.md` | Notion, Gmail, aprovações e locks externos |
| `modules/cellular-runtime.md` | células, runs, concorrência, recursos, autoridade e manutenção |
| `references/` | exemplos, contratos longos, tabelas, troubleshooting e material que não é necessário em toda execução |

## Declaração de módulos pelas skills

Cada skill de candidatura terá cabeçalho explícito e pequeno:

```yaml
requires:
  - runtime-core
  - cv-delivery
```

Exemplos esperados:

| Skill | Módulos |
|---|---|
| `intake-orchestrator` | `runtime-core`, `intake-fit-map` |
| `career-fit-analysis` | `runtime-core`, `intake-fit-map` |
| `cv-generator` | `runtime-core`, `cv-delivery` |
| `cover-letter` | `runtime-core`, `intake-fit-map` |
| `feras-pitch` e `habilidades-chave` | `runtime-core`, `intake-fit-map` |
| `notion-transactions` | `runtime-core`, `notion-email` |
| `self-email-draft` | `runtime-core`, `notion-email` |
| operação celular | `runtime-core`, `cellular-runtime` |

A tabela de roteamento apontará para a skill e seus módulos; não duplicará os
detalhes operacionais dos módulos.

## Regras invioláveis

As regras abaixo precisam permanecer sempre acessíveis, seja no núcleo ou no
`runtime-core` obrigatório:

- um profile Hermes possui no máximo uma candidatura ativa e uma candidatura
  possui no máximo um profile ativo;
- sessões Hermes usam somente caminhos e artefatos do `application_id` vinculado;
- não há fallback silencioso a FIT_MAP, workflow ou derivados globais;
- troca de vaga exige release explícito do binding atual;
- gates existentes de FIT_MAP, CV, revisão, aprovação, Notion, email e entrega
  continuam obrigatórios;
- locks de Notion, Gmail e OneDrive continuam serializando somente recursos
  externos compartilhados.

## Migração

1. Criar os cinco módulos com o conteúdo canônico extraído das fontes atuais.
2. Reduzir `career-system/SKILL.md` ao contrato de composição e a regras comuns.
3. Reduzir `AGENTS.md` ao núcleo e à tabela de roteamento curta.
4. Atualizar as skills de candidatura para declarar `requires`, removendo a
   instrução de ler toda a skill central.
5. Mover conteúdo longo remanescente para `references/`, mantendo links claros.
6. Atualizar a validação estrutural e os testes de segurança para a nova
   arquitetura.
7. Remover redirecionamentos e duplicações somente depois de os testes cobrirem a
   nova rota de carregamento.

Não haverá mudança de comandos, formatos de artefato, schema SQLite, binding de
profiles ou pipeline celular nesta refatoração.

## Falhas e comportamento seguro

- Uma skill sem `requires`, ou que cite módulo inexistente, falha na validação
  estrutural.
- Um módulo ausente ou inválido bloqueia a execução com o nome do módulo; o agente
  não improvisa e não recorre a instrução global antiga.
- Conflitos de regra são resolvidos mantendo uma única fonte canônica no módulo
  responsável; cópias textuais são removidas.

## Critérios de aceite

- `AGENTS.md` com no máximo 15 KB.
- `career-system/SKILL.md` com no máximo 10 KB.
- Nenhuma skill de candidatura exige leitura integral de `career-system/SKILL.md`.
- Todas as skills de candidatura declaram módulos válidos.
- Validação estrutural verifica tamanho, declaração de módulos, existência dos
  módulos e ausência das dependências monolíticas removidas.
- Testes preservam o binding profile -> candidatura, isolamento app-scoped, gates
  de entrega e proteção de recursos externos.
- A suíte completa permanece verde.

## Fora de escopo

- Gerar instruções dinamicamente por código no hook Hermes.
- Alterar comportamento do pipeline de candidatura.
- Reescrever referências de conteúdo do candidato ou de vagas.
- Alterar a configuração dos profiles Hermes ou reiniciar o RPi5.
