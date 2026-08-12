"""SQLite accessor for RC005/A3 session lifecycle state."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

FIELDS = (
    "agent_id", "project", "sprint", "employee", "role", "task_family",
    "session_state", "cache_read", "context_window", "context_pct",
    "last_seen_at", "throttle_until", "reset_time", "compact_count",
    "opened_at", "retired_at",
)


class SessionLifecycleStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def get(self, session_key: str) -> dict[str, Any] | None:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM session_lifecycle WHERE session_key = ?", (session_key,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def upsert(self, session_key: str, **values: Any) -> dict[str, Any]:
        unknown = set(values) - set(FIELDS)
        if unknown:
            raise ValueError(f"unsupported session lifecycle fields: {sorted(unknown)}")
        values.setdefault("last_seen_at", int(time.time() * 1000))
        columns = ["session_key", *values]
        assignments = ", ".join(f"{name}=excluded.{name}" for name in values)
        sql = (
            f"INSERT INTO session_lifecycle ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)}) "
            f"ON CONFLICT(session_key) DO UPDATE SET {assignments}"
        )
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(sql, (session_key, *values.values()))
            conn.commit()
        finally:
            conn.close()
        return self.get(session_key) or {}

    def mark_throttled(self, session_key: str, *, throttle_until: str,
                       reset_time: str | None = None) -> dict[str, Any]:
        return self.upsert(session_key, session_state="THROTTLED",
                           throttle_until=throttle_until, reset_time=reset_time)

    def update_telemetry(self, session_key: str, *, cache_read: int,
                         context_window: int, session_state: str = "ACTIVE") -> dict[str, Any]:
        pct = (float(cache_read) / context_window) if context_window > 0 else None
        return self.upsert(session_key, session_state=session_state,
                           cache_read=cache_read, context_window=context_window,
                           context_pct=pct)
