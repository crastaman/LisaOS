"""LisaOS Auto-Resume — deterministic pipeline advancement after dispatch.

Pure decision functions: loads persisted graph state, decides whether to
continue autonomously or wake MAIN via systemEvent. Never spawns workers,
never modifies the dependency graph, never makes LLM calls. The Dispatcher
remains the sole execution authority.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
ORCHESTRATION_DIR = LISA_BASE / "reports" / "lisa" / "orchestration"
GRAPH_STATE_PATH = ORCHESTRATION_DIR / "graph_state.json"
WAKE_PENDING_PATH = ORCHESTRATION_DIR / "wake_pending.json"
OPENCLAW_DB = Path.home() / ".openclaw" / "state" / "openclaw.sqlite"
OPENCLAW_BIN = os.environ.get("OPENCLAW_BIN", "/opt/homebrew/bin/openclaw")

DECISION_CONTINUE = "CONTINUE"
DECISION_WAKE_MAIN = "WAKE_MAIN"
DECISION_DONE = "DONE"

TERMINAL = frozenset({"completed", "failed", "blocked", "timed_out"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- state I/O -----------------------------------------------------------

def load_graph_state(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    p = path or GRAPH_STATE_PATH
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_graph_state(state: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Atomic write: tmp + os.replace."""
    p = path or GRAPH_STATE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


# -- high-water mark ------------------------------------------------------

def _compute_high_water_mark(run_ids: Optional[set] = None) -> int:
    """Max task_runs.created_at (ms) — scoped when run_ids is provided.

    run_ids=None  → all task_runs (backward-compat / unscoped).
    run_ids=set() → empty set, return 0 (no mission runs yet).
    run_ids={...} → MAX(created_at) WHERE run_id IN (...).
    """
    if not OPENCLAW_DB.is_file():
        return 0
    if run_ids is not None and not run_ids:
        return 0
    try:
        conn = sqlite3.connect(f"file:{OPENCLAW_DB}?mode=ro", uri=True)
        try:
            if run_ids is None:
                row = conn.execute(
                    "SELECT MAX(created_at) FROM task_runs"
                    " WHERE created_at IS NOT NULL"
                ).fetchone()
            else:
                placeholders = ",".join("?" for _ in run_ids)
                row = conn.execute(
                    f"SELECT MAX(created_at) FROM task_runs"
                    f" WHERE run_id IN ({placeholders})"
                    f" AND created_at IS NOT NULL",
                    tuple(run_ids),
                ).fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        finally:
            conn.close()
    except sqlite3.Error:
        return 0


# -- decision functions --------------------------------------------------

def needs_dispatch(state: Optional[Dict[str, Any]]) -> bool:
    """True if pending or newly-ready work exists."""
    if state is None:
        return False
    packages = state.get("packages", {})
    if not packages:
        return False

    # Any non-terminal package means work is pending.
    if any(s not in TERMINAL for s in packages.values()):
        return True

    # New task_runs since last checkpoint (scoped to mission's own runs)?
    hwm = state.get("high_water_mark_ms", 0)
    mission_ids = state.get("mission_run_ids")
    if mission_ids is not None:
        hwm_now = _compute_high_water_mark(set(mission_ids))
    else:
        # legacy state without mission_run_ids: unscoped backward compat
        hwm_now = _compute_high_water_mark(None)
    if hwm_now > hwm:
        return True

    # Escalation still undelivered?
    if WAKE_PENDING_PATH.is_file():
        return True

    return False


def needs_escalation(
    state: Optional[Dict[str, Any]],
    packages_meta: Optional[Dict[str, Dict[str, Any]]] = None,
) -> bool:
    """True if MAIN must be woken: critical failure, retry exhaustion, full blockage."""
    if state is None:
        return False
    packages = state.get("packages", {})
    failed_ids = [pid for pid, s in packages.items() if s in ("failed", "timed_out")]
    if not failed_ids:
        return False

    if packages_meta:
        for pid in failed_ids:
            meta = packages_meta.get(pid, {})
            if meta.get("risk") == "critical":
                return True
            retries = meta.get("retries", 0)
            if retries >= meta.get("max_retries", 3):
                return True

    # Full blockage: all terminal, zero completed, and at least one blocked.
    if (all(s in TERMINAL for s in packages.values())
            and any(s == "blocked" for s in packages.values())
            and not any(s == "completed" for s in packages.values())):
        return True

    return False


def decide_action(
    state: Optional[Dict[str, Any]],
    packages_meta: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    if state is None:
        return DECISION_DONE
    if needs_escalation(state, packages_meta):
        return DECISION_WAKE_MAIN
    if needs_dispatch(state):
        return DECISION_CONTINUE
    return DECISION_DONE


# -- systemEvent delivery ------------------------------------------------

def _send_system_event(text: str, session_key: str = "main") -> bool:
    try:
        result = subprocess.run(
            [OPENCLAW_BIN, "system", "event",
             "--text", text, "--session-key", session_key,
             "--mode", "now", "--json"],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _write_wake_pending(goal_path_str: str) -> None:
    WAKE_PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    WAKE_PENDING_PATH.write_text(
        json.dumps({"at": _now_iso(), "goal_path": goal_path_str}) + "\n",
        encoding="utf-8",
    )


# -- pipeline advancement ------------------------------------------------

def build_graph_state(
    graph: Any,
    goal_path: str,
    mission_run_ids: Optional[list] = None,
) -> Dict[str, Any]:
    """Build state dict from a DependencyGraph + goal path.

    mission_run_ids: task_run run_id strings from this dispatch cycle.
    Stored so HWM queries scope to the mission's own activity.
    """
    summary = graph.summary()
    packages: Dict[str, str] = {}
    for pid in getattr(graph, "completed", set()):
        packages[pid] = "completed"
    for pid in getattr(graph, "failed", set()):
        packages[pid] = "failed"
    for pid in graph.blocked():
        packages[pid] = "blocked"
    for pid in getattr(graph, "in_progress", set()):
        packages[pid] = "in_progress"
    mids = list(mission_run_ids or [])
    return {
        "schema": "lisa-graph-state/1",
        "goal_path": goal_path,
        "packages": packages,
        "high_water_mark_ms": _compute_high_water_mark(set(mids) if mids else None),
        "last_dispatch_at": _now_iso(),
        "escalation_pending": False,
        "mission_run_ids": mids,
    }


def resume_if_needed(
    goal_path: str,
    packages_meta: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Load persisted graph state and decide whether to re-dispatch.

    Called BEFORE dispatch (by mission wrapper, watcher, or cron trigger) to
    determine whether a mission needs another dispatch cycle. Pure decision:
    never spawns workers, never modifies state, never calls MAIN/LLM.

    Exactly-once guard: if the mission is already DONE (all terminal, no new
    runs), this returns DECISION_DONE and the caller must NOT re-dispatch.

    Returns CONTINUE / WAKE_MAIN / DONE.
    """
    state = load_graph_state()
    if state is None:
        return DECISION_DONE

    # Verify this state belongs to the requested mission.
    stored_goal = state.get("goal_path", "")
    if stored_goal and Path(stored_goal).resolve() != Path(goal_path).resolve():
        return DECISION_DONE

    return decide_action(state, packages_meta)


def advance_pipeline(
    goal_path: str,
    graph: Any = None,
    packages_meta: Optional[Dict[str, Dict[str, Any]]] = None,
    new_run_ids: Optional[list] = None,
    max_cycles: int = 20,
) -> str:
    """Post-dispatch: persist state, escalate if needed, return decision.

    Called after Dispatcher.run() completes. Writes graph state atomically,
    wakes MAIN via systemEvent on escalation, writes wake_pending.json if
    the event is undeliverable.

    new_run_ids: task_run run_id strings from the just-completed dispatch
    cycle. Merged into mission_run_ids so HWM stays mission-scoped.

    Returns CONTINUE / WAKE_MAIN / DONE.
    """
    cycles = 0
    last_decision = DECISION_DONE

    while cycles < max_cycles:
        cycles += 1

        state = load_graph_state()

        if state is None and graph is not None:
            state = build_graph_state(graph, goal_path)
            write_graph_state(state)
        elif state is not None and graph is not None:
            # Merge latest graph into existing state.
            for pid in getattr(graph, "completed", set()):
                state["packages"][pid] = "completed"
            for pid in getattr(graph, "failed", set()):
                state["packages"][pid] = "failed"
            for pid in graph.blocked():
                state["packages"][pid] = "blocked"
            existing_ids = set(state.get("mission_run_ids") or ())
            existing_ids.update(new_run_ids or ())
            state["mission_run_ids"] = sorted(existing_ids)
            state["high_water_mark_ms"] = _compute_high_water_mark(existing_ids)
            state["last_dispatch_at"] = _now_iso()
            write_graph_state(state)

        decision = decide_action(state, packages_meta)
        last_decision = decision

        if decision == DECISION_WAKE_MAIN:
            failed = [pid for pid, s in (state or {}).get("packages", {}).items()
                      if s in ("failed", "timed_out")]
            blocked = [pid for pid, s in (state or {}).get("packages", {}).items()
                       if s == "blocked"]
            msg = f"LisaOS: {len(failed)} failed"
            if blocked:
                msg += f", {len(blocked)} blocked"
            msg += f". Goal: {Path(goal_path).name}"

            if _send_system_event(msg):
                if state:
                    state["escalation_pending"] = False
                if WAKE_PENDING_PATH.is_file():
                    WAKE_PENDING_PATH.unlink(missing_ok=True)
            else:
                if state:
                    state["escalation_pending"] = True
                _write_wake_pending(goal_path)
            if state:
                write_graph_state(state)
            break

        elif decision == DECISION_CONTINUE:
            # Dispatcher.run() already processed the full graph synchronously.
            # CONTINUE signals the next cron tick should re-dispatch.
            break

        else:  # DONE
            break

    return last_decision
