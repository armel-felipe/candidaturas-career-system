---
name: processe-a-vaga
description: >
  Use when the user asks to process a job end to end, such as "processe a vaga",
  "faz tudo" or "analisa e registra", after the job has an identified source.
---

# Processe a Vaga — Pacote-base

## Pacote-base

Esta skill fecha somente o pacote-base da candidatura. O resultado esperado é:

1. intake persistido no SQLite;
2. FIT_MAP final, pontuado e validado;
3. para `standard_cv`: CV DOCX gerado/aprovado e entregue no OneDrive;
4. para `gupy_registration`: inscrição/registro Gupy comprovado no Notion;
5. registro do Notion criado ou atualizado.

O fechamento do pacote-base é representado pelo estágio `core_package_sealed`.
O `delivery_profile` é persistido na candidatura; nunca inferir CV obrigatório
somente porque o arquivo não existe. FERAS, carta de apresentação e habilidades
Gupy são pós-processamento e ficam fora do fechamento desta skill.

## Identidade e autoridade

- Resolver a candidatura por `application_id` usando `applications:resolve` e
  `applications:reconcile`/os repositórios SQLite-scoped equivalentes. O
  resolvedor exige um seletor explícito (`--application-id`, `--notion-id`,
  fingerprint ou identidade composta) e nunca consulta o ponteiro global.
- Passar `--application-id` em todas as etapas depois do intake.
- Usar somente `.career-state/applications_v2/<application_id>/` para arquivos de
  compatibilidade da execução.
- Nunca usar `active_job`, `active_intake`, `.career-state/fit_map.json` ou
  `.career-state/workflow_state.json` para escolher a vaga.
- Nunca escrever, limpar ou sincronizar destrutivamente `workflow_state.json`.

## Fluxo do pacote-base

### 1. Intake

Usar o comando canônico conforme a origem:

```bash
npm run intake:linkedin-job -- --url "<url>"
npm run intake:paste -- --company "<empresa>" --role "<cargo>" --text-file <arquivo>
npm run agent:evaluate-notion -- <id_unico>
```

Guardar o `application_id` e o fingerprint retornados. Se houver interrupção,
retomar com `npm run intake:resume -- --application-id "<id>"`.

### Rota de produção celular

O pedido end-to-end (`processe a vaga`, `faz tudo`, `analisa e registra`) não é
executado como uma sequência livre de comandos pelo modelo. Depois do intake,
usar o orquestrador celular:

```bash
npm run applications:plan -- --application-id "<id>" --deliverable cv
npm run applications:run -- --application-id "<id>" --run-id "<run_id_retornado>" --run-agent
npm run applications:inspect-run -- --application-id "<id>" --run-id "<run_id>"
```

Se uma célula bloquear, reparar somente o nó indicado e retomar o mesmo
`run_id`:

```bash
npm run applications:repair -- --application-id "<id>" --run-id "<run_id>" --node "<node_id>" --reason "<motivo objetivo>"
```

O agente não pode cair para `fit-map:finalize`, executar uma etapa posterior
manualmente ou injetar provenance no FIT_MAP para contornar um bloqueio
celular. Se faltar binding, manifest ou receipt, declarar a execução bloqueada
com o nó e o motivo objetivos. A criação/atualização no Notion permanece uma
ação separada e só ocorre quando o usuário a autorizar explicitamente.

### 2. FIT_MAP

As instruções abaixo valem para uma análise FIT_MAP isolada. Em um pedido
end-to-end, a análise pertence à célula `analyze_fit` da rota de produção
celular acima; não cair para `fit-map:finalize` legado.

Ler as referências obrigatórias, preencher o draft no diretório da candidatura
e executar os gates na ordem:

```bash
npm run validate:fit-map:draft -- --application-id "<id>"
npm run fit-map:finalize -- --application-id "<id>"
npm run validate:fit-map:quality -- --application-id "<id>"
npm run fit-map:summary -- --application-id "<id>"
```

O FIT_MAP final deve estar vinculado ao fingerprint e à revisão atual da
descrição. Não reaproveitar análise histórica sem vínculo explícito.

### 3. CV, revisão e entrega (`standard_cv`)

Executar o pipeline CV com o mesmo `application_id`, registrar keywords sobre o
DOCX final e rodar o reviewer objetivo antes de aprovar:

```bash
npm run cv:build-content -- --application-id "<id>"
npm run cv:validate-content -- --application-id "<id>"
npm run cv:docx
npm run validate:docx
python3 scripts/register_keywords.py --fit-map .career-state/applications_v2/<id>/fit_map.json --cv outputs/<cv>.docx --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json
python3 scripts/review_output.py --kind cv --artifact outputs/<cv>.docx --fit-map .career-state/applications_v2/<id>/fit_map.json --registry .career-state/applications_v2/<id>/derived/keyword_ats_registry.json --report outputs/_tmp/output_review_report.json
npm run cv:deliver -- --application-id "<application_id>" --artifact outputs/<cv>.docx
```

Não considerar o pacote fechado sem `approved_for_delivery=true` e entrega
confirmada pelo relatório do OneDrive.

Para `gupy_registration`, não executar esta etapa por padrão. O registro da
inscrição no Notion é a evidência de entrega; somente gerar CV/OneDrive se o
pedido do usuário criar essa necessidade.

### 4. Notion

Depois dos gates do CV e da entrega, criar ou atualizar o registro pelo
`application_id`, usando o job description persistido e sem selecionar outra
candidatura por ponteiro global.

## Pós-processamento

Depois de `core_package_sealed`, usar o serviço SQLite-scoped de pós-processamento:

- `create_post_artifact(application_id, "feras")`;
- `create_post_artifact(application_id, "gupy_skills")`;
- `create_post_artifact(application_id, "cover_letter")`;
- `list_post_artifacts(application_id)`;
- `read_post_artifact(application_id, artifact_id)`;
- `revise_positioning(application_id, changes)`.

Cada saída fica ligada à revisão do FIT_MAP e, quando aplicável, à revisão de
posicionamento. Uma revisão nova preserva os artefatos antigos e não reabre nem
limpa os gates do pacote-base.

## Critério de conclusão

Só declarar a skill concluída quando houver evidência do contrato correspondente
ao `delivery_profile`, atualização Notion e estágio `core_package_sealed`.
Saídas de pós-processamento são tarefas reentrantes e devem ser revisadas por
`output-reviewer` antes de serem entregues.
