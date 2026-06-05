#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path


MOJIBAKE_MARKERS = ("Ã", "Â", "â€“", "â€”", "â€™", "â€œ", "â€", "ï¿½")

MISSING_ACCENT_PATTERNS = {
    r"\bASSUNTO\b": "Use apenas no corpo de instrucoes, nao no email final.",
    r"\bOPERACOES\b": "OPERAÇÕES",
    r"\bOPERACAO\b": "OPERAÇÃO",
    r"\boperacoes\b": "operações",
    r"\boperacao\b": "operação",
    r"\bOperacoes\b": "Operações",
    r"\bOperacao\b": "Operação",
    r"\bOla\b": "Olá",
    r"\bola\b": "olá",
    r"\bexperiencia\b": "experiência",
    r"\bExperiencia\b": "Experiência",
    r"\barea\b": "área",
    r"\bArea\b": "Área",
    r"\bescalavel\b": "escalável",
    r"\bEscalavel\b": "Escalável",
    r"\bprevisivel\b": "previsível",
    r"\bPrevisivel\b": "Previsível",
    r"\bvoce\b": "você",
    r"\bVoce\b": "Você",
    r"\bcurriculo\b": "currículo",
    r"\bCurriculo\b": "Currículo",
    r"\babraco\b": "abraço",
    r"\bAbraco\b": "Abraço",
    r"\ba vaga\b": "à vaga",
    r"\ba area\b": "à área",
    r"\bareas\b": "áreas",
    r"\bAreas\b": "Áreas",
}

INTERNAL_MARKERS = (
    "FIT_MAP",
    "Area-Chave",
    "Experiencia-Chave",
    "Resultado-Chave",
    "Caracteristica-Chave",
    "Nome-Da-Empresa",
    "Titulo-Vaga",
    "TITULO-VAGA",
    "canonical",
    "canônico",
    "canonico",
)


def read_body(body: str | None, body_file: Path | None) -> str:
    if body is not None and body_file is not None:
        raise SystemExit("Use either --body or --body-file, not both.")
    if body_file is not None:
        if not body_file.exists() or not body_file.is_file():
            raise SystemExit(f"Body file not found: {body_file}")
        return body_file.read_text(encoding="utf-8")
    return body or ""


def collect_issues(subject: str, body: str) -> list[str]:
    text = f"{subject}\n{body}"
    issues = []

    for marker in MOJIBAKE_MARKERS:
        if marker in text:
            issues.append(f"Encoding/mojibake marker found: {marker}")

    for marker in INTERNAL_MARKERS:
        if marker in text:
            issues.append(f"Internal marker leaked into email text: {marker}")

    for pattern, suggestion in MISSING_ACCENT_PATTERNS.items():
        matches = sorted(set(re.findall(pattern, text)))
        for match in matches:
            issues.append(f"Possible Portuguese spelling/accent issue: '{match}' -> '{suggestion}'")

    if re.search(r"\bVAGA [A-Z0-9 ]*OPERACOES", subject):
        issues.append("Subject appears to be missing accents in all-caps title; prefer 'OPERAÇÕES'.")

    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review Gmail draft subject/body before creating a real draft.")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body")
    parser.add_argument("--body-file", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    body = read_body(args.body, args.body_file)
    issues = collect_issues(args.subject, body)
    if issues:
        print("Email text review failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Email text review passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
