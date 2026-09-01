from __future__ import annotations

import json
from pathlib import Path

from career.services.harness_supervisor import HarnessSupervisor


class _FakeDatabase:
    def __init__(self):
        self.latest = None

    def fetch_one(self, query, params=()):
        if "application_runs" in query:
            return self.latest
        return None


class _PlanFailureDatabase(_FakeDatabase):
    def __init__(self):
        super().__init__()
        self.application_run_reads = 0

    def fetch_one(self, query, params=()):
        if "application_runs" in query:
            self.application_run_reads += 1
            if self.application_run_reads == 1:
                return None
        return super().fetch_one(query, params)


def test_package_pipeline_starts_serial_plan_and_runs_once_per_continuation(
    tmp_path: Path, monkeypatch
):
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)
    supervisor.root = tmp_path
    supervisor.db = _FakeDatabase()
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[2] == "applications:plan":
            supervisor.db.latest = {
                "run_id": "run_serial_1",
                "application_id": "app-serial",
                "status": "planned",
            }
            return type("Completed", (), {
                "returncode": 0,
                "stdout": json.dumps({"status": "planned", "run_id": "run_serial_1"}),
                "stderr": "",
            })()
        return type("Completed", (), {
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "status": "ready",
                    "run_id": "run_serial_1",
                    "execution_mode": "serial",
                    "serial_stage": {
                        "stage": "analyze",
                        "status": "awaiting_agent",
                        "next_stage": None,
                    },
                }
            ),
            "stderr": "",
        })()

    monkeypatch.setattr(
        "career.services.harness_supervisor.subprocess.run", fake_run
    )

    first = supervisor._execute_pipeline_request(
        "processe a vaga com CV, OneDrive e Notion",
        requested_steps=["cv", "onedrive", "notion"],
        application_id="app-serial",
        model=None,
        variant=None,
        runtime_context=None,
        channel="cli",
    )
    second = supervisor._execute_pipeline_request(
        "continue",
        requested_steps=["cv", "onedrive", "notion"],
        application_id="app-serial",
        model=None,
        variant=None,
        runtime_context=None,
        channel="cli",
    )

    assert first["status"] == "awaiting_agent"
    assert second["status"] == "awaiting_agent"
    assert first["run_id"] == second["run_id"] == "run_serial_1"
    assert sum(command[2] == "applications:plan" for command in calls) == 1
    assert sum(command[2] == "applications:run" for command in calls) == 2
    plan_command = calls[0]
    assert "--execution-mode" in plan_command
    assert plan_command[plan_command.index("--execution-mode") + 1] == "serial"
    assert plan_command.count("--deliverable") == 2
    assert calls[1][-1] == "--run-agent"


def test_plan_failure_adopts_newly_persisted_serial_run_without_duplicate_plan(
    tmp_path: Path, monkeypatch
):
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)
    supervisor.root = tmp_path
    supervisor.db = _PlanFailureDatabase()
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[2] == "applications:plan":
            supervisor.db.latest = {
                "run_id": "run_persisted_before_failure",
                "application_id": "app-rappi",
                "status": "running",
                "graph_json": json.dumps({"execution_mode": "serial"}),
            }
            return type("Completed", (), {
                "returncode": 1,
                "stdout": "",
                "stderr": "planner exited after persisting the run",
            })()
        return type("Completed", (), {
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "status": "running",
                    "run_id": "run_persisted_before_failure",
                    "execution_mode": "serial",
                    "serial_stage": {"stage": "analyze", "status": "awaiting_agent"},
                }
            ),
            "stderr": "",
        })()

    monkeypatch.setattr(
        "career.services.harness_supervisor.subprocess.run", fake_run
    )

    result = supervisor._run_serial_package_base(
        requested_steps=["cv", "notion"],
        application_id="app-rappi",
        model=None,
        variant=None,
    )

    assert result["run_id"] == "run_persisted_before_failure"
    assert result["status"] == "awaiting_agent"
    assert sum(command[2] == "applications:plan" for command in calls) == 1
    assert sum(command[2] == "applications:run" for command in calls) == 1


def test_pipeline_does_not_report_approval_as_completed(monkeypatch):
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)
    supervisor.root = Path(".")
    supervisor.db = _FakeDatabase()

    monkeypatch.setattr(
        supervisor,
        "_run_serial_package_base",
        lambda **_kwargs: {
            "status": "awaiting_approval",
            "application_id": "app-approval",
            "run_id": "run-approval",
            "next_stage": "notion",
        },
    )

    result = supervisor._execute_pipeline_request(
        "CV, OneDrive e Notion",
        requested_steps=["cv", "onedrive", "notion"],
        application_id="app-approval",
        model=None,
        variant=None,
        runtime_context=None,
        channel="cli",
    )

    assert result["status"] == "awaiting_approval"
    assert result["status"] != "completed"
