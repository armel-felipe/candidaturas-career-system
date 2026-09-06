from __future__ import annotations

import subprocess
import shlex
import re
from pathlib import Path
from typing import Any, Callable

from career.utils import ValidationFailure, read_json, sha256_file


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
        if kind == "onedrive_delivery":
            return self._execute_onedrive_delivery(payload)
        raise ValidationFailure(f"Unsupported approved action kind: {kind!r}")

    def _execute_onedrive_delivery(self, payload: dict[str, Any]) -> dict[str, Any]:
        application_id = str(payload.get("application_id") or "").strip()
        artifact_value = str(payload.get("artifact") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", application_id):
            raise ValidationFailure("OneDrive delivery requires a scoped application_id.")
        if not artifact_value:
            raise ValidationFailure("OneDrive delivery requires an artifact.")
        artifact = (self.root / artifact_value).resolve()
        try:
            artifact.relative_to((self.root / "outputs").resolve())
        except ValueError as exc:
            raise ValidationFailure("OneDrive artifact must remain inside outputs/.") from exc
        if not artifact.is_file():
            raise ValidationFailure("OneDrive artifact is missing.")
        expected_hash = str(payload.get("artifact_sha256") or "").strip()
        if expected_hash and sha256_file(artifact) != expected_hash:
            raise ValidationFailure("OneDrive artifact changed after approval.")
        command = [
            "npm",
            "run",
            "cv:deliver",
            "--",
            "--application-id",
            application_id,
            "--artifact",
            str(artifact.relative_to(self.root)),
        ]
        return self._run(command, "onedrive_delivery")

    def _execute_notion(self, payload: dict[str, Any]) -> dict[str, Any]:
        executed_result = payload.get("executed_result")
        executed_result = executed_result if isinstance(executed_result, dict) else {}
        resolved_page_id = (
            payload.get("resolved_page_id")
            or payload.get("page_id")
            or executed_result.get("page_id")
        )
        resolved_record_id = (
            payload.get("resolved_record_id")
            or payload.get("record_id")
            or executed_result.get("record_id")
        )
        action_status = str(payload.get("status") or "").strip().casefold()
        if (
            (
                action_status in {"written", "executed", "completed"}
                or payload.get("executed") is True
            )
            and (
                payload.get("real_write_executed") is True
                or str(resolved_page_id or "").strip()
            )
        ):
            result = {
                "status": "completed",
                "action": "notion",
                "already_executed": True,
                "resolved_page_id": resolved_page_id,
            }
            if resolved_record_id is not None:
                result["resolved_record_id"] = resolved_record_id
            return result
        command = payload.get("command")
        if isinstance(command, str):
            try:
                command = shlex.split(command)
            except ValueError as exc:
                raise ValidationFailure(
                    f"Notion command contains invalid shell quoting: {exc}"
                ) from exc
        elif not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            command_list = payload.get("command_list")
            if not isinstance(command_list, list) or not all(
                isinstance(item, str) and item.strip() for item in command_list
            ):
                raise ValidationFailure(
                    "Notion pending action must contain command or command_list."
                )
            try:
                command = shlex.split(command_list[-1])
            except ValueError as exc:
                raise ValidationFailure(
                    f"Notion command_list contains invalid shell quoting: {exc}"
                ) from exc
        if "--dry-run" in command:
            raise ValidationFailure(
                "Notion pending action command must be the approved write command, not dry-run."
            )
        allowed_prefixes = [
            ["npm", "run", "notion:create-current"],
            ["npm", "run", "notion:update-record-current"],
            ["npm", "run", "notion:update-page-current"],
            ["npm", "run", "notion:update-description-record"],
            ["./scripts/python.sh", "scripts/notion_sync.py"],
            ["scripts/python.sh", "scripts/notion_sync.py"],
            [str(self.root / "scripts" / "python.sh"), "scripts/notion_sync.py"],
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
