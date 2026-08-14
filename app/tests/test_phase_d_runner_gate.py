from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from career.services.canary_control import CanaryTarget, REDACTED_REQUEST_PROMPT, probe_runner
from scripts import phase_d_canary


def _runner_config() -> dict[str, object]:
    return {
        "kind": "hermes",
        "command": "hermes",
        "agent": "build",
        "timeout_minutes": 90,
    }


def _canary_target(root: Path) -> CanaryTarget:
    profile_root = root / "profiles" / "vagas_bot_01"
    profile_root.mkdir(parents=True, exist_ok=True)
    workspace_root = root.resolve()
    return CanaryTarget(
        bot_name="vagas_bot_01",
        compose_service="vagas_bot_01",
        hermes_config=profile_root / "config.yaml",
        adapter_script=workspace_root / "scripts" / "telegram_harness_adapter.py",
        control_db_path=workspace_root / ".career-state" / "career.db",
        authority_ledger_path=workspace_root / ".career-state" / "authority.json",
        workspace_root=workspace_root,
        compose_path=workspace_root / "compose.yaml",
    )


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
    manifest_kind: str = "phase_d_runner_gate_manifest",
    manifest_version: int = 1,
    d0_approved: bool = True,
    d1_approved: bool = True,
    d2_approved: bool = True,
    d0_status: str | None = None,
    d1_status: str | None = None,
    d2_status: str | None = None,
    request_hash: str | None = None,
    read_allowlist: list[str] | None = None,
    write_allowlist: list[str] | None = None,
) -> Path:
    manifest_path = root / ".career-state" / "phase_d_runner_gate.json"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    body = {
        "kind": manifest_kind,
        "version": manifest_version,
        "target": "vagas_bot_01",
        "approvals": {
            "d0": {
                "kind": "phase_d_gate_evidence",
                "version": 1,
                "gate": "d0",
                "approved": d0_approved,
                "status": d0_status or ("ready" if d0_approved else "blocked"),
                "evidence_path": str(root / ".career-state" / "phase_d_gates" / "d0_preflight.json"),
                "evidence_hash": "stub-d0",
            },
            "d1": {
                "kind": "phase_d_gate_evidence",
                "version": 1,
                "gate": "d1",
                "approved": d1_approved,
                "status": d1_status or ("dry_run_ok" if d1_approved else "blocked"),
                "evidence_path": str(root / ".career-state" / "phase_d_gates" / "d1_stage_hook.json"),
                "evidence_hash": "stub-d1",
            },
            "d2": {
                "kind": "phase_d_gate_evidence",
                "version": 1,
                "gate": "d2",
                "approved": d2_approved,
                "status": d2_status or ("completed" if d2_approved else "blocked"),
                "evidence_path": str(root / ".career-state" / "phase_d_gates" / "d2_controlled_run.json"),
                "evidence_hash": "stub-d2",
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
    evidence_dir = root / ".career-state" / "phase_d_gates"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_payloads = {
        "d0_preflight.json": {
            "kind": "phase_d_gate_evidence",
            "version": 1,
            "gate": "d0",
            "target": "vagas_bot_01",
            "approved": body["approvals"]["d0"]["approved"],
            "status": body["approvals"]["d0"]["status"],
            "result": {"status": body["approvals"]["d0"]["status"]},
        },
        "d1_stage_hook.json": {
            "kind": "phase_d_gate_evidence",
            "version": 1,
            "gate": "d1",
            "target": "vagas_bot_01",
            "approved": body["approvals"]["d1"]["approved"],
            "status": body["approvals"]["d1"]["status"],
            "result": {"status": body["approvals"]["d1"]["status"]},
        },
        "d2_controlled_run.json": {
            "kind": "phase_d_gate_evidence",
            "version": 1,
            "gate": "d2",
            "target": "vagas_bot_01",
            "approved": body["approvals"]["d2"]["approved"],
            "status": body["approvals"]["d2"]["status"],
            "result": {
                "status": body["approvals"]["d2"]["status"],
                "application_id": payload["application_id"],
                "run_id": payload["run_id"],
                "node_id": payload["node_id"],
                "attempt": payload["attempt"],
                "request_json": str(request_json),
                "request_md": str(request_json.with_suffix(".md")),
                "request_hash": body["approvals"]["d2"]["request_hash"],
                "read_allowlist": list(
                    read_allowlist if read_allowlist is not None else payload["read_allowlist"]
                ),
                "write_allowlist": list(
                    write_allowlist if write_allowlist is not None else payload["write_allowlist"]
                ),
            },
        },
    }
    for name, evidence in evidence_payloads.items():
        evidence_path = evidence_dir / name
        serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        body["approvals"][evidence["gate"]]["evidence_hash"] = hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
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

    result = probe_runner(_canary_target(tmp_path), _runner_config())

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

    result = probe_runner(_canary_target(tmp_path), _runner_config())

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

    result = probe_runner(_canary_target(tmp_path), _runner_config())

    assert result["status"] == "blocked"
    assert result["blocker"] == "d3_approvals_missing"
    assert calls == []


def test_probe_runner_blocks_when_manifest_approval_status_is_contradictory(
    tmp_path, monkeypatch
):
    request_json, payload = _materialize_task3_request(tmp_path)
    _write_runner_gate_manifest(
        tmp_path,
        request_json,
        payload,
        d0_approved=True,
        d0_status="blocked",
    )
    calls: list[dict[str, object]] = []

    def blocked_harness(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("probe_runner must not call HarnessSupervisor on contradictory approvals")

    monkeypatch.setattr(
        "career.services.canary_control.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        blocked_harness,
    )

    result = probe_runner(_canary_target(tmp_path), _runner_config())

    assert result["status"] == "blocked"
    assert result["blocker"] == "d3_approvals_incoherent"
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

    result = probe_runner(_canary_target(tmp_path), _runner_config())

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

    result = probe_runner(_canary_target(tmp_path), _runner_config())

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


def test_probe_runner_rejects_noncanonical_manifest_kind_and_version(tmp_path, monkeypatch):
    request_json, payload = _materialize_task3_request(tmp_path)
    _write_runner_gate_manifest(
        tmp_path,
        request_json,
        payload,
        manifest_kind="wrong_kind",
        manifest_version=9,
    )
    calls: list[dict[str, object]] = []

    def blocked_harness(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("probe_runner must not call HarnessSupervisor with invalid gate manifest")

    monkeypatch.setattr(
        "career.services.canary_control.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        blocked_harness,
    )

    result = probe_runner(_canary_target(tmp_path), _runner_config())

    assert result["status"] == "blocked"
    assert result["blocker"] == "d3_gate_manifest_invalid"
    assert calls == []


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

    result = probe_runner(_canary_target(tmp_path), _runner_config())

    assert result["status"] == "blocked"
    assert result["blocker"] == "d2_request_mismatch"
    assert calls == []


def test_probe_runner_rejects_controlled_runner_kind_without_calling_harness(
    tmp_path, monkeypatch
):
    request_json, payload = _materialize_task3_request(tmp_path)
    _write_runner_gate_manifest(tmp_path, request_json, payload)
    calls: list[dict[str, object]] = []

    def blocked_harness(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("probe_runner must not call HarnessSupervisor for controlled runner probes")

    monkeypatch.setattr(
        "career.services.canary_control.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.HarnessSupervisor.run_application_stage",
        blocked_harness,
    )

    result = probe_runner(
        _canary_target(tmp_path),
        {
            "kind": "controlled",
            "command": "controlled",
            "timeout_minutes": 1,
        },
    )

    assert result["status"] == "blocked"
    assert result["blocker"] == "runner_kind_unsupported"
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
        lambda target, runner_config, gate_manifest_path=None: expected,
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
        lambda target, runner_config, gate_manifest_path=None: expected,
    )

    exit_code = phase_d_canary.main(
        ["runner-probe", "--compose", str(compose_path), "--bot", "vagas_bot_01", "--json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected
