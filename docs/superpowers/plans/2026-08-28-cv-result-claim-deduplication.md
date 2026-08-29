# CV Result Claim Deduplication Plan

> Corrigir a duplicação de métricas entre escopo/responsabilidade e resultado em
> CVs concisos, usando a candidatura do bot-01 como regressão real.

## Roadmap

- ID: `CV-017`, `CV-018` e `CELLULAR-008`
- Plano: `2026-08-28-cv-result-claim-deduplication`
- Fonte canônica: `.agents/skills/career-system/references/candidate_cv_facts.json`
- Candidatura-alvo: `local_20260827T192403_744013_empresa_confidencial_8ac097b4`

## Regra

1. Bullet 1: escopo, responsabilidade e time; métricas de responsabilidade podem
   aparecer aqui quando não forem repetidas como resultado.
2. Bullet 2: atribuição, posicionamento, mecanismo ou caso; sem métrica de resultado.
3. Bullet 3: resultado mensurável; métricas tratadas como resultado aparecem aqui.
4. Uma mesma métrica quantitativa não pode aparecer nos bullets 1 e 3.

## Contenção celular

Quando `analyze_fit` falhar, o repair não pode executar o draft/binding que
pertence à tentativa anterior. O repair deve devolver a tentativa reservada a
`planned`; somente a retomada do agente pode criar a nova tentativa e gravar o
binding correspondente ao manifesto novo.

## Execução

- [x] Reproduzir o caso real e escrever testes regressivos.
- [x] Corrigir o `result_bullet` canônico do Diretor de Operações e o fragmento
      de resumo que apontava budget como resultado.
- [x] Adicionar validação de duplicação quantitativa entre bullets 1 e 3.
- [x] Impedir que o repair de `analyze_fit` execute binding stale; cobrir o caso
      com teste regressivo.
- [x] Adicionar cláusulas PT-BR controladas para as keywords de atendimento
      sustentadas pela evidência canônica.
- [x] Regenerar o CV v2 pelo fluxo canônico, revisar e entregar no OneDrive.
- [x] Atualizar o roadmap com evidência final da run e do artefato.

## Evidência final

- Run celular concluída: `run_bdc2377ca46a447595a6c500a21f0c23`.
- `review_cv`: `approved_for_delivery=true`, ATS top8 `8,0/8`, zero
  `missing_unexplained`, blockers e warnings.
- Diretor de Operações: `budget de R$300MM/ano` somente no bullet 1; o bullet 2
  contém o mecanismo S&OP sem o valor; o bullet 3 contém apenas os resultados
  de cobertura, indisponibilidade e viagens agrupadas.
- Receipt de entrega: `status=delivered`, artefato hash
  `d50e44da7d9a33b26672e7ab8ef4b58f9e8a5a227e356408b843fe186865f21d`, destino
  `onedrive:01_armel/Curriculos/personalizados/felipe_armel_cv_gerente_de_customer_experience_empresa_confidencial.docx`.
