CREATE TABLE IF NOT EXISTS migration_runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    input_root TEXT NOT NULL,
    report_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS migration_sources (
    source_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES migration_runs(run_id) ON DELETE CASCADE,
    application_id TEXT,
    bot_id TEXT,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(run_id, path, source_hash)
);

CREATE INDEX IF NOT EXISTS idx_migration_sources_application
    ON migration_sources(application_id, kind, created_at);

CREATE TABLE IF NOT EXISTS migration_conflicts (
    conflict_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES migration_runs(run_id) ON DELETE CASCADE,
    application_id TEXT,
    path TEXT,
    reason TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'blocked',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_migration_conflicts_run_status
    ON migration_conflicts(run_id, status);

CREATE TABLE IF NOT EXISTS legacy_records (
    record_id TEXT PRIMARY KEY,
    migration_run_id TEXT NOT NULL REFERENCES migration_runs(run_id) ON DELETE CASCADE,
    application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
    bot_id TEXT,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    imported_at TEXT NOT NULL,
    UNIQUE(application_id, kind, path, source_hash)
);

CREATE INDEX IF NOT EXISTS idx_legacy_records_application_kind
    ON legacy_records(application_id, kind, imported_at);

CREATE TABLE IF NOT EXISTS application_locations (
    location_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    bot_id TEXT NOT NULL,
    location_path TEXT NOT NULL,
    manifest_hash TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(application_id, bot_id, location_path)
);

CREATE INDEX IF NOT EXISTS idx_application_locations_bot
    ON application_locations(bot_id, application_id);
