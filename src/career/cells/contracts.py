from __future__ import annotations

from dataclasses import dataclass


CONTRACT_VERSION = "1"


@dataclass(frozen=True)
class CellContract:
    """Declarative, versioned behavior for one application cell."""

    node_id: str
    version: str
    requires: tuple[str, ...]
    produces: tuple[str, ...]
    validators: tuple[str, ...]
    resources: tuple[str, ...]
    invalidates: tuple[str, ...]
    repair_scope: str
    max_attempts: int
    allows_external_effect: bool


def _contract(
    node_id: str,
    *,
    requires: tuple[str, ...] = (),
    produces: tuple[str, ...],
    validators: tuple[str, ...],
    resources: tuple[str, ...] = (),
    invalidates: tuple[str, ...] = (),
    repair_scope: str,
    max_attempts: int = 3,
    allows_external_effect: bool = False,
) -> CellContract:
    return CellContract(
        node_id=node_id,
        version=CONTRACT_VERSION,
        requires=requires,
        produces=produces,
        validators=validators,
        resources=resources,
        invalidates=invalidates,
        repair_scope=repair_scope,
        max_attempts=max_attempts,
        allows_external_effect=allows_external_effect,
    )


CELL_CONTRACTS: dict[str, CellContract] = {
    "capture_source": _contract(
        "capture_source",
        produces=("job_description.md",),
        validators=("validate-job-description",),
        resources=("linkedin-session",),
        invalidates=("normalize_job",),
        repair_scope="source_capture_only",
        max_attempts=2,
        allows_external_effect=True,
    ),
    "normalize_job": _contract(
        "normalize_job",
        requires=("capture_source",),
        produces=(
            "derived/job_normalized.json",
            "derived/handover_summary.json",
            "derived/evidence_index.json",
        ),
        validators=("context:validate",),
        invalidates=("analyze_fit",),
        repair_scope="job_normalization_only",
    ),
    "analyze_fit": _contract(
        "analyze_fit",
        requires=("normalize_job",),
        produces=("fit_map.json",),
        validators=("validate:fit-map", "validate:fit-map:quality", "validate-provenance"),
        invalidates=(
            "compose_cv",
            "sync_notion_initial",
            "generate_feras",
            "generate_cover_letter",
            "generate_habilidades",
        ),
        repair_scope="fit_map_only",
    ),
    "compose_cv": _contract(
        "compose_cv",
        requires=("analyze_fit",),
        produces=("artifacts/cv_content.json",),
        validators=("cv:validate-content", "validate-cv-provenance"),
        invalidates=("render_cv", "review_cv", "deliver_cv", "sync_notion_final"),
        repair_scope="cv_content_only",
    ),
    "render_cv": _contract(
        "render_cv",
        requires=("compose_cv",),
        produces=("artifacts/cv.docx",),
        validators=("validate:docx",),
        invalidates=("review_cv", "deliver_cv", "sync_notion_final"),
        repair_scope="cv_render_only",
    ),
    "review_cv": _contract(
        "review_cv",
        requires=("render_cv", "analyze_fit"),
        produces=("reviews/cv_review.json",),
        validators=("cv:approve",),
        invalidates=("deliver_cv", "sync_notion_final"),
        repair_scope="cv_review_only",
    ),
    "deliver_cv": _contract(
        "deliver_cv",
        requires=("review_cv",),
        produces=("artifacts/cv_delivery_receipt.json",),
        validators=("validate-delivery-receipt",),
        resources=("delivery:onedrive-cv",),
        repair_scope="cv_delivery_only",
        max_attempts=2,
        allows_external_effect=True,
    ),
    "sync_notion_initial": _contract(
        "sync_notion_initial",
        requires=("analyze_fit",),
        produces=("artifacts/notion_initial_receipt.json",),
        validators=("validate-notion-receipt",),
        resources=("notion-write",),
        repair_scope="notion_initial_sync_only",
        max_attempts=2,
        allows_external_effect=True,
    ),
    "sync_notion_final": _contract(
        "sync_notion_final",
        produces=("artifacts/notion_final_receipt.json",),
        validators=("validate-notion-receipt",),
        resources=("notion-write",),
        repair_scope="notion_final_sync_only",
        max_attempts=2,
        allows_external_effect=True,
    ),
    "generate_feras": _contract(
        "generate_feras",
        requires=("analyze_fit",),
        produces=("artifacts/feras.md",),
        validators=("validate-feras", "validate-provenance"),
        invalidates=("review_feras", "sync_notion_final"),
        repair_scope="feras_content_only",
    ),
    "review_feras": _contract(
        "review_feras",
        requires=("generate_feras",),
        produces=("reviews/feras_review.json",),
        validators=("review-output:feras",),
        invalidates=("sync_notion_final",),
        repair_scope="feras_review_only",
    ),
    "generate_cover_letter": _contract(
        "generate_cover_letter",
        requires=("analyze_fit",),
        produces=("artifacts/cover_letter.md",),
        validators=("validate-cover-letter", "validate-provenance"),
        invalidates=("review_cover_letter", "sync_notion_final"),
        repair_scope="cover_letter_content_only",
    ),
    "review_cover_letter": _contract(
        "review_cover_letter",
        requires=("generate_cover_letter",),
        produces=("reviews/cover_letter_review.json",),
        validators=("review-output:cover-letter",),
        invalidates=("sync_notion_final",),
        repair_scope="cover_letter_review_only",
    ),
    "generate_habilidades": _contract(
        "generate_habilidades",
        requires=("analyze_fit",),
        produces=("artifacts/habilidades.md",),
        validators=("validate-habilidades", "validate-provenance"),
        invalidates=("review_habilidades", "sync_notion_final"),
        repair_scope="habilidades_content_only",
    ),
    "review_habilidades": _contract(
        "review_habilidades",
        requires=("generate_habilidades",),
        produces=("reviews/habilidades_review.json",),
        validators=("review-output:habilidades",),
        invalidates=("sync_notion_final",),
        repair_scope="habilidades_review_only",
    ),
}
