"""Durable session retirement and handoff artifacts (RC005/D2)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.session_lifecycle import SessionLifecycleStore

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
DEFAULT_DB = Path.home() / ".openclaw" / "state" / "openclaw.sqlite"
HANDOFF_DIR = LISA_BASE / "reports" / "lisa" / "orchestration" / "handoffs"


def handoff_required(session: dict[str, Any] | None, *, threshold: float | None = None) -> bool:
    if threshold is None:
        from core.reliability_config import load_reliability_config
        threshold = load_reliability_config().session_threshold("warning_threshold_pct", 0.80)
    return float((session or {}).get("context_pct") or 0) >= threshold


def retire_session(session_key: str, reason: str, context_pct: float,
                   *, db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return SessionLifecycleStore(db_path).upsert(
        session_key, session_state="RETIRED", context_pct=min(1.0, max(0.0, context_pct)),
        retired_at=now, last_seen_at=int(datetime.now(timezone.utc).timestamp() * 1000),
    ) | {"retirement_reason": reason}


def write_handoff(session_key: str, target_worker: str, summary: Any,
                  *, output_dir: Path = HANDOFF_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in session_key)[-120:]
    path = output_dir / f"{safe}-handoff.json"
    payload = {"schema": "lisa-handoff/1", "session_key": session_key,
               "target_worker": target_worker, "summary": summary,
               "created_at": datetime.now(timezone.utc).isoformat()}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path
