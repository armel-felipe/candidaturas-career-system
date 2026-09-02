from career.services.database import Database
from career.services.harness_command_store import HarnessCommandStore


def _payload(*, profile="vagas_bot_01", session="chat-1", message_id="m-1", application_id="app-1"):
    return {
        "message_id": message_id,
        "message": "atualize o Notion e depois gere o CV",
        "session_id": session,
        "runtime_context": {
            "runtime": "hermes", "profile_id": profile, "session_id": session,
            "application_id": application_id,
        },
    }


def test_enqueue_is_idempotent_and_preserves_original_scope(tmp_path):
    store = HarnessCommandStore(Database(tmp_path / "career.db"))
    first = store.enqueue(_payload())
    duplicate = store.enqueue(_payload(application_id="wrong-app"))

    assert first["command_id"] == duplicate["command_id"]
    assert duplicate["deduplicated"] is True
    assert duplicate["application_id"] == "app-1"


def test_same_telegram_chat_isolated_by_profile(tmp_path):
    store = HarnessCommandStore(Database(tmp_path / "career.db"))
    bot_01 = store.enqueue(_payload(profile="vagas_bot_01"))
    bot_02 = store.enqueue(_payload(profile="vagas_bot_02"))

    assert bot_01["command_id"] != bot_02["command_id"]
    assert bot_01["profile_id"] == "vagas_bot_01"
    assert bot_02["profile_id"] == "vagas_bot_02"


def test_claim_is_exclusive_and_final_result_is_durable(tmp_path):
    store = HarnessCommandStore(Database(tmp_path / "career.db"))
    command = store.enqueue(_payload())

    assert store.claim(command["command_id"], worker_id="worker-a") is not None
    assert store.claim(command["command_id"], worker_id="worker-b") is None
    finished = store.finish(
        command["command_id"], status="awaiting_approval",
        result={"status": "awaiting_approval"}, reply_text="Confirme a escrita no Notion.",
    )

    assert finished["status"] == "awaiting_approval"
    assert finished["reply_text"] == "Confirme a escrita no Notion."
