from __future__ import annotations

from dataclasses import dataclass

from career.utils import ValidationFailure


TASK_TO_STATE = {
    "notion.refresh_cache": "notion_cache_ready",
    "notion.build_cache": "notion_cache_ready",
    "project.save_job_description": "job_description_saved",
    "fit_map.template": "fit_map_template_ready",
    "fit_map.validate_draft": "fit_map_draft_valid",
    "fit_map.build": "fit_map_built",
    "fit_map.score": "fit_map_scored",
    "fit_map.validate": "fit_map_validated",
    "cv.review": "cv_review_passed",
    "cv.approve": "cv_review_passed",
    "project.diagnose_runtime": "runtime_diagnosed",
    "memory.build": "memory_bundle_ready",
}

TASK_REQUIREMENTS = {
    "fit_map.build": ["fit_map_draft_valid"],
    "fit_map.score": ["fit_map_built"],
    "fit_map.validate": ["fit_map_scored"],
    "cv.review": ["fit_map_validated"],
    "cv.approve": ["fit_map_validated"],
}


@dataclass(slots=True)
class WorkflowStateMachine:
    completed_states: set[str]
    fingerprints: dict
    active_job_fingerprint: str | None = None

    def ensure_task_allowed(self, task_name: str) -> None:
        missing = [state for state in TASK_REQUIREMENTS.get(task_name, []) if state not in self.completed_states]
        if missing:
            raise ValidationFailure(
                f"Task {task_name} blocked by workflow state. Missing prerequisite states: {', '.join(missing)}"
            )
        if not self.active_job_fingerprint:
            return
        for required_state in TASK_REQUIREMENTS.get(task_name, []):
            prerequisite_task = next((name for name, state in TASK_TO_STATE.items() if state == required_state), None)
            if not prerequisite_task:
                continue
            prior = self.fingerprints.get(prerequisite_task, {})
            prior_job = prior.get("active_job_fingerprint")
            if not prior_job:
                raise ValidationFailure(
                    f"Task {task_name} blocked by active job mismatch. "
                    f"Prerequisite {prerequisite_task} has no active job fingerprint; "
                    "rerun the prerequisite for the current job."
                )
            if prior_job != self.active_job_fingerprint:
                raise ValidationFailure(
                    f"Task {task_name} blocked by active job mismatch. "
                    f"Prerequisite {prerequisite_task} belongs to {prior_job}, "
                    f"current active job is {self.active_job_fingerprint}."
                )

    def complete_task(self, task_name: str) -> str | None:
        state = TASK_TO_STATE.get(task_name)
        if state:
            self.completed_states.add(state)
        return state
