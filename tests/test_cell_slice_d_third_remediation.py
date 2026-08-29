import hashlib
import json

import pytest

from career.cells.capabilities import CapabilitySet
from career.cells.handlers import CellExecutionContext, production_handler_registry
from career.services.application_context import paths_for
from career.services.notion import NotionCellAdapter
from career.utils import ValidationFailure, read_json, write_json


class FakeLegacyNotionService:
    def __init__(self):
        self.calls = []

    def create(self, token, database_id, fit_map_path, job_description_path, **kwargs):
        self.calls.append(("create", kwargs))
        return {"page": {"id": "f4f7ad7e-2f21-4f5e-aab8-4d129d2a67ab", "url": "https://notion/new"}}

    def update(self, token, database_id, record_id, fit_map_path, job_description_path, **kwargs):
        self.calls.append(("update-record", record_id, kwargs))
        return {"resolved_page_id": "page-for-record", "resolved_record_id": record_id, "page": {"url": "https://notion/record"}}

    def update_page(self, token, database_id, page_id, fit_map_path, job_description_path, **kwargs):
        self.calls.append(("update-page", page_id, kwargs))
        return {"page": {"id": page_id, "url": "https://notion/existing"}}


def _context(tmp_path, node_id, files, *, application_id="app-real"):
    paths = paths_for(application_id, root=tmp_path / "applications")
    staging = paths.cells_dir / node_id / "1" / "staging"
    receipts = paths.cells_dir / node_id / "receipts" / "run-real"
    staging.mkdir(parents=True, exist_ok=True)
    inputs = {}
    for name, payload in files.items():
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        path = paths.app_dir / "inputs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        inputs[name] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    return CellExecutionContext(
        application_id=application_id,
        run_id="run-real",
        node_id=node_id,
        attempt=1,
        paths=paths,
        manifest_path=staging.parent / "manifest.json",
        staging_dir=staging,
        inputs=inputs,
        output_paths=(),
        capabilities=CapabilitySet(
            application_root=paths.app_dir,
            read_paths=[paths.app_dir],
            write_paths=[staging, receipts, paths.reviews_dir, paths.derived_dir],
        ),
        repair_scope="test",
    )


def _real_normalized_outputs(tmp_path):
    application_id = "app-real"
    paths = paths_for(application_id, root=tmp_path / "applications")
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    write_json(paths.identity, {
        "kind": "application_identity", "application_id": application_id,
        "company": "Acme", "role": "Diretor de Operações", "source_type": "pasted_text",
    })
    source = """# Diretor de Operações
Empresa: Acme
## Sobre a vaga
Liderar operações, planejamento e análise de dados com melhoria contínua.
## Responsabilidades
- Conduzir operações e indicadores para decisões executivas.
## Requisitos
- Experiência em operações, planejamento e dados.
""".encode("utf-8")
    paths.job_description.write_bytes(source)
    output = production_handler_registry()["normalize_job"](
        _context(tmp_path, "normalize_job", {"capture_source:job_description.md": source})
    )
    return paths, output.artifacts


def _fit_map(application_id, terms):
    return {
        "cargo": "Diretor de Operações",
        "empresa": "Acme",
        "keywords_para_ats": terms,
        "keywords_habilidade_ats": [{"keyword": term} for term in terms],
        "historias_selecionadas": {"principal": {"resultado": "reduziu custos em 13%"}},
    }


def _branch_inputs(normalized, fit_map):
    return {
        "analyze_fit:fit_map.json": fit_map,
        "normalize_job:job_normalized.json": normalized["job_normalized.json"],
        "normalize_job:handover_summary.json": normalized["handover_summary.json"],
        "normalize_job:evidence_index.json": normalized["evidence_index.json"],
    }


def test_connected_notion_uuid_create_is_updated_by_page_id_without_duplicate(tmp_path):
    fit = tmp_path / "fit.json"
    job = tmp_path / "job.md"
    fit.write_text("{}", encoding="utf-8")
    job.write_text("job", encoding="utf-8")
    service = FakeLegacyNotionService()
    adapter = NotionCellAdapter(service=service, credentials=("token", "database"))

    initial = adapter.sync_cell({
        "operation": "notion_initial_sync", "status": "Aplicação andamento",
        "fit_map_path": str(fit), "job_description_path": str(job), "extra_artifacts": [],
    })
    final = adapter.sync_cell({
        "operation": "notion_final_sync", "status": "Aplicação andamento",
        "page_id": initial["page_id"], "fit_map_path": str(fit),
        "job_description_path": str(job), "extra_artifacts": [],
    })

    assert initial == {"page_id": "f4f7ad7e-2f21-4f5e-aab8-4d129d2a67ab", "record_id": "", "url": "https://notion/new"}
    assert final["page_id"] == initial["page_id"]
    assert service.calls == [
        ("create", {"status": "Aplicação andamento", "dry_run": False}),
        ("update-page", initial["page_id"], {"status": "Aplicação andamento", "dry_run": False}),
    ]


def test_notion_numeric_record_id_still_uses_record_update(tmp_path):
    fit = tmp_path / "fit.json"
    job = tmp_path / "job.md"
    fit.write_text("{}", encoding="utf-8")
    job.write_text("job", encoding="utf-8")
    service = FakeLegacyNotionService()
    adapter = NotionCellAdapter(service=service, credentials=("token", "database"))

    receipt = adapter.sync_cell({
        "operation": "notion_final_sync", "status": "Aplicação andamento", "record_id": "77",
        "fit_map_path": str(fit), "job_description_path": str(job), "extra_artifacts": [],
    })

    assert receipt == {"page_id": "page-for-record", "record_id": "77", "url": "https://notion/record"}
    assert service.calls == [("update-record", 77, {"status": "Aplicação andamento", "dry_run": False})]


def test_synthetic_application_id_is_not_used_as_initial_notion_page(tmp_path):
    requests = []

    def fake_notion(request):
        requests.append(request)
        return {
            "page_id": "f4f7ad7e-2f21-4f5e-aab8-4d129d2a67ab",
            "url": "https://notion/new",
        }

    context = _context(tmp_path, "sync_notion_initial", {
        "application_identity": {
            "application_id": "app-real",
            "aliases": {
                "notion_page_id": "local_20260827_jobgether_abc123",
            },
        },
        "analyze_fit:fit_map.json": {},
    })
    result = production_handler_registry(notion_client=fake_notion)[
        "sync_notion_initial"
    ](context)

    receipt = json.loads(result.artifacts["notion_initial_receipt.json"])
    assert receipt["page_id"] == "f4f7ad7e-2f21-4f5e-aab8-4d129d2a67ab"
    assert requests[0]["page_id"] == ""
    assert requests[0]["record_id"] == ""


def test_real_normalize_packs_drive_all_branch_evidence_with_stable_source_bound_ids(tmp_path):
    paths, normalized = _real_normalized_outputs(tmp_path)
    keywords = json.loads(normalized["job_normalized.json"])["job_keywords"]
    evidence = json.loads(normalized["evidence_index.json"])
    terms = keywords["top_focus_terms"]
    assert terms and keywords["matched_keywords"]
    assert evidence["evidence_items"] and {"term", "source"} <= set(evidence["evidence_items"][0])

    for node_id, artifact_name in (
        ("generate_feras", "feras.md"),
        ("generate_cover_letter", "cover_letter.md"),
        ("generate_habilidades", "habilidades.md"),
    ):
        output = production_handler_registry()[node_id](
            _context(tmp_path, node_id, _branch_inputs(normalized, _fit_map("app-real", terms)))
        )
        branch_evidence = json.loads(output.artifacts["evidence_index.json"])
        assert branch_evidence["selected_evidence"]
        assert all(item["term"] and item["source"] and item["id"].startswith("evidence:") for item in branch_evidence["selected_evidence"])
        assert terms[0] in output.artifacts[artifact_name].decode("utf-8")


def test_cover_letter_review_uses_context_application_scope_for_real_evidence(tmp_path):
    _paths, normalized = _real_normalized_outputs(tmp_path)
    evidence = json.loads(normalized["evidence_index.json"])
    terms = json.loads(normalized["job_normalized.json"])["job_keywords"]["top_focus_terms"]
    fit_map = _fit_map("app-real", terms)
    generated = production_handler_registry()["generate_cover_letter"](
        _context(tmp_path, "generate_cover_letter", _branch_inputs(normalized, fit_map))
    )
    review_files = {
        **_branch_inputs(normalized, fit_map),
        "generate_cover_letter:cover_letter.md": generated.artifacts["cover_letter.md"],
        "generate_cover_letter:handover_summary.json": generated.artifacts["handover_summary.json"],
        "generate_cover_letter:evidence_index.json": generated.artifacts["evidence_index.json"],
    }
    review = production_handler_registry()["review_cover_letter"](
        _context(tmp_path, "review_cover_letter", review_files)
    )
    assert json.loads(review.artifacts["cover_letter_review.json"])["approved"] is True

    for content, tampered_evidence in (
        ("Olá", None),
        (generated.artifacts["cover_letter.md"].decode("utf-8").replace("reduziu custos em 13%", "inventou resultados"), None),
        (generated.artifacts["cover_letter.md"].decode("utf-8"), {**evidence, "application_id": "other-app"}),
    ):
        altered = dict(review_files)
        altered["generate_cover_letter:cover_letter.md"] = content.encode("utf-8")
        if tampered_evidence is not None:
            altered["normalize_job:evidence_index.json"] = json.dumps(tampered_evidence).encode("utf-8")
        with pytest.raises((ValidationFailure, ValueError)) as rejected:
            production_handler_registry()["review_cover_letter"](
                _context(tmp_path, "review_cover_letter", altered)
            )
        assert not isinstance(rejected.value, TypeError)
