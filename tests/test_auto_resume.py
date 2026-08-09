"""Tests for core/auto_resume.py — deterministic pipeline advancement.

Validates: needs_dispatch true/false, needs_escalation critical/non-critical,
exactly-once high-water-mark behavior, duplicate tick no-op, graph state
round-trip, and DependencyGraph.from_state() reconstruction.

All tests are hermetic: no real OpenClaw DB access, no subprocess calls,
no network, no spend.
"""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.dependency_graph import DependencyGraph, GraphError
from core.workforce_resolver import WorkPackage
import core.auto_resume as ar


# -- helpers -------------------------------------------------------------

def _make_state(packages=None, hwm=0, escalation_pending=False, mission_run_ids=None):
    return {
        "schema": "lisa-graph-state/1",
        "goal_path": "/tmp/test_goal.json",
        "packages": packages or {},
        "high_water_mark_ms": hwm,
        "last_dispatch_at": "2026-08-09T22:00:00+00:00",
        "escalation_pending": escalation_pending,
        "mission_run_ids": mission_run_ids or [],
    }


def _pkg(id, deps=None, risk="normal"):
    return WorkPackage(
        id=id, description=f"package {id}",
        required_capabilities=["code"],
        risk=risk, depends_on=list(deps or []),
    )


class TestNeedsDispatch(unittest.TestCase):
    """needs_dispatch() — signals when work remains or new runs exist."""

    def test_none_state_returns_false(self):
        self.assertFalse(ar.needs_dispatch(None))

    def test_empty_packages_returns_false(self):
        self.assertFalse(ar.needs_dispatch(_make_state(packages={})))

    def test_in_progress_package_returns_true(self):
        state = _make_state(packages={"a": "in_progress"})
        self.assertTrue(ar.needs_dispatch(state))

    def test_all_terminal_no_new_runs_returns_false(self):
        state = _make_state(packages={"a": "completed", "b": "failed"})
        with patch.object(ar, "_compute_high_water_mark", return_value=0):
            self.assertFalse(ar.needs_dispatch(state))

    def test_new_task_runs_since_watermark_returns_true(self):
        state = _make_state(packages={"a": "completed"}, hwm=100,
                            mission_run_ids=["run-1"])
        with patch.object(ar, "_compute_high_water_mark", return_value=200):
            self.assertTrue(ar.needs_dispatch(state))

    def test_wake_pending_marker_returns_true(self, tmp_path=None):
        state = _make_state(packages={"a": "completed"}, hwm=100)
        with patch.object(ar, "_compute_high_water_mark", return_value=100):
            with patch.object(ar, "WAKE_PENDING_PATH",
                              Path(tempfile.mkstemp(suffix=".json")[1])):
                ar.WAKE_PENDING_PATH.write_text('{"at":"now"}')
                try:
                    self.assertTrue(ar.needs_dispatch(state))
                finally:
                    ar.WAKE_PENDING_PATH.unlink(missing_ok=True)


class TestNeedsEscalation(unittest.TestCase):
    """needs_escalation() — wakes MAIN only for critical/hard failures."""

    def test_none_state_returns_false(self):
        self.assertFalse(ar.needs_escalation(None))

    def test_no_failures_returns_false(self):
        state = _make_state(packages={"a": "completed", "b": "completed"})
        self.assertFalse(ar.needs_escalation(state))

    def test_non_critical_failure_no_meta_returns_false(self):
        state = _make_state(packages={"a": "failed"})
        self.assertFalse(ar.needs_escalation(state))

    def test_critical_failure_returns_true(self):
        state = _make_state(packages={"a": "failed"})
        meta = {"a": {"risk": "critical"}}
        self.assertTrue(ar.needs_escalation(state, meta))

    def test_non_critical_failure_stays_silent(self):
        state = _make_state(packages={"a": "failed"})
        meta = {"a": {"risk": "normal"}}
        self.assertFalse(ar.needs_escalation(state))

    def test_retry_exhaustion_returns_true(self):
        state = _make_state(packages={"a": "failed"})
        meta = {"a": {"risk": "normal", "retries": 3, "max_retries": 3}}
        self.assertTrue(ar.needs_escalation(state, meta))

    def test_retry_not_exhausted_stays_silent(self):
        # non-critical, retries remaining, another completed = no escalation
        state = _make_state(packages={"a": "failed", "b": "completed"})
        meta = {"a": {"risk": "normal", "retries": 2, "max_retries": 3}}
        self.assertFalse(ar.needs_escalation(state, meta))

    def test_full_blockage_zero_completed_returns_true(self):
        # a failed, b blocked (depends on a) — cascading dependency failure
        state = _make_state(packages={"a": "failed", "b": "blocked"})
        self.assertTrue(ar.needs_escalation(state))

    def test_full_blockage_with_completed_returns_false(self):
        # one completed means progress was made — not full blockage
        state = _make_state(packages={"a": "completed", "b": "blocked"})
        self.assertFalse(ar.needs_escalation(state))


class TestDecideAction(unittest.TestCase):
    """decide_action() — returns the correct decision enum."""

    def test_none_state_returns_done(self):
        self.assertEqual(ar.decide_action(None), ar.DECISION_DONE)

    def test_all_green_returns_done(self):
        state = _make_state(packages={"a": "completed", "b": "completed"}, hwm=100,
                            mission_run_ids=["run-1"])
        with patch.object(ar, "_compute_high_water_mark", return_value=100):
            self.assertEqual(ar.decide_action(state), ar.DECISION_DONE)

    def test_critical_failure_returns_wake_main(self):
        state = _make_state(packages={"a": "failed"})
        meta = {"a": {"risk": "critical"}}
        self.assertEqual(ar.decide_action(state, meta), ar.DECISION_WAKE_MAIN)

    def test_pending_work_returns_continue(self):
        state = _make_state(packages={"a": "in_progress", "b": "completed"})
        self.assertEqual(ar.decide_action(state), ar.DECISION_CONTINUE)


class TestExactlyOnce(unittest.TestCase):
    """High-water-mark prevents double-processing of the same runs."""

    def test_same_watermark_no_new_runs_skips(self):
        """If hwm hasn't advanced and all packages are terminal, skip."""
        state = _make_state(packages={"a": "completed"}, hwm=500)
        with patch.object(ar, "_compute_high_water_mark", return_value=500):
            self.assertFalse(ar.needs_dispatch(state))

    def test_duplicate_tick_noop(self):
        """Two ticks with identical state produce identical decisions."""
        state = _make_state(packages={"a": "completed"}, hwm=500)
        with patch.object(ar, "_compute_high_water_mark", return_value=500):
            d1 = ar.decide_action(state)
            d2 = ar.decide_action(state)
            self.assertEqual(d1, d2)
            self.assertEqual(d1, ar.DECISION_DONE)

    def test_new_run_advances_watermark_triggers_dispatch(self):
        """A task_run created after the watermark triggers re-dispatch."""
        state = _make_state(packages={"a": "completed"}, hwm=100,
                            mission_run_ids=["run-1"])
        with patch.object(ar, "_compute_high_water_mark", return_value=150):
            self.assertTrue(ar.needs_dispatch(state))


class TestGraphStateRoundTrip(unittest.TestCase):
    """DependencyGraph.from_state() + build_graph_state() round-trip."""

    def test_round_trip_completed_and_failed(self):
        pkgs = [_pkg("a"), _pkg("b", deps=["a"]), _pkg("c")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_complete("a")
        g.mark_complete("b")
        g.mark_failed("c")
        state = ar.build_graph_state(g, "/tmp/goal.json")
        self.assertEqual(state["packages"]["a"], "completed")
        self.assertEqual(state["packages"]["b"], "completed")
        self.assertEqual(state["packages"]["c"], "failed")

    def test_from_state_reconstructs_terminal(self):
        pkgs = [_pkg("a"), _pkg("b", deps=["a"]), _pkg("c")]
        state = _make_state(packages={"a": "completed", "b": "failed"})
        g2 = DependencyGraph.from_state(pkgs, state)
        self.assertIn("a", g2.completed)
        self.assertIn("b", g2.failed)
        # c was not in state — it remains pending
        self.assertNotIn("c", g2.completed)
        self.assertNotIn("c", g2.failed)

    def test_from_state_ignores_unknown_ids(self):
        pkgs = [_pkg("a")]
        state = _make_state(packages={"a": "completed", "z": "completed"})
        g = DependencyGraph.from_state(pkgs, state)
        self.assertIn("a", g.completed)
        # z silently ignored (state outlives goal)

    def test_from_state_timed_out_maps_to_failed(self):
        pkgs = [_pkg("a")]
        state = _make_state(packages={"a": "timed_out"})
        g = DependencyGraph.from_state(pkgs, state)
        self.assertIn("a", g.failed)

    def test_from_state_blocked_is_computed_not_stored(self):
        pkgs = [_pkg("a"), _pkg("b", deps=["a"])]
        # a failed, b should be computed as blocked
        state = _make_state(packages={"a": "failed", "b": "blocked"})
        g = DependencyGraph.from_state(pkgs, state)
        self.assertIn("a", g.failed)
        # blocked is NOT explicitly stored — from_state only sets
        # completed/failed; blocked is derived transitively by ready_frontier
        blocked = g.blocked()
        self.assertIn("b", blocked)

    def test_ready_frontier_respects_reconstructed_state(self):
        pkgs = [_pkg("a"), _pkg("b", deps=["a"]), _pkg("c")]
        state = _make_state(packages={"a": "completed"})
        g = DependencyGraph.from_state(pkgs, state)
        frontier = g.ready_frontier()
        frontier_ids = {p.id for p in frontier}
        self.assertIn("b", frontier_ids)  # a done, b ready
        self.assertIn("c", frontier_ids)  # no deps, always ready


class TestGraphStateIO(unittest.TestCase):
    """Atomic write + load round-trip."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "graph_state.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_write_and_load_round_trip(self):
        state = _make_state(packages={"a": "completed", "b": "failed"})
        ar.write_graph_state(state, self.state_path)
        loaded = ar.load_graph_state(self.state_path)
        self.assertEqual(loaded["packages"], state["packages"])
        self.assertEqual(loaded["schema"], state["schema"])

    def test_load_nonexistent_returns_none(self):
        path = Path(self.tmpdir.name) / "nonexistent.json"
        self.assertIsNone(ar.load_graph_state(path))

    def test_load_corrupt_json_returns_none(self):
        self.state_path.write_text("not json{{{")
        self.assertIsNone(ar.load_graph_state(self.state_path))

    def test_atomic_write_no_partial_reads(self):
        """verify .tmp file is renamed, not directly written."""
        state = _make_state(packages={"a": "completed"})
        ar.write_graph_state(state, self.state_path)
        # State file exists, tmp file should not
        self.assertTrue(self.state_path.is_file())
        self.assertFalse(self.state_path.with_suffix(".json.tmp").is_file())


class TestAdvancePipeline(unittest.TestCase):
    """advance_pipeline() — end-to-end post-dispatch flow."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.real_state_path = ar.GRAPH_STATE_PATH
        self.real_wake_path = ar.WAKE_PENDING_PATH
        self.state_path = Path(self.tmpdir.name) / "graph_state.json"
        self.wake_path = Path(self.tmpdir.name) / "wake_pending.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    @patch.object(ar, "GRAPH_STATE_PATH", None)
    @patch.object(ar, "WAKE_PENDING_PATH", None)
    def test_all_completed_returns_done(self):
        pkgs = [_pkg("a"), _pkg("b")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_complete("a")
        g.mark_complete("b")
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "WAKE_PENDING_PATH", self.wake_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=0):
            decision = ar.advance_pipeline("/t/goal.json", graph=g)
            self.assertEqual(decision, ar.DECISION_DONE)
            self.assertTrue(self.state_path.is_file())

    @patch.object(ar, "GRAPH_STATE_PATH", None)
    @patch.object(ar, "WAKE_PENDING_PATH", None)
    def test_in_progress_returns_continue(self):
        pkgs = [_pkg("a")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_in_progress("a")
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "WAKE_PENDING_PATH", self.wake_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=0):
            decision = ar.advance_pipeline("/t/goal.json", graph=g)
            self.assertEqual(decision, ar.DECISION_CONTINUE)

    @patch.object(ar, "GRAPH_STATE_PATH", None)
    @patch.object(ar, "WAKE_PENDING_PATH", None)
    def test_critical_failure_wakes_main(self):
        pkgs = [_pkg("a", risk="critical")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_failed("a")
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "WAKE_PENDING_PATH", self.wake_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=0), \
             patch.object(ar, "_send_system_event", return_value=True):
            decision = ar.advance_pipeline(
                "/t/goal.json", graph=g,
                packages_meta={"a": {"risk": "critical"}},
            )
            self.assertEqual(decision, ar.DECISION_WAKE_MAIN)
            loaded = ar.load_graph_state(self.state_path)
            self.assertFalse(loaded["escalation_pending"])

    @patch.object(ar, "GRAPH_STATE_PATH", None)
    @patch.object(ar, "WAKE_PENDING_PATH", None)
    def test_system_event_unreachable_writes_wake_pending(self):
        pkgs = [_pkg("a", risk="critical")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_failed("a")
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "WAKE_PENDING_PATH", self.wake_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=0), \
             patch.object(ar, "_send_system_event", return_value=False):
            decision = ar.advance_pipeline(
                "/t/goal.json", graph=g,
                packages_meta={"a": {"risk": "critical"}},
            )
            self.assertEqual(decision, ar.DECISION_WAKE_MAIN)
            self.assertTrue(self.wake_path.is_file())
            loaded = ar.load_graph_state(self.state_path)
            self.assertTrue(loaded["escalation_pending"])

    @patch.object(ar, "GRAPH_STATE_PATH", None)
    @patch.object(ar, "WAKE_PENDING_PATH", None)
    def test_max_cycles_guard(self):
        pkgs = [_pkg("a")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_in_progress("a")
        with patch.object(ar, "GRAPH_STATE_PATH", self.state_path), \
             patch.object(ar, "WAKE_PENDING_PATH", self.wake_path), \
             patch.object(ar, "_compute_high_water_mark", return_value=0), \
             patch.object(ar, "decide_action", return_value=ar.DECISION_CONTINUE):
            decision = ar.advance_pipeline("/t/goal.json", graph=g, max_cycles=3)
            # Since decide_action always returns CONTINUE, loop hits max_cycles
            self.assertEqual(decision, ar.DECISION_CONTINUE)


class TestBuildGraphState(unittest.TestCase):
    """build_graph_state() — constructs state dict from a DependencyGraph."""

    def test_includes_all_terminal_statuses(self):
        pkgs = [_pkg("a"), _pkg("b", deps=["a"]), _pkg("c")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_complete("a")
        g.mark_failed("c")
        state = ar.build_graph_state(g, "/tmp/g.json")
        self.assertEqual(state["packages"]["a"], "completed")
        self.assertEqual(state["packages"]["c"], "failed")
        # b is ready (dep a completed), not blocked
        self.assertNotIn("b", state["packages"])
        # completed+failed cover the terminal entries

    def test_in_progress_included(self):
        pkgs = [_pkg("a")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_in_progress("a")
        state = ar.build_graph_state(g, "/tmp/g.json")
        self.assertEqual(state["packages"]["a"], "in_progress")

    def test_schema_and_goal_path_present(self):
        g = DependencyGraph.from_packages([_pkg("a")])
        state = ar.build_graph_state(g, "/tmp/goal.json")
        self.assertEqual(state["schema"], "lisa-graph-state/1")
        self.assertEqual(state["goal_path"], "/tmp/goal.json")


class TestMissionScopedHWM(unittest.TestCase):
    """HWM scoped to mission_run_ids — unrelated activity ignored."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test_openclaw.sqlite"
        self._init_db()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS task_runs ("
            "  run_id TEXT PRIMARY KEY,"
            "  created_at INTEGER,"
            "  status TEXT,"
            "  ended_at INTEGER"
            ")"
        )
        conn.commit()
        conn.close()

    def _insert_run(self, run_id: str, created_at_ms: int,
                    status: str = "completed") -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT OR REPLACE INTO task_runs(run_id, created_at, status)"
            " VALUES (?, ?, ?)",
            (run_id, created_at_ms, status),
        )
        conn.commit()
        conn.close()

    def _patch_db(self):
        """Context manager to monkeypatch OPENCLAW_DB."""
        return patch.object(ar, "OPENCLAW_DB", self.db_path)

    # -- regression tests -------------------------------------------------

    def test_mission_a_done_unrelated_b_does_not_trigger_dispatch(self):
        """(a)(b)(c)(d) Mission A complete; unrelated B runs → A stays DONE."""
        self._insert_run("run-a1", 100, "completed")
        state = _make_state(
            packages={"a": "completed"},
            hwm=100,
            mission_run_ids=["run-a1"],
        )
        # Unrelated Mission B inserts a new run
        self._insert_run("run-b1", 9999, "completed")

        with self._patch_db():
            self.assertFalse(ar.needs_dispatch(state))
            self.assertEqual(ar.decide_action(state), ar.DECISION_DONE)

    def test_unrelated_activity_no_mission_ids_no_spurious_dispatch(self):
        """(b)(c) mission_run_ids empty + unrelated runs = still DONE."""
        self._insert_run("run-x", 500, "completed")
        state = _make_state(
            packages={"a": "completed"},
            hwm=0,
            mission_run_ids=[],
        )
        with self._patch_db():
            self.assertFalse(ar.needs_dispatch(state))
            self.assertEqual(ar.decide_action(state), ar.DECISION_DONE)

    def test_mission_own_new_run_advances_hwm_correctly(self):
        """(f) New run in mission's own set advances HWM → CONTINUE."""
        self._insert_run("run-a1", 100, "completed")
        self._insert_run("run-a2", 200, "completed")
        state = _make_state(
            packages={"a": "completed"},
            hwm=100,
            mission_run_ids=["run-a1", "run-a2"],
        )
        with self._patch_db():
            self.assertTrue(ar.needs_dispatch(state))

    def test_empty_mission_run_ids_returns_hwm_zero(self):
        """Empty mission_run_ids → HWM=0, no spurious advancement."""
        self._insert_run("run-x", 9999, "completed")
        with self._patch_db():
            hwm = ar._compute_high_water_mark(set())
            self.assertEqual(hwm, 0)

    def test_none_run_ids_still_unscoped_backward_compat(self):
        """None run_ids = all task_runs (backward compat)."""
        self._insert_run("run-x", 777, "completed")
        with self._patch_db():
            hwm = ar._compute_high_water_mark(None)
            self.assertEqual(hwm, 777)

    def test_scoped_set_only_sees_own_runs(self):
        """Scoped query only sees the given run_ids."""
        self._insert_run("run-a", 100, "completed")
        self._insert_run("run-b", 200, "completed")
        self._insert_run("run-c", 300, "completed")
        with self._patch_db():
            hwm = ar._compute_high_water_mark({"run-a", "run-c"})
            self.assertEqual(hwm, 300)  # max of (100, 300)

    def test_build_graph_state_includes_mission_run_ids(self):
        """build_graph_state stores mission_run_ids in output."""
        g = DependencyGraph.from_packages([_pkg("a")])
        g.mark_complete("a")
        state = ar.build_graph_state(g, "/tmp/g.json",
                                     mission_run_ids=["r1", "r2"])
        self.assertEqual(state["mission_run_ids"], ["r1", "r2"])

    def test_build_graph_state_none_mission_ids_empty_list(self):
        """build_graph_state with None → empty mission_run_ids."""
        g = DependencyGraph.from_packages([_pkg("a")])
        state = ar.build_graph_state(g, "/tmp/g.json")
        self.assertEqual(state["mission_run_ids"], [])

    def test_advance_pipeline_merges_new_run_ids(self):
        """advance_pipeline merges new_run_ids into mission_run_ids."""
        state_path = Path(self.tmpdir.name) / "gs.json"
        wake_path = Path(self.tmpdir.name) / "wp.json"
        pkgs = [_pkg("a")]
        g = DependencyGraph.from_packages(pkgs)
        g.mark_complete("a")

        # Simulate state from first dispatch
        self._insert_run("run-a1", 100, "completed")
        state = ar.build_graph_state(g, "/t/g.json", mission_run_ids=["run-a1"])
        ar.write_graph_state(state, state_path)

        # Second dispatch — new run, existing state has run-a1
        self._insert_run("run-a2", 200, "completed")
        g2 = DependencyGraph.from_packages(pkgs)
        g2.mark_complete("a")
        with patch.object(ar, "GRAPH_STATE_PATH", state_path), \
             patch.object(ar, "WAKE_PENDING_PATH", wake_path), \
             patch.object(ar, "OPENCLAW_DB", self.db_path):
            decision = ar.advance_pipeline(
                "/t/g.json", graph=g2, new_run_ids=["run-a2"],
            )
        loaded = ar.load_graph_state(state_path)
        self.assertIn("run-a1", loaded["mission_run_ids"])
        self.assertIn("run-a2", loaded["mission_run_ids"])
        self.assertEqual(loaded["high_water_mark_ms"], 200)
        self.assertEqual(decision, ar.DECISION_DONE)


if __name__ == "__main__":
    unittest.main()
