from __future__ import annotations

from typing import Any


CONTRACTS: dict[str, dict[str, Any]] = {
    "fit-map": {
        "inputs": ["job_description.md", "reference_digest.json"],
        "outputs": ["fit_map.draft.json"],
        "rules": [
            "Must validate with validate:fit-map:draft",
            "No placeholders allowed",
        ],
    },
    "cv": {
        "inputs": ["cv_input_pack.json", "cv_content_seed.json"],
        "outputs": ["cv_content.json"],
        "rules": [
            "Must run context:assert-active first",
            "DOCX in outputs/ required",
        ],
    },
    "cover-letter": {
        "inputs": ["cover_letter_input_pack.json"],
        "outputs": ["cover_letter.md"],
        "rules": ["Review before delivery"],
    },
    "feras": {
        "inputs": ["feras_input_pack.json"],
        "outputs": ["feras_formal.md"],
        "rules": ["First person narrative"],
    },
    "habilidades": {
        "inputs": ["habilidades_input_pack.json"],
        "outputs": ["habilidades_gupy.md"],
        "rules": ["No repeated stories across skills"],
    },
    "notion-update": {
        "inputs": ["fit_map.json", "notion_update_payload.json"],
        "outputs": ["notion page update"],
        "rules": ["Dry-run first", "No mojibake"],
    },
    "email-draft": {
        "inputs": ["cv.docx", "cover_letter.md"],
        "outputs": ["gmail draft"],
        "rules": ["Review before draft", "Never send automatically"],
    },
    "linkedin": {
        "inputs": ["job_description.md"],
        "outputs": ["linkedin message"],
        "rules": ["Use local authenticated scripts", "No browser/web_search"],
    },
}


class AgentContracts:
    def get_contract(self, name: str) -> dict[str, Any] | None:
        return CONTRACTS.get(name)

    def list_contracts(self) -> dict[str, dict[str, Any]]:
        return dict(CONTRACTS)
