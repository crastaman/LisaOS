"""Tests for LISA-I010: internal runtime provenance + ledger chronology repair.

Run:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_internal_runs -v

Fully hermetic: throwaway sqlite shaped like OpenClaw's `task_runs`, throwaway
ledgers and plan artifacts in tempdirs. No network, no OpenClaw, no spend, and
the real machine state is never read or written.

Covers the sprint's Tests 1-6: correlated internal planner call, fake internal
claim, normal governed worker, genuine bypass, blocked ledger sequence, and
successful ledger sequence.
"""

import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.governance_detector import (
    detect_violations, load_observed_activity, scan,
)
from core.internal_runs import (
    EVIDENCE_EXPECTATIONS, PROVENANCE_SCHEMA_VERSION,
    RUN_KIND_INTERNAL_PLANNER, RUN_KIND_WORK_PACKAGE_WORKER,
    load_internal_runs, record_internal_run, verify_internal_run,
)

LISA_BIN = str(Path(__file__).resolve().parent.parent / "bin" / "lisa")
LISA_HOME = str(Path(__file__).resolve().parent.parent)

_GOVERNED = ("S099 — implement the billing module, run the tests and commit "
             "the result")
_PLANNER_PROMPT = ("You are a work-package decomposition engine for LisaOS. "
                   "Your output MUST be ONLY a valid JSON array. Mission: "
                   "S099 implement the billing module and run tests")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_db(tmp, rows):
    path = Path(tmp) / "openclaw.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, agent_id TEXT, "
                 "runtime TEXT, status TEXT, task TEXT, created_at INTEGER)")
    conn.executemany("INSERT INTO task_runs VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return str(path)


def _row(run_id, task=_GOVERNED, agent="lisa-claude-sonnet", runtime="cli"):
    return (run_id, agent, runtime, "succeeded", task, 1785860000000)


def _intake(tmp, request_ids):
    path = Path(tmp) / "intake.jsonl"
    path.write_text("".join(
        json.dumps({"request_id": r, "status": "PLAN_READY", "mission": "m"}) + "\n"
        for r in request_ids))
    return str(path)


def _plans(tmp, request_ids):
    plans = Path(tmp) / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    for r in request_ids:
        (plans / f"{r}.json").write_text('[{"id": "p1"}]')
    return str(plans)


# --------------------------------------------------------------------------- #
# The provenance contract itself
# --------------------------------------------------------------------------- #

class TestProvenanceContract(unittest.TestCase):

    def test_record_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "internal_runs.jsonl"
            record = record_internal_run("run-1", request_id="req-1", path=log)
            self.assertEqual(record["run_kind"], RUN_KIND_INTERNAL_PLANNER)
            self.assertEqual(record["schema_version"], PROVENANCE_SCHEMA_VERSION)
            self.assertFalse(record["work_product_expected"])
            self.assertEqual(record["evidence_expected"], "planning_artifact")
            loaded = load_internal_runs(log)
            self.assertEqual(loaded["run-1"]["request_id"], "req-1")

    def test_unknown_run_kind_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                record_internal_run("r", run_kind="whatever", request_id="x",
                                    path=Path(tmp) / "l.jsonl")

    def test_empty_run_id_records_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "l.jsonl"
            self.assertIsNone(record_internal_run("", request_id="x", path=log))
            self.assertFalse(log.exists())

    def test_unwritable_ledger_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "blocked"
            blocker.write_text("i am a file")
            self.assertIsNone(
                record_internal_run("r", request_id="x", path=blocker / "l.jsonl"))

    def test_corrupt_ledger_line_does_not_hide_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "l.jsonl"
            record_internal_run("r1", request_id="q1", path=log)
            with log.open("a") as fh:
                fh.write("{not json\n")
            record_internal_run("r2", request_id="q2", path=log)
            self.assertEqual(set(load_internal_runs(log)), {"r1", "r2"})

    def test_worker_kind_expects_a_work_product(self):
        self.assertTrue(
            EVIDENCE_EXPECTATIONS[RUN_KIND_WORK_PACKAGE_WORKER]["work_product_expected"])

    def test_verification_requires_intake_and_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = {"run_kind": RUN_KIND_INTERNAL_PLANNER, "request_id": "req-1"}
            ok, missing = verify_internal_run(
                record, intake_path=_intake(tmp, ["req-1"]),
                plans_dir=_plans(tmp, ["req-1"]))
            self.assertTrue(ok, missing)

    def test_verification_fails_without_intake_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, missing = verify_internal_run(
                {"run_kind": RUN_KIND_INTERNAL_PLANNER, "request_id": "ghost"},
                intake_path=_intake(tmp, ["other"]), plans_dir=_plans(tmp, ["ghost"]))
            self.assertFalse(ok)
            self.assertIn("intake_record", missing)

    def test_verification_fails_without_planning_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, missing = verify_internal_run(
                {"run_kind": RUN_KIND_INTERNAL_PLANNER, "request_id": "req-1"},
                intake_path=_intake(tmp, ["req-1"]), plans_dir=_plans(tmp, []))
            self.assertFalse(ok)
            self.assertIn("planning_artifact", missing)

    def test_verification_fails_without_request_id(self):
        ok, missing = verify_internal_run({"run_kind": RUN_KIND_INTERNAL_PLANNER,
                                           "request_id": None})
        self.assertFalse(ok)


# --------------------------------------------------------------------------- #
# Test 1 — correlated internal planner call
# --------------------------------------------------------------------------- #

class TestCorrelatedInternalPlanner(unittest.TestCase):

    def test_correlated_planner_run_creates_no_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("planner-run", task=_PLANNER_PROMPT)])
            log = Path(tmp) / "internal.jsonl"
            record_internal_run("planner-run", request_id="req-1", path=log)

            violations = detect_violations(
                load_observed_activity(db), evidence_ids=set(),
                internal_runs=load_internal_runs(log),
                intake_path=_intake(tmp, ["req-1"]), plans_dir=_plans(tmp, ["req-1"]))
            self.assertEqual(violations, [],
                             "a correctly correlated planner run must not violate")

    def test_planner_run_needs_no_work_product(self):
        """The whole point: work-product evidence is never demanded of it."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("planner-run", task=_PLANNER_PROMPT)])
            log = Path(tmp) / "internal.jsonl"
            record_internal_run("planner-run", request_id="req-1", path=log)
            violations = scan(
                db_path=db, workforce_evidence="/nonexistent",
                work_product_index="/nonexistent", ack_path=Path(tmp) / "a.jsonl",
                internal_runs_path=log, intake_path=_intake(tmp, ["req-1"]),
                plans_dir=_plans(tmp, ["req-1"]))
            self.assertEqual(violations, [])


# --------------------------------------------------------------------------- #
# Test 2 — fake internal claim
# --------------------------------------------------------------------------- #

class TestFakeInternalClaim(unittest.TestCase):

    def test_uncorroborated_claim_still_violates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("liar", task=_PLANNER_PROMPT)])
            log = Path(tmp) / "internal.jsonl"
            record_internal_run("liar", request_id="never-existed", path=log)

            violations = detect_violations(
                load_observed_activity(db), evidence_ids=set(),
                internal_runs=load_internal_runs(log),
                intake_path=_intake(tmp, ["other"]), plans_dir=_plans(tmp, ["other"]))
            self.assertEqual(len(violations), 1)
            violation = violations[0]
            self.assertEqual(violation.governing_rule, ["P1_UNCORROBORATED_PROVENANCE"])
            self.assertIn("intake_record", violation.missing_evidence)
            self.assertIn("planning_artifact", violation.missing_evidence)
            self.assertIn("grants no exemption", violation.reason)

    def test_claim_with_intake_but_no_plan_still_violates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("half", task=_PLANNER_PROMPT)])
            log = Path(tmp) / "internal.jsonl"
            record_internal_run("half", request_id="req-1", path=log)
            violations = detect_violations(
                load_observed_activity(db), evidence_ids=set(),
                internal_runs=load_internal_runs(log),
                intake_path=_intake(tmp, ["req-1"]), plans_dir=_plans(tmp, []))
            self.assertEqual(len(violations), 1)
            self.assertEqual(violations[0].missing_evidence, ["planning_artifact"])

    def test_no_blanket_exemption_by_agent_or_prompt(self):
        """An identical planner-shaped prompt on the planner agent, with NO
        provenance record, is still a violation."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("unrecorded", task=_PLANNER_PROMPT,
                                     agent="lisa-claude-sonnet")])
            violations = detect_violations(
                load_observed_activity(db), evidence_ids=set(), internal_runs={},
                intake_path=_intake(tmp, ["req-1"]), plans_dir=_plans(tmp, ["req-1"]))
            self.assertEqual(len(violations), 1)


# --------------------------------------------------------------------------- #
# Tests 3 & 4 — worker correlation and genuine bypass unchanged
# --------------------------------------------------------------------------- #

class TestExistingCorrelationIntact(unittest.TestCase):

    def test_worker_with_evidence_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("worker-1")])
            self.assertEqual(
                detect_violations(load_observed_activity(db),
                                  evidence_ids={"worker-1"}, internal_runs={}), [])

    def test_worker_without_evidence_still_violates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("worker-1")])
            violations = detect_violations(load_observed_activity(db),
                                           evidence_ids=set(), internal_runs={})
            self.assertEqual(len(violations), 1)
            self.assertIn("workforce_evidence", violations[0].missing_evidence)

    def test_genuine_bypass_on_main_still_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("bypass", agent="main", runtime="tui")])
            violations = detect_violations(load_observed_activity(db),
                                           evidence_ids=set(), internal_runs={})
            self.assertEqual(len(violations), 1)
            self.assertEqual(violations[0].observed_activity["agent_id"], "main")

    def test_read_only_conversation_still_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("chat", task="Explain how the dispatcher works")])
            self.assertEqual(
                detect_violations(load_observed_activity(db), evidence_ids=set(),
                                  internal_runs={}), [])

    def test_mixed_population(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [
                _row("planner", task=_PLANNER_PROMPT), _row("worker-ok"),
                _row("bypass"), _row("chat", task="what is the status?"),
            ])
            log = Path(tmp) / "internal.jsonl"
            record_internal_run("planner", request_id="req-1", path=log)
            violations = detect_violations(
                load_observed_activity(db), evidence_ids={"worker-ok"},
                internal_runs=load_internal_runs(log),
                intake_path=_intake(tmp, ["req-1"]), plans_dir=_plans(tmp, ["req-1"]))
            self.assertEqual([v.observed_activity["run_id"] for v in violations],
                             ["bypass"])


# --------------------------------------------------------------------------- #
# Tests 5 & 6 — intake ledger chronology
# --------------------------------------------------------------------------- #

def _run_lisa(args, env=None):
    base = {**os.environ, "PYTHONPATH": LISA_HOME,
            "LISA_GOVERNANCE_DB": "/nonexistent/openclaw-test.sqlite"}
    if env:
        base.update(env)
    return subprocess.run([sys.executable, LISA_BIN] + args,
                          capture_output=True, text=True, env=base)


def _stub_dispatch(tmp, exit_code=0):
    stub = Path(tmp) / "stub-dispatch"
    argv_file = Path(tmp) / "stub-argv.txt"
    stub.write_text(f'#!/bin/sh\necho "$@" > {argv_file}\nexit {exit_code}\n')
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(stub), argv_file


def _goal(tmp):
    goal = [{"id": "pkg-a", "description": "Read the codebase and report findings",
             "required_capabilities": ["documentation"], "risk": "low",
             "mode": "balanced", "depends_on": []}]
    path = Path(tmp) / "goal.json"
    path.write_text(json.dumps(goal))
    return str(path)


def _statuses(intake_path):
    p = Path(intake_path)
    if not p.exists():
        return []
    return [json.loads(line)["status"]
            for line in p.read_text().splitlines() if line.strip()]


class TestLedgerChronology(unittest.TestCase):

    def test_successful_sequence_records_dispatched_only_after_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub, argv_file = _stub_dispatch(tmp)
            result = _run_lisa(
                ["S099 audit the billing module", "--goal", _goal(tmp),
                 "--intake-path", str(intake)],
                env={"LISA_TEST_MODE": "1", "LISA_DISPATCH_CMD": stub})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            statuses = _statuses(intake)
            self.assertEqual(
                statuses,
                ["GOVERNANCE_CHECK_STARTED", "GOVERNANCE_CHECK_PASSED",
                 "DISPATCH_STARTED", "DISPATCHED", "DISPATCH_COMPLETED"],
                statuses)
            self.assertTrue(argv_file.exists(), "dispatcher was not invoked")

    def test_blocked_sequence_never_claims_dispatch(self):
        """Test 5: a blocked run must not record DISPATCH_STARTED or DISPATCHED."""
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub, argv_file = _stub_dispatch(tmp)
            # A real (tiny) governance DB containing one uncorrelated bypass.
            db = _make_db(tmp, [_row("bypass-run")])
            result = _run_lisa(
                ["S099 audit the billing module", "--goal", _goal(tmp),
                 "--intake-path", str(intake)],
                env={"LISA_TEST_MODE": "1", "LISA_DISPATCH_CMD": stub,
                     "LISA_GOVERNANCE_DB": db})
            self.assertEqual(result.returncode, 9, result.stdout + result.stderr)

            statuses = _statuses(intake)
            self.assertEqual(statuses,
                             ["GOVERNANCE_CHECK_STARTED", "GOVERNANCE_BLOCKED"],
                             statuses)
            self.assertNotIn("DISPATCH_STARTED", statuses)
            self.assertNotIn("DISPATCHED", statuses)
            self.assertFalse(argv_file.exists(),
                             "dispatcher must not be invoked when blocked")

    def test_dispatched_timestamp_is_not_before_dispatch_started(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub, _ = _stub_dispatch(tmp)
            _run_lisa(["S099 audit", "--goal", _goal(tmp),
                       "--intake-path", str(intake)],
                      env={"LISA_TEST_MODE": "1", "LISA_DISPATCH_CMD": stub})
            records = {json.loads(l)["status"]: json.loads(l)
                       for l in Path(intake).read_text().splitlines() if l.strip()}
            self.assertGreaterEqual(records["DISPATCHED"]["timestamp"],
                                    records["DISPATCH_STARTED"]["timestamp"])

    def test_all_ledger_events_share_one_request_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub, _ = _stub_dispatch(tmp)
            _run_lisa(["S099 audit", "--goal", _goal(tmp),
                       "--intake-path", str(intake)],
                      env={"LISA_TEST_MODE": "1", "LISA_DISPATCH_CMD": stub})
            ids = {json.loads(l)["request_id"]
                   for l in Path(intake).read_text().splitlines() if l.strip()}
            self.assertEqual(len(ids), 1, ids)


if __name__ == "__main__":
    unittest.main()
