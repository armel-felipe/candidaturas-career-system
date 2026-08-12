# Routing Table — Career System

| Pedido | Skill | Módulos |
|---|---|---|
| Analisar vaga, URL ou texto | `intake-orchestrator` → `career-fit-analysis` | runtime-core, intake-fit-map |
| Gerar CV | `cv-generator` | runtime-core, cv-delivery |
| Carta, pitch, habilidades, networking | skill correspondente | runtime-core, intake-fit-map |
| Notion, planilha ou email | skill correspondente | runtime-core, notion-email |
| Pipeline completo | `processe-a-vaga` | runtime-core, intake-fit-map, cv-delivery, notion-email |

Carregue a skill e os módulos declarados em seu front matter. Não carregue a biblioteca inteira por padrão.
