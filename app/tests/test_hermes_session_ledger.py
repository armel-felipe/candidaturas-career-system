from __future__ import annotations

import pytest

from career.services.hermes_session_ledger import (
    HermesSessionLedger,
    HermesSessionLedgerError,
)


def test_new_ledger_has_no_current_binding(tmp_path):
    ledger = HermesSessionLedger(tmp_path / "hermes_session_ledger.json", "application-42")

    assert ledger.history() == []
    assert ledger.current_binding() is None


def test_record_reset_persists_complete_session_transition(tmp_path):
    ledger = HermesSessionLedger(tmp_path / "hermes_session_ledger.json", "application-42")

    result = ledger.record_reset(
        profile_id="vagas_bot_01",
        session_key="agent:main:telegram:dm:123",
        old_session_id="old-session",
        new_session_id="new-session",
        run_id="run-7",
        reason="applications_v2:done",
        idempotency_key="run-7:reset",
    )

    assert result["status"] == "recorded"
    assert result["operation"] == "reset"
    assert result["application_id"] == "application-42"
    assert result["profile_id"] == "vagas_bot_01"
    assert result["session_key"] == "agent:main:telegram:dm:123"
    assert result["old_session_id"] == "old-session"
    assert result["new_session_id"] == "new-session"
    assert result["target_session_id"] is None
    assert result["run_id"] == "run-7"
    assert result["reason"] == "applications_v2:done"
    assert result["created_at"]

    assert ledger.current_binding() == {
        "application_id": "application-42",
        "profile_id": "vagas_bot_01",
        "session_key": "agent:main:telegram:dm:123",
        "current_session_id": "new-session",
    }

    reloaded = HermesSessionLedger(tmp_path / "hermes_session_ledger.json", "application-42")
    assert reloaded.history() == [result]


def test_ledger_rejects_a_different_profile_binding(tmp_path):
    ledger = HermesSessionLedger(tmp_path / "hermes_session_ledger.json", "application-42")
    ledger.record_reset(
        profile_id="vagas_bot_01",
        session_key="agent:main:telegram:dm:123",
        old_session_id="old-session",
        new_session_id="new-session",
        run_id="run-7",
        reason="applications_v2:done",
        idempotency_key="run-7:reset",
    )

    with pytest.raises(HermesSessionLedgerError, match="profile_id"):
        ledger.record_reset(
            profile_id="vagas_bot_02",
            session_key="agent:main:telegram:dm:123",
            old_session_id="new-session",
            new_session_id="other-session",
            run_id="run-8",
            reason="applications_v2:done",
            idempotency_key="run-8:reset",
        )


def test_same_idempotency_key_returns_existing_record_without_duplicate(tmp_path):
    ledger = HermesSessionLedger(tmp_path / "hermes_session_ledger.json", "application-42")
    kwargs = {
        "profile_id": "vagas_bot_01",
        "session_key": "agent:main:telegram:dm:123",
        "old_session_id": "old-session",
        "new_session_id": "new-session",
        "run_id": "run-7",
        "reason": "applications_v2:done",
        "idempotency_key": "run-7:reset",
    }

    first = ledger.record_reset(**kwargs)
    replay = ledger.record_reset(**kwargs)

    assert replay == first
    assert len(ledger.history()) == 1


def test_reusing_idempotency_key_with_different_payload_is_rejected(tmp_path):
    ledger = HermesSessionLedger(tmp_path / "hermes_session_ledger.json", "application-42")
    kwargs = {
        "profile_id": "vagas_bot_01",
        "session_key": "agent:main:telegram:dm:123",
        "old_session_id": "old-session",
        "new_session_id": "new-session",
        "run_id": "run-7",
        "reason": "applications_v2:done",
        "idempotency_key": "run-7:reset",
    }
    ledger.record_reset(**kwargs)

    with pytest.raises(HermesSessionLedgerError, match="idempotency_key"):
        ledger.record_reset(**{**kwargs, "new_session_id": "different-session"})


def test_record_resume_updates_current_binding_to_target_session(tmp_path):
    ledger = HermesSessionLedger(tmp_path / "hermes_session_ledger.json", "application-42")
    ledger.record_reset(
        profile_id="vagas_bot_01",
        session_key="agent:main:telegram:dm:123",
        old_session_id="old-session",
        new_session_id="new-session",
        run_id="run-7",
        reason="applications_v2:done",
        idempotency_key="run-7:reset",
    )

    result = ledger.record_resume(
        profile_id="vagas_bot_01",
        session_key="agent:main:telegram:dm:123",
        old_session_id="new-session",
        target_session_id="old-session",
        run_id="run-8",
        reason="manual_correction",
        idempotency_key="run-8:resume",
    )

    assert result["operation"] == "resume"
    assert result["new_session_id"] == "old-session"
    assert result["target_session_id"] == "old-session"
    assert ledger.current_binding()["current_session_id"] == "old-session"
