-- LISA-RC005 / RC003 Wave 2 session lifecycle store (additive only).
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
