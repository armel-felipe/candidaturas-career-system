# Guardrails de Qualidade do Resumo do CV — Design

## Objetivo

Evitar que o resumo de um CV personalizado publique texto bruto da vaga,
ignore as histórias escolhidas no FIT_MAP ou use uma direção de catálogo
incompatível com o posicionamento sênior da candidatura.

## Composição PT-BR

O resumo terá duas frases obrigatórias e uma terceira opcional, sempre em
primeira pessoa:

1. **Posicionamento curto:** parte de uma abertura canônica e de temas
   compactos extraídos de `keywords_vaga` e `competencias_vaga`. Nunca usa
   `dor_central` literalmente e não reproduz sentenças da descrição.
2. **Provas:** usa duas experiências distintas na ordem de
   `historias_selecionadas` que também estejam presentes no CV. Cada prova é
   vinculada a um bullet canônico defensável.
3. **Direção:** só publica `caso` do catálogo se houver aderência suficiente
   aos sinais de cargo/competências da vaga. Um caso guiado apenas por termos
   operacionais genéricos, como SLA, CSAT ou custo, é omitido quando a vaga
   tem posicionamento estratégico mais amplo.

## Contrato do catálogo

`select_positioning` continua retornando o melhor caso para rastreabilidade,
mas expõe se ele é publicável no resumo. Publicabilidade exige sinais de alta
prioridade — cargo, keywords ATS ou competências da vaga — e não pode ser
sustentada somente por descrição bruta ou histórias. Quando não for
publicável, o payload preserva o caso e a proveniência, mas o resumo não cria
frase de direção.

## Testes de aceitação

- Nenhum trecho com mais de seis palavras de `dor_central` aparece na abertura.
- Para um FIT_MAP com histórias VivaReal, iFood e WeHandle, as duas provas usam
  as duas primeiras histórias presentes no CV, não uma prioridade estática.
- Caso com aderência apenas operacional não aparece como direção para uma vaga
  de transformação/AI/orquestração executiva.
- O caso continua publicável em uma vaga cuja aderência venha de cargo,
  competência ou keyword ATS.
- A candidatura 515 é regenerada e revisada como exemplo editorial real antes
  de aprovar a alteração.

## Fora de escopo

Não alterar fatos canônicos, FIT_MAP, schema do catálogo, conteúdo das
experiências ou idioma inglês nesta correção.
