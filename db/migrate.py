#!/usr/bin/env python3
"""Backup-first idempotent RC004+RC005 reliability migration runner."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

from db.migrate_reliability import apply_migration as apply_wave1


def _backup(path: Path) -> Path:
    target = path.with_suffix(path.suffix + f".reliability-backup-{int(time.time() * 1000)}")
    src = sqlite3.connect(str(path))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def apply_all(path: Path, *, backup: bool = True) -> Path | None:
    if not path.is_file():
        raise FileNotFoundError(path)
    backup_path = _backup(path) if backup else None
    apply_wave1(path, backup=False)
    migration_dir = Path(__file__).parent / "migrations"
    sql_paths = [migration_dir / "rc003_002_session_lifecycle.sql",
                 migration_dir / "rc003_003_observability.sql"]
    conn = sqlite3.connect(str(path))
    try:
        for sql_path in sql_paths:
            conn.executescript(sql_path.read_text(encoding="utf-8"))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return backup_path


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("usage: db/migrate.py DB_PATH [--no-backup]")
    target = Path(argv[1])
    backup_path = apply_all(target, backup="--no-backup" not in argv[2:])
    print(f"migrated={target}")
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
