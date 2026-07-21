from __future__ import annotations

import hashlib
import json
import zipfile
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from xml.etree import ElementTree

import pytest

from career.cells import handlers as cell_handlers
from career.cells.executor import CellExecutor
from career.services import cv_content
from career.services.application_context import paths_for
from career.services.database import Database
from career.utils import read_json, write_json
from career.utils import ValidationFailure


def _docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as docx:
        root = ElementTree.fromstring(docx.read("word/document.xml"))
    return "\n".join(
        node.text or ""
        for node in root.findall(
            ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
        )
    )


def _job_text(company: str, role: str, language: str) -> str:
    if language == "en":
        return (
            f"# {role}\nCompany: {company}\n\n"
            "## About the job\nLead operations planning, data, and cross-functional execution.\n"
            "## Responsibilities\nLead operations planning, data, and cross-functional execution.\n"
            "## Qualifications\nOperations leadership, SQL, S&OP, pricing, and dashboards.\n"
        )
    return (
        f"# {role}\nEmpresa: {company}\n\n"
        "## Responsabilidades\nLiderar operações, planejamento, dados e execução transversal.\n"
        "## Requisitos\nLiderança em operações, SQL, S&OP, pricing e dashboards.\n"
    )


def _draft(company: str, role: str, *, language: str, marker: str) -> dict:
    keywords = (
        ["operations", "growth", "SQL", "data", "S&OP", "pricing", "dashboards", "Excel"]
        if language == "en"
        else ["operações", "liderança", "planejamento", "SQL", "dados", "S&OP", "pricing", "dashboards"]
    )
    story = {
        "empresa": "iFood",
        "resultado": "Expansão de 400 para 800 cidades",
        "keywords_cobertas": keywords,
        "angulo": "liderança operacional baseada em dados",
        "ajustes": ["usar somente escopo comprovado"],
    }
    score = {
        "item": "operations",
        "tipo": "DIRETO",
        "evidencia": "Experiência comprovada em operações",
        "resultado": "Redução de custo em 13%",
        "nota": 1.0,
        "prova_literal": True,
        "fonte_base": "referencias:1",
    }
    return {
        "cargo": role,
        "empresa": company,
        "idioma": language,
        "modo": "Modo 1 - vaga especifica",
        "dor_central": f"Scale {marker} operations with data and governance",
        "keywords_vaga": [{"termo": keyword, "origem": "requisitos"} for keyword in keywords],
        "competencias_vaga": [{"competencia": "SQL", "tipo": "ferramenta"}],
        "mapa_ajuste": [
            {
                "termo_vaga": keyword,
                "tipo_ajuste": "DIRETO",
                "evidencia": "iFood com escala nacional",
                "empresa_origem": "iFood",
                "resultado_numero": "400 para 800 cidades",
                "angulo_sugerido": "conectar escala, dados e execucao",
                "ajustes_feitos": ["preservar o escopo literal"],
                "defensavel": True,
            }
            for keyword in keywords[:3]
        ],
        "objecoes": [
            {
                "objecao": f"Mudança de contexto setorial {index}",
                "classificacao": "media",
                "origem": "Mudança de contexto setorial",
                "mitigacao": "Apresentar evidencia operacional transferivel",
                "evidencia_real": "iFood, expansão de 400 para 800 cidades",
            }
            for index in range(1, 4)
        ],
        "nota_aderencia": {
            "final": None,
            "dimensoes": {
                "requisitos_obrigatorios": {"itens": [score]},
                "responsabilidades_principais": {"itens": [score]},
                "ausencia_gaps_criticos": {"gaps": []},
                "diferenciais_desejaveis": {"itens": [score]},
            },
        },
        "gaps_sem_cobertura": ["Experiência literal no setor da empresa"],
        "historias_selecionadas": {
            "principal": story,
            "secundaria": {**story, "empresa": "wehandle"},
            "terceira": {**story, "empresa": "VivaReal"},
        },
        "keywords_habilidade_ats": [
            {
                "keyword": keyword,
                "prioridade": index,
                "experiencia_alvo": "iFood",
                "bullet_sugerido": "Responsavel",
                "origem": "ja selecionada",
            }
            for index, keyword in enumerate(
                keywords
                + ["CSAT", "Python", "Databricks", "Grafana", "Tableau", "Power BI", "pipeline"],
                start=1,
            )
        ],
    }


def _seed(paths, *, company: str, role: str, language: str, marker: str) -> None:
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        paths.identity,
        {
            "kind": "application_identity",
            "application_id": paths.application_id,
            "source_type": "pasted_text",
            "source_id": marker,
            "company": company,
            "role": role,
        },
    )
    paths.job_description.write_text(_job_text(company, role, language), encoding="utf-8")
    write_json(paths.fit_map_draft, _draft(company, role, language=language, marker=marker))


def _run_through(executor: CellExecutor, run_id: str, target: str):
    results = []
    for _ in range(12):
        if executor.node_status(run_id, target) in {"validated", "blocked"}:
            break
        batch = executor.run_ready(run_id)
        results.extend(batch)
        if not batch:
            break
    assert executor.node_status(run_id, target) == "validated"
    return next(item for item in results if item.node_id == target)


def test_two_application_scoped_cv_pipelines_do_not_share_content_or_reviews(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    first = paths_for("cv-pt", root=applications_root)
    second = paths_for("cv-en", root=applications_root)
    _seed(first, company="Acme Brasil", role="Diretor de Operações", language="pt-BR", marker="pt-marker")
    _seed(second, company="Acme Global", role="Operations Director", language="en", marker="en-marker")
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers=cell_handlers.production_handler_registry(),
        validators=cell_handlers.production_validator_registry(),
    )
    try:
        first_plan = executor.plan(first.application_id, {"cv"})
        second_plan = executor.plan(second.application_id, {"cv"})
        render_barrier = Barrier(2)
        render_lock = Lock()
        render_entries: list[str] = []

        def run_isolated(plan):
            worker_database = Database(database.db_path)
            handlers = cell_handlers.production_handler_registry()
            base_render = handlers["render_cv"]

            def synchronized_render(context):
                with render_lock:
                    render_entries.append(context.application_id)
                render_barrier.wait(timeout=10)
                return base_render(context)

            handlers["render_cv"] = synchronized_render
            worker = CellExecutor(
                worker_database,
                applications_root=applications_root,
                handlers=handlers,
                validators=cell_handlers.production_validator_registry(),
            )
            try:
                return _run_through(worker, plan.run_id, "review_cv")
            finally:
                worker_database.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(run_isolated, first_plan)
            second_future = pool.submit(run_isolated, second_plan)
            first_result = first_future.result()
            second_result = second_future.result()

        assert set(render_entries) == {first.application_id, second.application_id}
        assert not render_barrier.broken

        first_manifest = read_json(first_result.manifest_path)
        second_manifest = read_json(second_result.manifest_path)
        first_artifact = Path(first_manifest["inputs"]["render_cv:cv.docx"]["path"])
        second_artifact = Path(second_manifest["inputs"]["render_cv:cv.docx"]["path"])
        assert first_artifact != second_artifact
        assert first_manifest["application_id"] != second_manifest["application_id"]
        assert first_manifest["inputs"]["render_cv:cv.docx"]["sha256"] != second_manifest["inputs"]["render_cv:cv.docx"]["sha256"]
        for manifest, artifact in ((first_manifest, first_artifact), (second_manifest, second_artifact)):
            outputs = {item["artifact_name"]: item for item in manifest["outputs"]}
            assert {"cv_review.json", "approved_cv_manifest.json"} <= set(outputs)
            report_path = Path(outputs["cv_review.json"]["path"])
            report = read_json(report_path)
            approval = read_json(Path(outputs["approved_cv_manifest.json"]["path"]))
            assert approval["review_report_artifact"] == "cv_review.json"
            assert approval["review_report_sha256"] == hashlib.sha256(report_path.read_bytes()).hexdigest()
            assert approval["artifact_path"] == str(artifact)
            assert approval["artifact_sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()

        first_render_manifest = read_json(first.cells_dir / first_plan.run_id / "render_cv" / "1" / "manifest.json")
        second_render_manifest = read_json(second.cells_dir / second_plan.run_id / "render_cv" / "1" / "manifest.json")
        first_content = read_json(Path(first_render_manifest["inputs"]["compose_cv:cv_content.json"]["path"]))
        second_content = read_json(Path(second_render_manifest["inputs"]["compose_cv:cv_content.json"]["path"]))
        assert first_content["metadata"]["language"] == "pt-BR"
        assert second_content["metadata"]["language"] == "en"
        portuguese_docx = _docx_text(first_artifact)
        english_docx = _docx_text(second_artifact)
        assert "Head de Operações" in portuguese_docx
        assert "maio/2024 — fev/2026" in portuguese_docx
        assert "Formação" in portuguese_docx
        assert "Stack técnica" in portuguese_docx
        assert "Português — Nativo" in portuguese_docx
        assert "Head of Operations" in english_docx
        assert "May 2024 — Feb 2026" in english_docx
        assert "maio/2024 — fev/2026" not in english_docx
        assert "Education" in english_docx
        assert "Technical Stack" in english_docx
        assert "Portuguese — Native" in english_docx
        for payload in (first_content, second_content):
            assert payload["metadata"]["candidate_facts_revision"]
            assert all("experience_id" in item and "evidence_id" in item for item in payload["experiences"])
            assert all("experience_id" in item and "evidence_id" in item for item in payload["ats_keyword_coverage"])
            cv_content.validate_canonical_provenance(payload)
            evidence = payload["metadata"]["candidate_facts"]["evidence"]
            assert len(evidence) == len(set(evidence))
        tampering = {
            "role": lambda item: item["experiencias"][0].__setitem__("cargo", "Tampered role"),
            "period": lambda item: item["experiencias"][0].__setitem__("periodo", "Tampered period"),
            "bullet": lambda item: item["experiencias"][0]["bullets"].__setitem__(0, "Tampered bullet"),
            "education": lambda item: item["formacao"].__setitem__(0, "Tampered education"),
            "language": lambda item: item["idiomas"].__setitem__(0, "Tampered language"),
            "stack": lambda item: item.__setitem__("stack", "Tampered stack"),
            "contact": lambda item: item["candidate"].__setitem__("email", "tampered@example.test"),
            "summary": lambda item: item.__setitem__("resumo", "Tampered summary"),
        }
        for field, mutate in tampering.items():
            tampered = deepcopy(first_content)
            mutate(tampered)
            with pytest.raises(ValidationFailure, match="evidence"):
                cv_content.validate_canonical_provenance(tampered)
        adversarial = deepcopy(first_content)
        provenance = adversarial["experiencias"][0]["provenance"]
        old_id = provenance["cargo"]
        old_record = adversarial["metadata"]["candidate_facts"]["evidence"].pop(old_id)
        forged_value = "Invented Operations Role"
        forged_hash = hashlib.sha256(forged_value.encode("utf-8")).hexdigest()
        revision = adversarial["metadata"]["candidate_facts_revision"]
        forged_id = hashlib.sha256(
            f"{revision}\0{old_record['source']}\0{old_record['kind']}\0{old_record['locator']}\0{forged_hash}".encode("utf-8")
        ).hexdigest()
        old_record["value_sha256"] = forged_hash
        adversarial["metadata"]["candidate_facts"]["evidence"][forged_id] = old_record
        adversarial["experiencias"][0]["cargo"] = forged_value
        provenance["cargo"] = forged_id
        with pytest.raises(ValidationFailure):
            cv_content.validate_canonical_provenance(adversarial)
        assert first_manifest["inputs"]["analyze_fit:fit_map.json"]["sha256"] != second_manifest["inputs"]["analyze_fit:fit_map.json"]["sha256"]
        assert not (first.reviews_dir / first_plan.run_id / "cv_review.json").exists()
        assert not (second.reviews_dir / second_plan.run_id / "cv_review.json").exists()
        assert first.reviews_dir != second.reviews_dir
        assert not first.cv_content.exists()
        assert not second.cv_content.exists()
        assert not (first.derived_dir / "keyword_ats_registry.json").exists()
        assert not (second.derived_dir / "keyword_ats_registry.json").exists()
    finally:
        database.close()
