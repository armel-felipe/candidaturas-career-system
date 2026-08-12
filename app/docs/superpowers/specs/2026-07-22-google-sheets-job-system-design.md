# Sistema de candidaturas pessoal com Google Sheets — desenho

## Objetivo

Produzir um guia completo, orientado a pessoas pouco técnicas, para que um
harness de IA (ChatGPT Work, Codex, Claude Code ou Gemini) construa e opere
um sistema local de candidaturas no Windows. O Google Sheets pessoal substitui
o Notion como tracker; o repositório local mantém os documentos, evidências e
estado técnico.

## Escopo aprovado

- Instalação conduzida pelo harness no Windows, com validação a cada etapa.
- Integração com uma planilha Google pessoal por OAuth do usuário.
- Captura e análise de vagas salvas do LinkedIn por navegador local com sessão
  autenticada, sem burlar login, CAPTCHA ou limites da plataforma.
- Pipeline: intake, descrição persistida, fit, decisão, CV, revisão, carta e
  atualização no tracker.
- Prompts universais e adaptações por harness.

## Arquitetura

O projeto local é a fonte de verdade para evidências e artefatos. A planilha é
o índice operacional compartilhável: uma linha por candidatura, com IDs,
estado, links e métricas. O harness apenas executa o contrato: não é fonte de
verdade de fatos profissionais nem de estado da candidatura.

```text
Pessoa -> harness de IA -> projeto local
                          |-> Google Sheets (tracker)
                          |-> navegador autenticado (LinkedIn)
                          `-> arquivos de evidência e entregáveis
```

## Componentes e responsabilidades

### Perfil factual

`perfil/autoconhecimento.md` é o contrato humano-IA. Ele contém apenas fatos
que a pessoa confirma e exemplos de escopo, resultado e evidência. O formato
é deliberadamente Markdown com campos nomeados, porque é legível por humanos,
portável entre harnesses, versionável e fácil de validar por scripts simples.

Formato mínimo:

```md
# Autoconhecimento profissional

## Identidade e posicionamento
- Nome, localidade, idiomas, links profissionais.
- Proposta de valor em 2–3 frases, aprovada pela pessoa.

## Alvos e restrições
- Cargos, setores, senioridade, localidades/regime e faixa desejada (opcional).
- Critérios de descarte.

## Experiências verificadas
### [Empresa] — [Cargo] | [MM/AAAA–MM/AAAA]
- Contexto e responsabilidade real.
- Ação própria, ferramentas/métodos e escopo.
- Resultado mensurável, unidade e período; ou "não mensurado".
- Evidência: fonte ou pessoa que pode confirmar.

## Competências defensáveis
| Competência | Nível/contexto | Evidência |
| --- | --- | --- |

## Banco de histórias
### [Título curto]
- Situação / desafio
- Ações da pessoa
- Resultado e métrica
- Competências demonstradas

## Formação e credenciais

## Lacunas e limites de alegação
- O que ainda está aprendendo, fatos incertos e alegações proibidas.

## Preferências de linguagem
- Tom, idioma do currículo por padrão e termos a evitar.
```

Regras: datas e cargos não podem ser inventados; toda métrica precisa de
unidade, período e contexto; histórias não podem ser duplicadas como se fossem
experiências distintas; lacunas explícitas não são automaticamente eliminadas
nem maquiadas. O sistema usa esse arquivo para selecionar e redigir evidência,
nunca para fabricar cobertura de requisito.

### Integração Google Sheets

Uma planilha pessoal terá abas `Candidaturas`, `Config`, `Listas`, `Métricas`
e `Logs`. A aba Candidaturas guarda metadados e ponteiros, não cópias grandes
ou credenciais. Acesso via OAuth local; segredos e tokens permanecem ignorados
pelo Git.

#### Aba `Candidaturas`: uma linha por vaga

| Coluna | Tipo | Por que existe | Atualização |
| --- | --- | --- | --- |
| `id_candidatura` | texto imutável (`APP-00001`) | Chave estável para ligar planilha, pasta local e logs, mesmo se cargo ou empresa mudarem. | Harness na criação. |
| `criada_em` | data/hora ISO | Permite medir tempo de ciclo e auditar origem. | Harness na criação. |
| `atualizada_em` | data/hora ISO | Mostra se o registro está parado. | Harness em alterações. |
| `empresa` | texto | Campo-base para busca, agrupamento e nome de artefatos. | Harness, confirmação humana se ambíguo. |
| `cargo` | texto | Identifica o alvo da análise e do CV. | Harness, confirmação humana se ambíguo. |
| `url_vaga` | URL | Permite voltar à fonte sem depender de memória do agente. | Harness ou pessoa. |
| `fonte` | lista | Distingue LinkedIn salva, LinkedIn direta, indicação, site da empresa, Gupy etc. | Harness. |
| `localidade` | texto | Apoia filtros de presencial/híbrido/remoto. | Harness quando disponível. |
| `regime_trabalho` | lista | Registra remoto, híbrido, presencial ou não informado. | Harness quando disponível. |
| `descricao_arquivo` | caminho relativo | Ponteiro para a cópia local da descrição, que preserva texto integral e versão. | Harness. |
| `descricao_hash` | texto | Detecta se a vaga foi alterada desde a análise. | Harness. |
| `idioma_vaga` | lista | Determina idioma do CV e da carta. | Harness com validação. |
| `fit_score` | número 0–100 | Prioriza a fila; nunca substitui a leitura qualitativa. | Harness após análise. |
| `fit_resumo` | texto curto | Explica a recomendação sem armazenar o FIT_MAP inteiro. | Harness. |
| `gaps_declarados` | texto curto | Separa lacunas reais de ausência de análise e impede invenção para cobri-las. | Harness após análise. |
| `decisao` | lista | Registra `prosseguir`, `pausar` ou `descartar`; a escolha é humana. | Pessoa. |
| `etapa` | lista controlada | Controla o fluxo: `capturada`, `descricao_validada`, `analisada`, `artefatos_em_rascunho`, `revisao_pendente`, `pronta_para_aplicacao`, `aplicada`, `encerrada`. | Harness até pronta; pessoa para aplicada/encerrada. |
| `proxima_acao` | texto curto | Torna a fila acionável sem reler todo o histórico. | Harness. |
| `prazo` | data | Evita perder janelas de candidatura. | Harness quando explícito; pessoa confirma. |
| `cv_arquivo` | caminho relativo/URL | Aponta para o CV final revisado, sem subir binário à planilha. | Harness após aprovação. |
| `carta_arquivo` | caminho relativo/URL | Faz o mesmo para a carta, se houver. | Harness após revisão. |
| `pasta_artefatos` | caminho relativo | Permite recuperação e auditoria por candidatura. | Harness na criação. |
| `observacoes_humanas` | texto | Espaço exclusivo para contexto que o agente não deve sobrescrever. | Pessoa. |
| `ultimo_erro` | texto curto | Expõe bloqueios acionáveis, sem esconder falhas. | Harness, limpo somente após resolução. |

Campos longos, como descrição integral, FIT_MAP, CV e carta, não vivem em
células: isso evita limites de tamanho, perda de formatação, duplicação e
conflitos de edição. A planilha mantém ponteiros e resumos; o projeto local
guarda as versões completas.

#### Aba `Listas`: vocabulários e validações

Contém as listas permitidas para `fonte`, `regime_trabalho`, `idioma_vaga`,
`decisao` e `etapa`. O harness usa validação de dados no Sheets, em vez de
texto livre, para que filtros, métricas e automações não quebrem por variantes
como “Aplicado”, “aplicada” ou “enviei”.

#### Aba `Config`: referência não secreta

Guarda `spreadsheet_id`, timezone, idioma padrão, pasta raiz local e opções de
comportamento. Não armazena `client_secret`, tokens OAuth, senhas ou cookies.
Esses dados ficam apenas em arquivos locais ignorados pelo Git.

#### Aba `Métricas`: visão derivada, não edição manual

Usa fórmulas/queries sobre `Candidaturas` para mostrar vagas por etapa, taxa de
avanço, idade média da fila, empresas recorrentes e distribuição de fit. A aba
não é fonte de verdade: assim não há divergência entre dashboard e registros.

#### Aba `Logs`: trilha de auditoria

Colunas `timestamp`, `id_candidatura`, `acao`, `resultado`, `detalhe_curto` e
`run_id`. Registra criação, sincronização, análise, geração, falha e retomada.
É especialmente útil quando diferentes harnesses forem usados no mesmo
projeto.

Regras de escrita: o harness atualiza apenas colunas de sua responsabilidade,
nunca apaga `observacoes_humanas`, nunca altera `decisao` sem comando explícito
e inclui `run_id` em qualquer operação que mude dados.

### LinkedIn

Playwright abre o navegador local persistente. O usuário autentica quando
necessário. O extractor lista as vagas salvas, registra URLs no tracker e
salva a descrição localmente antes de análise. Erros de autenticação, CAPTCHA
ou conteúdo ausente interrompem o fluxo com pedido de texto bruto.

### Pipeline e controle de estado

Cada vaga passa por estados explícitos e reversíveis: capturada, descrição
validada, analisada, decisão, artefatos em rascunho, revisada e pronta para
aplicação manual. O sistema preserva versões, registra logs e tem comandos de
retomada e diagnóstico.

## Tratamento de falhas

- Dependência ausente: o harness instala ou apresenta o comando e valida.
- OAuth falho: invalida token local e reautoriza sem exibir segredo.
- Sheets indisponível: grava fila local e sincroniza mediante ação explícita.
- LinkedIn inacessível: solicita descrição colada; não tenta contorno.
- Validação de CV falha: bloqueia entrega e aponta evidência/keyword faltante.

## Verificação de aceitação

O manual exigirá testes de fumaça para instalação, leitura/escrita em uma
planilha de teste, criação de uma candidatura de teste, importação de uma vaga
salva ou texto colado, geração de artefato e retomada após falha simulada.

## Limites

O primeiro guia não incluirá candidatura automática, envio automático de
e-mails, scraping sem sessão autorizada ou compartilhamento de credenciais.
Aplicar para vagas continua uma ação humana.
