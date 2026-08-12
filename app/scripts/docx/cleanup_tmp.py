#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


DEFAULT_TMP_DIR = Path("outputs/_tmp")


def should_delete(path: Path, cutoff_ts: float | None) -> bool:
    if path.name == ".gitkeep":
        return False
    if cutoff_ts is None:
        return True
    return path.stat().st_mtime <= cutoff_ts


def is_blocked_review_report(path: Path) -> bool:
    if path.name != "output_review_report.json":
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    approved = payload.get("approved_for_delivery", payload.get("approved"))
    return approved is not True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Limpa artefatos temporarios de outputs/_tmp sem depender do modelo que gerou o arquivo."
    )
    parser.add_argument("--tmp-dir", default=str(DEFAULT_TMP_DIR))
    parser.add_argument(
        "--older-than-minutes",
        type=int,
        help="Se informado, remove apenas arquivos mais antigos que esse limite.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria removido sem apagar arquivos.",
    )
    args = parser.parse_args()

    tmp_dir = Path(args.tmp_dir)
    if not tmp_dir.exists():
        print(f"Tmp directory not found: {tmp_dir}")
        return 0

    cutoff_ts = None
    if args.older_than_minutes is not None:
        cutoff_ts = time.time() - (args.older_than_minutes * 60)

    removed = 0
    kept = 0
    blocked: list[Path] = []
    for path in sorted(tmp_dir.iterdir()):
        if not path.is_file():
            kept += 1
            continue
        if not should_delete(path, cutoff_ts):
            kept += 1
            continue
        if is_blocked_review_report(path):
            blocked.append(path)
            kept += 1
            print(f"Kept blocked review report: {path}")
            continue
        if args.dry_run:
            print(f"Would remove: {path}")
        else:
            path.unlink(missing_ok=True)
            print(f"Removed: {path}")
        removed += 1

    mode = "dry-run" if args.dry_run else "cleanup"
    print(f"Tmp {mode} finished. Removed={removed} Kept={kept}")
    if blocked:
        print("Cleanup blocked because output_review_report.json is missing approval.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
