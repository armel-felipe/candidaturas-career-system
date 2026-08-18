CREATE TABLE IF NOT EXISTS gate_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id TEXT NOT NULL REFERENCES validation_receipts(receipt_id) ON DELETE CASCADE,
    dependency_type TEXT NOT NULL,
    dependency_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(receipt_id, dependency_type, dependency_id)
);

CREATE INDEX IF NOT EXISTS idx_gate_dependencies_receipt
    ON gate_dependencies(receipt_id);

CREATE TABLE IF NOT EXISTS artifact_versions (
    version_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    artifact_id TEXT REFERENCES artifacts(artifact_id) ON DELETE SET NULL,
    run_id TEXT REFERENCES application_runs(run_id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    source_revision_id TEXT,
    positioning_revision_id TEXT,
    path TEXT,
    content_hash TEXT NOT NULL,
    mime_type TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifact_versions_application_kind
    ON artifact_versions(application_id, kind, created_at);

CREATE TABLE IF NOT EXISTS artifact_contents (
    version_id TEXT PRIMARY KEY REFERENCES artifact_versions(version_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notion_records (
    record_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL UNIQUE REFERENCES applications(id) ON DELETE CASCADE,
    notion_page_id TEXT,
    notion_database_id TEXT,
    notion_unique_id TEXT,
    notion_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notion_records_unique_id
    ON notion_records(notion_unique_id)
    WHERE notion_unique_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS notion_syncs (
    sync_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    record_id TEXT REFERENCES notion_records(record_id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    synced_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notion_syncs_application_time
    ON notion_syncs(application_id, synced_at);

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    artifact_version_id TEXT REFERENCES artifact_versions(version_id) ON DELETE SET NULL,
    channel TEXT NOT NULL,
    target TEXT,
    status TEXT NOT NULL,
    report_path TEXT,
    report_hash TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    delivered_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deliveries_application_channel
    ON deliveries(application_id, channel, delivered_at);
