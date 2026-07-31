"""Constitution v2 r6 remediation tests.

Pins the r5 independent-review findings ADV-01, ADV-02, ADV-03, ADV-05, and
ADV-06. Fully hermetic: no network, spend, or real OpenClaw spawn.
"""

from __future__ import annotations

import functools
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core.dependency_graph import DependencyGraph
from core.dispatcher import (
    Dispatcher,
    EvidenceSinkError,
    ExecutionResult,
    EXECUTOR_PROVENANCE_ATTR,
    MAIN_INLINE,
    SIMULATED_LABEL,
    WORKER_REAL,
    WORKER_SIMULATED,
    executor_provenance,
    mark_executor,
    simulated_executor,
)
from core.workforce_resolver import (
    EvidenceSerializationError,
    WorkPackage,
    WorkforceResolver,
)
from tests.test_dispatcher import real_employees, resolver_all_available


def _workforce() -> WorkforceResolver:
    return WorkforceResolver(real_employees(), resolver_all_available())


def _graph(*package_ids: str) -> DependencyGraph:
    return DependencyGraph.from_packages(
        WorkPackage(
            id=package_id,
            description=package_id,
            required_capabilities=["microtask"],
        )
        for package_id in package_ids
    )


def _valid_result(assignment) -> ExecutionResult:
    return ExecutionResult(
        success=True,
        actual_runtime=assignment.resolved_runtime,
        execution_evidence_source=SIMULATED_LABEL,
    )


class TestStrictExecutorProvenance(unittest.TestCase):
    def _callable_with_raw_provenance(self, value):
        def executor(pkg, assignment):
            return _valid_result(assignment)

        if value is not ...:
            setattr(executor, EXECUTOR_PROVENANCE_ATTR, value)
        return executor

    def test_missing_provenance_rejected(self):
        with self.assertRaises(ValueError):
            Dispatcher(
                _workforce(),
                executor=self._callable_with_raw_provenance(...),
            )

    def test_empty_provenance_rejected(self):
        with self.assertRaises(ValueError):
            Dispatcher(
                _workforce(),
                executor=self._callable_with_raw_provenance(""),
            )

    def test_unknown_provenance_rejected(self):
        with self.assertRaises(ValueError):
            Dispatcher(
                _workforce(),
                executor=self._callable_with_raw_provenance("bogus-provenance"),
            )

    def test_non_string_provenance_rejected(self):
        for value in (1, False, object()):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    Dispatcher(
                        _workforce(),
                        executor=self._callable_with_raw_provenance(value),
                    )

    def test_valid_provenance_mutated_invalid_after_construction_is_rejected(self):
        executor = self._callable_with_raw_provenance(WORKER_SIMULATED)
        dispatcher = Dispatcher(_workforce(), executor=executor)
        setattr(executor, EXECUTOR_PROVENANCE_ATTR, "invalid-after-construction")

        with self.assertRaises(ValueError):
            dispatcher.run(_graph("invalid"))

    def test_valid_provenance_mutated_to_another_valid_value_drives_current_run(self):
        executor = self._callable_with_raw_provenance(WORKER_SIMULATED)
        dispatcher = Dispatcher(_workforce(), executor=executor)
        setattr(executor, EXECUTOR_PROVENANCE_ATTR, MAIN_INLINE)

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence.jsonl"
            dispatcher.evidence_path = evidence
            report = dispatcher.run(_graph("current"))
            record = json.loads(evidence.read_text())

        self.assertEqual(record["execution_provenance"], MAIN_INLINE)
        self.assertEqual(report.metrics.main_completed, 1)
        self.assertEqual(report.metrics.worker_completed, 0)


class TestStrictExecutorResult(unittest.TestCase):
    def _run_result(self, returned):
        @lambda fn: mark_executor(fn, WORKER_SIMULATED)
        def executor(pkg, assignment):
            return returned(assignment) if callable(returned) else returned

        graph = _graph("malformed")
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence.jsonl"
            report = Dispatcher(
                _workforce(), executor=executor, evidence_path=evidence,
            ).run(graph)
            record = json.loads(evidence.read_text())
        return graph, report, record

    def test_none_arbitrary_object_and_mapping_returns_normalize_to_failure(self):
        for returned in (None, object(), {"success": True}):
            with self.subTest(returned=type(returned).__name__):
                graph, report, record = self._run_result(returned)
                self.assertEqual(graph.summary()["failed"], 1)
                self.assertEqual(report.graph_summary["completed"], 0)
                self.assertIs(record["execution_success"], False)
                self.assertEqual(
                    record["execution_evidence_source"],
                    "fail-closed-malformed-executor-result",
                )

    def test_non_boolean_success_never_completes_package(self):
        for value in ("false", 1, None):
            with self.subTest(value=repr(value)):
                graph, report, record = self._run_result(
                    lambda assignment, value=value: ExecutionResult(
                        success=value,
                        actual_runtime=assignment.resolved_runtime,
                    )
                )
                self.assertEqual(graph.summary()["completed"], 0)
                self.assertEqual(graph.summary()["failed"], 1)
                self.assertIs(record["execution_success"], False)
                self.assertIn("success must be bool", record["execution_error"])

    def test_malformed_error_field_normalizes_to_failure(self):
        _, _, record = self._run_result(
            lambda assignment: ExecutionResult(
                success=True,
                actual_runtime=assignment.resolved_runtime,
                error={"not": "a string"},
            )
        )
        self.assertIs(record["execution_success"], False)
        self.assertIn("error must be str or None", record["execution_error"])

    def test_non_json_safe_tokens_normalize_to_json_safe_failure(self):
        graph, _, record = self._run_result(
            lambda assignment: ExecutionResult(
                success=True,
                actual_runtime=assignment.resolved_runtime,
                tokens={"bad": {1, 2}},
            )
        )
        self.assertEqual(graph.summary()["failed"], 1)
        self.assertIs(record["execution_success"], False)
        self.assertIsNone(record["tokens"])
        self.assertIn("not a strict JSON value", record["execution_error"])

    def test_malformed_result_fails_one_package_and_safe_sibling_continues(self):
        @lambda fn: mark_executor(fn, WORKER_SIMULATED)
        def executor(pkg, assignment):
            if pkg.id == "bad":
                return None
            time.sleep(0.02)
            return _valid_result(assignment)

        graph = _graph("bad", "sibling")
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence.jsonl"
            report = Dispatcher(
                _workforce(), executor=executor, evidence_path=evidence,
            ).run(graph)
            records = [
                json.loads(line)
                for line in evidence.read_text().splitlines()
            ]

        self.assertEqual(report.graph_summary["failed"], 1)
        self.assertEqual(report.graph_summary["completed"], 1)
        self.assertEqual({record["work_package_id"] for record in records},
                         {"bad", "sibling"})


class TestEvidenceCompletionBoundary(unittest.TestCase):
    def test_success_is_not_finalized_until_evidence_append_returns(self):
        graph = _graph("ordered")
        dispatcher = Dispatcher(_workforce(), executor=simulated_executor)
        original = dispatcher._record_evidence
        observed = []

        with tempfile.TemporaryDirectory() as tmp:
            dispatcher.evidence_path = Path(tmp) / "evidence.jsonl"

            def observing_sink(assignment):
                observed.append(assignment.work_package_id in graph.completed)
                return original(assignment)

            dispatcher._record_evidence = observing_sink
            report = dispatcher.run(graph)

        self.assertEqual(observed, [False])
        self.assertEqual(report.graph_summary["completed"], 1)

    def test_forced_serialization_failure_is_systemic_and_no_success_remains(self):
        graph = _graph("one", "two")
        dispatcher = Dispatcher(_workforce(), executor=simulated_executor)

        with patch(
            "core.dispatcher.record_assignment_evidence",
            side_effect=EvidenceSerializationError("forced serialization failure"),
        ):
            with self.assertRaises(EvidenceSinkError) as ctx:
                dispatcher.run(graph)

        self.assertEqual(graph.summary()["completed"], 0)
        self.assertEqual(graph.summary()["failed"], 2)
        self.assertEqual(ctx.exception.report.graph_summary["completed"], 0)
        self.assertIn("systemic evidence-sink failure", str(ctx.exception))

    def test_forced_append_failure_is_systemic_and_no_success_remains(self):
        graph = _graph("one", "two")
        dispatcher = Dispatcher(_workforce(), executor=simulated_executor)

        with patch(
            "core.dispatcher.record_assignment_evidence",
            side_effect=OSError("forced append failure"),
        ):
            with self.assertRaises(EvidenceSinkError) as ctx:
                dispatcher.run(graph)

        self.assertEqual(graph.summary()["completed"], 0)
        self.assertEqual(graph.summary()["failed"], 2)
        self.assertEqual(ctx.exception.report.graph_summary["failed"], 2)

    def test_directory_as_evidence_file_fails_closed_systemically(self):
        graph = _graph("one")
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = Dispatcher(
                _workforce(),
                executor=simulated_executor,
                evidence_path=Path(tmp),
            )
            with self.assertRaises(EvidenceSinkError):
                dispatcher.run(graph)

        self.assertEqual(graph.summary()["completed"], 0)
        self.assertEqual(graph.summary()["failed"], 1)


class TestDisclosedProvenanceResiduals(unittest.TestCase):
    def test_functools_wraps_replacement_still_inherits_valid_provenance(self):
        @lambda fn: mark_executor(fn, WORKER_REAL)
        def marked_inner(pkg, assignment):
            raise AssertionError("replacement wrapper must not delegate")

        @functools.wraps(marked_inner)
        def replacement(pkg, assignment):
            return _valid_result(assignment)

        self.assertEqual(executor_provenance(replacement), WORKER_REAL)
        with tempfile.TemporaryDirectory() as tmp:
            report = Dispatcher(
                _workforce(),
                executor=replacement,
                evidence_path=Path(tmp) / "evidence.jsonl",
            ).run(_graph("wraps"))
        self.assertEqual(report.metrics.worker_completed, 1)

    def test_shared_simulated_executor_can_be_remarked_process_wide(self):
        original = executor_provenance(simulated_executor)
        self.addCleanup(mark_executor, simulated_executor, original)
        mark_executor(simulated_executor, MAIN_INLINE)

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence.jsonl"
            report = Dispatcher(
                _workforce(),
                executor=simulated_executor,
                evidence_path=evidence,
            ).run(_graph("remarked"))
            record = json.loads(evidence.read_text())

        self.assertEqual(record["execution_provenance"], MAIN_INLINE)
        self.assertEqual(record["execution_evidence_source"], SIMULATED_LABEL)
        self.assertEqual(report.metrics.main_completed, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
