#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys

from _bootstrap import bootstrap

bootstrap()

from telegram_harness_adapter import process_message


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
    session_id = str(payload.get("session_id") or "telegram")
    message_id = hashlib.sha256(f"{session_id}\n{message}".encode("utf-8")).hexdigest()[:24]
    result = process_message(message, message_id=message_id, execute=True)
    compact = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    context = (
        "O HarnessSupervisor ja processou esta mensagem. "
        "Nao use ferramentas e nao repita o workflow. "
        "Responda ao usuario apenas com um resumo claro deste resultado JSON:\n"
        + compact
    )
    print(json.dumps({"context": context}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
