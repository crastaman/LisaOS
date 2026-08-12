-- RC005 Wave 4 additive observability schema. Apply hermetically/reviewed only.
CREATE TABLE IF NOT EXISTS lisa_audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  from_state TEXT,
  to_state TEXT,
  payload TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lisa_audit_events_kind_created
  ON lisa_audit_events(kind, created_at);

CREATE TABLE IF NOT EXISTS lisa_cron_run_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT,
  channel TEXT,
  delivery_state TEXT NOT NULL,
  command_state TEXT NOT NULL,
  detail TEXT,
  tokens_burned INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
