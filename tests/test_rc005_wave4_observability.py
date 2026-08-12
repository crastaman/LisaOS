from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.execution_state import EXEC_UNKNOWN
from core.lifecycle_events import emit_event
from core.reconciliation import (ReconciliationEvidence, decide_reconciliation,
                                 pending_reconciliation_queue)
from core.auto_resume import reconcile_unknowns
from core.session_lifecycle import SessionLifecycleStore
from db.migrate import apply_all

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, SourceFileLoader(name, str(path)))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def observability_db(tmp: str) -> Path:
    db = Path(tmp) / "state.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT)")
    conn.commit(); conn.close()
    apply_all(db, backup=False)
    return db


class TestT12T14CronPreflight(unittest.TestCase):
    def test_absent_channel_records_cron_only_and_burns_zero_tokens(self):
        preflight = load_script("cron_preflight", ROOT / "bin/lisa-cron-preflight")
        with tempfile.TemporaryDirectory() as tmp:
            db = observability_db(tmp)
            allowed, detail = preflight.delivery_preflight(None)
            self.assertFalse(allowed)
            preflight.record_preflight(db, job_id="cron:2c8-test", channel=None,
                                       allowed=allowed, detail=detail)
            conn = sqlite3.connect(db)
            cron = conn.execute("SELECT delivery_state,tokens_burned FROM lisa_cron_run_logs").fetchone()
            task_count = conn.execute("SELECT COUNT(*) FROM task_runs").fetchone()[0]
            conn.close()
        self.assertEqual(cron, ("UNDELIVERABLE", 0))
        self.assertEqual(task_count, 0)

    def test_present_absent_best_effort_matrix(self):
        preflight = load_script("cron_preflight_matrix", ROOT / "bin/lisa-cron-preflight")
        self.assertEqual(preflight.delivery_preflight("telegram:123"), (True, "channel_present"))
        self.assertEqual(preflight.delivery_preflight(None), (False, "channel_absent"))
        self.assertEqual(preflight.delivery_preflight(None, best_effort=True),
                         (True, "best_effort_without_channel"))

    def test_db_error_preserves_fail_closed_exit_three(self):
        preflight = load_script("cron_preflight_error", ROOT / "bin/lisa-cron-preflight")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "native-only.sqlite"
            sqlite3.connect(db).close()
            self.assertEqual(preflight.main(["--db", str(db), "--job-id", "x"]), 3)

    def test_native_schema_coexists_and_apply_all_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "openclaw-shape.sqlite"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT)")
            conn.execute("CREATE TABLE audit_events (sequence INTEGER, event_id TEXT, kind TEXT, action TEXT)")
            conn.execute("CREATE TABLE cron_run_logs (store_key TEXT, job_id TEXT, seq INTEGER, status TEXT)")
            conn.commit(); conn.close()
            apply_all(db, backup=False); apply_all(db, backup=False)
            self.assertTrue(emit_event(db, "session.open", entity_id="s"))
            conn = sqlite3.connect(db)
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            native_audit = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            lisa_audit = conn.execute("SELECT COUNT(*) FROM lisa_audit_events").fetchone()[0]
            conn.close()
        self.assertTrue({"audit_events", "cron_run_logs", "lisa_audit_events",
                         "lisa_cron_run_logs"}.issubset(names))
        self.assertEqual((native_audit, lisa_audit), (0, 1))


class TestT9LifecycleAudit(unittest.TestCase):
    def test_reconcile_default_is_side_effect_free(self):
        state = {"packages": {"p": {"status": "execution_unknown",
                                      "execution_state": EXEC_UNKNOWN}}}
        with patch("core.lifecycle_events.emit_event") as emit:
            decisions = reconcile_unknowns(state)
        self.assertEqual(decisions["p"]["decision"], "ESCALATE")
        emit.assert_not_called()

    def test_auto_resume_caller_emits_reconcile_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = observability_db(tmp)
            state = {"packages": {"p": {"status": "execution_unknown",
                                          "execution_state": EXEC_UNKNOWN}}}
            decisions = reconcile_unknowns(state, event_db_path=db)
            conn = sqlite3.connect(db)
            count = conn.execute("SELECT COUNT(*) FROM lisa_audit_events "
                                 "WHERE kind='reconcile.decision'").fetchone()[0]
            conn.close()
        self.assertEqual(decisions["p"]["decision"], "ESCALATE")
        self.assertEqual(count, 1)

    def test_reconcile_decision_and_unknown_queue_are_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = observability_db(tmp)
            evidence = ReconciliationEvidence(package_id="p", execution_state=EXEC_UNKNOWN)
            decision = decide_reconciliation(evidence, event_db_path=db)
            state = {"packages": {"p": {"status": "execution_unknown"},
                                  "q": {"status": "completed"}}}
            queue = pending_reconciliation_queue(state)
            conn = sqlite3.connect(db)
            event = conn.execute("SELECT kind,entity_id,to_state FROM lisa_audit_events").fetchone()
            conn.close()
        self.assertEqual(decision.decision, "ESCALATE")
        self.assertEqual([item["package_id"] for item in queue], ["p"])
        self.assertEqual(event, ("reconcile.decision", "p", "ESCALATE"))

    def test_session_transitions_emit_kind_scoped_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = observability_db(tmp)
            store = SessionLifecycleStore(db)
            store.upsert("s", session_state="ACTIVE")
            store.mark_throttled("s", throttle_until="later")
            store.upsert("s", session_state="RETIRED", retired_at="now")
            conn = sqlite3.connect(db)
            store.upsert("s", session_state="IDLE")
            kinds = [row[0] for row in conn.execute("SELECT kind FROM lisa_audit_events ORDER BY id")]
            conn.close()
        self.assertEqual(kinds, ["session.open", "session.throttle", "session.retire",
                                 "session.reuse"])


class TestReconcileFourDimensions(unittest.TestCase):
    def test_four_dimensions_include_session_jsonl_ground_truth(self):
        reconcile = load_script("lisa_reconcile_wave4", ROOT / "bin/lisa-reconcile")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            session = home / "agents/a/sessions/s.jsonl"; session.parent.mkdir(parents=True)
            session.write_text(json.dumps({"session_key": "agent:a:s"}) + "\n")
            old = reconcile.OPENCLAW_HOME; reconcile.OPENCLAW_HOME = home
            try:
                dims = reconcile._four_dimensions({}, {"dispatch_state": "ACKNOWLEDGED",
                    "execution_state": "COMPLETED", "session_state": "IDLE",
                    "result_state": "INGESTED", "session_key": "agent:a:s"})
            finally:
                reconcile.OPENCLAW_HOME = old
        self.assertEqual(dims["dispatch"], "ACKNOWLEDGED")
        self.assertTrue(dims["session"]["jsonl_seen"])
        self.assertEqual(dims["result"], "INGESTED")


if __name__ == "__main__":
    unittest.main()
