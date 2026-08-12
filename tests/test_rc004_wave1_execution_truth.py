"""RC004 Wave 1 adversarial tests.

Hermetic coverage for RC003 Gate 1 subset: T1-T5, T9, T13, T14.
No real OpenClaw spawn, no network, no live DB mutation.
"""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.dependency_graph import DependencyGraph
from core.dispatcher import (
    Dispatcher,
    ExecutionResult,
    WORKER_SIMULATED,
    mark_executor,
)
from core.execution_state import (
    COMMAND_FAILED,
    COMMAND_TIMED_OUT,
    DISPATCH_ACKNOWLEDGED,
    EXEC_COMPLETED,
    EXEC_FAILED,
    EXEC_UNKNOWN,
    RESULT_UNKNOWN,
    SESSION_UNKNOWN,
    classify_execution_source,
)
from core.graph_state_store import GraphStateStore, mission_id_for_goal
from core.reconciliation import (
    RECONCILE_ESCALATE,
    RECONCILE_RESUME,
    RECONCILE_RETRY,
    ReconciliationEvidence,
    decide_reconciliation,
)
from core.reliability_config import ReliabilityConfig
from core.workforce_resolver import WorkPackage, WorkforceResolver
from db.migrate_reliability import apply_migration
from tests.test_workforce_resolver import real_employees, resolver_all_available


def _wf() -> WorkforceResolver:
    return WorkforceResolver(real_employees(), resolver_all_available())


def _pkg(pid: str = "p") -> WorkPackage:
    return WorkPackage(id=pid, description="x", required_capabilities=["microtask"])


class TestA1UnknownClassification(unittest.TestCase):
    def test_t1_timeout_after_worker_start_maps_unknown_not_failed(self):
        self.assertEqual(
            classify_execution_source("fail-closed-subprocess-error"),
            EXEC_UNKNOWN,
        )

    def test_t2_lost_ack_bad_json_maps_unknown(self):
        self.assertEqual(
            classify_execution_source("fail-closed-bad-json-response"),
            EXEC_UNKNOWN,
        )

    def test_t3_pre_dispatch_failure_is_authoritative_failed(self):
        self.assertEqual(
            classify_execution_source("fail-closed-gateway-unreachable"),
            EXEC_FAILED,
        )


class TestB1ReconciliationGate(unittest.TestCase):
    def test_t9_unknown_cannot_retry_without_verified_death(self):
        decision = decide_reconciliation(ReconciliationEvidence(
            package_id="p",
            execution_state=EXEC_UNKNOWN,
            session_live=None,
            task_run_live=None,
            artifact_present=None,
        ))
        self.assertEqual(decision.decision, RECONCILE_ESCALATE)

    def test_t13_liveness_ambiguity_escalates(self):
        decision = decide_reconciliation(ReconciliationEvidence(
            package_id="p",
            execution_state=EXEC_UNKNOWN,
            session_live=None,
            task_run_live=False,
            artifact_present=False,
            verified_dead=None,
        ))
        self.assertEqual(decision.decision, RECONCILE_ESCALATE)

    def test_live_or_completed_unknown_resumes_not_retries(self):
        live = decide_reconciliation(ReconciliationEvidence(
            package_id="p",
            execution_state=EXEC_UNKNOWN,
            task_run_live=True,
        ))
        self.assertEqual(live.decision, RECONCILE_RESUME)

        complete = decide_reconciliation(ReconciliationEvidence(
            package_id="p",
            execution_state=EXEC_UNKNOWN,
            task_run_completed=True,
            artifact_present=True,
        ))
        self.assertEqual(complete.decision, RECONCILE_RESUME)

    def test_retry_requires_verified_death_and_budget(self):
        cfg = ReliabilityConfig({"reconciliation": {"enabled": True, "auto_retry_max": 1}})
        decision = decide_reconciliation(ReconciliationEvidence(
            package_id="p",
            execution_state=EXEC_UNKNOWN,
            verified_dead=True,
            death_evidence_authoritative=True,
            retry_count=0,
        ), config=cfg)
        self.assertEqual(decision.decision, RECONCILE_RETRY)

        exhausted = decide_reconciliation(ReconciliationEvidence(
            package_id="p",
            execution_state=EXEC_UNKNOWN,
            verified_dead=True,
            death_evidence_authoritative=True,
            retry_count=1,
        ), config=cfg)
        self.assertEqual(exhausted.decision, RECONCILE_ESCALATE)

    def test_caller_claimed_death_is_not_retry_authority(self):
        cfg = ReliabilityConfig({"reconciliation": {"enabled": True, "auto_retry_max": 1}})
        decision = decide_reconciliation(ReconciliationEvidence(
            package_id="p",
            execution_state=EXEC_UNKNOWN,
            verified_dead=True,
            death_evidence_authoritative=False,
            retry_count=0,
        ), config=cfg)
        self.assertEqual(decision.decision, RECONCILE_ESCALATE)


class TestC1DispatcherEvidenceBoundary(unittest.TestCase):
    def test_t1_dispatcher_exception_becomes_execution_unknown(self):
        def boom(_wp, _assignment):
            raise TimeoutError("subprocess timed out after spawn")

        mark_executor(boom, WORKER_SIMULATED)
        graph = DependencyGraph.from_packages([_pkg()])
        with tempfile.TemporaryDirectory() as tmp:
            ev = Path(tmp) / "ev.jsonl"
            report = Dispatcher(_wf(), executor=boom, evidence_path=ev).run(graph)
        a = report.assignments["p"]
        self.assertEqual(a.execution_state, EXEC_UNKNOWN)
        self.assertTrue(a.requires_reconciliation)
        self.assertIn("reconciliation required", report.errors[0])

    def test_t4_delivery_failure_after_success_is_not_execution_failure(self):
        def delivery_failed(_wp, _assignment):
            return ExecutionResult(
                success=True,
                actual_runtime="sim",
                execution_state=EXEC_COMPLETED,
                result_state="DELIVERY_FAILED",
                command_state=COMMAND_FAILED,
                execution_evidence_source="delivery-failed-after-success",
            )

        mark_executor(delivery_failed, WORKER_SIMULATED)
        graph = DependencyGraph.from_packages([_pkg()])
        with tempfile.TemporaryDirectory() as tmp:
            report = Dispatcher(
                _wf(), executor=delivery_failed, evidence_path=Path(tmp) / "ev.jsonl"
            ).run(graph)
        self.assertEqual(report.graph_summary["completed"], 1)
        a = report.assignments["p"]
        self.assertEqual(a.execution_state, EXEC_COMPLETED)
        self.assertEqual(a.result_state, "DELIVERY_FAILED")
        self.assertFalse(a.requires_reconciliation)

    def test_t14_command_failure_is_distinct_from_worker_success(self):
        def command_failed_worker_success(_wp, _assignment):
            return ExecutionResult(
                success=True,
                actual_runtime="sim",
                execution_state=EXEC_COMPLETED,
                command_state=COMMAND_FAILED,
                execution_evidence_source="command-failed-worker-success",
            )

        mark_executor(command_failed_worker_success, WORKER_SIMULATED)
        graph = DependencyGraph.from_packages([_pkg()])
        with tempfile.TemporaryDirectory() as tmp:
            report = Dispatcher(
                _wf(), executor=command_failed_worker_success,
                evidence_path=Path(tmp) / "ev.jsonl",
            ).run(graph)
        a = report.assignments["p"]
        self.assertEqual(report.graph_summary["completed"], 1)
        self.assertEqual(a.execution_state, EXEC_COMPLETED)
        self.assertEqual(a.command_state, COMMAND_FAILED)

    def test_unknown_survives_graph_state_serialization(self):
        def unknown(_wp, _assignment):
            return ExecutionResult(
                success=False,
                actual_runtime="sim",
                execution_state=EXEC_UNKNOWN,
                command_state=COMMAND_TIMED_OUT,
                execution_evidence_source="fail-closed-subprocess-error",
            )

        mark_executor(unknown, WORKER_SIMULATED)
        graph = DependencyGraph.from_packages([_pkg()])
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            Dispatcher(
                _wf(), executor=unknown,
                evidence_path=Path(tmp) / "ev.jsonl",
                graph_state_path=str(state_path),
            ).run(graph)
            state = __import__("json").loads(state_path.read_text())
        self.assertEqual(state["packages"]["p"]["status"], "execution_unknown")

    def test_unknown_graph_state_serialization_carries_run_and_terminal_evidence(self):
        terminal = {"signal": {"source": "worker-terminal"}, "verified_death": True}

        def unknown(_wp, _assignment):
            return ExecutionResult(
                success=False,
                actual_runtime="sim",
                run_id="r-unknown",
                agent_id="lisa-test",
                execution_state=EXEC_UNKNOWN,
                command_state=COMMAND_FAILED,
                execution_evidence_source="worker-terminal",
                terminal_evidence=terminal,
            )

        mark_executor(unknown, WORKER_SIMULATED)
        graph = DependencyGraph.from_packages([_pkg()])
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            Dispatcher(
                _wf(), executor=unknown,
                evidence_path=Path(tmp) / "ev.jsonl",
                graph_state_path=str(state_path),
                mission_id="m1",
            ).run(graph)
            state = __import__("json").loads(state_path.read_text())
        package_state = state["packages"]["p"]
        self.assertEqual(package_state["status"], "execution_unknown")
        self.assertEqual(package_state["run_id"], "r-unknown")
        self.assertEqual(package_state["terminal_evidence"], terminal)

    def test_dispatcher_denies_previous_unknown_without_retry_decision(self):
        graph = DependencyGraph.from_packages([_pkg()])

        def ok(_wp, _assignment):
            return ExecutionResult(success=True, actual_runtime="sim")

        mark_executor(ok, WORKER_SIMULATED)
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            state_path.write_text(
                '{"schema":"lisa-graph-state/1","mission_id":"m1",'
                '"packages":{"p":"execution_unknown"}}\n',
                encoding="utf-8",
            )
            report = Dispatcher(
                _wf(), executor=ok,
                evidence_path=Path(tmp) / "ev.jsonl",
                graph_state_path=str(state_path),
                mission_id="m1",
            ).run(graph)
        self.assertEqual(report.graph_summary["failed"], 1)
        self.assertIn("without_RETRY_decision", report.errors[0])

    def test_dispatcher_allows_previous_unknown_with_retry_decision(self):
        graph = DependencyGraph.from_packages([_pkg()])

        def ok(_wp, _assignment):
            return ExecutionResult(success=True, actual_runtime="sim")

        mark_executor(ok, WORKER_SIMULATED)
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            state_path.write_text(
                '{"schema":"lisa-graph-state/1","mission_id":"m1",'
                '"packages":{"p":"execution_unknown"},'
                '"reconciliation_decisions":{"p":{"decision":"RETRY",'
                '"mission_id":"m1","package_id":"p"}}}\n',
                encoding="utf-8",
            )
            report = Dispatcher(
                _wf(), executor=ok,
                evidence_path=Path(tmp) / "ev.jsonl",
                graph_state_path=str(state_path),
                mission_id="m1",
            ).run(graph)
            state = __import__("json").loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(report.graph_summary["completed"], 1)
            self.assertTrue(state["reconciliation_decisions"]["p"]["consumed"])

    def test_retry_decision_is_single_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            state_path.write_text(
                '{"schema":"lisa-graph-state/1","mission_id":"m1",'
                '"packages":{"p":"execution_unknown"},'
                '"reconciliation_decisions":{"p":{"decision":"RETRY",'
                '"mission_id":"m1","package_id":"p"}}}\n',
                encoding="utf-8",
            )
            dispatcher = Dispatcher(
                _wf(),
                executor=mark_executor(
                    lambda _wp, _a: ExecutionResult(success=True),
                    WORKER_SIMULATED,
                ),
                graph_state_path=str(state_path),
                mission_id="m1",
            )
            first = dispatcher._dispatch_allowed_by_reconciliation("p")
            second = dispatcher._dispatch_allowed_by_reconciliation("p")
        self.assertEqual(first, (True, "reconciliation_retry_authorized"))
        self.assertEqual(second, (False, "reconciliation_RETRY_already_consumed"))

    def test_two_missions_same_package_id_do_not_collide(self):
        def ok(_wp, _assignment):
            return ExecutionResult(success=True, actual_runtime="sim")

        mark_executor(ok, WORKER_SIMULATED)
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            state_path.write_text(
                '{"schema":"lisa-graph-state/1","mission_id":"mission-a",'
                '"packages":{"p":"execution_unknown"}}\n',
                encoding="utf-8",
            )
            report = Dispatcher(
                _wf(), executor=ok,
                evidence_path=Path(tmp) / "ev.jsonl",
                graph_state_path=str(state_path),
                mission_id="mission-b",
            ).run(DependencyGraph.from_packages([_pkg("p")]))
        self.assertEqual(report.graph_summary["completed"], 1)

    def test_missing_mission_identity_with_unknown_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            state_path.write_text(
                '{"schema":"lisa-graph-state/1","packages":{"p":"execution_unknown"}}\n',
                encoding="utf-8",
            )
            dispatcher = Dispatcher(
                _wf(),
                executor=mark_executor(lambda _wp, _a: ExecutionResult(success=True), WORKER_SIMULATED),
                graph_state_path=str(state_path),
                mission_id="m1",
            )
            allowed = dispatcher._dispatch_allowed_by_reconciliation("p")
        self.assertEqual(allowed, (False, "missing_mission_identity"))

    def test_malformed_graph_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            state_path.write_text("{not-json", encoding="utf-8")
            dispatcher = Dispatcher(
                _wf(),
                executor=mark_executor(lambda _wp, _a: ExecutionResult(success=True), WORKER_SIMULATED),
                graph_state_path=str(state_path),
                mission_id="m1",
            )
            allowed = dispatcher._dispatch_allowed_by_reconciliation("p")
        self.assertEqual(allowed, (False, "durable_state_malformed"))

    def test_missing_graph_state_does_not_authorize_ambiguous_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = Dispatcher(
                _wf(),
                executor=mark_executor(lambda _wp, _a: ExecutionResult(success=True), WORKER_SIMULATED),
                graph_state_path=str(Path(tmp) / "missing.json"),
                mission_id="m1",
            )
            allowed = dispatcher._dispatch_allowed_by_reconciliation("p")
        self.assertEqual(allowed, (True, "not_previously_unknown"))

    def test_two_concurrent_retry_consumers_only_one_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            state_path.write_text(
                '{"schema":"lisa-graph-state/1","mission_id":"m1",'
                '"packages":{"p":"execution_unknown"},'
                '"reconciliation_decisions":{"p":{"decision":"RETRY",'
                '"mission_id":"m1","package_id":"p"}}}\n',
                encoding="utf-8",
            )
            results = []
            barrier = threading.Barrier(2)

            def contend():
                dispatcher = Dispatcher(
                    _wf(),
                    executor=mark_executor(lambda _wp, _a: ExecutionResult(success=True), WORKER_SIMULATED),
                    graph_state_path=str(state_path),
                    mission_id="m1",
                )
                barrier.wait()
                results.append(dispatcher._dispatch_allowed_by_reconciliation("p"))

            threads = [threading.Thread(target=contend) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(sum(1 for r in results if r[0]), 1)
        self.assertEqual(sum(1 for r in results if r[1] == "reconciliation_RETRY_already_consumed"), 1)

    def test_concurrent_graph_state_writers_merge_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GraphStateStore(Path(tmp) / "graph_state.json")
            barrier = threading.Barrier(2)

            def write_pkg(pid):
                barrier.wait()
                def mutate(loaded):
                    state = loaded.state if loaded.valid else {}
                    packages = dict(state.get("packages") or {})
                    packages[pid] = "completed"
                    return {"schema": "lisa-graph-state/1", "mission_id": "m1", "packages": packages}
                store.mutate_locked(mutate)

            threads = [threading.Thread(target=write_pkg, args=(pid,)) for pid in ("a", "b")]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            loaded = store.load().state
        self.assertEqual(loaded["packages"], {"a": "completed", "b": "completed"})

    def test_stale_auto_resume_writer_cannot_replay_consumed_retry(self):
        import core.auto_resume as ar

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            base = {
                "schema": "lisa-graph-state/1",
                "mission_id": "m1",
                "packages": {"p": "execution_unknown"},
                "reconciliation_decisions": {
                    "p": {"decision": "RETRY", "mission_id": "m1", "package_id": "p"}
                },
            }
            ar.write_graph_state(base, state_path)
            stale = __import__("copy").deepcopy(base)
            consumed = threading.Event()

            def consume_retry():
                dispatcher = Dispatcher(
                    _wf(),
                    executor=mark_executor(lambda _wp, _a: ExecutionResult(success=True), WORKER_SIMULATED),
                    graph_state_path=str(state_path),
                    mission_id="m1",
                )
                self.assertEqual(
                    dispatcher._dispatch_allowed_by_reconciliation("p"),
                    (True, "reconciliation_retry_authorized"),
                )
                consumed.set()

            def stale_write():
                consumed.wait(timeout=5)
                ar.write_graph_state(stale, state_path)

            threads = [threading.Thread(target=consume_retry), threading.Thread(target=stale_write)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            loaded = GraphStateStore(state_path).load().state

        self.assertTrue(loaded["reconciliation_decisions"]["p"]["consumed"])

    def test_advance_pipeline_race_preserves_consumed_retry_and_graph_merge(self):
        import core.auto_resume as ar

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            ar.write_graph_state({
                "schema": "lisa-graph-state/1",
                "mission_id": "m1",
                "goal_path": "/tmp/g.json",
                "packages": {"p": "execution_unknown", "q": "in_progress"},
                "reconciliation_decisions": {
                    "p": {"decision": "RETRY", "mission_id": "m1", "package_id": "p"}
                },
            }, state_path)
            graph = DependencyGraph.from_packages([_pkg("q")])
            graph.mark_complete("q")
            barrier = threading.Barrier(2)

            def consume_retry():
                barrier.wait()
                dispatcher = Dispatcher(
                    _wf(),
                    executor=mark_executor(lambda _wp, _a: ExecutionResult(success=True), WORKER_SIMULATED),
                    graph_state_path=str(state_path),
                    mission_id="m1",
                )
                dispatcher._dispatch_allowed_by_reconciliation("p")

            def advance():
                barrier.wait()
                ar.advance_pipeline("/tmp/g.json", graph=graph, graph_state_path=state_path)

            threads = [threading.Thread(target=consume_retry), threading.Thread(target=advance)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            loaded = GraphStateStore(state_path).load().state

        self.assertEqual(loaded["packages"]["q"], "completed")
        self.assertTrue(loaded["reconciliation_decisions"]["p"]["consumed"])

    def test_interrupted_atomic_write_leaves_previous_valid_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GraphStateStore(Path(tmp) / "graph_state.json")
            store.write_atomic({"schema": "lisa-graph-state/1", "packages": {"p": "completed"}})
            tmp_file = store.path.with_name(store.path.name + ".orphan.tmp")
            tmp_file.write_text("{partial", encoding="utf-8")
            loaded = store.load()
        self.assertTrue(loaded.valid)
        self.assertEqual(loaded.state["packages"]["p"], "completed")


class TestA3Migration(unittest.TestCase):
    def test_migration_is_idempotent_and_preserves_existing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT, created_at INTEGER)"
            )
            conn.execute(
                "INSERT INTO task_runs(run_id, status, created_at) VALUES ('r1','succeeded',1)"
            )
            conn.commit()
            conn.close()

            apply_migration(db, backup=False)
            apply_migration(db, backup=False)

            conn = sqlite3.connect(db)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(task_runs)")}
            row = conn.execute("SELECT run_id, status FROM task_runs").fetchone()
            lifecycle = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='session_lifecycle'"
            ).fetchone()
            conn.close()

        self.assertIn("execution_state", cols)
        self.assertIn("terminal_evidence", cols)
        self.assertEqual(row, ("r1", "succeeded"))
        self.assertIsNotNone(lifecycle)

    def test_lifecycle_writer_updates_migrated_task_run(self):
        from core.openclaw_bridge import _update_task_run_lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT, created_at INTEGER)"
            )
            conn.execute(
                "INSERT INTO task_runs(run_id, status, created_at) VALUES ('r1','succeeded',1)"
            )
            conn.commit()
            conn.close()
            apply_migration(db, backup=False)

            with patch("core.openclaw_bridge.OPENCLAW_DB", db):
                wrote = _update_task_run_lifecycle(
                    "r1",
                    dispatch_state=DISPATCH_ACKNOWLEDGED,
                    execution_state=EXEC_UNKNOWN,
                    session_state=SESSION_UNKNOWN,
                    result_state=RESULT_UNKNOWN,
                    requires_reconciliation_flag=True,
                    terminal_evidence={"signal": {"source": "test"}},
                    command_state=COMMAND_TIMED_OUT,
                )

            conn = sqlite3.connect(db)
            row = conn.execute(
                "SELECT execution_state, requires_reconciliation, command_state "
                "FROM task_runs WHERE run_id='r1'"
            ).fetchone()
            conn.close()

        self.assertTrue(wrote)
        self.assertEqual(row, (EXEC_UNKNOWN, 1, COMMAND_TIMED_OUT))

    def test_timeout_path_recovers_run_id_and_persists_unknown(self):
        from core.openclaw_bridge import build_real_executor
        from tests.test_openclaw_bridge import _FakeAssignment, _FakePkg, _resolver
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT, "
                "created_at INTEGER, agent_id TEXT, session_key TEXT, task TEXT)"
            )
            conn.execute(
                "INSERT INTO task_runs(run_id, status, created_at, agent_id, session_key, task) "
                "VALUES ('run-timeout','running',0,'lisa-gpt','pending','x')"
            )
            conn.commit()
            conn.close()
            apply_migration(db, backup=False)

            def fake_run_agent(agent_id, message, session_key, timeout_seconds):
                conn = sqlite3.connect(db)
                conn.execute(
                    "UPDATE task_runs SET created_at=?, session_key=?, task=? "
                    "WHERE run_id='run-timeout'",
                    (9999999999999, session_key, message),
                )
                conn.commit()
                conn.close()
                raise subprocess.TimeoutExpired("openclaw", timeout_seconds)

            with patch("core.openclaw_bridge.OPENCLAW_DB", db), \
                 patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok")), \
                 patch("core.openclaw_bridge.non_wbs_agents", return_value=[{"id": "lisa-gpt", "model": "openai/gpt-5.5"}]), \
                 patch("core.openclaw_bridge._run_agent", side_effect=fake_run_agent):
                result = build_real_executor(resolver=_resolver())(
                    _FakePkg("p", description="x"),
                    _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
                )

            conn = sqlite3.connect(db)
            row = conn.execute(
                "SELECT execution_state, requires_reconciliation "
                "FROM task_runs WHERE run_id='run-timeout'"
            ).fetchone()
            conn.close()

        self.assertEqual(result.run_id, "run-timeout")
        self.assertEqual(row, (EXEC_UNKNOWN, 1))


class TestB1AutoResumeIntegration(unittest.TestCase):
    def test_unknown_records_gate_decision_and_wakes_main(self):
        import core.auto_resume as ar

        state = {
            "schema": "lisa-graph-state/1",
            "packages": {"p": "execution_unknown"},
            "mission_run_ids": [],
        }
        self.assertEqual(ar.decide_action(state), ar.DECISION_WAKE_MAIN)
        self.assertEqual(
            state["reconciliation_decisions"]["p"]["decision"],
            RECONCILE_ESCALATE,
        )

    def test_resume_if_needed_persists_reconciliation_decision(self):
        import core.auto_resume as ar

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            ar.write_graph_state({
                "schema": "lisa-graph-state/1",
                "mission_id": mission_id_for_goal("/tmp/g.json"),
                "goal_path": "/tmp/g.json",
                "packages": {"p": "execution_unknown"},
                "mission_run_ids": [],
            }, state_path)
            with patch.object(ar, "GRAPH_STATE_PATH", state_path):
                decision = ar.resume_if_needed("/tmp/g.json")
            loaded = ar.load_graph_state(state_path)
        self.assertEqual(decision, ar.DECISION_WAKE_MAIN)
        self.assertEqual(
            loaded["reconciliation_decisions"]["p"]["decision"],
            RECONCILE_ESCALATE,
        )

    def test_resume_applies_authoritative_completed_task_run(self):
        import core.auto_resume as ar

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT)"
            )
            conn.execute(
                "INSERT INTO task_runs(run_id, status) VALUES ('r-complete','succeeded')"
            )
            conn.commit()
            conn.close()
            ar.write_graph_state({
                "schema": "lisa-graph-state/1",
                "mission_id": mission_id_for_goal("/tmp/g.json"),
                "goal_path": "/tmp/g.json",
                "packages": {"p": {"status": "execution_unknown", "run_id": "r-complete"}},
                "mission_run_ids": ["r-complete"],
            }, state_path)
            with patch.object(ar, "GRAPH_STATE_PATH", state_path), \
                 patch.object(ar, "WAKE_PENDING_PATH", Path(tmp) / "wake.json"), \
                 patch.object(ar, "OPENCLAW_DB", db):
                decision = ar.resume_if_needed("/tmp/g.json")
            loaded = ar.load_graph_state(state_path)
        self.assertEqual(decision, ar.DECISION_DONE)
        self.assertEqual(loaded["packages"]["p"], "completed")
        self.assertEqual(
            loaded["reconciliation_decisions"]["p"]["decision"],
            RECONCILE_RESUME,
        )

    def test_caller_claimed_dead_unknown_still_escalates(self):
        import core.auto_resume as ar

        state = {
            "schema": "lisa-graph-state/1",
            "mission_id": "m1",
            "packages": {"p": "execution_unknown"},
            "mission_run_ids": [],
        }
        meta = {"p": {"verified_dead": True, "retry_count": 0}}
        self.assertEqual(ar.decide_action(state, meta), ar.DECISION_WAKE_MAIN)
        self.assertEqual(
            state["reconciliation_decisions"]["p"]["decision"],
            RECONCILE_ESCALATE,
        )

    def test_failed_task_run_without_dead_session_remains_unknown(self):
        import core.auto_resume as ar

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT)")
            conn.execute("INSERT INTO task_runs(run_id, status) VALUES ('r-failed','failed')")
            conn.commit()
            conn.close()
            state = {
                "schema": "lisa-graph-state/1",
                "mission_id": "m1",
                "packages": {"p": {"status": "execution_unknown", "run_id": "r-failed"}},
                "mission_run_ids": ["r-failed"],
            }
            with patch.object(ar, "OPENCLAW_DB", db):
                self.assertEqual(ar.decide_action(state), ar.DECISION_WAKE_MAIN)
        self.assertEqual(state["reconciliation_decisions"]["p"]["decision"], RECONCILE_ESCALATE)

    def test_failed_task_run_with_dead_session_without_terminal_evidence_remains_unknown(self):
        import core.auto_resume as ar

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT, session_key TEXT)"
            )
            conn.execute(
                "CREATE TABLE session_lifecycle (session_key TEXT PRIMARY KEY, session_state TEXT)"
            )
            conn.execute(
                "INSERT INTO task_runs(run_id, status, session_key) "
                "VALUES ('r-failed','failed','s-dead')"
            )
            conn.execute(
                "INSERT INTO session_lifecycle(session_key, session_state) "
                "VALUES ('s-dead','dead')"
            )
            conn.commit()
            conn.close()
            state = {
                "schema": "lisa-graph-state/1",
                "mission_id": "m1",
                "packages": {"p": {"status": "execution_unknown", "run_id": "r-failed"}},
                "mission_run_ids": ["r-failed"],
            }
            with patch.object(ar, "OPENCLAW_DB", db):
                self.assertEqual(ar.decide_action(state), ar.DECISION_WAKE_MAIN)
        self.assertEqual(state["reconciliation_decisions"]["p"]["decision"], RECONCILE_ESCALATE)

    def test_authoritative_failed_task_run_with_dead_session_and_terminal_evidence_allows_retry(self):
        import core.auto_resume as ar

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT, session_key TEXT)"
            )
            conn.execute(
                "CREATE TABLE session_lifecycle (session_key TEXT PRIMARY KEY, session_state TEXT)"
            )
            conn.execute(
                "INSERT INTO task_runs(run_id, status, session_key) "
                "VALUES ('r-failed','failed','s-dead')"
            )
            conn.execute(
                "INSERT INTO session_lifecycle(session_key, session_state) "
                "VALUES ('s-dead','dead')"
            )
            conn.commit()
            conn.close()
            state = {
                "schema": "lisa-graph-state/1",
                "mission_id": "m1",
                "packages": {
                    "p": {
                        "status": "execution_unknown",
                        "run_id": "r-failed",
                        "terminal_evidence": {"verified_death": True},
                    }
                },
                "mission_run_ids": ["r-failed"],
            }
            with patch.object(ar, "OPENCLAW_DB", db):
                self.assertEqual(ar.decide_action(state), ar.DECISION_CONTINUE)
        self.assertEqual(state["reconciliation_decisions"]["p"]["decision"], RECONCILE_RETRY)

    def test_task_run_terminal_evidence_is_authoritative_death_source(self):
        import core.auto_resume as ar

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE task_runs ("
                "run_id TEXT PRIMARY KEY, status TEXT, session_key TEXT, terminal_evidence TEXT)"
            )
            conn.execute(
                "CREATE TABLE session_lifecycle (session_key TEXT PRIMARY KEY, session_state TEXT)"
            )
            conn.execute(
                "INSERT INTO task_runs(run_id, status, session_key, terminal_evidence) "
                "VALUES ('r-failed','failed','s-dead','{\"verified_death\":true}')"
            )
            conn.execute(
                "INSERT INTO session_lifecycle(session_key, session_state) "
                "VALUES ('s-dead','dead')"
            )
            conn.commit()
            conn.close()
            state = {
                "schema": "lisa-graph-state/1",
                "mission_id": "m1",
                "packages": {"p": {"status": "execution_unknown", "run_id": "r-failed"}},
                "mission_run_ids": ["r-failed"],
            }
            with patch.object(ar, "OPENCLAW_DB", db):
                self.assertEqual(ar.decide_action(state), ar.DECISION_CONTINUE)
        self.assertEqual(state["reconciliation_decisions"]["p"]["decision"], RECONCILE_RETRY)

    def test_verified_live_task_run_stays_running(self):
        import core.auto_resume as ar

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw.sqlite"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT)")
            conn.execute("INSERT INTO task_runs(run_id, status) VALUES ('r-live','running')")
            conn.commit()
            conn.close()
            state = {
                "schema": "lisa-graph-state/1",
                "mission_id": "m1",
                "packages": {"p": {"status": "execution_unknown", "run_id": "r-live"}},
                "mission_run_ids": ["r-live"],
            }
            with patch.object(ar, "OPENCLAW_DB", db):
                self.assertEqual(ar.decide_action(state), ar.DECISION_DONE)
        self.assertEqual(state["packages"]["p"]["status"], "running")
        self.assertEqual(state["reconciliation_decisions"]["p"]["decision"], RECONCILE_RESUME)

    def test_ambiguous_liveness_remains_unknown(self):
        import core.auto_resume as ar

        state = {
            "schema": "lisa-graph-state/1",
            "mission_id": "m1",
            "packages": {"p": {"status": "execution_unknown", "run_id": "missing"}},
            "mission_run_ids": ["missing"],
        }
        self.assertEqual(ar.decide_action(state), ar.DECISION_WAKE_MAIN)
        self.assertEqual(state["packages"]["p"]["status"], "execution_unknown")
        self.assertEqual(state["reconciliation_decisions"]["p"]["decision"], RECONCILE_ESCALATE)

    def test_advance_pipeline_preserves_existing_unknown(self):
        import core.auto_resume as ar

        pkgs = [_pkg()]
        graph = DependencyGraph.from_packages(pkgs)
        graph.mark_failed("p")
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "graph_state.json"
            wake_path = Path(tmp) / "wake.json"
            ar.write_graph_state({
                "schema": "lisa-graph-state/1",
                "goal_path": "/tmp/g.json",
                "packages": {"p": "execution_unknown"},
                "mission_run_ids": [],
            }, state_path)
            with patch.object(ar, "GRAPH_STATE_PATH", state_path), \
                 patch.object(ar, "WAKE_PENDING_PATH", wake_path), \
                 patch.object(ar, "_send_system_event", return_value=True):
                ar.advance_pipeline("/tmp/g.json", graph=graph)
            loaded = ar.load_graph_state(state_path)
        self.assertEqual(loaded["packages"]["p"], "execution_unknown")

    def test_auto_resume_uses_explicit_scoped_state_path(self):
        import core.auto_resume as ar

        pkgs = [_pkg()]
        graph = DependencyGraph.from_packages(pkgs)
        graph.mark_complete("p")
        with tempfile.TemporaryDirectory() as tmp:
            scoped_path = Path(tmp) / "graph_state-scoped.json"
            global_path = Path(tmp) / "graph_state.json"
            wake_path = Path(tmp) / "wake.json"
            with patch.object(ar, "GRAPH_STATE_PATH", global_path), \
                 patch.object(ar, "WAKE_PENDING_PATH", wake_path):
                state = ar.build_graph_state(graph, "/tmp/g.json", mission_run_ids=[])
                ar.write_graph_state(state, scoped_path)
                decision = ar.advance_pipeline(
                    "/tmp/g.json",
                    graph=graph,
                    graph_state_path=scoped_path,
                )
                scoped = ar.load_graph_state(scoped_path)
                global_state = ar.load_graph_state(global_path)
        self.assertEqual(decision, ar.DECISION_DONE)
        self.assertIsNone(global_state)
        self.assertEqual(scoped["packages"]["p"], "completed")


class TestBridgeUnknownTags(unittest.TestCase):
    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge.non_wbs_agents", return_value=[{"id": "lisa-gpt", "model": "openai/gpt-5.5"}])
    @patch("core.openclaw_bridge._run_agent")
    def test_t5_nonzero_session_limit_is_unknown_not_failed(self, run_agent, _agents, _health):
        from core.openclaw_bridge import build_real_executor
        from tests.test_openclaw_bridge import _FakeAssignment, _FakePkg, _resolver

        run_agent.return_value = (
            1,
            "",
            "FailoverError: You've hit your session limit · resets 2:50pm",
        )
        result = build_real_executor(resolver=_resolver())(
            _FakePkg("p"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.execution_state, EXEC_UNKNOWN)
        self.assertTrue(result.requires_reconciliation)
        self.assertEqual(result.command_state, COMMAND_FAILED)

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run")
    @patch("core.openclaw_bridge.non_wbs_agents", return_value=[{"id": "lisa-gpt", "model": "openai/gpt-5.5"}])
    @patch("core.openclaw_bridge._run_agent")
    def test_success_requires_task_run_confirmation(self, run_agent, _agents, fetch, _health):
        from core.openclaw_bridge import build_real_executor
        from tests.test_openclaw_bridge import _FakeAssignment, _FakePkg, _REAL_RESPONSE_SHAPE, _resolver

        run_agent.return_value = (0, _REAL_RESPONSE_SHAPE, "")
        fetch.return_value = None
        result = build_real_executor(resolver=_resolver())(
            _FakePkg("p"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.execution_state, EXEC_UNKNOWN)

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run")
    @patch("core.openclaw_bridge.non_wbs_agents", return_value=[{"id": "lisa-gpt", "model": "openai/gpt-5.5"}])
    @patch("core.openclaw_bridge._run_agent")
    def test_declared_artifact_missing_keeps_execution_unknown(self, run_agent, _agents, fetch, _health):
        from core.openclaw_bridge import build_real_executor
        from tests.test_openclaw_bridge import _FakeAssignment, _REAL_RESPONSE_SHAPE, _resolver

        class P:
            id = "p"
            description = "x"
            expected_artifact_path = "/tmp/definitely-missing-rc004-artifact"

        run_agent.return_value = (0, _REAL_RESPONSE_SHAPE, "")
        fetch.return_value = {"run_id": "r1", "status": "succeeded"}
        result = build_real_executor(resolver=_resolver())(
            P(),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.execution_state, EXEC_UNKNOWN)
        self.assertEqual(result.terminal_evidence["artifact"]["exists"], False)

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run")
    @patch("core.openclaw_bridge.non_wbs_agents", return_value=[{"id": "lisa-gpt", "model": "openai/gpt-5.5"}])
    @patch("core.openclaw_bridge._run_agent")
    def test_artifact_requirement_flag_can_be_disabled(self, run_agent, _agents, fetch, _health):
        from core.openclaw_bridge import build_real_executor
        from tests.test_openclaw_bridge import _FakeAssignment, _REAL_RESPONSE_SHAPE, _resolver
        from core.reliability_config import ReliabilityConfig

        class P:
            id = "p"
            description = "x"
            expected_artifact_path = "/tmp/definitely-missing-rc004-artifact"

        run_agent.return_value = (0, _REAL_RESPONSE_SHAPE, "")
        fetch.return_value = {"run_id": "r1", "status": "succeeded"}
        with patch(
            "core.openclaw_bridge.load_reliability_config",
            return_value=ReliabilityConfig({
                "reconciliation": {"enabled": True, "auto_retry_max": 1},
                "evidence": {"require_artifact": False},
            }),
        ):
            result = build_real_executor(resolver=_resolver())(
                P(),
                _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
            )
        self.assertTrue(result.success)
        self.assertEqual(result.execution_state, EXEC_COMPLETED)


if __name__ == "__main__":
    unittest.main()
