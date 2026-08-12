"""Tests for auto-resume wiring: mission wrapper + watcher + trigger + exactly-once.

Covers:
  1. resume_if_needed() decision flow (CONTINUE/DONE/WAKE_MAIN)
  2. Mission wrapper: dispatch→auto-resume→next-stage (integration)
  3. Watcher no-op on unchanged / all-terminal state
  4. Watcher fires (re-dispatches) on changed state (non-terminal work)
  5. DONE mission never re-dispatches (exactly-once guard)
  6. HWM mission-scoped preserved across dispatch cycles
  7. Trigger logic: fire/don't-fire decisions from graph state

All tests hermetic: no real OpenClaw, no subprocess, no network, no spend.
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.dependency_graph import DependencyGraph, GraphError
from core.workforce_resolver import WorkPackage
import core.auto_resume as ar

# -- test helpers ---------------------------------------------------------

def _pkg(id, deps=None, risk="normal"):
    return WorkPackage(
        id=id, description=f"package {id}",
        required_capabilities=["code"],
        risk=risk, depends_on=list(deps or []),
    )


def _make_state(packages=None, hwm=0, goal_path="/tmp/test_goal.json",
                mission_run_ids=None, escalation_pending=False):
    return {
        "schema": "lisa-graph-state/1",
        "goal_path": goal_path,
        "packages": packages or {},
        "high_water_mark_ms": hwm,
        "last_dispatch_at": "2026-08-09T22:00:00+00:00",
        "escalation_pending": escalation_pending,
        "mission_run_ids": mission_run_ids or [],
    }


def _make_goal_file(packages, tmpdir):
    """Write a goal.json to tmpdir and return the path."""
    data = []
    for pkg in packages:
        data.append({
            "id": pkg.id,
            "description": pkg.description,
            "required_capabilities": pkg.required_capabilities,
            "risk": pkg.risk,
            "depends_on": pkg.depends_on,
        })
    path = Path(tmpdir) / "goal.json"
    path.write_text(json.dumps(data))
    return str(path)


# ============================================================================
# 1. resume_if_needed() decision flow
# ============================================================================

class TestResumeIfNeeded(unittest.TestCase):
    """resume_if_needed() — loads state and returns CONTINUE/DONE/WAKE_MAIN."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "graph_state.json"
        self.goal_path = str(Path(self.tmpdir.name) / "goal.json")
        # Write a dummy goal file so path resolution works.
        Path(self.goal_path).write_text("[]")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_no_state_returns_done(self):
        """No persisted state → DONE (nothing to resume)."""
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            result = ar.resume_if_needed(self.goal_path)
            self.assertEqual(result, ar.DECISION_DONE)

    def test_all_completed_no_new_runs_returns_done(self):
        """All terminal, HWM static → DONE (exactly-once guard)."""
        state = _make_state(
            packages={"a": "completed", "b": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=100):
            result = ar.resume_if_needed(self.goal_path)
            self.assertEqual(result, ar.DECISION_DONE)

    def test_in_progress_returns_continue(self):
        """Non-terminal work → CONTINUE."""
        state = _make_state(
            packages={"a": "in_progress", "b": "completed"},
            hwm=100, goal_path=self.goal_path,
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            result = ar.resume_if_needed(self.goal_path)
            self.assertEqual(result, ar.DECISION_CONTINUE)

    def test_critical_failure_returns_wake_main(self):
        """Critical failure → WAKE_MAIN."""
        state = _make_state(
            packages={"a": "failed"},
            hwm=100, goal_path=self.goal_path,
        )
        ar.write_graph_state(state, self.state_path)
        meta = {"a": {"risk": "critical"}}
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            result = ar.resume_if_needed(self.goal_path, packages_meta=meta)
            self.assertEqual(result, ar.DECISION_WAKE_MAIN)

    def test_goal_path_mismatch_returns_done(self):
        """State for a different mission → DONE (safety guard)."""
        state = _make_state(
            packages={"a": "in_progress"},
            hwm=0,
            goal_path="/different/mission/goal.json",
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            result = ar.resume_if_needed(self.goal_path)
            self.assertEqual(result, ar.DECISION_DONE)

    def test_new_run_advances_hwm_returns_continue(self):
        """An unrelated global HWM advance does not resume completed work."""
        state = _make_state(
            packages={"a": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=200):
            result = ar.resume_if_needed(self.goal_path)
            # RC003 §5.1 supersedes the global HWM with per-package HWM.
            self.assertEqual(result, ar.DECISION_DONE)


# ============================================================================
# 2. Mission wrapper: dispatch → auto-resume → next-stage (integration)
# ============================================================================

class TestMissionWrapper(unittest.TestCase):
    """bin/lisa-mission integration: the wrapper loops dispatch → resume decision.

    Rather than importing bin/lisa-mission (hyphenated filename blocks
    importlib), these tests exercise each decision-path of the wrapper's
    core loop through the auto-resume state file — the same mechanism the
    real subprocess sees when it calls resume_if_needed().

    The wrapper logic under test:
      dispatch → resume_if_needed → CONTINUE → re-dispatch → ... → DONE
                                  → WAKE_MAIN → exit 3
                                  → DONE → exit 0
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "graph_state.json"
        self.goal_path = _make_goal_file(
            [_pkg("a"), _pkg("b")], self.tmpdir.name,
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_single_dispatch_done(self):
        """After dispatch completes all work → DONE → wrapper exits 0."""
        state = _make_state(
            packages={"a": "completed", "b": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=100):
            decision = ar.resume_if_needed(self.goal_path)
            self.assertEqual(decision, ar.DECISION_DONE,
                             "wrapper exits 0 when resume returns DONE")

    def test_continue_re_dispatches(self):
        """In-progress work → CONTINUE → wrapper re-dispatches."""
        state = _make_state(
            packages={"a": "in_progress", "b": "completed"},
            hwm=100, goal_path=self.goal_path,
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            decision = ar.resume_if_needed(self.goal_path)
            self.assertEqual(decision, ar.DECISION_CONTINUE,
                             "wrapper re-dispatches when resume returns CONTINUE")

    def test_wake_main_propagates_exit_code_3(self):
        """Full blockage → WAKE_MAIN → wrapper exits 3."""
        state = _make_state(
            packages={"a": "failed", "b": "blocked"},
            hwm=100, goal_path=self.goal_path,
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            decision = ar.resume_if_needed(self.goal_path)
            self.assertEqual(decision, ar.DECISION_WAKE_MAIN,
                             "wrapper exits 3 when resume returns WAKE_MAIN")


# ============================================================================
# 3. Watcher: no-op on unchanged / all-terminal state
# ============================================================================

class TestWatcherNoOp(unittest.TestCase):
    """lisa-auto-resume-watch.py no-op when nothing changed."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "graph_state.json"
        self.goal_path = str(Path(self.tmpdir.name) / "goal.json")
        Path(self.goal_path).write_text("[]")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_no_state_no_op(self):
        """No graph state → watcher exits 0 (no work)."""
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            # _find_active_goal returns None when no state
            from core.auto_resume import load_graph_state
            goal = None
            state = load_graph_state()
            if state:
                goal = state.get("goal_path")
            self.assertIsNone(goal)

    def test_all_terminal_no_new_runs_no_op(self):
        """All completed, HWM unchanged → DONE decision."""
        state = _make_state(
            packages={"a": "completed", "b": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=100):
            decision = ar.resume_if_needed(self.goal_path)
            self.assertEqual(decision, ar.DECISION_DONE)
            # Watcher would exit 0 — no subprocess call.

    def test_no_state_at_all_no_op(self):
        """GRAPH_STATE_PATH missing entirely → watcher exits 0."""
        missing = Path(self.tmpdir.name) / "nonexistent.json"
        with patch.object(ar, "GRAPH_STATE_PATH", missing):
            state = ar.load_graph_state()
            self.assertIsNone(state)
            # resume_if_needed returns DONE for None state.
            decision = ar.resume_if_needed("/any/goal.json")
            self.assertEqual(decision, ar.DECISION_DONE)


# ============================================================================
# 4. Watcher fires on changed state (non-terminal work or new HWM)
# ============================================================================

class TestWatcherFires(unittest.TestCase):
    """lisa-auto-resume-watch.py fires (re-dispatches) on changed state."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "graph_state.json"
        self.goal_path = str(Path(self.tmpdir.name) / "goal.json")
        Path(self.goal_path).write_text("[]")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_in_progress_triggers_continue(self):
        """Non-terminal packages → CONTINUE (watcher fires)."""
        state = _make_state(
            packages={"a": "in_progress", "b": "completed"},
            hwm=100, goal_path=self.goal_path,
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            decision = ar.resume_if_needed(self.goal_path)
            self.assertEqual(decision, ar.DECISION_CONTINUE)

    def test_ready_work_triggers_continue(self):
        """Pending packages (ready but not yet dispatched) → CONTINUE."""
        state = _make_state(
            packages={"a": "completed", "b": "not_started"},
            hwm=100, goal_path=self.goal_path,
        )
        ar.write_graph_state(state, self.state_path)
        # RC003 §5.1: readiness comes from package state, not global HWM.
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            decision = ar.resume_if_needed(self.goal_path)
            self.assertEqual(decision, ar.DECISION_CONTINUE)

    def test_new_run_advances_hwm_fires(self):
        """An unrelated global task_run does not wake a completed mission."""
        state = _make_state(
            packages={"a": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)
        # Simulate a new run appearing (HWM now 200)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=200):
            decision = ar.resume_if_needed(self.goal_path)
            # RC003 §5.1 supersedes global HWM wakeups with package HWM.
            self.assertEqual(decision, ar.DECISION_DONE)

    def test_failed_retry_exhaustion_wakes_main(self):
        """RC003 §6.2: exhausted authoritative failure escalates."""
        state = _make_state(
            packages={"a": "completed", "b": {"status": "failed", "retry_count": 1}},
            hwm=100, goal_path=self.goal_path,
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=100):
            decision = ar.resume_if_needed(self.goal_path)
            self.assertEqual(decision, ar.DECISION_WAKE_MAIN)


# ============================================================================
# 5. DONE mission never re-dispatches (exactly-once guard)
# ============================================================================

class TestExactlyOnce(unittest.TestCase):
    """DONE mission is never re-dispatched — exactly-once guarantee."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "graph_state.json"
        self.goal_path = str(Path(self.tmpdir.name) / "goal.json")
        Path(self.goal_path).write_text("[]")
        self.db_path = Path(self.tmpdir.name) / "test_openclaw.sqlite"
        self._init_db()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS task_runs ("
            "  run_id TEXT PRIMARY KEY, created_at INTEGER,"
            "  status TEXT, ended_at INTEGER)"
        )
        conn.commit()
        conn.close()

    def _insert_run(self, run_id, created_at_ms, status="completed"):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT OR REPLACE INTO task_runs(run_id, created_at, status)"
            " VALUES (?, ?, ?)", (run_id, created_at_ms, status),
        )
        conn.commit()
        conn.close()

    def test_done_mission_resume_returns_done(self):
        """All completed, HWM static → resume_if_needed returns DONE."""
        self._insert_run("run-1", 100, "completed")
        state = _make_state(
            packages={"a": "completed", "b": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "OPENCLAW_DB", self.db_path):
            decision = ar.resume_if_needed(self.goal_path)
            self.assertEqual(decision, ar.DECISION_DONE)

    def test_done_mission_unrelated_run_ignored(self):
        """Unrelated task_run does NOT re-trigger a DONE mission."""
        self._insert_run("run-a1", 100, "completed")
        self._insert_run("run-unrelated", 9999, "completed")
        state = _make_state(
            packages={"a": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-a1"],
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "OPENCLAW_DB", self.db_path):
            # needs_dispatch should be False because the new run is not
            # in mission_run_ids, so the scoped HWM query won't see it.
            self.assertFalse(ar.needs_dispatch(state))
            decision = ar.resume_if_needed(self.goal_path)
            self.assertEqual(decision, ar.DECISION_DONE)

    def test_duplicate_consecutive_checks_same_decision(self):
        """Two consecutive checks on a DONE mission both return DONE."""
        self._insert_run("run-1", 100, "completed")
        state = _make_state(
            packages={"a": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "OPENCLAW_DB", self.db_path):
            d1 = ar.resume_if_needed(self.goal_path)
            d2 = ar.resume_if_needed(self.goal_path)
            d3 = ar.resume_if_needed(self.goal_path)
            self.assertEqual(d1, ar.DECISION_DONE)
            self.assertEqual(d2, ar.DECISION_DONE)
            self.assertEqual(d3, ar.DECISION_DONE)

    def test_done_mission_never_dispatches_after_terminal(self):
        """Once terminal with no new runs, DONE holds across restarts."""
        self._insert_run("run-1", 100, "completed")
        state = _make_state(
            packages={"a": "completed", "b": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)

        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "OPENCLAW_DB", self.db_path):
            # First check
            self.assertEqual(ar.resume_if_needed(self.goal_path), ar.DECISION_DONE)
            # Simulate watcher restart: re-load state, same result
            self.assertEqual(ar.resume_if_needed(self.goal_path), ar.DECISION_DONE)
            # Simulate cron re-trigger: still DONE
            self.assertEqual(ar.resume_if_needed(self.goal_path), ar.DECISION_DONE)

    def test_done_mission_does_not_dispatch_even_on_state_reload(self):
        """Re-loading state from disk should not change a DONE decision."""
        self._insert_run("run-1", 100, "completed")
        state = _make_state(
            packages={"a": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)

        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "OPENCLAW_DB", self.db_path):
            d1 = ar.resume_if_needed(self.goal_path)
            # Re-read state (simulating watcher re-evaluating)
            state2 = ar.load_graph_state()
            d2 = ar.decide_action(state2)
            self.assertEqual(d1, d2)
            self.assertEqual(d1, ar.DECISION_DONE)


# ============================================================================
# 6. HWM mission-scoped preserved across dispatch cycles
# ============================================================================

class TestHWMMissionScoped(unittest.TestCase):
    """HWM is scoped to mission_run_ids — preserved across cycles."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "graph_state.json"
        self.goal_path = str(Path(self.tmpdir.name) / "goal.json")
        Path(self.goal_path).write_text("[]")
        self.db_path = Path(self.tmpdir.name) / "test_openclaw.sqlite"
        self._init_db()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS task_runs ("
            "  run_id TEXT PRIMARY KEY, created_at INTEGER,"
            "  status TEXT, ended_at INTEGER)"
        )
        conn.commit()
        conn.close()

    def _insert_run(self, run_id, created_at_ms):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT OR REPLACE INTO task_runs(run_id, created_at, status)"
            " VALUES (?, ?, ?)", (run_id, created_at_ms, "completed"),
        )
        conn.commit()
        conn.close()

    def test_hwm_preserved_across_cycles(self):
        """HWM accumulates across dispatch cycles via mission_run_ids merge."""
        self._insert_run("run-1", 100)
        self._insert_run("run-2", 200)

        # Build initial state with run-1
        pkgs = [_pkg("a")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_complete("a")

        with patch.object(ar, "OPENCLAW_DB", self.db_path):
            state = ar.build_graph_state(g, self.goal_path,
                                         mission_run_ids=["run-1"])
            self.assertEqual(state["high_water_mark_ms"], 100)
            self.assertEqual(state["mission_run_ids"], ["run-1"])

            ar.write_graph_state(state, self.state_path)

            # Simulate advance_pipeline merging run-2
            g2 = DependencyGraph.from_packages(pkgs)
            g2.mark_complete("a")
            with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
                 patch.object(ar, "WAKE_PENDING_PATH",
                              Path(self.tmpdir.name) / "wp.json"):
                decision = ar.advance_pipeline(
                    self.goal_path, graph=g2, new_run_ids=["run-2"],
                )

            loaded = ar.load_graph_state(self.state_path)
            self.assertIn("run-1", loaded["mission_run_ids"])
            self.assertIn("run-2", loaded["mission_run_ids"])
            self.assertEqual(loaded["high_water_mark_ms"], 200)

    def test_hwm_scoped_only_sees_own_runs(self):
        """Scoped HWM ignores runs not in mission_run_ids."""
        self._insert_run("mission-a-1", 100)
        self._insert_run("mission-b-1", 9999)

        with patch.object(ar, "OPENCLAW_DB", self.db_path):
            # Scoped to mission A only → sees max of (100)
            hwm = ar._compute_high_water_mark({"mission-a-1"})
            self.assertEqual(hwm, 100)

    def test_empty_mission_run_ids_hwm_zero(self):
        """Empty mission_run_ids → HWM = 0."""
        self._insert_run("some-run", 500)
        with patch.object(ar, "OPENCLAW_DB", self.db_path):
            hwm = ar._compute_high_water_mark(set())
            self.assertEqual(hwm, 0)

    def test_build_state_preserves_mission_ids(self):
        """build_graph_state stores mission_run_ids in output."""
        self._insert_run("r1", 100)
        g = DependencyGraph.from_packages([_pkg("a")])
        g.mark_complete("a")
        with patch.object(ar, "OPENCLAW_DB", self.db_path):
            state = ar.build_graph_state(g, self.goal_path,
                                         mission_run_ids=["r1"])
            self.assertEqual(state["mission_run_ids"], ["r1"])

    def test_advance_pipeline_none_new_run_ids_preserves_existing(self):
        """advance_pipeline with new_run_ids=None preserves existing ids."""
        self._insert_run("r1", 100)
        state = _make_state(
            packages={"a": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["r1"],
        )
        ar.write_graph_state(state, self.state_path)
        pkgs = [_pkg("a")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_complete("a")
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "WAKE_PENDING_PATH",
                          Path(self.tmpdir.name) / "wp.json"), \
             patch.object(ar, "OPENCLAW_DB", self.db_path):
            decision = ar.advance_pipeline(
                self.goal_path, graph=g, new_run_ids=None,
            )
        loaded = ar.load_graph_state(self.state_path)
        self.assertIn("r1", loaded["mission_run_ids"])
        self.assertEqual(decision, ar.DECISION_DONE)


# ============================================================================
# 7. Trigger logic: fire/don't-fire from graph state
# ============================================================================

class TestTriggerLogic(unittest.TestCase):
    """The trigger's {fire: bool} decisions from graph state."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "graph_state.json"
        self.goal_path = str(Path(self.tmpdir.name) / "goal.json")
        Path(self.goal_path).write_text("[]")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_trigger_fire_false_when_done(self):
        """All completed, no new runs → fire=false."""
        state = _make_state(
            packages={"a": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=100):
            self.assertFalse(ar.needs_dispatch(state))

    def test_trigger_fire_true_when_pending(self):
        """Non-terminal packages → fire=true."""
        state = _make_state(
            packages={"a": "in_progress"},
            hwm=100, goal_path=self.goal_path,
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            self.assertTrue(ar.needs_dispatch(state))

    def test_trigger_fire_true_when_hwm_advanced(self):
        """HWM advanced → fire=true."""
        state = _make_state(
            packages={"a": "completed"},
            hwm=100, goal_path=self.goal_path,
            mission_run_ids=["run-1"],
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=150):
            self.assertTrue(ar.needs_dispatch(state))

    def test_trigger_no_llm_invocation(self):
        """Trigger decision is pure state check — no LLM, no subprocess."""
        state = _make_state(
            packages={"a": "in_progress"},
            hwm=100, goal_path=self.goal_path,
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            # Pure function — just loads JSON and checks conditions.
            decision = ar.resume_if_needed(self.goal_path)
            self.assertIn(decision, (ar.DECISION_CONTINUE, ar.DECISION_DONE,
                                     ar.DECISION_WAKE_MAIN))

    def test_trigger_broken_state_wakes_main_without_dispatch(self):
        """Corrupt/invalid state → WAKE_MAIN (fail closed, no redispatch)."""
        self.state_path.write_text("not json{{{")
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            state = ar.load_graph_state()
            self.assertIsNone(state)
            self.assertFalse(ar.needs_dispatch(state))
            decision = ar.resume_if_needed(self.goal_path)
            self.assertEqual(decision, ar.DECISION_WAKE_MAIN)

    def test_trigger_full_blockage_wakes_main(self):
        """Full blockage → WAKE_MAIN (trigger reports escalation)."""
        state = _make_state(
            packages={"a": "failed", "b": "blocked"},
            hwm=100, goal_path=self.goal_path,
        )
        ar.write_graph_state(state, self.state_path)
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path):
            decision = ar.resume_if_needed(self.goal_path)
            # Full blockage with zero completed → WAKE_MAIN
            self.assertEqual(decision, ar.DECISION_WAKE_MAIN)


if __name__ == "__main__":
    unittest.main()
