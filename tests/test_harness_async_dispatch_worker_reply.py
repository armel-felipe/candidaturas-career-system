import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hermes_harness_dispatch_worker as worker
from career.utils import write_json


def test_worker_delivers_nested_supervisor_block_reply(tmp_path, monkeypatch):
    dispatch_dir = tmp_path / "dispatch"
    dispatch_dir.mkdir()
    request = {
        "message_id": "m1",
        "message": "continue o cv",
        "runtime_context": {},
        "decision": "block",
        "dispatch_action": "awaiting_agent",
        "scope": {},
    }
    write_json(dispatch_dir / "request.json", request)
    write_json(dispatch_dir / "status.json", {"status": "awaiting_agent", "request_id": "m1"})
    write_json(
        dispatch_dir / "lease.json",
        {"owner": "worker", "pid": os.getpid(), "expires_at": "2099-01-01T00:00:00+00:00"},
    )
    monkeypatch.setattr(
        worker,
        "process_message",
        lambda *_args, **_kwargs: {
            "status": "blocked",
            "result": {
                "status": "blocked",
                "reply_text": "A candidatura está bloqueada.",
            },
        },
    )
    delivered = []
    monkeypatch.setattr(
        worker,
        "_deliver_reply",
        lambda reply_text: delivered.append(reply_text) or {"status": "sent"},
    )

    result = worker.run_worker(dispatch_dir)

    assert result["status"] == "blocked"
    assert delivered == ["A candidatura está bloqueada."]
