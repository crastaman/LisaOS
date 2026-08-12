#!/usr/bin/env python3
"""Apply RC004 Wave 1 reliability schema migration to an sqlite database.

The runner is idempotent by inspecting existing columns before applying each
additive change. By default it targets OpenClaw's local gateway DB and creates
a same-directory backup before writing. Tests pass an isolated temp DB.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

OPENCLAW_DB = Path.home() / ".openclaw" / "state" / "openclaw.sqlite"

TASK_RUN_COLUMNS = {
    "dispatch_state": "TEXT",
    "execution_state": "TEXT",
    "session_state": "TEXT",
    "result_state": "TEXT",
    "requires_reconciliation": "INTEGER",
    "terminal_evidence": "TEXT",
    "command_state": "TEXT",
}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def apply_migration(path: Path, *, backup: bool = True) -> Path | None:
    if not path.is_file():
        raise FileNotFoundError(path)
    backup_path: Path | None = None
    if backup:
        backup_path = path.with_suffix(
            path.suffix + f".rc004-wave1-backup-{int(time.time())}"
        )
        src = sqlite3.connect(str(path))
        try:
            dst = sqlite3.connect(str(backup_path))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

    conn = sqlite3.connect(str(path))
    try:
        cols = _columns(conn, "task_runs")
        if not cols:
            raise RuntimeError("task_runs table not found")
        for name, coltype in TASK_RUN_COLUMNS.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE task_runs ADD COLUMN {name} {coltype}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_runs_reconcile "
            "ON task_runs(requires_reconciliation, execution_state)"
        )
        conn.execute(
            """
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
            )
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return backup_path


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else OPENCLAW_DB
    backup = "--no-backup" not in argv[2:]
    backup_path = apply_migration(target, backup=backup)
    print(f"migrated={target}")
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
