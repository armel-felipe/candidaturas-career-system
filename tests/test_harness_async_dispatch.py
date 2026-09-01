import json
import io
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hermes_harness_context_hook as hook
import hermes_harness_dispatch_worker as worker
import telegram_harness_adapter as adapter
from career.utils import write_json


class _FakeWorkerProcess:
    _next_pid = 41000

    def __init__(self, command, *, env, start_new_session):
        type(self)._next_pid += 1
        self.pid = type(self)._next_pid
        self.command = command
        self.env = env
        self.start_new_session = start_new_session


def _payload(message_id="m1", **overrides):
    payload = {
        "message_id": message_id,
        "message": "analise a vaga",
        "session_id": "session-1",
        "turn_id": "turn-1",
        "runtime_context": {
            "runtime": "hermes",
            "profile_id": "vagas_bot_01",
            "session_id": "session-1",
            "turn_id": "turn-1",
            "application_id": "app-1",
            "run_id": "run-1",
        },
    }
    payload.update(overrides)
    return payload


def test_pre_llm_dispatch_returns_without_waiting_for_pipeline(tmp_path, monkeypatch):
    started = []

    def slow_worker(command, **kwargs):
        started.append((command, kwargs))
        return _FakeWorkerProcess(command, **kwargs)

    monkeypatch.setattr(adapter.subprocess, "Popen", slow_worker)
    began = time.monotonic()
    result = adapter.dispatch_harness_job(_payload(), root=tmp_path)
    elapsed = time.monotonic() - began

    assert elapsed < 5
    assert result["status"] == "awaiting_agent"
    assert result["message_id"] == "m1"
    assert result["request_id"] == "m1"
    assert result["worker_started"] is True
    assert result["decision"] == "block"
    assert result["scope"]["application_id"] == "app-1"
    assert result["next_state"] == "awaiting_agent"
    assert started[0][1]["start_new_session"] is True
    assert started[0][1]["env"]["CAREER_HARNESS_SUBAGENT"] == "1"

    envelope = tmp_path / ".career-state" / "harness" / "dispatches" / "m1"
    assert (envelope / "request.json").is_file()
    assert (envelope / "status.json").is_file()
    assert (envelope / "lease.json").is_file()
    request = json.loads((envelope / "request.json").read_text(encoding="utf-8"))
    assert request["runtime_context"]["application_id"] == "app-1"
    assert request["runtime_context"]["run_id"] == "run-1"
    assert request["decision"] == "block"
    assert request["scope"]["application_id"] == "app-1"


def test_duplicate_message_id_reuses_one_worker(tmp_path, monkeypatch):
    started = []

    def fake_popen(command, **kwargs):
        started.append(command)
        return _FakeWorkerProcess(command, **kwargs)

    monkeypatch.setattr(adapter.subprocess, "Popen", fake_popen)
    first = adapter.dispatch_harness_job(_payload(), root=tmp_path)
    second = adapter.dispatch_harness_job(_payload(), root=tmp_path)

    assert len(started) == 1
    assert first["request_id"] == second["request_id"] == "m1"
    assert second["status"] == "awaiting_agent"
    assert second["worker_started"] is False
    assert second["deduplicated"] is True


def test_dispatch_stale_lease_is_structured_blocked_without_new_worker(tmp_path, monkeypatch):
    def fail_popen(*_args, **_kwargs):
        raise AssertionError("stale dispatch must not start another worker")

    monkeypatch.setattr(adapter.subprocess, "Popen", fail_popen)
    dispatch_dir = tmp_path / ".career-state" / "harness" / "dispatches" / "m1"
    dispatch_dir.mkdir(parents=True)
    write_json(dispatch_dir / "request.json", _payload())
    write_json(dispatch_dir / "status.json", {"status": "running", "request_id": "m1"})
    write_json(
        dispatch_dir / "lease.json",
        {
            "owner": "dead-worker",
            "pid": 999999,
            "acquired_at": "2000-01-01T00:00:00+00:00",
            "expires_at": "2000-01-01T00:00:01+00:00",
        },
    )

    result = adapter.dispatch_harness_job(_payload(), root=tmp_path)

    assert result["status"] == "blocked"
    assert result["blocker_reason"] in {"dispatch_lease_expired", "dispatch_worker_dead"}
    assert json.loads((dispatch_dir / "status.json").read_text())["status"] == "blocked"


def test_worker_executes_outside_hook_and_persists_completed(tmp_path, monkeypatch):
    dispatch_dir = tmp_path / "dispatch"
    dispatch_dir.mkdir()
    write_json(dispatch_dir / "request.json", _payload())
    write_json(
        dispatch_dir / "status.json",
        {"status": "awaiting_agent", "request_id": "m1", "message_id": "m1"},
    )
    write_json(
        dispatch_dir / "lease.json",
        {"owner": "worker", "pid": os.getpid(), "expires_at": "2099-01-01T00:00:00+00:00"},
    )
    calls = []

    def fake_process(message, **kwargs):
        calls.append((message, kwargs))
        return {"status": "completed", "result": {"status": "completed"}}

    monkeypatch.setattr(worker, "process_message", fake_process)
    result = worker.run_worker(dispatch_dir)

    assert result["status"] == "completed"
    assert calls == [("analise a vaga", {
        "message_id": "m1",
        "execute": True,
        "runtime_context": _payload()["runtime_context"],
        "root": Path(tmp_path),
    })]
    persisted = json.loads((dispatch_dir / "result.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "completed"
    assert json.loads((dispatch_dir / "status.json").read_text())["status"] == "completed"
    assert not (dispatch_dir / "lease.json").exists()


def test_worker_rejects_missing_lease_before_pipeline(tmp_path, monkeypatch):
    dispatch_dir = tmp_path / "dispatch"
    dispatch_dir.mkdir()
    write_json(dispatch_dir / "request.json", _payload())
    write_json(dispatch_dir / "status.json", {"status": "awaiting_agent", "request_id": "m1"})
    monkeypatch.setattr(worker, "process_message", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("worker must validate lease before executing")
    ))

    result = worker.run_worker(dispatch_dir)

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "dispatch_lease_missing"


def test_worker_reentrancy_is_blocked(tmp_path):
    dispatch_dir = tmp_path / "dispatch"
    dispatch_dir.mkdir()
    write_json(dispatch_dir / "request.json", _payload())
    write_json(dispatch_dir / "status.json", {"status": "running", "request_id": "m1"})
    write_json(dispatch_dir / "lease.json", {"owner": "other", "pid": os.getpid()})

    result = worker.run_worker(dispatch_dir)

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "dispatch_reentrancy"


def test_context_hook_dispatches_without_executing_pipeline(monkeypatch, capsys, tmp_path):
    captured = {}

    def fake_dispatch(payload):
        captured["payload"] = payload
        return {
            "status": "awaiting_agent",
            "message_id": payload["message_id"],
            "request_id": payload["message_id"],
            "worker_started": True,
            "application_id": "app-1",
            "run_id": "run-1",
        }

    def forbidden_process(*_args, **_kwargs):
        raise AssertionError("pre-LLM hook must not execute the pipeline")

    monkeypatch.setattr(hook, "ROOT", tmp_path)
    monkeypatch.setattr(hook, "should_intercept", lambda _message: True)
    monkeypatch.setattr(hook, "dispatch_harness_job", fake_dispatch, raising=False)
    monkeypatch.setattr(hook, "process_message", forbidden_process, raising=False)
    monkeypatch.setattr(
        hook,
        "application_context_service",
        type("Context", (), {"profile_id_from_env": staticmethod(lambda: "vagas_bot_01")}),
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({
            "session_id": "session-1",
            "extra": {"user_message": "analise a vaga", "turn_id": "turn-1"},
        })),
    )

    assert hook.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["action"] == "block"
    assert output["decision"] == "block"
    assert "awaiting_agent" in output["context"]
    assert captured["payload"]["runtime_context"]["application_id"] is None
    assert captured["payload"]["session_id"] == "session-1"
