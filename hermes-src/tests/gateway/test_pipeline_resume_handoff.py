from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key
from gateway.config import Platform


def _entry(session_id: str) -> SessionEntry:
    source = SessionSource(
        platform=Platform.TELEGRAM,
        user_id="user-1",
        chat_id="chat-1",
        user_name="tester",
        chat_type="dm",
    )
    from datetime import datetime

    return SessionEntry(
        session_key=build_session_key(source),
        session_id=session_id,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )


@pytest.mark.asyncio
async def test_resume_reopens_old_session_without_replaying_transcript_into_new_context():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    current = _entry("clean-session")
    target = _entry("old-session")
    runner.session_store = SimpleNamespace(_entries={current.session_key: current})
    runner._handle_resume_command = AsyncMock(
        side_effect=lambda event: runner.session_store._entries.__setitem__(
            current.session_key, target
        )
    )

    result = await runner.resume_session_key(
        current.session_key,
        target_session_id="old-session",
        expected_session_id="clean-session",
        reason="manual_correction",
        idempotency_key="run-2:resume",
    )

    assert result["status"] == "resumed"
    event = runner._handle_resume_command.await_args.args[0]
    assert isinstance(event, MessageEvent)
    assert event.text == "/resume old-session"
    assert event.internal is True
    assert event.metadata["pipeline_session_boundary"] is True
    assert runner.session_store._entries[current.session_key].session_id == "old-session"
