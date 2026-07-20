from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from career.cells.contracts import CELL_CONTRACTS, CONTRACT_VERSION, CellContract
from career.services.application_context import ApplicationPaths
from career.utils import write_json


_DELIVERABLE_TARGETS: dict[str, tuple[str, ...]] = {
    "cv": ("deliver_cv",),
    "notion": ("sync_notion_initial",),
    "feras": ("review_feras",),
    "cover_letter": ("review_cover_letter",),
    "habilidades": ("review_habilidades",),
}

_FINAL_NOTION_DEPENDENCIES: dict[str, str] = {
    "cv": "review_cv",
    "feras": "review_feras",
    "cover_letter": "review_cover_letter",
    "habilidades": "review_habilidades",
}


@dataclass(frozen=True)
class NodePlan:
    node_id: str
    requires: tuple[str, ...]
    produces: tuple[str, ...]
    validators: tuple[str, ...]
    resources: tuple[str, ...]
    invalidates: tuple[str, ...]
    repair_scope: str
    max_attempts: int
    allows_external_effect: bool
    contract_version: str

    def as_dict(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "requires": list(self.requires),
            "produces": list(self.produces),
            "validators": list(self.validators),
            "resources": list(self.resources),
            "invalidates": list(self.invalidates),
            "repair_scope": self.repair_scope,
            "max_attempts": self.max_attempts,
            "allows_external_effect": self.allows_external_effect,
            "contract_version": self.contract_version,
        }


@dataclass(frozen=True)
class RunPlan:
    run_id: str
    application_id: str
    nodes: tuple[NodePlan, ...]
    edges: tuple[tuple[str, str], ...]
    resource_locks: tuple[str, ...]
    created_at: str
    contract_version: str

    def dependencies_of(self, node_id: str) -> tuple[str, ...]:
        node = next((item for item in self.nodes if item.node_id == node_id), None)
        if node is None:
            raise KeyError(f"unknown plan node: {node_id}")
        return node.requires

    def ready_after(self, completed: Iterable[str]) -> tuple[str, ...]:
        completed_nodes = frozenset(completed)
        return tuple(
            node.node_id
            for node in self.nodes
            if node.node_id not in completed_nodes and set(node.requires) <= completed_nodes
        )

    def is_acyclic(self) -> bool:
        dependencies = {node.node_id: set(node.requires) for node in self.nodes}
        if any(
            required not in dependencies
            for required_set in dependencies.values()
            for required in required_set
        ):
            return False

        remaining = {node_id: set(required) for node_id, required in dependencies.items()}
        while remaining:
            ready = {node_id for node_id, required in remaining.items() if not required}
            if not ready:
                return False
            remaining = {
                node_id: required - ready
                for node_id, required in remaining.items()
                if node_id not in ready
            }
        return True

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "application_id": self.application_id,
            "nodes": [node.as_dict() for node in self.nodes],
            "edges": [list(edge) for edge in self.edges],
            "resource_locks": list(self.resource_locks),
            "created_at": self.created_at,
            "contract_version": self.contract_version,
        }


def compile_run_plan(
    application_id: str,
    requested_deliverables: Iterable[str],
    application_paths: ApplicationPaths,
) -> RunPlan:
    """Compile, validate, and persist an immutable application DAG."""
    if not application_id or application_paths.application_id != application_id:
        raise ValueError("application_id must match application_paths")
    if isinstance(requested_deliverables, (str, bytes)):
        raise ValueError("requested_deliverables must be an iterable of deliverable names")

    requested = frozenset(requested_deliverables)
    unknown = requested - _DELIVERABLE_TARGETS.keys()
    if unknown:
        raise ValueError(f"unknown deliverable(s): {', '.join(sorted(unknown))}")

    contracts = _validated_contract_registry(CELL_CONTRACTS)
    selected = {"normalize_job", "analyze_fit"}
    for deliverable in requested:
        selected.update(_DELIVERABLE_TARGETS[deliverable])

    notion_dependencies = tuple(
        node_id
        for deliverable, node_id in _FINAL_NOTION_DEPENDENCIES.items()
        if "notion" in requested and deliverable in requested
    )
    if notion_dependencies:
        selected.add("sync_notion_final")

    include_capture = not application_paths.job_description.exists()
    if include_capture:
        selected.add("capture_source")

    _include_dependencies(selected, contracts)
    if not include_capture:
        selected.discard("capture_source")

    node_plans: dict[str, NodePlan] = {}
    for node_id in selected:
        contract = contracts.get(node_id)
        if contract is None:
            raise ValueError(f"missing contract for node: {node_id}")
        requires = contract.requires
        if node_id == "normalize_job" and not include_capture:
            requires = tuple(required for required in requires if required != "capture_source")
        elif node_id == "sync_notion_final":
            requires = notion_dependencies
        missing_dependencies = set(requires) - selected
        if missing_dependencies:
            missing = ", ".join(sorted(missing_dependencies))
            raise ValueError(f"missing contract dependency for {node_id}: {missing}")
        node_plans[node_id] = _compile_node(contract, requires, application_paths.app_dir)

    ordered_nodes = _topological_order(tuple(node_plans.values()))
    _reject_output_collisions(ordered_nodes)
    edges = tuple(
        sorted((required, node.node_id) for node in ordered_nodes for required in node.requires)
    )
    resource_locks = tuple(sorted({resource for node in ordered_nodes for resource in node.resources}))
    plan = RunPlan(
        run_id=f"run_{uuid4().hex}",
        application_id=application_id,
        nodes=ordered_nodes,
        edges=edges,
        resource_locks=resource_locks,
        created_at=datetime.now(UTC).isoformat(),
        contract_version=CONTRACT_VERSION,
    )
    if not plan.is_acyclic():
        raise ValueError("cell plan contains a cycle")

    write_json(application_paths.app_dir / "plans" / f"{plan.run_id}.json", plan.as_dict())
    return plan


def _validated_contract_registry(
    contracts: dict[str, CellContract],
) -> dict[str, CellContract]:
    node_ids = [contract.node_id for contract in contracts.values()]
    duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate node ID(s): {', '.join(duplicates)}")
    return dict(contracts)


def _include_dependencies(selected: set[str], contracts: dict[str, CellContract]) -> None:
    pending = list(selected)
    while pending:
        node_id = pending.pop()
        contract = contracts.get(node_id)
        if contract is None:
            raise ValueError(f"missing contract for node: {node_id}")
        for required in contract.requires:
            if required not in selected:
                selected.add(required)
                pending.append(required)


def _compile_node(contract: CellContract, requires: tuple[str, ...], app_dir: Path) -> NodePlan:
    return NodePlan(
        node_id=contract.node_id,
        requires=requires,
        produces=tuple(str((app_dir / path).resolve()) for path in contract.produces),
        validators=contract.validators,
        resources=contract.resources,
        invalidates=contract.invalidates,
        repair_scope=contract.repair_scope,
        max_attempts=contract.max_attempts,
        allows_external_effect=contract.allows_external_effect,
        contract_version=contract.version,
    )


def _topological_order(nodes: tuple[NodePlan, ...]) -> tuple[NodePlan, ...]:
    by_id = {node.node_id: node for node in nodes}
    dependencies = {node.node_id: set(node.requires) for node in nodes}
    ordered: list[NodePlan] = []
    while dependencies:
        ready = sorted(node_id for node_id, required in dependencies.items() if not required)
        if not ready:
            raise ValueError("cell plan contains a cycle")
        ordered.extend(by_id[node_id] for node_id in ready)
        ready_set = set(ready)
        dependencies = {
            node_id: required - ready_set
            for node_id, required in dependencies.items()
            if node_id not in ready_set
        }
    return tuple(ordered)


def _reject_output_collisions(nodes: tuple[NodePlan, ...]) -> None:
    owners: dict[str, str] = {}
    for node in nodes:
        for path in node.produces:
            previous = owners.get(path)
            if previous is not None:
                raise ValueError(f"output-path collision: {path} ({previous}, {node.node_id})")
            owners[path] = node.node_id
