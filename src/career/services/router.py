from __future__ import annotations

ROUTES: dict[str, dict[str, str | None]] = {
    "analyze_job": {"specialist": "fit-map", "next_step": "fill_fit_map_draft"},
    "generate_cv": {"specialist": "cv", "next_step": "build_cv_content"},
    "generate_feras": {"specialist": "feras", "next_step": "generate_feras"},
    "generate_cover_letter": {"specialist": "cover-letter", "next_step": "generate_cover_letter"},
    "query_applications": {"specialist": "query", "next_step": "execute_query"},
    "networking": {"specialist": "linkedin", "next_step": "generate_message"},
    "notion_sync": {"specialist": "notion", "next_step": "sync_notion"},
    "reset": {"specialist": "reset", "next_step": "confirm_reset"},
    "email_draft": {"specialist": "email-draft", "next_step": "prepare_draft"},
    "menu": {"specialist": "menu", "next_step": "show_menu"},
    "linkedin_saved_jobs": {"specialist": "linkedin", "next_step": "list_saved_jobs"},
    "resume": {"specialist": "resume", "next_step": "resume_workflow"},
    "heartbeat": {"specialist": "orchestrate", "next_step": "run_heartbeat"},
    "habilidades": {"specialist": "habilidades", "next_step": "generate_habilidades"},
    "unknown": {"specialist": None, "next_step": "clarify"},
}


class Router:
    def route(self, intent: str) -> dict:
        return dict(ROUTES.get(intent, ROUTES["unknown"]))
