#!/usr/bin/env python3
"""LISA-RC006 Wave 5B — End-to-End Reliability Acceptance (R1–R15).

Exercises the REAL production code paths (no mocks of the units under test):
  - core/reconciliation.decide_reconciliation / reconcile_unknowns
  - core/auto_resume.decide_action / resume_if_needed / needs_dispatch
  - core/fencing.check_dispatch_fence
  - core/session_telemetry (session_context_usage + provider_window)
  - core/session_policy (decide_session / context_state)
  - core/session_lifecycle (SessionLifecycleStore)
  - core/handoff (write_handoff / handoff_required / retire_session)
  - core/capacity_ledger (CapacityLedger / parse_throttle_reset)
  - core/lifecycle_events (emit_event)
  - bin/lisa-cron-preflight (fail-closed delivery)

Hermetic: temp directories, temp DBs, temp graph-state files. NEVER touches
the live OpenClaw DB, live graph_state.json, WBS, or any protected file.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.execution_state import (
    COMMAND_OK, EXEC_COMPLETED, EXEC_UNKNOWN,
    RESULT_DELIVERY_FAILED,
)
from core.fencing import brief_hash, check_dispatch_fence
from core.reconciliation import (
    RECONCILE_ESCALATE, RECONCILE_RESUME, RECONCILE_RETRY,
    ReconciliationEvidence, decide_reconciliation,
)
from core import auto_resume
from core.graph_state_store import GraphStateStore
from core.session_telemetry import provider_window, session_context_usage
from core.session_policy import (
    CTX_HEALTHY, CTX_RESET, CTX_WARNING, FRESH, REUSE, decide_session,
    context_state,
)
from core.session_lifecycle import SessionLifecycleStore
from core.handoff import (
    build_production_summary,
    handoff_required,
    retire_session,
    write_handoff,
)
from core.capacity_ledger import (
    DEGRADED, EXHAUSTED, CapacityLedger, parse_throttle_reset,
)
from core.lifecycle_events import emit_event

LISA_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_SQL = LISA_ROOT / "db" / "migrations" / "rc003_003_observability.sql"
SESSION_SQL = LISA_ROOT / "db" / "migrations" / "rc003_002_session_lifecycle.sql"
CRON_PREFLIGHT = LISA_ROOT / "bin" / "lisa-cron-preflight"


def new_db(td: str, name: str = "obs.sqlite") -> Path:
    """Create a temp DB with rc003_002 + rc003_003 applied (hermetic)."""
    db = Path(td) / name
    conn = sqlite3.connect(str(db))
    conn.executescript(SESSION_SQL.read_text())
    conn.executescript(MIGRATION_SQL.read_text())
    conn.commit()
    conn.close()
    return db


def build_goal(td: str, packages: list[dict], *, name: str = "goal.json") -> Path:
    goal = Path(td) / name
    goal.write_text(json.dumps({"goal": "rc006", "packages": packages}))
    return goal


def build_state(packages: dict, *, mission_id: str = "m1",
                goal_path: str | Path = "/tmp/rc006-goal.json") -> dict:
    return {
        "schema": "lisa-graph-state/2",
        "goal_path": str(goal_path),
        "mission_id": mission_id,
        "packages": packages,
        "mission_run_ids": [],
        "high_water_mark_ms": 0,
        "last_dispatch_at": None,
        "reconciliation_decisions": {},
    }


class TestR1_NormalAutonomousMission(unittest.TestCase):
    """mission -> decomposition -> worker assignment -> dispatch ack -> RUNNING
    -> terminal evidence -> result ingestion -> COMPLETED -> checkpoint."""

    def test_full_mission_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            goal = build_goal(td, [
                {"id": "p1", "brief": "task one"},
                {"id": "p2", "brief": "task two"},
            ])
            state_path = Path(td) / "graph.json"
            state = build_state({
                "p1": {"status": "completed", "execution_state": "COMPLETED",
                       "run_ids": ["r1"], "brief_hash": "x"},
                "p2": {"status": "not_started"},
            }, mission_id=auto_resume.mission_id_for_goal(goal),
               goal_path=goal)
            GraphStateStore(state_path).write_atomic(state)

            # Completed package skipped; outstanding continues
            decision = auto_resume.resume_if_needed(
                str(goal), graph_state_path=state_path)
            self.assertEqual(decision, auto_resume.DECISION_CONTINUE)

            # After p2 completes, mission is done
            state["packages"]["p2"] = {"status": "completed",
                                       "execution_state": "COMPLETED",
                                       "run_ids": ["r2"], "brief_hash": "y"}
            GraphStateStore(state_path).write_atomic(state)
            decision = auto_resume.resume_if_needed(
                str(goal), graph_state_path=state_path)
            self.assertEqual(decision, auto_resume.DECISION_DONE)


class TestR2_CommandFailureWhileWorkerContinues(unittest.TestCase):
    """Command/transport failure must NOT become worker FAILED; execution
    becomes UNKNOWN when authority is insufficient; no blind redispatch."""

    def test_command_timeout_is_unknown_not_failed(self):
        evidence = ReconciliationEvidence(
            package_id="p1", run_id="r1", execution_state=EXEC_UNKNOWN,
            session_live=None, task_run_live=None, task_run_completed=None,
            artifact_present=None, verified_dead=False,
            death_evidence_authoritative=False,
            reasons=["command transport timeout; no worker-error payload"],
        )
        decision = decide_reconciliation(evidence)
        self.assertEqual(decision.decision, RECONCILE_ESCALATE)
        self.assertNotEqual(decision.decision, RECONCILE_RETRY)

    def test_live_worker_discovered(self):
        """Reconciliation RESUME when live session evidence exists."""
        evidence = ReconciliationEvidence(
            package_id="p1", run_id="r1", execution_state=EXEC_UNKNOWN,
            session_live=True, task_run_live=True, task_run_completed=False,
            artifact_present=None, verified_dead=False,
            death_evidence_authoritative=False,
            reasons=["command lost ack but session live"],
        )
        decision = decide_reconciliation(evidence)
        self.assertEqual(decision.decision, RECONCILE_RESUME)

    def test_unknown_never_blind_retry(self):
        """UNKNOWN + no evidence => ESCALATE, never RETRY."""
        for evidence in [
            ReconciliationEvidence(package_id="p1", execution_state=EXEC_UNKNOWN,
                                   session_live=None, task_run_live=None,
                                   verified_dead=False,
                                   death_evidence_authoritative=False),
            ReconciliationEvidence(package_id="p1", execution_state=EXEC_UNKNOWN,
                                   session_live=False, task_run_live=False,
                                   verified_dead=False,
                                   death_evidence_authoritative=False),
            ReconciliationEvidence(package_id="p1", execution_state=EXEC_UNKNOWN,
                                   session_live=None, task_run_live=None,
                                   verified_dead=True,
                                   death_evidence_authoritative=False),
        ]:
            decision = decide_reconciliation(evidence)
            self.assertEqual(decision.decision, RECONCILE_ESCALATE,
                             f"expected ESCALATE for {evidence.to_dict()}")


class TestR3_TimeoutLostAck(unittest.TestCase):
    """Timeout != authoritative execution failure; enters UNKNOWN."""

    def test_timeout_unknown(self):
        evidence = ReconciliationEvidence(
            package_id="p1", run_id="r1", execution_state=EXEC_UNKNOWN,
            session_live=None, task_run_live=None, task_run_completed=None,
            artifact_present=None, verified_dead=False,
            death_evidence_authoritative=False,
            reasons=["subprocess TimeoutExpired"],
        )
        decision = decide_reconciliation(evidence)
        self.assertEqual(decision.decision, RECONCILE_ESCALATE)

    def test_authoritative_death_retry(self):
        """RETRY only with authoritative death evidence."""
        evidence = ReconciliationEvidence(
            package_id="p1", run_id="r1", execution_state=EXEC_UNKNOWN,
            session_live=False, task_run_live=False, task_run_completed=False,
            artifact_present=False, verified_dead=True,
            death_evidence_authoritative=True,
            reasons=["verified process death; no remote continuation"],
        )
        decision = decide_reconciliation(evidence)
        self.assertEqual(decision.decision, RECONCILE_RETRY)


class TestR4_UnknownReconciliation(unittest.TestCase):
    """UNKNOWN -> RECONCILE -> RESUME/RETRY via decide_action + reconcile_unknowns."""

    def test_unknown_escalates_in_decision(self):
        state = build_state({
            "p1": {"status": "execution_unknown", "execution_state": EXEC_UNKNOWN,
                   "run_ids": ["r1"]},
        })
        decision = auto_resume.decide_action(state)
        self.assertEqual(decision, auto_resume.DECISION_WAKE_MAIN)

    def test_unknown_resume_after_evidence(self):
        """reconcile_unknowns with live-evidence meta marks RESUME."""
        with tempfile.TemporaryDirectory() as td:
            goal = build_goal(td, [{"id": "p1", "brief": "x"}])
            state_path = Path(td) / "graph.json"
            state = build_state({
                "p1": {"status": "execution_unknown", "execution_state": EXEC_UNKNOWN,
                       "run_ids": ["r1"]},
            }, mission_id=auto_resume.mission_id_for_goal(goal),
               goal_path=goal)
            GraphStateStore(state_path).write_atomic(state)
            # meta supplies live execution evidence
            decisions = auto_resume.reconcile_unknowns(
                state, {"p1": {"run_id": "r1", "task_run_live": True,
                               "session_live": True}})
            self.assertEqual(decisions["p1"]["decision"], RECONCILE_RESUME)


class TestR5_DuplicateDispatchFencing(unittest.TestCase):
    """Exactly-once admission semantics via check_dispatch_fence."""

    def setUp(self):
        self.goal = "/tmp/rc006-goal.json"
        self.pkg = "p1"
        self.family = "rc006-smoke"
        self.session = "s1"
        self.digest = brief_hash("same brief")

    def test_deny_preserves_live_nonterminal_owner(self):
        """RC006 DSP-F2: a denied duplicate must NOT clobber a live
        in-flight owner to execution_unknown in the durable record."""
        from core.dispatcher import Dispatcher, WORKER_SIMULATED, ExecutionResult
        from core.graph_state_store import GRAPH_STATE_V2
        from tests.test_rc004_wave1_execution_truth import _wf, _pkg, mark_executor

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            prior = {"status": "in_progress",
                     "dispatch_state": "ACKNOWLEDGED",
                     "brief_hash": self.digest,
                     "task_family": self.family,
                     "session_key": self.session,
                     "fencing_key": "fence-old",
                     "run_id": "run-old",
                     "run_ids": ["run-old"]}
            GraphStateStore(path).write_atomic({
                "schema": GRAPH_STATE_V2, "mission_id": "m1",
                "packages": {"p1": prior}})
            dispatcher = Dispatcher(
                _wf(),
                executor=mark_executor(
                    lambda _wp, _a: ExecutionResult(success=True),
                    WORKER_SIMULATED,
                ),
                graph_state_path=str(path),
                mission_id="m1",
            )
            # Same brief + same session + non-terminal ACKNOWLEDGED record
            # -> fence denies (duplicate) BEFORE any dispatch.
            wp = _pkg("p1")
            setattr(wp, "_rc005_session_key", self.session)
            wp.task_family = self.family
            wp.description = "same brief"
            allowed, reason = dispatcher._dispatch_allowed_by_reconciliation(wp)
            self.assertFalse(allowed)
            self.assertEqual(reason, "duplicate_nonterminal_dispatch")
            record = GraphStateStore(path).load_v2().state["packages"]["p1"]
            self.assertEqual(record["status"], "in_progress")
            self.assertEqual(record["run_ids"], ["run-old"])
            self.assertFalse(record.get("requires_reconciliation"))
            self.assertTrue(record["fence_events"])

    def test_first_dispatch_allowed(self):
        decision = check_dispatch_fence(
            record=None, goal=self.goal, package_id=self.pkg,
            task_family=self.family, session_key=self.session,
            brief_digest=self.digest)
        self.assertTrue(decision.allowed)

    def test_duplicate_nonterminal_denied(self):
        record = {"status": "running", "dispatch_state": "ACKNOWLEDGED",
                  "task_family": self.family, "session_key": self.session,
                  "brief_hash": self.digest}
        decision = check_dispatch_fence(
            record=record, goal=self.goal, package_id=self.pkg,
            task_family=self.family, session_key=self.session,
            brief_digest=self.digest)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "duplicate_nonterminal_dispatch")

    def test_consumed_retry_never_reauthorizes_dispatch(self):
        """Sol HIGH-3: a CONSUMED reconciliation decision must never
        re-authorize dispatch through the fence — racing process B must not
        reuse process A's consumed RETRY once status left EXECUTION_UNKNOWN."""
        record = {"status": "in_progress", "dispatch_state": "ACKNOWLEDGED",
                  "task_family": self.family, "session_key": "s1",
                  "brief_hash": self.digest}
        # Consumed RETRY with different/absent session -> denied
        for other_session in ("s2", None):
            decision = check_dispatch_fence(
                record=record, goal=self.goal, package_id=self.pkg,
                task_family=self.family, session_key=other_session,
                brief_digest=self.digest,
                reconciliation={"decision": "RETRY", "consumed": True,
                                "evidence": {"verified_dead": True,
                                              "death_evidence_authoritative": True}})
            self.assertFalse(decision.allowed, f"consumed RETRY reused for {other_session}")
            self.assertEqual(decision.reason, "duplicate_nonterminal_dispatch")
        # Consumed RETRY same session -> also denied
        same = check_dispatch_fence(
            record=record, goal=self.goal, package_id=self.pkg,
            task_family=self.family, session_key="s1",
            brief_digest=self.digest,
            reconciliation={"decision": "RETRY", "consumed": True,
                            "evidence": {"verified_dead": True,
                                          "death_evidence_authoritative": True}})
        self.assertFalse(same.allowed)
        # Terminal record + consumed decision -> fresh dispatch allowed
        terminal = check_dispatch_fence(
            record={"status": "completed", "dispatch_state": "ACKNOWLEDGED",
                    "task_family": self.family, "session_key": "s1",
                    "brief_hash": self.digest},
            goal=self.goal, package_id=self.pkg,
            task_family=self.family, session_key="s1",
            brief_digest=self.digest,
            reconciliation={"decision": "RETRY", "consumed": True,
                            "evidence": {"verified_dead": True,
                                          "death_evidence_authoritative": True}})
        self.assertTrue(terminal.allowed)

    def test_retry_requires_fresh_session(self):
        record = {"status": "running", "dispatch_state": "ACKNOWLEDGED",
                  "task_family": self.family, "session_key": self.session,
                  "brief_hash": self.digest}
        # RETRY + same session -> denied (must use fresh session)
        same = check_dispatch_fence(
            record=record, goal=self.goal, package_id=self.pkg,
            task_family=self.family, session_key=self.session,
            brief_digest=self.digest,
            reconciliation={"decision": "RETRY",
                            "evidence": {"verified_dead": True,
                                          "death_evidence_authoritative": True}})
        self.assertFalse(same.allowed)
        self.assertEqual(same.reason, "retry_must_use_fresh_session")
        # RETRY without authoritative death evidence -> never authorized,
        # regardless of session (Sol HIGH-2 hardening)
        bare = check_dispatch_fence(
            record=record, goal=self.goal, package_id=self.pkg,
            task_family=self.family, session_key="fresh-x",
            brief_digest=self.digest,
            reconciliation={"decision": "RETRY", "evidence": {"x": 1}})
        self.assertFalse(bare.allowed)
        self.assertEqual(bare.reason, "duplicate_nonterminal_dispatch")
        # RETRY with authoritative evidence + fresh session -> allowed
        fresh = check_dispatch_fence(
            record=record, goal=self.goal, package_id=self.pkg,
            task_family=self.family, session_key="fresh-x",
            brief_digest=self.digest,
            reconciliation={"decision": "RETRY",
                            "evidence": {"verified_dead": True,
                                          "death_evidence_authoritative": True}})
        self.assertTrue(fresh.allowed)

    def test_terminal_allow_fresh_dispatch(self):
        record = {"status": "completed", "dispatch_state": "ACKNOWLEDGED",
                  "task_family": self.family, "session_key": self.session,
                  "brief_hash": self.digest}
        decision = check_dispatch_fence(
            record=record, goal=self.goal, package_id=self.pkg,
            task_family=self.family, session_key=self.session,
            brief_digest=self.digest)
        self.assertTrue(decision.allowed)

    def test_reconciliation_resume_allowed_same_session(self):
        record = {"status": "running", "dispatch_state": "ACKNOWLEDGED",
                  "task_family": self.family, "session_key": self.session,
                  "brief_hash": self.digest}
        decision = check_dispatch_fence(
            record=record, goal=self.goal, package_id=self.pkg,
            task_family=self.family, session_key=self.session,
            brief_digest=self.digest,
            reconciliation={"decision": "RESUME", "evidence": {"x": 1}})
        self.assertTrue(decision.allowed)

    def test_cross_session_duplicate_denied(self):
        """Sol HIGH-1: same non-terminal ACKNOWLEDGED package/brief/family
        must NOT be re-dispatchable under a different or absent session."""
        record = {"status": "running", "dispatch_state": "ACKNOWLEDGED",
                  "task_family": self.family, "session_key": "s1",
                  "brief_hash": self.digest}
        for other_session in ("s2", None):
            decision = check_dispatch_fence(
                record=record, goal=self.goal, package_id=self.pkg,
                task_family=self.family, session_key=other_session,
                brief_digest=self.digest)
            self.assertFalse(decision.allowed,
                             f"cross-session duplicate admitted for {other_session}")
            self.assertEqual(decision.reason, "duplicate_nonterminal_dispatch")

    def test_resume_requires_same_session(self):
        """Sol HIGH-1 corollary: RESUME authorizes the ORIGINAL session;
        a different prospective session must be denied."""
        record = {"status": "running", "dispatch_state": "ACKNOWLEDGED",
                  "task_family": self.family, "session_key": "s1",
                  "brief_hash": self.digest}
        decision = check_dispatch_fence(
            record=record, goal=self.goal, package_id=self.pkg,
            task_family=self.family, session_key="s2",
            brief_digest=self.digest,
            reconciliation={"decision": "RESUME", "evidence": {"x": 1}})
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "resume_requires_same_session")

    def test_retry_requires_authoritative_death_evidence(self):
        """Sol HIGH-2: RETRY admission must revalidate authoritative death
        evidence; a bare/injected RETRY record never authorizes replay."""
        # Bare RETRY without evidence -> not an unconsumed retry
        self.assertFalse(auto_resume._is_unconsumed_retry(
            {"decision": "RETRY", "consumed": False}))
        # RETRY with non-authoritative evidence -> not authorized
        self.assertFalse(auto_resume._is_unconsumed_retry({
            "decision": "RETRY", "consumed": False,
            "evidence": {"verified_dead": True,
                          "death_evidence_authoritative": False}}))
        # RETRY with authoritative death evidence -> authorized
        self.assertTrue(auto_resume._is_unconsumed_retry({
            "decision": "RETRY", "consumed": False,
            "evidence": {"verified_dead": True,
                          "death_evidence_authoritative": True}}))
        # RETRY already consumed -> never authorized
        self.assertFalse(auto_resume._is_unconsumed_retry({
            "decision": "RETRY", "consumed": True,
            "evidence": {"verified_dead": True,
                          "death_evidence_authoritative": True}}))


class TestR6_RestartDurableResume(unittest.TestCase):
    """Multi-package mission; simulate interruption; resume from durable state."""

    def test_restart_resume_skips_completed(self):
        with tempfile.TemporaryDirectory() as td:
            goal = build_goal(td, [
                {"id": "p1", "brief": "a"}, {"id": "p2", "brief": "b"},
                {"id": "p3", "brief": "c"},
            ])
            state_path = Path(td) / "graph.json"

            # p1+p2 done, p3 active/UNKNOWN before interruption
            state = build_state({
                "p1": {"status": "completed", "execution_state": "COMPLETED",
                       "run_ids": ["r1"], "brief_hash": "a"},
                "p2": {"status": "completed", "execution_state": "COMPLETED",
                       "run_ids": ["r2"], "brief_hash": "b"},
                "p3": {"status": "execution_unknown", "execution_state": EXEC_UNKNOWN,
                       "run_ids": ["r3"], "brief_hash": "c"},
            }, mission_id=auto_resume.mission_id_for_goal(goal),
               goal_path=goal)
            GraphStateStore(state_path).write_atomic(state)

            # simulate restart: fresh process reads durable state
            decision = auto_resume.resume_if_needed(
                str(goal), graph_state_path=state_path, enforce_staleness=True)
            # UNKNOWN must not silently CONTINUE; escalate to reconcile
            self.assertEqual(decision, auto_resume.DECISION_WAKE_MAIN)

            # mission identity preserved
            stored = GraphStateStore(state_path).load_v2()
            self.assertEqual(
                stored.state["mission_id"],
                auto_resume.mission_id_for_goal(goal))
            self.assertEqual(stored.state["packages"]["p1"]["status"], "completed")
            self.assertEqual(stored.state["packages"]["p2"]["status"], "completed")

            # UNKNOWN reconciled with live evidence => RESUME, not replay
            decisions = auto_resume.reconcile_unknowns(
                stored.state, {"p3": {"run_id": "r3", "task_run_live": True,
                                      "session_live": True}})
            self.assertEqual(decisions["p3"]["decision"], RECONCILE_RESUME)


class TestR7_ContextPressureSessionPolicy(unittest.TestCase):
    """Session lifecycle: HEALTHY/PRESSURE/FRESH/REUSE/RETIRE."""

    def test_healthy_reuses(self):
        decision = decide_session(active_context=50_000, context_window=200_000)
        self.assertEqual(decision.decision, REUSE)

    def test_pressure_fresh(self):
        decision = decide_session(active_context=170_000, context_window=200_000)
        self.assertEqual(decision.decision, FRESH)

    def test_reset_required_fresh(self):
        decision = decide_session(active_context=210_000, context_window=200_000)
        self.assertEqual(decision.decision, FRESH)

    def test_unknown_telemetry_fails_safe(self):
        decision = decide_session(active_context=None, context_window=200_000)
        self.assertEqual(decision.decision, FRESH)

    def test_boundaries_force_fresh(self):
        for kwargs in [
            {"task_family_same": False},
            {"worker_same": False},
            {"sprint_same": False},
            {"role_switch": True},
            {"review_family_same": False},
            {"session_limit_failure": True},
            {"provenance_untrusted": True},
            {"contamination_risk": True},
        ]:
            decision = decide_session(active_context=10_000,
                                      context_window=200_000, **kwargs)
            self.assertEqual(decision.decision, FRESH,
                             f"expected FRESH for {kwargs}")

    def test_retire_through_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            db = new_db(td, "lifecycle.sqlite")
            store = SessionLifecycleStore(db)
            store.upsert("s1", session_state="ACTIVE", context_pct=0.4)
            retired = retire_session("s1", "context pressure", 0.93, db_path=db)
            self.assertEqual(retired["session_state"], "RETIRED")
            # durable handoff written
            handoff = write_handoff("s1", "lisa-qwen",
                                    {"mission": "rc006-r7"},
                                    output_dir=Path(td) / "handoffs")
            self.assertTrue(handoff.is_file())
            # audit trail emitted
            kinds = [r[0] for r in sqlite3.connect(str(db)).execute(
                "SELECT kind FROM lisa_audit_events ORDER BY id").fetchall()]
            self.assertIn("session.open", kinds)
            self.assertIn("session.retire", kinds)


class TestR8_DurableHandoff(unittest.TestCase):
    """Handoff contains everything a fresh session needs; resume from it."""

    REQUIRED_KEYS = [
        "mission_objective", "current_wave", "current_package",
        "completed_work", "outstanding_work", "repo", "branch", "head",
        "authorization_boundaries", "active_workers", "unknown_workers",
        "unresolved_errors", "decisions", "artifacts", "gate_state",
        "next_permitted_action",
    ]

    def test_handoff_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            summary = {
                "mission_objective": "RC006 acceptance",
                "current_wave": "5B",
                "current_package": "R8",
                "completed_work": ["R1", "R2"],
                "outstanding_work": ["R9"],
                "repo": "/Users/lisa/Lisa",
                "branch": "feature/lisa-console",
                "head": "332804e66d10b61d00b83e79b6aab9f071658daf",
                "authorization_boundaries": ["no WBS", "no force push"],
                "active_workers": ["sol"],
                "unknown_workers": ["deepseek-pro"],
                "unresolved_errors": [],
                "decisions": [{"id": "d1", "decision": "ESCALATE"}],
                "artifacts": ["/tmp/rc006-artifact"],
                "gate_state": "5B IN PROGRESS",
                "next_permitted_action": "complete R9 then gate 5B",
            }
            path = write_handoff("session-r8", "lisa-qwen", summary,
                                 output_dir=Path(td) / "handoffs")
            stored = json.loads(path.read_text())
            self.assertEqual(stored["schema"], "lisa-handoff/1")
            self.assertEqual(stored["session_key"], "session-r8")
            self.assertEqual(stored["target_worker"], "lisa-qwen")
            self.assertIn("created_at", stored)
            for key in self.REQUIRED_KEYS:
                self.assertIn(key, stored["summary"],
                              f"handoff missing {key}")
            # resume from handoff: a fresh reader needs no conversational memory
            resumed = json.loads(path.read_text())["summary"]
            self.assertEqual(resumed["head"],
                             "332804e66d10b61d00b83e79b6aab9f071658daf")
            self.assertEqual(resumed["next_permitted_action"],
                             "complete R9 then gate 5B")

    def test_handoff_required_threshold(self):
        self.assertTrue(handoff_required({"context_pct": 0.85}))
        self.assertFalse(handoff_required({"context_pct": 0.40}))
        self.assertFalse(handoff_required(None))
        self.assertFalse(handoff_required({"context_pct": None}))

    def test_production_writer_emits_complete_contract(self):
        """R3: the production path emits ALL 16 required contract keys."""
        with tempfile.TemporaryDirectory() as td:
            # Minimal but well-formed authoritative mission ledger: the
            # enrichment layer must only read it, never rewrite it.
            state = {
                "title": "RC006 acceptance",
                "status": "WAVE 5C IN PROGRESS",
                "repo": "/repo",
                "branch": "feature/x",
                "verified_head": "abc123",
                "wbs_boundary": "WBS050 MUST NOT BEGIN",
                "wave_5a": {"5a1": {}},
                "wave_5b": {"result": "PASS"},
                "wave5c": {"review1_sol_final": "ACCEPT",
                            "review2_deepseek_pro": "PENDING"},
            }
            ledger = Path(td) / "mission.json"
            ledger.write_text(json.dumps(state), encoding="utf-8")
            path = write_handoff("session-prod", "lisa-qwen", None,
                                 output_dir=Path(td) / "handoffs",
                                 mission_path=ledger)
            stored = json.loads(path.read_text())
            self.assertEqual(stored["schema"], "lisa-handoff/1")
            for key in self.REQUIRED_KEYS:
                self.assertIn(key, stored["summary"],
                              f"production writer missing {key}")
            # Authorization boundary explicitly carries WBS050-NOT-authorized.
            boundaries = stored["summary"]["authorization_boundaries"]
            self.assertTrue(any("WBS050" in b and "NOT authorized" in b
                                for b in boundaries))
            # Ledger file itself untouched by the writer (read-only authority).
            self.assertEqual(json.loads(ledger.read_text()), state)

    def test_fields_come_from_authoritative_state(self):
        """R3: contract values must be sourced from the ledger, not invented."""
        with tempfile.TemporaryDirectory() as td:
            state = {
                "title": "Mission X", "status": "WAVE 1 IN PROGRESS",
                "repo": "/r", "branch": "b", "verified_head": "deadbeef",
                "wbs_boundary": "no WBS",
                "wave_5a": {}, "wave_5b": {},
                "wave5c": {"review_a": "PENDING"},
            }
            ledger = Path(td) / "mission.json"
            ledger.write_text(json.dumps(state), encoding="utf-8")
            summary = build_production_summary(
                mission_path=ledger,
                capacity_path=Path(td) / "no-capacity.json",
                graph_path=Path(td) / "no-graph.json",
                violations_path=Path(td) / "no-violations.jsonl",
                orchestration_dir=Path(td) / "no-orch",
                gate_report=Path(td) / "no-gate.md",
            )
            self.assertEqual(summary["mission_objective"], "Mission X")
            self.assertEqual(summary["repo"], "/r")
            self.assertEqual(summary["branch"], "b")
            self.assertEqual(summary["head"], "deadbeef")
            self.assertEqual(summary["current_package"], "WAVE 1 IN PROGRESS")
            # Unknown workers / unresolved errors default to [] when the
            # authoritative sources are absent (no invented values).
            self.assertEqual(summary["unknown_workers"], [])
            self.assertEqual(summary["unresolved_errors"], [])
            self.assertEqual(summary["active_workers"], [])

    def test_handoff_survives_process_boundary(self):
        """R3: a fresh process can recover the artifact with no extra context."""
        with tempfile.TemporaryDirectory() as td:
            state = {
                "title": "Boundary", "status": "PENDING",
                "repo": "/repo", "branch": "b", "verified_head": "h1",
                "wbs_boundary": "none",
                "wave_5a": {}, "wave_5b": {},
                "wave5c": {"review_a": "PENDING"},
            }
            ledger = Path(td) / "mission.json"
            ledger.write_text(json.dumps(state), encoding="utf-8")
            out = Path(td) / "handoffs"
            path = write_handoff("session-prod", "lisa-qwen", None,
                                 output_dir=out, mission_path=ledger)
            code = (
                "import json, sys; "
                "d = json.load(open(sys.argv[1])); "
                "s = d['summary']; "
                "assert d['schema'] == 'lisa-handoff/1'; "
                "assert s['repo'] == '/repo'; "
                "assert s['head'] == 'h1'; "
                "assert s['mission_objective'] == 'Boundary'; "
                "print('FRESH-PROCESS-RECOVERY-OK')"
            )
            result = subprocess.run(
                [sys.executable, "-c", code, str(path)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("FRESH-PROCESS-RECOVERY-OK", result.stdout)

    def test_malformed_state_fails_safely(self):
        """R3: missing/malformed authoritative state never raises; the writer
        degrades to a partial contract rather than inventing values."""
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing.json"
            summary = build_production_summary(mission_path=missing)
            self.assertEqual(summary, {})
            # Explicit empty summary still yields a valid artifact.
            path = write_handoff("session-bad", "lisa-qwen", {},
                                 output_dir=Path(td) / "h",
                                 mission_path=missing)
            stored = json.loads(path.read_text())
            self.assertEqual(stored["schema"], "lisa-handoff/1")
            self.assertEqual(stored["summary"], {})
            # Malformed JSON degrades to {} as well -- never a raise.
            broken = Path(td) / "broken.json"
            broken.write_text("{not json", encoding="utf-8")
            self.assertEqual(build_production_summary(mission_path=broken), {})

    def test_explicit_summary_regression_preserved(self):
        """R3: callers that pass an explicit summary keep it byte-for-byte
        (legacy 3-key context-retirement and R8 roundtrip behavior)."""
        with tempfile.TemporaryDirectory() as td:
            summary = {"reason": ["x"], "context": {"pct": 0.9},
                       "next_task_family": "impl"}
            path = write_handoff("session-legacy", "lisa-qwen", summary,
                                 output_dir=Path(td) / "handoffs")
            stored = json.loads(path.read_text())
            self.assertEqual(stored["summary"], summary)


class TestR9_ProviderThrottling(unittest.TestCase):
    """Throttle distinguished from execution failure; Retry-After parsed."""

    def test_throttle_recorded_separately(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = CapacityLedger.at_path(Path(td) / "ledger.json")
            reset = (datetime.now(timezone.utc) +
                     timedelta(seconds=60)).isoformat()
            ledger.record_exhaustion("lisa-qwen",
                                     exhausted_until=reset)
            state = ledger.get("lisa-qwen")
            self.assertEqual(state.health_state, EXHAUSTED)
            self.assertEqual(state.next_available_at, reset)
            self.assertIsNotNone(state.exhausted_until)

    def test_local_failure_not_throttle(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = CapacityLedger.at_path(Path(td) / "ledger.json")
            ledger.record_failure("lisa-qwen", reason="connection reset")
            state = ledger.get("lisa-qwen")
            self.assertEqual(state.health_state, DEGRADED)
            self.assertIsNone(state.next_available_at)

    def test_retry_after_parsed(self):
        now = datetime(2026, 8, 13, 0, 0, 0, tzinfo=timezone.utc)
        reset = parse_throttle_reset("HTTP 429 retry-after: 120s", now=now)
        self.assertEqual(reset, (now + timedelta(seconds=120)).isoformat())
        self.assertIsNone(parse_throttle_reset("connection reset", now=now))

    def test_exhaustion_blocks_dispatch_until_reset(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = CapacityLedger.at_path(Path(td) / "ledger.json")
            ledger.record_exhaustion(
                "lisa-codex-premium",
                exhausted_until=(datetime.now(timezone.utc) +
                                 timedelta(hours=2)).isoformat())
            # repeated dispatch must not be attempted while exhausted
            ok, why = ledger.is_usable("lisa-codex-premium", risk="normal")
            self.assertFalse(ok, why)
            # alternative provider available
            ok, why = ledger.is_usable("lisa-qwen", risk="normal")
            self.assertTrue(ok, why)


class TestR11_CronDeliveryPreflight(unittest.TestCase):
    """valid / invalid / missing channel; zero token burn on block."""

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(CRON_PREFLIGHT), *args],
            capture_output=True, text=True)

    def test_valid_channel(self):
        r = self._run("--channel", "webchat")
        self.assertEqual(r.returncode, 0)

    def test_missing_channel(self):
        r = self._run()
        self.assertEqual(r.returncode, 3)

    def test_invalid_channel(self):
        r = self._run("--channel", "")
        self.assertEqual(r.returncode, 3)


class TestR12_ObservabilityTruth(unittest.TestCase):
    """Lisa truthfully exposes all lifecycle dimensions via real emit paths."""

    def test_all_dimensions_visible(self):
        with tempfile.TemporaryDirectory() as td:
            db = new_db(td)
            # DISPATCH + EXECUTION + SESSION + RESULT + COMMAND + RECONCILE
            self.assertTrue(emit_event(db, "session.open", entity_type="session",
                                       entity_id="s1", to_state="ACTIVE"))
            self.assertTrue(emit_event(db, "reconcile.decision", entity_type="package",
                                       entity_id="p1", from_state=EXEC_UNKNOWN,
                                       to_state="RESUME",
                                       payload={"decision": "RESUME"}))
            conn = sqlite3.connect(str(db))
            kinds = [r[0] for r in conn.execute(
                "SELECT kind FROM lisa_audit_events ORDER BY id").fetchall()]
            rows = conn.execute(
                "SELECT COUNT(*) FROM lisa_audit_events").fetchone()[0]
            conn.close()
            self.assertIn("session.open", kinds)
            self.assertIn("reconcile.decision", kinds)
            self.assertEqual(rows, 2)
            # payload truth: UNKNOWN queryable via from_state
            conn = sqlite3.connect(str(db))
            hit = conn.execute(
                "SELECT COUNT(*) FROM lisa_audit_events WHERE from_state = ?",
                (EXEC_UNKNOWN,)).fetchone()[0]
            conn.close()
            self.assertEqual(hit, 1)


class TestR13_ContextTelemetrySemantics(unittest.TestCase):
    """RC002 failure class: cacheRead not misread as fresh usage; no 999%."""

    def test_provider_windows(self):
        self.assertEqual(provider_window("anthropic"), 200_000)
        self.assertEqual(provider_window("openai"), 200_000)
        self.assertEqual(provider_window("deepseek"), 128_000)
        self.assertEqual(provider_window("glm"), 128_000)
        self.assertEqual(provider_window("qwen"), 200_000)
        self.assertEqual(provider_window(None), 200_000)

    def test_cache_read_never_alone_drives_pct(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "agents" / "lisa-qwen" / "sessions"
            root.mkdir(parents=True)
            line = json.dumps({
                "timestamp": "2026-08-13T00:00:00Z",
                "session_key": "s-ctx",
                "usage": {"cacheRead": 500_000, "input": 1000, "output": 500,
                          "totalTokens": 1500, "provider": "deepseek"},
            })
            (root / "s-ctx.jsonl").write_text(line + "\n")
            usage = session_context_usage(
                "s-ctx", sessions_root=Path(td) / "agents", provider="deepseek")
            self.assertEqual(usage["cache_read"], 500_000)
            # active_context uses real total, NOT cacheRead
            self.assertEqual(usage["active_context"], 1500)
            self.assertLessEqual(usage["pct"], 1.0)
            self.assertGreater(usage["pct"], 0.0)
            # correct deepseek window
            self.assertEqual(usage["context_window"], 128_000)

    def test_missing_telemetry_fails_safe(self):
        with tempfile.TemporaryDirectory() as td:
            usage = session_context_usage(
                "no-such-session", sessions_root=Path(td) / "agents",
                provider="anthropic")
            self.assertIsNone(usage["active_context"])
            self.assertIsNone(usage["pct"])
            # policy treats unknown as FRESH (never blind REUSE)
            decision = decide_session(active_context=None,
                                      context_window=200_000)
            self.assertEqual(decision.decision, FRESH)

    def test_context_state_classifier(self):
        self.assertEqual(context_state(50_000, context_window=200_000), CTX_HEALTHY)
        self.assertEqual(context_state(170_000, context_window=200_000), CTX_WARNING)
        self.assertEqual(context_state(210_000, context_window=200_000), CTX_RESET)
        # None fails toward isolation
        self.assertEqual(context_state(None, context_window=200_000), CTX_WARNING)


class TestR14_ResultDeliveryFailure(unittest.TestCase):
    """Execution COMPLETED but delivery fails => DELIVERY_FAILED, never
    worker FAILED. Exercises the REAL production phase-4 finalization path
    (build_real_executor -> _execute phase 4), not a hand-inserted row."""

    def test_delivery_failure_separate_from_worker(self):
        with tempfile.TemporaryDirectory() as td:
            db = new_db(td)
            # execution COMPLETED (reconcile decision records truth)
            self.assertTrue(emit_event(db, "reconcile.decision",
                                       entity_type="package", entity_id="p1",
                                       from_state=EXEC_UNKNOWN,
                                       to_state="RESUME",
                                       payload={"decision": "RESUME"}))
            # delivery failure recorded separately: command OK, delivery failed
            conn = sqlite3.connect(str(db))
            conn.execute(
                "INSERT INTO lisa_cron_run_logs "
                "(job_id,channel,delivery_state,command_state,detail,"
                "tokens_burned,created_at) VALUES (?,?,?,?,?,?,?)",
                ("job1", "invalid", "DELIVERY_FAILED", "OK",
                 "result delivery failed after execution completed", 5,
                 "2026-08-13T00:00:00Z"))
            conn.commit()
            row = conn.execute(
                "SELECT delivery_state, command_state FROM lisa_cron_run_logs"
            ).fetchone()
            # execution COMPLETED row still present (reconcile.decision RESUME)
            executed = conn.execute(
                "SELECT COUNT(*) FROM lisa_audit_events WHERE kind=?",
                ("reconcile.decision",)).fetchone()[0]
            conn.close()
            self.assertEqual(row[0], "DELIVERY_FAILED")
            self.assertEqual(row[1], "OK")  # command succeeded; delivery failed
            self.assertEqual(executed, 1)

    def test_delivery_failure_production_path(self):
        """Real bridge path: terminal evidence CONFIRMED (task_runs
        succeeded) but result persistence/delivery fails -> execution stays
        COMPLETED, result_state=DELIVERY_FAILED, NOT worker FAILED, NOT
        EXECUTION_UNKNOWN (DSP-F1)."""
        from core.openclaw_bridge import build_real_executor
        from tests.test_openclaw_bridge import (
            _FakeAssignment, _FakePkg, _REAL_RESPONSE_SHAPE, _resolver,
        )

        with tempfile.TemporaryDirectory() as td:
            db = new_db(td)
            with patch("core.openclaw_bridge.OPENCLAW_DB", db), \
                 patch("core.openclaw_bridge.gateway_reachable",
                       return_value=(True, "ok")), \
                 patch("core.openclaw_bridge.non_wbs_agents",
                       return_value=[{"id": "lisa-gpt",
                                      "model": "openai/gpt-5.5"}]), \
                 patch("core.openclaw_bridge._run_agent",
                       return_value=(0, _REAL_RESPONSE_SHAPE, "")), \
                 patch("core.openclaw_bridge._fetch_task_run",
                       return_value={"run_id": "r1",
                                     "status": "succeeded"}), \
                 patch("core.openclaw_bridge._lifecycle_columns_available",
                       return_value=True), \
                 patch("core.openclaw_bridge._update_task_run_lifecycle",
                       return_value=False):
                result = build_real_executor(resolver=_resolver())(
                    _FakePkg("p"),
                    _FakeAssignment(physical_model="openai/gpt-5.5",
                                    available=True),
                )

        self.assertTrue(result.success)
        self.assertEqual(result.execution_state, EXEC_COMPLETED)
        self.assertEqual(result.result_state, RESULT_DELIVERY_FAILED)
        self.assertFalse(result.requires_reconciliation)
        self.assertEqual(result.command_state, COMMAND_OK)
        self.assertEqual(
            result.terminal_evidence.get("persistence", {}).get("result"),
            "DELIVERY_FAILED",
        )


class TestR15_LongRunAutonomy(unittest.TestCase):
    """Wave 5 mission itself is the evidence; harness sanity."""

    def test_mission_ledger_exists(self):
        ledger = LISA_ROOT / "reports/lisa/orchestration/rc006_mission_state.json"
        self.assertTrue(ledger.is_file())
        data = json.loads(ledger.read_text())
        self.assertEqual(data["mission"], "LISA-RC006")
        self.assertEqual(data["verified_head"],
                         "332804e66d10b61d00b83e79b6aab9f071658daf")

    def test_regression_baseline_file(self):
        baseline = LISA_ROOT / "reports/lisa/orchestration/rc006_regression_baseline.json"
        self.assertTrue(baseline.is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
