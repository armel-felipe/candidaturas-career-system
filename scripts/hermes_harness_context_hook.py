#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.services.harness_supervisor import HarnessSupervisor
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
        return "O HarnessSupervisor ja processou esta mensagem. Responda somente: OK"
    compact = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    return (
        "O HarnessSupervisor ja processou e executou esta mensagem. "
        "Nao use ferramentas e nao repita o workflow. "
        "Responda ao usuario apenas com um resumo claro deste resultado JSON:\n"
        + compact
    )


def should_intercept(message: str) -> bool:
    supervisor = HarnessSupervisor(ROOT)
    decision = supervisor.classify(message)
    pending_path = ROOT / ".career-state" / "harness" / "pending_input.json"
    return decision.workflow != "generic_assistant" or pending_path.exists()


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
    result = process_message(message, message_id=message_id, execute=True)
    reply_text = result.get("reply_text")
    if isinstance(reply_text, str) and reply_text.strip():
        write_transform_reply(session_id, turn_id, reply_text.strip())
    context = build_context(result)
    print(json.dumps({"context": context}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
