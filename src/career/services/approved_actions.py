from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

from career.utils import ValidationFailure, read_json


class ApprovedActionExecutor:
    def __init__(
        self,
        root: Path,
        run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ):
        self.root = root
        self.run_command = run_command

    def execute(self, action_path: Path) -> dict[str, Any]:
        payload = read_json(action_path)
        kind = str(payload.get("kind") or "")
        if kind == "notion":
            return self._execute_notion(payload)
        if kind == "gmail_draft":
            return self._execute_gmail_draft(payload)
        raise ValidationFailure(f"Unsupported approved action kind: {kind!r}")

    def _execute_notion(self, payload: dict[str, Any]) -> dict[str, Any]:
        command = payload.get("command")
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise ValidationFailure("Notion pending action must contain a string command list.")
        allowed_prefixes = [
            ["npm", "run", "notion:create-current"],
            ["npm", "run", "notion:update-record-current"],
            ["npm", "run", "notion:update-page-current"],
            ["npm", "run", "notion:update-description-record"],
        ]
        if not any(command[: len(prefix)] == prefix for prefix in allowed_prefixes):
            raise ValidationFailure(f"Notion command is not allowed: {command}")
        return self._run(command, "notion")

    def _execute_gmail_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        recipient = str(payload.get("to") or "").strip()
        subject = str(payload.get("subject") or "").strip()
        body = str(payload.get("body") or "").strip()
        attachments = payload.get("attachments") or []
        if not recipient or not subject or not body:
            raise ValidationFailure("Gmail draft requires to, subject and body.")
        if not isinstance(attachments, list):
            raise ValidationFailure("Gmail draft attachments must be a list.")
        review = [
            str(self.root / "scripts" / "python.sh"),
            "scripts/review_email_text.py",
            "--subject",
            subject,
            "--body",
            body,
        ]
        review_result = self._run(review, "gmail_review")
        command = [
            str(self.root / "scripts" / "python.sh"),
            "scripts/create_gmail_draft.py",
            "--to",
            recipient,
            "--subject",
            subject,
            "--body",
            body,
        ]
        for item in attachments:
            attachment = (self.root / str(item)).resolve()
            if not attachment.exists():
                raise ValidationFailure(f"Gmail attachment does not exist: {item}")
            command.extend(["--attach", str(attachment)])
        draft_result = self._run(command, "gmail_draft")
        return {"status": "completed", "review": review_result, "draft": draft_result}

    def _run(self, command: list[str], action: str) -> dict[str, Any]:
        result = self.run_command(
            command,
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise ValidationFailure(
                f"Approved action {action} failed ({result.returncode}): "
                f"{(result.stderr or result.stdout)[-2000:]}"
            )
        return {
            "status": "completed",
            "action": action,
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
