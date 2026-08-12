#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from build_fit_map import canonical_fit_map


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


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def iter_strings(value, trail: str = "$"):
    if isinstance(value, str):
        yield trail, value
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_strings(item, f"{trail}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from iter_strings(item, f"{trail}.{key}")


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".career-state/fit_map.draft.json")
    if not path.exists():
        print(f"Draft FIT_MAP not found: {path}", file=sys.stderr)
        return 1

    try:
        draft = read_json(path)
    except Exception as exc:
        print(f"Invalid JSON in draft {path}: {exc}", file=sys.stderr)
        return 1

    placeholders: list[str] = []
    for field_path, text in iter_strings(draft):
        lowered = text.strip().casefold()
        for marker in PLACEHOLDER_MARKERS:
            if marker.casefold() in lowered:
                placeholders.append(f"{field_path} contains unresolved placeholder: {text!r}")
                break

    if placeholders:
        print("Draft FIT_MAP still contains placeholders:", file=sys.stderr)
        for item in placeholders:
            print(f"- {item}", file=sys.stderr)
        return 1

    try:
        canonical_fit_map(draft)
    except Exception as exc:
        print(f"Draft FIT_MAP invalid: {exc}", file=sys.stderr)
        return 1

    print(f"Draft FIT_MAP valid: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
