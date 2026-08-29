from __future__ import annotations

from pathlib import Path

from career.services import applications_v2


class HandoffAwareBridge:
    def __init__(self, *, handoff_path: Path, current_session_id: str = "clean-1"):
        self.handoff_path = handoff_path
        self.current_session_id = current_session_id
        self.reset_called = False

    def observe_current_session(self, application_id, profile_id, session_key):
        return {"status": "ok", "current_session_id": self.current_session_id}

    def reset_for_application(self, *args):
        assert self.handoff_path.exists(), "handoff must exist before gateway mutation"
        self.reset_called = True
        return {
            "status": "reset",
            "old_session_id": self.current_session_id,
            "new_session_id": "clean-2",
            "idempotency_key": "run-1:reset",
        }


def _paths(tmp_path: Path):
    app_dir = tmp_path / "app-1"
    app_dir.mkdir(parents=True)
    paths = applications_v2._app_paths(app_dir)
    for name in ("job_description", "fit_map", "conversation_context"):
        paths[name].write_text("artifact", encoding="utf-8")
    return paths


def _config():
    return {
        "hermes_session_boundaries": {
            "enabled": True,
            "mode": "live",
            "profile_id": "vagas_bot_01",
            "session_key": "telegram:vagas_bot_01:chat-1",
            "endpoints": {"vagas_bot_01": "http://bot01.test:8642/api/gateway/session-boundary"},
        }
    }


def test_handoff_is_persisted_before_boundary_mutation(monkeypatch, tmp_path):
    paths = _paths(tmp_path)
    bridge = HandoffAwareBridge(handoff_path=paths["hermes_handoff"])
    monkeypatch.setattr(applications_v2, "HermesSessionBridge", lambda **kwargs: bridge)

    state = {
        "stage": "done",
        "service_status": "done",
        "score": 8.0,
        "next_action": None,
    }
    result = applications_v2._maybe_apply_hermes_session_boundary(
        {"record_id": "app-1", "company": "Acme", "role": "COO"},
        paths,
        state,
        _config(),
        run_id="run-1",
        pipeline_dry_run=False,
    )

    handoff = applications_v2.read_json(paths["hermes_handoff"])
    assert bridge.reset_called is True
    assert result["status"] == "reset"
    assert handoff["application_id"] == "app-1"
    assert handoff["company"] == "Acme"
    assert handoff["role"] == "COO"
    assert handoff["current_session_id"] == "clean-1"
    assert handoff["last_run_id"] == "run-1"
    assert all(Path(path).exists() for path in handoff["artifact_paths"])


def test_handoff_result_is_compact_and_points_to_existing_file(monkeypatch, tmp_path):
    paths = _paths(tmp_path)
    bridge = HandoffAwareBridge(handoff_path=paths["hermes_handoff"])
    monkeypatch.setattr(applications_v2, "HermesSessionBridge", lambda **kwargs: bridge)

    result = applications_v2._maybe_apply_hermes_session_boundary(
        {"record_id": "app-1", "company": "Acme", "role": "COO"},
        paths,
        {"stage": "low_fit", "service_status": "completed", "score": 4.0},
        _config(),
        run_id="run-1",
        pipeline_dry_run=False,
    )

    assert result["handoff_path"] == str(paths["hermes_handoff"])
    assert result["application_id"] == "app-1"
    assert result["stage"] == "low_fit"


def test_handoff_records_previous_session_ids_without_loading_transcript(tmp_path):
    paths = _paths(tmp_path)
    payload = applications_v2.write_hermes_handoff(
        {"record_id": "app-1", "company": "Acme", "role": "COO"},
        paths,
        {
            "stage": "done",
            "service_status": "done",
            "score": 8.0,
            "next_action": None,
        },
        run_id="run-2",
        current_session_id="clean-2",
        previous_session_ids=["old-1", "clean-1"],
    )

    assert payload["previous_session_ids"] == ["old-1", "clean-1"]
    assert "conversation_history" not in payload
    assert paths["hermes_handoff"].exists()
