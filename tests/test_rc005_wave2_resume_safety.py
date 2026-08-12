from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from unittest.mock import patch
from core.auto_resume import DECISION_CONTINUE, DECISION_DONE, DECISION_WAKE_MAIN, needs_dispatch, resume_if_needed
from core.dependency_graph import DependencyGraph
from core.dispatcher import Dispatcher, ExecutionResult, WORKER_SIMULATED, mark_executor
from core.fencing import brief_hash, check_dispatch_fence
from core.graph_state_store import GRAPH_STATE_V2, GraphStateStore, normalize_graph_state
from core.session_lifecycle import SessionLifecycleStore
from core.reliability_config import ReliabilityConfig
from core.workforce_resolver import Employee, WorkPackage, WorkforceResolver
from db.migrate import apply_all
from tests.test_workforce_resolver import real_employees, resolver_all_available


def pkg(pid="p", *, family="implementation"):
    return WorkPackage(pid, "  same   normalized brief ", ["code"], task_family=family,
                       project="lisa", sprint="rc005", employee="sol", role="worker")


def workforce():
    employee = Employee("sol", "eng", "senior", ["code"], "codex", "codex", [],
                        "subscription", "high", "fail")
    return WorkforceResolver({"sol": employee})


def executor(counter):
    def run(_pkg, _assignment):
        counter.append(_pkg.id)
        return ExecutionResult(True, actual_runtime="sim", run_id=f"run-{_pkg.id}")
    return mark_executor(run, WORKER_SIMULATED)


class TestWave2GraphState(unittest.TestCase):
    def test_authoritative_failed_below_cap_retries_and_at_cap_escalates(self):
        base = {"schema": GRAPH_STATE_V2, "goal_path": "/tmp/g",
                "last_dispatch_at": datetime.now(timezone.utc).isoformat()}
        below = normalize_graph_state({**base, "packages": {"p": {"status": "failed", "retry_count": 0}}})
        capped = normalize_graph_state({**base, "packages": {"p": {"status": "failed", "retry_count": 1}}})
        from core.auto_resume import decide_action
        self.assertEqual(decide_action(below), DECISION_CONTINUE)
        self.assertEqual(decide_action(capped), DECISION_WAKE_MAIN)

    def test_t7_restart_skips_completed_and_maps_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = normalize_graph_state({
                "schema": GRAPH_STATE_V2, "mission_id": "m1", "goal_path": "/tmp/g.json",
                "last_dispatch_at": datetime.now(timezone.utc).isoformat(),
                "packages": {"p": {"status": "completed", "run_ids": ["r1"]}},
            })
            GraphStateStore(path).write_atomic(state)
            calls = []
            report = Dispatcher(workforce(), executor=executor(calls), graph_state_path=str(path),
                                mission_id="m1").run(DependencyGraph.from_packages([pkg()]))
            loaded = GraphStateStore(path).load_v2().state
        self.assertEqual(calls, [])
        self.assertEqual(report.graph_summary["completed"], 1)
        self.assertEqual(loaded["run_id_to_package"]["r1"], "p")

    def test_t8_stale_state_wakes_and_package_hwm_ignores_unrelated_global_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            goal = Path(tmp) / "goal.json"
            goal.write_text("[]", encoding="utf-8")
            old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            state = normalize_graph_state({
                "schema": GRAPH_STATE_V2, "mission_id": __import__("core.graph_state_store", fromlist=["mission_id_for_goal"]).mission_id_for_goal(goal),
                "goal_path": str(goal), "last_dispatch_at": old,
                "packages": {"p": {"status": "completed", "last_event_ms": 10, "run_ids": []}},
            })
            GraphStateStore(path).write_atomic(state)
            decision = resume_if_needed(str(goal), graph_state_path=path, enforce_staleness=True)
        self.assertEqual(decision, DECISION_WAKE_MAIN)

    def test_package_hwm_is_not_global(self):
        state = normalize_graph_state({"schema": GRAPH_STATE_V2, "goal_path": "/tmp/g",
            "last_dispatch_at": datetime.now(timezone.utc).isoformat(),
            "packages": {"p": {"status": "completed", "last_event_ms": 100, "run_ids": []}}})
        self.assertFalse(needs_dispatch(state))

    def test_package_hwm_ignores_seeded_unrelated_global_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE task_runs (run_id TEXT, created_at INTEGER)")
            conn.execute("INSERT INTO task_runs VALUES ('unrelated', 999999)")
            conn.commit(); conn.close()
            state = normalize_graph_state({"schema": GRAPH_STATE_V2, "goal_path": "/tmp/g",
                "packages": {"p": {"status": "completed", "run_ids": ["mine"], "last_event_ms": 10}}})
            with patch("core.auto_resume.OPENCLAW_DB", db):
                self.assertFalse(needs_dispatch(state))

    def test_t18_v1_stale_is_normalized_and_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            goal = Path(tmp) / "goal.json"; goal.write_text("[]", encoding="utf-8")
            path.write_text(json.dumps({"schema": "lisa-graph-state/1", "goal_path": str(goal),
                "mission_id": __import__("core.graph_state_store", fromlist=["mission_id_for_goal"]).mission_id_for_goal(goal),
                "last_dispatch_at": "2026-08-09T00:00:00+00:00", "packages": {"p": "completed"}}))
            decision = resume_if_needed(str(goal), graph_state_path=path, enforce_staleness=True)
            loaded = json.loads(path.read_text())
        self.assertEqual(decision, DECISION_WAKE_MAIN)
        self.assertEqual(loaded["schema"], GRAPH_STATE_V2)
        self.assertEqual(loaded["stale_reason"], "stale_last_dispatch_at")


class TestWave2Fencing(unittest.TestCase):
    def test_log_only_records_but_allows_and_enforce_denies(self):
        digest = brief_hash("same normalized brief")
        record = {"status": "in_progress", "dispatch_state": "ACKNOWLEDGED",
                  "brief_hash": digest, "task_family": "implementation",
                  "session_key": "s"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            GraphStateStore(path).write_atomic({"schema": GRAPH_STATE_V2, "mission_id": "m",
                                                "packages": {"p": record}})
            dispatch = Dispatcher(workforce(), executor=executor([]), graph_state_path=str(path), mission_id="m")
            item = pkg(); setattr(item, "_rc005_session_key", "s")
            log_cfg = ReliabilityConfig({"reconciliation": {"auto_retry_max": 1},
                                         "fencing": {"enabled": True, "mode": "log_only"}})
            with patch("core.dispatcher.load_reliability_config", return_value=log_cfg):
                allowed, reason = dispatch._dispatch_allowed_by_reconciliation(item)
            self.assertTrue(allowed); self.assertTrue(reason.startswith("log_only:"))
            self.assertEqual(GraphStateStore(path).load_v2().state["packages"]["p"]["fence_events"][-1]["mode"], "log_only")
            GraphStateStore(path).write_atomic({"schema": GRAPH_STATE_V2, "mission_id": "m",
                                                "packages": {"p": record}})
            enforce_cfg = ReliabilityConfig({"reconciliation": {"auto_retry_max": 1},
                                             "fencing": {"enabled": True, "mode": "enforce"}})
            with patch("core.dispatcher.load_reliability_config", return_value=enforce_cfg):
                allowed, _ = dispatch._dispatch_allowed_by_reconciliation(item)
            self.assertFalse(allowed)

    def test_two_store_instances_mutually_exclude_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"; GraphStateStore(path).write_atomic({"count": 0})
            def increment(store):
                for _ in range(20):
                    store.mutate_locked(lambda loaded: {"count": loaded.state.get("count", 0) + 1})
            threads = [threading.Thread(target=increment, args=(GraphStateStore(path),)) for _ in range(2)]
            [t.start() for t in threads]; [t.join() for t in threads]
            self.assertEqual(GraphStateStore(path).load().state["count"], 40)

    def test_enforced_denial_preserves_reconciliation_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            item = pkg(); setattr(item, "_rc005_session_key", "s")
            item.required_capabilities = ["architecture"]
            digest = brief_hash(item.description)
            prior = {"status": "in_progress", "dispatch_state": "ACKNOWLEDGED",
                     "brief_hash": digest, "task_family": item.task_family,
                     "session_key": "s", "fencing_key": "fence-old",
                     "run_id": "run-old", "run_ids": ["run-old"]}
            GraphStateStore(path).write_atomic({"schema": GRAPH_STATE_V2, "mission_id": "m",
                                                "packages": {"p": prior}})
            cfg = ReliabilityConfig({"reconciliation": {"auto_retry_max": 1},
                                     "fencing": {"enabled": True, "mode": "enforce"}})
            with patch("core.dispatcher.load_reliability_config", return_value=cfg):
                proper_workforce = WorkforceResolver(real_employees(), resolver_all_available())
                Dispatcher(proper_workforce, executor=executor([]), graph_state_path=str(path),
                           mission_id="m").run(DependencyGraph.from_packages([item]))
            record = GraphStateStore(path).load_v2().state["packages"]["p"]
        self.assertEqual(record["status"], "execution_unknown")
        self.assertEqual(record["run_ids"], ["run-old"])
        self.assertEqual(record["session_key"], "s")
        self.assertEqual(record["fencing_key"], "fence-old")
        self.assertTrue(record["requires_reconciliation"])

    def test_hash_is_normalized_and_stable(self):
        self.assertEqual(brief_hash("a  b\n c"), brief_hash("a b c"))

    def test_t10_duplicate_same_session_denied_and_retry_fresh_allowed(self):
        digest = brief_hash("brief")
        record = {"status": "in_progress", "dispatch_state": "ACKNOWLEDGED",
                  "brief_hash": digest, "task_family": "impl", "session_key": "s1"}
        denied = check_dispatch_fence(record=record, goal="g", package_id="p",
            task_family="impl", session_key="s1", brief_digest=digest)
        allowed = check_dispatch_fence(record=record, goal="g", package_id="p",
            task_family="impl", session_key="s2", brief_digest=digest,
            reconciliation={"decision": "RETRY", "evidence": {"verified_dead": True}})
        self.assertFalse(denied.allowed)
        self.assertTrue(allowed.allowed)

    def test_resume_holds_acknowledged_nonterminal_before_continue(self):
        state = normalize_graph_state({"schema": GRAPH_STATE_V2, "goal_path": "/tmp/g",
            "last_dispatch_at": datetime.now(timezone.utc).isoformat(), "packages": {
                "p": {"status": "in_progress", "dispatch_state": "ACKNOWLEDGED",
                      "brief_hash": brief_hash("x"), "task_family": "impl", "session_key": "s"}}})
        self.assertFalse(needs_dispatch(state))


class TestWave2SessionLifecycle(unittest.TestCase):
    def test_unprefixed_graph_key_resolves_canonical_bridge_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE session_lifecycle (session_key TEXT PRIMARY KEY, session_state TEXT, last_seen_at TEXT)")
            conn.execute("INSERT INTO session_lifecycle VALUES (?, ?, ?)",
                         ("agent:lisa-codex:lisa-session-suffix", "ACTIVE", "2026-08-12"))
            conn.commit(); conn.close()
            with patch("core.auto_resume.OPENCLAW_DB", db):
                from core.auto_resume import _fetch_session_lifecycle
                row = _fetch_session_lifecycle("suffix")
        self.assertEqual(row["session_key"], "agent:lisa-codex:lisa-session-suffix")

    def test_backup_first_migrations_and_accessor_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT)")
            conn.commit(); conn.close()
            backup = apply_all(db, backup=True)
            backup_exists = bool(backup and backup.is_file())
            apply_all(db, backup=False)
            store = SessionLifecycleStore(db)
            store.upsert("s1", agent_id="a", session_state="ACTIVE")
            row = store.update_telemetry("s1", cache_read=50, context_window=100)
            throttled = store.mark_throttled("s1", throttle_until="later")
        self.assertTrue(backup_exists)
        self.assertEqual(row["context_pct"], 0.5)
        self.assertEqual(throttled["session_state"], "THROTTLED")


if __name__ == "__main__":
    unittest.main()
