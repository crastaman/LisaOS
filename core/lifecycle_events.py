"""Kind-scoped lifecycle audit events for RC005/F1."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_KINDS = frozenset({
    "session.open", "session.reuse", "session.pressure", "session.compact",
    "session.retire", "session.throttle", "reconcile.decision",
    "cron.delivery_preflight",
})


def emit_event(db_path: str | Path, kind: str, *, entity_type: str | None = None,
               entity_id: str | None = None, from_state: str | None = None,
               to_state: str | None = None, payload: dict[str, Any] | None = None) -> bool:
    """Append one meaningful transition; no per-tick events and no migration."""
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"unsupported lifecycle event kind: {kind}")
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                "INSERT INTO lisa_audit_events "
                "(kind,entity_type,entity_id,from_state,to_state,payload,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (kind, entity_type, entity_id, from_state, to_state,
                 json.dumps(payload or {}, sort_keys=True),
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except sqlite3.Error:
        return False
