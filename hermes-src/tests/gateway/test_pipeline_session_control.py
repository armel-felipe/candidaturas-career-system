from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key


def _source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="user-1",
        chat_id="chat-1",
        user_name="tester",
        chat_type="dm",
    )


def _entry(session_id: str) -> SessionEntry:
    source = _source()
    return SessionEntry(
        session_key=build_session_key(source),
        session_id=session_id,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )


def _runner_with_fake_reset():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    old = _entry("session-old")
    new = _entry("session-new")
    runner.session_store = SimpleNamespace(_entries={old.session_key: old})

    async def fake_reset(event: MessageEvent):
        assert event.text == "/new"
        assert event.internal is True
        runner.session_store._entries[old.session_key] = new
        return "Session reset"

    runner._handle_reset_command = fake_reset
    return runner, old, new


@pytest.mark.asyncio
async def test_reset_session_key_rotates_only_the_expected_binding():
    runner, old, new = _runner_with_fake_reset()

    result = await runner.reset_session_key(
        old.session_key,
        expected_session_id="session-old",
        reason="pipeline:test",
        idempotency_key="run-1:reset",
    )

    assert result == {
        "status": "reset",
        "operation": "reset",
        "session_key": old.session_key,
        "old_session_id": "session-old",
        "new_session_id": "session-new",
        "target_session_id": None,
        "reason": "pipeline:test",
        "idempotency_key": "run-1:reset",
    }


@pytest.mark.asyncio
async def test_reset_session_key_returns_conflict_for_stale_expected_session():
    runner, old, _new = _runner_with_fake_reset()

    result = await runner.reset_session_key(
        old.session_key,
        expected_session_id="different-session",
        reason="pipeline:test",
        idempotency_key="run-1:reset",
    )

    assert result["status"] == "conflict"
    assert result["old_session_id"] == "session-old"
    assert runner._handle_reset_command.__name__ == "fake_reset"


@pytest.mark.asyncio
async def test_reset_session_key_replays_same_idempotency_key_without_second_reset():
    runner, old, _new = _runner_with_fake_reset()
    handler = runner._handle_reset_command

    first = await runner.reset_session_key(
        old.session_key,
        expected_session_id="session-old",
        reason="pipeline:test",
        idempotency_key="run-1:reset",
    )
    second = await runner.reset_session_key(
        old.session_key,
        expected_session_id="session-old",
        reason="pipeline:test",
        idempotency_key="run-1:reset",
    )

    assert first["status"] == "reset"
    assert second["status"] == "already_applied"
    assert runner._handle_reset_command is handler


@pytest.mark.asyncio
async def test_resume_session_key_reports_invalid_target_when_native_resume_does_not_switch():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    old = _entry("session-current")
    runner.session_store = SimpleNamespace(_entries={old.session_key: old})

    async def fake_resume(event: MessageEvent):
        assert event.text == "/resume session-old"
        return "Session not found"

    runner._handle_resume_command = fake_resume

    result = await runner.resume_session_key(
        old.session_key,
        target_session_id="session-old",
        expected_session_id="session-current",
        reason="manual_correction",
        idempotency_key="run-2:resume",
    )

    assert result["status"] == "invalid_target"
    assert result["target_session_id"] == "session-old"


@pytest.mark.asyncio
async def test_resume_session_key_switches_to_target_through_native_handler():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    old = _entry("session-current")
    target = _entry("session-old")
    runner.session_store = SimpleNamespace(_entries={old.session_key: old})

    async def fake_resume(event: MessageEvent):
        assert event.text == "/resume session-old"
        runner.session_store._entries[old.session_key] = target
        return "Session resumed"

    runner._handle_resume_command = fake_resume

    result = await runner.resume_session_key(
        old.session_key,
        target_session_id="session-old",
        expected_session_id="session-current",
        reason="manual_correction",
        idempotency_key="run-2:resume",
    )

    assert result["status"] == "resumed"
    assert result["old_session_id"] == "session-current"
    assert result["new_session_id"] == "session-old"


@pytest.mark.asyncio
async def test_session_boundary_status_is_read_only_and_returns_current_binding():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    old = _entry("session-current")
    runner.session_store = SimpleNamespace(_entries={old.session_key: old})

    result = await runner.session_boundary_status(old.session_key)

    assert result == {
        "status": "ok",
        "operation": "status",
        "session_key": old.session_key,
        "current_session_id": "session-current",
    }
    assert runner.session_store._entries[old.session_key].session_id == "session-current"


@pytest.mark.asyncio
async def test_session_boundary_status_reports_missing_binding():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.session_store = SimpleNamespace(_entries={})

    result = await runner.session_boundary_status("agent:missing")

    assert result["status"] == "not_found"


class _Request:
    def __init__(self, payload, authorization="Bearer test-key"):
        self._payload = payload
        self.headers = {"Authorization": authorization}
        self.method = "POST"
        self.path_qs = "/api/gateway/session-boundary"
        self.transport = None
        self.remote = ""

    async def json(self):
        return self._payload


class _StatusRequest(_Request):
    def __init__(self, session_key, authorization="Bearer test-key"):
        super().__init__({}, authorization=authorization)
        self.method = "GET"
        self.query = {"session_key": session_key}


def _response_json(response):
    return json.loads(response.text)


@pytest.mark.asyncio
async def test_api_session_boundary_requires_authentication():
    from gateway.platforms.api_server import APIServerAdapter

    adapter = APIServerAdapter(
        PlatformConfig(enabled=True, extra={"key": "test-key"})
    )

    response = await adapter._handle_gateway_session_boundary(
        _Request({}, authorization="Bearer wrong-key")
    )

    assert response.status == 401


@pytest.mark.asyncio
async def test_api_session_boundary_dispatches_reset_to_active_runner():
    from gateway.platforms.api_server import APIServerAdapter

    adapter = APIServerAdapter(
        PlatformConfig(enabled=True, extra={"key": "test-key"})
    )
    runner = SimpleNamespace(
        reset_session_key=AsyncMock(
            return_value={
                "status": "reset",
                "operation": "reset",
                "session_key": "agent:main:telegram:dm:chat-1",
                "old_session_id": "old",
                "new_session_id": "new",
                "reason": "pipeline:test",
                "idempotency_key": "run-1:reset",
            }
        )
    )
    payload = {
        "operation": "reset",
        "session_key": "agent:main:telegram:dm:chat-1",
        "expected_session_id": "old",
        "reason": "pipeline:test",
        "idempotency_key": "run-1:reset",
    }

    with patch("gateway.run._gateway_runner_ref", return_value=runner):
        response = await adapter._handle_gateway_session_boundary(_Request(payload))

    assert response.status == 200
    assert _response_json(response)["status"] == "reset"
    runner.reset_session_key.assert_awaited_once_with(
        "agent:main:telegram:dm:chat-1",
        expected_session_id="old",
        reason="pipeline:test",
        idempotency_key="run-1:reset",
    )


@pytest.mark.asyncio
async def test_api_session_boundary_status_dispatches_read_only_lookup():
    from gateway.platforms.api_server import APIServerAdapter

    adapter = APIServerAdapter(
        PlatformConfig(enabled=True, extra={"key": "test-key"})
    )
    runner = SimpleNamespace(
        session_boundary_status=AsyncMock(
            return_value={
                "status": "ok",
                "operation": "status",
                "session_key": "agent:main:telegram:dm:chat-1",
                "current_session_id": "old",
            }
        )
    )

    with patch("gateway.run._gateway_runner_ref", return_value=runner):
        response = await adapter._handle_gateway_session_boundary_status(
            _StatusRequest("agent:main:telegram:dm:chat-1")
        )

    assert response.status == 200
    assert _response_json(response)["current_session_id"] == "old"
    runner.session_boundary_status.assert_awaited_once_with(
        "agent:main:telegram:dm:chat-1"
    )


@pytest.mark.asyncio
async def test_api_session_boundary_rejects_missing_expected_session():
    from gateway.platforms.api_server import APIServerAdapter

    adapter = APIServerAdapter(
        PlatformConfig(enabled=True, extra={"key": "test-key"})
    )
    payload = {
        "operation": "reset",
        "session_key": "agent:main:telegram:dm:chat-1",
        "reason": "pipeline:test",
        "idempotency_key": "run-1:reset",
    }

    response = await adapter._handle_gateway_session_boundary(_Request(payload))

    assert response.status == 400


@pytest.mark.asyncio
async def test_api_session_boundary_rejects_missing_session_key():
    from gateway.platforms.api_server import APIServerAdapter

    adapter = APIServerAdapter(
        PlatformConfig(enabled=True, extra={"key": "test-key"})
    )
    payload = {
        "operation": "reset",
        "expected_session_id": "old",
        "reason": "pipeline:test",
        "idempotency_key": "run-1:reset",
    }

    response = await adapter._handle_gateway_session_boundary(_Request(payload))

    assert response.status == 400
