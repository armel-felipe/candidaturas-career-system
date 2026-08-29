from __future__ import annotations

import json
from pathlib import Path

import pytest

from career.services.hermes_session_bridge import HermesSessionBridge


class InProcessGateway:
    """Small gateway contract emulator used for deterministic canaries."""

    def __init__(self):
        self.current = {}
        self.sessions = {}
        self.reset_count = 0
        self.calls = []

    def seed(self, profile_id: str, session_id: str, messages: list[dict]):
        self.current[profile_id] = session_id
        self.sessions[session_id] = list(messages)

    def __call__(self, method, url, headers, payload, timeout):
        profile_id = headers["X-Hermes-Profile"]
        self.calls.append((method, profile_id, payload))
        if method == "GET":
            return {
                "_http_status": 200,
                "status": "ok",
                "current_session_id": self.current[profile_id],
            }
        expected = payload["expected_session_id"]
        if expected != self.current[profile_id]:
            return {"_http_status": 409, "status": "conflict", "old_session_id": self.current[profile_id]}
        if payload["operation"] == "reset":
            self.reset_count += 1
            old = self.current[profile_id]
            new = f"{profile_id}-clean-{self.reset_count}"
            self.current[profile_id] = new
            self.sessions[new] = []
            return {
                "_http_status": 200,
                "status": "reset",
                "old_session_id": old,
                "new_session_id": new,
            }
        target = payload["target_session_id"]
        if target not in self.sessions:
            return {"_http_status": 409, "status": "invalid_target"}
        self.current[profile_id] = target
        return {
            "_http_status": 200,
            "status": "resumed",
            "old_session_id": expected,
            "new_session_id": target,
            "target_session_id": target,
        }


class TimeoutGateway(InProcessGateway):
    def __call__(self, method, url, headers, payload, timeout):
        if method == "POST":
            self.calls.append((method, headers["X-Hermes-Profile"], payload))
            raise TimeoutError("canary gateway unavailable")
        return super().__call__(method, url, headers, payload, timeout)


def _bridge(tmp_path: Path, gateway, profile_id: str, *, mode="live"):
    application_id = f"app-{profile_id}"
    app_dir = tmp_path / "applications_v2" / application_id
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "hermes_handoff.json").write_text(
        json.dumps({"application_id": application_id, "stage": "done"}),
        encoding="utf-8",
    )
    return HermesSessionBridge(
        root=tmp_path,
        mode=mode,
        endpoints={profile_id: f"http://{profile_id}.test:8642/api/gateway/session-boundary"},
        api_keys={profile_id: f"key-{profile_id}"},
        transport=gateway,
        binding_loader=lambda requested_profile: {
            "profile_id": requested_profile,
            "application_id": application_id,
            "status": "active",
        },
    ), application_id


@pytest.mark.parametrize("profile_id", ["vagas_bot_01", "vagas_bot_02"])
def test_dry_run_canary_never_sends_mutation_for_each_bot(tmp_path, profile_id):
    gateway = InProcessGateway()
    gateway.seed(profile_id, f"{profile_id}-old", [{"role": "user", "content": "legacy"}])
    bridge, application_id = _bridge(tmp_path, gateway, profile_id, mode="dry_run")

    result = bridge.reset_for_application(
        application_id,
        profile_id,
        f"telegram:{profile_id}:chat-1",
        "dry-run-1",
        "pipeline:done",
    )

    assert result["status"] == "dry_run"
    assert [call[0] for call in gateway.calls] == ["GET"]
    assert gateway.current[profile_id] == f"{profile_id}-old"


@pytest.mark.parametrize("profile_id", ["vagas_bot_01", "vagas_bot_02"])
def test_each_bot_preserves_old_transcript_and_supports_correction_cycle(tmp_path, profile_id):
    gateway = InProcessGateway()
    old_session_id = f"{profile_id}-old"
    legacy = [{"role": "user", "content": f"legacy-{index}"} for index in range(100)]
    gateway.seed(profile_id, old_session_id, legacy)
    bridge, application_id = _bridge(tmp_path, gateway, profile_id)
    session_key = f"telegram:{profile_id}:chat-1"

    first = bridge.reset_for_application(
        application_id, profile_id, session_key, "run-1", "pipeline:done"
    )
    clean_session_id = first["new_session_id"]
    resumed = bridge.resume_for_application(
        application_id, old_session_id, "run-2", "manual_correction"
    )
    second = bridge.reset_for_application(
        application_id, profile_id, session_key, "run-3", "pipeline:done"
    )

    assert first["status"] == "reset"
    assert resumed["status"] == "resumed"
    assert second["status"] == "reset"
    assert gateway.sessions[old_session_id] == legacy
    assert gateway.sessions[clean_session_id] == []
    assert gateway.current[profile_id] == second["new_session_id"]
    post_payloads = [payload for method, _profile, payload in gateway.calls if method == "POST"]
    assert all("transcript" not in payload and "messages" not in payload for payload in post_payloads)


def test_gateway_failure_stays_pending_and_does_not_mark_reset_as_success(tmp_path):
    profile_id = "vagas_bot_01"
    gateway = TimeoutGateway()
    gateway.seed(profile_id, "old", [])
    bridge, application_id = _bridge(tmp_path, gateway, profile_id)

    result = bridge.reset_for_application(
        application_id, profile_id, "telegram:vagas_bot_01:chat-1", "run-1", "pipeline:done"
    )

    assert result["status"] == "pending_verification"
    assert bridge.ledger_for_application(application_id).history()[-1]["status"] == "pending_verification"
    assert gateway.current[profile_id] == "old"
