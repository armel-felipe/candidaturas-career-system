#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.services import application_context as application_context_service
from career.utils import read_json
from telegram_harness_adapter import _dispatch_metadata, dispatch_harness_job


def reply_state_path(session_id: str) -> str:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24]
    hermes_home = os.environ.get("HERMES_HOME") or str(os.path.expanduser("~/.hermes"))
    return os.path.join(hermes_home, "state", "career-harness-replies", f"{digest}.json")


def clear_transform_reply(session_id: str) -> None:
    try:
        os.unlink(reply_state_path(session_id))
    except FileNotFoundError:
        pass


def write_transform_reply(session_id: str, turn_id: str, reply_text: str) -> None:
    path = reply_state_path(session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(
            {"session_id": session_id, "turn_id": turn_id, "reply_text": reply_text},
            handle,
            ensure_ascii=False,
        )
    os.replace(temporary, path)


def build_context(result: dict) -> str:
    reply_text = result.get("reply_text")
    if isinstance(reply_text, str) and reply_text.strip():
        return (
            "O HarnessSupervisor ja processou esta mensagem. "
            "Se nenhum plugin substituir sua saida, responda exatamente com o texto abaixo, "
            "sem prefixos, sem sufixos e sem reformular:\n"
            f"<<CAREER_HARNESS_REPLY>>\n{reply_text.strip()}\n<</CAREER_HARNESS_REPLY>>"
        )
    compact = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    return (
        "O HarnessSupervisor ja processou e executou esta mensagem. "
        "Nao use ferramentas e nao repita o workflow. "
        "Responda ao usuario apenas com um resumo claro deste resultado JSON:\n"
        + compact
    )


def build_block_message(result: dict) -> str:
    request_id = str(result.get("request_id") or result.get("message_id") or "unknown")
    status = str(result.get("status") or "blocked")
    reason = str(result.get("blocker_reason") or "supervisor_dispatch")
    return (
        "HarnessSupervisor bloqueou o turno para impedir execução fora do fluxo "
        f"canônico (status={status}, reason={reason}, request_id={request_id})."
    )


def should_intercept(message: str) -> bool:
    pending_path = ROOT / ".career-state" / "harness" / "pending_input.json"
    menu_state_path = ROOT / ".career-state" / "harness" / "menu_state.json"
    text = " ".join(str(message or "").strip().split())
    if pending_path.exists():
        try:
            pending = read_json(pending_path)
        except Exception:
            pending = {}
        # Legacy pending inputs without a session binding are stale state, not
        # permission to intercept every future Telegram message.
        if isinstance(pending, dict) and pending.get("session_id"):
            expires_at = str(pending.get("expires_at") or "").strip()
            if expires_at:
                try:
                    if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) <= datetime.now(timezone.utc):
                        pending_path.unlink(missing_ok=True)
                    else:
                        return True
                except ValueError:
                    pending_path.unlink(missing_ok=True)
    if menu_state_path.exists() and text.isdigit() and 1 <= len(text) <= 2:
        return True
    # Compatibility predicate for older diagnostics.  The live hook does not
    # call this helper: all classification belongs to the asynchronous worker.
    lowered = text.casefold()
    return any(
        marker in lowered
        for marker in (
            "vaga", "currículo", "curriculo", "candidatura", "notion",
            "linkedin", "cv", "carta", "pitch", "status", "olá", "ola",
        )
    )


def _hook_failure_result(exc: Exception, payload: dict) -> dict:
    message_id = str(payload.get("message_id") or "unknown")
    return {
        "status": "blocked",
        "kind": "harness_hook_failure",
        "request_id": message_id,
        "message_id": message_id,
        **_dispatch_metadata(payload, "blocked"),
        "blocker_reason": "harness_execution_failed",
        "error_type": type(exc).__name__,
        "error": str(exc)[:500],
    }


def _emit_block(result: dict) -> None:
    context = build_context(result)
    print(
        json.dumps(
            {
                "action": "block",
                "decision": "block",
                "message": build_block_message(result),
                "context": context,
                "harness_result": result,
            },
            ensure_ascii=False,
            default=str,
        )
    )


def main() -> int:
    if os.environ.get("CAREER_HARNESS_SUBAGENT") == "1":
        result = _hook_failure_result(
            RuntimeError("harness subagent hook invocation is forbidden"),
            {
                "message_id": "subagent",
                "session_id": "subagent",
                "turn_id": "",
                "runtime_context": {
                    "runtime": "hermes",
                    "profile_id": None,
                    "session_id": "subagent",
                    "turn_id": "",
                    "application_id": None,
                    "run_id": None,
                },
            },
        )
        _emit_block(result)
        return 0
    dispatch_payload = {
        "message_id": "unknown",
        "message": "",
        "session_id": "telegram",
        "turn_id": "",
        "runtime_context": {
            "runtime": "hermes",
            "profile_id": None,
            "session_id": "telegram",
            "turn_id": "",
            "application_id": None,
            "run_id": None,
        },
    }
    try:
        payload = json.load(sys.stdin)
        extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
        message = str(extra.get("user_message") or "").strip()
        if not message:
            raise ValueError("pre-LLM hook received an empty user message")
        # Every inbound Telegram turn is dispatched to the supervisor.  The
        # classification belongs in the worker so the pre-LLM hook remains a
        # bounded transport gate and never performs supervisor work inline.
        session_id = str(payload.get("session_id") or "telegram")
        clear_transform_reply(session_id)
        turn_id = str(extra.get("turn_id") or "").strip()
        if turn_id:
            identity = f"{session_id}\n{turn_id}"
        else:
            history = extra.get("conversation_history")
            history_size = len(history) if isinstance(history, list) else 0
            identity = f"{session_id}\n{history_size}\n{message}"
        message_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        dispatch_payload = {
            "message_id": message_id,
            "message": message,
            "session_id": session_id,
            "turn_id": turn_id,
            "runtime_context": {
                "runtime": "hermes",
                "profile_id": application_context_service.profile_id_from_env(),
                "session_id": session_id,
                "turn_id": turn_id,
                "application_id": None,
                "run_id": None,
            },
        }
        result = dispatch_harness_job(dispatch_payload)
        reply_text = result.get("reply_text")
        if isinstance(reply_text, str) and reply_text.strip():
            write_transform_reply(session_id, turn_id, reply_text.strip())
    except Exception as exc:  # pragma: no cover - exercised by live hook failures
        # Any failure in classification, scope resolution, persistence, or
        # serialization remains fail-closed: Hermes must not call the model.
        result = _hook_failure_result(exc, dispatch_payload)
    try:
        _emit_block(result)
    except Exception as exc:  # pragma: no cover - defensive serialization path
        _emit_block(_hook_failure_result(exc, dispatch_payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
