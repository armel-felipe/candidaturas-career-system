import hashlib
import json
from pathlib import Path

import pytest

from career.cells.capabilities import CapabilitySet
from career.cells.contracts import CELL_CONTRACTS
from career.cells.executor import CellExecutor
from career.cells.handlers import CellExecutionContext, CellOutput, ValidatorResult, production_handler_registry
from career.services.application_context import paths_for
from career.services.database import Database
from career.services.delivery import CanonicalDeliveryCellAdapter
from career.services.notion import NotionCellAdapter


class FakeNotion:
    def __init__(self):
        self.mutation_count = 0
        self.requests = []

    def sync_cell(self, request):
        self.mutation_count += 1
        self.requests.append(dict(request))
        return {"page_id": "page-123", "url": "https://notion.so/page-123"}


class FakeDelivery:
    def __init__(self):
        self.delivery_count = 0

    def deliver_cell(self, request, artifact):
        self.delivery_count += 1
        return {"delivery_id": "delivery-123", "url": "https://files.example/cv.docx"}


def _context(tmp_path, node_id, files):
    paths = paths_for("app-1", root=tmp_path / "applications")
    staging = paths.cells_dir / node_id / "1" / "staging"
    receipt_cache = paths.cells_dir / node_id / "receipts" / "run-1"
    staging.mkdir(parents=True)
    inputs = {}
    for name, content in files.items():
        path = paths.app_dir / "inputs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        inputs[name] = {"path": str(path), "sha256": hashlib.sha256(content).hexdigest()}
    return CellExecutionContext(
        application_id="app-1",
        run_id="run-1",
        node_id=node_id,
        attempt=1,
        paths=paths,
        manifest_path=paths.cells_dir / node_id / "1" / "manifest.json",
        staging_dir=staging,
        inputs=inputs,
        output_paths=(),
        capabilities=CapabilitySet(
            application_root=paths.app_dir,
            read_paths=[paths.app_dir],
            write_paths=[staging, receipt_cache],
        ),
        repair_scope="test",
    )


def test_repeated_notion_final_sync_reuses_matching_receipt_without_second_mutation(tmp_path):
    fake_notion = FakeNotion()
    context = _context(
        tmp_path,
        "sync_notion_final",
        {"review_feras:feras_review.json": b'{"approved": true}'},
    )
    handler = production_handler_registry(notion_client=fake_notion)["sync_notion_final"]

    first = handler(context)
    second = handler(context)
    first_receipt = json.loads(first.artifacts["notion_final_receipt.json"])
    second_receipt = json.loads(second.artifacts["notion_final_receipt.json"])

    assert first_receipt["request_hash"] == second_receipt["request_hash"]
    assert fake_notion.mutation_count == 1
    assert first_receipt["operation"] == "notion_final_sync"
    assert first_receipt["page_id"] == "page-123"
    assert first_receipt["url"] == "https://notion.so/page-123"
    assert first_receipt["application_id"] == "app-1"
    assert first_receipt["run_id"] == "run-1"
    assert first_receipt["node_id"] == "sync_notion_final"
    assert len(json.dumps(first_receipt, sort_keys=True).encode("utf-8")) <= 2048


def test_notion_final_never_passes_docx_to_text_only_extra_artifacts(tmp_path):
    fake_notion = FakeNotion()
    context = _context(
        tmp_path,
        "sync_notion_final",
        {
            "review_cv:approved_cv_manifest.json": b'{"application_id": "app-1"}',
            "render_cv:cv.docx": b"PK\x03\x04not-text",
            "review_feras:feras_review.json": b'{"approved": true}',
        },
    )

    production_handler_registry(notion_client=fake_notion)["sync_notion_final"](context)

    assert fake_notion.mutation_count == 1
    assert all(not str(path).endswith(".docx") for path in fake_notion.requests[0]["extra_artifacts"])


def test_repeated_cv_delivery_reuses_artifact_hash_receipt_and_declares_canonical_lock(tmp_path):
    fake_delivery = FakeDelivery()
    context = _context(
        tmp_path,
        "deliver_cv",
        {
            "review_cv:approved_cv_manifest.json": b'{"application_id": "app-1", "approved_for_delivery": true}',
            "render_cv:cv.docx": b"PK\x03\x04a-cellular-docx",
        },
    )
    approval_path = Path(context.inputs["review_cv:approved_cv_manifest.json"]["path"])
    docx_path = Path(context.inputs["render_cv:cv.docx"]["path"])
    approval_path.write_text(json.dumps({
        "application_id": "app-1", "approved_for_delivery": True,
        "artifact_path": str(docx_path), "artifact_sha256": hashlib.sha256(docx_path.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    context.inputs["review_cv:approved_cv_manifest.json"]["sha256"] = hashlib.sha256(approval_path.read_bytes()).hexdigest()
    handler = production_handler_registry(delivery_client=fake_delivery)["deliver_cv"]

    first = handler(context)
    second = handler(context)
    receipt = json.loads(first.artifacts["cv_delivery_receipt.json"])

    assert json.loads(second.artifacts["cv_delivery_receipt.json"])["request_hash"] == receipt["request_hash"]
    assert fake_delivery.delivery_count == 1
    assert receipt["artifact_hash"] == hashlib.sha256(b"PK\x03\x04a-cellular-docx").hexdigest()
    assert receipt["target"] == "onedrive-cv"
    assert CELL_CONTRACTS["deliver_cv"].resources == ("delivery:onedrive-cv",)


def test_delivery_rejects_approval_manifest_for_a_different_docx_hash(tmp_path):
    context = _context(
        tmp_path,
        "deliver_cv",
        {
            "review_cv:approved_cv_manifest.json": json.dumps(
                {
                    "application_id": "app-1",
                    "approved_for_delivery": True,
                    "artifact_path": "/wrong/cv.docx",
                    "artifact_sha256": "0" * 64,
                }
            ).encode(),
            "render_cv:cv.docx": b"PK\x03\x04actual-docx",
        },
    )

    with pytest.raises(ValueError, match="exact DOCX"):
        production_handler_registry(delivery_client=FakeDelivery())["deliver_cv"](context)


def test_initial_notion_sync_is_idempotent_and_uses_declared_target_status(tmp_path):
    fake_notion = FakeNotion()
    context = _context(
        tmp_path,
        "sync_notion_initial",
        {
            "application_identity": b'{"application_id":"app-1","target_status":"Preliminary review"}',
            "analyze_fit:fit_map.json": b'{"application_id":"app-1"}',
        },
    )
    handler = production_handler_registry(notion_client=fake_notion)["sync_notion_initial"]

    first = handler(context)
    second = handler(context)

    assert fake_notion.mutation_count == 1
    assert fake_notion.requests[0]["status"] == "Preliminary review"
    assert json.loads(first.artifacts["notion_initial_receipt.json"])["request_hash"] == json.loads(second.artifacts["notion_initial_receipt.json"])["request_hash"]


def test_default_production_clients_are_lazy_adapters_with_explicit_preflight(monkeypatch):
    registry = production_handler_registry()

    assert registry["sync_notion_initial"].__closure__
    assert isinstance(NotionCellAdapter(), NotionCellAdapter)
    assert isinstance(CanonicalDeliveryCellAdapter(), CanonicalDeliveryCellAdapter)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_APPLICATIONS_DATABASE_ID", raising=False)
    with pytest.raises(RuntimeError, match="Notion.*preflight"):
        NotionCellAdapter(env={}).preflight()


def test_executor_delivery_uses_exact_rendered_docx_and_review_manifest(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    paths = paths_for("app-1", root=tmp_path / "applications")
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text("job", encoding="utf-8")
    fake_delivery = FakeDelivery()

    def handler(context):
        outputs = {
            "normalize_job": {"job_normalized.json": b"{}", "handover_summary.json": b"{}", "evidence_index.json": b"{}"},
            "analyze_fit": {"fit_map.json": b"{}"},
            "compose_cv": {"cv_content.json": b"{}"},
            "render_cv": {"cv.docx": b"PK\x03\x04rendered"},
        }
        if context.node_id == "review_cv":
            docx = context.inputs["render_cv:cv.docx"]
            approval = {
                "application_id": context.application_id, "approved_for_delivery": True,
                "artifact_path": docx["path"], "artifact_sha256": docx["sha256"],
            }
            return CellOutput(artifacts={
                "cv_review.json": b"{}", "polish_review.json": b"{}",
                "approved_cv_manifest.json": json.dumps(approval).encode(), "keyword_ats_registry.json": b"{}",
            })
        return CellOutput(artifacts=outputs[context.node_id])

    def validator(context, _output):
        report = context.paths.reviews_dir / f"{context.node_id}-{context.validator_command}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        return ValidatorResult.passed(context.validator_command, report)

    handlers = {name: handler for name in ("normalize_job", "analyze_fit", "compose_cv", "render_cv", "review_cv")}
    handlers["deliver_cv"] = production_handler_registry(delivery_client=fake_delivery)["deliver_cv"]
    validators = {command: validator for command in (
        "context:validate", "validate:fit-map", "validate:fit-map:quality", "validate-provenance",
        "cv:validate-content", "validate-cv-provenance", "validate:docx", "cv:approve", "validate-delivery-receipt",
    )}
    executor = CellExecutor(database, applications_root=tmp_path / "applications", handlers=handlers, validators=validators)
    try:
        plan = executor.plan("app-1", {"cv"})
        while executor.node_status(plan.run_id, "deliver_cv") not in {"validated", "blocked"}:
            assert executor.run_ready(plan.run_id)
        assert executor.node_status(plan.run_id, "deliver_cv") == "validated"
        assert fake_delivery.delivery_count == 1
    finally:
        database.close()
