#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.services import fit_map as fit_map_service


TOOL_RE = re.compile(r"^\*\*Tool:", re.MULTILINE)
ASSISTANT_RE = re.compile(r"^## Assistant\b", re.MULTILINE)
NOTE_RE = re.compile(r"\bNota final\b|\bNota de Ader[êe]ncia\b|Subtotal:", re.IGNORECASE)
PROMISED_WRITE_RE = re.compile(
    r"vou agora escrever|vou preencher|write the fit_map|write the draft|escrever o fit_map|preencher o draft",
    re.IGNORECASE,
)
WRITE_TOOL_RE = re.compile(r"\*\*Tool:\s*(write|edit|apply_patch)\b", re.IGNORECASE)
TEMPLATE_RE = re.compile(r"npm run fit-map:template|fit-map template", re.IGNORECASE)
VALIDATE_DRAFT_RE = re.compile(r"validate:fit-map:draft|fit-map validate-draft", re.IGNORECASE)
BUILD_RE = re.compile(r"fit-map:build|fit-map build", re.IGNORECASE)
SCORE_RE = re.compile(r"fit-map:score|fit-map score", re.IGNORECASE)
REGISTER_RE = re.compile(r"register_keywords\.py|keywords:register", re.IGNORECASE)


def _assistant_blocks(text: str) -> list[str]:
    starts = [match.start() for match in ASSISTANT_RE.finditer(text)]
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        blocks.append(text[start:end])
    return blocks


def _long_blocks_without_tools(text: str, min_chars: int) -> list[dict]:
    result = []
    for index, block in enumerate(_assistant_blocks(text), start=1):
        if len(block) >= min_chars and not TOOL_RE.search(block):
            result.append({"assistant_block": index, "chars": len(block)})
    return result


def diagnose(
    session_path: Path,
    *,
    min_chars_without_tool: int = 8000,
    draft_path: Path | None = None,
    fit_map_path: Path | None = None,
    job_description_path: Path | None = None,
) -> dict:
    text = session_path.read_text(encoding="utf-8", errors="replace")
    status = fit_map_service.status(
        draft_path=draft_path or fit_map_service.CAREER_STATE / "fit_map.draft.json",
        fit_map_path=fit_map_path or fit_map_service.CAREER_STATE / "fit_map.json",
        job_description_path=job_description_path,
    )
    long_blocks = _long_blocks_without_tools(text, min_chars_without_tool)
    command_patterns = [
        ("fit-map:template", TEMPLATE_RE),
        ("validate:fit-map:draft", VALIDATE_DRAFT_RE),
        ("fit-map:build", BUILD_RE),
        ("fit-map:score", SCORE_RE),
        ("register_keywords", REGISTER_RE),
    ]
    command_positions = {
        name: max((match.start() for match in pattern.finditer(text)), default=-1)
        for name, pattern in command_patterns
    }
    template_seen = command_positions["fit-map:template"] >= 0
    validate_draft_seen = command_positions["validate:fit-map:draft"] >= 0
    promised_write = bool(PROMISED_WRITE_RE.search(text))
    write_tool_seen = bool(WRITE_TOOL_RE.search(text))
    note_mentions = len(NOTE_RE.findall(text))

    draft_placeholder = status["draft"]["placeholder_count"] > 0
    fit_map_stale = status["fit_map"]["exists"] and not status["fit_map"]["matches_active_job"]

    last_completed_step = max(command_positions.items(), key=lambda item: item[1])[0]
    if command_positions[last_completed_step] < 0:
        last_completed_step = "unknown"

    stalled = bool(
        long_blocks
        or (promised_write and not write_tool_seen and draft_placeholder)
        or (template_seen and not validate_draft_seen and draft_placeholder)
        or (note_mentions >= 3 and draft_placeholder)
    )

    return {
        "session": str(session_path),
        "stalled": stalled,
        "signals": {
            "long_assistant_blocks_without_tools": long_blocks,
            "promised_write_without_write_tool": promised_write and not write_tool_seen,
            "note_recalculation_mentions": note_mentions,
            "template_seen_without_validate_draft": template_seen and not validate_draft_seen,
            "draft_placeholder": draft_placeholder,
            "fit_map_stale": fit_map_stale,
        },
        "last_completed_step": last_completed_step,
        "next_required_step": status["next_required_step"],
        "fit_map_status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostica travamentos operacionais em logs de sessão.")
    parser.add_argument("session", help="Arquivo session-*.md exportado pelo runtime.")
    parser.add_argument("--min-chars-without-tool", type=int, default=8000)
    parser.add_argument("--draft")
    parser.add_argument("--fit-map")
    parser.add_argument("--job-description")
    args = parser.parse_args()

    payload = diagnose(
        Path(args.session),
        min_chars_without_tool=args.min_chars_without_tool,
        draft_path=Path(args.draft) if args.draft else None,
        fit_map_path=Path(args.fit_map) if args.fit_map else None,
        job_description_path=Path(args.job_description) if args.job_description else None,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if payload["stalled"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
