from __future__ import annotations

import json
from pathlib import Path

from career.services.canary_control import probe_runner


def _runner_config() -> dict[str, object]:
    return {
        "kind": "hermes",
        "command": "hermes",
        "agent": "build",
        "timeout_minutes": 90,
    }


def _materialize_task3_request(root: Path, *, application_id: str = "canary-app") -> Path:
    request_dir = (
        root
        / ".career-state"
        / "applications_v2"
        / application_id
        / "requests"
        / "cellular"
        / "run-canary"
        / "analyze_fit"
        / "1"
    )
    request_dir.mkdir(parents=True, exist_ok=True)
    request_json = request_dir / "request.json"
    request_md = request_dir / "request.md"
    manifest = (
        root
        / ".career-state"
        / "applications_v2"
        / application_id
        / "cells"
        / "analyze_fit"
        / "1"
        / "manifest.json"
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{}", encoding="utf-8")
    draft = root / ".career-state" / "applications_v2" / application_id / "fit_map.draft.json"
    request_json.write_text(
        json.dumps(
            {
                "cellular": True,
                "application_id": application_id,
                "run_id": "run-canary",
                "node_id": "analyze_fit",
                "attempt": 1,
                "manifest_path": str(manifest),
                "read_allowlist": [str(manifest)],
                "write_allowlist": [str(draft)],
                "objective": "Produce only the FIT_MAP draft.",
            }
        ),
        encoding="utf-8",
    )
    request_md.write_text("# request\n", encoding="utf-8")
    return request_json


def test_probe_runner_blocks_when_runner_is_unavailable_without_calling_harness(
    tmp_path, monkeypatch
):
    calls: list[dict[str, object]] = []

    def blocked_harness(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("probe_runner must not call HarnessSupervisor when runner is unavailable")

    monkeypatch.setattr("career.services.canary_control.shutil.which", lambda name: None)
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        blocked_harness,
    )

    result = probe_runner(_runner_config(), tmp_path)

    assert result == {
        "status": "blocked",
        "command": [
            "hermes",
            "--accept-hooks",
            "-z",
            "Leia o arquivo .career-state/runner_probe/request.md. Runner probe only; do not resume prior sessions.",
        ],
        "type": "hermes",
        "available": False,
        "returncode": 127,
        "blocker": "runner_unavailable",
    }
    assert "resume" not in result["command"]
    assert calls == []


def test_probe_runner_uses_task3_request_and_returns_compact_report(tmp_path, monkeypatch):
    request_json = _materialize_task3_request(tmp_path)
    captured: dict[str, object] = {}

    def fake_harness(self, **kwargs):
        captured.update(kwargs)
        return {
            "command": ["/usr/bin/hermes", "--accept-hooks", "-z", "fresh request only"],
            "returncode": 0,
            "stdout": "should stay out of the probe report",
            "stderr": "should stay out of the probe report",
            "isolation": {"status": "ok"},
        }

    monkeypatch.setattr(
        "career.services.canary_control.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        fake_harness,
    )

    result = probe_runner(_runner_config(), tmp_path)

    assert result == {
        "status": "completed",
        "command": ["/usr/bin/hermes", "--accept-hooks", "-z", "fresh request only"],
        "type": "hermes",
        "available": True,
        "returncode": 0,
        "blocker": None,
    }
    assert "stdout" not in result
    assert "stderr" not in result
    assert captured["record_key"] == "canary-app"
    assert Path(captured["application_dir"]).resolve() == request_json.parents[5].resolve()
    assert Path(captured["request_json"]).resolve() == request_json.resolve()
    assert Path(captured["request_md"]).resolve() == request_json.with_suffix(".md").resolve()


def test_probe_runner_blocks_without_task3_request_and_never_falls_back(
    tmp_path, monkeypatch
):
    calls: list[dict[str, object]] = []

    def fake_harness(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("probe_runner must not call HarnessSupervisor without a Task 3 request")

    monkeypatch.setattr(
        "career.services.canary_control.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        fake_harness,
    )

    result = probe_runner(_runner_config(), tmp_path)

    assert result == {
        "status": "blocked",
        "command": [
            "/usr/bin/hermes",
            "--accept-hooks",
            "-z",
            "Leia o arquivo .career-state/runner_probe/request.md. Runner probe only; do not resume prior sessions.",
        ],
        "type": "hermes",
        "available": True,
        "returncode": None,
        "blocker": "d2_request_missing",
    }
    assert "resume" not in result["command"]
    assert calls == []
