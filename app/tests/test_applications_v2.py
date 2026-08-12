from __future__ import annotations

import pytest

from career.services import applications_v2
from career.services.database import Database
from career.utils import ValidationFailure


def test_activate_local_parallel_mode_sets_two_cellular_workers(tmp_path, monkeypatch):
    state_dir = tmp_path / ".career-state"
    database = Database(state_dir / "career.db")
    database.init_schema()
    monkeypatch.setattr(applications_v2, "V2_DIR", state_dir / "applications_v2")

    try:
        result = applications_v2.activate_local_parallel_mode(max_workers=2)
    finally:
        database.close()

    assert result == {
        "status": "activated",
        "pipeline_mode": "cellular",
        "max_per_run": 2,
        "cellular_max_workers": 2,
        "control_db_id": result["control_db_id"],
    }
    assert result["control_db_id"].startswith("control_")


def test_activate_local_parallel_mode_rejects_other_capacity():
    with pytest.raises(ValueError, match="exactly 2"):
        applications_v2.activate_local_parallel_mode(max_workers=3)


def test_parallel_mode_status_requires_matching_control_database_id(tmp_path, monkeypatch):
    state_dir = tmp_path / ".career-state"
    database = Database(state_dir / "career.db")
    database.init_schema()
    monkeypatch.setattr(applications_v2, "V2_DIR", state_dir / "applications_v2")

    try:
        activated = applications_v2.activate_local_parallel_mode(max_workers=2)
        missing = applications_v2.parallel_mode_status()
        monkeypatch.setenv("CAREER_CONTROL_DB_ID", activated["control_db_id"])
        ready = applications_v2.parallel_mode_status()
    finally:
        database.close()

    assert missing["ready"] is False
    assert missing["blocker"] == "career_control_db_id_missing"
    assert ready["ready"] is True
    assert ready["control_db_id"] == activated["control_db_id"]


def test_cellular_heartbeat_requires_ready_parallel_runtime(monkeypatch):
    monkeypatch.setattr(
        applications_v2,
        "parallel_mode_status",
        lambda: {"ready": False, "blocker": "career_control_db_id_missing"},
    )

    with pytest.raises(ValidationFailure, match="career_control_db_id_missing"):
        applications_v2.run_heartbeat(
            applications_v2.HeartbeatV2Options(
                max_per_run=2,
                run_agent=True,
                dry_run=False,
                cellular=True,
                enforce_parallel_runtime=True,
            )
        )


def test_cellular_parallel_mode_rejects_capacity_other_than_two(monkeypatch):
    monkeypatch.setattr(
        applications_v2,
        "parallel_mode_status",
        lambda: {"ready": True, "pipeline_mode": "cellular"},
    )

    with pytest.raises(ValidationFailure, match="exactly 2 applications"):
        applications_v2.run_heartbeat(
            applications_v2.HeartbeatV2Options(
                max_per_run=3,
                run_agent=True,
                dry_run=False,
                cellular=True,
                enforce_parallel_runtime=True,
            )
        )
