from __future__ import annotations

import json
from pathlib import Path

import pytest

from career.services import applications_v2
from career.services.hermes_session_bridge import HermesSessionBridge, HermesSessionBridgeError
from career.services.hermes_session_ledger import HermesSessionLedger


class FakeTransport:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def __call__(self, method, url, headers, payload, timeout):
        self.calls.append((method, url, dict(headers), payload))
        if not self.responses:
            raise AssertionError("unexpected transport call")
        return self.responses.pop(0)


def _status(session_id="clean-1"):
    return {
        "_http_status": 200,
        "status": "ok",
        "current_session_id": session_id,
    }


def _reset():
    return {
        "_http_status": 200,
        "status": "reset",
        "operation": "reset",
        "old_session_id": "clean-1",
        "new_session_id": "clean-2",
    }


def _secure_bridge(tmp_path: Path, transport: FakeTransport):
    app_dir = tmp_path / "applications_v2" / "app-1"
    app_dir.mkdir(parents=True)
    (app_dir / "hermes_handoff.json").write_text(
        json.dumps({"application_id": "app-1", "stage": "done"}),
        encoding="utf-8",
    )
    return HermesSessionBridge(
        root=tmp_path,
        mode="live",
        endpoints={"vagas_bot_01": "http://bot01.test:8642/api/gateway/session-boundary"},
        api_keys={"vagas_bot_01": "super-secret"},
        transport=transport,
        binding_loader=lambda profile_id: {
            "profile_id": profile_id,
            "application_id": "app-1",
            "status": "active",
        },
    )


def _seed_ledger(tmp_path: Path, *, session_key="telegram:vagas_bot_01:chat-1"):
    ledger = HermesSessionLedger(
        tmp_path / "applications_v2" / "app-1" / "hermes_session_ledger.json",
        "app-1",
    )
    ledger.record_reset(
        profile_id="vagas_bot_01",
        session_key=session_key,
        old_session_id="old-1",
        new_session_id="clean-1",
        run_id="run-0",
        reason="pipeline:done",
        idempotency_key="run-0:reset",
    )
    return ledger


def test_cross_chat_route_is_rejected_before_gateway_request(tmp_path):
    transport = FakeTransport()
    bridge = _secure_bridge(tmp_path, transport)
    _seed_ledger(tmp_path)

    result = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-2", "run-1", "pipeline:done"
    )

    assert result["status"] == "binding_conflict"
    assert transport.calls == []


def test_cross_profile_is_rejected_before_gateway_request(tmp_path):
    transport = FakeTransport()
    bridge = _secure_bridge(tmp_path, transport)

    with pytest.raises(HermesSessionBridgeError, match="unsupported profile_id"):
        bridge.reset_for_application(
            "app-1", "vagas_bot_03", "telegram:vagas_bot_03:chat-1", "run-1", "pipeline:done"
        )
    assert transport.calls == []


def test_missing_handoff_blocks_mutation(tmp_path):
    transport = FakeTransport(responses=[_status(), _reset()])
    bridge = HermesSessionBridge(
        root=tmp_path,
        mode="live",
        endpoints={"vagas_bot_01": "http://bot01.test:8642/api/gateway/session-boundary"},
        api_keys={"vagas_bot_01": "super-secret"},
        transport=transport,
        binding_loader=lambda profile_id: {"application_id": "app-1", "status": "active"},
    )

    result = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )

    assert result["status"] == "handoff_required"
    assert transport.calls == []


def test_deleted_transcript_is_not_resumable(tmp_path):
    transport = FakeTransport()
    bridge = _secure_bridge(tmp_path, transport)
    ledger = _seed_ledger(tmp_path)
    ledger.mark_transcript_deleted("old-1", reason="operator_deleted_transcript")

    result = bridge.resume_for_application("app-1", "old-1", "run-1", "manual_correction")

    assert result["status"] == "not_resumable"
    assert result["reason"] == "transcript_deleted"
    assert transport.calls == []


def test_bearer_key_never_appears_in_bridge_result(tmp_path):
    transport = FakeTransport(responses=[_status(), _reset()])
    bridge = _secure_bridge(tmp_path, transport)

    result = bridge.reset_for_application(
        "app-1", "vagas_bot_01", "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )

    assert "super-secret" not in json.dumps(result)
    assert transport.calls[0][2]["Authorization"] == "Bearer super-secret"


def test_reconcile_pending_reset_reads_status_without_issuing_another_reset(tmp_path, monkeypatch):
    ledger = _seed_ledger(tmp_path)
    ledger.record_reset(
        profile_id="vagas_bot_01",
        session_key="telegram:vagas_bot_01:chat-1",
        old_session_id="clean-1",
        new_session_id="clean-1",
        run_id="run-1",
        reason="pipeline:done",
        idempotency_key="run-1:reset",
        status="pending_verification",
    )

    class ObserverOnlyBridge:
        def __init__(self, **kwargs):
            self.reset_called = False

        def observe_current_session(self, application_id, profile_id, session_key):
            return {"status": "ok", "current_session_id": "clean-2"}

        def reset_for_application(self, *args):
            self.reset_called = True
            raise AssertionError("reconciliation must never issue a reset")

    monkeypatch.setattr(applications_v2, "HermesSessionBridge", ObserverOnlyBridge)
    report = applications_v2.reconcile_hermes_session_boundaries(
        root=tmp_path,
        config={"hermes_session_boundaries": {"enabled": True, "mode": "live", "endpoints": {}}},
    )

    assert report["reconciled"] == 1
    records = ledger.history()
    assert records[-1]["operation"] == "reconcile"
    assert records[-1]["status"] == "reconciled"
    assert records[-1]["new_session_id"] == "clean-2"


def test_boundary_events_use_session_hash_and_not_full_session_key(monkeypatch, tmp_path):
    class EventBridge:
        def observe_current_session(self, *args):
            return {"status": "ok", "current_session_id": "clean-1"}

        def reset_for_application(self, *args):
            return {"status": "reset", "old_session_id": "clean-1", "new_session_id": "clean-2"}

    monkeypatch.setattr(applications_v2, "HermesSessionBridge", lambda **kwargs: EventBridge())
    app_dir = tmp_path / "app-1"
    app_dir.mkdir(parents=True)
    paths = applications_v2._app_paths(app_dir)
    paths["job_description"].write_text("job", encoding="utf-8")

    result = applications_v2._maybe_apply_hermes_session_boundary(
        {"record_id": "app-1", "company": "Acme", "role": "COO"},
        paths,
        {"stage": "done", "service_status": "done", "score": 8.0},
        {
            "hermes_session_boundaries": {
                "enabled": True,
                "mode": "live",
                "profile_id": "vagas_bot_01",
                "session_key": "telegram:vagas_bot_01:chat-1",
                "endpoints": {},
            }
        },
        run_id="run-1",
        pipeline_dry_run=False,
    )

    events = applications_v2.read_json(paths["event_log"])["events"]
    names = [event["type"] for event in events]
    assert "session_boundary_requested" in names
    assert "session_boundary_applied" in names
    serialized = json.dumps(events)
    assert "telegram:vagas_bot_01:chat-1" not in serialized
    assert result["status"] == "reset"
