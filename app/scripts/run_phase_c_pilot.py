#!/usr/bin/env python3
"""Run the Phase C controlled cellular pilot in an explicit workspace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from career.cells.contracts import CELL_CONTRACTS
from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career.services import applications_v2
from career.services.agent_runner import SubprocessAgentRunner
from career.services.application_context import paths_for
from career.services.cell_store import CellStore
from career.services.database import Database
from career.services.harness_supervisor import HarnessSupervisor
from career.utils import read_json, sha256_file, write_json


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Phase C cellular pilot")
    parser.add_argument("--workspace", required=True, type=Path)
    return parser.parse_args()


def run_pilot(workspace: Path) -> dict:
    workspace = workspace.resolve()
    state_dir = workspace / ".career-state"
    applications_root = state_dir / "applications_v2"
    db_path = state_dir / "career.db"
    ledger_path = state_dir / "authority.json"
    app_id = "phase-c-pilot"
    control_owner = "phase-c-pilot-owner"
    workspace_owner = "phase-c-pilot-worker"
    state_dir.mkdir(parents=True, exist_ok=True)
    applications_root.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        {
            "CAREER_CONTROL_DB_PATH": str(db_path),
            "CAREER_AUTHORITY_LEDGER_PATH": str(ledger_path),
            "CAREER_WORKSPACE_OWNER": workspace_owner,
        }
    )

    database = Database(db_path, authority_ledger_path=ledger_path)
    database.prepare_authority_ledger_provisioning()
    control_db_id = database.control_db_identity()
    database.provision_authority_ledger(
        expected_control_db_id=control_db_id, provisioned_by=control_owner
    )
    database.init_schema()
    os.environ["CAREER_CONTROL_DB_ID"] = control_db_id

    paths = paths_for(app_id, root=applications_root)
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    for directory in (
        paths.plans_dir,
        paths.cells_dir,
        paths.artifacts_dir,
        paths.reviews_dir,
        paths.derived_dir,
        paths.requests_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    paths.job_description.write_text(
        "Cargo: Operations Lead\nResponsabilidades: liderar operações.\n",
        encoding="utf-8",
    )
    write_json(
        paths.identity,
        {"kind": "application_identity", "application_id": app_id},
    )

    contract = CELL_CONTRACTS["analyze_fit"]
    run_id = "run_phase_c_pilot"
    node = {
        "node_id": contract.node_id,
        "requires": [],
        "produces": [str(paths.app_dir / "fit_map.json")],
        "validators": list(contract.validators),
        "resources": [],
        "invalidates": list(contract.invalidates),
        "repair_scope": contract.repair_scope,
        "max_attempts": contract.max_attempts,
        "allows_external_effect": False,
        "contract_version": contract.version,
    }
    graph = {
        "run_id": run_id,
        "application_id": app_id,
        "nodes": [node],
        "edges": [],
        "resource_locks": [],
        "created_at": "phase-c-pilot",
        "contract_version": contract.version,
    }
    write_json(paths.plans_dir / f"{run_id}.json", graph)
    CellStore(database).create_run(app_id, run_id, graph=graph)

    def pilot_handler(_context):
        return CellOutput(artifacts={"fit_map.json": json.dumps({"pilot": True})})

    def pilot_validator(context, _output, *, command):
        report_path = context.staging_dir / f"{command}.json"
        report_path.write_text(
            json.dumps({"command": command, "result": "passed"}), encoding="utf-8"
        )
        return ValidatorResult.passed(command, report_path)

    validators = {
        command: (lambda context, output, command=command: pilot_validator(context, output, command=command))
        for command in contract.validators
    }
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={"analyze_fit": pilot_handler},
        validators=validators,
        worker_id="phase-c-pilot-executor",
        workspace_owner=workspace_owner,
        workspace_control_db_id=control_db_id,
        require_authoritative_workspace=True,
    )
    prepared = executor.prepare_ready_node(run_id, "analyze_fit")

    worker_script = workspace / "scripts" / "controlled_agent_worker.py"
    worker_script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).with_name("controlled_agent_worker.py"), worker_script)
    request_json, request_md = applications_v2._write_cellular_analyze_request(
        paths,
        prepared,
        workspace_owner=workspace_owner,
        control_db_id=control_db_id,
    )
    harness_result = HarnessSupervisor(workspace).run_application_stage(
        stage="analyze",
        record_key=app_id,
        application_dir=paths.app_dir,
        request_json=request_json,
        request_md=request_md,
        runner_config={"kind": "controlled", "timeout_minutes": 1},
        workspace_owner=workspace_owner,
        control_db_id=control_db_id,
    )
    if harness_result.get("returncode") != 0 or harness_result.get("isolation", {}).get("status") != "ok":
        raise RuntimeError(f"controlled harness pilot failed: {harness_result}")

    write_json(
        applications_v2._draft_binding_path(paths),
        {
            "kind": "cellular_fit_map_draft_binding",
            "application_id": app_id,
            "run_id": run_id,
            "node_id": "analyze_fit",
            "attempt": prepared.attempt,
            "job_fingerprint": sha256_file(paths.job_description),
            "draft_sha256": sha256_file(paths.fit_map_draft),
            "manifest_path": str(prepared.manifest_path),
        },
    )
    execution = executor.run_ready(run_id)
    runtime_run = database.fetch_one(
        "SELECT runtime_run_id, status, source FROM runtime_runs WHERE run_id = ?",
        (run_id,),
    )
    request_row = database.fetch_one(
        "SELECT payload_hash, payload_bytes FROM cell_requests "
        "WHERE run_id = ? AND node_id = ? AND attempt = ?",
        (run_id, "analyze_fit", prepared.attempt),
    )
    counts = {}
    for table in (
        "cell_inputs",
        "cell_requests",
        "cell_handovers",
        "validation_receipts",
        "runtime_runs",
        "artifacts",
    ):
        counts[table] = int(
            database.fetch_one(
                f"SELECT COUNT(*) AS count FROM {table} WHERE run_id = ?",
                (run_id,),
            )["count"]
        )
    counts["runtime_observations"] = int(
        database.fetch_one(
            "SELECT COUNT(*) AS count FROM runtime_observations o "
            "JOIN runtime_runs r ON r.runtime_run_id = o.runtime_run_id "
            "WHERE r.run_id = ?",
            (run_id,),
        )["count"]
    )
    result = {
        "status": "completed" if execution and execution[0].status == "validated" else "blocked",
        "application_id": app_id,
        "run_id": run_id,
        "request_json": str(request_json),
        "request_cellular": read_json(request_json).get("cellular"),
        "request_hash": request_row["payload_hash"] if request_row else None,
        "request_bytes": request_row["payload_bytes"] if request_row else None,
        "sqlite_counts": counts,
        "harness": harness_result,
        "execution": [item.status for item in execution],
        "runtime": dict(runtime_run) if runtime_run else None,
        "fit_map_draft": str(paths.fit_map_draft),
    }
    write_json(workspace / "phase_c_pilot_result.json", result)
    database.close()
    return result


if __name__ == "__main__":
    print(json.dumps(run_pilot(_args().workspace), ensure_ascii=False, indent=2, default=str))
