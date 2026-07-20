from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from career.cells.contracts import CELL_CONTRACTS
from career.services.application_context import ApplicationPaths
from career.utils import read_json, utc_now_iso, write_json


@dataclass(frozen=True)
class AttemptManifest:
    path: Path
    staging_dir: Path
    manifest: dict[str, Any]


@dataclass(frozen=True)
class PublishedArtifact:
    path: Path
    manifest_path: Path
    manifest: dict[str, Any]


@dataclass(frozen=True)
class RunCompletion:
    path: Path
    manifest: dict[str, Any]


class ManifestStore:
    """Application-scoped manifests and immutable artifact revisions."""

    _HASH_PREFIX_LENGTH = 12

    def __init__(self, paths: ApplicationPaths):
        self.paths = paths
        self.application_dir = paths.app_dir.resolve()

    def begin_attempt(
        self,
        node_id: str,
        attempt: int,
        *,
        run_id: str = "",
        contract_version: str = "1",
        inputs: Mapping[str, Any] | None = None,
        read_paths: Iterable[Path] = (),
        write_paths: Iterable[Path] = (),
        context: Mapping[str, Any] | None = None,
        status: str = "planned",
    ) -> AttemptManifest:
        attempt_dir = self._attempt_dir(node_id, attempt)
        staging_dir = self._target(attempt_dir / "staging", strict_child=True)
        manifest_path = self._target(attempt_dir / "manifest.json", strict_child=True)
        resolved_read_paths = [str(self._target(path)) for path in read_paths]
        resolved_write_paths = [str(self._target(path)) for path in write_paths]
        normalized_inputs = self._normalize_inputs(inputs or {})
        attempt_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            attempt_dir.mkdir()
        except FileExistsError as exc:
            raise RuntimeError(
                f"attempt already exists: {node_id}/{attempt}"
            ) from exc
        staging_dir.mkdir()
        manifest = {
            "kind": "cell_attempt_manifest",
            "application_id": self.paths.application_id,
            "run_id": str(run_id),
            "node_id": node_id,
            "attempt": attempt,
            "contract_version": str(contract_version),
            "inputs": normalized_inputs,
            "capabilities": {
                "read_paths": resolved_read_paths,
                "write_paths": resolved_write_paths,
            },
            "context": dict(context or {}),
            "outputs": [],
            "validators": [],
            "status": status,
            "created_at": utc_now_iso(),
        }
        self._write_json_once(manifest_path, manifest, "attempt manifest")
        return AttemptManifest(path=manifest_path, staging_dir=staging_dir, manifest=manifest)

    def write_handover(
        self,
        node_id: str,
        attempt: int,
        handover: Mapping[str, Any],
    ) -> Path:
        attempt_dir = self._attempt_dir(node_id, attempt)
        self._load_attempt(node_id, attempt)
        handover_path = self._target(
            attempt_dir / "handover_summary.json", strict_child=True
        )
        self._write_json_once(handover_path, dict(handover), "attempt handover")
        return handover_path

    def publish_file(
        self,
        node_id: str,
        attempt: int,
        artifact_name: str,
        content: bytes,
        *,
        inputs: Mapping[str, Any] | None = None,
        validators: Iterable[Mapping[str, Any]] = (),
    ) -> PublishedArtifact:
        if not isinstance(content, bytes):
            raise TypeError("published content must be bytes")
        contract = CELL_CONTRACTS.get(node_id)
        if contract is None:
            raise ValueError(f"unknown cell contract: {node_id}")
        normalized_validators = self._normalize_validators(
            validators, required_commands=contract.validators
        )
        safe_artifact_name = self._safe_segment(artifact_name, "artifact_name")
        attempt_record = self._load_or_begin_attempt(node_id, attempt, inputs or {})
        self._assert_attempt_identity(attempt_record.manifest, node_id, attempt)
        if attempt_record.manifest.get("contract_version") != contract.version:
            raise ValueError(f"stale attempt contract version: {node_id}/{attempt}")
        if attempt_record.manifest.get("status") not in {
            "planned",
            "reserved",
            "running",
            "repairing",
        }:
            raise RuntimeError(
                f"attempt cannot be reused after status {attempt_record.manifest.get('status')}: "
                f"{node_id}/{attempt}"
            )
        persisted_inputs = attempt_record.manifest.get("inputs")
        if not isinstance(persisted_inputs, Mapping):
            raise ValueError(f"persisted attempt inputs are invalid: {node_id}/{attempt}")
        normalized_inputs = (
            dict(persisted_inputs)
            if inputs is None
            else self._normalize_inputs(inputs)
        )
        if normalized_inputs != persisted_inputs:
            raise ValueError(
                f"publication inputs do not match persisted attempt inputs: {node_id}/{attempt}"
            )
        self._claim_attempt_publication(attempt_record)
        digest = hashlib.sha256(content).hexdigest()
        revision = digest[: self._HASH_PREFIX_LENGTH]
        revision_dir = self._target(
            self.paths.artifacts_dir / safe_artifact_name / revision,
            strict_child=True,
        )
        publication_path = self._target(
            revision_dir / safe_artifact_name,
            strict_child=True,
        )
        artifact_manifest_path = self._target(
            revision_dir / "manifest.json",
            strict_child=True,
        )
        staging_path = self._target(
            attempt_record.staging_dir / safe_artifact_name,
            strict_child=True,
        )
        attempt_record.staging_dir.mkdir(parents=True, exist_ok=True)
        staging_path.write_bytes(content)
        revision_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            revision_dir.mkdir()
        except FileExistsError as exc:
            staging_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"artifact revision already exists: {safe_artifact_name}/{revision}"
            ) from exc
        os.replace(staging_path, publication_path)

        artifact_manifest = {
            "kind": "artifact_manifest",
            "application_id": self.paths.application_id,
            "run_id": attempt_record.manifest.get("run_id", ""),
            "node_id": node_id,
            "attempt": attempt,
            "artifact_name": safe_artifact_name,
            "path": str(publication_path),
            "manifest_path": str(artifact_manifest_path),
            "sha256": digest,
            "revision": revision,
            "inputs": normalized_inputs,
            "validators": normalized_validators,
            "status": "validated",
            "published_at": utc_now_iso(),
        }
        self._write_json_once(
            artifact_manifest_path, artifact_manifest, "artifact revision manifest"
        )

        attempt_manifest = dict(attempt_record.manifest)
        attempt_manifest["validators"] = normalized_validators
        attempt_manifest["outputs"] = [
            *attempt_manifest.get("outputs", []),
            {
                "artifact_name": safe_artifact_name,
                "path": str(publication_path),
                "sha256": digest,
                "revision": revision,
                "manifest_path": str(artifact_manifest_path),
            },
        ]
        attempt_manifest["status"] = "validated"
        attempt_manifest["finished_at"] = utc_now_iso()
        write_json(attempt_record.path, attempt_manifest)
        return PublishedArtifact(
            path=publication_path,
            manifest_path=artifact_manifest_path,
            manifest=artifact_manifest,
        )

    def finish_run(
        self,
        run_id: str,
        *,
        validated_artifacts: Iterable[PublishedArtifact | Mapping[str, Any]],
        blocked_nodes: Iterable[Mapping[str, Any]],
    ) -> RunCompletion:
        run_id = str(run_id)
        if not run_id:
            raise ValueError("run_id is required")
        supplied_artifacts = [
            self._persisted_validated_artifact(item, run_id)
            for item in validated_artifacts
        ]
        supplied_blockers = [
            self._persisted_blocked_node(item, run_id) for item in blocked_nodes
        ]
        plan_nodes = self._load_run_plan_nodes(run_id)
        terminal_attempts = self._load_terminal_attempts(run_id, plan_nodes)
        artifacts = self._discover_validated_artifacts(run_id, terminal_attempts)
        blockers = [
            self._persisted_blocked_node(
                {"node_id": node_id, "attempt": record.manifest["attempt"]},
                run_id,
            )
            for node_id, record in terminal_attempts.items()
            if record.manifest.get("status") == "blocked"
        ]
        discovered_artifact_paths = {
            item["manifest_path"] for item in artifacts
        }
        if any(
            item["manifest_path"] not in discovered_artifact_paths
            for item in supplied_artifacts
        ):
            raise ValueError("supplied artifact is not part of the persisted run")
        discovered_blockers = {
            (item["node_id"], item["attempt"]) for item in blockers
        }
        if any(
            (item["node_id"], item["attempt"]) not in discovered_blockers
            for item in supplied_blockers
        ):
            raise ValueError("supplied blocker is not part of the persisted run")
        manifest = {
            "kind": "run_completion_manifest",
            "application_id": self.paths.application_id,
            "run_id": run_id,
            "validated_artifacts": artifacts,
            "blocked_nodes": blockers,
            "status": "blocked" if blockers else "completed",
            "completed_at": utc_now_iso(),
        }
        manifest_path = self._target(
            self.paths.run_completion_manifest, strict_child=True
        )
        write_json(manifest_path, manifest)
        return RunCompletion(path=manifest_path, manifest=manifest)

    def _load_or_begin_attempt(
        self,
        node_id: str,
        attempt: int,
        inputs: Mapping[str, Any],
    ) -> AttemptManifest:
        attempt_dir = self._attempt_dir(node_id, attempt)
        manifest_path = self._target(attempt_dir / "manifest.json", strict_child=True)
        staging_dir = self._target(attempt_dir / "staging", strict_child=True)
        if not manifest_path.exists():
            return self.begin_attempt(node_id, attempt, inputs=inputs)
        return self._load_attempt(node_id, attempt)

    def _load_attempt(self, node_id: str, attempt: int) -> AttemptManifest:
        attempt_dir = self._attempt_dir(node_id, attempt)
        manifest_path = self._target(attempt_dir / "manifest.json", strict_child=True)
        staging_dir = self._target(attempt_dir / "staging", strict_child=True)
        if not manifest_path.is_file():
            raise ValueError(f"persisted attempt manifest not found: {node_id}/{attempt}")
        manifest = read_json(manifest_path)
        if not isinstance(manifest, Mapping):
            raise ValueError(f"persisted attempt manifest is invalid: {manifest_path}")
        self._assert_attempt_identity(manifest, node_id, attempt)
        return AttemptManifest(
            path=manifest_path,
            staging_dir=staging_dir,
            manifest=dict(manifest),
        )

    def _attempt_dir(self, node_id: str, attempt: int) -> Path:
        safe_node_id = self._safe_segment(node_id, "node_id")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt <= 0:
            raise ValueError("attempt must be a positive integer")
        return self._target(
            self.paths.cells_dir / safe_node_id / str(attempt),
            strict_child=True,
        )

    def _normalize_inputs(self, inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        for name, value in inputs.items():
            key = str(name)
            if isinstance(value, Path):
                input_path = self._target(value)
                if not input_path.is_file():
                    raise ValueError(f"input path is not a file: {input_path}")
                item = {
                    "path": str(input_path),
                    "sha256": self._sha256_file(input_path),
                    "revision": None,
                    "source_kind": "file",
                }
            elif isinstance(value, Mapping):
                item = {
                    "path": str(value.get("path", key)),
                    "sha256": str(value.get("sha256", "")),
                    "revision": value.get("revision"),
                    "source_kind": str(value.get("source_kind", "artifact")),
                }
                if not item["sha256"]:
                    raise ValueError(f"input {key} requires sha256")
            else:
                item = {
                    "path": key,
                    "sha256": str(value),
                    "revision": None,
                    "source_kind": "artifact",
                }
            normalized[key] = item
        return normalized

    def _normalize_validators(
        self,
        validators: Iterable[Mapping[str, Any]],
        *,
        required_commands: Iterable[str],
    ) -> list[dict[str, Any]]:
        normalized = []
        for validator in validators:
            if isinstance(validator, Mapping):
                item = validator
            else:
                raise ValueError(
                    "validator requires an executed result mapping; command strings are not proof"
                )
            command = str(item.get("command", "")).strip()
            if not command:
                raise ValueError("validator command is required")
            if item.get("result") != "passed":
                raise ValueError(f"validator did not pass: {command}")
            report_path = item.get("report_path", "")
            if not report_path:
                raise ValueError(f"validator report_path is required: {command}")
            resolved_report_path = self._target(Path(report_path), strict_child=True)
            if not resolved_report_path.is_file():
                raise ValueError(f"validator report does not exist: {resolved_report_path}")
            normalized.append(
                {
                    "command": command,
                    "result": "passed",
                    "report_path": str(resolved_report_path),
                    "executed_at": str(item.get("executed_at") or utc_now_iso()),
                }
            )
        if not normalized:
            raise ValueError("at least one passed validator is required before publication")
        executed_commands = {item["command"] for item in normalized}
        missing_commands = set(required_commands) - executed_commands
        if missing_commands:
            raise ValueError(
                "missing required validator(s): " + ", ".join(sorted(missing_commands))
            )
        return normalized

    def _persisted_validated_artifact(
        self,
        item: PublishedArtifact | Mapping[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        supplied = item.manifest if isinstance(item, PublishedArtifact) else dict(item)
        manifest_path_value = (
            item.manifest_path
            if isinstance(item, PublishedArtifact)
            else supplied.get("manifest_path")
        )
        if not manifest_path_value:
            raise ValueError("persisted artifact manifest path is required")
        manifest_path = self._target(Path(str(manifest_path_value)), strict_child=True)
        try:
            manifest_path.relative_to(self.paths.artifacts_dir.resolve())
        except ValueError as exc:
            raise ValueError(
                f"persisted artifact manifest must be within artifacts directory: {manifest_path}"
            ) from exc
        if not manifest_path.is_file():
            raise ValueError(f"persisted artifact manifest not found: {manifest_path}")
        persisted = read_json(manifest_path)
        if not isinstance(persisted, Mapping):
            raise ValueError(f"persisted artifact manifest is invalid: {manifest_path}")
        persisted = dict(persisted)
        if supplied != persisted:
            raise ValueError("forged artifact mapping does not match persisted artifact manifest")
        if persisted.get("kind") != "artifact_manifest":
            raise ValueError("persisted artifact manifest has invalid kind")
        if persisted.get("application_id") != self.paths.application_id:
            raise ValueError("foreign artifact manifest belongs to another application")
        if persisted.get("run_id") != run_id:
            raise ValueError("stale artifact manifest belongs to another run")
        if persisted.get("status") != "validated":
            raise ValueError("persisted artifact manifest is not validated")

        artifact_name = self._safe_segment(
            str(persisted.get("artifact_name", "")), "artifact_name"
        )
        revision = self._safe_segment(str(persisted.get("revision", "")), "revision")
        expected_dir = self._target(
            self.paths.artifacts_dir / artifact_name / revision, strict_child=True
        )
        if manifest_path != expected_dir / "manifest.json":
            raise ValueError("persisted artifact manifest path is not canonical")
        artifact_path = self._target(
            Path(str(persisted.get("path", ""))), strict_child=True
        )
        if artifact_path != expected_dir / artifact_name or not artifact_path.is_file():
            raise ValueError("persisted artifact path is missing or not canonical")
        if self._sha256_file(artifact_path) != persisted.get("sha256"):
            raise ValueError("persisted artifact hash does not match content")
        node_id = str(persisted.get("node_id", ""))
        contract = CELL_CONTRACTS.get(node_id)
        if contract is None:
            raise ValueError(f"persisted artifact has unknown cell contract: {node_id}")
        self._normalize_validators(
            persisted.get("validators", []),
            required_commands=contract.validators,
        )

        attempt = persisted.get("attempt")
        attempt_record = self._load_attempt(node_id, attempt)
        if attempt_record.manifest.get("run_id") != run_id:
            raise ValueError("stale artifact attempt belongs to another run")
        if attempt_record.manifest.get("status") != "validated":
            raise ValueError("artifact attempt is not persisted as validated")
        if not any(
            output.get("manifest_path") == str(manifest_path)
            and output.get("sha256") == persisted.get("sha256")
            for output in attempt_record.manifest.get("outputs", [])
            if isinstance(output, Mapping)
        ):
            raise ValueError("artifact is not recorded by its persisted attempt manifest")
        return persisted

    def _load_run_plan_nodes(self, run_id: str) -> tuple[str, ...]:
        safe_run_id = self._safe_segment(run_id, "run_id")
        plan_path = self._target(
            self.paths.plans_dir / f"{safe_run_id}.json", strict_child=True
        )
        if not plan_path.is_file():
            raise ValueError(f"persisted run plan not found: {plan_path}")
        plan = read_json(plan_path)
        if not isinstance(plan, Mapping):
            raise ValueError(f"persisted run plan is invalid: {plan_path}")
        if (
            plan.get("application_id") != self.paths.application_id
            or plan.get("run_id") != run_id
        ):
            raise ValueError("persisted run plan identity mismatch")
        raw_nodes = plan.get("nodes")
        if not isinstance(raw_nodes, list) or not raw_nodes:
            raise ValueError("persisted run plan requires at least one node")
        node_ids: list[str] = []
        for node in raw_nodes:
            if not isinstance(node, Mapping):
                raise ValueError("persisted run plan contains an invalid node")
            node_id = self._safe_segment(str(node.get("node_id", "")), "node_id")
            if node_id not in CELL_CONTRACTS:
                raise ValueError(f"persisted run plan has unknown node: {node_id}")
            node_ids.append(node_id)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("persisted run plan contains duplicate nodes")
        return tuple(node_ids)

    def _load_terminal_attempts(
        self, run_id: str, plan_nodes: Iterable[str]
    ) -> dict[str, AttemptManifest]:
        terminal: dict[str, AttemptManifest] = {}
        for node_id in plan_nodes:
            node_dir = self._target(self.paths.cells_dir / node_id, strict_child=True)
            attempts: list[AttemptManifest] = []
            if node_dir.is_dir():
                for attempt_dir in node_dir.iterdir():
                    if not attempt_dir.is_dir() or not attempt_dir.name.isdigit():
                        continue
                    record = self._load_attempt(node_id, int(attempt_dir.name))
                    if record.manifest.get("run_id") == run_id:
                        attempts.append(record)
            if not attempts:
                raise ValueError(f"run has no persisted attempt for planned node: {node_id}")
            latest = max(attempts, key=lambda item: item.manifest["attempt"])
            status = latest.manifest.get("status")
            if status not in {"validated", "blocked"}:
                raise ValueError(
                    f"run has nonterminal attempt for {node_id}: {status}"
                )
            if status == "validated" and not latest.manifest.get("outputs"):
                raise ValueError(
                    f"validated attempt has no persisted outputs: {node_id}"
                )
            terminal[node_id] = latest
        return terminal

    def _discover_validated_artifacts(
        self,
        run_id: str,
        terminal_attempts: Mapping[str, AttemptManifest],
    ) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        seen_manifest_paths: set[str] = set()
        for node_id, terminal_attempt in terminal_attempts.items():
            if terminal_attempt.manifest.get("status") != "validated":
                continue
            for output in terminal_attempt.manifest.get("outputs", []):
                if not isinstance(output, Mapping) or not output.get("manifest_path"):
                    raise ValueError(
                        f"validated attempt has invalid persisted output: {node_id}"
                    )
                manifest_path = self._target(
                    Path(str(output["manifest_path"])), strict_child=True
                )
                if not manifest_path.is_file():
                    raise ValueError(
                        f"persisted output manifest not found for {node_id}: {manifest_path}"
                    )
                persisted = read_json(manifest_path)
                if not isinstance(persisted, Mapping):
                    raise ValueError(
                        f"persisted output manifest is invalid: {manifest_path}"
                    )
                artifact = self._persisted_validated_artifact(persisted, run_id)
                if (
                    artifact.get("node_id") != node_id
                    or artifact.get("attempt")
                    != terminal_attempt.manifest.get("attempt")
                ):
                    raise ValueError(
                        f"persisted output belongs to a stale attempt: {manifest_path}"
                    )
                for key in (
                    "artifact_name",
                    "path",
                    "sha256",
                    "revision",
                    "manifest_path",
                ):
                    if output.get(key) != artifact.get(key):
                        raise ValueError(
                            f"persisted output provenance mismatch for {node_id}: {key}"
                        )
                if artifact["manifest_path"] in seen_manifest_paths:
                    raise ValueError(
                        f"duplicate persisted output manifest: {artifact['manifest_path']}"
                    )
                seen_manifest_paths.add(artifact["manifest_path"])
                artifacts.append(artifact)
        return artifacts

    def _persisted_blocked_node(
        self, item: Mapping[str, Any], run_id: str
    ) -> dict[str, Any]:
        if not isinstance(item, Mapping):
            raise TypeError("blocked node reference must be a mapping")
        node_id = str(item.get("node_id", ""))
        attempt = item.get("attempt")
        if not node_id or attempt is None:
            raise ValueError("persisted blocked attempt requires node_id and attempt")
        record = self._load_attempt(node_id, attempt)
        persisted = record.manifest
        expected_identity = {
            "application_id": self.paths.application_id,
            "run_id": run_id,
            "node_id": node_id,
            "attempt": attempt,
            "status": "blocked",
        }
        if any(persisted.get(key) != value for key, value in expected_identity.items()):
            raise ValueError("persisted blocked attempt does not match run or blocked status")
        for key, value in item.items():
            if key == "manifest_path":
                if self._target(Path(str(value)), strict_child=True) != record.path:
                    raise ValueError("forged blocked node manifest path")
            elif key in persisted and persisted.get(key) != value:
                raise ValueError("forged blocked node mapping does not match persisted attempt")
        return {
            "node_id": node_id,
            "attempt": attempt,
            "status": "blocked",
            "manifest_path": str(record.path),
        }

    def _assert_attempt_identity(
        self, manifest: Mapping[str, Any], node_id: str, attempt: int
    ) -> None:
        if (
            manifest.get("kind") != "cell_attempt_manifest"
            or manifest.get("application_id") != self.paths.application_id
            or manifest.get("node_id") != node_id
            or manifest.get("attempt") != attempt
        ):
            raise ValueError(f"persisted attempt manifest identity mismatch: {node_id}/{attempt}")

    @staticmethod
    def _claim_attempt_publication(attempt: AttemptManifest) -> None:
        claim_path = attempt.path.parent / "publication.claim"
        try:
            descriptor = os.open(
                claim_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            raise RuntimeError(
                f"attempt cannot be reused for publication: "
                f"{attempt.manifest.get('node_id')}/{attempt.manifest.get('attempt')}"
            ) from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(utc_now_iso() + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _write_json_once(path: Path, data: Any, label: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, path)
            except FileExistsError as exc:
                raise RuntimeError(f"{label} already exists: {path}") from exc
        finally:
            Path(temporary_name).unlink(missing_ok=True)

    def _target(self, path: Path, *, strict_child: bool = False) -> Path:
        target = Path(path).resolve()
        try:
            relative = target.relative_to(self.application_dir)
        except ValueError as exc:
            raise ValueError(
                f"path must be within application directory: {target}"
            ) from exc
        if strict_child and relative == Path("."):
            raise ValueError(
                f"path must be strictly within application directory: {target}"
            )
        return target

    @staticmethod
    def _safe_segment(value: str, field: str) -> str:
        candidate = str(value)
        if not candidate or candidate in {".", ".."} or Path(candidate).name != candidate:
            raise ValueError(
                f"{field} must name one path segment within the application directory"
            )
        return candidate

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
