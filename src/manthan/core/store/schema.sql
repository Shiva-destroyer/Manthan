-- Manthan unified results store (PRD §6.3, §8.5).
-- One SQLite schema for all three domains: campaign -> run -> turn -> verdict;
-- run -> finding -> tag; run -> metric. WAL mode, stdlib sqlite3, no server.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS campaign (
    id          TEXT PRIMARY KEY,
    domain      TEXT NOT NULL,              -- prompt | agent | rag | all
    config_hash TEXT NOT NULL,
    seed        INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    label       TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS run (
    id           TEXT PRIMARY KEY,
    campaign_id  TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
    objective_id TEXT NOT NULL,
    target_label TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'completed',  -- completed | skipped | error
    domain       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS turn (
    id        TEXT PRIMARY KEY,
    run_id    TEXT NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    idx       INTEGER NOT NULL,
    role      TEXT NOT NULL,                -- system | user | assistant | tool
    content   TEXT NOT NULL,
    latency_s REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS verdict (
    id         TEXT PRIMARY KEY,
    turn_id    TEXT NOT NULL REFERENCES turn(id) ON DELETE CASCADE,
    judge_name TEXT NOT NULL,
    label      TEXT NOT NULL,               -- refusal | partial | success
    score      REAL NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS finding (
    id             TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    success        INTEGER NOT NULL DEFAULT 0,   -- 0 | 1
    evaded_defense INTEGER NOT NULL DEFAULT 0,   -- 0 | 1
    strategy       TEXT NOT NULL DEFAULT '',
    objective_id   TEXT NOT NULL DEFAULT '',
    score          REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS tag (
    id         TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    owasp_id   TEXT NOT NULL,
    atlas_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metric (
    id      TEXT PRIMARY KEY,
    run_id  TEXT NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    name    TEXT NOT NULL,
    value   REAL NOT NULL,
    ci_low  REAL,
    ci_high REAL,
    method  TEXT DEFAULT '',                -- CI method (FR-C6)
    seed    INTEGER                          -- recorded seed  (FR-C6)
);

CREATE INDEX IF NOT EXISTS ix_run_campaign ON run(campaign_id);
CREATE INDEX IF NOT EXISTS ix_turn_run     ON turn(run_id);
CREATE INDEX IF NOT EXISTS ix_verdict_turn ON verdict(turn_id);
CREATE INDEX IF NOT EXISTS ix_finding_run  ON finding(run_id);
CREATE INDEX IF NOT EXISTS ix_tag_finding  ON tag(finding_id);
CREATE INDEX IF NOT EXISTS ix_metric_run   ON metric(run_id);
