"""Proof-of-work tests for the LisaOS governance detection backstop (Phase 6).

Run:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_governance_detector -v

Fully hermetic: every test builds a throwaway sqlite database shaped like
OpenClaw's `task_runs` and throwaway evidence ledgers in a tempdir. No network,
no OpenClaw, no spend, and the real machine state is never read.

Covers: valid governed execution, missing evidence, bypass attempts, false
positives, repeated violations, the acknowledgement flow, deterministic output,
and the guarantee that detection never mutates evidence.
"""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.governance_detector import (
    DEFAULT_RUNTIMES, GovernanceDetectionError, GovernanceViolation,
    SEVERITY_CRITICAL, SEVERITY_WARNING, acknowledge, build_governance_report,
    detect_violations, evidence_run_ids, governed_signal,
    load_observed_activity, record_violations, render_governance_report,
    report_to_json, require_clean_execution, scan, severity_for,
    unacknowledged, violation_id_for,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_db(tmp: str, rows) -> str:
    """A throwaway database shaped like OpenClaw's task_runs table."""
    path = Path(tmp) / "openclaw.sqlite"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, agent_id TEXT, "
        "runtime TEXT, status TEXT, task TEXT, created_at INTEGER)")
    conn.executemany(
        "INSERT INTO task_runs (run_id, agent_id, runtime, status, task, created_at) "
        "VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return str(path)


_GOVERNED_TASK = ("S046 — implement the appointment module and run the test suite, "
                  "then commit the result")
_READ_ONLY_TASK = "Explain what the Lisa dispatcher does and how it routes work"


def _row(run_id, task=_GOVERNED_TASK, agent="lisa-claude-sonnet", runtime="cli",
         status="succeeded", created=1785860000000):
    return (run_id, agent, runtime, status, task, created)


def _evidence(tmp: str, run_ids, name="workforce_evidence.jsonl", key="execution_run_id"):
    path = Path(tmp) / name
    path.write_text("\n".join(
        json.dumps({key: rid, "work_package_id": f"pkg-{i}"})
        for i, rid in enumerate(run_ids)) + ("\n" if run_ids else ""))
    return str(path)


# --------------------------------------------------------------------------- #
# Observation
# --------------------------------------------------------------------------- #

class TestObservation(unittest.TestCase):

    def test_reads_task_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1"), _row("r2")])
            observed = load_observed_activity(db)
            self.assertEqual([a.run_id for a in observed], ["r1", "r2"])
            self.assertEqual(observed[0].agent_id, "lisa-claude-sonnet")
            self.assertEqual(observed[0].source, "openclaw.task_runs")

    def test_absent_database_yields_nothing(self):
        """A backstop that cannot see must not pretend to protect."""
        self.assertEqual(load_observed_activity("/nonexistent/openclaw.sqlite"), [])

    def test_unreadable_database_yields_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            junk = Path(tmp) / "not-a-db.sqlite"
            junk.write_text("this is not sqlite")
            self.assertEqual(load_observed_activity(junk), [])

    def test_cron_runtime_excluded_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1", runtime="cron"), _row("r2", runtime="cli")])
            self.assertEqual([a.run_id for a in load_observed_activity(db)], ["r2"])

    def test_runtime_filter_can_be_widened(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1", runtime="cron")])
            self.assertEqual(len(load_observed_activity(db, runtimes=())), 1)

    def test_since_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("old", created=1000), _row("new", created=9000)])
            observed = load_observed_activity(db, since_ms=5000)
            self.assertEqual([a.run_id for a in observed], ["new"])

    def test_timestamp_comes_from_the_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1", created=1785860000000)])
            self.assertTrue(load_observed_activity(db)[0].observed_at.startswith("2026-"))

    def test_malformed_timestamp_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [("r1", "a", "cli", "ok", "t", None)])
            self.assertEqual(load_observed_activity(db)[0].observed_at, "unknown")


class TestEvidenceCorrelation(unittest.TestCase):

    def test_reads_run_ids_from_workforce_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _evidence(tmp, ["r1", "r2"])
            self.assertEqual(evidence_run_ids(workforce_evidence=path,
                                              work_product_index="/nonexistent"),
                             {"r1", "r2"})

    def test_reads_run_ids_from_work_product_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _evidence(tmp, ["r3"], name="index.jsonl", key="run_id")
            self.assertEqual(evidence_run_ids(workforce_evidence="/nonexistent",
                                              work_product_index=path), {"r3"})

    def test_corrupt_line_does_not_hide_other_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ev.jsonl"
            path.write_text('{"execution_run_id": "r1"}\n{corrupt\n'
                            '{"execution_run_id": "r2"}\n')
            self.assertEqual(evidence_run_ids(workforce_evidence=path,
                                              work_product_index="/nonexistent"),
                             {"r1", "r2"})

    def test_absent_ledgers_yield_empty(self):
        self.assertEqual(evidence_run_ids(workforce_evidence="/nonexistent/a",
                                          work_product_index="/nonexistent/b"), set())


# --------------------------------------------------------------------------- #
# Governed-shape detection and the false-positive asymmetry
# --------------------------------------------------------------------------- #

class TestGovernedSignal(unittest.TestCase):

    def test_sprint_implementation_is_governed(self):
        governed, rules, _ = governed_signal(_GOVERNED_TASK)
        self.assertTrue(governed)
        self.assertIn("G5_SPRINT_REFERENCE", rules)

    def test_explanation_is_not_governed(self):
        governed, rules, _ = governed_signal(_READ_ONLY_TASK)
        self.assertFalse(governed)
        self.assertEqual(rules, [])

    def test_ordinary_conversation_is_not_governed(self):
        for text in ("what is the status of the appointments module?",
                     "how does the dispatcher choose a worker?",
                     "summarise yesterday's architectural discussion",
                     "why did we choose the observed/declared split?",
                     "show me the roadmap"):
            governed, _, _ = governed_signal(text)
            self.assertFalse(governed, f"false positive on: {text!r}")

    def test_ambiguous_text_is_never_a_violation_signal(self):
        """Intake defaults ambiguity to GOVERNED; detection must NOT.

        This asymmetry is the core false-positive control: being wrong at
        intake merely over-governs, but being wrong here blocks real work and
        accuses an operator of a bypass.
        """
        from core.task_classifier import classify
        text = "zzzz qqqq wobble"
        self.assertEqual(classify(text).classification, "GOVERNED")
        self.assertEqual(classify(text).matched_rules, ["DEFAULT_GOVERNED_AMBIGUOUS"])
        governed, rules, reason = governed_signal(text)
        self.assertFalse(governed)
        self.assertIn("ambiguous", reason)

    def test_empty_task_is_not_governed(self):
        self.assertFalse(governed_signal("")[0])

    def test_severity_reflects_change_making(self):
        self.assertEqual(severity_for(["G1_REPO_WRITE"]), SEVERITY_CRITICAL)
        self.assertEqual(severity_for(["G2_EXECUTION_MUTATION"]), SEVERITY_CRITICAL)
        self.assertEqual(severity_for(["G5_SPRINT_REFERENCE"]), SEVERITY_WARNING)
        self.assertEqual(severity_for(["G3_WORK_TYPE", "G4_MULTI_DOMAIN"]),
                         SEVERITY_WARNING)


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #

class TestDetection(unittest.TestCase):

    def test_governed_work_with_evidence_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1")])
            observed = load_observed_activity(db)
            self.assertEqual(detect_violations(observed, evidence_ids={"r1"}), [])

    def test_governed_work_without_evidence_is_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1")])
            violations = detect_violations(load_observed_activity(db), evidence_ids=set())
            self.assertEqual(len(violations), 1)
            violation = violations[0]
            self.assertEqual(violation.severity, SEVERITY_CRITICAL)
            self.assertIn("workforce_evidence", violation.missing_evidence)
            self.assertIn("no LisaOS evidence", violation.reason)
            self.assertEqual(violation.observed_activity["run_id"], "r1")

    def test_read_only_work_without_evidence_is_not_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1", task=_READ_ONLY_TASK)])
            self.assertEqual(
                detect_violations(load_observed_activity(db), evidence_ids=set()), [])

    def test_bypass_on_main_agent_detected(self):
        """The S046 failure mode: a mission pasted into a chat session."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1", agent="main", runtime="tui")])
            violations = detect_violations(load_observed_activity(db), evidence_ids=set())
            self.assertEqual(len(violations), 1)
            self.assertEqual(violations[0].observed_activity["agent_id"], "main")

    def test_manual_worker_dispatch_is_also_a_bypass(self):
        """Invoking a lisa-* agent by hand still skips LisaOS intake."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1", agent="lisa-codex")])
            self.assertEqual(
                len(detect_violations(load_observed_activity(db), evidence_ids=set())), 1)

    def test_mixed_population_only_flags_the_uncorrelated(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [
                _row("governed-1"), _row("bypass-1"),
                _row("chat-1", task=_READ_ONLY_TASK), _row("governed-2"),
            ])
            violations = detect_violations(load_observed_activity(db),
                                           evidence_ids={"governed-1", "governed-2"})
            self.assertEqual([v.observed_activity["run_id"] for v in violations],
                             ["bypass-1"])

    def test_violation_id_is_deterministic(self):
        self.assertEqual(violation_id_for("r1"), violation_id_for("r1"))
        self.assertNotEqual(violation_id_for("r1"), violation_id_for("r2"))

    def test_repeated_scans_produce_identical_violations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1"), _row("r2")])
            observed = load_observed_activity(db)
            first = [v.to_dict() for v in detect_violations(observed, evidence_ids=set())]
            second = [v.to_dict() for v in detect_violations(observed, evidence_ids=set())]
            self.assertEqual(first, second)

    def test_violation_carries_the_full_phase6_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1")])
            violation = detect_violations(load_observed_activity(db),
                                          evidence_ids=set())[0].to_dict()
            for key in ("violation_id", "timestamp", "reason", "governing_rule",
                        "observed_activity", "missing_evidence", "severity",
                        "acknowledged", "acknowledged_by", "schema_version"):
                self.assertIn(key, violation, key)

    def test_timestamp_is_observed_not_wall_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1", created=1785860000000)])
            violation = detect_violations(load_observed_activity(db), evidence_ids=set())[0]
            self.assertEqual(violation.timestamp,
                             load_observed_activity(db)[0].observed_at)


# --------------------------------------------------------------------------- #
# Acknowledgement flow
# --------------------------------------------------------------------------- #

class TestAcknowledgement(unittest.TestCase):

    def _violation(self, run_id="r1"):
        return GovernanceViolation(
            violation_id=violation_id_for(run_id), timestamp="2026-08-05T00:00:00+00:00",
            reason="test", governing_rule=["G1_REPO_WRITE"],
            observed_activity={"run_id": run_id}, missing_evidence=["workforce_evidence"],
            severity=SEVERITY_CRITICAL)

    def test_unacknowledged_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            ack = Path(tmp) / "acks.jsonl"
            self.assertEqual(len(unacknowledged([self._violation()], ack_path=ack)), 1)

    def test_acknowledgement_clears_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            ack = Path(tmp) / "acks.jsonl"
            violation = self._violation()
            acknowledge([violation.violation_id], operator="lisa",
                        reason="reviewed historical bypass", path=ack)
            self.assertEqual(unacknowledged([violation], ack_path=ack), [])

    def test_acknowledgement_is_attributed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ack = Path(tmp) / "acks.jsonl"
            acknowledge(["abc"], operator="roshan", reason="known migration", path=ack)
            record = json.loads(ack.read_text().splitlines()[0])
            self.assertEqual(record["operator"], "roshan")
            self.assertEqual(record["reason"], "known migration")
            self.assertIn("abc", record["violation_ids"])

    def test_acknowledgement_requires_an_operator(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                acknowledge(["abc"], operator="", reason="r", path=Path(tmp) / "a.jsonl")

    def test_acknowledging_one_does_not_clear_another(self):
        with tempfile.TemporaryDirectory() as tmp:
            ack = Path(tmp) / "acks.jsonl"
            first, second = self._violation("r1"), self._violation("r2")
            acknowledge([first.violation_id], operator="lisa", reason="ok", path=ack)
            pending = unacknowledged([first, second], ack_path=ack)
            self.assertEqual([v.violation_id for v in pending], [second.violation_id])

    def test_violations_ledger_is_append_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "violations.jsonl"
            record_violations([self._violation("r1")], path=log)
            record_violations([self._violation("r2")], path=log)
            self.assertEqual(len(log.read_text().strip().splitlines()), 2)


# --------------------------------------------------------------------------- #
# Fail-closed gate
# --------------------------------------------------------------------------- #

class TestGate(unittest.TestCase):

    def test_clean_state_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1")])
            evidence = _evidence(tmp, ["r1"])
            result = require_clean_execution(
                db_path=db, workforce_evidence=evidence,
                work_product_index="/nonexistent", ack_path=Path(tmp) / "a.jsonl",
                violations_path=Path(tmp) / "v.jsonl")
            self.assertEqual(result, [])

    def test_violation_blocks_and_never_continues_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1")])
            with self.assertRaises(GovernanceDetectionError) as ctx:
                require_clean_execution(
                    db_path=db, workforce_evidence="/nonexistent",
                    work_product_index="/nonexistent", ack_path=Path(tmp) / "a.jsonl",
                    violations_path=Path(tmp) / "v.jsonl")
            self.assertEqual(len(ctx.exception.violations), 1)
            self.assertIn("blocked", str(ctx.exception))

    def test_gate_records_violations_it_blocks_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1")])
            log = Path(tmp) / "v.jsonl"
            with self.assertRaises(GovernanceDetectionError):
                require_clean_execution(
                    db_path=db, workforce_evidence="/nonexistent",
                    work_product_index="/nonexistent",
                    ack_path=Path(tmp) / "a.jsonl", violations_path=log)
            self.assertTrue(log.is_file())

    def test_acknowledgement_unblocks_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1")])
            ack = Path(tmp) / "a.jsonl"
            acknowledge([violation_id_for("r1")], operator="lisa",
                        reason="reviewed", path=ack)
            result = require_clean_execution(
                db_path=db, workforce_evidence="/nonexistent",
                work_product_index="/nonexistent", ack_path=ack,
                violations_path=Path(tmp) / "v.jsonl")
            self.assertEqual(len(result), 1)
            self.assertTrue(result[0].acknowledged)

    def test_absent_observation_source_leaves_gate_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                require_clean_execution(
                    db_path="/nonexistent/openclaw.sqlite",
                    workforce_evidence="/nonexistent", work_product_index="/nonexistent",
                    ack_path=Path(tmp) / "a.jsonl", violations_path=Path(tmp) / "v.jsonl"),
                [])


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

class TestReporting(unittest.TestCase):

    def _violations(self, tmp, count=2):
        db = _make_db(tmp, [_row(f"r{i}") for i in range(count)])
        return detect_violations(load_observed_activity(db), evidence_ids=set())

    def test_clean_report(self):
        report = build_governance_report([], scanned=5)
        self.assertEqual(report["counts"]["violations"], 0)
        self.assertIn("No governance violations detected",
                      render_governance_report(report))

    def test_report_lists_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_governance_report(self._violations(tmp), scanned=2)
            entry = report["violations"][0]
            for key in ("detected_rule", "evidence_found", "evidence_missing",
                        "classification", "recommended_operator_action"):
                self.assertIn(key, entry, key)
            self.assertEqual(entry["classification"], "GOVERNED_WORK_WITHOUT_EVIDENCE")

    def test_report_statements_are_traceable(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_governance_report(self._violations(tmp))
            for entry in report["violations"]:
                for item in entry["statements"]:
                    self.assertTrue(item["source"].strip())
                    self.assertIn(item["label"], ("OBSERVED", "MISSING"))

    def test_report_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            violations = self._violations(tmp)
            self.assertEqual(report_to_json(build_governance_report(violations)),
                             report_to_json(build_governance_report(violations)))

    def test_report_has_no_wall_clock_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = report_to_json(build_governance_report(self._violations(tmp)))
            for forbidden in ("generated_at", "detected_at", "scanned_at"):
                self.assertNotIn(forbidden, text, forbidden)

    def test_rendered_report_states_it_does_not_decide(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = render_governance_report(build_governance_report(self._violations(tmp)))
            self.assertIn("does not decide how the work should proceed", text)

    def test_render_rejects_a_non_report(self):
        with self.assertRaises(GovernanceDetectionError):
            render_governance_report({"not": "a report"})

    def test_scan_is_read_only_over_the_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp, [_row("r1")])
            before = Path(db).read_bytes()
            scan(db_path=db, workforce_evidence="/nonexistent",
                 work_product_index="/nonexistent", ack_path=Path(tmp) / "a.jsonl")
            self.assertEqual(Path(db).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
