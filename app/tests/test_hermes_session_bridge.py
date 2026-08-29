from __future__ import annotations

import json
from pathlib import Path

import pytest

from career.services.hermes_session_bridge import (
    HermesSessionBridge,
    HermesSessionBridgeError,
)


class FakeTransport:
    def __init__(self, responses=None, errors=None):
        self.responses = list(responses or [])
        self.errors = list(errors or [])
        self.calls: list[dict] = []

    def __call__(self, method, url, headers, payload, timeout):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "payload": payload,
                "timeout": timeout,
            }
        )
        if self.errors:
            error = self.errors.pop(0)
            raise error
        if not self.responses:
            raise AssertionError("fake transport has no response")
        return self.responses.pop(0)


def _bridge(tmp_path: Path, transport: FakeTransport, *, mode: str = "live"):
    handoff_path = tmp_path / "applications_v2" / "app-1" / "hermes_handoff.json"
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text('{"application_id":"app-1","stage":"done"}', encoding="utf-8")
    return HermesSessionBridge(
        root=tmp_path,
        mode=mode,
        endpoints={
            "vagas_bot_01": "http://bot01.test:8642/api/gateway/session-boundary",
            "vagas_bot_02": "http://bot02.test:8642/api/gateway/session-boundary",
        },
        api_keys={"vagas_bot_01": "secret-01", "vagas_bot_02": "secret-02"},
        transport=transport,
        binding_loader=lambda profile_id: {
            "profile_id": profile_id,
            "application_id": "app-1",
            "status": "active",
        },
    )


def _status(session_id: str = "old"):
    return {
        "_http_status": 200,
        "status": "ok",
        "session_key": "telegram:vagas_bot_01:chat-1",
        "current_session_id": session_id,
    }


def _reset_result(status: str = "reset"):
    return {
        "_http_status": 200 if status in {"reset", "already_applied"} else 409,
        "status": status,
        "operation": "reset",
        "session_key": "telegram:vagas_bot_01:chat-1",
        "old_session_id": "old",
        "new_session_id": "new" if status == "reset" else None,
        "target_session_id": None,
        "reason": "pipeline:done",
        "idempotency_key": "run-1:reset",
    }


def test_reset_success_reads_binding_and_records_ledger(tmp_path):
    transport = FakeTransport(responses=[_status(), _reset_result()])
    bridge = _bridge(tmp_path, transport)

    result = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )

    assert result["status"] == "reset"
    assert result["old_session_id"] == "old"
    assert result["new_session_id"] == "new"
    assert [call["method"] for call in transport.calls] == ["GET", "POST"]
    assert transport.calls[1]["payload"]["expected_session_id"] == "old"
    assert transport.calls[1]["payload"]["idempotency_key"] == "run-1:reset"
    assert transport.calls[1]["headers"]["Authorization"] == "Bearer secret-01"
    records = bridge.ledger_for_application("app-1").history()
    assert records[-1]["status"] == "reset"
    assert records[-1]["new_session_id"] == "new"


def test_already_applied_is_idempotent_and_recorded(tmp_path):
    transport = FakeTransport(responses=[_status("new"), {**_reset_result("already_applied"), "old_session_id": "new", "new_session_id": "new"}])
    bridge = _bridge(tmp_path, transport)

    result = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )

    assert result["status"] == "already_applied"
    assert bridge.ledger_for_application("app-1").history()[-1]["status"] == "already_applied"


def test_gateway_conflict_does_not_mutate_ledger(tmp_path):
    transport = FakeTransport(responses=[_status(), _reset_result("conflict")])
    bridge = _bridge(tmp_path, transport)

    result = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )

    assert result["status"] == "gateway_conflict"
    assert bridge.ledger_for_application("app-1").history() == []


def test_ambiguous_mutation_timeout_retries_same_idempotency_and_marks_pending(tmp_path):
    class MutationTimeoutTransport(FakeTransport):
        def __call__(self, method, url, headers, payload, timeout):
            self.calls.append(
                {
                    "method": method,
                    "url": url,
                    "headers": dict(headers),
                    "payload": payload,
                    "timeout": timeout,
                }
            )
            if method == "GET":
                return _status()
            raise TimeoutError("mutation timed out")

    transport = MutationTimeoutTransport()
    bridge = _bridge(tmp_path, transport)

    result = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )

    assert result["status"] == "pending_verification"
    post_calls = [call for call in transport.calls if call["method"] == "POST"]
    assert len(post_calls) == 2
    assert post_calls[0]["payload"]["idempotency_key"] == post_calls[1]["payload"]["idempotency_key"]
    record = bridge.ledger_for_application("app-1").history()[-1]
    assert record["status"] == "pending_verification"
    assert record["new_session_id"] == "old"


def test_status_timeout_retries_once_then_returns_pending_without_mutation(tmp_path):
    transport = FakeTransport(errors=[TimeoutError("status timeout"), TimeoutError("status timeout")])
    bridge = _bridge(tmp_path, transport)

    result = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )

    assert result["status"] == "pending_verification"
    assert [call["method"] for call in transport.calls] == ["GET", "GET"]
    assert bridge.ledger_for_application("app-1").history() == []


def test_malformed_status_response_is_pending_and_does_not_mutate(tmp_path):
    transport = FakeTransport(responses=[["not", "json"]])
    bridge = _bridge(tmp_path, transport)

    result = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )

    assert result["status"] == "pending_verification"
    assert len(transport.calls) == 1


def test_unknown_profile_is_rejected_before_transport(tmp_path):
    transport = FakeTransport()
    bridge = _bridge(tmp_path, transport)

    with pytest.raises(HermesSessionBridgeError, match="unsupported profile_id"):
        bridge.reset_for_application(
            "app-1", "other-bot", "telegram:other-bot:chat-1", "run-1", "pipeline:done"
        )

    assert transport.calls == []


def test_dry_run_observes_current_session_without_post(tmp_path):
    transport = FakeTransport(responses=[_status()])
    bridge = _bridge(tmp_path, transport, mode="dry_run")

    result = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )

    assert result["status"] == "dry_run"
    assert result["old_session_id"] == "old"
    assert result["new_session_id"] == "old"
    assert [call["method"] for call in transport.calls] == ["GET"]
    assert bridge.ledger_for_application("app-1").history()[-1]["status"] == "dry_run"


def test_resume_can_use_the_persisted_binding_to_return_to_a_prior_session(tmp_path):
    transport = FakeTransport(
        responses=[
            _status("new"),
            {
                "_http_status": 200,
                "status": "resumed",
                "operation": "resume",
                "old_session_id": "new",
                "new_session_id": "old",
                "target_session_id": "old",
            },
        ]
    )
    bridge = _bridge(tmp_path, transport)
    bridge.ledger_for_application("app-1").record_reset(
        profile_id="vagas_bot_01",
        session_key="telegram:vagas_bot_01:chat-1",
        old_session_id="older",
        new_session_id="new",
        run_id="run-0",
        reason="pipeline:done",
        idempotency_key="run-0:reset",
    )
    handoff_path = tmp_path / "applications_v2" / "app-1" / "hermes_handoff.json"
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(json.dumps({"stage": "done"}), encoding="utf-8")

    result = bridge.resume_for_application("app-1", "old", "run-2", "manual_correction")

    assert result["status"] == "resumed"
    assert result["new_session_id"] == "old"
    assert result["application_id"] == "app-1"
    assert result["stage"] == "done"
    assert result["handoff_path"] == str(handoff_path)
    assert transport.calls[1]["payload"]["target_session_id"] == "old"


def test_endpoint_allowlist_has_no_arbitrary_profile_resolution(tmp_path):
    bridge = _bridge(tmp_path, FakeTransport())

    assert bridge.endpoint_for_profile("vagas_bot_01").startswith("http://bot01.test")
    with pytest.raises(HermesSessionBridgeError, match="unsupported profile_id"):
        bridge.endpoint_for_profile("vagas_bot_03")


def test_observe_current_session_is_read_only_and_does_not_create_ledger_record(tmp_path):
    transport = FakeTransport(responses=[_status("clean-1")])
    bridge = _bridge(tmp_path, transport)

    result = bridge.observe_current_session(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1"
    )

    assert result["status"] == "ok"
    assert result["current_session_id"] == "clean-1"
    assert [call["method"] for call in transport.calls] == ["GET"]
    assert bridge.ledger_for_application("app-1").history() == []


def test_bridge_supports_clean_to_old_to_clean_correction_cycle(tmp_path):
    transport = FakeTransport(
        responses=[
            _status("clean-1"),
            {
                "_http_status": 200,
                "status": "reset",
                "operation": "reset",
                "old_session_id": "clean-1",
                "new_session_id": "clean-2",
            },
            _status("clean-2"),
            {
                "_http_status": 200,
                "status": "resumed",
                "operation": "resume",
                "old_session_id": "clean-2",
                "new_session_id": "old-1",
                "target_session_id": "old-1",
            },
            _status("old-1"),
            {
                "_http_status": 200,
                "status": "reset",
                "operation": "reset",
                "old_session_id": "old-1",
                "new_session_id": "clean-3",
            },
        ]
    )
    bridge = _bridge(tmp_path, transport)

    first = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )
    resumed = bridge.resume_for_application("app-1", "old-1", "run-2", "manual_correction")
    second = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-3", "pipeline:done"
    )

    assert first["new_session_id"] == "clean-2"
    assert resumed["new_session_id"] == "old-1"
    assert second["new_session_id"] == "clean-3"
    assert bridge.ledger_for_application("app-1").current_binding()["current_session_id"] == "clean-3"
