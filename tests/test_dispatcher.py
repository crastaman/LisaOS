"""Proof-of-work tests for the LisaOS Ready-Frontier Scheduler / Dispatcher
(Phase 2).

Validates core/dispatcher.py end to end against the REAL, shipped
`registry/employees.yml` combined with the same hermetic 9-provider
ProviderResolver fixtures used by tests/test_workforce_resolver.py (no real
network/provider calls, no spend -- the default `simulated_executor` just
sleeps briefly in-process).

Covers:
  * Parallel execution: independent ready work is dispatched together, not
    serially -- demonstrated via measured wall-clock vs serial-sum duration.
  * Dependency-blocked waiting is correctly NOT flagged as a failure.
  * Fail-closed per package: an unstaffable package fails without blocking
    independent siblings.
  * No silent DeepSeek fallback at the dispatch level.
  * Subscription-first admission ordering under concurrency contention.
  * Provider-cap throttling is legitimate and does not trip anti-regression.
  * Runtime evidence is recorded for every executed package.
  * run_dispatch_gates() passes on a healthy dispatch.

Run with:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_dispatcher -v
"""

import json
import tempfile
import unittest
from pathlib import Path

from core.workforce_resolver import WorkPackage, WorkforceResolver
from core.dependency_graph import DependencyGraph
from core.dispatcher import Dispatcher, ExecutionResult
from core.anti_regression import run_dispatch_gates

from tests.test_workforce_resolver import (
    real_employees,
    resolver_all_available,
    resolver_no_claude_cli,
    DEEPSEEK_PHYSICAL,
)


def _run(packages, *, resolver=None, max_concurrency=8, max_per_provider=3,
        evidence_path=None):
    wf = WorkforceResolver(real_employees(), resolver or resolver_all_available())
    graph = DependencyGraph.from_packages(packages)
    dispatcher = Dispatcher(wf, max_concurrency=max_concurrency,
                            max_per_provider=max_per_provider,
                            evidence_path=evidence_path)
    return dispatcher.run(graph)


# --------------------------------------------------------------------------- #
# Parallel execution
# --------------------------------------------------------------------------- #

class TestParallelExecution(unittest.TestCase):
    def test_independent_work_dispatched_in_parallel(self):
        packages = [
            WorkPackage(id="a", description="", required_capabilities=["architecture"]),
            WorkPackage(id="b", description="", required_capabilities=["microtask"]),
            WorkPackage(id="c", description="",
                       required_capabilities=["code-implementation", "bulk-mechanical"]),
            WorkPackage(id="d", description="",
                       required_capabilities=["documentation", "long-context",
                                              "bulk-mechanical"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(packages, evidence_path=Path(tmp) / "ev.jsonl")

        self.assertEqual(report.graph_summary["completed"], 4)
        self.assertEqual(report.graph_summary["failed"], 0)
        self.assertEqual(report.errors, [])
        # 4 independent packages on 4 different providers must all have been
        # admitted on the SAME tick (the very first one).
        self.assertEqual(report.metrics.ready_frontier_sizes[0], 4)
        # Genuine wall-clock parallelism: running 4 tasks concurrently must
        # be meaningfully faster than running them back-to-back.
        self.assertGreater(report.metrics.parallel_efficiency, 1.5)
        self.assertLess(report.metrics.wall_clock_seconds,
                        report.metrics.serial_sum_seconds)

    def test_no_unexplained_idle_capacity_while_ready_work_exists(self):
        packages = [
            WorkPackage(id=f"p{i}", description="", required_capabilities=["microtask"])
            for i in range(3)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(packages, max_concurrency=8, max_per_provider=8,
                         evidence_path=Path(tmp) / "ev.jsonl")
        self.assertEqual(report.metrics.max_unexplained_idle_ready, 0)


# --------------------------------------------------------------------------- #
# Dependency-blocked waiting is acceptable
# --------------------------------------------------------------------------- #

class TestDependencyBlockedWaiting(unittest.TestCase):
    def test_dependent_package_only_completes_after_its_dependencies(self):
        packages = [
            WorkPackage(id="a", description="", required_capabilities=["architecture"]),
            WorkPackage(id="b", description="", required_capabilities=["microtask"]),
            WorkPackage(id="merge", description="",
                       required_capabilities=["review", "irreversible-judgement",
                                              "security-review"],
                       depends_on=["a", "b"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(packages, evidence_path=Path(tmp) / "ev.jsonl")

        self.assertEqual(report.graph_summary["completed"], 3)
        # merge must not have been ready on tick 0 (only a, b were).
        self.assertEqual(report.metrics.ready_frontier_sizes[0], 2)
        # A later tick must show merge becoming ready (frontier size 1) once
        # a and b are done -- proving it waited for its dependencies, not
        # that it was "stuck" due to a scheduling failure.
        self.assertIn(1, report.metrics.ready_frontier_sizes[1:])
        # Waiting on dependencies must NOT be flagged as idle-while-ready.
        self.assertEqual(report.metrics.max_unexplained_idle_ready, 0)


# --------------------------------------------------------------------------- #
# Fail-closed behaviour
# --------------------------------------------------------------------------- #

class TestFailClosedDispatch(unittest.TestCase):
    def test_unstaffable_package_fails_without_blocking_independent_siblings(self):
        packages = [
            WorkPackage(id="good", description="", required_capabilities=["microtask"]),
            WorkPackage(id="bad", description="",
                       required_capabilities=["nonexistent-capability"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(packages, evidence_path=Path(tmp) / "ev.jsonl")

        self.assertEqual(report.graph_summary["completed"], 1)
        self.assertEqual(report.graph_summary["failed"], 1)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("bad", report.errors[0])
        self.assertIn("bad", report.assignments)
        self.assertFalse(report.assignments["bad"].available)

    def test_no_available_model_fails_closed_never_silently_uses_deepseek(self):
        # chief-architect (architecture) has NO fallback chain. With the
        # Anthropic subscription down, this MUST fail closed, never silently
        # land on DeepSeek (which isn't even in its chain).
        packages = [WorkPackage(id="arch", description="",
                                required_capabilities=["architecture"])]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(packages, resolver=resolver_no_claude_cli(),
                         evidence_path=Path(tmp) / "ev.jsonl")

        self.assertEqual(report.graph_summary["failed"], 1)
        ev = report.assignments["arch"]
        self.assertFalse(ev.available)
        self.assertIsNone(ev.physical_model)
        self.assertNotEqual(ev.physical_model, DEEPSEEK_PHYSICAL)

    def test_dependents_of_a_failed_package_become_blocked_not_silently_dropped(self):
        packages = [
            WorkPackage(id="bad", description="",
                       required_capabilities=["nonexistent-capability"]),
            WorkPackage(id="dependent", description="", required_capabilities=["microtask"],
                       depends_on=["bad"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(packages, evidence_path=Path(tmp) / "ev.jsonl")
        self.assertEqual(report.graph_summary["failed"], 1)
        self.assertEqual(report.graph_summary["blocked"], 1)
        self.assertNotIn("dependent", report.assignments)  # never staffed/run


# --------------------------------------------------------------------------- #
# Subscription-first admission ordering
# --------------------------------------------------------------------------- #

class TestSubscriptionAwareness(unittest.TestCase):
    def test_subscription_candidate_admitted_before_elastic_under_contention(self):
        # Both ready at tick 0; only ONE concurrency slot -- forces a choice.
        packages = [
            WorkPackage(id="sub", description="", required_capabilities=["microtask"]),
            WorkPackage(id="elastic", description="",
                       required_capabilities=["code-implementation", "bulk-mechanical"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(packages, max_concurrency=1, max_per_provider=1,
                         evidence_path=Path(tmp) / "ev.jsonl")

        self.assertEqual(report.graph_summary["completed"], 2)
        sub_wait = report.metrics.wait_times["sub"]
        elastic_wait = report.metrics.wait_times["elastic"]
        # The subscription-backed package (claude-haiku) must be admitted
        # first; the elastic-API one (deepseek) waits for the freed slot.
        self.assertLess(sub_wait, elastic_wait)
        self.assertEqual(report.assignments["sub"].resolved_logical, "claude-haiku")
        self.assertEqual(report.assignments["elastic"].resolved_logical, "deepseek")


# --------------------------------------------------------------------------- #
# Provider-cap throttling is legitimate, not a scheduling failure
# --------------------------------------------------------------------------- #

class TestProviderCapThrottling(unittest.TestCase):
    def test_provider_cap_throttle_does_not_trip_idle_gate(self):
        packages = [
            WorkPackage(id=f"m{i}", description="", required_capabilities=["microtask"])
            for i in range(5)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(packages, max_concurrency=8, max_per_provider=2,
                         evidence_path=Path(tmp) / "ev.jsonl")

        self.assertEqual(report.graph_summary["completed"], 5)
        self.assertGreater(report.metrics.provider_capacity_limited_events, 0)
        self.assertEqual(report.metrics.max_unexplained_idle_ready, 0)


# --------------------------------------------------------------------------- #
# Runtime evidence
# --------------------------------------------------------------------------- #

class TestRuntimeEvidence(unittest.TestCase):
    def test_evidence_recorded_with_required_fields_for_every_execution(self):
        packages = [
            WorkPackage(id="a", description="", required_capabilities=["microtask"]),
            WorkPackage(id="b", description="",
                       required_capabilities=["code-implementation", "bulk-mechanical"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            ev_path = Path(tmp) / "ev.jsonl"
            report = _run(packages, evidence_path=ev_path)

            lines = ev_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 2)
            for line in lines:
                rec = json.loads(line)
                for field in ("employee", "intended_family", "intended_model",
                             "resolved_logical", "resolved_runtime", "actual_runtime",
                             "duration_seconds", "fallback_reason", "evidence_source",
                             "routed_by"):
                    self.assertIn(field, rec)
                self.assertEqual(rec["routed_by"], "workforce_resolver")
                self.assertIsNotNone(rec["actual_runtime"])
                self.assertIsNotNone(rec["duration_seconds"])

    def test_actual_runtime_matches_resolved_with_default_executor(self):
        packages = [WorkPackage(id="a", description="", required_capabilities=["microtask"])]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(packages, evidence_path=Path(tmp) / "ev.jsonl")
        a = report.assignments["a"]
        self.assertEqual(a.actual_runtime, a.resolved_runtime)
        self.assertTrue(a.matches_actual)


# --------------------------------------------------------------------------- #
# Anti-regression gates against a real dispatch
# --------------------------------------------------------------------------- #

class TestDispatchAntiRegressionGates(unittest.TestCase):
    def test_healthy_dispatch_passes_all_gates(self):
        packages = [
            WorkPackage(id="a", description="", required_capabilities=["architecture"]),
            WorkPackage(id="b", description="", required_capabilities=["microtask"]),
            WorkPackage(id="c", description="",
                       required_capabilities=["code-implementation", "bulk-mechanical"]),
        ]
        hermetic_resolver = resolver_all_available()
        with tempfile.TemporaryDirectory() as tmp:
            wf = WorkforceResolver(real_employees(), hermetic_resolver)
            graph = DependencyGraph.from_packages(packages)
            dispatcher = Dispatcher(wf, evidence_path=Path(tmp) / "ev.jsonl")
            report = dispatcher.run(graph)

        gates = run_dispatch_gates(report, hermetic_resolver)
        self.assertTrue(gates.passed, [(r.name, r.detail) for r in gates.failures])

    def test_main_never_appears_as_the_executor(self):
        # Structural guarantee: the dispatcher has no code path that
        # increments main_completed -- every WorkAssignment it produces is
        # routed_by="workforce_resolver".
        packages = [WorkPackage(id="a", description="", required_capabilities=["microtask"])]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(packages, evidence_path=Path(tmp) / "ev.jsonl")
        self.assertEqual(report.metrics.main_completed, 0)
        self.assertEqual(report.metrics.main_work_ratio, 0.0)
        for a in report.assignments.values():
            self.assertEqual(a.routed_by, "workforce_resolver")


# --------------------------------------------------------------------------- #
# Custom executor injection (failure path)
# --------------------------------------------------------------------------- #

class TestExecutorFailure(unittest.TestCase):
    def test_execution_failure_marks_package_failed_and_records_error(self):
        def failing_executor(pkg, assignment):
            return ExecutionResult(success=False, actual_runtime=assignment.resolved_runtime,
                                   error="simulated crash")

        wf = WorkforceResolver(real_employees(), resolver_all_available())
        graph = DependencyGraph.from_packages(
            [WorkPackage(id="a", description="", required_capabilities=["microtask"])]
        )
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = Dispatcher(wf, executor=failing_executor,
                                    evidence_path=Path(tmp) / "ev.jsonl")
            report = dispatcher.run(graph)

        self.assertEqual(report.graph_summary["failed"], 1)
        self.assertTrue(any("simulated crash" in e for e in report.errors))


# --------------------------------------------------------------------------- #
# Phase 3: scheduler integration with the Capacity Ledger + Policy Engine.
#
# PolicyEngine is duck-type compatible with WorkforceResolver (same
# `.employees` / `.resolve()` shape), so it drops into Dispatcher(workforce=...)
# with ZERO changes to core/dispatcher.py -- proving "the scheduler can select
# workforce based on mode + capacity" without redesigning the Phase 2
# scheduler.
# --------------------------------------------------------------------------- #

class TestCapacityLedgerSchedulerIntegration(unittest.TestCase):
    def test_dispatch_through_policy_engine_updates_ledger_on_real_execution(self):
        from core.policy_engine import PolicyEngine
        from core.workforce_modes import WorkforceModeRegistry
        from core.capacity_ledger import CapacityLedger, ledger_recording_executor

        ledger = CapacityLedger.in_memory()
        engine = PolicyEngine(real_employees(), resolver_all_available(),
                             WorkforceModeRegistry(), ledger)
        packages = [
            WorkPackage(id="a", description="", required_capabilities=["microtask"]),
            WorkPackage(id="b", description="",
                       required_capabilities=["code-implementation", "bulk-mechanical"]),
        ]
        graph = DependencyGraph.from_packages(packages)
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = Dispatcher(engine, executor=ledger_recording_executor(ledger),
                                    evidence_path=Path(tmp) / "ev.jsonl")
            report = dispatcher.run(graph)

        self.assertEqual(report.graph_summary["completed"], 2)
        # The ledger must have recorded a real success for whichever logical
        # providers were actually used by this dispatch.
        used = {a.resolved_logical for a in report.assignments.values()}
        for logical in used:
            entry = ledger.get(logical)
            self.assertGreaterEqual(entry.total_successes, 1)
            self.assertIsNotNone(entry.last_success_at)

    def test_mode_restricted_dispatch_never_uses_disallowed_employee(self):
        from core.policy_engine import PolicyEngine
        from core.workforce_modes import WorkforceModeRegistry
        from core.capacity_ledger import CapacityLedger

        engine = PolicyEngine(real_employees(), resolver_all_available(),
                             WorkforceModeRegistry(), CapacityLedger.in_memory())
        packages = [
            WorkPackage(id="a", description="", required_capabilities=["microtask"],
                       mode="architecture"),
        ]
        graph = DependencyGraph.from_packages(packages)
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = Dispatcher(engine, evidence_path=Path(tmp) / "ev.jsonl")
            report = dispatcher.run(graph)

        # architecture mode only allows chief-architect/cto-reviewer, neither
        # of which provides 'microtask' -- must fail closed, not silently
        # reassign to operations-microtask-agent.
        self.assertEqual(report.graph_summary["failed"], 1)
        self.assertTrue(any("architecture" in e or "no employee provides" in e
                           for e in report.errors))

    def test_ledger_exclusion_prevents_selection_even_when_provider_credentialed(self):
        from core.policy_engine import PolicyEngine
        from core.workforce_modes import WorkforceModeRegistry
        from core.capacity_ledger import CapacityLedger

        ledger = CapacityLedger.in_memory()
        for _ in range(3):
            ledger.record_failure("claude-haiku", reason="simulated repeated timeout")
        engine = PolicyEngine(real_employees(), resolver_all_available(),
                             WorkforceModeRegistry(), ledger)
        packages = [
            WorkPackage(id="a", description="", required_capabilities=["microtask"],
                       risk="low"),
        ]
        graph = DependencyGraph.from_packages(packages)
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = Dispatcher(engine, evidence_path=Path(tmp) / "ev.jsonl")
            report = dispatcher.run(graph)

        self.assertEqual(report.graph_summary["completed"], 1)
        assignment = report.assignments["a"]
        # claude-haiku is provider-credentialed (resolver_all_available), but
        # the ledger marked it unavailable from real observed failures -- the
        # scheduler must have skipped it for the explicit fallback.
        self.assertNotEqual(assignment.resolved_logical, "claude-haiku")
        self.assertEqual(assignment.fallback_from, "claude-haiku")


if __name__ == "__main__":
    unittest.main(verbosity=2)
