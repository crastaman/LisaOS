"""Mission-scoped durable graph-state persistence for RC004R.

All reconciliation/admission state mutations use one advisory lock and
collision-safe temp files. The store is intentionally small: it protects the
Wave 1 execution-truth boundary without redesigning the scheduler.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def mission_id_for_goal(goal_path: str | Path | None) -> str | None:
    if not goal_path:
        return None
    try:
        text = str(Path(goal_path).expanduser().resolve())
    except OSError:
        text = str(goal_path)
    return "goal:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def scoped_graph_state_path(base_path: str | Path, mission_id: str | None) -> Path:
    p = Path(base_path)
    if not mission_id:
        return p
    suffix = hashlib.sha256(mission_id.encode("utf-8")).hexdigest()[:16]
    return p.with_name(f"{p.stem}-{suffix}{p.suffix}")


@dataclass(frozen=True)
class GraphStateLoad:
    state: dict[str, Any]
    exists: bool
    valid: bool
    error: str | None = None


class GraphStateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @contextmanager
    def locked(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("w", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def load(self) -> GraphStateLoad:
        if not self.path.exists():
            return GraphStateLoad({}, exists=False, valid=True)
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return GraphStateLoad({}, exists=True, valid=False, error=str(exc))
        if not isinstance(loaded, dict):
            return GraphStateLoad({}, exists=True, valid=False, error="graph state is not an object")
        return GraphStateLoad(loaded, exists=True, valid=True)

    def write_atomic(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        try:
            tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, self.path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

    def mutate_locked(self, fn: Callable[[GraphStateLoad], dict[str, Any]]) -> dict[str, Any]:
        with self.locked():
            loaded = self.load()
            state = fn(loaded)
            self.write_atomic(state)
            return state