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

from core.execution_state import EXEC_UNKNOWN
from core.graph_state_store import GraphStateStore, mission_id_for_goal, scoped_graph_state_path
from core.reconciliation import (
    RECONCILE_RESUME,
    RECONCILE_RETRY,
    ReconciliationEvidence,
    decide_reconciliation,
    graph_unknown_packages,
)

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
UNKNOWN_STATUSES = frozenset({"execution_unknown", "EXECUTION_UNKNOWN"})
LIVE_TASK_STATUSES = frozenset({"running", "queued", "pending", "in_progress", "started"})
COMPLETED_TASK_STATUSES = frozenset({"succeeded", "ok"})
FAILED_TASK_STATUSES = frozenset({"failed", "timed_out", "cancelled"})
LIVE_SESSION_STATES = frozenset({"running", "live", "active", "in_progress"})
DEAD_SESSION_STATES = frozenset({"dead", "closed", "ended", "expired", "failed"})


def graph_state_path_for_goal(goal_path: str) -> Path:
    """Return the mission-scoped graph-state path for a goal file."""
    return scoped_graph_state_path(GRAPH_STATE_PATH, mission_id_for_goal(goal_path))


def _package_status(raw: Any) -> str:
    if isinstance(raw, dict):
        return raw.get("status") or raw.get("execution_state") or ""
    return str(raw)


def _fetch_task_run(run_id: str | None) -> Dict[str, Any] | None:
    if not run_id or not OPENCLAW_DB.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{OPENCLAW_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM task_runs WHERE run_id = ? LIMIT 1",
                (run_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _fetch_session_lifecycle(session_key: str | None) -> Dict[str, Any] | None:
    if not session_key or not OPENCLAW_DB.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{OPENCLAW_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='session_lifecycle'"
            ).fetchone()
            if not table:
                return None
            row = conn.execute(
                "SELECT * FROM session_lifecycle WHERE session_key = ? LIMIT 1",
                (session_key,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _artifact_present(path: str | None) -> bool | None:
    if not path:
        return None
    return Path(path).exists()


def _authoritative_meta(
    pid: str,
    raw: Any,
    packages_meta: Optional[Dict[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    meta = dict((packages_meta or {}).get(pid, {}))
    if isinstance(raw, dict):
        meta = {**raw, **meta}

    row = _fetch_task_run(meta.get("run_id"))
    if row:
        status = str(row.get("status") or "").lower()
        meta.setdefault("task_run_completed", status in COMPLETED_TASK_STATUSES)
        meta.setdefault("task_run_live", status in LIVE_TASK_STATUSES)
        if row.get("session_key"):
            meta.setdefault("session_key", row.get("session_key"))
        if row.get("execution_state"):
            meta.setdefault("execution_state", row.get("execution_state"))
        if row.get("terminal_evidence") and not meta.get("terminal_evidence"):
            try:
                terminal_evidence = json.loads(row.get("terminal_evidence") or "{}")
                if isinstance(terminal_evidence, dict):
                    meta["terminal_evidence"] = terminal_evidence
            except (TypeError, json.JSONDecodeError):
                pass

    session = _fetch_session_lifecycle(meta.get("session_key"))
    session_state = str((session or {}).get("session_state") or "").lower()
    if session_state in LIVE_SESSION_STATES:
        meta.setdefault("session_live", True)
    elif session_state in DEAD_SESSION_STATES:
        meta.setdefault("session_live", False)

    artifact_path = (
        meta.get("expected_artifact_path")
        or meta.get("artifact_path")
        or meta.get("artifact")
    )
    artifact = _artifact_present(str(artifact_path) if artifact_path else None)
    if artifact is not None:
        meta.setdefault("artifact_present", artifact)
    elif meta.get("task_run_completed") is True:
        meta.setdefault("artifact_present", True)

    terminal_evidence = meta.get("terminal_evidence")
    terminal_verified_dead = (
        isinstance(terminal_evidence, dict)
        and terminal_evidence.get("verified_death") is True
    )

    if row:
        status = str(row.get("status") or "").lower()
        session_dead = session_state in DEAD_SESSION_STATES if session_state else False
        if status in FAILED_TASK_STATUSES and session_dead and terminal_verified_dead:
            meta["authoritative_verified_dead"] = True

    return meta


def apply_reconciliation_decisions(state: Dict[str, Any]) -> None:
    packages = state.setdefault("packages", {})
    for pid, decision in (state.get("reconciliation_decisions") or {}).items():
        if decision.get("decision") != RECONCILE_RESUME:
            continue
        reasons = set((decision.get("evidence") or {}).get("reasons") or [])
        if "completed task_run and artifact found" in reasons:
            packages[pid] = "completed"
        elif "live execution signal found" in reasons:
            packages[pid] = {
                "status": "running",
                "execution_state": EXEC_UNKNOWN,
            }


def reconcile_unknowns(
    state: Optional[Dict[str, Any]],
    packages_meta: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run the B1 gate for UNKNOWN packages and store decisions in state.

    The default evidence is intentionally indeterminate; callers/tests may
    supply package metadata with explicit probe facts. Without such evidence
    the gate records ESCALATE, never RETRY.
    """
    decisions: Dict[str, Any] = {}
    if state is None:
        return decisions
    for pid in graph_unknown_packages(state):
        existing = (state.get("reconciliation_decisions") or {}).get(pid)
        if isinstance(existing, dict) and existing.get("consumed") is True:
            decisions[pid] = existing
            continue
        if _is_unconsumed_retry(existing):
            decisions[pid] = existing
            continue
        raw = (state.get("packages") or {}).get(pid)
        meta = _authoritative_meta(pid, raw, packages_meta)
        decision = decide_reconciliation(ReconciliationEvidence(
            package_id=pid,
            run_id=meta.get("run_id"),
            execution_state=meta.get("execution_state") or EXEC_UNKNOWN,
            session_live=meta.get("session_live"),
            task_run_live=meta.get("task_run_live"),
            task_run_completed=meta.get("task_run_completed"),
            artifact_present=meta.get("artifact_present"),
            verified_dead=meta.get("authoritative_verified_dead"),
            death_evidence_authoritative=bool(meta.get("authoritative_verified_dead")),
            retry_count=int(meta.get("retry_count") or 0),
        ))
        decisions[pid] = decision.to_dict()
    if decisions:
        state.setdefault("reconciliation_decisions", {}).update(decisions)
        apply_reconciliation_decisions(state)
    return decisions


def _is_unconsumed_retry(record: Dict[str, Any] | None) -> bool:
    return (
        isinstance(record, dict)
        and record.get("decision") == RECONCILE_RETRY
        and record.get("consumed") is not True
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- state I/O -----------------------------------------------------------

def load_graph_state(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    p = path or GRAPH_STATE_PATH
    loaded = GraphStateStore(p).load()
    return loaded.state if loaded.valid and loaded.exists else None


def write_graph_state(state: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Atomic write that preserves concurrently consumed retry decisions."""
    p = path or GRAPH_STATE_PATH

    def merge(loaded):
        if not loaded.valid:
            return state
        merged = dict(state)
        existing_decisions = (loaded.state.get("reconciliation_decisions") or {})
        incoming_decisions = dict(state.get("reconciliation_decisions") or {})
        for pid, existing in existing_decisions.items():
            incoming = incoming_decisions.get(pid)
            if isinstance(existing, dict) and existing.get("consumed") is True:
                combined = dict(incoming or {})
                combined.update(existing)
                combined["consumed"] = True
                incoming_decisions[pid] = combined
        if incoming_decisions:
            merged["reconciliation_decisions"] = incoming_decisions
        return merged

    GraphStateStore(p).mutate_locked(merge)


def _set_escalation_pending(path: Path, pending: bool) -> None:
    def mutate(loaded):
        state = loaded.state if loaded.valid and loaded.exists else {}
        state["escalation_pending"] = pending
        return state

    GraphStateStore(path).mutate_locked(mutate)


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

    unknown = graph_unknown_packages(state)
    if unknown:
        decisions = reconcile_unknowns(state)
        return all(
            _is_unconsumed_retry(decisions.get(pid))
            for pid in unknown
        )

    # Any non-terminal package means work is pending, except a verified live
    # remote execution which must be held, not redispatched.
    if any(_package_status(s) not in TERMINAL | {"running"} for s in packages.values()):
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
    unknown = graph_unknown_packages(state)
    if unknown:
        decisions = reconcile_unknowns(state, packages_meta)
        return any(
            decisions.get(pid, {}).get("decision") != RECONCILE_RETRY
            for pid in unknown
        )
    failed_ids = [
        pid for pid, s in packages.items()
        if _package_status(s) in ("failed", "timed_out")
    ]
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
    statuses = [_package_status(s) for s in packages.values()]
    if (all(s in TERMINAL for s in statuses)
            and any(s == "blocked" for s in statuses)
            and not any(s == "completed" for s in statuses)):
        return True

    return False


def decide_action(
    state: Optional[Dict[str, Any]],
    packages_meta: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    if state is None:
        return DECISION_DONE
    unknown = graph_unknown_packages(state)
    if unknown:
        decisions = reconcile_unknowns(state, packages_meta)
        if not graph_unknown_packages(state):
            if needs_escalation(state, packages_meta):
                return DECISION_WAKE_MAIN
            if needs_dispatch(state):
                return DECISION_CONTINUE
            return DECISION_DONE
        if all(
            _is_unconsumed_retry(decisions.get(pid))
            for pid in unknown
        ):
            return DECISION_CONTINUE
        return DECISION_WAKE_MAIN
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
        meta = getattr(graph, "package_metadata", {}).get(pid, {}) if hasattr(graph, "package_metadata") else {}
        packages[pid] = meta.get("status", "failed")
    for pid in graph.blocked():
        packages[pid] = "blocked"
    for pid in getattr(graph, "in_progress", set()):
        packages[pid] = "in_progress"
    mids = list(mission_run_ids or [])
    return {
        "schema": "lisa-graph-state/1",
        "mission_id": mission_id_for_goal(goal_path),
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
    graph_state_path: Optional[Path] = None,
) -> str:
    """Load persisted graph state and decide whether to re-dispatch.

    Called BEFORE dispatch (by mission wrapper, watcher, or cron trigger) to
    determine whether a mission needs another dispatch cycle. Pure decision:
    never spawns workers, never modifies state, never calls MAIN/LLM.

    Exactly-once guard: if the mission is already DONE (all terminal, no new
    runs), this returns DECISION_DONE and the caller must NOT re-dispatch.

    Returns CONTINUE / WAKE_MAIN / DONE.
    """
    state_path = graph_state_path or GRAPH_STATE_PATH
    store = GraphStateStore(state_path)
    with store.locked():
        loaded = store.load()
        if not loaded.exists:
            return DECISION_DONE
        if not loaded.valid:
            return DECISION_WAKE_MAIN
        state = loaded.state

        # Verify this state belongs to the requested mission.
        stored_goal = state.get("goal_path", "")
        if stored_goal and Path(stored_goal).resolve() != Path(goal_path).resolve():
            return DECISION_DONE
        expected_mission = mission_id_for_goal(goal_path)
        state_mission = state.get("mission_id")
        if state_mission and expected_mission and state_mission != expected_mission:
            return DECISION_DONE
        if graph_unknown_packages(state) and not state_mission:
            return DECISION_WAKE_MAIN

        had_unknown = bool(graph_unknown_packages(state))
        decision = decide_action(state, packages_meta)
        if had_unknown:
            store.write_atomic(state)
        return decision


def advance_pipeline(
    goal_path: str,
    graph: Any = None,
    packages_meta: Optional[Dict[str, Dict[str, Any]]] = None,
    new_run_ids: Optional[list] = None,
    max_cycles: int = 20,
    graph_state_path: Optional[Path] = None,
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
    state_path = graph_state_path or GRAPH_STATE_PATH

    while cycles < max_cycles:
        cycles += 1

        store = GraphStateStore(state_path)
        with store.locked():
            loaded = store.load()
            state = loaded.state if loaded.valid and loaded.exists else None

            if state is None and graph is not None:
                state = build_graph_state(graph, goal_path)
            elif state is not None and graph is not None:
                # Merge latest graph into existing state without releasing the
                # admission lock, so reconciliation decisions are durable with
                # the package lifecycle view that produced them.
                packages = state.setdefault("packages", {})
                for pid in getattr(graph, "completed", set()):
                    packages[pid] = "completed"
                for pid in getattr(graph, "failed", set()):
                    previous = packages.get(pid)
                    packages[pid] = (
                        previous if _package_status(previous) == "execution_unknown"
                        else "failed"
                    )
                for pid in graph.blocked():
                    packages[pid] = "blocked"
                existing_ids = set(state.get("mission_run_ids") or ())
                existing_ids.update(new_run_ids or ())
                state["mission_run_ids"] = sorted(existing_ids)
                state["high_water_mark_ms"] = _compute_high_water_mark(existing_ids)
                state["last_dispatch_at"] = _now_iso()

            decision = decide_action(state, packages_meta)
            if state is not None:
                store.write_atomic(state)
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
                    _set_escalation_pending(state_path, False)
                if WAKE_PENDING_PATH.is_file():
                    WAKE_PENDING_PATH.unlink(missing_ok=True)
            else:
                if state:
                    _set_escalation_pending(state_path, True)
                _write_wake_pending(goal_path)
            break

        elif decision == DECISION_CONTINUE:
            # Dispatcher.run() already processed the full graph synchronously.
            # CONTINUE signals the next cron tick should re-dispatch.
            break

        else:  # DONE
            break

    return last_decision
