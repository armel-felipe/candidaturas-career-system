from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        staging_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "kind": "cell_attempt_manifest",
            "application_id": self.paths.application_id,
            "run_id": str(run_id),
            "node_id": node_id,
            "attempt": attempt,
            "contract_version": str(contract_version),
            "inputs": self._normalize_inputs(inputs or {}),
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
        write_json(manifest_path, manifest)
        return AttemptManifest(path=manifest_path, staging_dir=staging_dir, manifest=manifest)

    def write_handover(
        self,
        node_id: str,
        attempt: int,
        handover: Mapping[str, Any],
    ) -> Path:
        attempt_dir = self._attempt_dir(node_id, attempt)
        handover_path = self._target(
            attempt_dir / "handover_summary.json", strict_child=True
        )
        write_json(handover_path, dict(handover))
        return handover_path

    def publish_file(
        self,
        node_id: str,
        attempt: int,
        artifact_name: str,
        content: bytes,
        *,
        inputs: Mapping[str, Any] | None = None,
        validators: Iterable[Mapping[str, Any] | str] = (),
    ) -> PublishedArtifact:
        if not isinstance(content, bytes):
            raise TypeError("published content must be bytes")
        safe_artifact_name = self._safe_segment(artifact_name, "artifact_name")
        attempt_record = self._load_or_begin_attempt(node_id, attempt, inputs or {})
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
        revision_dir.mkdir(parents=True, exist_ok=True)
        if publication_path.exists():
            if self._sha256_file(publication_path) != digest:
                staging_path.unlink()
                raise RuntimeError(f"artifact revision prefix collision: {revision}")
            staging_path.unlink()
        else:
            os.replace(staging_path, publication_path)

        normalized_inputs = self._normalize_inputs(inputs or attempt_record.manifest["inputs"])
        normalized_validators = self._normalize_validators(validators)
        artifact_manifest = {
            "kind": "artifact_manifest",
            "application_id": self.paths.application_id,
            "run_id": attempt_record.manifest.get("run_id", ""),
            "node_id": node_id,
            "attempt": attempt,
            "artifact_name": safe_artifact_name,
            "path": str(publication_path),
            "sha256": digest,
            "revision": revision,
            "inputs": normalized_inputs,
            "validators": normalized_validators,
            "status": "validated",
            "published_at": utc_now_iso(),
        }
        write_json(artifact_manifest_path, artifact_manifest)

        attempt_manifest = dict(attempt_record.manifest)
        attempt_manifest["inputs"] = normalized_inputs
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
        artifacts = [self._validated_artifact(item) for item in validated_artifacts]
        blockers = [dict(item) for item in blocked_nodes]
        if any(not item.get("node_id") for item in blockers):
            raise ValueError("every blocked node requires a node_id")
        manifest = {
            "kind": "run_completion_manifest",
            "application_id": self.paths.application_id,
            "run_id": str(run_id),
            "validated_artifacts": artifacts,
            "blocked_nodes": blockers,
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
        return AttemptManifest(
            path=manifest_path,
            staging_dir=staging_dir,
            manifest=read_json(manifest_path),
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
        validators: Iterable[Mapping[str, Any] | str],
    ) -> list[dict[str, Any]]:
        normalized = []
        for validator in validators:
            if isinstance(validator, str):
                item: Mapping[str, Any] = {"command": validator, "result": "passed"}
            elif isinstance(validator, Mapping):
                item = validator
            else:
                raise TypeError("validator must be a command or mapping")
            report_path = item.get("report_path", "")
            if report_path:
                report_path = str(self._target(Path(report_path)))
            normalized.append(
                {
                    "command": str(item.get("command", "")),
                    "result": item.get("result"),
                    "report_path": report_path,
                    "executed_at": str(item.get("executed_at") or utc_now_iso()),
                }
            )
        return normalized

    def _validated_artifact(
        self, item: PublishedArtifact | Mapping[str, Any]
    ) -> dict[str, Any]:
        manifest = item.manifest if isinstance(item, PublishedArtifact) else dict(item)
        if manifest.get("status") != "validated":
            raise ValueError("run completion accepts only validated artifacts")
        artifact_path = manifest.get("path")
        if artifact_path:
            self._target(Path(str(artifact_path)), strict_child=True)
        return dict(manifest)

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
