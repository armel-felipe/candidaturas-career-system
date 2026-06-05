#!/usr/bin/env python3
import json
import sys
from pathlib import Path


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
REQUIRED_KEYWORD_ENTRY = ["termo", "origem"]
REQUIRED_COMPETENCY_ENTRY = ["competencia", "tipo"]
REQUIRED_ADJUSTMENT_ENTRY = [
    "termo_vaga",
    "tipo_ajuste",
    "evidencia",
    "empresa_origem",
    "resultado_numero",
    "angulo_sugerido",
    "ajustes_feitos",
    "defensavel",
]
REQUIRED_OBJECTION_ENTRY = [
    "objecao",
    "classificacao",
    "origem",
    "mitigacao",
    "evidencia_real",
]
REQUIRED_STORY_ENTRY = ["empresa", "resultado", "keywords_cobertas", "angulo", "ajustes"]
REQUIRED_ATS_ENTRY = ["keyword", "prioridade", "experiencia_alvo", "bullet_sugerido", "origem"]
REQUIRED_SCORE_DIMENSIONS = [
    "requisitos_obrigatorios",
    "responsabilidades_principais",
    "ausencia_gaps_criticos",
    "diferenciais_desejaveis",
]
REQUIRED_KEYWORD_ORIGINS = {"titulo", "requisitos", "responsabilidades", "diferenciais"}
REQUIRED_COMPETENCY_TYPES = {"hard skill", "soft skill", "ferramenta", "setor"}
REQUIRED_ADJUSTMENT_TYPES = {"DIRETO", "REPOSICIONAMENTO", "GAP"}
REQUIRED_OBJECTION_CLASSES = {"forte", "media", "média", "fraca"}
REQUIRED_ATS_ORIGINS = {"já selecionada", "adicionada por densidade", "gap sem cobertura"}
REQUIRED_ATS_BULLETS = {"Responsável", "Utilizando", "Consegui", "Resumo", "Stack"}


def require_string(value, field_name: str):
    if not isinstance(value, str):
        print(f"{field_name} must be a string", file=sys.stderr)
        return None
    if not value.strip():
        print(f"{field_name} must not be empty", file=sys.stderr)
        return None
    return value


def require_list_of_strings(values, field_name: str) -> bool:
    if not isinstance(values, list):
        print(f"{field_name} must be an array", file=sys.stderr)
        return False
    for index, item in enumerate(values):
        if not isinstance(item, str):
            print(f"{field_name}[{index}] must be a string", file=sys.stderr)
            return False
    return True


def require_non_empty_list(values, field_name: str, *, minimum: int = 1, maximum=None) -> bool:
    if not isinstance(values, list):
        print(f"{field_name} must be an array", file=sys.stderr)
        return False
    if len(values) < minimum:
        print(f"{field_name} must contain at least {minimum} item(s)", file=sys.stderr)
        return False
    if maximum is not None and len(values) > maximum:
        print(f"{field_name} must contain at most {maximum} item(s)", file=sys.stderr)
        return False
    return True


def require_choice(value: str, field_name: str, allowed: set[str]) -> bool:
    if value not in allowed:
        print(f"{field_name} must be one of: {', '.join(sorted(allowed))}", file=sys.stderr)
        return False
    return True


def require_object_list(entries, field_name: str, required_keys: list[str]) -> bool:
    if not isinstance(entries, list):
        print(f"{field_name} must be an array", file=sys.stderr)
        return False
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            print(f"{field_name}[{index}] must be an object", file=sys.stderr)
            return False
        missing = [key for key in required_keys if key not in item]
        if missing:
            print(
                f"{field_name}[{index}] missing keys: {', '.join(missing)}",
                file=sys.stderr,
            )
            return False
    return True


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".career-state/fit_map.json")
    if not path.exists():
        print(f"FIT_MAP not found: {path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Invalid JSON in {path}: {exc}", file=sys.stderr)
        return 1

    missing = [key for key in REQUIRED_TOP_LEVEL if key not in data]
    if missing:
        print("Missing top-level fields: " + ", ".join(missing), file=sys.stderr)
        return 1

    for key in ["cargo", "empresa", "modo", "dor_central"]:
        if require_string(data.get(key), key) is None:
            return 1

    stories = data.get("historias_selecionadas")
    if not isinstance(stories, dict):
        print("historias_selecionadas must be an object", file=sys.stderr)
        return 1

    missing_stories = [key for key in REQUIRED_STORIES if key not in stories]
    if missing_stories:
        print("Missing story fields: " + ", ".join(missing_stories), file=sys.stderr)
        return 1

    list_fields = [
        "keywords_vaga",
        "competencias_vaga",
        "keywords_para_ats",
        "mapa_ajuste",
        "objecoes",
        "gaps_sem_cobertura",
        "keywords_habilidade_ats",
    ]
    bad_lists = [key for key in list_fields if not isinstance(data.get(key), list)]
    if bad_lists:
        print("Fields must be arrays: " + ", ".join(bad_lists), file=sys.stderr)
        return 1

    if not require_object_list(data.get("keywords_vaga"), "keywords_vaga", REQUIRED_KEYWORD_ENTRY):
        return 1
    if not require_object_list(data.get("competencias_vaga"), "competencias_vaga", REQUIRED_COMPETENCY_ENTRY):
        return 1
    if not require_object_list(data.get("mapa_ajuste"), "mapa_ajuste", REQUIRED_ADJUSTMENT_ENTRY):
        return 1
    if not require_object_list(data.get("objecoes"), "objecoes", REQUIRED_OBJECTION_ENTRY):
        return 1
    if not require_object_list(
        data.get("keywords_habilidade_ats"),
        "keywords_habilidade_ats",
        REQUIRED_ATS_ENTRY,
    ):
        return 1
    if not require_non_empty_list(data.get("keywords_vaga"), "keywords_vaga"):
        return 1
    if not require_non_empty_list(data.get("competencias_vaga"), "competencias_vaga"):
        return 1
    if not require_non_empty_list(data.get("mapa_ajuste"), "mapa_ajuste", minimum=3):
        return 1
    if not require_non_empty_list(data.get("objecoes"), "objecoes", minimum=3, maximum=5):
        return 1
    if not require_non_empty_list(data.get("gaps_sem_cobertura"), "gaps_sem_cobertura"):
        return 1
    if not require_non_empty_list(data.get("keywords_habilidade_ats"), "keywords_habilidade_ats", minimum=15, maximum=15):
        return 1

    if not require_list_of_strings(data.get("keywords_para_ats"), "keywords_para_ats"):
        return 1
    if not require_list_of_strings(data.get("gaps_sem_cobertura"), "gaps_sem_cobertura"):
        return 1

    for index, item in enumerate(data.get("keywords_vaga", [])):
        if require_string(item.get("termo"), f"keywords_vaga[{index}].termo") is None:
            return 1
        origin = require_string(item.get("origem"), f"keywords_vaga[{index}].origem")
        if origin is None:
            return 1
        if not require_choice(origin, f"keywords_vaga[{index}].origem", REQUIRED_KEYWORD_ORIGINS):
            return 1

    for index, item in enumerate(data.get("competencias_vaga", [])):
        if require_string(item.get("competencia"), f"competencias_vaga[{index}].competencia") is None:
            return 1
        competence_type = require_string(item.get("tipo"), f"competencias_vaga[{index}].tipo")
        if competence_type is None:
            return 1
        if not require_choice(competence_type, f"competencias_vaga[{index}].tipo", REQUIRED_COMPETENCY_TYPES):
            return 1

    for index, item in enumerate(data.get("mapa_ajuste", [])):
        if require_string(item.get("termo_vaga"), f"mapa_ajuste[{index}].termo_vaga") is None:
            return 1
        adjustment_type = require_string(item.get("tipo_ajuste"), f"mapa_ajuste[{index}].tipo_ajuste")
        if adjustment_type is None:
            return 1
        if not require_choice(adjustment_type, f"mapa_ajuste[{index}].tipo_ajuste", REQUIRED_ADJUSTMENT_TYPES):
            return 1
        for key in ["evidencia", "empresa_origem", "resultado_numero", "angulo_sugerido"]:
            if require_string(item.get(key), f"mapa_ajuste[{index}].{key}") is None:
                return 1
        if not require_list_of_strings(item.get("ajustes_feitos"), f"mapa_ajuste[{index}].ajustes_feitos"):
            return 1
        if adjustment_type != "GAP" and not item.get("ajustes_feitos"):
            print(f"mapa_ajuste[{index}].ajustes_feitos must contain at least one item for non-GAP adjustments", file=sys.stderr)
            return 1
        if not isinstance(item.get("defensavel"), bool):
            print(f"mapa_ajuste[{index}].defensavel must be boolean", file=sys.stderr)
            return 1
        if adjustment_type == "GAP" and item.get("defensavel") is not False:
            print(f"mapa_ajuste[{index}].defensavel must be false when tipo_ajuste is GAP", file=sys.stderr)
            return 1

    for index, item in enumerate(data.get("objecoes", [])):
        for key in REQUIRED_OBJECTION_ENTRY:
            if require_string(item.get(key), f"objecoes[{index}].{key}") is None:
                return 1
        if not require_choice(
            item.get("classificacao"),
            f"objecoes[{index}].classificacao",
            REQUIRED_OBJECTION_CLASSES,
        ):
            return 1

    for story_name in REQUIRED_STORIES:
        story = stories.get(story_name)
        if story is None:
            print(f"historias_selecionadas.{story_name} must not be null", file=sys.stderr)
            return 1
        if not isinstance(story, dict):
            print(f"historias_selecionadas.{story_name} must be null or an object", file=sys.stderr)
            return 1
        missing_story_fields = [key for key in REQUIRED_STORY_ENTRY if key not in story]
        if missing_story_fields:
            print(
                f"historias_selecionadas.{story_name} missing keys: "
                + ", ".join(missing_story_fields),
                file=sys.stderr,
            )
            return 1
        for key in ["empresa", "resultado", "angulo"]:
            if require_string(story.get(key), f"historias_selecionadas.{story_name}.{key}") is None:
                return 1
        if not require_list_of_strings(
            story.get("keywords_cobertas"),
            f"historias_selecionadas.{story_name}.keywords_cobertas",
        ):
            return 1
        if not story.get("keywords_cobertas"):
            print(f"historias_selecionadas.{story_name}.keywords_cobertas must contain at least one item", file=sys.stderr)
            return 1
        if not require_list_of_strings(
            story.get("ajustes"),
            f"historias_selecionadas.{story_name}.ajustes",
        ):
            return 1

    for index, item in enumerate(data.get("keywords_habilidade_ats", [])):
        if require_string(item.get("keyword"), f"keywords_habilidade_ats[{index}].keyword") is None:
            return 1
        priority = item.get("prioridade")
        if not isinstance(priority, int):
            print(f"keywords_habilidade_ats[{index}].prioridade must be integer", file=sys.stderr)
            return 1
        if priority < 1 or priority > len(data.get("keywords_habilidade_ats", [])):
            print(f"keywords_habilidade_ats[{index}].prioridade is out of range", file=sys.stderr)
            return 1
        for key in ["experiencia_alvo", "bullet_sugerido", "origem"]:
            if require_string(item.get(key), f"keywords_habilidade_ats[{index}].{key}") is None:
                return 1
        if not require_choice(item.get("origem"), f"keywords_habilidade_ats[{index}].origem", REQUIRED_ATS_ORIGINS):
            return 1
        if not require_choice(item.get("bullet_sugerido"), f"keywords_habilidade_ats[{index}].bullet_sugerido", REQUIRED_ATS_BULLETS):
            return 1

    priorities = [item.get("prioridade") for item in data.get("keywords_habilidade_ats", [])]
    if len(priorities) != len(set(priorities)):
        print("keywords_habilidade_ats contains duplicate priorities", file=sys.stderr)
        return 1
    expected_priorities = list(range(1, len(priorities) + 1))
    if sorted(priorities) != expected_priorities:
        print("keywords_habilidade_ats priorities must form a contiguous sequence starting at 1", file=sys.stderr)
        return 1

    if set(data.get("keywords_para_ats", [])) != {item.get("keyword") for item in data.get("keywords_habilidade_ats", [])}:
        print("keywords_para_ats must mirror the exact keyword set from keywords_habilidade_ats", file=sys.stderr)
        return 1

    score = data.get("nota_aderencia")
    if score is not None and not isinstance(score, (int, float, dict)):
        print("nota_aderencia must be null, number, or calculation object", file=sys.stderr)
        return 1
    if isinstance(score, dict):
        if not isinstance(score.get("final"), (int, float)):
            print("nota_aderencia.final must be a number", file=sys.stderr)
            return 1
        dimensions = score.get("dimensoes")
        if not isinstance(dimensions, dict):
            print("nota_aderencia.dimensoes must be an object", file=sys.stderr)
            return 1
        missing_dimensions = [key for key in REQUIRED_SCORE_DIMENSIONS if key not in dimensions]
        if missing_dimensions:
            print(
                "nota_aderencia.dimensoes missing: " + ", ".join(missing_dimensions),
                file=sys.stderr,
            )
            return 1
        item_dimensions = [
            "requisitos_obrigatorios",
            "responsabilidades_principais",
            "diferenciais_desejaveis",
        ]
        for dimension_name in item_dimensions:
            dimension = dimensions.get(dimension_name)
            if not isinstance(dimension, dict):
                print(f"nota_aderencia.dimensoes.{dimension_name} must be an object", file=sys.stderr)
                return 1
            if not isinstance(dimension.get("peso"), (int, float)):
                print(f"nota_aderencia.dimensoes.{dimension_name}.peso must be numeric", file=sys.stderr)
                return 1
            if not isinstance(dimension.get("contagem_itens"), int):
                print(
                    f"nota_aderencia.dimensoes.{dimension_name}.contagem_itens must be integer",
                    file=sys.stderr,
                )
                return 1
            if not isinstance(dimension.get("soma_notas"), (int, float)):
                print(
                    f"nota_aderencia.dimensoes.{dimension_name}.soma_notas must be numeric",
                    file=sys.stderr,
                )
                return 1
            if not isinstance(dimension.get("cobertura_percentual"), (int, float)):
                print(
                    f"nota_aderencia.dimensoes.{dimension_name}.cobertura_percentual must be numeric",
                    file=sys.stderr,
                )
                return 1
            if not isinstance(dimension.get("pontos"), (int, float)):
                print(f"nota_aderencia.dimensoes.{dimension_name}.pontos must be numeric", file=sys.stderr)
                return 1
            items = dimension.get("itens")
            if not require_non_empty_list(items, f"nota_aderencia.dimensoes.{dimension_name}.itens"):
                return 1
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    print(
                        f"nota_aderencia.dimensoes.{dimension_name}.itens[{index}] must be an object",
                        file=sys.stderr,
                    )
                    return 1
                for key in ["item", "tipo", "evidencia", "resultado"]:
                    if require_string(item.get(key), f"nota_aderencia.dimensoes.{dimension_name}.itens[{index}].{key}") is None:
                        return 1
                if require_string(item.get("fonte_base"), f"nota_aderencia.dimensoes.{dimension_name}.itens[{index}].fonte_base") is None:
                    return 1
                if "prova_literal" in item and not isinstance(item.get("prova_literal"), bool):
                    print(
                        f"nota_aderencia.dimensoes.{dimension_name}.itens[{index}].prova_literal must be boolean",
                        file=sys.stderr,
                    )
                    return 1
                for key in ["nota", "nota_maxima", "ponderacao"]:
                    if not isinstance(item.get(key), (int, float)):
                        print(
                            f"nota_aderencia.dimensoes.{dimension_name}.itens[{index}].{key} must be numeric",
                            file=sys.stderr,
                        )
                        return 1
                if not require_choice(
                    item.get("tipo"),
                    f"nota_aderencia.dimensoes.{dimension_name}.itens[{index}].tipo",
                    REQUIRED_ADJUSTMENT_TYPES,
                ):
                    return 1
                if item.get("nota") == 1.0 and item.get("tipo") != "DIRETO":
                    print(
                        f"nota_aderencia.dimensoes.{dimension_name}.itens[{index}] with nota=1.0 must have tipo=DIRETO",
                        file=sys.stderr,
                    )
                    return 1
                if item.get("nota") == 1.0 and item.get("prova_literal") is not True:
                    print(
                        f"nota_aderencia.dimensoes.{dimension_name}.itens[{index}] with nota=1.0 must have prova_literal=true",
                        file=sys.stderr,
                    )
                    return 1

        gap_dimension = dimensions.get("ausencia_gaps_criticos")
        if not isinstance(gap_dimension, dict):
            print("nota_aderencia.dimensoes.ausencia_gaps_criticos must be an object", file=sys.stderr)
            return 1
        for key in ["peso", "desconto_total", "cobertura_percentual", "pontos"]:
            if not isinstance(gap_dimension.get(key), (int, float)):
                print(
                    f"nota_aderencia.dimensoes.ausencia_gaps_criticos.{key} must be numeric",
                    file=sys.stderr,
                )
                return 1
        gaps = gap_dimension.get("gaps")
        if not isinstance(gaps, list):
            print("nota_aderencia.dimensoes.ausencia_gaps_criticos.gaps must be an array", file=sys.stderr)
            return 1
        for index, gap in enumerate(gaps):
            if not isinstance(gap, dict):
                print(
                    f"nota_aderencia.dimensoes.ausencia_gaps_criticos.gaps[{index}] must be an object",
                    file=sys.stderr,
                )
                return 1
            for key in ["gap", "severidade"]:
                if require_string(gap.get(key), f"nota_aderencia.dimensoes.ausencia_gaps_criticos.gaps[{index}].{key}") is None:
                    return 1
            if not isinstance(gap.get("desconto"), (int, float)):
                print(
                    f"nota_aderencia.dimensoes.ausencia_gaps_criticos.gaps[{index}].desconto must be numeric",
                    file=sys.stderr,
                )
                return 1
            if gap.get("severidade") not in {"forte", "media", "média", "fraca", "leve"}:
                print(
                    f"nota_aderencia.dimensoes.ausencia_gaps_criticos.gaps[{index}].severidade must be forte/media/média/fraca/leve",
                    file=sys.stderr,
                )
                return 1

    print(f"FIT_MAP valid: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
