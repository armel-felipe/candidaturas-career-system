from __future__ import annotations

import json
import os

from career.services.database import Database
from scripts.run_phase_c_pilot import run_pilot


def test_phase_c_controlled_pilot_completes_cell_execution(tmp_path):
    previous = {
        key: os.environ.get(key)
        for key in (
            "CAREER_CONTROL_DB_PATH",
            "CAREER_AUTHORITY_LEDGER_PATH",
            "CAREER_WORKSPACE_OWNER",
            "CAREER_CONTROL_DB_ID",
        )
    }
    try:
        result = run_pilot(tmp_path)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert result["status"] == "completed"
    assert result["execution"] == ["validated"]
    assert result["runtime"]["status"] == "completed"
    assert result["request_hash"]
    assert result["sqlite_counts"] == {
        "cell_inputs": 1,
        "cell_requests": 1,
        "cell_handovers": 1,
        "validation_receipts": 3,
        "runtime_runs": 1,
        "artifacts": 1,
        "runtime_observations": 2,
    }
    request = json.loads(__import__("pathlib").Path(result["request_json"]).read_text())
    assert request["cellular"] is True
    assert request["application_id"] == "phase-c-pilot"

    database = Database(tmp_path / ".career-state" / "career.db")
    database.init_schema()
    attempt = database.fetch_one(
        "SELECT status, inputs_registered_at FROM cell_attempts "
        "WHERE run_id = ? AND node_id = ? AND attempt = 1",
        ("run_phase_c_pilot", "analyze_fit"),
    )
    assert attempt["status"] == "validated"
    assert attempt["inputs_registered_at"] is not None
    database.close()
