# Instalação no Windows

Este guia prioriza Windows 11 e PowerShell. Você não precisa executar os
comandos sozinho: envie o prompt-mestre para um harness que tenha acesso ao
terminal local e responda às confirmações de segurança quando ele pedir.

## Pré-requisitos humanos

- Computador Windows 11 com conta de administrador, ou alguém que possa aprovar
  instalações pelo `winget`.
- Conta Google pessoal e navegador Chrome ou Edge instalado.
- Conta LinkedIn, apenas se você quiser importar vagas salvas.
- Uma pasta local com acesso normal de leitura/escrita.
- 30–60 minutos para a primeira instalação e autorização do Google.

## Programas que o harness deve verificar

| Programa | Por que é necessário | Verificação |
| --- | --- | --- |
| winget | instala dependências de modo reproduzível | `winget --version` |
| Git | histórico e proteção contra sobrescrita | `git --version` |
| Node.js LTS | automação do navegador/Playwright | `node --version` |
| Python 3.11+ | scripts, integração Google e validações | `python --version` |
| Chrome ou Edge | sessão LinkedIn e OAuth local | abrir o navegador normalmente |
| VS Code ou PowerShell | espaço de trabalho e terminal | `pwsh --version` ou abrir PowerShell |

O harness só instala uma dependência após mostrar o motivo e receber a
confirmação necessária do Windows. Depois de cada instalação ele roda a coluna
“Verificação”. Se a verificação falhar, ele para, mostra o erro e propõe a
correção — não segue simulando sucesso.

## Estrutura que será criada

```text
%USERPROFILE%\Documents\SistemaCandidaturas\
├── perfil\autoconhecimento.md
├── inbox\job_descriptions\
├── state\google-oauth\
├── outputs\APP-00001\
├── logs\
├── scripts\
├── .gitignore
└── README.md
```

`state`, perfil, inbox e outputs são dados pessoais. O harness deve inicializar
Git para versionar o que for seguro, mas nunca adicionar credenciais, tokens,
cookies, currículo com dados sensíveis sem sua permissão, ou o perfil a um
repositório público.

## Teste mínimo antes de usar vagas reais

1. `git --version`, `node --version` e `python --version` retornam versões.
2. O projeto existe no caminho acima e o `.gitignore` contém os segredos.
3. O OAuth lê o título do tracker e cria/remove `TESTE_OAUTH_OK` somente em
   `Logs`.
4. A planilha contém abas e cabeçalhos descritos em `google-sheets.md`.
5. O harness cria uma candidatura fictícia `APP-00001` sem gerar CV nem tocar
   no LinkedIn.

Somente depois desse teste, preencha seu perfil e importe uma vaga real.
