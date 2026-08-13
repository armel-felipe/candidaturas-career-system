from __future__ import annotations

import hashlib
import json

import pytest

from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career.services.agent_requests import CellRequestBuilder
from career.services.cell_store import CellStore
from career.services.database import Database
from career.services.application_context import paths_for
from career.utils import write_json


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    yield database
    database.close()


def _receipt():
    return {"status": "validated", "paths": [], "hashes": {}, "metadata": {}}


def test_attempt_inputs_are_registered_and_hash_checked_before_finish(db, tmp_path):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["capture_source"]})
    reservation = store.reserve_node("run-a", "capture_source", "worker-a")
    source = tmp_path / "source.md"
    source.write_text("vaga", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    result = store.register_attempt_inputs(
        "run-a",
        "capture_source",
        reservation["attempt"],
        {
            "source_description": {
                "path": str(source),
                "sha256": digest,
                "source_kind": "file",
                "required": True,
                "version": "source-v1",
            }
        },
    )

    assert result["count"] == 1
    assert store.validate_attempt_inputs("run-a", "capture_source", reservation["attempt"])["valid"]
    assert db.fetch_one(
        "SELECT input_name, content_hash, version, required FROM cell_inputs"
    ) == {
        "input_name": "source_description",
        "content_hash": digest,
        "version": "source-v1",
        "required": 1,
    }

    source.write_text("alterada", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        store.validate_attempt_inputs("run-a", "capture_source", reservation["attempt"])


def test_request_is_a_bounded_projection_of_persisted_inputs(db, tmp_path):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["capture_source"]})
    reservation = store.reserve_node("run-a", "capture_source", "worker-a")
    source = tmp_path / "source.md"
    source.write_text("vaga", encoding="utf-8")
    store.register_attempt_inputs(
        "run-a",
        "capture_source",
        reservation["attempt"],
        {"source_description": source},
    )

    request = CellRequestBuilder(db).build(
        run_id="run-a", node_id="capture_source", attempt=reservation["attempt"]
    )

    assert request["run_id"] == "run-a"
    assert request["node_id"] == "capture_source"
    assert request["inputs"][0]["input_name"] == "source_description"
    assert "vaga" not in json.dumps(request, ensure_ascii=False)
    assert db.fetch_one(
        "SELECT node_id, attempt, payload_hash FROM cell_requests"
    )["node_id"] == "capture_source"


def test_request_admission_rejects_oversized_projection(db, tmp_path):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["capture_source"]})
    reservation = store.reserve_node("run-a", "capture_source", "worker-a")
    source = tmp_path / "source.md"
    source.write_text("vaga", encoding="utf-8")
    store.register_attempt_inputs(
        "run-a", "capture_source", reservation["attempt"], {"source_description": source}
    )

    with pytest.raises(ValueError, match="exceeds maximum"):
        CellRequestBuilder(db, max_bytes=32).build(
            run_id="run-a", node_id="capture_source", attempt=reservation["attempt"]
        )

    assert db.fetch_one("SELECT COUNT(*) AS count FROM cell_requests") == {"count": 0}


def test_finish_attempt_records_handover_and_validation_receipts_atomically(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["capture_source"]})
    reservation = store.reserve_node("run-a", "capture_source", "worker-a")

    store.register_attempt_inputs("run-a", "capture_source", reservation["attempt"], {})
    store.finish_attempt(
        "run-a",
        "capture_source",
        reservation["attempt"],
        "validated",
        worker_id="worker-a",
        receipt=_receipt(),
        handover={"kind": "capture", "job_fingerprint": "a" * 64},
        validation_receipts=[
            {
                "validator": "validate-source",
                "result": "passed",
                "report_path": "/tmp/report.json",
                "report_sha256": "b" * 64,
            }
        ],
    )

    assert db.fetch_one(
        "SELECT status, payload_hash FROM cell_handovers"
    )["status"] == "validated"
    assert db.fetch_one(
        "SELECT validator, result FROM validation_receipts"
    ) == {"validator": "validate-source", "result": "passed"}
    assert db.fetch_one("SELECT status FROM cell_nodes") == {"status": "validated"}


def test_prepared_input_registration_can_extend_until_handler_start(db, tmp_path):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["capture_source"]})
    reservation = store.reserve_node("run-a", "capture_source", "worker-a")
    store.register_attempt_inputs("run-a", "capture_source", reservation["attempt"], {})
    source = tmp_path / "later.md"
    source.write_text("não deveria entrar", encoding="utf-8")

    assert store.register_attempt_inputs(
        "run-a", "capture_source", reservation["attempt"], {"late": source}
    )["count"] == 1
    assert store.mark_attempt_running(
        "run-a", "capture_source", reservation["attempt"], "worker-a"
    )
    with pytest.raises(ValueError, match="immutable"):
        store.register_attempt_inputs("run-a", "capture_source", reservation["attempt"], {})


def test_finish_attempt_rejects_handover_with_wrong_identity(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["capture_source"]})
    reservation = store.reserve_node("run-a", "capture_source", "worker-a")
    store.register_attempt_inputs("run-a", "capture_source", reservation["attempt"], {})

    with pytest.raises(ValueError, match="handover"):
        store.finish_attempt(
            "run-a",
            "capture_source",
            reservation["attempt"],
            "validated",
            worker_id="worker-a",
            receipt=_receipt(),
            handover={"run_id": "other-run"},
        )

    assert db.fetch_one("SELECT status FROM cell_nodes") == {"status": "reserved"}


def test_executor_persists_projection_before_handler_and_commit_after_validation(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    application_paths = paths_for("app-a", root=tmp_path / "applications")
    application_paths.app_dir.mkdir(parents=True)
    (application_paths.app_dir / "source_input.md").write_text(
        "descrição", encoding="utf-8"
    )
    write_json(
        application_paths.identity,
        {"application_id": "app-a", "source_id": "source-1", "source_type": "paste"},
    )
    observed: list[dict] = []

    def handler(context):
        observed.append(
            {
                "inputs": database.fetch_all("SELECT * FROM cell_inputs"),
                "requests": database.fetch_all("SELECT * FROM cell_requests"),
            }
        )
        return CellOutput(
            artifacts={"job_description.md": "descrição".encode("utf-8")},
            handover={"kind": "source_capture_handover", "run_id": context.run_id},
        )

    def validator(context, output):
        report = context.paths.reviews_dir / "source.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        return ValidatorResult.passed(context.validator_command, report)

    executor = CellExecutor(
        database,
        applications_root=tmp_path / "applications",
        handlers={"capture_source": handler},
        validators={"validate-job-description": validator},
    )
    plan = executor.plan("app-a", {"cv"})

    result = executor.run_ready(plan.run_id)[0]

    assert result.status == "validated"
    assert len(observed) == 1
    assert observed[0]["inputs"]
    assert observed[0]["requests"][0]["node_id"] == "capture_source"
    assert (result.manifest_path.parent / "request.json").is_file()
    assert (result.manifest_path.parent / "request.md").is_file()
    assert database.fetch_one("SELECT status FROM cell_handovers") == {
        "status": "validated"
    }
    assert database.fetch_one(
        "SELECT validator, result, report_sha256 FROM validation_receipts"
    ) == {
        "validator": "validate-job-description",
        "result": "passed",
        "report_sha256": hashlib.sha256(b"{}").hexdigest(),
    }
    assert executor.ready_nodes(plan.run_id) == ("normalize_job",)
    database.close()
