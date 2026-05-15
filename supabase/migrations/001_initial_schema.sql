-- KANIT Initial Schema for Supabase
-- Run this in the Supabase SQL Editor or via supabase db push

-- ─── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;  -- for RAG embeddings

-- ─── Organizations (multi-tenant) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    api_key_hash TEXT,
    plan        TEXT NOT NULL DEFAULT 'trial',
    trial_reviews_used INT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Cases ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cases (
    case_id         TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    status          TEXT NOT NULL,
    score           INTEGER NOT NULL,
    payload_json    TEXT NOT NULL,
    report_markdown TEXT NOT NULL DEFAULT '',
    org_id          UUID REFERENCES organizations(id)
);
CREATE INDEX IF NOT EXISTS idx_cases_org_id ON cases(org_id);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at DESC);

-- ─── Incidents ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS incidents (
    incident_id     TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    incident_type   TEXT NOT NULL,
    employee_code   TEXT,
    role_code       TEXT,
    team_code       TEXT,
    station_code    TEXT,
    source_case_id  TEXT NOT NULL,
    evidence_score  INTEGER NOT NULL,
    payload_json    TEXT NOT NULL,
    org_id          UUID REFERENCES organizations(id)
);
CREATE INDEX IF NOT EXISTS idx_incidents_org_id ON incidents(org_id);
CREATE INDEX IF NOT EXISTS idx_incidents_team_code ON incidents(team_code);
CREATE INDEX IF NOT EXISTS idx_incidents_employee_code ON incidents(employee_code);

-- ─── Learning Tasks ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS learning_tasks (
    task_id         TEXT PRIMARY KEY,
    incident_id     TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    employee_code   TEXT,
    role_code       TEXT,
    team_code       TEXT,
    station_code    TEXT,
    skill_id        TEXT NOT NULL,
    status          TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    org_id          UUID REFERENCES organizations(id)
);
CREATE INDEX IF NOT EXISTS idx_learning_tasks_org_id ON learning_tasks(org_id);
CREATE INDEX IF NOT EXISTS idx_learning_tasks_employee ON learning_tasks(employee_code);

-- ─── Mentor Reviews ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mentor_reviews (
    review_id       TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    employee_code   TEXT NOT NULL,
    skill_id        TEXT NOT NULL,
    reviewer_code   TEXT NOT NULL,
    decision        TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    org_id          UUID REFERENCES organizations(id)
);
CREATE INDEX IF NOT EXISTS idx_mentor_reviews_employee ON mentor_reviews(employee_code);
CREATE INDEX IF NOT EXISTS idx_mentor_reviews_org_id ON mentor_reviews(org_id);

-- ─── Evidence Graphs ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evidence_graphs (
    incident_id     TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    org_id          UUID REFERENCES organizations(id)
);

-- ─── Inductive Patterns ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inductive_patterns (
    pattern_id      TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    scope_type      TEXT NOT NULL,
    scope_code      TEXT NOT NULL,
    skill_id        TEXT NOT NULL,
    confidence      REAL NOT NULL,
    status          TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    org_id          UUID REFERENCES organizations(id)
);
CREATE INDEX IF NOT EXISTS idx_patterns_scope ON inductive_patterns(scope_type, scope_code);

-- ─── Training Deltas ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS training_deltas (
    delta_id        TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    skill_id        TEXT NOT NULL,
    pattern_id      TEXT,
    payload_json    TEXT NOT NULL,
    org_id          UUID REFERENCES organizations(id)
);

-- ─── Shift Readiness ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shift_readiness (
    readiness_id    TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    team_code       TEXT NOT NULL,
    station_code    TEXT,
    shift_code      TEXT NOT NULL,
    risk_level      TEXT NOT NULL,
    readiness_score INTEGER NOT NULL,
    payload_json    TEXT NOT NULL,
    org_id          UUID REFERENCES organizations(id)
);
CREATE INDEX IF NOT EXISTS idx_readiness_team ON shift_readiness(team_code);

-- ─── COPQ Estimates ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS copq_estimates (
    impact_id               TEXT PRIMARY KEY,
    created_at              TEXT NOT NULL,
    scope_type              TEXT NOT NULL,
    scope_code              TEXT NOT NULL,
    estimated_exposure_tl   INTEGER NOT NULL,
    payload_json            TEXT NOT NULL,
    org_id                  UUID REFERENCES organizations(id)
);

-- ─── RAG: Policy Chunks ──────────────────────────────────────────────────────
-- Used for Ford CSR, AIAG manuals, company SOPs
CREATE TABLE IF NOT EXISTS policy_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID REFERENCES organizations(id),  -- NULL = global (Ford CSR etc.)
    source      TEXT NOT NULL,       -- 'ford_csr_june_2025', 'aiag_8d', 'company_sop'
    section     TEXT,                -- e.g. '§6.2 Containment Requirements'
    content     TEXT NOT NULL,
    embedding   vector(1024),        -- nvidia/nv-embedqa-e5-v5 dimension
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_policy_chunks_source ON policy_chunks(source);
-- ivfflat index for fast similarity search (run after bulk insert)
-- CREATE INDEX ON policy_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ─── Row-Level Security ──────────────────────────────────────────────────────
-- Enable RLS on all tenant tables (enforced at DB level)
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE mentor_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_graphs ENABLE ROW LEVEL SECURITY;
ALTER TABLE inductive_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_deltas ENABLE ROW LEVEL SECURITY;
ALTER TABLE shift_readiness ENABLE ROW LEVEL SECURITY;
ALTER TABLE copq_estimates ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS (backend uses service role key)
-- User-facing queries (when Supabase Auth is wired up) will use JWT org_id claim
-- For now: service role key = full access, no RLS restriction

-- Bypass policy for service role (used by backend)
CREATE POLICY "service_role_bypass" ON cases USING (true);
CREATE POLICY "service_role_bypass" ON incidents USING (true);
CREATE POLICY "service_role_bypass" ON learning_tasks USING (true);
CREATE POLICY "service_role_bypass" ON mentor_reviews USING (true);
CREATE POLICY "service_role_bypass" ON evidence_graphs USING (true);
CREATE POLICY "service_role_bypass" ON inductive_patterns USING (true);
CREATE POLICY "service_role_bypass" ON training_deltas USING (true);
CREATE POLICY "service_role_bypass" ON shift_readiness USING (true);
CREATE POLICY "service_role_bypass" ON copq_estimates USING (true);
