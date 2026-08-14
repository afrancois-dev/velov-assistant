-- Monitoring tables for Grafana (created idempotently; the app also creates
-- these via SQLAlchemy on startup).

CREATE TABLE IF NOT EXISTS requests (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL DEFAULT NOW(),
    conversation_id TEXT,
    intent TEXT,
    retrieval_mode TEXT,
    latency_retrieval_ms DOUBLE PRECISION DEFAULT 0,
    latency_llm_ms DOUBLE PRECISION DEFAULT 0,
    latency_total_ms DOUBLE PRECISION DEFAULT 0,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL DEFAULT NOW(),
    conversation_id TEXT,
    rating INTEGER,
    comment TEXT
);

CREATE INDEX IF NOT EXISTS idx_requests_ts ON requests (ts);
CREATE INDEX IF NOT EXISTS idx_feedback_ts ON feedback (ts);
