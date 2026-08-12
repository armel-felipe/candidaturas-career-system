# runtime-core

## Mandatory rules

- **profile Hermes → candidatura**: cada `HERMES_HOME` possui uma única candidatura ativa e cada candidatura tem um único profile ativo.
- Em sessão Hermes direta, **não usar estado global**; usar somente `.career-state/applications_v2/<application_id>/` e artefatos app-scoped.
- Mensagens seguintes retomam a candidatura vinculada. Consultar `career applications profile-status` para inspecionar o vínculo.
- Trocar de vaga exige `career applications profile-release --application-id <ID>` antes do novo intake.
- Sem binding ativo, pedir uma origem de vaga; nunca inferir contexto por sessão de outro profile, FIT_MAP global ou arquivo global.
- Trabalhar por ponteiros e resumos compactos; não despejar JSONs, descrições ou relatórios longos na conversa.
