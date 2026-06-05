from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from career.utils import ValidationFailure, ensure


PLACEHOLDER_MARKERS = (
    "[preencher",
    "[keyword",
    "[competencia",
    "[termo",
    "[empresa",
    "[numero",
    "[angulo",
    "[ajuste",
    "[texto",
    "[1-2 frases",
    "titulo | requisitos | responsabilidades | diferenciais",
    "hard skill | soft skill | ferramenta | setor",
    "DIRETO | REPOSICIONAMENTO | GAP",
    "forte | media | fraca",
    "forte | media | fraca | leve",
    "Responsável | Utilizando | Consegui | Resumo | Stack",
    "já selecionada | adicionada por densidade | gap sem cobertura",
    "[arquivo:linhas]",
)

WEAK_PLACEHOLDER_VALUES = {
    "-",
    "--",
    "---",
    "...",
    "n/a",
    "na",
    "não informado",
    "nao informado",
    "a definir",
    "arquivo",
    "arquivo:linha",
    "arquivo:linhas",
    "fonte:linhas",
    "tbd",
    "x",
    "y",
    "z",
}

WEAK_PLACEHOLDER_PATTERNS = (
    re.compile(r"\.\.\."),
    re.compile(r"\b(?:empresa|companhia|projeto|case)\s+[xyz]\b", re.IGNORECASE),
)


def _iter_strings(value: Any, trail: str = "$"):
    if isinstance(value, str):
        yield trail, value
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_strings(item, f"{trail}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _iter_strings(item, f"{trail}.{key}")


@dataclass(slots=True)
class FitMapDraftSchema:
    payload: dict[str, Any]

    def validate(self) -> dict[str, Any]:
        ensure(isinstance(self.payload, dict), "Draft FIT_MAP root must be an object")
        placeholders: list[str] = []
        for field_path, text in _iter_strings(self.payload):
            lowered = text.strip().casefold()
            if lowered in WEAK_PLACEHOLDER_VALUES:
                placeholders.append(f"{field_path} contains weak placeholder: {text!r}")
                continue
            for pattern in WEAK_PLACEHOLDER_PATTERNS:
                if pattern.search(text):
                    placeholders.append(f"{field_path} contains weak placeholder pattern: {text!r}")
                    break
            else:
                for marker in PLACEHOLDER_MARKERS:
                    if marker.casefold() in lowered:
                        placeholders.append(f"{field_path} contains unresolved placeholder: {text!r}")
                        break
                continue
            continue
        if placeholders:
            raise ValidationFailure("Draft FIT_MAP still contains placeholders:\n- " + "\n- ".join(placeholders))
        return self.payload


@dataclass(slots=True)
class FitMapFinalSchema:
    payload: dict[str, Any]

    REQUIRED_TOP_LEVEL = [
        "cargo",
        "empresa",
        "modo",
        "dor_central",
        "keywords_vaga",
        "competencias_vaga",
        "keywords_para_ats",
        "mapa_ajuste",
        "objecoes",
        "nota_aderencia",
        "gaps_sem_cobertura",
        "historias_selecionadas",
        "keywords_habilidade_ats",
    ]

    REQUIRED_STORIES = ["principal", "secundaria", "terceira"]

    def validate(self) -> dict[str, Any]:
        ensure(isinstance(self.payload, dict), "FIT_MAP root must be an object")
        missing = [key for key in self.REQUIRED_TOP_LEVEL if key not in self.payload]
        ensure(not missing, "Missing top-level fields: " + ", ".join(missing))
        for key in ["cargo", "empresa", "modo", "dor_central"]:
            ensure(isinstance(self.payload.get(key), str) and self.payload[key].strip(), f"{key} must be a non-empty string")

        stories = self.payload.get("historias_selecionadas")
        ensure(isinstance(stories, dict), "historias_selecionadas must be an object")
        for story_name in self.REQUIRED_STORIES:
            story = stories.get(story_name)
            ensure(isinstance(story, dict), f"historias_selecionadas.{story_name} must be an object")
            for key in ["empresa", "resultado", "angulo"]:
                ensure(isinstance(story.get(key), str) and story[key].strip(), f"historias_selecionadas.{story_name}.{key} must be a non-empty string")
            covered = story.get("keywords_cobertas")
            ensure(isinstance(covered, list) and covered, f"historias_selecionadas.{story_name}.keywords_cobertas must be a non-empty array")

        ats_items = self.payload.get("keywords_habilidade_ats")
        ensure(isinstance(ats_items, list) and len(ats_items) == 15, "keywords_habilidade_ats must contain exactly 15 items")
        priorities = [item.get("prioridade") for item in ats_items if isinstance(item, dict)]
        ensure(len(priorities) == 15, "keywords_habilidade_ats entries must be objects")
        ensure(sorted(priorities) == list(range(1, 16)), "keywords_habilidade_ats priorities must be a contiguous sequence starting at 1")

        score = self.payload.get("nota_aderencia")
        ensure(isinstance(score, dict), "nota_aderencia must be a scored object")
        ensure(isinstance(score.get("final"), (int, float)), "nota_aderencia.final must be numeric")
        ensure(isinstance(score.get("dimensoes"), dict), "nota_aderencia.dimensoes must be an object")
        return self.payload
