#!/usr/bin/env python3
"""Run the Phase C controlled cellular pilot in an explicit workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from career.cells.contracts import CELL_CONTRACTS
from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career.services import applications_v2
from career.services.application_context import paths_for
from career.services.cell_store import CellStore
from career.services.database import Database
from career.services.harness_supervisor import HarnessSupervisor
from career.utils import read_json, sha256_file, write_json

DEFAULT_APPLICATION_ID = "phase-c-pilot"
DEFAULT_RUN_ID = "run_phase_c_pilot"
DEFAULT_RUNNER_KIND = "controlled"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Phase C cellular pilot")
    parser.add_argument("--workspace", required=True, type=Path)
    return parser.parse_args()


def _pilot_token(application_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", application_id).strip("_") or "pilot"


def _pilot_metadata(application_id: str) -> dict[str, str]:
    if application_id == DEFAULT_APPLICATION_ID:
        return {
            "run_id": DEFAULT_RUN_ID,
            "control_owner": "phase-c-pilot-owner",
            "workspace_owner": "phase-c-pilot-worker",
            "worker_id": "phase-c-pilot-executor",
            "result_name": "phase_c_pilot_result.json",
        }
    token = _pilot_token(application_id)
    return {
        "run_id": f"run_{token}",
        "control_owner": f"{application_id}-owner",
        "workspace_owner": f"{application_id}-worker",
        "worker_id": f"{application_id}-executor",
        "result_name": f"{token}_result.json",
    }


def _prepare_state_root(
    workspace: Path,
    *,
    control_db_path: Path | None,
    authority_ledger_path: Path | None,
) -> tuple[Path, Path, Path]:
    state_dir = workspace / ".career-state"
    if (control_db_path is None) != (authority_ledger_path is None):
        raise ValueError(
            "control_db_path and authority_ledger_path must be provided together"
        )
    if control_db_path is None and authority_ledger_path is None:
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir, state_dir / "career.db", state_dir / "authority.json"

    db_path = Path(control_db_path).resolve()
    ledger_path = Path(authority_ledger_path).resolve()
    if db_path.name != "career.db" or ledger_path.name != "authority.json":
        raise ValueError(
            "canonical canary authority paths must end with career.db and authority.json"
        )
    db_root = db_path.parent
    ledger_root = ledger_path.parent
    if db_root != ledger_root:
        raise ValueError(
            "workspace requires control_db_path and authority_ledger_path under one state root"
        )
    db_root.mkdir(parents=True, exist_ok=True)
    if state_dir.exists() or state_dir.is_symlink():
        if state_dir.resolve() != db_root:
            raise ValueError(
                "workspace .career-state conflicts with the authoritative canary state root"
            )
    elif db_root == state_dir:
        state_dir.mkdir(parents=True, exist_ok=True)
    else:
        state_dir.parent.mkdir(parents=True, exist_ok=True)
        state_dir.symlink_to(db_root, target_is_directory=True)
    return state_dir, db_path, ledger_path


def run_pilot(
    workspace: Path,
    application_id: str = DEFAULT_APPLICATION_ID,
    *,
    control_db_path: Path | None = None,
    authority_ledger_path: Path | None = None,
) -> dict:
    workspace = workspace.resolve()
    state_dir, db_path, ledger_path = _prepare_state_root(
        workspace,
        control_db_path=control_db_path,
        authority_ledger_path=authority_ledger_path,
    )
    applications_root = state_dir / "applications_v2"
    app_id = paths_for(application_id, root=applications_root).application_id
    metadata = _pilot_metadata(app_id)
    run_id = metadata["run_id"]
    control_owner = metadata["control_owner"]
    workspace_owner = metadata["workspace_owner"]
    worker_id = metadata["worker_id"]
    runner_kind = DEFAULT_RUNNER_KIND
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
        worker_id=worker_id,
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
        runner_config={"kind": runner_kind, "timeout_minutes": 1},
        workspace_owner=workspace_owner,
        control_db_id=control_db_id,
    )
    if harness_result.get("returncode") != 0 or harness_result.get("isolation", {}).get("status") != "ok":
        raise RuntimeError(f"controlled harness pilot failed: {harness_result}")
    materialized_request = read_json(request_json)
    materialized_request_json = json.dumps(
        materialized_request, sort_keys=True, separators=(",", ":")
    )
    materialized_request_hash = hashlib.sha256(
        materialized_request_json.encode("utf-8")
    ).hexdigest()
    materialized_request_bytes = len(materialized_request_json.encode("utf-8"))

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
    runtime_payload = dict(harness_result.get("runtime") or {})
    if runtime_run:
        runtime_payload.update(dict(runtime_run))
    result = {
        "status": "completed" if execution and execution[0].status == "validated" else "blocked",
        "application_id": app_id,
        "run_id": run_id,
        "runner_kind": runner_kind,
        "request_json": str(request_json),
        "request_cellular": materialized_request.get("cellular"),
        "request_hash": materialized_request_hash,
        "request_bytes": materialized_request_bytes,
        "manifest_path": str(prepared.manifest_path),
        "control_db_path": str(db_path),
        "authority_ledger_path": str(ledger_path),
        "sqlite_counts": counts,
        "harness": harness_result,
        "execution": [item.status for item in execution],
        "runtime": runtime_payload or None,
        "fit_map_draft": str(paths.fit_map_draft),
    }
    write_json(workspace / metadata["result_name"], result)
    database.close()
    return result


if __name__ == "__main__":
    print(json.dumps(run_pilot(_args().workspace), ensure_ascii=False, indent=2, default=str))
