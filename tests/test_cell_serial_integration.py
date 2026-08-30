from __future__ import annotations

from types import SimpleNamespace

from career.services import applications_v2


class _FakeExecutor:
    def __init__(self, execution_mode: str):
        self.execution_mode = execution_mode
        self.calls: list[str] = []

    def _load_run(self, run_id: str):
        self.calls.append(f"load:{run_id}")
        return SimpleNamespace(execution_mode=self.execution_mode), None

    def run_serial_stage(self, run_id: str):
        self.calls.append(f"serial:{run_id}")
        return ["serial-stage"]

    def run_ready(self, run_id: str):
        self.calls.append(f"ready:{run_id}")
        return ["wave-ready"]


def test_serial_service_consumes_only_serial_stage(monkeypatch):
    executor = _FakeExecutor("serial")

    def unexpected_wave_drain(*args, **kwargs):
        raise AssertionError("serial execution must not drain wave successors")

    monkeypatch.setattr(
        applications_v2, "_drain_cellular_ready_waves", unexpected_wave_drain
    )

    executed = applications_v2._execute_cellular_ready(executor, "run-serial")

    assert executed == ["serial-stage"]
    assert executor.calls == ["load:run-serial", "serial:run-serial"]


def test_wave_service_keeps_existing_wave_drain(monkeypatch):
    executor = _FakeExecutor("wave")
    monkeypatch.setattr(
        applications_v2,
        "_drain_cellular_ready_waves",
        lambda current_executor, run_id: ["wave-drained"],
    )

    executed = applications_v2._execute_cellular_ready(executor, "run-wave")

    assert executed == ["wave-ready", "wave-drained"]
    assert executor.calls == ["load:run-wave", "ready:run-wave"]
