from __future__ import annotations

from pathlib import Path

from career.services import applications_v2
from career.services.harness_supervisor import HarnessSupervisor


class FakeBridge:
    def __init__(self, *, result):
        self.result = result
        self.calls = []

    def reset_for_application(self, *args):
        self.calls.append(args)
        return dict(self.result)

    def observe_current_session(self, *args):
        return {"status": "ok", "current_session_id": "clean-1"}


def _config(mode="live"):
    return {
        "hermes_session_boundaries": {
            "enabled": True,
            "mode": mode,
            "profile_id": "vagas_bot_01",
            "session_key": "telegram:vagas_bot_01:chat-1",
            "endpoints": {"vagas_bot_01": "http://bot01.test:8642/api/gateway/session-boundary"},
        }
    }


def _paths(tmp_path: Path):
    return applications_v2._app_paths(tmp_path / "app-1")


def test_terminal_done_can_request_boundary_and_preserves_pipeline_result(monkeypatch, tmp_path):
    fake = FakeBridge(result={"status": "pending_verification", "idempotency_key": "run-1:reset"})
    monkeypatch.setattr(applications_v2, "HermesSessionBridge", lambda **kwargs: fake)

    state = {"stage": "done", "service_status": "done", "score": 8.0}
    result = applications_v2._maybe_apply_hermes_session_boundary(
        {"record_id": "app-1"},
        _paths(tmp_path),
        state,
        _config(),
        run_id="run-1",
        pipeline_dry_run=False,
    )

    assert result["status"] == "pending_verification"
    assert state["stage"] == "done"
    assert fake.calls == [
        (
            "app-1",
            "vagas_bot_01",
            "telegram:vagas_bot_01:chat-1",
            "run-1",
            "pipeline:done",
        )
    ]


def test_running_stage_never_requests_boundary(monkeypatch, tmp_path):
    constructed = []
    monkeypatch.setattr(
        applications_v2,
        "HermesSessionBridge",
        lambda **kwargs: constructed.append(kwargs),
    )

    state = {"stage": "generate_running", "service_status": "running"}
    result = applications_v2._maybe_apply_hermes_session_boundary(
        {"record_id": "app-1"},
        _paths(tmp_path),
        state,
        _config(),
        run_id="run-1",
        pipeline_dry_run=False,
    )

    assert result["status"] == "skipped_running_stage"
    assert constructed == []


def test_disabled_by_default_does_not_construct_or_call_bridge(monkeypatch, tmp_path):
    constructed = []
    monkeypatch.setattr(
        applications_v2,
        "HermesSessionBridge",
        lambda **kwargs: constructed.append(kwargs),
    )

    state = {"stage": "done"}
    result = applications_v2._maybe_apply_hermes_session_boundary(
        {"record_id": "app-1"},
        _paths(tmp_path),
        state,
        {"hermes_session_boundaries": {"enabled": False}},
        run_id="run-1",
        pipeline_dry_run=False,
    )

    assert result["status"] == "disabled"
    assert constructed == []


def test_gateway_failure_is_recorded_as_pending_without_changing_stage(monkeypatch, tmp_path):
    fake = FakeBridge(result={"status": "gateway_conflict", "error": "CAS conflict"})
    monkeypatch.setattr(applications_v2, "HermesSessionBridge", lambda **kwargs: fake)

    state = {"stage": "low_fit", "service_status": "completed", "score": 4.0}
    result = applications_v2._maybe_apply_hermes_session_boundary(
        {"record_id": "app-1"},
        _paths(tmp_path),
        state,
        _config(),
        run_id="run-1",
        pipeline_dry_run=False,
    )

    assert result["status"] == "gateway_conflict"
    assert state["stage"] == "low_fit"


def test_harness_keeps_new_as_generic_message_and_not_pipeline_control():
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)

    decision = supervisor.classify("/new")

    assert decision.workflow == "generic_assistant"
    assert decision.reason != "gateway_session_boundary"
