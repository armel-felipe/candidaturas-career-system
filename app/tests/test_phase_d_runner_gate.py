from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from career.services.canary_control import REDACTED_REQUEST_PROMPT, probe_runner
from scripts import phase_d_canary


def _runner_config() -> dict[str, object]:
    return {
        "kind": "hermes",
        "command": "hermes",
        "agent": "build",
        "timeout_minutes": 90,
    }


def _materialize_task3_request(
    root: Path,
    *,
    application_id: str = "canary-app",
    run_id: str = "run-canary",
    attempt: int = 1,
) -> tuple[Path, dict[str, object]]:
    request_dir = (
        root
        / ".career-state"
        / "applications_v2"
        / application_id
        / "requests"
        / "cellular"
        / run_id
        / "analyze_fit"
        / str(attempt)
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
        / str(attempt)
        / "manifest.json"
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{}", encoding="utf-8")
    draft = (
        root
        / ".career-state"
        / "applications_v2"
        / application_id
        / "fit_map.draft.json"
    )
    payload: dict[str, object] = {
        "cellular": True,
        "application_id": application_id,
        "run_id": run_id,
        "node_id": "analyze_fit",
        "attempt": attempt,
        "manifest_path": str(manifest),
        "read_allowlist": [str(manifest)],
        "write_allowlist": [str(draft)],
        "objective": "Produce only the FIT_MAP draft.",
    }
    request_json.write_text(json.dumps(payload), encoding="utf-8")
    request_md.write_text("# request\n", encoding="utf-8")
    return request_json, payload


def _write_runner_gate_manifest(
    root: Path,
    request_json: Path,
    payload: dict[str, object],
    *,
    d0_approved: bool = True,
    d1_approved: bool = True,
    d2_approved: bool = True,
    request_hash: str | None = None,
    read_allowlist: list[str] | None = None,
    write_allowlist: list[str] | None = None,
) -> Path:
    manifest_path = root / ".career-state" / "phase_d_runner_gate.json"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    body = {
        "kind": "phase_d_runner_gate_manifest",
        "version": 1,
        "target": "vagas_bot_01",
        "approvals": {
            "d0": {"approved": d0_approved, "status": "ready" if d0_approved else "blocked"},
            "d1": {"approved": d1_approved, "status": "dry_run_ok" if d1_approved else "blocked"},
            "d2": {
                "approved": d2_approved,
                "status": "completed" if d2_approved else "blocked",
                "application_id": payload["application_id"],
                "run_id": payload["run_id"],
                "node_id": payload["node_id"],
                "attempt": payload["attempt"],
                "request_json": str(request_json),
                "request_md": str(request_json.with_suffix(".md")),
                "request_hash": request_hash
                if request_hash is not None
                else hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                "read_allowlist": list(read_allowlist if read_allowlist is not None else payload["read_allowlist"]),
                "write_allowlist": list(
                    write_allowlist if write_allowlist is not None else payload["write_allowlist"]
                ),
            },
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(body), encoding="utf-8")
    return manifest_path


def test_probe_runner_blocks_when_runner_is_unavailable_without_calling_harness(
    tmp_path, monkeypatch
):
    request_json, payload = _materialize_task3_request(tmp_path)
    _write_runner_gate_manifest(tmp_path, request_json, payload)
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
            REDACTED_REQUEST_PROMPT,
        ],
        "type": "hermes",
        "available": False,
        "returncode": 127,
        "blocker": "runner_unavailable",
    }
    assert "resume" not in result["command"]
    assert calls == []


def test_probe_runner_blocks_without_explicit_gate_manifest_even_if_multiple_requests_exist(
    tmp_path, monkeypatch
):
    _materialize_task3_request(tmp_path, application_id="canary-app", run_id="run-canary-a")
    _materialize_task3_request(tmp_path, application_id="other-app", run_id="run-canary-b")
    calls: list[dict[str, object]] = []

    def blocked_harness(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("probe_runner must not select an arbitrary request")

    monkeypatch.setattr(
        "career.services.canary_control.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        blocked_harness,
    )

    result = probe_runner(_runner_config(), tmp_path)

    assert result["status"] == "blocked"
    assert result["blocker"] == "d3_gate_manifest_missing"
    assert "resume" not in result["command"]
    assert calls == []


def test_probe_runner_requires_explicit_d0_d1_d2_approvals_before_harness(
    tmp_path, monkeypatch
):
    request_json, payload = _materialize_task3_request(tmp_path)
    _write_runner_gate_manifest(tmp_path, request_json, payload, d1_approved=False)
    calls: list[dict[str, object]] = []

    def blocked_harness(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("probe_runner must not call HarnessSupervisor without D0-D2 approval")

    monkeypatch.setattr(
        "career.services.canary_control.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        blocked_harness,
    )

    result = probe_runner(_runner_config(), tmp_path)

    assert result["status"] == "blocked"
    assert result["blocker"] == "d3_approvals_missing"
    assert calls == []


def test_probe_runner_blocks_when_d2_request_incomplete(tmp_path, monkeypatch):
    request_json, payload = _materialize_task3_request(tmp_path)
    _write_runner_gate_manifest(tmp_path, request_json, payload, write_allowlist=[])
    calls: list[dict[str, object]] = []

    def blocked_harness(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("probe_runner must not call HarnessSupervisor with incomplete D2 evidence")

    monkeypatch.setattr(
        "career.services.canary_control.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        blocked_harness,
    )

    result = probe_runner(_runner_config(), tmp_path)

    assert result["status"] == "blocked"
    assert result["blocker"] == "d2_request_incomplete"
    assert calls == []


def test_probe_runner_uses_explicit_d2_binding_and_ignores_other_requests(tmp_path, monkeypatch):
    request_json, payload = _materialize_task3_request(tmp_path, application_id="canary-app", run_id="run-a")
    _materialize_task3_request(tmp_path, application_id="other-app", run_id="run-b")
    _write_runner_gate_manifest(tmp_path, request_json, payload)
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


def test_probe_runner_blocks_when_explicit_d2_hash_mismatches(tmp_path, monkeypatch):
    request_json, payload = _materialize_task3_request(tmp_path)
    _write_runner_gate_manifest(tmp_path, request_json, payload, request_hash="wrong-hash")
    calls: list[dict[str, object]] = []

    def blocked_harness(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("probe_runner must not call HarnessSupervisor on D2 mismatch")

    monkeypatch.setattr(
        "career.services.canary_control.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        blocked_harness,
    )

    result = probe_runner(_runner_config(), tmp_path)

    assert result["status"] == "blocked"
    assert result["blocker"] == "d2_request_mismatch"
    assert calls == []


def test_runner_probe_cli_returns_blocked_json_and_non_zero(monkeypatch, capsys, tmp_path):
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_text("services: {}\n", encoding="utf-8")
    expected = {
        "status": "blocked",
        "command": ["hermes", "--accept-hooks", "-z", "fresh only"],
        "type": "hermes",
        "available": False,
        "returncode": 127,
        "blocker": "runner_unavailable",
    }
    monkeypatch.setattr(
        phase_d_canary,
        "resolve_target_from_compose",
        lambda **kwargs: SimpleNamespace(workspace_root=tmp_path),
    )
    monkeypatch.setattr(
        phase_d_canary,
        "probe_runner",
        lambda runner_config, root, gate_manifest_path=None: expected,
    )

    exit_code = phase_d_canary.main(
        ["runner-probe", "--compose", str(compose_path), "--bot", "vagas_bot_01", "--json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == expected


def test_runner_probe_cli_returns_compact_json_and_zero_for_completed(monkeypatch, capsys, tmp_path):
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_text("services: {}\n", encoding="utf-8")
    expected = {
        "status": "completed",
        "command": ["/usr/bin/hermes", "--accept-hooks", "-z", "fresh only"],
        "type": "hermes",
        "available": True,
        "returncode": 0,
        "blocker": None,
    }
    monkeypatch.setattr(
        phase_d_canary,
        "resolve_target_from_compose",
        lambda **kwargs: SimpleNamespace(workspace_root=tmp_path),
    )
    monkeypatch.setattr(
        phase_d_canary,
        "probe_runner",
        lambda runner_config, root, gate_manifest_path=None: expected,
    )

    exit_code = phase_d_canary.main(
        ["runner-probe", "--compose", str(compose_path), "--bot", "vagas_bot_01", "--json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected
