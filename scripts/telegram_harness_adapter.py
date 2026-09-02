#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.services.harness_supervisor import HarnessSupervisor
from career.services.application_context import canonical_database
from career.services.harness_command_store import (
    FINAL_STATUSES as _COMMAND_FINAL_STATUSES,
    HarnessCommandStore,
)
from career.utils import read_json, utc_now_iso, write_json


_TERMINAL_DISPATCH_STATUSES = frozenset({
    "completed", "blocked", "awaiting_input", "awaiting_approval", "ready"
})


def _nested_blocked_reply(result: dict[str, Any]) -> str | None:
    """Return a safe user-facing reply for a blocked supervisor result."""
    payload = result.get("result") if isinstance(result, dict) else None
    if not isinstance(payload, dict):
        return None
    display_text = payload.get("display_text")
    if isinstance(display_text, str) and display_text.strip():
        return display_text.strip()
    if str(payload.get("status") or "") != "blocked":
        return None

    blocker_reason = ""
    current: Any = payload
    for _ in range(5):
        if not isinstance(current, dict):
            break
        candidate = str(current.get("blocker_reason") or "").strip()
        if candidate:
            blocker_reason = candidate
            break
        current = current.get("result")

    if blocker_reason == "explicit_application_scope_required":
        return (
            "Não consegui continuar porque a candidatura não está vinculada "
            "a esta sessão. Nenhuma etapa foi executada."
        )
    if blocker_reason:
        return (
            "A solicitação foi bloqueada pelo fluxo canônico "
            f"({blocker_reason}). Nenhuma etapa foi executada."
        )
    return "A solicitação foi bloqueada pelo fluxo canônico. Nenhuma etapa foi executada."


def _dispatch_dir(root: Path, message_id: str) -> Path:
    raw_id = str(message_id or "").strip()
    if not raw_id:
        raise ValueError("message_id is required for harness dispatch")
    # Always hash the external identifier.  Keeping a readable ID for some
    # inputs would collide with an unsafe ID whose digest happens to equal it.
    safe_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
    return root / ".career-state" / "harness" / "dispatches" / safe_id


def _parse_timestamp(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _lease_alive(lease: dict[str, Any]) -> bool:
    expires_at = _parse_timestamp(lease.get("expires_at"))
    if expires_at is None or expires_at <= datetime.now(timezone.utc):
        return False
    try:
        pid = int(lease.get("pid") or 0)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@contextmanager
def _dispatch_lock(dispatch_dir: Path):
    import fcntl

    dispatch_dir.mkdir(parents=True, exist_ok=True)
    lock_path = dispatch_dir / ".lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def dispatch_harness_job(
    payload: dict[str, Any], *, root: Path = ROOT
) -> dict[str, Any]:
    """Persist and start one bounded worker for a Hermes pre-LLM request."""
    message_id = str(payload.get("message_id") or "").strip()
    # SQLite is the authority for the inbound turn.  The dispatch directory
    # below remains a transport/debug mirror while the worker migration is
    # rolled out; it may never choose a different scope or replay a command.
    command_store = HarnessCommandStore(canonical_database(root=root))
    command = command_store.enqueue(payload)
    command_id = str(command["command_id"])
    command_status = str(command["status"])
    if command.get("deduplicated") and command_status in _COMMAND_FINAL_STATUSES:
        stored_result = _command_result(command)
        return {
            **stored_result,
            "request_id": message_id,
            "message_id": message_id,
            "command_id": command_id,
            **_dispatch_metadata(payload, command_status),
            "deduplicated": True,
        }
    if command.get("deduplicated"):
        # A live command is already owned by a worker.  Never consult its
        # filesystem mirror to decide whether that worker is alive: a process
        # restart is recovered by the database claim lease, not by turning the
        # user's replay into a canonical block.
        return {
            "status": "awaiting_agent",
            "request_id": message_id,
            "message_id": message_id,
            "command_id": command_id,
            **_dispatch_metadata(
                {
                    **payload,
                    "runtime_context": {
                        **(payload.get("runtime_context") if isinstance(payload.get("runtime_context"), dict) else {}),
                        "application_id": command.get("application_id"),
                        "run_id": command.get("run_id"),
                    },
                },
                "awaiting_agent",
            ),
            "worker_started": False,
            "deduplicated": True,
        }
    dispatch_dir = _dispatch_dir(root, message_id)
    with _dispatch_lock(dispatch_dir):
        status_path = dispatch_dir / "status.json"
        result_path = dispatch_dir / "result.json"
        lease_path = dispatch_dir / "lease.json"
        if status_path.is_file():
            status = read_json(status_path)
            current_status = str(status.get("status") or "")
            original_payload = payload
            request_path = dispatch_dir / "request.json"
            if request_path.is_file():
                try:
                    stored_request = read_json(request_path)
                    if isinstance(stored_request, dict):
                        original_payload = stored_request
                except Exception:
                    original_payload = payload
            if current_status in _TERMINAL_DISPATCH_STATUSES:
                result = read_json(result_path) if result_path.is_file() else status
                return {
                    **result,
                    "request_id": message_id,
                    **_dispatch_metadata(
                        original_payload,
                        str(result.get("next_state") or current_status),
                    ),
                    "deduplicated": True,
                }
            if current_status in {"awaiting_agent", "running"}:
                lease = read_json(lease_path) if lease_path.is_file() else {}
                if not _lease_alive(lease):
                    blocked = {
                        "status": "blocked",
                        "request_id": message_id,
                        "message_id": message_id,
                        **_dispatch_metadata(original_payload, "blocked"),
                        "blocker_reason": (
                            "dispatch_lease_expired"
                            if lease_path.is_file()
                            else "dispatch_worker_dead"
                        ),
                    }
                    write_json(status_path, blocked)
                    write_json(result_path, blocked)
                    return {**blocked, "deduplicated": True}
                return {
                    "status": "awaiting_agent",
                    "request_id": message_id,
                    "message_id": message_id,
                    **_dispatch_metadata(original_payload, "awaiting_agent"),
                    "worker_started": False,
                    "deduplicated": True,
                }

        request = {
            **payload,
            "message_id": message_id,
            "command_id": command_id,
            "created_at": utc_now_iso(),
            **_dispatch_metadata(payload, "awaiting_agent"),
        }
        write_json(dispatch_dir / "request.json", request)
        write_json(
            status_path,
            {
                "status": "awaiting_agent",
                "request_id": message_id,
                "message_id": message_id,
                "created_at": request["created_at"],
                **_dispatch_metadata(payload, "awaiting_agent"),
            },
        )
        # Publish the lease before spawning.  The child claims this lease
        # after acquiring the same dispatch lock; this closes the window in
        # which a fast worker could finish before the parent persisted one.
        expires_at = (
            datetime.now(timezone.utc) + timedelta(hours=2)
        ).isoformat()
        write_json(
            lease_path,
            {
                "owner": f"harness-dispatcher-{os.getpid()}",
                "pid": os.getpid(),
                "acquired_at": utc_now_iso(),
                "expires_at": expires_at,
                "state": "starting",
            },
        )
        worker_command = [
            sys.executable,
            str(Path(__file__).with_name("hermes_harness_dispatch_worker.py")),
            "--dispatch-dir",
            str(dispatch_dir),
        ]
        worker_env = {**os.environ, "CAREER_HARNESS_SUBAGENT": "1"}
        try:
            worker = subprocess.Popen(
                worker_command,
                env=worker_env,
                start_new_session=True,
            )
        except Exception as exc:
            blocked = {
                "status": "blocked",
                "request_id": message_id,
                "message_id": message_id,
                **_dispatch_metadata(payload, "blocked"),
                "blocker_reason": "dispatch_worker_start_failed",
                "error": f"{type(exc).__name__}: {exc}"[:500],
            }
            write_json(status_path, blocked)
            write_json(result_path, blocked)
            lease_path.unlink(missing_ok=True)
            return blocked
        try:
            worker_pid = int(worker.pid)
        except (AttributeError, TypeError, ValueError):
            worker_pid = 0
        if worker_pid <= 0:
            blocked = {
                "status": "blocked",
                "request_id": message_id,
                "message_id": message_id,
                **_dispatch_metadata(payload, "blocked"),
                "blocker_reason": "dispatch_worker_invalid_pid",
            }
            write_json(status_path, blocked)
            write_json(result_path, blocked)
            lease_path.unlink(missing_ok=True)
            return blocked
        # The child cannot enter run_worker until this lock is released, so
        # it will observe the real PID rather than the dispatcher PID.
        write_json(
            lease_path,
            {
                "owner": f"harness-worker-{worker_pid}",
                "pid": worker_pid,
                "acquired_at": utc_now_iso(),
                "expires_at": expires_at,
                "state": "starting",
            },
        )
        return {
            "status": "awaiting_agent",
            "request_id": message_id,
            "message_id": message_id,
            **_dispatch_metadata(payload, "awaiting_agent"),
            "worker_pid": worker_pid,
            "worker_started": True,
            "deduplicated": False,
            "command_id": command_id,
        }


def _command_result(command: dict[str, Any]) -> dict[str, Any]:
    raw = command.get("result_json")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {
        "status": command.get("status"),
        "reply_text": command.get("reply_text"),
        "blocker_reason": command.get("blocker_reason"),
    }


def process_message(
    message: str,
    *,
    message_id: str | None = None,
    execute: bool = True,
    runtime_context: dict[str, Any] | None = None,
    supervisor: HarnessSupervisor | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    normalized = " ".join(str(message or "").strip().split())
    if not normalized:
        raise ValueError("Telegram message cannot be empty.")
    stable_id = message_id or hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    cache_path = _message_cache_path(
        root, stable_id=stable_id, runtime_context=runtime_context
    )
    if cache_path.exists():
        cached = read_json(cache_path)
        if not _should_retry_cached_message(cached):
            cached["deduplicated"] = True
            return cached
    supervisor = supervisor or HarnessSupervisor(root)
    result = supervisor.handle_message(
        normalized,
        channel="telegram",
        execute=execute,
        runtime_context=runtime_context,
    )
    envelope = {
        "message_id": stable_id,
        "received_at": utc_now_iso(),
        "message": normalized,
        "deduplicated": False,
        "result": result,
    }
    payload = result.get("result") if isinstance(result.get("result"), dict) else {}
    display_text = payload.get("display_text") if isinstance(payload, dict) else None
    if isinstance(display_text, str) and display_text.strip():
        envelope["reply_text"] = display_text
    else:
        blocked_reply = _nested_blocked_reply(result)
        if blocked_reply:
            envelope["reply_text"] = blocked_reply
    write_json(cache_path, envelope)
    return envelope


def _message_cache_path(
    root: Path, *, stable_id: str, runtime_context: dict[str, Any] | None
) -> Path:
    """Return a cache path that cannot collide across bot profiles/sessions."""
    context = runtime_context if isinstance(runtime_context, dict) else {}
    raw = "\x1f".join((
        str(context.get("runtime") or "hermes").strip() or "hermes",
        str(context.get("profile_id") or "default").strip() or "default",
        str(context.get("session_id") or "").strip(),
        str(stable_id).strip(),
    ))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return root / ".career-state" / "telegram" / "messages" / f"{digest}.json"


def _dispatch_metadata(payload: dict[str, Any], next_state: str) -> dict[str, Any]:
    runtime_context = payload.get("runtime_context")
    runtime_context = runtime_context if isinstance(runtime_context, dict) else {}
    scope = {
        "runtime": runtime_context.get("runtime") or "hermes",
        "profile_id": runtime_context.get("profile_id"),
        "session_id": payload.get("session_id") or runtime_context.get("session_id"),
        "turn_id": payload.get("turn_id") or runtime_context.get("turn_id"),
        "application_id": runtime_context.get("application_id"),
        "run_id": runtime_context.get("run_id"),
        "source": "pre_llm_call",
    }
    return {
        "decision": "block",
        "dispatch_action": "awaiting_agent",
        "next_state": next_state,
        "scope": scope,
    }


def _should_retry_cached_message(cached: dict[str, Any]) -> bool:
    result = cached.get("result") if isinstance(cached.get("result"), dict) else {}
    if not isinstance(result, dict):
        return False
    if result.get("status") != "blocked":
        return False
    return str(result.get("blocker_reason") or "") in {
        "no_deterministic_route",
        "generic_runner_unavailable",
        "generic_runner_failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message")
    parser.add_argument("--message-id")
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--route-only", action="store_true")
    args = parser.parse_args()
    if args.stdin:
        message = sys.stdin.read()
    else:
        message = args.message
    if not message:
        raise SystemExit("Use --message or --stdin.")
    result = process_message(
        message,
        message_id=args.message_id,
        execute=not args.route_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
