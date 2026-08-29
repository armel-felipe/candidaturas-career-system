#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.services.harness_supervisor import HarnessSupervisor
from career.services import application_context as application_context_service
from career.utils import read_json
from telegram_harness_adapter import process_message


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
    supervisor = HarnessSupervisor(ROOT)
    decision = supervisor.classify(message)
    return decision.workflow != "generic_assistant" or decision.reason == "meta_question_about_previous_output"


def main() -> int:
    if os.environ.get("CAREER_HARNESS_SUBAGENT") == "1":
        print("{}")
        return 0
    payload = json.load(sys.stdin)
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    message = str(extra.get("user_message") or "").strip()
    if not message:
        print("{}")
        return 0
    if not should_intercept(message):
        print("{}")
        return 0
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
    try:
        result = process_message(
            message,
            message_id=message_id,
            execute=True,
            runtime_context={
                "runtime": "hermes",
                "profile_id": application_context_service.profile_id_from_env(),
                "session_id": session_id,
                "turn_id": turn_id,
            },
        )
    except Exception as exc:  # pragma: no cover - exercised by live hook failures
        # A pre-LLM hook failure must remain inside the HarnessSupervisor
        # contract. Exit code 1 lets Hermes continue with an unconstrained
        # model turn, which is precisely how manual FIT_MAP/provenance
        # workarounds escaped the supervisor.
        result = {
            "status": "blocked",
            "kind": "harness_hook_failure",
            "blocker_reason": "harness_execution_failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }
    reply_text = result.get("reply_text")
    if isinstance(reply_text, str) and reply_text.strip():
        write_transform_reply(session_id, turn_id, reply_text.strip())
    context = build_context(result)
    print(json.dumps({"context": context}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
