-- LISA-RC004 / RC003 Wave 1 additive reliability schema.
-- OpenClaw-owned sqlite only. No destructive DDL; existing rows are untouched.

ALTER TABLE task_runs ADD COLUMN dispatch_state TEXT;
ALTER TABLE task_runs ADD COLUMN execution_state TEXT;
ALTER TABLE task_runs ADD COLUMN session_state TEXT;
ALTER TABLE task_runs ADD COLUMN result_state TEXT;
ALTER TABLE task_runs ADD COLUMN requires_reconciliation INTEGER;
ALTER TABLE task_runs ADD COLUMN terminal_evidence TEXT;
ALTER TABLE task_runs ADD COLUMN command_state TEXT;

CREATE INDEX IF NOT EXISTS idx_task_runs_reconcile
  ON task_runs(requires_reconciliation, execution_state);

CREATE TABLE IF NOT EXISTS session_lifecycle (
  session_key TEXT PRIMARY KEY,
  agent_id TEXT,
  project TEXT,
  sprint TEXT,
  employee TEXT,
  role TEXT,
  task_family TEXT,
  session_state TEXT,
  cache_read INTEGER,
  context_window INTEGER,
  context_pct REAL,
  last_seen_at INTEGER,
  throttle_until TEXT,
  reset_time TEXT,
  compact_count INTEGER DEFAULT 0,
  opened_at INTEGER,
  retired_at INTEGER
);
