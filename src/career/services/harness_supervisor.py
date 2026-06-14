from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
from typing import Any

from career.services.agent_runner import AgentRunRequest, SubprocessAgentRunner
from career.services.approvals import ApprovalStore
from career.services.approved_actions import ApprovedActionExecutor
from career.services.harness_runs import HarnessRunStore, begin_specialist_run
from career.utils import read_json, utc_now_iso


LINKEDIN_JOB_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/(?:jobs(?:/view)?|job)/[^\s]+", re.IGNORECASE)
LINKEDIN_POST_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:feed/update|posts|pulse)/[^\s]+",
    re.IGNORECASE,
)
NOTION_ID_RE = re.compile(r"\b(?:notion|vaga|id)\s*#?\s*(\d+)\b", re.IGNORECASE)

SPECIALIST_OUTPUT_PATTERNS = {
    "fit-map": [".career-state/fit_map.draft.json"],
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
    "notion-update": [".career-state/pending_actions/*.json"],
    "email-draft": [".career-state/pending_actions/*.json"],
    "linkedin": [
        ".career-state/linkedin_job_extract.json",
        ".career-state/linkedin_post_extract.json",
        ".career-state/workflow_state.json",
        "inbox/job_descriptions/*.md",
        "inbox/linkedin_posts/*.md",
    ],
}


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

        if any(token in lowered for token in ("vagas salvas", "saved jobs", "rastreador de vagas")):
            return self._decision("linkedin_saved_jobs", "intake", "high", "linkedin_saved_jobs_request")

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

        analysis_requested = any(
            token in lowered for token in ("avali", "analis", "aderencia", "aderência", "fit_map", "fit map")
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

        return self._decision("help", "route", "low", "no_deterministic_route")

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
        decision = self.classify(message)
        envelope: dict[str, Any] = {
            "status": "routed",
            "channel": channel,
            "message": message,
            "decision": decision.to_dict(),
            "executed": False,
        }
        if not execute:
            return envelope

        workflow = decision.workflow
        if workflow == "applications_status":
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

            envelope["result"] = agent_guard_service.evaluate_notion_local(
                int((decision.parameters or {})["record_id"])
            )
        elif workflow == "linkedin_job_intake":
            from career.services import intake as intake_service

            intake_result = intake_service.from_linkedin_job(str((decision.parameters or {})["url"]))
            envelope["result"] = {
                "intake": intake_result,
                "specialist": self.prepare_specialist("fit-map"),
            }
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
            envelope["result"] = {
                "intake": intake_result,
                "specialist": self.execute_specialist(
                    "fit-map", objective=message, model=model, variant=variant
                ),
            }
        elif workflow == "pasted_job_intake":
            from career.services import intake as intake_service

            parameters = decision.parameters or {}
            intake_result = intake_service.from_paste(
                company=str(parameters["company"]),
                role=str(parameters["role"]),
                text=str(parameters["text"]),
            )
            envelope["result"] = {
                "intake": intake_result,
                "specialist": self.execute_specialist(
                    "fit-map", objective=f"Analisar {parameters['role']} na {parameters['company']}", model=model, variant=variant
                ),
            }
        elif workflow == "pasted_job_missing_metadata":
            envelope["status"] = "blocked"
            envelope["blocker_reason"] = "pasted_job_requires_empresa_and_cargo_headers"
            return envelope
        elif workflow == "linkedin_saved_jobs":
            envelope["status"] = "prepared"
            envelope["result"] = {
                "command": "npm run linkedin:saved-jobs:extract",
                "next_action": "run_saved_jobs_extractor",
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
        else:
            envelope["status"] = "blocked"
            envelope["blocker_reason"] = "no_deterministic_route"
            return envelope
        envelope["executed"] = True
        result_status = envelope.get("result", {}).get("status") if isinstance(envelope.get("result"), dict) else None
        envelope["status"] = "blocked" if result_status == "blocked" else "completed"
        return envelope

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
