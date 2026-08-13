from __future__ import annotations

import json
import shutil
from pathlib import Path

from career.cells.contracts import CELL_CONTRACTS
from career.services.agent_requests import CellRequestBuilder
from career.services.cell_store import CellStore
from career.services.database import Database
from career.services.harness_supervisor import HarnessSupervisor


def test_harness_runs_controlled_cell_and_records_runtime(tmp_path, monkeypatch):
    root = tmp_path
    app_dir = root / ".career-state" / "applications_v2" / "app-a"
    manifest_path = app_dir / "cells" / "analyze_fit" / "1" / "manifest.json"
    draft_path = app_dir / "fit_map.draft.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "application_id": "app-a",
                "run_id": "run-a",
                "node_id": "analyze_fit",
                "capabilities": {
                    "read_paths": [str(manifest_path)],
                    "write_paths": [str(draft_path)],
                },
            }
        ),
        encoding="utf-8",
    )
    scripts_dir = root / "scripts"
    scripts_dir.mkdir()
    source = Path(__file__).parents[1] / "scripts" / "controlled_agent_worker.py"
    shutil.copy2(source, scripts_dir / source.name)

    db = Database(root / ".career-state" / "career.db")
    db.init_schema()
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["analyze_fit"]})
    reservation = store.reserve_node("run-a", "analyze_fit", "worker-a")
    builder = CellRequestBuilder(db)
    payload = builder.build(
        run_id="run-a",
        node_id="analyze_fit",
        attempt=reservation["attempt"],
        cellular_context={
            "cellular": True,
            "manifest_path": str(manifest_path),
            "read_allowlist": [str(manifest_path)],
            "write_allowlist": [str(draft_path)],
            "objective": "Produce only the FIT_MAP draft.",
        },
    )
    request_json, request_md = builder.materialize(
        payload,
        app_dir / "requests" / "cellular" / "run-a" / "analyze_fit" / "1",
    )
    monkeypatch.setattr(HarnessSupervisor, "_acquire_cellular_workspace", lambda *args, **kwargs: None)

    result = HarnessSupervisor(root).run_application_stage(
        stage="analyze",
        record_key="app-a",
        application_dir=app_dir,
        request_json=request_json,
        request_md=request_md,
        runner_config={"kind": "controlled", "timeout_minutes": 1},
    )

    assert result["returncode"] == 0, result
    assert result["isolation"]["status"] == "ok", json.dumps(result["isolation"], indent=2, default=str)
    assert result["runtime"]["status"] == "completed"
    assert json.loads(draft_path.read_text(encoding="utf-8"))["application_id"] == "app-a"
    runtime_row = db.fetch_one(
        "SELECT status, source FROM runtime_runs WHERE run_id = ?",
        ("run-a",),
    )
    assert runtime_row["status"] == "completed"
    assert runtime_row["source"] == "cellular-harness"
    db.close()
