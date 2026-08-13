#!/usr/bin/env python3
"""Deterministic Phase C worker used only by the controlled pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one bounded cellular pilot task")
    parser.add_argument("--request", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = json.loads(args.request.read_text(encoding="utf-8"))
    required = ("cellular", "application_id", "run_id", "node_id", "attempt")
    if payload.get("cellular") is not True or any(not payload.get(key) for key in required[1:]):
        raise SystemExit("controlled worker requires a complete cellular request")
    if payload["node_id"] != "analyze_fit":
        raise SystemExit("controlled worker pilot only supports analyze_fit")
    write_allowlist = payload.get("write_allowlist")
    if not isinstance(write_allowlist, list) or not write_allowlist:
        raise SystemExit("controlled worker requires write_allowlist")
    manifest_path = Path(str(payload.get("manifest_path") or "")).resolve()
    if not manifest_path.is_file():
        raise SystemExit("controlled worker requires an existing manifest")
    cells_dir = next((parent for parent in manifest_path.parents if parent.name == "cells"), None)
    if cells_dir is None:
        raise SystemExit("controlled worker manifest is outside an application")
    application_dir = cells_dir.parent
    normalized_outputs = []
    for item in write_allowlist:
        candidate = Path(str(item)).resolve()
        try:
            candidate.relative_to(application_dir)
        except ValueError as exc:
            raise SystemExit("controlled worker output escapes application") from exc
        normalized_outputs.append(candidate)
    draft_candidates = [
        item for item in normalized_outputs if item.name == "fit_map.draft.json"
    ]
    if len(draft_candidates) != 1:
        raise SystemExit("controlled worker requires exactly one fit_map.draft.json output")
    draft_path = draft_candidates[0]
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(
        json.dumps(
            {
                "cargo": "Controlled Phase C Pilot",
                "application_id": payload["application_id"],
                "run_id": payload["run_id"],
                "attempt": int(payload["attempt"]),
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "completed", "output": str(draft_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
