#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import bootstrap


ROOT = bootstrap()

from career.services import candidate_evidence  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild the compatible candidate CV facts view from candidate evidence."
    )
    parser.add_argument(
        "--evidence",
        default=str(candidate_evidence.CANDIDATE_EVIDENCE_PATH),
    )
    parser.add_argument(
        "--legacy",
        default=str(candidate_evidence.LEGACY_CV_FACTS_PATH),
    )
    parser.add_argument(
        "--output",
        default=str(candidate_evidence.LEGACY_CV_FACTS_PATH),
    )
    args = parser.parse_args()

    result = candidate_evidence.rebuild_candidate_facts(
        evidence_path=Path(args.evidence),
        legacy_facts_path=Path(args.legacy),
        output_path=Path(args.output),
    )
    print(f"Candidate CV facts rebuilt: {result['output']}")
    print(f"Evidence source: {result['evidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
