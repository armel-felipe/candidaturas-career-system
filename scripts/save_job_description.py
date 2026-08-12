#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


DEFAULT_OUTPUT_DIR = Path("inbox/job_descriptions")


def slugify(value: str, max_length: int = 80) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    value = value[:max_length].strip("_")
    return value or "vaga_sem_nome"


def normalize_text(value: str) -> str:
    lines = value.replace("\r\n", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip() + "\n"


def load_fit_map(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_text(args: argparse.Namespace) -> str:
    if args.text_file:
        if args.text_file == "-":
            raise ValueError(
                "`--text-file -` nao e suportado por este script. "
                "Para texto vindo da conversa/pipe, use `--stdin`. "
                "Para arquivo ja salvo, passe um caminho real em `--text-file`."
            )
        return Path(args.text_file).read_text(encoding="utf-8")
    if args.stdin:
        import sys

        return sys.stdin.read()
    raise ValueError("Provide --text-file or --stdin.")


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "Salva a descricao bruta da vaga em inbox/job_descriptions com nome padronizado. "
            "--fit-map e opcional: quando empresa/cargo ainda nao existirem no FIT_MAP, "
            "use --company e --role."
        ),
        epilog=(
            "Exemplos:\n"
            "  python scripts/save_job_description.py --company \"Empresa\" --role \"Cargo\" "
            "--text-file inbox/job_descriptions/raw.md\n"
            "  @'\\nTexto bruto da vaga\\n'@ | python scripts/save_job_description.py "
            "--company \"Empresa\" --role \"Cargo\" --stdin\n"
            "\n"
            "Observacao: `--text-file -` nao usa stdin neste script. Use `--stdin`."
        ),
    )
    parser.add_argument(
        "--fit-map",
        default=".career-state/fit_map.json",
        help="FIT_MAP opcional usado apenas para inferir empresa/cargo quando esses argumentos nao forem passados.",
    )
    parser.add_argument("--company", help="Empresa da vaga quando ainda nao houver FIT_MAP ativo.")
    parser.add_argument("--role", help="Cargo da vaga quando ainda nao houver FIT_MAP ativo.")
    parser.add_argument(
        "--text-file",
        help="Arquivo com o texto bruto da vaga. Passe um caminho real; nao use `-`.",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Le o texto bruto da vaga da entrada padrao (use quando o texto vier da conversa/pipe).",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Diretorio de saida para o markdown salvo.")
    args = parser.parse_args()

    try:
        raw_text = resolve_text(args)
    except ValueError as exc:
        print(str(exc))
        return 2

    text = normalize_text(raw_text)
    if not text.strip():
        print("Job description text is empty.")
        return 1

    company = args.company
    role = args.role
    if not company or not role:
        fit_map_path = Path(args.fit_map)
        if fit_map_path.exists():
            fit_map = load_fit_map(fit_map_path)
            company = company or fit_map.get("empresa", "")
            role = role or fit_map.get("cargo", "")

    company_slug = slugify(company or "empresa")
    role_slug = slugify(role or "cargo")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{company_slug}_{role_slug}.md"
    output_path.write_text(text, encoding="utf-8")

    print(f"Job description saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
