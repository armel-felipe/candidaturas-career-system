# Learned Lessons — Memória Adicional

Registro de lições aprendidas e convenções operacionais para consulta rápida.
Este arquivo serve como memória adicional do sistema de candidaturas.

## Autorização presumida em pedidos de atualização

- **Regra:** quando o usuário pede explicitamente criar/atualizar/salvar um
  registro (ex.: atualização do Notion, geração de CV, envio para OneDrive),
  o pedido **presume autorização** — o harness pode executar a escrita real
  **sem segunda confirmação**.
- **Fundamento:** a policy `notion_write=explicit_request` já cobre esse caso.
  Se o usuário pediu explicitamente a ação, não é preciso perguntar de novo.
- **Exceção:** se o pedido for de *prévia*, *preview* ou *dry-run*, manter
  apenas o dry-run e **não** disparar a escrita real.
- **Aplicação prática:** pedidos como "quero a geração do cv personalizado,
  atualização do registro do notion, e envio do cv para o onedrive" autorizam
  a execução completa do fluxo sem confirmação adicional.
- **NUNCA perguntar "quer que eu faça?" depois de um pedido explícito.** Se o
  usuário pediu, executa. Pedir confirmação redundante é burrice e trava o fluxo.

## Outras lições

- **Fluxo manual de CV + Notion + OneDrive (vaga app-scoped):** o `cv build-content --application-id <ID>` gera o conteúdo correto a partir do FIT_MAP app-scoped, mas salva em `.career-state/cv_content.json` (global). O `cv validate-content --application-id <ID>` espera o path app-scoped e valida OK. Para o reviewer/approve, passar `--fit-map .career-state/applications_v2/<ID>/fit_map.json` explicitamente — sem isso, usa o FIT_MAP global (stale) e bloqueia.
- **Campo "Arquivo final aprovado" no Notion:** só é preenchido se o `fit_map.json` tiver `service_final_artifact` (e `service_final_cv_language`, `service_review_status`, `service_status`, `service_stage`). Em fluxo manual, adicionar esses campos ao fit_map.json antes do `update-from-fit-map-record`.
- **`update-from-fit-map-record` exige job-description com filename `notion_record_<id>.md` ou `conexa_<cargo>.md`** (slug do cargo) — o path app-scoped `job_description.md` falha no check de mismatch. Usar `inbox/job_descriptions/`.
- **`--extra-artifact` do Notion só aceita texto** (.md/.txt/.json), não DOCX. O CV entra pelo campo "Arquivo final aprovado" via `service_final_artifact`.
- **Keywords ATS em inglês em CV PT-BR:** adicionar entradas de tradução ao `keyword_translation_registry.json` e injetar os termos nos bullets (tanto `experiencias[]` strings quanto `experiences[]` objetos) antes de regenerar o DOCX. O reviewer usa os equivalentes PT-BR como cobertura defensável.
- **Travessão largo (em-dash `—` / en-dash `–`) no CV:** a regra canônica já está automatizada em `_sanitize_punctuation` (`src/career/services/cv_content.py`), que roda no `cv:build-content` e troca `—`/`–` por hífen/vírgula conforme o contexto. Não replique a regra manualmente — siga o pipeline. O risco real é a injeção manual de keywords ATS **após** o `build-content` reintroduzir `—` no final dos bullets. Procedimento para não errar: 1) injete keywords de forma natural na prosa PT-BR (equivalentes do `keyword_translation_registry.json`), nunca como sufixo `" — Keyword."`; 2) regenere o DOCX e rode os gates do `cv-generator` (`validate:docx`, `register_keywords.py`, `review_output.py`, `cv:approve`); 3) antes de entregar, confira o DOCX final com contagem de `\u2014`/`\u2013` = 0 — o `validate_docx.py` ainda não cobre isso, então é verificação manual.
- **OneDrive v2:** ao corrigir um CV já entregue, gerar `_v2.docx` (nunca sobrescrever o nome existente) e entregar como nova versão; atualizar o campo "Arquivo final aprovado" no Notion para apontar para a v2.
