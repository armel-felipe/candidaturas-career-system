import hashlib
import json

import pytest

from career.cells import handlers
from career.cells.capabilities import CapabilitySet
from career.cells.handlers import CellExecutionContext, CellOutput, production_handler_registry, production_validator_registry
from career.services import feras
from career.cells.planner import compile_run_plan
from career.services import cover_letter, habilidades_chave
from career.services.application_context import paths_for
from career.services.notion import NotionCellAdapter


class FakeNotionService:
    def __init__(self):
        self.calls = []

    def create(self, token, database_id, fit_map_path, job_description_path, **kwargs):
        self.calls.append(("create", kwargs))
        return {"page": {"id": "new-page", "url": "https://notion/new-page"}}

    def update(self, token, database_id, record_id, fit_map_path, job_description_path, **kwargs):
        self.calls.append(("update", record_id, kwargs))
        return {"resolved_page_id": "existing-page", "resolved_record_id": record_id, "page": {"url": "https://notion/existing-page"}}


def _context(tmp_path, node_id, files):
    paths = paths_for("app-1", root=tmp_path / "apps")
    staging = paths.cells_dir / node_id / "1" / "staging"
    receipts = paths.cells_dir / node_id / "receipts" / "run-1"
    staging.mkdir(parents=True)
    inputs = {}
    for name, payload in files.items():
        path = paths.app_dir / "inputs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        inputs[name] = {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest()}
    return CellExecutionContext(
        application_id="app-1", run_id="run-1", node_id=node_id, attempt=1,
        paths=paths, manifest_path=staging.parent / "manifest.json", staging_dir=staging,
        inputs=inputs, output_paths=(),
        capabilities=CapabilitySet(
            application_root=paths.app_dir,
            read_paths=[paths.app_dir],
            write_paths=[staging, receipts, paths.reviews_dir],
        ),
        repair_scope="test",
    )


def test_notion_final_plan_requires_fit_initial_receipt_and_selected_reviews(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text("job", encoding="utf-8")

    plan = compile_run_plan("app-1", {"notion", "cv", "feras"}, paths)

    assert plan.dependencies_of("sync_notion_final") == (
        "analyze_fit", "sync_notion_initial", "review_cv", "review_feras"
    )


def test_notion_adapter_updates_existing_and_never_creates_final_without_record(tmp_path):
    fit = tmp_path / "fit.json"
    job = tmp_path / "job.md"
    fit.write_text("{}", encoding="utf-8")
    job.write_text("job", encoding="utf-8")
    fake = FakeNotionService()
    adapter = NotionCellAdapter(service=fake, credentials=("token", "database"))

    existing = adapter.sync_cell({
        "operation": "notion_final_sync", "record_id": "77", "status": "Aplicação andamento",
        "fit_map_path": str(fit), "job_description_path": str(job), "extra_artifacts": [],
    })
    assert existing["page_id"] == "existing-page"
    assert fake.calls == [("update", 77, {"status": "Aplicação andamento", "dry_run": False})]
    created = adapter.sync_cell({
        "operation": "notion_initial_sync", "status": "Aplicação andamento",
        "fit_map_path": str(fit), "job_description_path": str(job), "extra_artifacts": [],
    })
    assert created["page_id"] == "new-page"
    assert fake.calls[-1] == ("create", {"status": "Aplicação andamento", "dry_run": False})
    with pytest.raises(RuntimeError, match="final.*record"):
        adapter.sync_cell({
            "operation": "notion_final_sync", "status": "Aplicação andamento",
            "fit_map_path": str(fit), "job_description_path": str(job), "extra_artifacts": [],
        })


def test_cover_and_habilidades_policy_rejects_empty_semantic_shells():
    with pytest.raises(Exception):
        cover_letter.validate_cellular_artifact("# Carta de Apresentação\n\nOlá")
    with pytest.raises(Exception):
        habilidades_chave.validate_cellular_artifact("# Habilidades-chave\n\n## Habilidades priorizadas\n- liderança")


def test_branch_evidence_uses_selected_normalized_evidence_and_atomic_receipt_write(tmp_path, monkeypatch):
    files = {
        "analyze_fit:fit_map.json": json.dumps({"cargo": "Diretor", "empresa": "Acme", "keywords_para_ats": ["operações"], "historias_selecionadas": {"principal": {"resultado": "reduziu custos"}}}).encode(),
        "normalize_job:job_normalized.json": '{"application_id":"app-1","keywords":["operações"]}'.encode(),
        "normalize_job:handover_summary.json": b'{"application_id":"app-1","job_fingerprint":"job"}',
        "normalize_job:evidence_index.json": b'{"application_id":"app-1","evidence_items":[{"id":"e-1","source":"facts:1","text":"reduziu custos"}]}',
    }
    context = _context(tmp_path, "generate_feras", files)
    output = production_handler_registry()["generate_feras"](context)
    evidence = json.loads(output.artifacts["evidence_index.json"])

    assert evidence["selected_evidence"] == [{"id": "e-1", "source": "facts:1"}]

    notion_context = _context(tmp_path, "sync_notion_initial", {
        "application_identity": b'{"application_id":"app-1"}',
        "analyze_fit:fit_map.json": b'{}',
    })
    replaced = []
    monkeypatch.setattr(handlers.os, "replace", lambda source, target: replaced.append((source, target)))
    production_handler_registry(notion_client=lambda _: {"page_id": "p", "url": "u"})["sync_notion_initial"](notion_context)
    assert replaced


def test_branch_review_validator_rejects_a_forged_hash_receipt(tmp_path):
    fit = {"cargo": "Diretor", "empresa": "Acme", "keywords_para_ats": ["operações"], "historias_selecionadas": {"principal": {"resultado": "reduziu custos"}}}
    content = feras.build_from_fit_map(fit).encode()
    context = _context(tmp_path, "review_feras", {
        "generate_feras:feras.md": content,
        "generate_feras:handover_summary.json": b"{}",
        "generate_feras:evidence_index.json": b"{}",
        "analyze_fit:fit_map.json": json.dumps(fit).encode(),
        "normalize_job:job_normalized.json": b"{}",
        "normalize_job:handover_summary.json": b"{}",
        "normalize_job:evidence_index.json": b"{}",
    })
    review = production_handler_registry()["review_feras"](context)
    forged = json.loads(review.artifacts["feras_review.json"])
    forged["artifact_sha256"] = "0" * 64

    result = production_validator_registry()["review-output:feras"](
        context, CellOutput(artifacts={"feras_review.json": json.dumps(forged).encode()})
    )

    assert result.result == "failed"
