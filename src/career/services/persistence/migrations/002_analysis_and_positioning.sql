CREATE TABLE IF NOT EXISTS fit_map_revisions (
    revision_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    application_revision_id TEXT REFERENCES application_revisions(revision_id) ON DELETE SET NULL,
    fingerprint TEXT,
    source_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    score_final REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fit_map_revisions_application_created
    ON fit_map_revisions(application_id, created_at);

CREATE TABLE IF NOT EXISTS fit_map_dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id TEXT NOT NULL REFERENCES fit_map_revisions(revision_id) ON DELETE CASCADE,
    dimension_key TEXT NOT NULL,
    score REAL,
    evidence_summary TEXT,
    gap_summary TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(revision_id, dimension_key)
);

CREATE TABLE IF NOT EXISTS fit_map_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id TEXT NOT NULL REFERENCES fit_map_revisions(revision_id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    coverage TEXT NOT NULL,
    importance REAL,
    evidence TEXT,
    UNIQUE(revision_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_fit_map_keywords_revision_coverage
    ON fit_map_keywords(revision_id, coverage);

CREATE TABLE IF NOT EXISTS fit_map_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id TEXT NOT NULL REFERENCES fit_map_revisions(revision_id) ON DELETE CASCADE,
    evidence_key TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(revision_id, evidence_key)
);

CREATE TABLE IF NOT EXISTS fit_map_objections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id TEXT NOT NULL REFERENCES fit_map_revisions(revision_id) ON DELETE CASCADE,
    objection_key TEXT NOT NULL,
    objection_text TEXT NOT NULL,
    response_text TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(revision_id, objection_key)
);

CREATE TABLE IF NOT EXISTS fit_map_stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id TEXT NOT NULL REFERENCES fit_map_revisions(revision_id) ON DELETE CASCADE,
    story_key TEXT NOT NULL,
    title TEXT,
    narrative TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(revision_id, story_key)
);

CREATE TABLE IF NOT EXISTS fit_map_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id TEXT NOT NULL REFERENCES fit_map_revisions(revision_id) ON DELETE CASCADE,
    score_key TEXT NOT NULL,
    score REAL NOT NULL,
    rationale TEXT,
    UNIQUE(revision_id, score_key)
);

CREATE TABLE IF NOT EXISTS positioning_revisions (
    revision_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    fit_map_revision_id TEXT REFERENCES fit_map_revisions(revision_id) ON DELETE SET NULL,
    source_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_positioning_revisions_application_created
    ON positioning_revisions(application_id, created_at);

CREATE TABLE IF NOT EXISTS positioning_stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id TEXT NOT NULL REFERENCES positioning_revisions(revision_id) ON DELETE CASCADE,
    story_key TEXT NOT NULL,
    title TEXT,
    narrative TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(revision_id, story_key)
);

CREATE TABLE IF NOT EXISTS positioning_principles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id TEXT NOT NULL REFERENCES positioning_revisions(revision_id) ON DELETE CASCADE,
    principle_key TEXT NOT NULL,
    content TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(revision_id, principle_key)
);

CREATE TABLE IF NOT EXISTS reference_documents (
    reference_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    reference_key TEXT NOT NULL,
    content TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(kind, reference_key)
);

CREATE TABLE IF NOT EXISTS candidate_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT REFERENCES reference_documents(reference_id) ON DELETE CASCADE,
    fact_key TEXT NOT NULL,
    fact_value TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candidate_facts_reference
    ON candidate_facts(reference_id, fact_key);

CREATE TABLE IF NOT EXISTS candidate_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT REFERENCES reference_documents(reference_id) ON DELETE CASCADE,
    evidence_key TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candidate_evidence_reference
    ON candidate_evidence(reference_id, evidence_key);

CREATE TABLE IF NOT EXISTS keyword_translations (
    keyword TEXT NOT NULL,
    locale TEXT NOT NULL,
    translation TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(keyword, locale)
);
