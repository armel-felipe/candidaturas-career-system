-- Durable conversation command queue.  A Telegram/Hermes turn is represented
-- exactly once here; filesystem envelopes are diagnostics only and may not
-- select an application or determine completion.
CREATE TABLE IF NOT EXISTS harness_commands (
    command_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    runtime TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    turn_id TEXT,
    message_id TEXT,
    message TEXT NOT NULL,
    application_id TEXT,
    run_id TEXT,
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'running', 'awaiting_input', 'awaiting_approval',
        'ready', 'completed', 'blocked'
    )),
    requested_steps_json TEXT NOT NULL DEFAULT '[]',
    result_json TEXT,
    reply_text TEXT,
    blocker_reason TEXT,
    claimed_by TEXT,
    claim_expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_harness_commands_claimable
    ON harness_commands(status, claim_expires_at, created_at);

CREATE INDEX IF NOT EXISTS idx_harness_commands_session
    ON harness_commands(runtime, profile_id, session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_harness_commands_application
    ON harness_commands(application_id, created_at);
