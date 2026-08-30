from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from career.cells.planner import RunPlan


SERIAL_STAGE_ORDER = (
    "normalize",
    "analyze",
    "cv",
    "delivery",
    "notion",
    "seal",
)

SERIAL_STAGE_NODES: dict[str, tuple[str, ...]] = {
    "normalize": ("capture_source", "normalize_job"),
    "analyze": ("analyze_fit",),
    "cv": ("compose_cv", "render_cv", "review_cv"),
    "delivery": ("deliver_cv",),
    "notion": ("sync_notion_initial", "sync_notion_final"),
    "seal": (),
}

_WAITING_STATUSES = {"awaiting_agent", "awaiting_approval"}
_ACTIVE_STATUSES = {"reserved", "running"}


@dataclass(frozen=True)
class SerialStageReport:
    stage: str
    status: str
    allowed_nodes: tuple[str, ...]
    completed_nodes: tuple[str, ...]
    next_stage: str | None
    blocked_nodes: tuple[str, ...]


def stage_node_ids(stage: str) -> tuple[str, ...]:
    try:
        return SERIAL_STAGE_NODES[stage]
    except KeyError as exc:
        raise ValueError(f"unknown serial stage: {stage}") from exc


def serial_stage_report(
    plan: RunPlan,
    statuses: Mapping[str, str],
) -> SerialStageReport:
    if plan.execution_mode != "serial":
        raise ValueError("serial stage report requires a serial execution mode")

    plan_nodes = tuple(node.node_id for node in plan.nodes)
    plan_node_set = set(plan_nodes)
    completed_nodes = tuple(
        node_id for node_id in plan_nodes if statuses.get(node_id) == "validated"
    )
    blocked_nodes = tuple(
        node_id for node_id in plan_nodes if statuses.get(node_id) == "blocked"
    )

    selected_stages = tuple(
        stage
        for stage in SERIAL_STAGE_ORDER
        if set(stage_node_ids(stage)) & plan_node_set or stage == "seal"
    )
    for index, stage in enumerate(selected_stages):
        nodes = tuple(node_id for node_id in stage_node_ids(stage) if node_id in plan_node_set)
        if not nodes:
            return SerialStageReport(
                stage=stage,
                status="ready",
                allowed_nodes=(),
                completed_nodes=completed_nodes,
                next_stage=None,
                blocked_nodes=blocked_nodes,
            )

        node_statuses = tuple(statuses.get(node_id, "planned") for node_id in nodes)
        if all(status == "validated" for status in node_statuses):
            continue

        if any(status == "blocked" for status in node_statuses):
            status = "blocked"
            next_stage = None
        elif any(status == "awaiting_approval" for status in node_statuses):
            status = "awaiting_approval"
            next_stage = None
        elif any(status == "awaiting_agent" for status in node_statuses):
            status = "awaiting_agent"
            next_stage = None
        elif any(status in _ACTIVE_STATUSES for status in node_statuses):
            status = "running"
            next_stage = None
        else:
            status = "ready"
            next_stage = selected_stages[index + 1] if index + 1 < len(selected_stages) else None

        allowed_nodes = tuple(
            node_id
            for node_id, node_status in zip(nodes, node_statuses)
            if node_status not in {"validated", "blocked"}
        )
        return SerialStageReport(
            stage=stage,
            status=status,
            allowed_nodes=allowed_nodes,
            completed_nodes=completed_nodes,
            next_stage=next_stage,
            blocked_nodes=blocked_nodes,
        )

    return SerialStageReport(
        stage="seal",
        status="ready",
        allowed_nodes=(),
        completed_nodes=completed_nodes,
        next_stage=None,
        blocked_nodes=blocked_nodes,
    )
