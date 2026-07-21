from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from career.paths import ROOT


class CanonicalDeliveryCellAdapter:
    """Lazy adapter for the canonical rclone delivery command.

    Construction never reads configuration or invokes rclone.  The external
    process is reached only from ``deliver_cell`` after the cell lock and
    receipt preflight have succeeded.
    """

    def __init__(self, *, env: Mapping[str, str] | None = None) -> None:
        self._env = env

    def preflight(self) -> tuple[str, str]:
        env = self._env if self._env is not None else os.environ
        remote = str(env.get("RCLONE_ONEDRIVE_REMOTE") or "").strip()
        folder = str(env.get("RCLONE_ONEDRIVE_DELIVERY_DIR") or "").strip()
        if not remote or not folder:
            raise RuntimeError("delivery preflight requires RCLONE_ONEDRIVE_REMOTE and RCLONE_ONEDRIVE_DELIVERY_DIR")
        if folder != "01_armel/Curriculos/personalizados" and not folder.startswith("01_armel/Curriculos/personalizados/"):
            raise RuntimeError("delivery preflight rejected a destination outside the canonical folder")
        if shutil.which("rclone") is None:
            raise RuntimeError("delivery preflight requires configured rclone")
        return remote, folder

    def deliver_cell(self, request: Mapping[str, Any], artifact: bytes) -> dict[str, str]:
        remote, folder = self.preflight()
        artifact_path = Path(str(request.get("artifact_path") or ""))
        if not artifact_path.is_file() or artifact_path.read_bytes() != artifact:
            raise RuntimeError("delivery preflight could not verify the exact cellular DOCX")
        command = [
            sys.executable,
            str(ROOT / "scripts" / "deliver_artifact.py"),
            "--file", str(artifact_path), "--remote", remote, "--folder", folder,
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"canonical delivery failed: {result.stderr[-500:] or result.stdout[-500:]}")
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        try:
            payload = json.loads("\n".join(lines))
        except json.JSONDecodeError as exc:
            raise RuntimeError("canonical delivery returned invalid JSON") from exc
        if payload.get("status") != "delivered":
            raise RuntimeError(f"canonical delivery did not deliver: {payload.get('status')}")
        return {
            "delivery_id": str(payload.get("destination") or ""),
            "url": str(payload.get("destination") or ""),
        }
