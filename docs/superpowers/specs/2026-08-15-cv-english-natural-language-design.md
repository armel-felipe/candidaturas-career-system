# Design — Fluxo de CV em inglês executivo natural

## Objetivo

Fazer com que CVs em inglês sejam reescritos diretamente em inglês executivo
idiomático, preservando integralmente os fatos do candidato e aplicando ATS
somente depois da qualidade textual.

## Decisão

1. As frases em inglês usadas pelo gerador permanecem em
   `.agents/skills/career-system/references/candidate_cv_facts.json`, que é a
   fonte factual versionada do renderer.
2. `cv_content` passa a executar um guard determinístico para CVs em inglês.
   Ele bloqueia padrões comprovadamente artificiais ou literais, sem tentar
   gerar texto criativo automaticamente.
3. A `cv-generator` documenta a ordem editorial: naturalidade, sintaxe,
   collocations, concisão, senioridade, fatos e só então ATS/reviewer.
4. Os testes cobrem as frases-problema da especificação, o Summary e a
   preservação factual. O DOCX continua sujeito aos gates existentes de
   validação, registro ATS e reviewer.

## Fluxo

```text
FIT_MAP em inglês
  -> fontes canônicas localizadas
  -> cv_content com guard editorial EN
  -> DOCX em *_en.docx
  -> validate:docx
  -> register_keywords.py --cv
  -> review_output.py / cv:approve
```

O guard não faz tradução automática nem aumenta senioridade, escopo, ownership,
equipe ou impacto. Quando encontra um padrão bloqueado, a fonte canônica deve
ser corrigida e o CV regenerado.

## Critérios de aceite

- Summary não usa narrativa autobiográfica repetitiva (`I have`, `I am pursuing`)
  quando uma formulação executiva factual for possível.
- As expressões sinalizadas pela especificação não aparecem no conteúdo EN.
- `which allowed me to` não é usado como estrutura causal recorrente.
- “240 direct and indirect people” não é fabricado quando a fonte só comprova
  uma organização de 240 pessoas.
- Os mesmos fatos, números e identificadores de experiência permanecem
  preservados.
- PT-BR e o renderer DOCX existente não sofrem alteração de idioma.
