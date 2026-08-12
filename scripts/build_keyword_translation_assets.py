#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from keyword_translation_utils import (
    DEFAULT_TRANSLATION_CANDIDATES,
    DEFAULT_TRANSLATION_REGISTRY,
    build_translation_candidates,
    load_translation_registry,
    read_json,
    write_json,
)


DEFAULT_KEYWORD_REGISTRY = Path(".career-state/derived/keyword_ats_registry.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuilds translation candidate assets from ATS keyword history.")
    parser.add_argument("--keyword-registry", default=str(DEFAULT_KEYWORD_REGISTRY))
    parser.add_argument("--translation-registry", default=str(DEFAULT_TRANSLATION_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_TRANSLATION_CANDIDATES))
    args = parser.parse_args()

    keyword_registry = read_json(Path(args.keyword_registry), default={"applications": [], "canonical_keywords": {}})
    translation_registry = load_translation_registry(Path(args.translation_registry))
    payload = build_translation_candidates(keyword_registry, translation_registry)
    output_path = Path(args.output)
    write_json(output_path, payload)

    print(f"Translation candidates updated: {output_path}")
    print(f"Candidates: {payload['candidate_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
