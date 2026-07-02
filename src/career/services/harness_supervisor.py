from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from typing import Any

from career.paths import CAREER_STATE
from career.services.agent_runner import AgentRunRequest, SubprocessAgentRunner
from career.services.approvals import ApprovalStore
from career.services.approved_actions import ApprovedActionExecutor
from career.services.harness_runs import HarnessRunStore, begin_specialist_run
from career.utils import ValidationFailure, read_json, utc_now_iso


LINKEDIN_JOB_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/(?:jobs(?:/view)?|job)/[^\s]+", re.IGNORECASE)
LINKEDIN_POST_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:feed/update|posts|pulse)/[^\s]+",
    re.IGNORECASE,
)
GENERIC_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
NOTION_ID_RE = re.compile(r"\b(?:notion|vaga|id)\s*#?\s*(\d+)\b", re.IGNORECASE)

SPECIALIST_OUTPUT_PATTERNS = {
    "fit-map": [
        ".career-state/fit_map.draft.json",
        ".career-state/workflow_state.json",
    ],
    "cv": [
        ".career-state/cv_content.json",
        "outputs/*.docx",
        "outputs/_tmp/output_review_report.json",
        "outputs/_tmp/polish_review.json",
        "outputs/_tmp/delivery_report.json",
    ],
    "cover-letter": ["outputs/*.md", "outputs/*.pdf", "outputs/_tmp/delivery_report.json"],
    "feras": ["outputs/*.md"],
    "habilidades": ["outputs/*.md"],
    "notion-update": [
        ".career-state/pending_actions/*.json",
        ".career-state/derived/active_context.json",
        ".career-state/derived/job_extract.json",
        ".career-state/derived/manifest.json",
        ".career-state/derived/keyword_ats_registry.json",
        ".career-state/derived/keyword_translation_candidates.json",
        "inbox/job_descriptions/*.md",
    ],
    "email-draft": [".career-state/pending_actions/*.json"],
    "linkedin": [
        ".career-state/linkedin_job_extract.json",
        ".career-state/linkedin_post_extract.json",
        ".career-state/workflow_state.json",
        "inbox/job_descriptions/*.md",
        "inbox/linkedin_posts/*.md",
    ],
}

ACTIVE_INTAKE_STALE_AFTER = timedelta(hours=24)
DEFAULT_HARNESS_AUTOMATION = {
    "fit_map": {
        "auto_finalize": True,
    },
    "approvals": {
        "notion_write": "explicit_request",
        "email_draft": "manual",
    },
}
PREVIEW_HINTS = (
    "dry-run",
    "dry run",
    "prévia",
    "previa",
    "preview",
    "sem escrever",
    "sem atualizar",
    "nao atualizar",
    "não atualizar",
    "so mostrar",
    "só mostrar",
)


@dataclass(frozen=True)
class DispatchDecision:
    workflow: str
    stage: str
    confidence: str
    reason: str
    requires_approval: bool = False
    parameters: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parameters"] = self.parameters or {}
        return payload


class HarnessSupervisor:
    """Deterministic front door shared by CLI, chat harnesses and Telegram."""

    def __init__(self, root: Path | None = None, runner: SubprocessAgentRunner | None = None):
        self.root = root
        self.runner = runner or (SubprocessAgentRunner(root) if root else None)

    def classify(self, message: str) -> DispatchDecision:
        raw_text = str(message or "").strip()
        text = " ".join(raw_text.split())
        lowered = text.casefold()
        if not text:
            return self._decision("help", "route", "high", "empty_message")

        if self._is_menu_request(lowered):
            return self._decision("menu", "menu", "high", "session_menu_request")

        selection = self._resolve_menu_selection(text)
        if selection:
            return self.classify(selection["prompt"])
        invalid_selection = self._invalid_menu_selection(text)
        if invalid_selection:
            return self._decision("invalid_menu_selection", "conversation", "high", invalid_selection)

        if self._is_runtime_introspection(lowered):
            return self._decision(
                "runtime_introspection",
                "status",
                "high",
                "runtime_introspection_request",
            )

        analysis_requested = any(
            token in lowered for token in ("avali", "analis", "aderencia", "aderência", "fit_map", "fit map")
        )

        job_match = LINKEDIN_JOB_RE.search(text)
        if job_match:
            return self._decision(
                "linkedin_job_intake",
                "intake",
                "high",
                "linkedin_job_url",
                parameters={"url": job_match.group(0)},
            )

        post_match = LINKEDIN_POST_RE.search(text)
        if post_match:
            company, role = self._company_role(raw_text)
            return self._decision(
                "linkedin_post_intake",
                "intake",
                "high",
                "linkedin_post_url",
                parameters={"url": post_match.group(0), "company": company, "role": role},
            )

        generic_url_match = GENERIC_URL_RE.search(text)
        if generic_url_match:
            company, role = self._company_role(raw_text)
            return self._decision(
                "external_url_intake",
                "intake",
                "high" if analysis_requested or text == generic_url_match.group(0) else "medium",
                "generic_job_url",
                parameters={"url": generic_url_match.group(0), "company": company, "role": role},
            )

        if any(token in lowered for token in ("vagas salvas", "saved jobs", "rastreador de vagas")):
            return self._decision("linkedin_saved_jobs", "intake", "high", "linkedin_saved_jobs_request")

        if any(
            phrase in lowered
            for phrase in (
                "continue o trabalho em andamento",
                "retomar trabalho em andamento",
                "retome o trabalho em andamento",
                "continue de onde parou",
            )
        ):
            return self._decision("resume", "resume", "high", "resume_active_workflow_request")

        if "heartbeat" in lowered or any(
            phrase in lowered for phrase in ("processar fila", "rodar fila", "executar fila", "processar candidaturas")
        ):
            return self._decision("applications_heartbeat", "orchestrate", "high", "queue_processing_request")

        if any(phrase in lowered for phrase in ("status das candidaturas", "status da fila", "applications status")):
            return self._decision("applications_status", "status", "high", "applications_status_request")

        notion_match = NOTION_ID_RE.search(text)
        if notion_match and any(token in lowered for token in ("avali", "analis", "fit", "aderencia", "aderência")):
            return self._decision(
                "notion_job_analysis",
                "intake",
                "high",
                "notion_record_analysis",
                parameters={"record_id": int(notion_match.group(1))},
            )

        if "notion" in lowered and any(token in lowered for token in ("avali", "analis", "fit")):
            return self._decision(
                "collect_notion_id", "conversation", "high", "notion_analysis_requires_record_id"
            )

        if "linkedin" in lowered and any(token in lowered for token in ("avali", "analis", "vaga")):
            return self._decision(
                "collect_linkedin_url", "conversation", "high", "linkedin_analysis_requires_url"
            )

        if any(phrase in lowered for phrase in ("colar vaga", "colar uma vaga", "enviar vaga em texto")):
            return self._decision(
                "collect_pasted_job", "conversation", "high", "pasted_job_requires_content"
            )

        if len(raw_text) >= 500 and analysis_requested:
            company, role = self._company_role(raw_text)
            if company and role:
                return self._decision(
                    "pasted_job_intake",
                    "intake",
                    "high",
                    "long_job_text_with_metadata",
                    parameters={"company": company, "role": role, "text": raw_text},
                )
            return self._decision(
                "pasted_job_missing_metadata",
                "intake",
                "high",
                "long_job_text_requires_company_and_role",
            )

        if any(token in lowered for token in ("email", "gmail")):
            return self._decision(
                "email_draft",
                "email-draft",
                "high",
                "email_request",
                requires_approval=True,
            )

        if "notion" in lowered and any(token in lowered for token in ("atualiz", "registre", "salve", "crie")):
            parameters: dict[str, Any] = {}
            if notion_match:
                parameters["record_id"] = int(notion_match.group(1))
            return self._decision(
                "notion_update",
                "notion-update",
                "high",
                "notion_write_request",
                requires_approval=True,
                parameters=parameters,
            )

        if any(token in lowered for token in ("curriculo", "currículo", "gerar cv", "adaptar cv")) or re.search(
            r"\bcv\b", lowered
        ):
            return self._decision("cv", "cv", "high", "cv_request")

        if any(token in lowered for token in ("carta de apresentacao", "carta de apresentação", "cover letter")):
            return self._decision("cover_letter", "cover-letter", "high", "cover_letter_request")

        if any(token in lowered for token in ("feras", "me fale sobre voce", "me fale sobre você", "pitch")):
            return self._decision("feras", "feras", "high", "feras_request")

        if any(token in lowered for token in ("gupy", "mercado livre", "habilidades", "resumo ats")):
            return self._decision("habilidades", "habilidades", "high", "skills_request")

        if analysis_requested:
            return self._decision("fit_map", "fit-map", "medium", "job_analysis_request")

        return self._decision("generic_assistant", "chat", "low", "no_deterministic_route")

    @staticmethod
    def _company_role(message: str) -> tuple[str | None, str | None]:
        company_match = re.search(r"(?im)^\s*empresa\s*:\s*(.+?)\s*$", message)
        role_match = re.search(r"(?im)^\s*(?:cargo|vaga)\s*:\s*(.+?)\s*$", message)
        company = company_match.group(1).strip() if company_match else None
        role = role_match.group(1).strip() if role_match else None
        return company, role

    def prepare_specialist(
        self,
        step: str,
        *,
        objective: str | None = None,
        extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from career.services import multiagent as multiagent_service

        request = multiagent_service.write_request(step, objective=objective, extras=extras)
        validation = multiagent_service.validate_request(step)
        result: dict[str, Any] = {
            "status": "prepared" if validation.get("status") == "ok" else "blocked",
            "step": step,
            "request": request,
            "validation": validation,
        }
        if step in {"notion-update", "email-draft"} and self.root:
            request_payload = read_json(self.root / request["versioned_request_json"])
            pending_action_path = (request_payload.get("extras") or {}).get("pending_action_path")
            approval = ApprovalStore(self.root).create(
                action=step,
                payload={
                    "request_id": request.get("request_id"),
                    "request_json": request.get("versioned_request_json"),
                    "request_md": request.get("versioned_request_md"),
                    "pending_action_path": pending_action_path,
                },
            )
            result["approval"] = {
                "approval_id": approval["approval_id"],
                "status": approval["status"],
            }
        return result

    def execute_approved_action(self, approval_id: str) -> dict[str, Any]:
        if not self.root:
            raise ValueError("HarnessSupervisor requires root to execute approved actions.")
        approvals = ApprovalStore(self.root)
        approval = approvals.get(approval_id)
        if approval.get("status") != "approved":
            return {
                "status": "blocked",
                "blocker_reason": "approval_not_approved",
                "approval": approval,
            }
        pending_path = str((approval.get("payload") or {}).get("pending_action_path") or "")
        if not pending_path:
            return {
                "status": "blocked",
                "blocker_reason": "pending_action_path_missing",
                "approval": approval,
            }
        result = ApprovedActionExecutor(self.root).execute(self.root / pending_path)
        consumed = approvals.consume(approval_id)
        return {"status": "completed", "approval": consumed, "result": result}

    def prepare_all_specialists(self) -> dict[str, Any]:
        from career.services import multiagent as multiagent_service

        return {
            "status": "prepared",
            "requests": [self.prepare_specialist(step) for step in multiagent_service.CONTRACTS],
        }

    def execute_specialist(
        self,
        step: str,
        *,
        objective: str | None = None,
        extras: dict[str, Any] | None = None,
        model: str | None = None,
        variant: str | None = None,
    ) -> dict[str, Any]:
        if not self.root or not self.runner:
            raise ValueError("HarnessSupervisor requires root and runner to execute specialists.")
        prepared = self.prepare_specialist(step, objective=objective, extras=extras)
        if prepared.get("validation", {}).get("status") != "ok":
            return prepared
        request = prepared["request"]
        request_json = self.root / request["versioned_request_json"]
        request_md = self.root / request["versioned_request_md"]
        run_dir = request_json.parent
        config_path = self.root / ".career-state" / "applications_v2" / "config.json"
        config = read_json(config_path) if config_path.exists() else {}
        runner_key = "analysis_runner" if step == "fit-map" else "generation_runner"
        runner_config = config.get(runner_key, {"command": "hermes", "agent": "build", "timeout_minutes": 90})
        active_model = model or str(config.get("active_model") or "")
        active_variant = variant or str(config.get("active_variant") or "")
        instruction = (
            "Leia o request anexado, execute somente esta etapa, grave os outputs permitidos "
            "e rode os comandos de validacao definidos no request."
        )
        run_request = AgentRunRequest(
            stage=step,
            record_key=str(request["request_id"]),
            request_path=request_md,
            instruction=instruction,
            runner_config=runner_config,
            model=active_model,
            variant=active_variant,
        )
        specialist_run = begin_specialist_run(
            self.root,
            run_dir,
            SPECIALIST_OUTPUT_PATTERNS.get(step, []),
        )
        command = self.runner.build_command(run_request)
        result = self.runner.run(run_request)
        isolation = specialist_run.inspect()
        payload = {
            "stage": step,
            "request_id": request["request_id"],
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "finished_at": utc_now_iso(),
            "run_dir": str(run_dir.relative_to(self.root)),
            "isolation": isolation,
        }
        specialist_run.finish(payload, isolation)
        status = "completed"
        if result.returncode != 0 or isolation.get("status") != "ok":
            status = "blocked"
        elif SPECIALIST_OUTPUT_PATTERNS.get(step) and not isolation.get("allowed_changed_files"):
            status = "blocked"
            payload["blocker_reason"] = "specialist_produced_no_allowed_output"
        elif step in {"notion-update", "email-draft"}:
            status = "awaiting_approval"
        if step == "fit-map" and status == "completed" and self._fit_map_auto_finalize_enabled():
            postprocess = self._finalize_fit_map_pipeline()
            payload["postprocess"] = postprocess
            if postprocess.get("status") != "completed":
                status = "blocked"
                payload["blocker_reason"] = str(postprocess.get("blocker_reason") or "fit_map_finalize_failed")
        if step in {"notion-update", "email-draft"} and status == "awaiting_approval":
            auto_execution = self._maybe_auto_execute_approved_action(step, objective=objective, prepared=prepared)
            if auto_execution:
                payload["approval_execution"] = auto_execution
                status = "completed" if auto_execution.get("status") == "completed" else "blocked"
                if status == "blocked":
                    payload["blocker_reason"] = str(
                        auto_execution.get("blocker_reason") or "approved_action_auto_execution_failed"
                    )
        return {
            **prepared,
            "status": status,
            "execution": payload,
        }

    def handle_message(
        self,
        message: str,
        *,
        channel: str = "cli",
        execute: bool = False,
        max_per_run: int | None = None,
        model: str | None = None,
        variant: str | None = None,
    ) -> dict[str, Any]:
        user_message = message
        pending = self._resolve_pending_input(message)
        if pending:
            message = str(pending["message"])
        selection = self._resolve_menu_selection(message)
        original_message = user_message
        if selection:
            input_request = self._menu_input_request(selection)
            if input_request:
                self._write_pending_input(input_request)
                return {
                    "status": "awaiting_input",
                    "channel": channel,
                    "message": original_message,
                    "decision": self._decision(
                        "collect_input", "conversation", "high", "menu_selection_requires_input"
                    ).to_dict(),
                    "menu_selection": selection,
                    "executed": False,
                    "result": input_request,
                }
            message = str(selection["prompt"])
        decision = self.classify(message)
        envelope: dict[str, Any] = {
            "status": "routed",
            "channel": channel,
            "message": original_message,
            "decision": decision.to_dict(),
            "executed": False,
        }
        if selection:
            envelope["menu_selection"] = selection
        if pending:
            envelope["pending_input"] = pending
        if not execute:
            return envelope

        workflow = decision.workflow
        try:
            if workflow == "menu":
                self._clear_pending_input()
                envelope["result"] = self._build_session_menu()
            elif workflow in {"collect_notion_id", "collect_linkedin_url", "collect_pasted_job"}:
                input_kind = {
                    "collect_notion_id": "notion_id",
                    "collect_linkedin_url": "linkedin_job_url",
                    "collect_pasted_job": "pasted_job",
                }[workflow]
                display_text = {
                    "notion_id": "Qual é o número da vaga no Notion? Pode responder somente com o número.",
                    "linkedin_job_url": "Envie a URL da vaga no LinkedIn.",
                    "pasted_job": (
                        "Cole a vaga com duas linhas no início: Empresa: nome e Cargo: nome. "
                        "Depois inclua a descrição completa."
                    ),
                }[input_kind]
                request = {
                    "status": "awaiting_input",
                    "kind": "input_request",
                    "input_kind": input_kind,
                    "display_text": display_text,
                }
                self._write_pending_input(request)
                envelope["result"] = request
            elif workflow == "resume":
                envelope["result"] = self._resume_and_continue(message, model=model, variant=variant)
            elif workflow == "applications_status":
                from career.services import applications_v2 as applications_service

                envelope["result"] = applications_service.heartbeat_status()
            elif workflow == "applications_heartbeat":
                from career.services import applications_v2 as applications_service

                envelope["result"] = applications_service.run_heartbeat(
                    applications_service.HeartbeatV2Options(
                        max_per_run=max_per_run,
                        run_agent=True,
                        dry_run=False,
                        model=model,
                        variant=variant,
                    )
                )
            elif workflow == "notion_job_analysis":
                from career.services import agent_guard as agent_guard_service

                record_id = int((decision.parameters or {})["record_id"])
                intake_result = agent_guard_service.evaluate_notion(record_id)
                envelope["result"] = self._pipeline_result(
                    intake=intake_result,
                    specialist=self.execute_specialist(
                        "fit-map", objective=f"Avaliar vaga Notion {record_id}", model=model, variant=variant
                    ),
                )
            elif workflow == "linkedin_job_intake":
                from career.services import intake as intake_service

                hints = self._saved_job_metadata_hints(selection)
                intake_result = intake_service.from_linkedin_job(
                    str((decision.parameters or {})["url"]),
                    metadata_hints=hints,
                )
                envelope["result"] = self._pipeline_result(
                    intake=intake_result,
                    specialist=self.execute_specialist(
                        "fit-map", objective=message, model=model, variant=variant
                    ),
                )
            elif workflow == "linkedin_post_intake":
                from career.services import intake as intake_service

                parameters = decision.parameters or {}
                if not parameters.get("company") or not parameters.get("role"):
                    envelope["status"] = "blocked"
                    envelope["blocker_reason"] = "linkedin_post_requires_company_and_role"
                    return envelope
                intake_result = intake_service.from_linkedin_post(
                    str(parameters["url"]),
                    company=str(parameters["company"]),
                    role=str(parameters["role"]),
                )
                envelope["result"] = self._pipeline_result(
                    intake=intake_result,
                    specialist=self.execute_specialist(
                        "fit-map", objective=message, model=model, variant=variant
                    ),
                )
            elif workflow == "external_url_intake":
                from career.services import intake as intake_service

                parameters = decision.parameters or {}
                intake_result = intake_service.from_url(
                    url=str(parameters["url"]),
                    company=str(parameters["company"]) if parameters.get("company") else None,
                    role=str(parameters["role"]) if parameters.get("role") else None,
                )
                envelope["result"] = self._pipeline_result(
                    intake=intake_result,
                    specialist=self.execute_specialist(
                        "fit-map", objective=message, model=model, variant=variant
                    ),
                )
            elif workflow == "pasted_job_intake":
                from career.services import intake as intake_service

                parameters = decision.parameters or {}
                intake_result = intake_service.from_paste(
                    company=str(parameters["company"]),
                    role=str(parameters["role"]),
                    text=str(parameters["text"]),
                )
                envelope["result"] = self._pipeline_result(
                    intake=intake_result,
                    specialist=self.execute_specialist(
                        "fit-map", objective=f"Analisar {parameters['role']} na {parameters['company']}", model=model, variant=variant
                    ),
                )
            elif workflow == "pasted_job_missing_metadata":
                envelope["status"] = "blocked"
                envelope["blocker_reason"] = "pasted_job_requires_empresa_and_cargo_headers"
                return envelope
            elif workflow == "linkedin_saved_jobs":
                envelope["result"] = self._extract_linkedin_saved_jobs()
            elif workflow == "runtime_introspection":
                from career.services import project as project_service

                envelope["result"] = project_service.hermes_runtime_snapshot()
                if isinstance(envelope["result"], dict):
                    stale = self._stale_active_intake_summary()
                    if stale:
                        envelope["result"]["stale_active_intake"] = stale
            elif workflow == "invalid_menu_selection":
                stale = self._stale_active_intake_summary()
                display_text = "Esse número não existe no menu atual. Responda com um número listado ou peça `menu` para recarregar."
                if stale:
                    display_text += (
                        f"\n\nHá um trabalho anterior salvo ({stale.get('role') or '-'} | {stale.get('company') or '-'})"
                        " mas ele parece antigo; se quiser retomá-lo, diga `continue o trabalho em andamento`."
                    )
                envelope["result"] = {
                    "status": "blocked",
                    "kind": "invalid_menu_selection",
                    "blocker_reason": "menu_selection_not_found",
                    "display_text": display_text,
                }
            elif workflow in {
                "fit_map",
                "cv",
                "cover_letter",
                "feras",
                "habilidades",
                "notion_update",
                "email_draft",
            }:
                step = {
                    "fit_map": "fit-map",
                    "cover_letter": "cover-letter",
                    "notion_update": "notion-update",
                    "email_draft": "email-draft",
                }.get(workflow, workflow)
                envelope["result"] = self.execute_specialist(
                    step,
                    objective=message,
                    model=model,
                    variant=variant,
                )
            elif workflow == "generic_assistant":
                envelope["result"] = self._run_generic_message(message, model=model)
            else:
                envelope["status"] = "blocked"
                envelope["blocker_reason"] = "no_deterministic_route"
                return envelope
        except ValidationFailure as exc:
            self._clear_menu_state()
            envelope["result"] = {
                "status": "blocked",
                "kind": "validation_failure",
                "blocker_reason": "workflow_validation_failed",
                "display_text": str(exc),
            }
        self._sync_menu_state_for_result(envelope.get("result"))
        result_status = envelope.get("result", {}).get("status") if isinstance(envelope.get("result"), dict) else None
        envelope["executed"] = result_status != "awaiting_input"
        envelope["status"] = (
            result_status
            if result_status in {"blocked", "awaiting_input", "awaiting_approval"}
            else "completed"
        )
        return envelope

    @staticmethod
    def _pipeline_result(*, intake: dict[str, Any], specialist: dict[str, Any]) -> dict[str, Any]:
        specialist_status = str(specialist.get("status") or "")
        status = specialist_status if specialist_status in {"blocked", "awaiting_approval"} else "completed"
        return {
            "status": status,
            "intake": intake,
            "specialist": specialist,
        }

    def _resume_and_continue(
        self, message: str, *, model: str | None, variant: str | None
    ) -> dict[str, Any]:
        from career.services import intake as intake_service

        resume = intake_service.resume()
        next_step = str(resume.get("next_required_step") or "")
        if "fill_fit_map" in next_step or "draft" in next_step:
            specialist = self.execute_specialist(
                "fit-map", objective=message, model=model, variant=variant
            )
            return {
                "status": "blocked" if specialist.get("status") == "blocked" else "completed",
                "resume": resume,
                "specialist": specialist,
            }
        return resume

    def _extract_linkedin_saved_jobs(self) -> dict[str, Any]:
        if not self.root:
            return {"status": "blocked", "blocker_reason": "harness_root_missing"}
        completed = subprocess.run(
            ["npm", "run", "linkedin:saved-jobs:extract"],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10 * 60,
        )
        if completed.returncode != 0:
            combined = f"{completed.stdout}\n{completed.stderr}"
            reason = "linkedin_auth_required" if "session" in combined.casefold() else "saved_jobs_extraction_failed"
            return {
                "status": "blocked",
                "blocker_reason": reason,
                "display_text": (
                    "A sessão do LinkedIn expirou. Preciso que você autentique o LinkedIn para continuar."
                    if reason == "linkedin_auth_required"
                    else "Não consegui atualizar as vagas salvas do LinkedIn. A extração foi interrompida."
                ),
            }
        output_path = self.root / "inbox" / "linkedin_saved_jobs.json"
        if not output_path.exists():
            return {"status": "blocked", "blocker_reason": "saved_jobs_output_missing"}
        payload = read_json(output_path)
        jobs = payload.get("jobs") or []
        self._write_saved_jobs_menu_state(jobs)
        lines = ["Vagas salvas no LinkedIn:"]
        for index, job in enumerate(jobs, start=1):
            lines.append(
                f"{index}. {job.get('title') or '-'} | {job.get('company') or '-'} | {job.get('location') or '-'}"
            )
            lines.append(f"   {job.get('url') or '-'}")
        lines.extend(["", "Responda com o número ou a URL da vaga que você quer analisar."])
        return {
            "status": "completed",
            "kind": "linkedin_saved_jobs",
            "extracted_at": payload.get("extractedAt"),
            "total": len(jobs),
            "jobs": jobs,
            "display_text": "\n".join(lines),
        }

    def _finalize_fit_map_pipeline(self) -> dict[str, Any]:
        if not self.root:
            return {"status": "blocked", "blocker_reason": "harness_root_missing"}
        from career.services import fit_map as fit_map_service
        from career.tasks.registry import run_task

        draft_path = CAREER_STATE / "fit_map.draft.json"
        fit_map_path = CAREER_STATE / "fit_map.json"
        try:
            results = {
                "validate_draft": run_task("fit_map.validate_draft", {"path": str(draft_path)}),
                "build": run_task("fit_map.build", {"draft": str(draft_path), "output": str(fit_map_path)}),
                "score": run_task("fit_map.score", {"path": str(fit_map_path)}),
                "validate": run_task("fit_map.validate", {"path": str(fit_map_path)}),
            }
            register_command = [
                str(self.root / "scripts" / "python.sh"),
                "scripts/register_keywords.py",
                "--fit-map",
                str(fit_map_path),
            ]
            registered = subprocess.run(
                register_command,
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10 * 60,
            )
            if registered.returncode != 0:
                return {
                    "status": "blocked",
                    "blocker_reason": "register_keywords_failed",
                    "command": register_command,
                    "stderr": (registered.stderr or registered.stdout)[-2000:],
                }
            summary = fit_map_service.payload_summary(fit_map_path)
            quality = fit_map_service.quality_report(fit_map_path)
            registry = fit_map_service.registry_summary()
            return {
                "status": "completed",
                "commands_executed": [
                    "fit_map.validate_draft",
                    "fit_map.build",
                    "fit_map.score",
                    "fit_map.validate",
                    "scripts/register_keywords.py --fit-map .career-state/fit_map.json",
                ],
                "results": results,
                "summary": {
                    "cargo": summary.get("cargo"),
                    "empresa": summary.get("empresa"),
                    "nota_final": summary.get("nota_final"),
                    "keyword_registration": registry.get("registered"),
                    "quality_status": quality.get("status"),
                },
            }
        except Exception as exc:
            return {
                "status": "blocked",
                "blocker_reason": "fit_map_finalize_failed",
                "error": str(exc),
            }

    def _maybe_auto_execute_approved_action(
        self,
        step: str,
        *,
        objective: str | None,
        prepared: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self.root:
            return None
        if not self._should_auto_execute_approved_action(step, objective=objective):
            return None
        approval_id = str((prepared.get("approval") or {}).get("approval_id") or "").strip()
        if not approval_id:
            return {
                "status": "blocked",
                "blocker_reason": "approval_id_missing",
            }
        try:
            ApprovalStore(self.root).approve(approval_id)
            executed = self.execute_approved_action(approval_id)
        except ValidationFailure as exc:
            return {
                "status": "blocked",
                "blocker_reason": "approved_action_validation_failed",
                "error": str(exc),
                "approval_id": approval_id,
            }
        executed["auto_approved"] = True
        executed["approval_policy"] = self._approval_policy(step)
        return executed

    def _should_auto_execute_approved_action(self, step: str, *, objective: str | None) -> bool:
        policy = self._approval_policy(step)
        if step == "email-draft":
            return policy == "always"
        if step != "notion-update":
            return False
        if policy == "always":
            return True
        if policy != "explicit_request":
            return False
        lowered = str(objective or "").casefold()
        return not any(hint in lowered for hint in PREVIEW_HINTS)

    def _approval_policy(self, step: str) -> str:
        config = self._automation_config()
        approvals = config.get("approvals", {}) if isinstance(config.get("approvals"), dict) else {}
        if step == "notion-update":
            return str(approvals.get("notion_write") or "manual")
        if step == "email-draft":
            return str(approvals.get("email_draft") or "manual")
        return "manual"

    def _fit_map_auto_finalize_enabled(self) -> bool:
        config = self._automation_config()
        fit_map = config.get("fit_map", {}) if isinstance(config.get("fit_map"), dict) else {}
        return bool(fit_map.get("auto_finalize", True))

    def _automation_config(self) -> dict[str, Any]:
        config_path = self.root / ".career-state" / "applications_v2" / "config.json" if self.root else None
        payload = read_json(config_path) if config_path and config_path.exists() else {}
        merged = {
            "fit_map": {**DEFAULT_HARNESS_AUTOMATION["fit_map"]},
            "approvals": {**DEFAULT_HARNESS_AUTOMATION["approvals"]},
        }
        harness = payload.get("harness", {}) if isinstance(payload.get("harness"), dict) else {}
        if isinstance(harness.get("fit_map"), dict):
            merged["fit_map"].update(harness["fit_map"])
        if isinstance(harness.get("approvals"), dict):
            merged["approvals"].update(harness["approvals"])
        return merged

    def _write_saved_jobs_menu_state(self, jobs: list[dict[str, Any]]) -> None:
        if not self.root:
            return
        from career.utils import write_json

        numbered_items = []
        for index, job in enumerate(jobs, start=1):
            numbered_items.append(
                {
                    "number": index,
                    "section_id": "linkedin_saved_jobs",
                    "section_title": "Vagas salvas no LinkedIn",
                    "id": f"linkedin_saved_job_{job.get('jobId') or index}",
                    "title": job.get("title"),
                    "description": f"{job.get('company') or '-'} | {job.get('location') or '-'}",
                    "prompt": job.get("url"),
                    "recommended": False,
                }
            )
        write_json(
            self.root / ".career-state" / "harness" / "menu_state.json",
            {
                "kind": "session_menu_state",
                "updated_at": utc_now_iso(),
                "menu_context": "linkedin_saved_jobs",
                "headline": "Vagas salvas no LinkedIn",
                "numbered_items": numbered_items,
            },
        )

    def _build_session_menu(self) -> dict[str, Any]:
        active = self._active_intake_summary()
        stale = self._stale_active_intake_summary()
        if active:
            payload = {
                "status": "completed",
                "kind": "session_menu",
                "menu_context": "active_job",
                "headline": "Ha uma vaga ativa. Posso continuar daqui.",
                "active_intake": active,
                "sections": [
                    {
                        "id": "continue_active_job",
                        "title": "Continuar vaga ativa",
                        "items": [
                            self._menu_item(
                                "resume",
                                "Retomar trabalho em andamento",
                                "Continuar exatamente do proximo passo salvo no estado local.",
                                "continue o trabalho em andamento",
                                recommended=True,
                            ),
                            self._menu_item(
                                "fit_map",
                                "Continuar analise da vaga ativa",
                                "Seguir o pipeline da analise/FIT_MAP da vaga atual.",
                                "continue a analise da vaga ativa",
                            ),
                        ],
                    },
                    {
                        "id": "generate_outputs",
                        "title": "Gerar entregaveis da vaga ativa",
                        "items": [
                            self._menu_item(
                                "cv",
                                "Gerar CV",
                                "Produzir o curriculo orientado pela vaga ativa.",
                                "gere um CV para a vaga ativa",
                            ),
                            self._menu_item(
                                "feras",
                                "Gerar pitch / FERAS",
                                "Produzir o pitch executivo e o texto FERAS.",
                                "gere um pitch FERAS para a vaga ativa",
                            ),
                            self._menu_item(
                                "cover_letter",
                                "Gerar carta",
                                "Produzir a carta de apresentacao da vaga ativa.",
                                "gere uma carta de apresentacao para a vaga ativa",
                            ),
                            self._menu_item(
                                "habilidades",
                                "Gerar habilidades ATS/Gupy",
                                "Montar habilidades-chave e resumo ATS da vaga ativa.",
                                "gere habilidades ATS para a vaga ativa",
                            ),
                        ],
                    },
                    {
                        "id": "capture_new_job",
                        "title": "Trocar para outra vaga",
                        "items": [
                            self._menu_item(
                                "linkedin_saved_jobs",
                                "Ver vagas salvas no LinkedIn",
                                "Abrir o rastreador salvo e escolher uma nova vaga.",
                                "listar minhas vagas salvas",
                            ),
                            self._menu_item(
                                "notion_job_analysis",
                                "Avaliar vaga do Notion por ID",
                                "Iniciar analise de uma vaga ja cadastrada no Notion.",
                                "quero avaliar uma vaga do Notion",
                            ),
                            self._menu_item(
                                "linkedin_job_intake",
                                "Avaliar vaga do LinkedIn por URL",
                                "Extrair a descricao da vaga e iniciar nova analise.",
                                "quero avaliar uma vaga do LinkedIn",
                            ),
                            self._menu_item(
                                "pasted_job_intake",
                                "Colar nova vaga para analise",
                                "Salvar uma descricao colada e abrir novo intake.",
                                "quero colar uma vaga para analise",
                            ),
                        ],
                    },
                    {
                        "id": "notion_actions",
                        "title": "Notion",
                        "items": [
                            self._menu_item(
                                "notion_update",
                                "Atualizar ou criar vaga no Notion",
                                "Preparar o dry-run de escrita no Notion a partir do estado atual.",
                                "atualize a vaga no Notion",
                            ),
                        ],
                    },
                ],
            }
            return self._finalize_menu_payload(payload)
        payload = {
            "status": "completed",
            "kind": "session_menu",
            "menu_context": "no_active_job",
            "headline": (
                "Nao ha vaga ativa recente. Estas sao as entradas mais uteis para comecar."
                if stale
                else "Nao ha vaga ativa. Estas sao as entradas mais uteis para comecar."
            ),
            "sections": [
                {
                    "id": "new_job_sources",
                    "title": "Entradas de vaga",
                    "items": [
                        self._menu_item(
                            "linkedin_saved_jobs",
                            "Ver vagas salvas no LinkedIn",
                            "Listar as vagas salvas no Jobs Tracker para escolher uma.",
                            "listar minhas vagas salvas",
                            recommended=True,
                        ),
                        self._menu_item(
                            "notion_job_analysis",
                            "Avaliar vaga do Notion por ID",
                            "Avaliar rapidamente uma vaga ja registrada no Notion.",
                            "quero avaliar uma vaga do Notion",
                            recommended=True,
                        ),
                        self._menu_item(
                            "linkedin_job_intake",
                            "Avaliar vaga do LinkedIn por URL",
                            "Extrair e persistir uma vaga do LinkedIn antes da analise.",
                            "quero avaliar uma vaga do LinkedIn",
                        ),
                        self._menu_item(
                            "pasted_job_intake",
                            "Colar nova vaga para analise",
                            "Usar texto colado quando a vaga nao vier do LinkedIn nem do Notion.",
                            "quero colar uma vaga para analise",
                        ),
                    ],
                },
            ],
        }
        if stale:
            payload["stale_active_intake"] = stale
            payload["sections"].append(
                {
                    "id": "resume_previous_job",
                    "title": "Retomar Trabalho Antigo",
                    "items": [
                        self._menu_item(
                            "resume",
                            f"Retomar {stale.get('role') or 'vaga anterior'}",
                            "Continuar manualmente o trabalho salvo anteriormente, mesmo ele parecendo antigo.",
                            "continue o trabalho em andamento",
                        )
                    ],
                }
            )
        return self._finalize_menu_payload(payload)

    def run_application_stage(
        self,
        *,
        stage: str,
        record_key: str,
        application_dir: Path,
        request_json: Path,
        request_md: Path,
        runner_config: dict[str, Any],
        model: str = "",
        variant: str = "",
        on_start: Callable[[list[str]], None] | None = None,
    ) -> dict[str, Any]:
        if not self.root or not self.runner:
            raise ValueError("HarnessSupervisor requires root and runner to execute stages.")
        instruction = self._stage_instruction(stage)
        run_request = AgentRunRequest(
            stage=stage,
            record_key=record_key,
            request_path=request_md,
            instruction=instruction,
            runner_config=runner_config,
            model=model,
            variant=variant,
        )
        harness_run = HarnessRunStore(self.root, application_dir).begin(stage, request_json, request_md)
        command = self.runner.build_command(run_request)
        if on_start:
            on_start(command)
        result = self.runner.run(run_request)
        isolation = harness_run.inspect()
        payload = {
            "stage": stage,
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "finished_at": utc_now_iso(),
            "run_dir": str(harness_run.run_dir.relative_to(self.root)),
            "isolation": isolation,
        }
        harness_run.finish(payload, isolation)
        return payload

    @staticmethod
    def _stage_instruction(stage: str) -> str:
        if stage == "analyze":
            return "Leia o request anexado e grave apenas o fit_map.draft.json."
        if stage == "repair":
            return "Leia o request anexado e repare somente os artefatos textuais permitidos."
        if stage == "generate":
            return "Leia o request anexado e grave somente os artefatos textuais pedidos."
        raise ValueError(f"Unsupported application stage: {stage}")

    def _run_generic_message(self, message: str, *, model: str | None = None) -> dict[str, Any]:
        if not self.root:
            return {"status": "blocked", "blocker_reason": "generic_runner_root_missing"}
        hermes = shutil.which("hermes")
        if not hermes:
            return {"status": "blocked", "blocker_reason": "generic_runner_unavailable"}
        command = [hermes, "--accept-hooks"]
        if model:
            command.extend(["--model", model])
        command.extend(["-z", message])
        env = os.environ.copy()
        env["CAREER_HARNESS_SUBAGENT"] = "1"
        completed = subprocess.run(
            command,
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15 * 60,
        )
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        return {
            "status": "completed" if completed.returncode == 0 else "blocked",
            "mode": "generic_hermes_fallback",
            **({"display_text": stdout} if completed.returncode == 0 and stdout else {}),
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": completed.returncode,
            **({"blocker_reason": "generic_runner_failed"} if completed.returncode != 0 else {}),
        }

    @staticmethod
    def _decision(
        workflow: str,
        stage: str,
        confidence: str,
        reason: str,
        *,
        requires_approval: bool = False,
        parameters: dict[str, Any] | None = None,
    ) -> DispatchDecision:
        return DispatchDecision(
            workflow=workflow,
            stage=stage,
            confidence=confidence,
            reason=reason,
            requires_approval=requires_approval,
            parameters=parameters,
        )

    @staticmethod
    def _menu_item(
        item_id: str,
        title: str,
        description: str,
        prompt: str,
        *,
        recommended: bool = False,
    ) -> dict[str, Any]:
        return {
            "id": item_id,
            "title": title,
            "description": description,
            "prompt": prompt,
            "recommended": recommended,
        }

    def _finalize_menu_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        numbered_items = self._numbered_menu_items(payload.get("sections") or [])
        payload["numbered_items"] = numbered_items
        payload["display_text"] = self._render_menu_text(payload)
        if self.root:
            self._write_menu_state(payload)
        return payload

    @staticmethod
    def _numbered_menu_items(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        numbered: list[dict[str, Any]] = []
        index = 1
        for section in sections:
            section_id = str(section.get("id") or "")
            section_title = str(section.get("title") or "")
            for item in section.get("items") or []:
                numbered.append(
                    {
                        "number": index,
                        "section_id": section_id,
                        "section_title": section_title,
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "description": item.get("description"),
                        "prompt": item.get("prompt"),
                        "recommended": bool(item.get("recommended")),
                    }
                )
                index += 1
        return numbered

    def _write_menu_state(self, payload: dict[str, Any]) -> None:
        state = {
            "kind": "session_menu_state",
            "updated_at": utc_now_iso(),
            "menu_context": payload.get("menu_context"),
            "headline": payload.get("headline"),
            "numbered_items": payload.get("numbered_items") or [],
        }
        path = self.root / ".career-state" / "harness" / "menu_state.json"
        from career.utils import write_json

        write_json(path, state)

    def _clear_menu_state(self) -> None:
        if not self.root:
            return
        (self.root / ".career-state" / "harness" / "menu_state.json").unlink(missing_ok=True)

    def _sync_menu_state_for_result(self, result: Any) -> None:
        if not self.root or not isinstance(result, dict):
            return
        if str(result.get("kind") or "") in {"session_menu", "linkedin_saved_jobs"}:
            return
        self._clear_menu_state()

    def _resolve_menu_selection(self, message: str) -> dict[str, Any] | None:
        text = " ".join(str(message or "").strip().split())
        if not re.fullmatch(r"\d{1,2}", text):
            return None
        payload = self._menu_state_payload()
        if not payload:
            return None
        items = payload.get("numbered_items") or []
        selected = next((item for item in items if int(item.get("number") or 0) == int(text)), None)
        if not selected:
            return None
        return {
            "number": int(text),
            "id": selected.get("id"),
            "title": selected.get("title"),
            "description": selected.get("description"),
            "prompt": selected.get("prompt"),
            "menu_context": payload.get("menu_context"),
        }

    def _invalid_menu_selection(self, message: str) -> str | None:
        text = " ".join(str(message or "").strip().split())
        if not re.fullmatch(r"\d{1,2}", text):
            return None
        payload = self._menu_state_payload()
        if not payload:
            return None
        items = payload.get("numbered_items") or []
        if any(int(item.get("number") or 0) == int(text) for item in items):
            return None
        return "numeric_menu_selection_not_found"

    def _menu_state_payload(self) -> dict[str, Any] | None:
        if not self.root:
            return None
        state_path = self.root / ".career-state" / "harness" / "menu_state.json"
        if not state_path.exists():
            return None
        try:
            return read_json(state_path)
        except Exception:
            return None

    @staticmethod
    def _menu_input_request(selection: dict[str, Any]) -> dict[str, Any] | None:
        item_id = str(selection.get("id") or "")
        requests = {
            "notion_job_analysis": (
                "notion_id",
                "Qual é o número da vaga no Notion? Pode responder somente com o número.",
            ),
            "linkedin_job_intake": (
                "linkedin_job_url",
                "Envie a URL da vaga no LinkedIn.",
            ),
            "pasted_job_intake": (
                "pasted_job",
                "Cole a vaga com duas linhas no início: Empresa: nome e Cargo: nome. Depois inclua a descrição completa.",
            ),
        }
        request = requests.get(item_id)
        if not request:
            return None
        return {
            "status": "awaiting_input",
            "kind": "input_request",
            "input_kind": request[0],
            "display_text": request[1],
        }

    @staticmethod
    def _saved_job_metadata_hints(selection: dict[str, Any] | None) -> dict[str, str]:
        if not isinstance(selection, dict) or selection.get("menu_context") != "linkedin_saved_jobs":
            return {}
        company = ""
        location = ""
        description = str(selection.get("description") or "")
        if " | " in description:
            company, location = [part.strip() for part in description.split(" | ", 1)]
        return {
            "role": str(selection.get("title") or "").strip(),
            "company": company,
            "location": location,
        }

    def _write_pending_input(self, request: dict[str, Any]) -> None:
        if not self.root:
            return
        from career.utils import write_json

        write_json(
            self.root / ".career-state" / "harness" / "pending_input.json",
            {**request, "updated_at": utc_now_iso()},
        )

    def _clear_pending_input(self) -> None:
        if not self.root:
            return
        (self.root / ".career-state" / "harness" / "pending_input.json").unlink(missing_ok=True)

    def _resolve_pending_input(self, message: str) -> dict[str, Any] | None:
        if not self.root:
            return None
        path = self.root / ".career-state" / "harness" / "pending_input.json"
        if not path.exists():
            return None
        pending = read_json(path)
        input_kind = str(pending.get("input_kind") or "")
        text = str(message or "").strip()
        resolved: str | None = None
        if input_kind == "notion_id" and re.fullmatch(r"\d+", text):
            resolved = f"avalie vaga Notion {text}"
        elif input_kind == "linkedin_job_url" and LINKEDIN_JOB_RE.search(text):
            resolved = text
        elif input_kind == "pasted_job" and len(text) >= 200:
            resolved = "Analise esta vaga\n" + text
        if not resolved:
            return None
        path.unlink(missing_ok=True)
        return {"input_kind": input_kind, "message": resolved}

    def _render_menu_text(self, payload: dict[str, Any]) -> str:
        lines = [str(payload.get("headline") or "Menu")]
        active = payload.get("active_intake") if isinstance(payload.get("active_intake"), dict) else None
        stale = payload.get("stale_active_intake") if isinstance(payload.get("stale_active_intake"), dict) else None
        if active:
            company = str(active.get("company") or "-")
            role = str(active.get("role") or "-")
            next_step = str(active.get("next_required_step") or "-")
            lines.append(f"Vaga ativa: {role} | {company}")
            lines.append(f"Próximo passo salvo: {next_step}")
        elif stale:
            company = str(stale.get("company") or "-")
            role = str(stale.get("role") or "-")
            updated_at = str(stale.get("updated_at") or "-")
            lines.append(f"Trabalho antigo detectado: {role} | {company}")
            lines.append(f"Última atualização salva: {updated_at}")
        for section in payload.get("sections") or []:
            lines.append("")
            lines.append(f"{section.get('title')}:")
            for item in payload.get("numbered_items") or []:
                if item.get("section_id") != section.get("id"):
                    continue
                suffix = " [recomendado]" if item.get("recommended") else ""
                lines.append(f"{item.get('number')}. {item.get('title')}{suffix}")
                lines.append(f"   {item.get('description')}")
        lines.append("")
        lines.append("Responda com o número da opção ou diga o que você quer fazer.")
        return "\n".join(lines)

    def _active_intake_summary(self) -> dict[str, Any] | None:
        active = self._raw_active_intake()
        if not active or self._is_stale_active_intake(active):
            return None
        return self._normalize_active_intake(active)

    def _stale_active_intake_summary(self) -> dict[str, Any] | None:
        active = self._raw_active_intake()
        if not active or not self._is_stale_active_intake(active):
            return None
        normalized = self._normalize_active_intake(active)
        normalized["stale"] = True
        return normalized

    def _raw_active_intake(self) -> dict[str, Any] | None:
        if not self.root:
            return None
        state_path = self.root / ".career-state" / "workflow_state.json"
        if not state_path.exists():
            return None
        payload = read_json(state_path)
        active = payload.get("active_intake")
        if not isinstance(active, dict) or not active.get("job_description_path"):
            return None
        return active

    @staticmethod
    def _normalize_active_intake(active: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_type": active.get("source_type"),
            "source_id": active.get("source_id"),
            "company": active.get("company"),
            "role": active.get("role"),
            "job_description_path": active.get("job_description_path"),
            "next_required_step": active.get("next_required_step"),
            "status": active.get("status"),
            "updated_at": active.get("updated_at"),
        }

    @staticmethod
    def _is_stale_active_intake(active: dict[str, Any]) -> bool:
        updated_at = str(active.get("updated_at") or "").strip()
        if not updated_at:
            return False
        try:
            parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - parsed > ACTIVE_INTAKE_STALE_AFTER

    @staticmethod
    def _is_runtime_introspection(lowered: str) -> bool:
        triggers = (
            "temperatura",
            "temperature",
            "config do hermes",
            "configuração do hermes",
            "configuracao do hermes",
            "hermes config",
            "qual modelo",
            "que modelo",
            "model you are using",
            "modelo que vc está usando",
            "modelo que vc esta usando",
            "runtime do hermes",
            "runtime local",
        )
        return any(trigger in lowered for trigger in triggers)

    @staticmethod
    def _is_menu_request(lowered: str) -> bool:
        if lowered.strip(" !.,?") in {
            "oi",
            "ola",
            "olá",
            "bom dia",
            "boa tarde",
            "boa noite",
        }:
            return True
        triggers = (
            "menu",
            "opcoes",
            "opções",
            "nova sessao",
            "nova sessão",
            "o que posso fazer",
            "atalhos",
            "acoes comuns",
            "ações comuns",
        )
        return any(trigger in lowered for trigger in triggers)
