# Guia: Sistema pessoal de candidaturas com Google Sheets

Este kit ajuda uma pessoa sem perfil técnico a instruir um harness de IA a
montar, no Windows, um sistema local de candidaturas. O tracker é uma planilha
Google pessoal; descrições de vaga, evidências e documentos ficam em arquivos
locais, onde podem ser versionados e revisados.

## O que este guia constrói

- Um projeto em `%USERPROFILE%\Documents\SistemaCandidaturas`.
- Um perfil factual que impede a IA de inventar experiências e métricas.
- Um Google Sheets com status, prioridades, métricas e log de operações.
- Um fluxo seguro para vagas coladas, URLs e vagas salvas do LinkedIn.
- Prompts para analisar aderência, gerar documentos, revisar e retomar falhas.

## Resultado final

Você terá uma linha por vaga no Sheets e uma pasta por candidatura no projeto
local. A planilha responde “o que fazer agora”; os arquivos respondem “em que
evidência isso se baseia”. Aplicar para a vaga continua sendo uma decisão e
ação manual sua.

## Antes de começar

1. Preencha [o modelo de autoconhecimento](templates/autoconhecimento.md).
2. Leia [instalação no Windows](instalacao-windows.md) e escolha seu harness.
3. Crie e teste o tracker seguindo [Google Sheets](google-sheets.md).

## Roteiro de implantação

1. Copie e envie o [prompt-mestre de instalação](prompts/prompt-mestre-instalacao.md).
2. Siga as [adaptações por harness](prompts/adaptacoes-por-harness.md).
3. Importe os modelos `candidaturas.csv` e `listas.csv` em uma planilha nova.
4. Faça o teste de leitura/escrita do Google antes de registrar uma vaga real.
5. Use o fluxo de [LinkedIn e pipeline](linkedin-e-pipeline.md), ou cole a
   descrição de uma vaga no harness.

## Como operar no dia a dia

Os prompts prontos estão em [operação diária](prompts/operacao-diaria.md).
Primeiro importe ou registre a vaga; depois analise; só então decida se vale
prosseguir. Gere CV/carta apenas para vagas com decisão humana `prosseguir`.

## Segurança e limites

Nunca cole `client_secret`, token OAuth, cookies, senha ou CV completo em chat
público. Use o [modelo de `.gitignore`](templates/.gitignore). O sistema não
envia e-mails, não submete candidaturas, não resolve CAPTCHA e não tenta burlar
login ou limites do LinkedIn.

## Diagnóstico e retomada

Consulte [validação e recuperação](validacao-e-recuperacao.md) quando um passo
falhar. O check final está em [checklist-final](checklist-final.md).

## Arquivos deste kit

- `templates/autoconhecimento.md`: fonte factual aprovada por você.
- `templates/candidaturas.csv`: cabeçalho da aba principal.
- `templates/listas.csv`: vocabulários usados nas validações do Sheets.
- `google-sheets.md`: colunas, abas, OAuth e teste de conexão.
- `instalacao-windows.md`: pré-requisitos e comandos de verificação.
- `linkedin-e-pipeline.md`: intake, análise, artefatos e limites.
- `prompts/`: instruções copiáveis para o harness.
