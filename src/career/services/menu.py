from __future__ import annotations


class MenuBuilder:
    def build(self, state: dict | None = None) -> list[dict]:
        state = state or {}
        options = [
            {"id": "analyze_job", "label": "Analisar vaga", "description": "Avaliar aderência a uma vaga"},
            {"id": "generate_cv", "label": "Gerar CV", "description": "Produzir currículo para a vaga ativa"},
            {"id": "generate_feras", "label": "Pitch / FERAS", "description": "Produzir pitch executivo"},
            {"id": "generate_cover_letter", "label": "Carta de apresentação", "description": "Produzir cover letter"},
            {"id": "query_applications", "label": "Consultar candidaturas", "description": "Filtrar e listar vagas"},
            {"id": "networking", "label": "Mensagem networking", "description": "Gerar mensagem para LinkedIn"},
            {"id": "notion_sync", "label": "Sincronizar Notion", "description": "Atualizar cache do Notion"},
            {"id": "reset", "label": "Resetar estado", "description": "Limpar estado ativo e recomeçar"},
        ]
        active = state.get("active_intake")
        if active:
            options.insert(
                0,
                {
                    "id": "resume",
                    "label": f"Continuar {active.get('role', 'vaga ativa')}",
                    "description": "Retomar do próximo passo salvo",
                },
            )
        return options

    def render(self, options: list[dict]) -> str:
        lines = ["Opções disponíveis:"]
        for i, opt in enumerate(options, start=1):
            lines.append(f"{i}. {opt['label']} — {opt['description']}")
        lines.append("")
        lines.append("Digite o número ou descreva o que deseja fazer.")
        return "\n".join(lines)
