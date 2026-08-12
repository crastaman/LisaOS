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

GRAPH_STATE_V2 = "lisa-graph-state/2"


def package_record(raw: Any) -> dict[str, Any]:
    """Normalize a v1 scalar or v2 package value to the v2 record shape."""
    if isinstance(raw, dict):
        record = dict(raw)
    else:
        status = str(raw or "not_started")
        record = {"status": status}
    status = str(record.get("status") or "not_started")
    record.setdefault("execution_state", record.get("execution_state"))
    record.setdefault("dispatch_state", record.get("dispatch_state"))
    record.setdefault("result_state", record.get("result_state"))
    record.setdefault("run_ids", [record["run_id"]] if record.get("run_id") else [])
    record.setdefault("brief_hash", None)
    record.setdefault("dispatched_at", None)
    record.setdefault("reconciled_at", None)
    record.setdefault("retry_count", 0)
    record.setdefault("fencing_key", None)
    record.setdefault("last_event_ms", 0)
    record["status"] = status
    return record


def normalize_graph_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return a v2 state without losing v1 provenance needed for T18."""
    normalized = dict(state)
    source_schema = str(state.get("schema") or "lisa-graph-state/1")
    normalized["schema"] = GRAPH_STATE_V2
    normalized["source_schema"] = source_schema
    normalized["normalized_from_v1"] = source_schema != GRAPH_STATE_V2
    normalized["packages"] = {
        str(pid): package_record(raw)
        for pid, raw in (state.get("packages") or {}).items()
    }
    run_map: dict[str, str] = dict(state.get("run_id_to_package") or {})
    for pid, record in normalized["packages"].items():
        for run_id in record.get("run_ids") or ():
            if run_id:
                run_map[str(run_id)] = pid
    normalized["run_id_to_package"] = run_map
    return normalized


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

    def load_v2(self) -> GraphStateLoad:
        loaded = self.load()
        if not loaded.valid or not loaded.exists:
            return loaded
        return GraphStateLoad(normalize_graph_state(loaded.state), True, True)

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
