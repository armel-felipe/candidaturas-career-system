from __future__ import annotations

import json
import threading
import time
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


def test_serial_worker_drains_ready_stage_until_seal(tmp_path: Path, monkeypatch):
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)
    supervisor.root = tmp_path
    supervisor.db = _FakeDatabase()
    supervisor.db.latest = {
        "run_id": "run_serial_drain",
        "application_id": "app-drain",
        "status": "planned",
        "graph_json": json.dumps({"execution_mode": "serial"}),
    }
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        stage_number = sum(item[2] == "applications:run" for item in calls)
        if stage_number == 1:
            payload = {
                "status": "ready", "run_id": "run_serial_drain",
                "execution_mode": "serial",
                "serial_stage": {"stage": "notion", "status": "ready", "next_stage": "seal"},
            }
        else:
            payload = {
                "status": "completed", "run_id": "run_serial_drain",
                "execution_mode": "serial",
                "serial_stage": {"stage": "seal", "status": "completed", "next_stage": None},
            }
        return type("Completed", (), {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""})()

    monkeypatch.setattr("career.services.harness_supervisor.subprocess.run", fake_run)
    result = supervisor._run_serial_package_base(
        requested_steps=["cv", "notion"], application_id="app-drain", model=None, variant=None,
    )

    assert result["status"] == "completed"
    assert result["serial_stage"]["stage"] == "seal"
    assert sum(command[2] == "applications:run" for command in calls) == 2


def test_plan_failure_does_not_execute_stdout_run_id_without_validated_database_run(
    tmp_path: Path, monkeypatch
):
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)
    supervisor.root = tmp_path
    supervisor.db = _FakeDatabase()
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return type("Completed", (), {
            "returncode": 1,
            "stdout": json.dumps({"run_id": "run_untrusted"}),
            "stderr": "planner failed",
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

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "serial_plan_creation_failed"
    assert result["stdout"]
    assert not any(command[2] == "applications:run" for command in calls)


def test_shared_latest_run_without_local_plan_is_not_reused(tmp_path: Path, monkeypatch):
    """A bot must not resume a serial graph persisted in the other bot's tree."""
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)
    supervisor.root = tmp_path
    supervisor.db = _FakeDatabase()
    supervisor.db.latest = {
        "run_id": "run_from_bot02",
        "application_id": "app-shared",
        "status": "running",
        "graph_json": json.dumps({"execution_mode": "serial"}),
    }
    applications_root = tmp_path / ".career-state" / "applications_v2"
    (applications_root / "app-shared" / "plans").mkdir(parents=True)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[2] == "applications:plan":
            plan_path = applications_root / "app-shared" / "plans" / "run_from_bot01.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "run_id": "run_from_bot01",
                        "application_id": "app-shared",
                        "execution_mode": "serial",
                    }
                ),
                encoding="utf-8",
            )
            supervisor.db.latest = {
                "run_id": "run_from_bot01",
                "application_id": "app-shared",
                "status": "planned",
                "graph_json": json.dumps({"execution_mode": "serial"}),
            }
            return type("Completed", (), {
                "returncode": 0,
                "stdout": json.dumps({"status": "planned", "run_id": "run_from_bot01"}),
                "stderr": "",
            })()
        return type("Completed", (), {
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "status": "running",
                    "run_id": "run_from_bot01",
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
        application_id="app-shared",
        model=None,
        variant=None,
    )

    assert result["status"] == "awaiting_agent"
    assert result["run_id"] == "run_from_bot01"
    assert calls[0][2] == "applications:plan"
    assert calls[1][2] == "applications:run"


def test_serial_run_failure_preserves_cli_stdout_for_diagnosis(tmp_path: Path, monkeypatch):
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)
    supervisor.root = tmp_path
    supervisor.db = _FakeDatabase()
    supervisor.db.latest = {
        "run_id": "run-failure-details",
        "application_id": "app-failure-details",
        "status": "running",
        "graph_json": json.dumps({"execution_mode": "serial"}),
    }
    monkeypatch.setattr(
        "career.services.harness_supervisor.subprocess.run",
        lambda command, **kwargs: type(
            "Completed",
            (),
            {
                "returncode": 1,
                "stdout": json.dumps({"error": "local plan mismatch"}),
                "stderr": "",
            },
        )(),
    )

    result = supervisor._run_serial_package_base(
        requested_steps=["cv", "notion"],
        application_id="app-failure-details",
        model=None,
        variant=None,
    )

    assert result["blocker_reason"] == "serial_run_failed"
    assert "local plan mismatch" in result["stdout"]


def test_concurrent_serial_continuations_create_one_plan_and_run(
    tmp_path: Path, monkeypatch
):
    supervisor_db = _FakeDatabase()
    supervisors = []
    for _ in range(2):
        supervisor = HarnessSupervisor.__new__(HarnessSupervisor)
        supervisor.root = tmp_path
        supervisor.db = supervisor_db
        supervisors.append(supervisor)
    calls = []
    calls_lock = threading.Lock()

    def fake_fetch_one(query, params=()):
        if "application_runs" in query and supervisor_db.latest is None:
            time.sleep(0.05)
        return _FakeDatabase.fetch_one(supervisor_db, query, params)

    supervisor_db.fetch_one = fake_fetch_one

    def fake_run(command, **kwargs):
        with calls_lock:
            calls.append(command)
            if command[2] == "applications:plan":
                supervisor_db.latest = {
                    "run_id": "run_concurrent",
                    "application_id": "app-concurrent",
                    "status": "planned",
                    "graph_json": json.dumps({"execution_mode": "serial"}),
                }
        time.sleep(0.05)
        if command[2] == "applications:plan":
            return type("Completed", (), {
                "returncode": 0,
                "stdout": json.dumps({"run_id": "run_concurrent"}),
                "stderr": "",
            })()
        return type("Completed", (), {
            "returncode": 0,
            "stdout": json.dumps({"status": "running", "run_id": "run_concurrent"}),
            "stderr": "",
        })()

    monkeypatch.setattr(
        "career.services.harness_supervisor.subprocess.run", fake_run
    )
    results = []

    def invoke(item):
        results.append(
            item._run_serial_package_base(
                requested_steps=["cv", "notion"],
                application_id="app-concurrent",
                model=None,
                variant=None,
            )
        )

    threads = [threading.Thread(target=invoke, args=(item,)) for item in supervisors]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads)
    assert len(results) == 2
    assert {item["run_id"] for item in results} == {"run_concurrent"}
    assert sum(command[2] == "applications:plan" for command in calls) == 1
    assert sum(command[2] == "applications:run" for command in calls) == 2


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
