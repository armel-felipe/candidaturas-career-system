import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hermes_harness_dispatch_worker as worker
from career.utils import write_json
from career.services.application_context import canonical_database
from career.services.harness_command_store import HarnessCommandStore


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


def test_worker_finishes_the_sqlite_command_not_just_the_file_mirror(tmp_path, monkeypatch):
    dispatch_dir = tmp_path / ".career-state" / "harness" / "dispatches" / "test"
    dispatch_dir.mkdir(parents=True)
    store = HarnessCommandStore(canonical_database(root=tmp_path))
    command = store.enqueue({
        "message_id": "m-sqlite", "message": "atualize o notion",
        "session_id": "session-1",
        "runtime_context": {"runtime": "hermes", "profile_id": "vagas_bot_01", "session_id": "session-1", "application_id": "app-1"},
    })
    write_json(dispatch_dir / "request.json", {
        "command_id": command["command_id"], "message_id": "m-sqlite",
        "message": "atualize o notion", "runtime_context": {"runtime": "hermes", "profile_id": "vagas_bot_01", "session_id": "session-1", "application_id": "app-1"},
        "scope": {"application_id": "app-1"},
    })
    write_json(dispatch_dir / "status.json", {"status": "awaiting_agent", "request_id": "m-sqlite"})
    write_json(dispatch_dir / "lease.json", {"owner": "worker", "pid": os.getpid(), "expires_at": "2099-01-01T00:00:00+00:00"})
    monkeypatch.setattr(worker, "process_message", lambda *_args, **_kwargs: {
        "status": "completed", "result": {"status": "completed", "display_text": "Notion atualizado."},
    })
    monkeypatch.setattr(worker, "_deliver_reply", lambda _text: {"status": "sent"})

    result = worker.run_worker(dispatch_dir)
    persisted = store.get(command["command_id"])

    assert result["status"] == "completed"
    assert persisted["status"] == "completed"
    assert persisted["reply_text"] == "Notion atualizado."


def test_worker_keeps_completed_notion_update_completed_when_reply_is_missing(
    tmp_path, monkeypatch
):
    dispatch_dir = tmp_path / "dispatch"
    dispatch_dir.mkdir()
    write_json(
        dispatch_dir / "request.json",
        {
            "message_id": "m-notion-completed",
            "message": "Pode atualizar o registro 624 no Notion.",
            "runtime_context": {},
            "decision": "block",
            "dispatch_action": "awaiting_agent",
            "scope": {},
        },
    )
    write_json(
        dispatch_dir / "status.json",
        {"status": "awaiting_agent", "request_id": "m-notion-completed"},
    )
    write_json(
        dispatch_dir / "lease.json",
        {"owner": "worker", "pid": os.getpid(), "expires_at": "2099-01-01T00:00:00+00:00"},
    )
    specialist_request = tmp_path / ".career-state" / "applications_v2" / "notion_624" / "request.json"
    write_json(
        specialist_request,
        {"application_id": "notion_624", "run_id": "run-624", "node_id": "notion-update"},
    )
    monkeypatch.setattr(
        worker,
        "process_message",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "result": {
                "status": "completed",
                "step": "notion-update",
                "request": {
                    "status": "ok",
                    "request_id": "notion-run-624",
                    "request_json": ".career-state/applications_v2/notion_624/request.json",
                },
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

    assert result["status"] == "completed"
    assert "Notion" in result["reply_text"]
    assert result["scope"]["application_id"] == "notion_624"
    assert delivered == [result["reply_text"]]


def test_worker_delivers_completed_cv_reply_when_specialist_has_no_display_text(
    tmp_path, monkeypatch
):
    dispatch_dir = tmp_path / "dispatch"
    dispatch_dir.mkdir()
    write_json(
        dispatch_dir / "request.json",
        {
            "message_id": "m-cv-completed",
            "message": "gere o CV",
            "runtime_context": {},
            "decision": "block",
            "dispatch_action": "awaiting_agent",
            "scope": {},
        },
    )
    write_json(
        dispatch_dir / "status.json",
        {"status": "awaiting_agent", "request_id": "m-cv-completed"},
    )
    write_json(
        dispatch_dir / "lease.json",
        {
            "owner": "worker",
            "pid": os.getpid(),
            "expires_at": "2099-01-01T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        worker,
        "process_message",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "result": {
                "status": "completed",
                "application_id": "app-cv",
                "requested_steps": ["cv"],
                "stages": [{"status": "completed", "step": "cv"}],
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

    assert result["status"] == "completed"
    assert "CV" in result["reply_text"]
    assert delivered == [result["reply_text"]]


def test_worker_exception_closes_claimed_sqlite_command(tmp_path, monkeypatch):
    dispatch_dir = tmp_path / ".career-state" / "harness" / "dispatches" / "failed"
    dispatch_dir.mkdir(parents=True)
    store = HarnessCommandStore(canonical_database(root=tmp_path))
    command = store.enqueue({
        "message_id": "m-failed", "message": "gere o CV",
        "session_id": "session-1",
        "runtime_context": {"runtime": "hermes", "profile_id": "vagas_bot_02", "session_id": "session-1", "application_id": "app-2"},
    })
    write_json(dispatch_dir / "request.json", {
        "command_id": command["command_id"], "message_id": "m-failed",
        "message": "gere o CV", "runtime_context": {"runtime": "hermes", "profile_id": "vagas_bot_02", "session_id": "session-1", "application_id": "app-2"},
    })
    write_json(dispatch_dir / "status.json", {"status": "awaiting_agent", "request_id": "m-failed"})
    write_json(dispatch_dir / "lease.json", {"owner": "worker", "pid": os.getpid(), "expires_at": "2099-01-01T00:00:00+00:00"})
    monkeypatch.setattr(worker, "process_message", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(worker, "_deliver_reply", lambda _text: {"status": "sent"})

    result = worker.run_worker(dispatch_dir)

    assert result["status"] == "blocked"
    assert store.get(command["command_id"])["status"] == "blocked"
