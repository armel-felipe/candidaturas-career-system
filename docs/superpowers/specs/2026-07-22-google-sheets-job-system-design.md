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
