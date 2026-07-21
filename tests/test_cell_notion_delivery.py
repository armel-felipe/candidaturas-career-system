import hashlib
import json
from pathlib import Path

from career.cells.capabilities import CapabilitySet
from career.cells.contracts import CELL_CONTRACTS
from career.cells.handlers import CellExecutionContext, production_handler_registry
from career.services.application_context import paths_for


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
    handler = production_handler_registry(delivery_client=fake_delivery)["deliver_cv"]

    first = handler(context)
    second = handler(context)
    receipt = json.loads(first.artifacts["cv_delivery_receipt.json"])

    assert json.loads(second.artifacts["cv_delivery_receipt.json"])["request_hash"] == receipt["request_hash"]
    assert fake_delivery.delivery_count == 1
    assert receipt["artifact_hash"] == hashlib.sha256(b"PK\x03\x04a-cellular-docx").hexdigest()
    assert receipt["target"] == "onedrive-cv"
    assert CELL_CONTRACTS["deliver_cv"].resources == ("delivery:onedrive-cv",)
