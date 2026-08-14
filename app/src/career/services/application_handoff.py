from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from career.cells.contracts import CELL_CONTRACTS, CONTRACT_VERSION
from career.cells.manifests import ManifestStore
from career.cells.planner import NodePlan, RunPlan
from career.services.agent_requests import CellRequestBuilder
from career.services.application_context import paths_for, validate_application_id
from career.services.canary_control import CanaryTarget, resolve_target_from_compose
from career.services.database import Database
from career.utils import read_json, utc_now_iso, write_json


APPROVED_BOTS = ("vagas_bot_01", "vagas_bot_02")
DEFAULT_COMPOSE = Path(__file__).resolve().parents[3] / "deploy" / "hermes" / "compose.yaml"
# The runtime library lives under ``app/`` while the operator's canonical
# intake state is kept at the repository root, one level above that runtime.
DEFAULT_SOURCE_ROOT = Path(__file__).resolve().parents[4] / ".career-state" / "applications_v2"
REQUIRED_DERIVED = (
    "job_normalized.json",
    "handover_summary.json",
    "evidence_index.json",
)
PROJECTED_FILES = (
    "job_description.md",
    "identity.json",
    "fit_map.draft.json",
)
MAX_PROJECTED_BYTES = 256 * 1024
LINKEDIN_JOB_RE = re.compile(r"linkedin\.com/jobs/view/(\d+)", re.IGNORECASE)


class HandoffError(RuntimeError):
    """Fail-closed error raised when a controlled handoff cannot proceed."""


class ApplicationHandoffService:
    """Project one canonical application into one resolved bot workspace.

    This service is deliberately operator-side. It prepares a bounded cell and
    returns; it never invokes an agent, Notion, CV generation, email, or cloud
    delivery side effect.
    """

    def __init__(
        self,
        *,
        compose_path: str | Path | None = None,
        source_root: str | Path | None = None,
    ):
        self.compose_path = Path(compose_path or DEFAULT_COMPOSE).resolve()
        self.source_root = Path(source_root or DEFAULT_SOURCE_ROOT).resolve()

    def resolve_target(self, target_bot: str) -> CanaryTarget:
        target_bot = str(target_bot or "").strip()
        if target_bot not in APPROVED_BOTS:
            raise ValueError(f"target bot must be one of: {', '.join(APPROVED_BOTS)}")
        if not self.compose_path.is_file():
            raise FileNotFoundError(f"compose file not found: {self.compose_path}")
        return resolve_target_from_compose(
            compose_path=self.compose_path,
            bot_name=target_bot,
        )

    def handoff(
        self,
        application_id: str,
        target_bot: str,
        *,
        dry_run: bool = False,
        apply: bool = False,
    ) -> dict[str, Any]:
        if dry_run and apply:
            raise ValueError("dry_run and apply are mutually exclusive")
        if not dry_run and not apply:
            dry_run = True
        application_id = validate_application_id(application_id)
        target = self.resolve_target(target_bot)
        source_app = (self.source_root / application_id).resolve()
        source_root = self.source_root.resolve()
        if not source_app.is_relative_to(source_root):
            raise ValueError("source application escapes source root")
        source = self._validate_source(source_app, application_id)
        source_fingerprint = source["fingerprint"]
        target_paths = paths_for(application_id, root=target.state_root / "applications_v2")
        profile_id = self._profile_id(target)
        database = self._open_database(target, initialize=apply)
        try:
            existing = self._existing_handoff(
                database,
                application_id=application_id,
                target_bot=target.bot_name,
                fingerprint=source_fingerprint,
            )
            if existing is not None:
                if existing["status"] == "conflict":
                    raise HandoffError(existing["reason"])
                return existing

            target_state = self._inspect_target_state(
                database, target_paths.app_dir, application_id, source_fingerprint
            )
            quarantine = self._quarantine_path(
                target.state_root, application_id, source_fingerprint
            )
            projection = self._projection_manifest(
                source_app,
                target_paths.app_dir,
                source_fingerprint,
                target.bot_name,
                quarantine if target_state["stale"] else None,
            )
            result: dict[str, Any] = {
                "status": "dry_run" if dry_run else "planned",
                "application_id": application_id,
                "target_bot": target.bot_name,
                "source": str(source_app),
                "target": str(target_paths.app_dir),
                "source_fingerprint": source_fingerprint,
                "profile_id": profile_id,
                "projection": projection,
                "cell": {"node_id": "analyze_fit", "status": "pending"},
            }
            if dry_run:
                return result

            return self._apply(
                database,
                target,
                target_paths,
                source,
                profile_id=profile_id,
                target_state=target_state,
                quarantine=quarantine,
                projection=projection,
            )
        finally:
            database.close()

    def _open_database(self, target: CanaryTarget, *, initialize: bool) -> Database:
        ledger = target.authority_ledger_path if target.authority_ledger_path.is_file() else None
        database = Database(target.control_db_path, authority_ledger_path=ledger)
        if initialize:
            database.init_schema()
        elif target.control_db_path.is_file():
            # Dry-run may inspect an existing schema, but must not create one.
            try:
                database.fetch_one("SELECT 1 FROM applications LIMIT 1")
            except Exception:
                database.close()
                raise HandoffError("existing control-plane cannot be inspected")
        return database

    @staticmethod
    def _profile_id(target: CanaryTarget) -> str:
        compose = yaml.safe_load(target.compose_path.read_text(encoding="utf-8")) or {}
        service = (compose.get("services") or {}).get(target.bot_name) or {}
        environment = service.get("environment") or {}
        if isinstance(environment, list):
            environment = {
                str(item).split("=", 1)[0]: str(item).split("=", 1)[1]
                for item in environment
                if "=" in str(item)
            }
        return str(environment.get("CAREER_HERMES_PROFILE_ID") or target.bot_name).strip()

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _validate_source(self, source_app: Path, application_id: str) -> dict[str, Any]:
        if not source_app.is_dir():
            raise FileNotFoundError(f"source application not found: {source_app}")
        identity_path = source_app / "identity.json"
        job_path = source_app / "job_description.md"
        draft_path = source_app / "fit_map.draft.json"
        if not identity_path.is_file() or not job_path.is_file() or not draft_path.is_file():
            raise HandoffError("source is missing identity.json, job_description.md, or fit_map.draft.json")
        try:
            identity = read_json(identity_path)
            draft = read_json(draft_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise HandoffError(f"source JSON is invalid: {exc}") from exc
        if identity.get("application_id") != application_id:
            raise ValueError("identity application_id does not match requested application")
        company = str(identity.get("company") or "").strip()
        role = str(identity.get("role") or "").strip()
        source_url = str(identity.get("source_id") or identity.get("source_url") or "").strip()
        if not company or not role or not source_url:
            raise HandoffError("source identity needs company, role, and source URL")
        job_match = LINKEDIN_JOB_RE.search(source_url)
        if not job_match:
            raise HandoffError("source URL must contain a LinkedIn job ID")
        aliases = identity.get("aliases") if isinstance(identity.get("aliases"), dict) else {}
        alias_url = str(aliases.get("linkedin_job_source_id") or source_url).strip()
        if alias_url != source_url:
            raise HandoffError("identity LinkedIn source aliases are inconsistent")
        if isinstance(draft, dict) and draft.get("application_id") not in {None, application_id}:
            raise ValueError("fit_map draft application_id does not match requested application")
        derived = source_app / "derived"
        missing_derived = [name for name in REQUIRED_DERIVED if not (derived / name).is_file()]
        if missing_derived:
            raise HandoffError("source is missing compact derived inputs: " + ", ".join(missing_derived))
        projected = [job_path, identity_path, draft_path, *(derived / name for name in REQUIRED_DERIVED)]
        total_bytes = sum(path.stat().st_size for path in projected)
        if total_bytes > MAX_PROJECTED_BYTES:
            raise HandoffError(f"projected inputs exceed bounded payload: {total_bytes} bytes")
        return {
            "identity": identity,
            "draft": draft,
            "company": company,
            "role": role,
            "source_url": source_url,
            "job_id": job_match.group(1),
            "job_path": job_path,
            "identity_path": identity_path,
            "draft_path": draft_path,
            "derived": derived,
            "fingerprint": self._sha256(job_path),
            "projected": projected,
        }

    def _existing_handoff(
        self,
        database: Database,
        *,
        application_id: str,
        target_bot: str,
        fingerprint: str,
    ) -> dict[str, Any] | None:
        try:
            events = database.fetch_all(
                "SELECT event, fingerprint, metadata FROM workflow_events "
                "WHERE application_id = ? ORDER BY id",
                (application_id,),
            )
        except Exception:
            return None
        for row in events:
            if row["event"] != "controlled_handoff_prepared":
                continue
            metadata = json.loads(row["metadata"] or "{}")
            prior_bot = str(metadata.get("target_bot") or "").strip()
            prior_fingerprint = str(row["fingerprint"] or "")
            if prior_bot != target_bot:
                return {
                    "status": "conflict",
                    "reason": f"application already handed off to another bot: {prior_bot or 'unknown'}",
                }
            if prior_fingerprint == fingerprint:
                return {
                    "status": "idempotent",
                    "application_id": application_id,
                    "target_bot": target_bot,
                    "source_fingerprint": fingerprint,
                    "run_id": metadata.get("run_id"),
                    "cell": metadata.get("cell") or {"node_id": "analyze_fit", "status": "reserved"},
                }
            return {
                "status": "conflict",
                "reason": "application has an existing handoff with a different source fingerprint",
            }
        return None

    @staticmethod
    def _inspect_target_state(
        database: Database,
        target_app: Path,
        application_id: str,
        source_fingerprint: str,
    ) -> dict[str, bool]:
        if not target_app.exists():
            return {"exists": False, "stale": False, "live": False}
        identity_path = target_app / "identity.json"
        job_path = target_app / "job_description.md"
        handoff_manifest = target_app / "handoff_manifest.json"
        live = False
        try:
            live = bool(
                database.fetch_one(
                    """SELECT 1 FROM cell_attempts a
                       JOIN application_runs r ON r.run_id = a.run_id
                       WHERE r.application_id = ? AND a.status IN ('reserved', 'running')
                       LIMIT 1""",
                    (application_id,),
                )
            )
            live = live or bool(
                database.fetch_one(
                    """SELECT 1 FROM workspace_leases
                       WHERE lease_name = 'authoritative-workspace' AND expires_at > ?
                       LIMIT 1""",
                    (utc_now_iso(),),
                )
            )
        except Exception:
            live = False
        identity_matches = False
        if identity_path.is_file():
            try:
                identity_matches = read_json(identity_path).get("application_id") == application_id
            except (OSError, json.JSONDecodeError):
                identity_matches = False
        fingerprint_matches = (
            job_path.is_file()
            and hashlib.sha256(job_path.read_bytes()).hexdigest() == source_fingerprint
        )
        manifest_matches = False
        if handoff_manifest.is_file():
            try:
                manifest_matches = read_json(handoff_manifest).get("source_fingerprint") == source_fingerprint
            except (OSError, json.JSONDecodeError):
                manifest_matches = False
        return {
            "exists": True,
            "stale": not (identity_matches and fingerprint_matches and manifest_matches),
            "live": live,
        }

    @staticmethod
    def _quarantine_path(state_root: Path, application_id: str, fingerprint: str) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return state_root / ".handoff_quarantine" / f"{stamp}_{application_id}_{fingerprint[:12]}"

    def _projection_manifest(
        self,
        source_app: Path,
        target_app: Path,
        fingerprint: str,
        target_bot: str,
        quarantine: Path | None,
    ) -> dict[str, Any]:
        files = []
        for relative in PROJECTED_FILES:
            source = source_app / relative
            files.append(self._file_entry(source, target_app / relative))
        for relative in (Path("derived") / name for name in REQUIRED_DERIVED):
            files.append(self._file_entry(source_app / relative, target_app / relative))
        return {
            "target_bot": target_bot,
            "source_fingerprint": fingerprint,
            "quarantine": str(quarantine) if quarantine else None,
            "files": files,
        }

    def _file_entry(self, source: Path, target: Path) -> dict[str, Any]:
        return {
            "source": str(source),
            "target": str(target),
            "sha256": self._sha256(source),
            "bytes": source.stat().st_size,
        }

    def _apply(
        self,
        database: Database,
        target: CanaryTarget,
        target_paths,
        source: dict[str, Any],
        *,
        profile_id: str,
        target_state: dict[str, bool],
        quarantine: Path,
        projection: dict[str, Any],
    ) -> dict[str, Any]:
        if target_state["live"]:
            raise HandoffError("target application has an active cell attempt")
        application_id = target_paths.application_id
        run_id = f"run_handoff_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:10]}"
        attempt = 1
        node_id = "analyze_fit"
        contract = CELL_CONTRACTS[node_id]
        plan = RunPlan(
            run_id=run_id,
            application_id=application_id,
            nodes=(
                NodePlan(
                    node_id=node_id,
                    requires=(),
                    produces=contract.produces,
                    validators=contract.validators,
                    resources=contract.resources,
                    invalidates=contract.invalidates,
                    repair_scope=contract.repair_scope,
                    max_attempts=contract.max_attempts,
                    allows_external_effect=False,
                    contract_version=CONTRACT_VERSION,
                ),
            ),
            edges=(),
            resource_locks=(),
            created_at=utc_now_iso(),
            contract_version=CONTRACT_VERSION,
        )
        moved = False
        try:
            if target_state["exists"]:
                if quarantine.exists():
                    raise HandoffError(f"quarantine path already exists: {quarantine}")
                quarantine.parent.mkdir(parents=True, exist_ok=True)
                target_paths.app_dir.rename(quarantine)
                moved = True
            self._project_files(source, target_paths.app_dir)
            target_paths.plans_dir.mkdir(parents=True, exist_ok=True)
            write_json(target_paths.plans_dir / f"{run_id}.json", plan.as_dict())
            run_paths = replace(
                target_paths,
                cells_dir=target_paths.cells_dir / run_id,
                artifacts_dir=target_paths.artifacts_dir / run_id,
                reviews_dir=target_paths.reviews_dir / run_id,
                run_completion_manifest=target_paths.app_dir / "runs" / run_id / "run_completion_manifest.json",
            )
            manifest_store = ManifestStore(run_paths)
            input_paths = {
                "job_description": run_paths.job_description,
                "identity": run_paths.identity,
                "fit_map_draft": run_paths.fit_map_draft,
                "job_normalized": run_paths.derived_dir / "job_normalized.json",
                "handover_summary": run_paths.derived_dir / "handover_summary.json",
                "evidence_index": run_paths.derived_dir / "evidence_index.json",
            }
            manifest = manifest_store.begin_attempt(
                node_id,
                attempt,
                run_id=run_id,
                contract_version=CONTRACT_VERSION,
                inputs=input_paths,
                read_paths=tuple(input_paths.values()),
                write_paths=(run_paths.fit_map, run_paths.cells_dir / node_id / str(attempt) / "staging"),
                context={"handoff": True, "target_bot": target.bot_name, "source_fingerprint": source["fingerprint"]},
                status="reserved",
            )
            now = utc_now_iso()
            expires_at = (datetime.now(UTC) + timedelta(hours=24)).isoformat()
            graph_json = json.dumps(plan.as_dict(), sort_keys=True, separators=(",", ":"))
            normalized_inputs = self._normalized_inputs(input_paths)
            with database.transaction(immediate=True) as conn:
                existing_app = conn.execute(
                    "SELECT id, company, role FROM applications WHERE id = ?", (application_id,)
                ).fetchone()
                if existing_app is not None and (
                    existing_app["company"] != source["company"] or existing_app["role"] != source["role"]
                ):
                    raise HandoffError("existing application identity conflicts with canonical source")
                conn.execute(
                    """INSERT INTO applications
                       (id, company, role, source_type, source_url, stage, funil_stage,
                        status, created_at, updated_at, job_description_path, fit_map_path)
                       VALUES (?, ?, ?, ?, ?, 'analyze_pending', 'Fila Agente',
                               'handoff_ready', ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET company=excluded.company,
                         role=excluded.role, source_type=excluded.source_type,
                         source_url=excluded.source_url, stage=excluded.stage,
                         funil_stage=excluded.funil_stage, status=excluded.status,
                         updated_at=excluded.updated_at, job_description_path=excluded.job_description_path,
                         fit_map_path=excluded.fit_map_path""",
                    (application_id, source["company"], source["role"], "linkedin_job", source["source_url"], now, now, str(target_paths.job_description), str(target_paths.fit_map)),
                )
                by_profile = conn.execute(
                    "SELECT application_id FROM profile_application_bindings WHERE profile_id = ? AND status = 'active'",
                    (profile_id,),
                ).fetchone()
                if by_profile is not None and by_profile["application_id"] != application_id:
                    raise HandoffError("target bot profile already owns another active application")
                by_app = conn.execute(
                    "SELECT profile_id FROM profile_application_bindings WHERE application_id = ? AND status = 'active'",
                    (application_id,),
                ).fetchone()
                if by_app is not None and by_app["profile_id"] != profile_id:
                    raise HandoffError("application is already owned by another bot profile")
                conn.execute(
                    """INSERT INTO profile_application_bindings
                       (profile_id, application_id, source, status, claimed_at)
                       VALUES (?, ?, 'controlled_handoff', 'active', ?)
                       ON CONFLICT(profile_id) DO UPDATE SET application_id=excluded.application_id,
                         source=excluded.source, status='active', claimed_at=excluded.claimed_at""",
                    (profile_id, application_id, now),
                )
                conn.execute(
                    "INSERT INTO application_runs (run_id, application_id, graph_json, contract_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (run_id, application_id, graph_json, CONTRACT_VERSION, now, now),
                )
                conn.execute(
                    "INSERT INTO cell_nodes (run_id, node_id, status, requires_json, reserved_by, reservation_expires_at, latest_attempt, created_at, updated_at) VALUES (?, ?, 'reserved', '[]', ?, ?, ?, ?, ?)",
                    (run_id, node_id, target.bot_name, expires_at, attempt, now, now),
                )
                conn.execute(
                    "INSERT INTO cell_attempts (run_id, node_id, attempt, worker_id, status, created_at, inputs_registered_at) VALUES (?, ?, ?, ?, 'reserved', ?, ?)",
                    (run_id, node_id, attempt, target.bot_name, now, now),
                )
                conn.executemany(
                    """INSERT INTO cell_inputs
                       (run_id, node_id, attempt, input_name, source_kind, source_node_id,
                        source_attempt, source_id, version, path, content_hash, required, created_at)
                       VALUES (?, ?, ?, ?, 'file', NULL, NULL, NULL, NULL, ?, ?, 1, ?)""",
                    [
                        (run_id, node_id, attempt, name, item["path"], item["content_hash"], now)
                        for name, item in normalized_inputs.items()
                    ],
                )
            request = CellRequestBuilder(database).build(
                run_id=run_id,
                node_id=node_id,
                attempt=attempt,
                cellular_context={
                    "cellular": True,
                    "manifest_path": str(manifest.path),
                    "read_allowlist": [str(path.resolve()) for path in input_paths.values()],
                    "write_allowlist": [str(run_paths.fit_map.resolve())],
                    "objective": "Execute only the analyze_fit cell for this application.",
                },
            )
            CellRequestBuilder.materialize(request, manifest.path.parent)
            handoff_manifest = {
                "kind": "controlled_application_handoff",
                "application_id": application_id,
                "target_bot": target.bot_name,
                "source_fingerprint": source["fingerprint"],
                "run_id": run_id,
                "node_id": node_id,
                "attempt": attempt,
                "projection": projection,
                "request_bytes": len(json.dumps(request, sort_keys=True).encode("utf-8")),
                "created_at": now,
            }
            write_json(target_paths.app_dir / "handoff_manifest.json", handoff_manifest)
            write_json(
                target_paths.state,
                {
                    "kind": "application_state",
                    "application_id": application_id,
                    "stage": "analyze_pending",
                    "stage_status": "reserved",
                    "source_fingerprint": source["fingerprint"],
                    "handoff_run_id": run_id,
                    "updated_at": now,
                },
            )
            database.execute(
                "INSERT INTO workflow_events (application_id, event, fingerprint, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
                (application_id, "controlled_handoff_prepared", source["fingerprint"], json.dumps({"target_bot": target.bot_name, "profile_id": profile_id, "run_id": run_id, "cell": {"node_id": node_id, "attempt": attempt, "status": "reserved"}, "projection": projection}), now),
            )
            self._normalize_permissions(target, target_paths.app_dir)
            return {
                "status": "applied",
                "application_id": application_id,
                "target_bot": target.bot_name,
                "source_fingerprint": source["fingerprint"],
                "run_id": run_id,
                "cell": {"node_id": node_id, "attempt": attempt, "status": "reserved"},
                "target": str(target_paths.app_dir),
                "quarantine": str(quarantine) if moved else None,
            }
        except Exception:
            self._rollback_projection(target_paths.app_dir, quarantine if moved else None, database, application_id, run_id)
            raise

    def _project_files(self, source: dict[str, Any], target_app: Path) -> None:
        target_app.mkdir(parents=True, exist_ok=True)
        for source_path in source["projected"]:
            relative = source_path.relative_to(source["job_path"].parent)
            target_path = target_app / relative
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

    @staticmethod
    def _normalized_inputs(input_paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "path": str(path.resolve()),
                "content_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
                "required": 1,
            }
            for name, path in input_paths.items()
        }

    @staticmethod
    def _normalize_permissions(target: CanaryTarget, app_dir: Path) -> None:
        owner_uid = os.stat(target.state_root).st_uid
        owner_gid = os.stat(target.state_root).st_gid
        for path in sorted(app_dir.rglob("*"), key=lambda item: (item.is_file(), str(item))):
            os.chown(path, owner_uid, owner_gid)
            os.chmod(path, 0o640 if path.is_file() else 0o750)
        os.chown(app_dir, owner_uid, owner_gid)
        os.chmod(app_dir, 0o750)

    @staticmethod
    def _rollback_projection(
        app_dir: Path,
        quarantine: Path | None,
        database: Database,
        application_id: str,
        run_id: str,
    ) -> None:
        shutil.rmtree(app_dir, ignore_errors=True)
        if quarantine is not None and quarantine.is_dir() and not app_dir.exists():
            app_dir.parent.mkdir(parents=True, exist_ok=True)
            quarantine.rename(app_dir)
        try:
            with database.transaction(immediate=True) as conn:
                conn.execute("DELETE FROM workflow_events WHERE application_id = ? AND event = 'controlled_handoff_prepared' AND fingerprint = (SELECT fingerprint FROM workflow_events WHERE application_id = ? AND event = 'controlled_handoff_prepared' ORDER BY id DESC LIMIT 1)", (application_id, application_id))
                conn.execute("DELETE FROM cell_requests WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM cell_inputs WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM cell_attempts WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM cell_nodes WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM application_runs WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM profile_application_bindings WHERE application_id = ? AND source = 'controlled_handoff'", (application_id,))
                conn.execute("DELETE FROM applications WHERE id = ? AND status = 'handoff_ready'", (application_id,))
        except Exception:
            pass
