from __future__ import annotations

import json
import sys

from career.services.agent_runner import AgentRunRequest, SubprocessAgentRunner


def test_controlled_runner_is_a_fresh_request_only_command(tmp_path):
    request_md = tmp_path / "request.md"
    request_md.write_text("# request\n", encoding="utf-8")
    command = SubprocessAgentRunner(tmp_path).build_command(
        AgentRunRequest(
            stage="analyze",
            record_key="app-a",
            request_path=request_md,
            instruction="ignored",
            runner_config={"kind": "controlled"},
        )
    )

    assert command[:2] == [sys.executable, str(tmp_path / "scripts" / "controlled_agent_worker.py")]
    assert command[-1] == str(tmp_path / "request.json")
    assert "resume" not in command


def test_controlled_runner_writes_only_the_declared_fit_map_output(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    source_script = (
        __import__("pathlib").Path(__file__).parents[1]
        / "scripts"
        / "controlled_agent_worker.py"
    )
    (scripts_dir / "controlled_agent_worker.py").write_text(
        source_script.read_text(encoding="utf-8"), encoding="utf-8"
    )
    draft = tmp_path / "application" / "fit_map.draft.json"
    manifest = tmp_path / "application" / "cells" / "analyze_fit" / "1" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    request_json = tmp_path / "request.json"
    request_md = tmp_path / "request.md"
    request_json.write_text(
        json.dumps(
            {
                "cellular": True,
                "application_id": "app-a",
                "run_id": "run-a",
                "node_id": "analyze_fit",
                "attempt": 1,
                "manifest_path": str(manifest),
                "write_allowlist": [str(draft)],
            }
        ),
        encoding="utf-8",
    )
    request_md.write_text("# request\n", encoding="utf-8")

    result = SubprocessAgentRunner(tmp_path).run(
        AgentRunRequest(
            stage="analyze",
            record_key="app-a",
            request_path=request_md,
            instruction="ignored",
            runner_config={"kind": "controlled", "timeout_minutes": 1},
        )
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(draft.read_text(encoding="utf-8"))["run_id"] == "run-a"


def test_controlled_runner_rejects_output_outside_application(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    source_script = __import__("pathlib").Path(__file__).parents[1] / "scripts" / "controlled_agent_worker.py"
    (scripts_dir / "controlled_agent_worker.py").write_text(
        source_script.read_text(encoding="utf-8"), encoding="utf-8"
    )
    manifest = tmp_path / "application" / "cells" / "analyze_fit" / "1" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    request_json = tmp_path / "request.json"
    request_md = tmp_path / "request.md"
    request_json.write_text(
        json.dumps(
            {
                "cellular": True,
                "application_id": "app-a",
                "run_id": "run-a",
                "node_id": "analyze_fit",
                "attempt": 1,
                "manifest_path": str(manifest),
                "write_allowlist": [str(tmp_path / "outside" / "fit_map.draft.json")],
            }
        ),
        encoding="utf-8",
    )
    request_md.write_text("# request\n", encoding="utf-8")

    result = SubprocessAgentRunner(tmp_path).run(
        AgentRunRequest(
            stage="analyze",
            record_key="app-a",
            request_path=request_md,
            instruction="ignored",
            runner_config={"kind": "controlled", "timeout_minutes": 1},
        )
    )

    assert result.returncode != 0
    assert not (tmp_path / "outside" / "fit_map.draft.json").exists()
