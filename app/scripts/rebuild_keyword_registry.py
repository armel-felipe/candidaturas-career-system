#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import bootstrap


ROOT = bootstrap()

from career.services import memory as memory_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild keyword ATS registry from the consolidated Notion cache.")
    parser.add_argument("--cache-path", default=str(ROOT / "inbox" / "notion" / "applications_cache.json"))
    parser.add_argument("--output", default=str(ROOT / ".career-state" / "derived" / "keyword_ats_registry.json"))
    args = parser.parse_args()

    result = memory_service.rebuild_keyword_registry_from_cache(
        cache_path=Path(args.cache_path),
        output_path=Path(args.output),
    )
    print(f"Keyword registry rebuilt: {result['output_path']}")
    print(f"Applications exported: {result['applications_exported']}")
    print(f"Canonical keywords: {result['canonical_keywords']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
