from __future__ import annotations

import re

INTENT_PATTERNS: dict[str, list[str]] = {
    "analyze_job": [
        "analisa",
        "avalia",
        "como me encaixo",
        "analise a vaga",
        "aderencia",
        "aderência",
        "fit_map",
        "fit map",
    ],
    "generate_cv": [
        "gera cv",
        "currículo",
        "curriculo",
        "cv para",
        "gerar cv",
        "adaptar cv",
        r"\bcv\b",
    ],
    "generate_feras": [
        "pitch",
        "feras",
        "me fale sobre você",
        "me fale sobre voce",
        "resumo gupy",
    ],
    "generate_cover_letter": [
        "carta de apresentação",
        "carta de apresentacao",
        "cover letter",
    ],
    "query_applications": [
        "vagas com",
        "filtro",
        "etapa funil",
        "aplicação em análise",
        "aplicacao em analise",
        "status das candidaturas",
        "status da fila",
        "applications status",
    ],
    "networking": [
        "mensagem linkedin",
        "networking",
        "contato recrutador",
    ],
    "notion_sync": [
        "notion",
        "sincronizar",
        "sweep",
    ],
    "reset": [
        "resetar",
        "reiniciar",
        "limpar base",
        "recomeçar",
        "recomecar",
    ],
    "email_draft": [
        "email",
        "gmail",
    ],
    "menu": [
        "menu",
        "opcoes",
        "opções",
        "o que posso fazer",
        "atalhos",
    ],
    "linkedin_saved_jobs": [
        "vagas salvas",
        "saved jobs",
        "rastreador de vagas",
    ],
    "resume": [
        "continue o trabalho em andamento",
        "retomar trabalho em andamento",
        "retome o trabalho em andamento",
        "continue de onde parou",
    ],
    "heartbeat": [
        "heartbeat",
        "processar fila",
        "rodar fila",
        "executar fila",
        "processar candidaturas",
    ],
    "habilidades": [
        "gupy",
        "mercado livre",
        "habilidades",
        "resumo ats",
    ],
}


class Classifier:
    def classify(self, message: str) -> str:
        raw_text = str(message or "").strip()
        if not raw_text:
            return "unknown"
        lowered = " ".join(raw_text.split()).casefold()

        for intent, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if pattern.startswith(r"\b"):
                    if re.search(pattern, lowered):
                        return intent
                elif pattern in lowered:
                    return intent

        return "unknown"
