#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import shlex
import shutil
import zipfile
import sys
import tempfile
from pathlib import Path

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.paths import CAREER_STATE, OUTPUTS
from career.schemas.fit_map import FitMapDraftSchema, FitMapFinalSchema
from career.schemas.notion import NotionApplicationsCacheSchema
from career.schemas.review import CvReviewReportSchema
from career.utils import read_json
from career.utils import ValidationFailure
from career.workflow.state_machine import WorkflowStateMachine
import notion_sync
import register_keywords
import review_output
import telegram_harness_adapter
import install_hermes_harness_hook
import hermes_harness_context_hook
from career.cli import build_parser
from career.services import applications_v2 as applications_service
from career.services.agent_runner import AgentRunRequest, AgentRunResult, SubprocessAgentRunner
from career.services.harness_supervisor import HarnessSupervisor
from career.services.harness_runs import ExclusiveRunLock, HarnessRunStore, begin_specialist_run
from career.services.approvals import ApprovalStore
from career.services.approved_actions import ApprovedActionExecutor
from career.services import review as review_service


def run_command(args: list[str]) -> None:
    if args and args[0] == "npm":
        npm_command = "npm.cmd" if shutil.which("npm.cmd") else "npm"
        args = [npm_command, *args[1:]]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise SystemExit(
            f"Command failed ({' '.join(args)}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def phase_1() -> None:
    NotionApplicationsCacheSchema(read_json(ROOT / "inbox/notion/applications_cache.json")).validate()
    FitMapFinalSchema(read_json(CAREER_STATE / "fit_map.json")).validate()
    report_path = OUTPUTS / "_tmp" / "output_review_report.json"
    if report_path.exists():
        CvReviewReportSchema(read_json(report_path)).validate()


def phase_2() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        draft_path = Path(tmp_dir) / "fit_map.draft.json"
        run_command([sys.executable, "scripts/career_cli.py", "fit-map", "template", "--output", str(draft_path)])
        FitMapDraftSchema(read_json(draft_path)).payload
    run_command([sys.executable, "scripts/career_cli.py", "notion", "build-cache"])


def phase_3() -> None:
    run_command([sys.executable, "scripts/career_cli.py", "workflow", "reset-state"])
    run_command([sys.executable, "scripts/career_cli.py", "workflow", "run-task", "notion.build_cache"])
    state = read_json(CAREER_STATE / "workflow_state.json")
    if "notion_cache_ready" not in state.get("completed_states", []):
        raise SystemExit("Workflow state did not register notion_cache_ready")


def phase_4() -> None:
    run_command([sys.executable, "scripts/career_cli.py", "project", "validate-structure"])


def phase_5() -> None:
    run_command([sys.executable, "scripts/career_cli.py", "workflow", "reset-state"])
    try:
        run_command([sys.executable, "scripts/career_cli.py", "workflow", "run-task", "fit_map.score"])
    except SystemExit:
        return
    raise SystemExit("State machine test failed: fit_map.score should not run before fit_map.build")


def phase_6() -> None:
    run_command([sys.executable, "scripts/career_cli.py", "notion", "refresh"])


def phase_7() -> None:
    run_command(["npm", "run", "validate:structure"])


def phase_8() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        session_path = tmp / "session-stalled.md"
        job_path = tmp / "job.md"
        draft_path = tmp / "fit_map.draft.json"
        fit_map_path = tmp / "fit_map.json"
        session_path.write_text(
            "## Assistant\nVou preencher o draft agora.\n\n**Tool: terminal**\n"
            "npm run fit-map:template\n",
            encoding="utf-8",
        )
        job_path.write_text("Descricao de vaga diferente do FIT_MAP salvo.", encoding="utf-8")
        run_command([sys.executable, "scripts/career_cli.py", "fit-map", "template", "--output", str(draft_path)])
        fit_map_path.write_text(
            json.dumps(
                {
                    "cargo": "Head de Revenue Operations",
                    "empresa": "iugu",
                    "modo": "Modo 1 - vaga especifica",
                    "dor_central": "fixture",
                    "keywords_vaga": [],
                    "competencias_vaga": [],
                    "keywords_para_ats": [],
                    "mapa_ajuste": [],
                    "objecoes": [],
                    "nota_aderencia": {"final": 1, "dimensoes": {}},
                    "gaps_sem_cobertura": [],
                    "historias_selecionadas": {},
                    "keywords_habilidade_ats": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                "scripts/diagnose_session_stall.py",
                str(session_path),
                "--draft",
                str(draft_path),
                "--fit-map",
                str(fit_map_path),
                "--job-description",
                str(job_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 1:
            raise SystemExit(f"Expected stalled session exit code 1, got {result.returncode}:\n{result.stdout}\n{result.stderr}")
        payload = json.loads(result.stdout)
        expected = {
            "stalled": True,
            "last_completed_step": "fit-map:template",
            "next_required_step": "preencher .career-state/fit_map.draft.json",
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                raise SystemExit(f"Unexpected stall diagnosis for {key}: {payload.get(key)!r}")
        signals = payload.get("signals", {})
        if not signals.get("draft_placeholder") or not signals.get("fit_map_stale"):
            raise SystemExit(f"Stall diagnosis missed expected signals: {signals}")


def phase_9() -> None:
    machine = WorkflowStateMachine(
        {"fit_map_draft_valid"},
        {"fit_map.validate_draft": {"active_job_fingerprint": "old-job"}},
        "new-job",
    )
    try:
        machine.ensure_task_allowed("fit_map.build")
    except ValidationFailure:
        return
    raise SystemExit("State machine should block FIT_MAP build when prerequisite belongs to another job")


def phase_10() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        draft_path = Path(tmp_dir) / "fit_map.draft.json"
        run_command([sys.executable, "scripts/career_cli.py", "fit-map", "template", "--output", str(draft_path)])
        result = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "fit-map",
                "validate-stage",
                "extract",
                "--path",
                str(draft_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            raise SystemExit("validate-stage extract should fail while template placeholders remain")


def phase_11() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        job_dir = Path(tmp_dir)
        job_path = job_dir / "atvos_gerente_de_planejamento_integrado_s_op_s_oe.md"
        job_path.write_text(
            "# Atvos - Gerente de Planejamento Integrado (S&OP | S&OE)\n\nDescrição real da vaga.\n",
            encoding="utf-8",
        )
        fit_map = {
            "empresa": "Atvos",
            "cargo": "Gerente de Planejamento Integrado (S&OP | S&OE)",
        }
        text, path, source = notion_sync.select_job_description_for_update(
            fit_map,
            None,
            "Pesquisa Inicial\nFeedback em caso de Reprovação",
            saved_job_dir=job_dir,
        )
        if source != "saved_job_description" or path != job_path or "Descrição real da vaga" not in text:
            raise SystemExit(
                "Notion manual-template update should select saved active job description, "
                f"got source={source!r}, path={path!r}"
            )


def phase_12() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        artifact = tmp / "cv.docx"
        fit_map = tmp / "fit_map.json"
        registry = tmp / "registry.json"
        report = tmp / "output_review_report.json"
        with zipfile.ZipFile(artifact, "w") as archive:
            archive.writestr(
                "word/document.xml",
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    "<w:body><w:p><w:r><w:t>CV de teste</w:t></w:r></w:p></w:body></w:document>"
                ),
            )
        fit_map.write_text("{}", encoding="utf-8")
        registry.write_text("{}", encoding="utf-8")

        original_run = review_service.subprocess.run
        original_build = review_service.legacy_review_output.build_cv_review
        try:
            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            review_service.subprocess.run = lambda *args, **kwargs: Result()
            review_service.legacy_review_output.build_cv_review = lambda *args, **kwargs: {
                "kind": "cv",
                "artifact": str(artifact),
                "company": "Atvos",
                "role": "Gerente",
                "approved": False,
                "approved_for_delivery": False,
                "ats_policy": {
                    "top8": {"score": 4.0, "score_max": 8},
                    "top15": {"score": 6.0, "score_max": 15},
                },
                "blockers": [{"id": "ats_top8_minimum_score", "message": "blocked", "evidence": ""}],
                "warnings": [],
                "totals": {
                    "weight_total_passed": 6,
                    "weight_total_total": 7,
                    "minor_passed": 10,
                    "minor_total": 11,
                    "minor_rate": 0.9091,
                    "blockers": 1,
                    "warnings": 0,
                },
                "weight_total_checks": [{"id": "top8_keywords_covered", "passed": False}],
                "minor_checks": [],
                "top8_keywords": [],
                "summary_chars": 100,
            }
            try:
                review_service.approve_cv(artifact, fit_map, registry, report)
            except SystemExit as exc:
                if "not approved" not in str(exc):
                    raise
            else:
                raise SystemExit("approve_cv should fail when review report approved=false")
        finally:
            review_service.subprocess.run = original_run
            review_service.legacy_review_output.build_cv_review = original_build


def phase_13() -> None:
    fit_map = {
        "keywords_habilidade_ats": [
            {
                "keyword": "Plano Operacional Unico",
                "prioridade": 1,
                "origem": "já selecionada",
            }
        ],
        "keywords_vaga": [],
        "gaps_sem_cobertura": [],
    }
    records = register_keywords.keyword_records(
        fit_map,
        "Busco posição liderando o Plano Operacional Único entre áreas.",
    )
    if records[0]["status"] != "covered_cv":
        raise SystemExit(f"Expected accent-insensitive covered_cv, got {records[0]}")

    top8, missing = review_output.top_keyword_results(
        fit_map,
        {"keyword_records": [{"keyword": "Plano Operacional Unico", "status": "missing_cv"}]},
        ["Busco posição liderando o Plano Operacional Único entre áreas."],
        {"entries": {}},
    )
    if missing or not top8[0]["covered"]:
        raise SystemExit(f"Expected reviewer normalized evidence coverage, got top8={top8}, missing={missing}")


def phase_14() -> None:
    def fit_map_for(classes: list[str]) -> dict:
        gaps = [
            f"Keyword {index} gap"
            for index, coverage_class in enumerate(classes, start=1)
            if coverage_class == "declared_gap"
        ]
        return {
            "keywords_habilidade_ats": [
                {
                    "keyword": f"Keyword {index}",
                    "prioridade": index,
                    "origem": "gap" if coverage_class == "declared_gap" else "já selecionada",
                }
                for index, coverage_class in enumerate(classes, start=1)
            ],
            "keywords_vaga": [],
            "gaps_sem_cobertura": gaps,
        }

    def application_for(classes: list[str]) -> dict:
        status_by_class = {
            "covered_exact": "covered_cv",
            "covered_similar": "covered_similar_cv",
            "declared_gap": "gap",
            "missing_unexplained": "missing_cv",
        }
        return {
            "keyword_records": [
                {
                    "keyword": f"Keyword {index}",
                    "status": status_by_class[coverage_class],
                }
                for index, coverage_class in enumerate(classes, start=1)
            ]
        }

    optimal_classes = [
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_similar",
        "covered_similar",
        "declared_gap",
    ]
    results, missing = review_output.top_keyword_results(
        fit_map_for(optimal_classes),
        application_for(optimal_classes),
        [],
        {"entries": {}},
    )
    summary = review_output.ats_score_summary(results, limit=8)
    if missing or summary["score"] != 6.6 or summary["level"] != "optimal":
        raise SystemExit(f"Expected optimal ATS policy case, got summary={summary}, missing={missing}")

    minimum_classes = [
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_similar",
        "covered_similar",
        "declared_gap",
        "declared_gap",
    ]
    results, missing = review_output.top_keyword_results(
        fit_map_for(minimum_classes),
        application_for(minimum_classes),
        [],
        {"entries": {}},
    )
    summary = review_output.ats_score_summary(results, limit=8)
    if missing or summary["score"] != 5.6 or summary["level"] != "minimum":
        raise SystemExit(f"Expected minimum ATS policy case, got summary={summary}, missing={missing}")

    blocked_classes = [
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_similar",
        "missing_unexplained",
        "missing_unexplained",
        "missing_unexplained",
    ]
    results, missing = review_output.top_keyword_results(
        fit_map_for(blocked_classes),
        application_for(blocked_classes),
        [],
        {"entries": {}},
    )
    summary = review_output.ats_score_summary(results, limit=8)
    if len(missing) != 3 or summary["score"] != 4.8 or summary["level"] != "blocked":
        raise SystemExit(f"Expected blocked ATS policy case, got summary={summary}, missing={missing}")


def phase_15() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        draft_path = tmp / "fit_map.draft.json"
        fit_map_path = tmp / "fit_map.json"
        job_path = tmp / "allied_brasil_gerente_supply_chain_e_pricing.md"
        run_command([sys.executable, "scripts/career_cli.py", "fit-map", "template", "--output", str(draft_path)])
        fit_map_path.write_text(
            json.dumps(
                {
                    "cargo": "Gerente de Planejamento Integrado",
                    "empresa": "Atvos",
                    "modo": "Modo 1 - vaga especifica",
                    "dor_central": "fixture",
                    "keywords_vaga": [],
                    "competencias_vaga": [],
                    "keywords_para_ats": [],
                    "mapa_ajuste": [],
                    "objecoes": [],
                    "nota_aderencia": {"final": 1, "dimensoes": {}},
                    "gaps_sem_cobertura": [],
                    "historias_selecionadas": {},
                    "keywords_habilidade_ats": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        job_path.write_text("Allied Brasil\nGerente Supply Chain e Pricing\n", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "fit-map",
                "guard",
                "--draft",
                str(draft_path),
                "--fit-map",
                str(fit_map_path),
                "--job-description",
                str(job_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 1:
            raise SystemExit(f"Guard should block placeholder draft, got {result.returncode}:\n{result.stdout}\n{result.stderr}")
        payload = json.loads(result.stdout)
        if payload.get("guard") != "blocked" or payload.get("next_required_step") != "preencher .career-state/fit_map.draft.json":
            raise SystemExit(f"Unexpected guard payload: {payload}")
        if "PARE A NARRATIVA" not in payload.get("instruction", ""):
            raise SystemExit(f"Guard instruction should be explicit, got: {payload.get('instruction')}")


def phase_16() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        output = tmp / "general_cv_strategy.json"
        report = tmp / "general_cv_strategy.md"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "general-cv",
                "strategy",
                "--output",
                str(output),
                "--report",
                str(report),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise SystemExit(f"General CV default strategy should pass:\n{result.stdout}\n{result.stderr}")
        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload.get("mode") != "concise" or payload.get("bullet_count_per_experience") != 3:
            raise SystemExit(f"Default general CV should be concise with 3 bullets, got {payload}")

        output_5 = tmp / "general_cv_strategy_5.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "general-cv",
                "strategy",
                "--mode",
                "expanded",
                "--bullet-count",
                "5",
                "--output",
                str(output_5),
                "--report",
                str(tmp / "report_5.md"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise SystemExit(f"General CV expanded with 5 bullets should pass:\n{result.stdout}\n{result.stderr}")
        payload_5 = json.loads(output_5.read_text(encoding="utf-8"))
        if payload_5.get("bullet_count_per_experience") != 5:
            raise SystemExit(f"Expected 5 bullets, got {payload_5}")

        concise_default_cluster = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "general-cv",
                "strategy",
                "--mode",
                "concise",
                "--output",
                str(tmp / "concise.json"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if concise_default_cluster.returncode != 0:
            raise SystemExit(
                "General CV concise without cluster should default to operations cluster:\n"
                f"{concise_default_cluster.stdout}\n{concise_default_cluster.stderr}"
            )
        payload_concise = json.loads((tmp / "concise.json").read_text(encoding="utf-8"))
        if payload_concise.get("dominant_cluster") != "operacoes_supply_logistica":
            raise SystemExit(f"Expected default operations cluster for concise CV, got {payload_concise}")

        concise_output = tmp / "general_cv_strategy_concise.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "general-cv",
                "strategy",
                "--mode",
                "concise",
                "--dominant-cluster",
                "operacoes_supply_logistica",
                "--output",
                str(concise_output),
                "--report",
                str(tmp / "report_concise.md"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise SystemExit(f"General CV concise with cluster should pass:\n{result.stdout}\n{result.stderr}")
        concise_payload = json.loads(concise_output.read_text(encoding="utf-8"))
        clusters = set(concise_payload.get("clusters", {}))
        if concise_payload.get("mode") != "concise" or clusters != {"operacoes_supply_logistica"}:
            raise SystemExit(f"Concise mode should only cover dominant cluster, got {concise_payload}")


def phase_17() -> None:
    applications = [
        {"record_id": 10, "status": "Em análise", "description_chars": 100, "title": "A"},
        {"record_id": 11, "status": "Aplicação Feita", "description_chars": 100, "title": "B"},
        {"record_id": 12, "status": "Analisando", "description_chars": 100, "title": "C"},
        {"record_id": 13, "status": "Aplicação em Análise", "description_chars": 0, "title": "D"},
        {"record_id": 14, "status": "Reprocessar", "description_chars": 100, "title": "E"},
        {"record_id": 15, "status": "Aplicação em Análise", "description_chars": 100, "title": "F", "is_archived": True},
    ]
    selected = applications_service._eligible(applications, applications_service.DEFAULT_CONFIG, 3)
    if [item["title"] for item in selected] != ["E", "D", "C"]:
        raise SystemExit(f"Unexpected heartbeat queue selection: {selected}")
    if applications_service.DEFAULT_CONFIG["no_description_status"] != "Sem descrição de vaga":
        raise SystemExit("Unexpected no-description Notion status spelling")
    if notion_sync.sanitize_automation_status("Aplicação Feita") != "Aplicação andamento":
        raise SystemExit("Legacy Notion completion status should be downgraded to Aplicação andamento")
    if applications_service.detect_job_language("About the role\nResponsibilities\nRequirements") != "en":
        raise SystemExit("Expected English job description detection")
    if applications_service.detect_job_language("Sobre a vaga\nResponsabilidades\nRequisitos") != "pt-BR":
        raise SystemExit("Expected Portuguese job description detection")

    with tempfile.TemporaryDirectory() as tmp_dir:
        artifact = Path(tmp_dir) / "felipe_armel_cv_fixture.docx"
        artifact.write_text("placeholder", encoding="utf-8")
        report = Path(tmp_dir) / "polish_review.json"
        original_docx_text = review_service.legacy_review_output.docx_text
        original_is_portuguese = review_service.legacy_review_output.is_portuguese_cv
        try:
            review_service.legacy_review_output.docx_text = lambda _path: (
                "Resumo\n"
                "Conduzi experimentation e data-driven decision making em operações.\n"
                "Experiência\n"
            )
            review_service.legacy_review_output.is_portuguese_cv = lambda _path: True
            payload = review_service.polish_cv(artifact, report)
            blockers = payload.get("approval_blockers", [])
            if not any("experimentation" in item for item in blockers):
                raise SystemExit(f"Expected experimentation blocker, got {payload}")
            if not report.exists():
                raise SystemExit("Polish report was not written")
        finally:
            review_service.legacy_review_output.docx_text = original_docx_text
            review_service.legacy_review_output.is_portuguese_cv = original_is_portuguese


def phase_18() -> None:
    if not hasattr(applications_service, "run_heartbeat"):
        raise SystemExit("applications_v2 service must expose run_heartbeat")
    if not hasattr(applications_service, "write_default_config"):
        raise SystemExit("applications_v2 service must expose write_default_config")


def phase_19() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "999"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        write_json = lambda path, payload: path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        write_json(
            paths["manifest"],
            {"role": "Gerente", "company": "Empresa", "title": "Gerente", "required_cv_filename_suffix": ""},
        )
        write_json(paths["fit_map"], {"cargo": "Gerente", "empresa": "Empresa", "nota_aderencia": {"final": 7.0}})
        paths["cv_content"].write_text(json.dumps({"summary": "ok", "experiences": []}), encoding="utf-8")
        paths["feras_formal"].write_text("FERAS\n", encoding="utf-8")
        paths["habilidades_gupy"].write_text("Habilidades\n", encoding="utf-8")
        paths["habilidades_mercado_livre"].write_text("Habilidades\n", encoding="utf-8")
        write_json(paths["cv_review_report"], {"approved_for_delivery": True})
        write_json(paths["polish_review"], {"polish_executed": True, "approval_blockers": []})
        original_outputs = applications_service.OUTPUTS
        try:
            applications_service.OUTPUTS = tmp / "outputs"
            if applications_service._is_review_approved(paths):
                raise SystemExit("Review cannot be approved when the expected DOCX file is missing")
        finally:
            applications_service.OUTPUTS = original_outputs


def phase_20() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        original_v2_dir = applications_service.V2_DIR
        original_inbox = applications_service.INBOX
        try:
            applications_service.V2_DIR = tmp / "applications_v2"
            applications_service.INBOX = tmp / "inbox"
            app_dir, paths = applications_service._write_package(
                {
                    "record_id": 501,
                    "title": "Planning & Materials Manager (Finished Goods)",
                    "role": "Planning & Materials Manager (Finished Goods)",
                    "company": "Beckman Coulter Diagnostics (Danaher)",
                    "description": "About the role\nPlanning & Materials Manager (Finished Goods)\n",
                }
            )
            saved_pointer = paths["saved_job_description"].read_text(encoding="utf-8").strip()
            saved_path = Path(saved_pointer)
            if not saved_path.exists():
                raise SystemExit("Expected canonical saved job description to be created during package write")
            if "planning_materials_manager_finished_goods" not in saved_path.name:
                raise SystemExit(f"Canonical saved job description slug is wrong: {saved_path.name}")
            if app_dir != applications_service.V2_DIR / "501":
                raise SystemExit(f"Unexpected application dir: {app_dir}")
        finally:
            applications_service.V2_DIR = original_v2_dir
            applications_service.INBOX = original_inbox


def phase_21() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "777"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        paths["job_description"].write_text("Sobre a vaga\nGerente de Pricing\n", encoding="utf-8")
        paths["fit_map_draft"].write_text("{}", encoding="utf-8")
        paths["manifest"].write_text(
            json.dumps({"role": "Gerente de Pricing", "company": "Empresa", "title": "Gerente de Pricing", "required_cv_filename_suffix": ""}),
            encoding="utf-8",
        )
        state = {"retry_count_analyze": 0, "last_error": None, "llm_session_count": 0, "llm_stage_attempts": {}}
        applications_service._set_stage(state, "analyze_running")

        original_run_agent = applications_service._run_agent
        original_postprocess = applications_service._postprocess_analyze
        original_write_state = applications_service._write_state
        original_write_context = applications_service._write_context

        calls = {"postprocess": 0, "write_state": 0}

        def fake_run_agent(stage, application, local_paths, config, options, local_state):
            if stage != "analyze":
                raise SystemExit(f"Unexpected stage for fake agent: {stage}")
            local_state["llm_session_count"] = int(local_state.get("llm_session_count") or 0) + 1

        def fake_postprocess(local_paths):
            calls["postprocess"] += 1
            if calls["postprocess"] == 1:
                raise ValidationFailure("draft still has placeholders")
            return 7.4

        def fake_write_state(local_paths, payload):
            calls["write_state"] += 1

        def fake_write_context(application, local_paths, payload):
            return None

        try:
            applications_service._run_agent = fake_run_agent
            applications_service._postprocess_analyze = fake_postprocess
            applications_service._write_state = fake_write_state
            applications_service._write_context = fake_write_context
            result = applications_service._run_analyze_with_retry(
                {"record_id": 777, "title": "Gerente de Pricing", "company": "Empresa", "role": "Gerente de Pricing"},
                paths,
                applications_service.DEFAULT_CONFIG,
                applications_service.HeartbeatV2Options(max_per_run=1, run_agent=True, dry_run=False),
                state,
            )
            if result != 7.4:
                raise SystemExit(f"Unexpected retry result: {result}")
            if state.get("retry_count_analyze") != 1:
                raise SystemExit(f"Analyze retry counter did not increment: {state}")
            if state.get("stage") != "analyze_retry_pending":
                raise SystemExit(f"State did not move to analyze_retry_pending before retry: {state}")
            if calls["postprocess"] != 2:
                raise SystemExit(f"Postprocess should run twice with retry, got {calls['postprocess']}")
            if calls["write_state"] != 1:
                raise SystemExit(f"Retry path should persist state once before rerun, got {calls['write_state']}")
        finally:
            applications_service._run_agent = original_run_agent
            applications_service._postprocess_analyze = original_postprocess
            applications_service._write_state = original_write_state
            applications_service._write_context = original_write_context


def phase_22() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "778"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        paths["job_description"].write_text("Sobre a vaga\nGerente de Pricing\n", encoding="utf-8")
        paths["fit_map_draft"].write_text("{}", encoding="utf-8")
        paths["manifest"].write_text(
            json.dumps({"role": "Gerente de Pricing", "company": "Empresa", "title": "Gerente de Pricing", "required_cv_filename_suffix": ""}),
            encoding="utf-8",
        )
        state = {"retry_count_analyze": 0, "last_error": None, "llm_session_count": 0, "llm_stage_attempts": {}}
        applications_service._set_stage(state, "analyze_running")

        original_run_agent = applications_service._run_agent
        original_postprocess = applications_service._postprocess_analyze
        original_write_state = applications_service._write_state
        original_write_context = applications_service._write_context

        calls = {"postprocess": 0, "write_state": 0}

        def fake_run_agent(stage, application, local_paths, config, options, local_state):
            if stage != "analyze":
                raise SystemExit(f"Unexpected stage for fake agent: {stage}")
            local_state["llm_session_count"] = int(local_state.get("llm_session_count") or 0) + 1

        def fake_postprocess(local_paths):
            calls["postprocess"] += 1
            raise ValidationFailure("fit map quality score below threshold")

        def fake_write_state(local_paths, payload):
            calls["write_state"] += 1

        def fake_write_context(application, local_paths, payload):
            return None

        try:
            applications_service._run_agent = fake_run_agent
            applications_service._postprocess_analyze = fake_postprocess
            applications_service._write_state = fake_write_state
            applications_service._write_context = fake_write_context
            try:
                applications_service._run_analyze_with_retry(
                    {"record_id": 778, "title": "Gerente de Pricing", "company": "Empresa", "role": "Gerente de Pricing"},
                    paths,
                    applications_service.DEFAULT_CONFIG,
                    applications_service.HeartbeatV2Options(max_per_run=1, run_agent=True, dry_run=False),
                    state,
                )
                raise SystemExit("Analyze retry should not rerun for non-retryable validation errors.")
            except ValidationFailure as exc:
                if "below threshold" not in str(exc):
                    raise
            if state.get("retry_count_analyze") != 0:
                raise SystemExit(f"Analyze retry counter should stay at zero for non-retryable errors: {state}")
            if calls["postprocess"] != 1:
                raise SystemExit(f"Postprocess should run once without retry, got {calls['postprocess']}")
            if calls["write_state"] != 0:
                raise SystemExit(f"State should not be persisted for skipped retry, got {calls['write_state']}")
        finally:
            applications_service._run_agent = original_run_agent
            applications_service._postprocess_analyze = original_postprocess
            applications_service._write_state = original_write_state
            applications_service._write_context = original_write_context


def phase_23() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "888"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        paths["job_description"].write_text("Sobre a vaga\nGerente\n", encoding="utf-8")
        paths["cv_review_report"].write_text(json.dumps({"approved_for_delivery": False}), encoding="utf-8")
        paths["polish_review"].write_text(json.dumps({"approval_blockers": ["pt_cv_keyword_shotgun_control"]}), encoding="utf-8")
        manifest = {
            "role": "Gerente",
            "company": "Empresa",
            "title": "Gerente",
            "required_cv_filename_suffix": "",
        }
        paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
        paths["fit_map"].write_text(json.dumps({"cargo": "Gerente", "empresa": "Empresa", "nota_aderencia": {"final": 7.2}}), encoding="utf-8")
        original_outputs = applications_service.OUTPUTS
        try:
            applications_service.OUTPUTS = tmp / "outputs"
            expected_docx = applications_service._expected_cv_docx_path(paths)
            expected_docx.parent.mkdir(parents=True, exist_ok=True)
            expected_docx.write_text("fixture", encoding="utf-8")
            stage, score = applications_service._derive_stage(paths, applications_service.DEFAULT_CONFIG)
            if stage != "blocked_review" or score != 7.2:
                raise SystemExit(f"Expected blocked_review stage, got stage={stage} score={score}")
        finally:
            applications_service.OUTPUTS = original_outputs


def phase_24() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "889"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        paths["fit_map"].write_text(
            json.dumps(
                {
                    "cargo": "Coordenador(a) de Operações",
                    "empresa": "Nomad",
                    "keywords_habilidade_ats": [
                        {"keyword": "Liderança de Operações", "prioridade": 1},
                        {"keyword": "Gestão de Incidentes", "prioridade": 2},
                        {"keyword": "SLAs", "prioridade": 3},
                        {"keyword": "Gestão de Times", "prioridade": 4},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        paths["cv_content"].write_text(
            json.dumps(
                {
                    "summary": "ok",
                    "experiences": [
                        {"role": "A", "company": "X", "period": "1", "bullets": [{"text": "b1"}]},
                        {"role": "B", "company": "Y", "period": "2", "bullets": [{"text": "b2"}]},
                        {"role": "C", "company": "Z", "period": "3", "bullets": [{"text": "b3"}]},
                    ],
                    "ats_keyword_coverage": [],
                    "education": [],
                    "languages": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        try:
            applications_service._validate_cv_content_contract(paths)
        except ValidationFailure as exc:
            if "between 4 and 8 experiences" not in str(exc):
                raise SystemExit(f"Unexpected validation error for cv_content contract: {exc}")
        else:
            raise SystemExit("cv_content contract should block when experiences < 4")


def phase_25() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "890"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        state = {
            "stage": "blocked_review",
            "score": 6.1,
            "last_error": "review blocked",
            "review_status": "blocked",
            "polish_status": "pending",
        }
        review_report = {
            "blockers": [{"id": "ats_top8_no_missing_unexplained"}],
            "top8_keywords": [
                {
                    "keyword": "Liderança de Operações",
                    "coverage_class": "missing_unexplained",
                    "experience_target": "wehandle - Head de Operações",
                    "coverage_note": None,
                },
                {
                    "keyword": "SLAs",
                    "coverage_class": "covered_exact",
                    "experience_target": "wehandle - Head de Operações",
                    "coverage_note": None,
                },
            ],
        }
        polish_report = {"approval_blockers": []}
        paths["fit_map"].write_text(json.dumps({"cargo": "Coordenador(a) de Operações", "empresa": "Nomad"}), encoding="utf-8")
        paths["cv_content"].write_text(json.dumps({"summary": "ok", "experiences": []}), encoding="utf-8")
        paths["cv_review_report"].write_text(json.dumps(review_report), encoding="utf-8")
        paths["polish_review"].write_text(json.dumps(polish_report), encoding="utf-8")
        paths["feras_formal"].write_text("x", encoding="utf-8")
        paths["habilidades_gupy"].write_text("x", encoding="utf-8")
        paths["habilidades_mercado_livre"].write_text("x", encoding="utf-8")
        applications_service._write_repair_request(paths, state, review_report, polish_report)
        payload = json.loads(paths["repair_request_json"].read_text(encoding="utf-8"))
        missing = payload.get("missing_unexplained_top8", [])
        if not missing or missing[0].get("keyword") != "Liderança de Operações":
            raise SystemExit(f"Repair request should register missing top8 keyword, got {payload}")
        if "4 e 8 experiências" not in " ".join(payload.get("repair_rules", [])):
            raise SystemExit(f"Repair rules should mention experience range, got {payload}")
        allowed, reason = applications_service._repair_decision(review_report, polish_report, state, applications_service.DEFAULT_CONFIG)
        if not allowed or reason != "missing_unexplained_top8":
            raise SystemExit(f"Repair decision should allow missing top8 remediation, got allowed={allowed} reason={reason}")


def phase_26() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    event_log = temp_root / "phase26_event_log.json"
    if event_log.exists():
        event_log.unlink()
    state = {
        "record_key": "999",
        "llm_session_count": 4,
        "llm_stage_attempts": {"analyze": 2, "generate": 1, "repair": 1},
    }
    remaining = applications_service._remaining_llm_sessions(state, applications_service.DEFAULT_CONFIG)
    if remaining != 0:
        raise SystemExit(f"Expected zero remaining LLM sessions, got {remaining}")
    try:
        applications_service._consume_llm_session_budget(
            state,
            applications_service.DEFAULT_CONFIG,
            stage="repair",
            paths={"event_log": event_log},
        )
        raise SystemExit("LLM budget guard should have blocked an extra session.")
    except SystemExit as exc:
        if "budget exhausted" not in str(exc):
            raise


def phase_27() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        request_path = Path(tmp_dir) / "request.md"
        request_path.write_text("# Request\n", encoding="utf-8")
        runner = SubprocessAgentRunner(ROOT)

        hermes_command = runner.build_command(
            AgentRunRequest(
                stage="analyze",
                record_key="901",
                request_path=request_path,
                instruction="Grave somente o draft.",
                runner_config={"command": "hermes", "agent": "build", "timeout_minutes": 90},
                model="provider/model",
                variant="medium",
            )
        )
        if Path(hermes_command[0]).name != "hermes":
            raise SystemExit(f"Hermes runner should resolve hermes executable, got {hermes_command}")
        if "--model" not in hermes_command or "provider/model" not in hermes_command:
            raise SystemExit(f"Hermes runner should forward model, got {hermes_command}")
        if "-z" not in hermes_command or "request.md" not in hermes_command[-1]:
            raise SystemExit(f"Hermes runner should send a file-scoped prompt, got {hermes_command}")

        opencode_command = runner.build_command(
            AgentRunRequest(
                stage="generate",
                record_key="902",
                request_path=request_path,
                instruction="Grave somente os artefatos textuais.",
                runner_config={
                    "command": "custom-harness",
                    "kind": "opencode",
                    "agent": "build",
                    "timeout_minutes": 90,
                },
                model="provider/model",
                variant="medium",
            )
        )
        expected_parts = {"run", "--agent", "build", "--file", "--title", "--model", "--variant"}
        if not expected_parts.issubset(set(opencode_command)):
            raise SystemExit(f"OpenCode-style runner command is incomplete: {opencode_command}")
        if str(request_path) not in opencode_command:
            raise SystemExit(f"OpenCode-style runner should receive request path, got {opencode_command}")


def phase_28() -> None:
    supervisor = HarnessSupervisor()
    cases = [
        ("abrir menu", "menu", {}),
        ("olá", "menu", {}),
        ("Avalie vaga Notion 316", "notion_job_analysis", {"record_id": 316}),
        ("processar fila de candidaturas", "applications_heartbeat", {}),
        ("gere um currículo para a vaga ativa", "cv", {}),
        ("gere um CV", "cv", {}),
        ("faça uma carta de apresentação", "cover_letter", {}),
        ("crie um draft de email", "email_draft", {}),
        ("atualize a vaga no Notion", "notion_update", {}),
        ("https://www.linkedin.com/jobs/view/4405127989/", "linkedin_job_intake", {}),
        ("listar minhas vagas salvas", "linkedin_saved_jobs", {}),
    ]
    for message, expected_workflow, expected_parameters in cases:
        decision = supervisor.classify(message)
        if decision.workflow != expected_workflow:
            raise SystemExit(
                f"Harness route mismatch for {message!r}: expected {expected_workflow}, got {decision.to_dict()}"
            )
        for key, value in expected_parameters.items():
            if (decision.parameters or {}).get(key) != value:
                raise SystemExit(f"Harness route parameters mismatch for {message!r}: {decision.to_dict()}")
    if not supervisor.classify("crie um draft de email").requires_approval:
        raise SystemExit("Email workflow must require explicit approval.")
    if not supervisor.classify("atualize a vaga no Notion").requires_approval:
        raise SystemExit("Notion write workflow must require explicit approval.")


def phase_29() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        root = Path(tmp_dir)
        app_dir = root / ".career-state" / "applications_v2" / "903"
        app_dir.mkdir(parents=True)
        allowed = app_dir / "fit_map.draft.json"
        forbidden = app_dir / "manifest.json"
        allowed.write_text("{}", encoding="utf-8")
        forbidden.write_text("{}", encoding="utf-8")
        request_json = app_dir / "analysis_request.json"
        request_md = app_dir / "analysis_request.md"
        request_json.write_text(
            json.dumps(
                {
                    "outputs": {
                        "allowed_files": [str(allowed.relative_to(root))],
                    }
                }
            ),
            encoding="utf-8",
        )
        request_md.write_text("# Analyze\n", encoding="utf-8")
        run = HarnessRunStore(root, app_dir).begin("analyze", request_json, request_md)
        allowed.write_text('{"ok": true}', encoding="utf-8")
        validation = run.inspect()
        if validation.get("status") != "ok":
            raise SystemExit(f"Allowed output should pass isolation: {validation}")
        forbidden.write_text('{"changed": true}', encoding="utf-8")
        validation = run.inspect()
        if validation.get("status") != "blocked" or "manifest.json" not in validation.get("unauthorized_changes", []):
            raise SystemExit(f"Unauthorized output should be blocked: {validation}")
        run.finish({"returncode": 0, "stdout": "ok", "stderr": ""}, validation)
        required = ["manifest.json", "request.json", "request.md", "result.json", "validation.json", "stdout.log", "stderr.log"]
        missing = [name for name in required if not (run.run_dir / name).exists()]
        if missing:
            raise SystemExit(f"Versioned run archive is incomplete: {missing}")


def phase_39() -> None:
    class FakeRunner:
        def build_command(self, request):
            return ["fake-runner", request.stage, str(request.request_path)]

        def run(self, request):
            payload = json.loads(request.request_path.with_suffix(".json").read_text(encoding="utf-8"))
            raw_outputs = []
            if isinstance(payload.get("outputs"), dict):
                raw_outputs.extend(payload["outputs"].get("allowed_files", []))
            if isinstance(payload.get("required_output"), dict):
                raw_outputs.extend(payload["required_output"].values())
            raw_outputs.extend(payload.get("allowed_outputs", []))
            for item in raw_outputs:
                output = ROOT / item
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text("{}", encoding="utf-8")
            return AgentRunResult(command=self.build_command(request), returncode=0, stdout="ok", stderr="")

    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        app_dir = Path(tmp_dir) / "904"
        app_dir.mkdir()
        supervisor = HarnessSupervisor(ROOT, runner=FakeRunner())
        stage_contracts = {
            "analyze": {"outputs": {"allowed_files": [str((app_dir / "fit_map.draft.json").relative_to(ROOT))]}},
            "generate": {"required_output": {"cv_content_path": str((app_dir / "cv_content.json").relative_to(ROOT))}},
            "repair": {"allowed_outputs": [str((app_dir / "cv_content.json").relative_to(ROOT))]},
        }
        for stage, contract in stage_contracts.items():
            request_json = app_dir / f"{stage}_request.json"
            request_md = app_dir / f"{stage}_request.md"
            request_json.write_text(json.dumps(contract), encoding="utf-8")
            request_md.write_text(f"# {stage}\n", encoding="utf-8")
            result = supervisor.run_application_stage(
                stage=stage,
                record_key="904",
                application_dir=app_dir,
                request_json=request_json,
                request_md=request_md,
                runner_config={"command": "fake-runner"},
            )
            if result.get("returncode") != 0 or result.get("isolation", {}).get("status") != "ok":
                raise SystemExit(f"Supervisor stage failed for {stage}: {result}")
            if not (ROOT / result["run_dir"] / "validation.json").exists():
                raise SystemExit(f"Supervisor did not archive validation for {stage}: {result}")


def phase_40() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        lock_path = Path(tmp_dir) / "heartbeat.lock"
        with ExclusiveRunLock(lock_path, "test heartbeat"):
            try:
                with ExclusiveRunLock(lock_path, "test heartbeat"):
                    raise SystemExit("Second heartbeat lock should not have been acquired.")
            except ValidationFailure as exc:
                if "already running" not in str(exc):
                    raise
        with ExclusiveRunLock(lock_path, "test heartbeat"):
            pass


def phase_30() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        root = Path(tmp_dir)
        store = ApprovalStore(root)
        pending = store.create("notion-update", {"request_id": "abc"})
        if pending.get("status") != "pending":
            raise SystemExit(f"Approval should start pending: {pending}")
        approved = store.approve(pending["approval_id"])
        if approved.get("status") != "approved":
            raise SystemExit(f"Approval should become approved: {approved}")
        consumed = store.consume(pending["approval_id"])
        if consumed.get("status") != "consumed":
            raise SystemExit(f"Approval should become consumed: {consumed}")

    supervisor = HarnessSupervisor(ROOT)
    prepared = supervisor.prepare_specialist("fit-map", objective="Test request versioning")
    request = prepared.get("request", {})
    if not request.get("request_id"):
        raise SystemExit(f"Specialist request should have request_id: {prepared}")
    versioned_json = ROOT / request["versioned_request_json"]
    versioned_md = ROOT / request["versioned_request_md"]
    if not versioned_json.exists() or not versioned_md.exists():
        raise SystemExit(f"Versioned specialist request is missing: {prepared}")
    email = supervisor.prepare_specialist("email-draft", objective="Test approval")
    if email.get("approval", {}).get("status") != "pending":
        raise SystemExit(f"Email specialist should create pending approval: {email}")


def phase_31() -> None:
    parser = build_parser()
    routed = parser.parse_args(["harness", "route", "--message", "gere um CV"])
    if routed.command != "harness" or routed.action != "route":
        raise SystemExit(f"Harness route CLI was not parsed correctly: {routed}")
    handled = parser.parse_args(
        ["harness", "handle", "--message", "processar fila", "--channel", "telegram", "--max-per-run", "1"]
    )
    if handled.channel != "telegram" or handled.max_per_run != 1:
        raise SystemExit(f"Harness handle CLI options were not parsed correctly: {handled}")
    habilidades = HarnessSupervisor(ROOT).prepare_specialist("habilidades", objective="Test habilidades request")
    if habilidades.get("request", {}).get("step") != "habilidades":
        raise SystemExit(f"Habilidades specialist is not available: {habilidades}")


def phase_32() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        root = Path(tmp_dir)
        (root / ".career-state").mkdir()
        run_dir = root / ".career-state" / "agent_requests" / "runs" / "run1"
        run = begin_specialist_run(root, run_dir, [".career-state/fit_map.draft.json"])
        allowed = root / ".career-state" / "fit_map.draft.json"
        allowed.write_text("{}", encoding="utf-8")
        validation = run.inspect()
        if validation.get("status") != "ok" or not validation.get("allowed_changed_files"):
            raise SystemExit(f"Specialist allowed output should pass: {validation}")
        forbidden = root / ".career-state" / "unexpected.json"
        forbidden.write_text("{}", encoding="utf-8")
        validation = run.inspect()
        if validation.get("status") != "blocked":
            raise SystemExit(f"Specialist unexpected output should be blocked: {validation}")
        run.finish({"returncode": 0, "stdout": "", "stderr": ""}, validation)


def phase_33() -> None:
    runner = SubprocessAgentRunner(ROOT)
    request_path = ROOT / ".career-state" / "agent_requests" / "fit-map_request.md"
    codex = runner.build_command(
        AgentRunRequest(
            stage="fit-map",
            record_key="905",
            request_path=request_path,
            instruction="Execute somente a etapa.",
            runner_config={"command": "codex", "kind": "codex", "timeout_minutes": 30},
            model="gpt-5.4",
        )
    )
    required = {"exec", "--ephemeral", "--sandbox", "workspace-write", "-C", "--model", "gpt-5.4"}
    if not required.issubset(set(codex)):
        raise SystemExit(f"Codex runner command is incomplete: {codex}")
    if "fit-map_request.md" not in codex[-1]:
        raise SystemExit(f"Codex runner should receive file-scoped prompt: {codex}")
    try:
        runner.build_command(
            AgentRunRequest(
                stage="fit-map",
                record_key="906",
                request_path=request_path,
                instruction="x",
                runner_config={"command": "unknown-runner", "kind": "unknown"},
            )
        )
        raise SystemExit("Unknown runner kind should be rejected.")
    except ValueError:
        pass


def phase_34() -> None:
    class FakeSupervisor:
        def __init__(self):
            self.calls = 0

        def handle_message(self, message, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return {"status": "blocked", "blocker_reason": "no_deterministic_route"}
            return {"status": "completed", "message": message, "kwargs": kwargs}

    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        supervisor = FakeSupervisor()
        first = telegram_harness_adapter.process_message(
            "status das candidaturas",
            message_id="telegram-1",
            execute=False,
            supervisor=supervisor,
            root=Path(tmp_dir),
        )
        second = telegram_harness_adapter.process_message(
            "status das candidaturas",
            message_id="telegram-1",
            execute=False,
            supervisor=supervisor,
            root=Path(tmp_dir),
        )
        third = telegram_harness_adapter.process_message(
            "status das candidaturas",
            message_id="telegram-1",
            execute=False,
            supervisor=supervisor,
            root=Path(tmp_dir),
        )
        if supervisor.calls != 2:
            raise SystemExit(f"Telegram adapter should retry transient blocked cache exactly once, calls={supervisor.calls}")
        if first.get("deduplicated") or second.get("deduplicated") or not third.get("deduplicated"):
            raise SystemExit(f"Telegram deduplication flags are incorrect: first={first}, second={second}, third={third}")


def phase_35() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        config = Path(tmp_dir) / "config.yaml"
        config.write_text("model:\n  default: test\nhooks: {}\n", encoding="utf-8")
        dry_run = install_hermes_harness_hook.install(config, apply=False)
        if dry_run.get("status") != "dry_run_ok" or "pre_llm_call" in config.read_text(encoding="utf-8"):
            raise SystemExit(f"Hermes hook dry-run should not edit config: {dry_run}")
        applied = install_hermes_harness_hook.install(config, apply=True)
        payload = __import__("yaml").safe_load(config.read_text(encoding="utf-8"))
        if applied.get("status") != "installed" or not payload.get("hooks", {}).get("pre_llm_call"):
            raise SystemExit(f"Hermes hook install failed: {applied}")
        command = payload["hooks"]["pre_llm_call"][0]["command"]
        if len(shlex.split(command)) != 2:
            raise SystemExit(f"Hermes hook command must survive spaces in paths: {command}")
        if not config.with_suffix(".yaml.bak.harness").exists():
            raise SystemExit("Hermes hook installer should create a backup.")


def phase_36() -> None:
    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return Result()

    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        root = Path(tmp_dir)
        notion_action = root / "notion.json"
        notion_action.write_text(
            json.dumps({"kind": "notion", "command": ["npm", "run", "notion:create-current"]}),
            encoding="utf-8",
        )
        result = ApprovedActionExecutor(root, run_command=fake_run).execute(notion_action)
        if result.get("status") != "completed" or not calls:
            raise SystemExit(f"Approved Notion action should execute: {result}")
        forbidden = root / "forbidden.json"
        forbidden.write_text(
            json.dumps({"kind": "notion", "command": ["rm", "-rf", "/"]}),
            encoding="utf-8",
        )
        try:
            ApprovedActionExecutor(root, run_command=fake_run).execute(forbidden)
            raise SystemExit("Forbidden approved action should be rejected.")
        except ValidationFailure:
            pass


def phase_37() -> None:
    supervisor = HarnessSupervisor()
    long_body = (
        "Empresa: Acme\nCargo: Head de Operações\nAnalise esta vaga\n"
        + "Responsabilidades e requisitos operacionais. " * 20
    )
    decision = supervisor.classify(long_body)
    if decision.workflow != "pasted_job_intake":
        raise SystemExit(f"Long pasted job should route through intake: {decision.to_dict()}")
    if (decision.parameters or {}).get("company") != "Acme":
        raise SystemExit(f"Pasted job company was not extracted: {decision.to_dict()}")
    missing = supervisor.classify("Analise esta vaga\n" + "Requisitos da vaga. " * 40)
    if missing.workflow != "pasted_job_missing_metadata":
        raise SystemExit(f"Long pasted job without metadata should block intake: {missing.to_dict()}")
    post = supervisor.classify(
        "Empresa: Acme\nCargo: Gerente\nhttps://www.linkedin.com/posts/example-123"
    )
    if post.workflow != "linkedin_post_intake" or not (post.parameters or {}).get("company"):
        raise SystemExit(f"LinkedIn post metadata was not extracted: {post.to_dict()}")


def phase_38() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "891"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        paths["fit_map"].write_text(
            json.dumps(
                {
                    "cargo": "Head of Operations",
                    "empresa": "BRL1 Network",
                    "keywords_habilidade_ats": [
                        {"keyword": "Gestão de Operações", "prioridade": 1},
                        {"keyword": "Planejamento Integrado", "prioridade": 2},
                        {"keyword": "Indicadores", "prioridade": 3},
                        {"keyword": "Liderança", "prioridade": 4},
                        {"keyword": "S&OP", "prioridade": 5},
                        {"keyword": "MRP", "prioridade": 6},
                        {"keyword": "OTIF", "prioridade": 7},
                        {"keyword": "Custos", "prioridade": 8},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        paths["cv_content"].write_text(
            json.dumps(
                {
                    "summary": "Executivo com 180+ POPs de validação regulatória e R$8MM de redução de GGF.",
                    "mode": "concise",
                    "experiences": [
                        {"role": "A", "company": "X", "period": "1", "bullets": [{"text": "b1"}, {"text": "b2 mecanismo com dados para resultado"}, {"text": "b3 resultado"}]},
                        {"role": "B", "company": "Y", "period": "2", "bullets": [{"text": "b1"}, {"text": "b2 mecanismo com dados para resultado"}, {"text": "Reduzi R$8MM em GGF."}]},
                        {"role": "C", "company": "Z", "period": "3", "bullets": [{"text": "b1"}, {"text": "b2 mecanismo com dados para resultado"}, {"text": "b3 resultado"}]},
                        {"role": "D", "company": "W", "period": "4", "bullets": [{"text": "b1"}, {"text": "b2 mecanismo com dados para resultado"}, {"text": "b3 resultado"}]},
                    ],
                    "ats_keyword_coverage": [
                        {"keyword": "Gestão de Operações", "experience_index": 0, "experience_role": "A", "bullet_index": 0, "coverage_mode": "exact", "defensible_evidence": "b1"},
                        {"keyword": "Planejamento Integrado", "experience_index": 1, "experience_role": "B", "bullet_index": 1, "coverage_mode": "exact", "defensible_evidence": "b2 mecanismo com dados para resultado"},
                        {"keyword": "Indicadores", "experience_index": 1, "experience_role": "B", "bullet_index": 2, "coverage_mode": "exact", "defensible_evidence": "Reduzi R$8MM em GGF."},
                        {"keyword": "Liderança", "experience_index": 2, "experience_role": "C", "bullet_index": 0, "coverage_mode": "exact", "defensible_evidence": "b1"},
                        {"keyword": "S&OP", "experience_index": 2, "experience_role": "C", "bullet_index": 1, "coverage_mode": "exact", "defensible_evidence": "b2 mecanismo com dados para resultado"},
                        {"keyword": "MRP", "experience_index": 2, "experience_role": "C", "bullet_index": 2, "coverage_mode": "exact", "defensible_evidence": "b3 resultado"},
                        {"keyword": "OTIF", "experience_index": 3, "experience_role": "D", "bullet_index": 0, "coverage_mode": "exact", "defensible_evidence": "b1"},
                        {"keyword": "Custos", "experience_index": 3, "experience_role": "D", "bullet_index": 2, "coverage_mode": "exact", "defensible_evidence": "b3 resultado"},
                    ],
                    "summary_support": [
                        {
                            "summary_fragment": "R$8MM de redução de GGF",
                            "experience_index": 1,
                            "experience_role": "B",
                            "experience_company": "Y",
                            "bullet_index": 2,
                            "defensible_evidence": "Reduzi R$8MM em GGF.",
                        },
                        {
                            "summary_fragment": "180+ POPs de validação regulatória",
                            "experience_index": 0,
                            "experience_role": "A",
                            "experience_company": "X",
                            "bullet_index": 2,
                            "defensible_evidence": "b3 resultado",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        try:
            applications_service._validate_cv_content_contract(paths)
        except ValidationFailure as exc:
            if "summary fragment not found in summary" in str(exc):
                raise SystemExit(f"Unexpected summary_support validation failure ordering: {exc}")
            if "mapped bullet does not contain factual anchors" not in str(exc):
                raise SystemExit(f"Unexpected validation error for summary_support contract: {exc}")
        else:
            raise SystemExit("cv_content contract should block summary fragments that are not backed by the mapped experience bullet")


def phase_41() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        root = Path(tmp_dir)
        state_dir = root / ".career-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "workflow_state.json").write_text(json.dumps({}), encoding="utf-8")
        supervisor = HarnessSupervisor(root)
        menu = supervisor.handle_message("menu", channel="cli", execute=True)
        result = menu.get("result") if isinstance(menu.get("result"), dict) else {}
        if result.get("kind") != "session_menu":
            raise SystemExit(f"Menu payload missing session_menu kind: {menu}")
        display = str(result.get("display_text") or "")
        if "Responda com o número da opção" not in display:
            raise SystemExit(f"Menu display text was not rendered: {display}")
        if (result.get("numbered_items") or [{}])[0].get("id") != "linkedin_saved_jobs":
            raise SystemExit(f"No-active-intake menu should start with an executable source: {result}")
        collect = supervisor.handle_message("2", channel="telegram", execute=True)
        collect_result = collect.get("result") if isinstance(collect.get("result"), dict) else {}
        if collect_result.get("input_kind") != "notion_id":
            raise SystemExit(f"Notion menu selection should request its missing ID: {collect}")
        routed = supervisor.handle_message("270", channel="telegram", execute=False)
        decision = routed.get("decision") if isinstance(routed.get("decision"), dict) else {}
        if decision.get("workflow") != "notion_job_analysis":
            raise SystemExit(f"Pending Notion ID did not resume the intended route: {routed}")
        supervisor._write_saved_jobs_menu_state(
            [
                {
                    "jobId": "4422954585",
                    "title": "Operations Manager",
                    "company": "Acme",
                    "location": "São Paulo",
                    "url": "https://www.linkedin.com/jobs/view/4422954585/",
                }
            ]
        )
        saved_selection = supervisor.handle_message("1", channel="telegram", execute=False)
        saved_decision = saved_selection.get("decision") if isinstance(saved_selection.get("decision"), dict) else {}
        if saved_decision.get("workflow") != "linkedin_job_intake":
            raise SystemExit(f"Saved-job number should route to its freshly extracted URL: {saved_selection}")
        exact = hermes_harness_context_hook.build_context({"reply_text": "Texto exato"})
        if exact != "O HarnessSupervisor ja processou esta mensagem. Responda somente: OK":
            raise SystemExit(f"Hermes deterministic reply should use a harmless placeholder: {exact}")
        pending_path = root / ".career-state" / "harness" / "pending_input.json"
        pending_path.unlink(missing_ok=True)
        original_root = hermes_harness_context_hook.ROOT
        hermes_harness_context_hook.ROOT = root
        try:
            if hermes_harness_context_hook.should_intercept("como você está?"):
                raise SystemExit("Ordinary conversation should remain with the outer Hermes agent.")
            if not hermes_harness_context_hook.should_intercept("olá"):
                raise SystemExit("A greeting should open the conversational menu.")
        finally:
            hermes_harness_context_hook.ROOT = original_root


def phase_42() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        root = Path(tmp_dir)
        state_dir = root / ".career-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "workflow_state.json").write_text(json.dumps({}), encoding="utf-8")
        supervisor = HarnessSupervisor(root)
        supervisor._write_saved_jobs_menu_state(
            [
                {
                    "jobId": "4431478354",
                    "title": "Gestor de Planejamento Operacional e Financeiro",
                    "company": "Loft",
                    "location": "São Paulo",
                    "url": "https://www.linkedin.com/jobs/view/4431478354/",
                }
            ]
        )
        from career.services import intake as intake_service

        original = intake_service.from_linkedin_job
        intake_service.from_linkedin_job = lambda _url, state_store=None, *, metadata_hints=None: (_ for _ in ()).throw(
            ValidationFailure("LinkedIn extraction produced generic metadata.")
        )
        try:
            result = supervisor.handle_message("1", channel="telegram", execute=True)
        finally:
            intake_service.from_linkedin_job = original
        payload = result.get("result") if isinstance(result.get("result"), dict) else {}
        if result.get("status") != "blocked":
            raise SystemExit(f"Harness should convert intake validation failures into blocked results: {result}")
        if payload.get("blocker_reason") != "workflow_validation_failed":
            raise SystemExit(f"Harness should preserve a deterministic blocker reason: {result}")
        if payload.get("display_text") != "LinkedIn extraction produced generic metadata.":
            raise SystemExit(f"Harness should surface the validation failure text to the user: {result}")


def phase_43() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        root = Path(tmp_dir)
        state_dir = root / ".career-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        stale_state = {
            "active_intake": {
                "source_type": "pasted_text",
                "source_id": None,
                "company": "Fiorde Logística Internacional",
                "role": "Gerente de Logística Nacional",
                "job_description_path": "inbox/job_descriptions/fiorde.md",
                "next_required_step": "fill_fit_map_draft",
                "status": "ready_for_model_analysis",
                "updated_at": "2026-06-20T12:00:00+00:00",
            }
        }
        (state_dir / "workflow_state.json").write_text(json.dumps(stale_state), encoding="utf-8")
        supervisor = HarnessSupervisor(root)
        menu = supervisor.handle_message("olá", channel="telegram", execute=True)
        result = menu.get("result") if isinstance(menu.get("result"), dict) else {}
        if result.get("menu_context") != "no_active_job":
            raise SystemExit(f"Stale active intake should not dominate the greeting menu: {menu}")
        if not result.get("stale_active_intake"):
            raise SystemExit(f"Stale active intake should still be exposed as optional resume context: {menu}")
        display = str(result.get("display_text") or "")
        if "Trabalho antigo detectado" not in display:
            raise SystemExit(f"Stale intake should be announced as old work in display text: {display}")


def phase_44() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        root = Path(tmp_dir)
        state_dir = root / ".career-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "workflow_state.json").write_text(json.dumps({}), encoding="utf-8")
        supervisor = HarnessSupervisor(root)
        supervisor._write_saved_jobs_menu_state(
            [
                {
                    "jobId": "4431478354",
                    "title": "Gestor de Planejamento Operacional e Financeiro",
                    "company": "Loft",
                    "location": "São Paulo",
                    "url": "https://www.linkedin.com/jobs/view/4431478354/",
                }
            ]
        )
        result = supervisor.handle_message("17", channel="telegram", execute=True)
        payload = result.get("result") if isinstance(result.get("result"), dict) else {}
        if result.get("status") != "blocked":
            raise SystemExit(f"Unknown numeric menu selection should block deterministically: {result}")
        if payload.get("blocker_reason") != "menu_selection_not_found":
            raise SystemExit(f"Unknown numeric menu selection should preserve blocker reason: {result}")
        if "Esse número não existe no menu atual." not in str(payload.get("display_text") or ""):
            raise SystemExit(f"Unknown numeric menu selection should explain the mismatch: {result}")


def phase_45() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        root = Path(tmp_dir)
        state_dir = root / ".career-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "workflow_state.json").write_text(json.dumps({}), encoding="utf-8")
        supervisor = HarnessSupervisor(root)
        supervisor._write_saved_jobs_menu_state(
            [
                {
                    "jobId": "4402585997",
                    "title": "Gerente de Operações Logísticas (PJ)",
                    "company": "To Do Green",
                    "location": "São Paulo, SP (Presencial)",
                    "url": "https://www.linkedin.com/jobs/view/4402585997/",
                }
            ]
        )
        captured: dict[str, Any] = {}
        from career.services import intake as intake_service

        original_from_linkedin_job = intake_service.from_linkedin_job
        original_execute_specialist = supervisor.execute_specialist

        def fake_from_linkedin_job(url: str, state_store=None, *, metadata_hints=None):
            captured["url"] = url
            captured["metadata_hints"] = metadata_hints
            return {"status": "ready_for_model_analysis"}

        supervisor.execute_specialist = lambda *args, **kwargs: {"status": "completed"}
        intake_service.from_linkedin_job = fake_from_linkedin_job
        try:
            supervisor.handle_message("1", channel="telegram", execute=True)
        finally:
            supervisor.execute_specialist = original_execute_specialist
            intake_service.from_linkedin_job = original_from_linkedin_job
        if captured.get("url") != "https://www.linkedin.com/jobs/view/4402585997/":
            raise SystemExit(f"Saved-job selection should route to the chosen URL: {captured}")
        if captured.get("metadata_hints") != {
            "role": "Gerente de Operações Logísticas (PJ)",
            "company": "To Do Green",
            "location": "São Paulo, SP (Presencial)",
        }:
            raise SystemExit(f"Saved-job selection should forward metadata hints into intake: {captured}")


PHASES = {
    1: phase_1,
    2: phase_2,
    3: phase_3,
    4: phase_4,
    5: phase_5,
    6: phase_6,
    7: phase_7,
    8: phase_8,
    9: phase_9,
    10: phase_10,
    11: phase_11,
    12: phase_12,
    13: phase_13,
    14: phase_14,
    15: phase_15,
    16: phase_16,
    17: phase_17,
    18: phase_18,
    19: phase_19,
    20: phase_20,
    21: phase_21,
    22: phase_22,
    23: phase_23,
    24: phase_24,
    25: phase_25,
    26: phase_26,
    27: phase_27,
    28: phase_28,
    29: phase_29,
    30: phase_30,
    31: phase_31,
    32: phase_32,
    33: phase_33,
    34: phase_34,
    35: phase_35,
    36: phase_36,
    37: phase_37,
    38: phase_38,
    39: phase_39,
    40: phase_40,
    41: phase_41,
    42: phase_42,
    43: phase_43,
    44: phase_44,
    45: phase_45,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, choices=sorted(PHASES), required=True)
    args = parser.parse_args()
    PHASES[args.phase]()
    print(json.dumps({"phase": args.phase, "status": "ok"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
