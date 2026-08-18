CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    notion_id TEXT,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    source_type TEXT DEFAULT 'paste',
    source_url TEXT,
    stage TEXT DEFAULT 'analyze_pending',
    funil_stage TEXT DEFAULT 'Fila Agente',
    score REAL,
    cv_language TEXT DEFAULT 'pt',
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    job_description_path TEXT,
    fit_map_path TEXT,
    cv_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_applications_funil_status
    ON applications(funil_stage, status);
CREATE INDEX IF NOT EXISTS idx_applications_notion_id
    ON applications(notion_id);
CREATE INDEX IF NOT EXISTS idx_applications_company_role
    ON applications(company, role);
CREATE INDEX IF NOT EXISTS idx_applications_stage_status
    ON applications(stage, status);

CREATE TABLE IF NOT EXISTS application_aliases (
    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    alias_type TEXT NOT NULL,
    alias_value TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE(alias_type, alias_value)
);

CREATE INDEX IF NOT EXISTS idx_application_aliases_application
    ON application_aliases(application_id, alias_type);

CREATE TABLE IF NOT EXISTS application_revisions (
    revision_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    revision_kind TEXT NOT NULL DEFAULT 'intake',
    fingerprint TEXT,
    source_hash TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(application_id, revision_kind, source_hash)
);

CREATE INDEX IF NOT EXISTS idx_application_revisions_application_created
    ON application_revisions(application_id, created_at);
CREATE INDEX IF NOT EXISTS idx_application_revisions_fingerprint
    ON application_revisions(fingerprint);

CREATE TABLE IF NOT EXISTS job_sources (
    source_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_url TEXT,
    fingerprint TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_sources_application
    ON job_sources(application_id, created_at);

CREATE TABLE IF NOT EXISTS job_descriptions (
    description_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    source_id TEXT REFERENCES job_sources(source_id) ON DELETE SET NULL,
    language TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_descriptions_application
    ON job_descriptions(application_id, created_at);

CREATE TABLE IF NOT EXISTS job_sections (
    section_id TEXT PRIMARY KEY,
    description_id TEXT NOT NULL REFERENCES job_descriptions(description_id) ON DELETE CASCADE,
    section_key TEXT NOT NULL,
    heading TEXT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(description_id, section_key)
);

CREATE TABLE IF NOT EXISTS workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES applications(id),
    event TEXT NOT NULL,
    fingerprint TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_events_app_event
    ON workflow_events(application_id, event);

CREATE TABLE IF NOT EXISTS notion_cache (
    id TEXT PRIMARY KEY,
    raw_json TEXT,
    company TEXT,
    role TEXT,
    funil_stage TEXT,
    canal_aplicacao TEXT,
    tipo_empresa TEXT,
    status TEXT,
    url TEXT,
    last_synced TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notion_cache_funil_stage
    ON notion_cache(funil_stage);
CREATE INDEX IF NOT EXISTS idx_notion_cache_company
    ON notion_cache(company);
CREATE INDEX IF NOT EXISTS idx_notion_cache_tipo_empresa
    ON notion_cache(tipo_empresa);
CREATE INDEX IF NOT EXISTS idx_notion_cache_canal_aplicacao
    ON notion_cache(canal_aplicacao);

CREATE TABLE IF NOT EXISTS keyword_registry (
    keyword TEXT NOT NULL,
    application_id TEXT NOT NULL,
    coverage TEXT NOT NULL DEFAULT 'missing',
    evidence TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (keyword, application_id)
);

CREATE INDEX IF NOT EXISTS idx_keyword_registry_application
    ON keyword_registry(application_id);

CREATE TABLE IF NOT EXISTS session_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    created_at TEXT NOT NULL,
    ttl_seconds INTEGER DEFAULT 3600
);

CREATE INDEX IF NOT EXISTS idx_session_memory_session_key
    ON session_memory(session_id, key);

CREATE TABLE IF NOT EXISTS application_runs (
    run_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL,
    graph_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    contract_version TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_application_runs_application_created
    ON application_runs(application_id, created_at);

CREATE TABLE IF NOT EXISTS cell_nodes (
    run_id TEXT NOT NULL REFERENCES application_runs(run_id),
    node_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    requires_json TEXT NOT NULL DEFAULT '[]',
    reserved_by TEXT,
    reservation_expires_at TEXT,
    latest_attempt INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (run_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_cell_nodes_run_status
    ON cell_nodes(run_id, status);

CREATE TABLE IF NOT EXISTS cell_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    worker_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    detail_json TEXT,
    UNIQUE (run_id, node_id, attempt),
    FOREIGN KEY (run_id, node_id) REFERENCES cell_nodes(run_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_cell_attempts_run_node
    ON cell_attempts(run_id, node_id);

CREATE TABLE IF NOT EXISTS cell_requests (
    request_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    contract_version TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    payload_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (run_id, node_id, attempt),
    FOREIGN KEY (run_id, node_id) REFERENCES cell_nodes(run_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_cell_requests_run_node
    ON cell_requests(run_id, node_id);

CREATE TABLE IF NOT EXISTS cell_inputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    input_name TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_node_id TEXT,
    source_attempt INTEGER,
    source_id TEXT,
    version TEXT,
    path TEXT,
    content_hash TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 1 CHECK (required IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE (run_id, node_id, attempt, input_name),
    FOREIGN KEY (run_id, node_id) REFERENCES cell_nodes(run_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_cell_inputs_run_node
    ON cell_inputs(run_id, node_id);

CREATE TABLE IF NOT EXISTS cell_handovers (
    handover_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    path TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (run_id, node_id, attempt),
    FOREIGN KEY (run_id, node_id) REFERENCES cell_nodes(run_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_cell_handovers_run_node
    ON cell_handovers(run_id, node_id);

CREATE TABLE IF NOT EXISTS canonical_journal_snapshots (
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    application_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    journal_path TEXT NOT NULL,
    journal_sha256 TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, node_id, attempt),
    FOREIGN KEY (run_id, node_id) REFERENCES cell_nodes(run_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_canonical_journal_application
    ON canonical_journal_snapshots(application_id, run_id);

CREATE TABLE IF NOT EXISTS validation_receipts (
    receipt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    validator TEXT NOT NULL,
    result TEXT NOT NULL,
    report_path TEXT,
    report_sha256 TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (run_id, node_id, attempt, validator),
    FOREIGN KEY (run_id, node_id) REFERENCES cell_nodes(run_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_validation_receipts_run_node
    ON validation_receipts(run_id, node_id, validator);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES application_runs(run_id),
    node_id TEXT NOT NULL,
    artifact_name TEXT NOT NULL,
    path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    input_hash TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_run_node
    ON artifacts(run_id, node_id);

CREATE TABLE IF NOT EXISTS artifact_dependencies (
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    input_hash TEXT NOT NULL,
    input_path TEXT,
    source_kind TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (artifact_id, input_hash)
);

CREATE INDEX IF NOT EXISTS idx_artifact_dependencies_artifact_input
    ON artifact_dependencies(artifact_id, input_hash);

CREATE TABLE IF NOT EXISTS resource_locks (
    resource_name TEXT PRIMARY KEY,
    worker_id TEXT NOT NULL,
    lease_id TEXT,
    acquired_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_resource_locks_resource_expires
    ON resource_locks(resource_name, expires_at);

CREATE TABLE IF NOT EXISTS workspace_leases (
    lease_name TEXT PRIMARY KEY,
    worker_id TEXT NOT NULL,
    run_id TEXT REFERENCES application_runs(run_id),
    lease_epoch INTEGER NOT NULL DEFAULT 1,
    acquired_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workspace_leases_expires
    ON workspace_leases(expires_at);

CREATE TABLE IF NOT EXISTS workspace_lease_takeovers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_name TEXT NOT NULL,
    prior_owner TEXT NOT NULL,
    prior_expires_at TEXT NOT NULL,
    new_owner TEXT NOT NULL,
    taken_over_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workspace_lease_takeovers_name_time
    ON workspace_lease_takeovers(lease_name, taken_over_at);

CREATE TABLE IF NOT EXISTS workspace_authority (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    control_db_id TEXT NOT NULL UNIQUE,
    storage_identity TEXT,
    authority_ledger_id TEXT,
    authority_epoch INTEGER NOT NULL DEFAULT 1,
    lease_epoch_counter INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_authority_handoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    control_db_id TEXT NOT NULL,
    prior_storage_identity TEXT NOT NULL,
    new_storage_identity TEXT NOT NULL,
    new_owner TEXT NOT NULL,
    prior_authority_epoch INTEGER NOT NULL DEFAULT 1,
    new_authority_epoch INTEGER NOT NULL DEFAULT 1,
    authorized_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_workers (
    worker_id TEXT PRIMARY KEY,
    runtime TEXT NOT NULL,
    profile_id TEXT,
    host TEXT,
    pid INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS runtime_runs (
    runtime_run_id TEXT PRIMARY KEY,
    worker_id TEXT NOT NULL REFERENCES runtime_workers(worker_id),
    run_id TEXT,
    application_id TEXT,
    node_id TEXT,
    session_id TEXT,
    source TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    request_bytes INTEGER,
    request_tokens INTEGER,
    output_bytes INTEGER,
    error TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_runtime_runs_worker_started
    ON runtime_runs(worker_id, started_at);

CREATE TABLE IF NOT EXISTS runtime_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    runtime_run_id TEXT NOT NULL REFERENCES runtime_runs(runtime_run_id),
    observed_at TEXT NOT NULL,
    context_tokens INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    tool_calls INTEGER,
    history_messages INTEGER,
    request_bytes INTEGER,
    source TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_runtime_observations_run_observed
    ON runtime_observations(runtime_run_id, observed_at);

CREATE TABLE IF NOT EXISTS profile_application_bindings (
    profile_id TEXT PRIMARY KEY,
    application_id TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    claimed_at TEXT NOT NULL,
    released_at TEXT
);
