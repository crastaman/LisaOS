"""Tests for the Constitution v2 r4 remediation (S044).

Each test class pins one confirmed finding from the independent Codex
constitutional review and its subsequent independent assessment, so a
regression re-opens a named constitutional gap rather than an anonymous bug.

Fully hermetic: no network, no spend, no real spawn.

    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_r4_remediation -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.dispatcher import (
    Dispatcher,
    ExecutionResult,
    simulated_executor,
    mark_executor,
    executor_provenance,
    WORKER_REAL,
    WORKER_SIMULATED,
    MAIN_INLINE,
    SIMULATED_LABEL,
)
from core.capacity_ledger import CapacityLedger, ledger_recording_executor
from core.dependency_graph import DependencyGraph
from core.workforce_resolver import WorkforceResolver, WorkPackage

from tests.test_dispatcher import real_employees, resolver_all_available


def _graph(pkg_id: str = "a", caps: list[str] | None = None) -> DependencyGraph:
    return DependencyGraph.from_packages(
        [WorkPackage(id=pkg_id, description="", required_capabilities=caps or ["microtask"])]
    )


def _workforce() -> WorkforceResolver:
    return WorkforceResolver(real_employees(), resolver_all_available())


# --------------------------------------------------------------------------- #
# B3 -- executor provenance / attribution truth
# --------------------------------------------------------------------------- #

class TestExecutorProvenance(unittest.TestCase):
    """B3: arbitrary executor injection, and hardcoded by_main=False."""

    def test_undeclared_executor_is_refused(self):
        def anonymous(pkg, assignment):
            return ExecutionResult(success=True, actual_runtime=assignment.resolved_runtime)

        with self.assertRaises(ValueError) as ctx:
            Dispatcher(_workforce(), executor=anonymous)
        self.assertIn("declared provenance", str(ctx.exception))

    def test_mark_executor_rejects_unknown_provenance(self):
        def e(pkg, assignment):
            return ExecutionResult(success=True)

        with self.assertRaises(ValueError):
            mark_executor(e, "definitely-not-a-provenance")

    def test_canonical_executors_declare_themselves(self):
        self.assertEqual(executor_provenance(simulated_executor), WORKER_SIMULATED)

        from core.openclaw_bridge import labelled_simulated_executor
        self.assertEqual(executor_provenance(labelled_simulated_executor), WORKER_SIMULATED)

    def test_main_inline_execution_is_attributed_to_main_not_worker(self):
        """The core of B3: before r4 this ran as main and reported as worker."""
        @lambda fn: mark_executor(fn, MAIN_INLINE)
        def in_process(pkg, assignment):
            return ExecutionResult(success=True, actual_runtime=assignment.resolved_runtime)

        with tempfile.TemporaryDirectory() as tmp:
            d = Dispatcher(_workforce(), executor=in_process,
                           evidence_path=Path(tmp) / "ev.jsonl")
            report = d.run(_graph())

        self.assertEqual(report.metrics.main_completed, 1)
        self.assertEqual(report.metrics.worker_completed, 0)
        self.assertEqual(report.metrics.delegation_ratio, 0.0)

    def test_worker_execution_is_attributed_to_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Dispatcher(_workforce(), executor=simulated_executor,
                           evidence_path=Path(tmp) / "ev.jsonl")
            report = d.run(_graph())

        self.assertEqual(report.metrics.worker_completed, 1)
        self.assertEqual(report.metrics.main_completed, 0)

    def test_provenance_is_recorded_on_the_evidence_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Dispatcher(_workforce(), executor=simulated_executor,
                           evidence_path=Path(tmp) / "ev.jsonl")
            report = d.run(_graph())

        self.assertEqual(report.assignments["a"].execution_provenance, WORKER_SIMULATED)

    def test_executor_swapped_after_construction_is_re_checked(self):
        """The check is re-derived per run(), not captured at __init__.

        Otherwise `d.executor = undeclared_fn` would run an undeclared
        callable while every record carried the originally-declared value.
        """
        d = Dispatcher(_workforce(), executor=simulated_executor)

        def undeclared(pkg, assignment):
            return ExecutionResult(success=True, actual_runtime=assignment.resolved_runtime)

        d.executor = undeclared
        with self.assertRaises(ValueError) as ctx:
            d.run(_graph())
        self.assertIn("declared provenance", str(ctx.exception))

    def test_swapped_executor_provenance_follows_what_actually_runs(self):
        d = Dispatcher(_workforce(), executor=simulated_executor)

        @lambda fn: mark_executor(fn, MAIN_INLINE)
        def in_process(pkg, assignment):
            return ExecutionResult(success=True, actual_runtime=assignment.resolved_runtime)

        d.executor = in_process
        with tempfile.TemporaryDirectory() as tmp:
            d.evidence_path = Path(tmp) / "ev.jsonl"
            report = d.run(_graph())

        # Recorded provenance must describe the callable that ran, not the
        # one supplied at construction.
        self.assertEqual(report.assignments["a"].execution_provenance, MAIN_INLINE)
        self.assertEqual(report.metrics.main_completed, 1)
        self.assertEqual(report.metrics.worker_completed, 0)

    def test_wrapper_cannot_launder_an_undeclared_inner_executor(self):
        def anonymous(pkg, assignment):
            return ExecutionResult(success=True)

        with self.assertRaises(ValueError):
            ledger_recording_executor(CapacityLedger.in_memory(), inner=anonymous)

    def test_wrapper_inherits_inner_provenance_rather_than_inventing_one(self):
        @lambda fn: mark_executor(fn, MAIN_INLINE)
        def in_process(pkg, assignment):
            return ExecutionResult(success=True, actual_runtime=assignment.resolved_runtime)

        wrapped = ledger_recording_executor(CapacityLedger.in_memory(), inner=in_process)
        self.assertEqual(executor_provenance(wrapped), MAIN_INLINE)


# --------------------------------------------------------------------------- #
# B2 -- execution outcome on the evidence record
# --------------------------------------------------------------------------- #

class TestExecutionOutcomeEvidence(unittest.TestCase):
    """B2: 04 SS1.1 requires an outcome; the ledger did not carry one."""

    def test_success_is_recorded_on_the_assignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Dispatcher(_workforce(), executor=simulated_executor,
                           evidence_path=Path(tmp) / "ev.jsonl")
            report = d.run(_graph())

        a = report.assignments["a"]
        self.assertIs(a.execution_success, True)
        self.assertIsNone(a.execution_error)

    def test_failure_is_distinguishable_from_success_in_the_ledger(self):
        @lambda fn: mark_executor(fn, WORKER_SIMULATED)
        def failing(pkg, assignment):
            return ExecutionResult(success=False, actual_runtime=assignment.resolved_runtime,
                                   error="upstream refused the task")

        with tempfile.TemporaryDirectory() as tmp:
            ev = Path(tmp) / "ev.jsonl"
            d = Dispatcher(_workforce(), executor=failing, evidence_path=ev)
            report = d.run(_graph())
            written = ev.read_text(encoding="utf-8").strip()

        a = report.assignments["a"]
        self.assertIs(a.execution_success, False)
        self.assertIn("upstream refused", a.execution_error)
        # The persisted record -- not just the in-memory report -- must show it.
        self.assertIn('"execution_success": false', written)
        self.assertIn("upstream refused", written)

    def test_unexecuted_assignment_has_no_outcome(self):
        from core.workforce_resolver import WorkAssignment
        a = WorkAssignment(
            work_package_id="x", employee=None, department=None, intended_family=None,
            intended_model=None, resolved_logical=None, physical_model=None,
            resolved_runtime=None, provider_id=None, available=False,
            auth_result=None, risk="low", mode="default",
        )
        self.assertIsNone(a.execution_success)
        self.assertIsNone(a.execution_error)


# --------------------------------------------------------------------------- #
# B4c -- simulation labelling is not caller-dependent
# --------------------------------------------------------------------------- #

class TestSimulationLabelling(unittest.TestCase):
    def test_bare_simulated_executor_labels_itself(self):
        """Before r4 only the openclaw_bridge wrapper applied the label."""
        result = simulated_executor(
            WorkPackage(id="p", description="", required_capabilities=["microtask"]),
            _stub_assignment(),
        )
        self.assertEqual(result.execution_evidence_source, SIMULATED_LABEL)

    def test_simulated_evidence_reaches_the_ledger_labelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            ev = Path(tmp) / "ev.jsonl"
            d = Dispatcher(_workforce(), executor=simulated_executor, evidence_path=ev)
            d.run(_graph())
            self.assertIn(SIMULATED_LABEL, ev.read_text(encoding="utf-8"))


def _stub_assignment():
    from core.workforce_resolver import WorkAssignment
    return WorkAssignment(
        work_package_id="p", employee="e", department="d", intended_family="f",
        intended_model="m", resolved_logical="m", physical_model="pm",
        resolved_runtime="rt", provider_id="pid", available=True,
        auth_result="ok", risk="low", mode="default",
    )


# --------------------------------------------------------------------------- #
# Authority leak 3 -- empty capability set
# --------------------------------------------------------------------------- #

class TestEmptyCapabilitySet(unittest.TestCase):
    """An empty requirement set used to match every employee."""

    def test_empty_requirements_match_no_candidate(self):
        self.assertEqual(real_employees().candidates_for([]), [])

    def test_empty_requirements_fail_closed_at_resolution(self):
        from core.workforce_resolver import WorkforceResolutionError
        wf = _workforce()
        with self.assertRaises(WorkforceResolutionError):
            wf.resolve(WorkPackage(id="empty", description="", required_capabilities=[]))

    def test_named_capability_still_staffs_normally(self):
        wf = _workforce()
        a = wf.resolve(WorkPackage(id="ok", description="",
                                   required_capabilities=["microtask"]))
        self.assertIsNotNone(a.employee)


if __name__ == "__main__":
    unittest.main(verbosity=2)
