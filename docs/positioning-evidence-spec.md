# Especificação — Evidências e posicionamento reutilizável

## Objetivo

Garantir que uma história ou competência relevante registrada em
`.agents/skills/career-system/references/autoconhecimento.md` possa ser
selecionada para uma candidatura e traduzida de forma consistente em CV,
FERAS, carta, habilidades, networking e respostas de entrevista, preservando
proveniência factual.

## Fonte e autoridade

- `autoconhecimento.md`, `perfil_restricoes.md`, dicionários de competências e
  referências canônicas continuam sendo fontes de conteúdo.
- A base estruturada de evidências será uma referência versionada no SQLite,
  com arquivo canônico revisável no workspace.
- `candidate_cv_facts.json` continuará existindo como visão compatível para o
  gerador de CV, mas não será a base completa do candidato.
- FIT_MAP e `positioning_revisions` representam decisões por candidatura.
- Packs, DOCX, FERAS e demais saídas são derivados e nunca fontes de fatos.
- Notion continua sendo memória operacional e snapshot legível da candidatura;
  não será fonte primária de evidências na primeira versão.

## Registro mínimo de uma história

Cada história estruturada deve conter:

```json
{
  "story_id": "wehandle_margin_efficiency",
  "title": "Eficiência operacional em atendimento",
  "experience_id": "wehandle_head_operacoes",
  "context": "Contexto factual do problema",
  "actions": ["Ação comprovada"],
  "results": ["Resultado comprovado"],
  "metrics": ["Métrica com unidade e período"],
  "capabilities": ["Competência demonstrada"],
  "allowed_claims": ["Formulação permitida no material de candidatura"],
  "source_refs": [
    {"path": ".agents/skills/career-system/references/autoconhecimento.md", "lines": "120-128"}
  ],
  "artifact_guidance": {
    "cv": "Formulação factual curta",
    "feras": "Ângulo narrativo em primeira pessoa",
    "interview": "Resposta em estrutura situação-ação-resultado"
  }
}
```

Uma interpretação estratégica — por exemplo, “reposicionar experiência de
operações para transformação” — deve ser armazenada separadamente da história
e nunca substituir a evidência original.

## Contrato de posicionamento por candidatura

O pacote scoped deve carregar `application_id`, `fit_map_revision_id`,
`positioning_revision_id`, `candidate_evidence_revision_id`, tese, persona,
stories selecionadas, claims permitidos, keywords, gaps e um mapa de destinos
por artefato. Cada artefato pode usar apenas histórias/claims desse pacote.

## Critérios de aceitação

1. Uma nova história incluída na base estruturada pode ser encontrada pelo
   FIT_MAP e materializada no pack sem alterar manualmente o DOCX.
2. Uma história selecionada para CV e FERAS aparece em ambos com redação
   adequada ao formato e o mesmo `story_id` de origem.
3. Uma afirmação sem `source_refs` ou `allowed_claims` não passa para saída
   aprovada.
4. Alterar uma evidência muda sua revisão/hash e invalida packs e artefatos que
   dependem dela.
5. O sync do Notion continua funcionando com os campos atuais e publica o
   resumo da revisão final, sem exigir nova propriedade.
