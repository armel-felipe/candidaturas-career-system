from __future__ import annotations

import json

from career.services import multiagent


def test_write_runbook_normalizes_legacy_contracts(tmp_path, monkeypatch):
    runbook_path = tmp_path / "multiagent_runbook.json"
    monkeypatch.setattr(multiagent, "ROOT", tmp_path)
    monkeypatch.setattr(multiagent, "RUNBOOK_PATH", runbook_path)

    result = multiagent.write_runbook()

    assert result["status"] == "ok"
    payload = json.loads(runbook_path.read_text(encoding="utf-8"))
    assert len(payload["steps"]) == 8
    assert all(isinstance(step["agent"], str) for step in payload["steps"])
    assert all(isinstance(step["purpose"], str) for step in payload["steps"])
