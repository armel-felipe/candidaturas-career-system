from __future__ import annotations

import json

from career.services.approved_actions import ApprovedActionExecutor


def test_written_notion_action_is_idempotently_completed(tmp_path):
    action_path = tmp_path / "notion.json"
    action_path.write_text(
        json.dumps(
            {
                "kind": "notion",
                "status": "written",
                "real_write_executed": True,
                "resolved_page_id": "page-624",
                "command_list": [
                    "./scripts/python.sh scripts/notion_sync.py update-from-fit-map-record 624"
                ],
            }
        ),
        encoding="utf-8",
    )
    calls = []

    result = ApprovedActionExecutor(
        tmp_path,
        run_command=lambda command, **kwargs: calls.append(command),
    ).execute(action_path)

    assert result["status"] == "completed"
    assert result["already_executed"] is True
    assert result["resolved_page_id"] == "page-624"
    assert calls == []


def test_notion_command_list_accepts_canonical_unexecuted_command(tmp_path):
    action_path = tmp_path / "notion.json"
    action_path.write_text(
        json.dumps(
            {
                "kind": "notion",
                "status": "pending",
                "command_list": [
                    "./scripts/python.sh scripts/notion_sync.py update-from-fit-map-record 624 --dry-run",
                    "./scripts/python.sh scripts/notion_sync.py update-from-fit-map-record 624",
                ],
            }
        ),
        encoding="utf-8",
    )
    calls = []

    class Result:
        returncode = 0
        stdout = "written"
        stderr = ""

    result = ApprovedActionExecutor(
        tmp_path,
        run_command=lambda command, **kwargs: calls.append(command) or Result(),
    ).execute(action_path)

    assert result["status"] == "completed"
    assert calls == [
        [
            "./scripts/python.sh",
            "scripts/notion_sync.py",
            "update-from-fit-map-record",
            "624",
        ]
    ]
