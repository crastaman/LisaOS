from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.capacity_ledger import (CapacityLedger, EXHAUSTED, ledger_recording_executor,
                                  parse_throttle_reset)
from core.dispatcher import ExecutionResult, WORKER_REAL, mark_executor
from core.handoff import handoff_required, retire_session, write_handoff
from core.session_policy import CTX_HEALTHY, CTX_RESET, CTX_WARNING, FRESH, REUSE, context_state, decide_session
from core.session_telemetry import session_context_usage
from core.reliability_config import ReliabilityConfig
from db.migrate import apply_all


class TestT6ContextTruth(unittest.TestCase):
    def test_telemetry_require_flag_controls_untrusted_fallback(self):
        from core.openclaw_bridge import _telemetry_session_decision
        missing = {"active_context": None, "context_window": 200_000}
        required = ReliabilityConfig({"telemetry": {"require": True}})
        optional = ReliabilityConfig({"telemetry": {"require": False}})
        self.assertIn("provenance", " ".join(_telemetry_session_decision(missing, required).reasons))
        self.assertNotIn("provenance", " ".join(_telemetry_session_decision(missing, optional).reasons))

    def test_thresholds_and_pct_clamp(self):
        self.assertEqual(context_state(79_999, context_window=100_000), CTX_HEALTHY)
        self.assertEqual(context_state(80_000, context_window=100_000), CTX_WARNING)
        self.assertEqual(context_state(100_000, context_window=100_000), CTX_RESET)
        self.assertEqual(decide_session(active_context=20_000).decision, REUSE)
        self.assertEqual(decide_session(active_context=200_000).decision, FRESH)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agent" / "sessions"; path.mkdir(parents=True)
            (path / "s.jsonl").write_text(json.dumps({"timestamp": "2026-08-12T00:00:00Z",
                "session_key": "agent:a:key", "usage": {"input": 30443, "output": 1911,
                "cacheRead": 25088, "cacheWrite": 0, "reasoningTokens": 1063,
                "totalTokens": 57442}}) + "\n")
            usage = session_context_usage("agent:a:key", sessions_root=Path(tmp), provider="anthropic")
        self.assertEqual(usage["active_context"], 57442)
        self.assertNotEqual(usage["active_context"], usage["cache_read"])
        self.assertEqual(usage["total_tokens"], 57442)

    def test_deepseek_total_variant_and_configured_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agent" / "sessions"; path.mkdir(parents=True)
            (path / "s.jsonl").write_text(json.dumps({"timestamp": "2026-08-12T00:00:00Z",
                "session_key": "s", "usage": {"input": 10, "output": 5,
                "cacheRead": 90000, "reasoningTokens": 2, "total": 17}}) + "\n")
            usage = session_context_usage("s", sessions_root=Path(tmp), provider="deepseek")
        self.assertEqual((usage["active_context"], usage["total_tokens"]), (17, 17))
        cfg = ReliabilityConfig({"session": {"warning_threshold_pct": .5,
                                              "reset_threshold_pct": .9}})
        with patch("core.reliability_config.load_reliability_config", return_value=cfg):
            self.assertEqual(context_state(60, context_window=100), CTX_WARNING)


class TestT11RetirementHandoff(unittest.TestCase):
    def test_retired_is_authoritative_dead_session_evidence(self):
        from core.auto_resume import _authoritative_meta
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE session_lifecycle (session_key TEXT PRIMARY KEY, session_state TEXT)")
            conn.execute("INSERT INTO session_lifecycle VALUES ('s', 'RETIRED')")
            conn.commit(); conn.close()
            with patch("core.auto_resume.OPENCLAW_DB", db):
                meta = _authoritative_meta("p", {"session_key": "s"}, None)
        self.assertFalse(meta["session_live"])

    def test_handoff_and_retirement_are_durable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            conn = sqlite3.connect(db); conn.execute("CREATE TABLE task_runs (run_id TEXT PRIMARY KEY, status TEXT)"); conn.commit(); conn.close()
            apply_all(db, backup=False)
            self.assertTrue(handoff_required({"context_pct": .80}))
            artifact = write_handoff("agent:a:key", "worker-b", {"next": "continue"}, output_dir=Path(tmp) / "handoffs")
            row = retire_session("agent:a:key", "context pressure", .9, db_path=db)
            payload = json.loads(artifact.read_text())
        self.assertEqual(row["session_state"], "RETIRED")
        self.assertIsNotNone(row["retired_at"])
        self.assertEqual(payload["target_worker"], "worker-b")


class TestT16CapacityTruth(unittest.TestCase):
    def test_queue_until_reset_flag_is_consumed_by_dispatch_priority(self):
        from core.dispatcher import _capacity_near_reset_for_dispatch
        class Ledger:
            def capacity_near_reset(self, logical, *, window_minutes):
                return logical == "codex" and window_minutes == 60
        class Workforce: ledger = Ledger(); capacity = None
        class Assignment: resolved_logical = "codex"
        off = ReliabilityConfig({"provider": {"queue_until_reset": False},
                                 "capacity": {"provider_window_minutes": 60}})
        on = ReliabilityConfig({"provider": {"queue_until_reset": True},
                                "capacity": {"provider_window_minutes": 60}})
        with patch("core.dispatcher.load_reliability_config", return_value=off):
            self.assertFalse(_capacity_near_reset_for_dispatch(Workforce(), Assignment()))
        with patch("core.dispatcher.load_reliability_config", return_value=on):
            self.assertTrue(_capacity_near_reset_for_dispatch(Workforce(), Assignment()))

    def test_local_failure_with_reset_like_text_does_not_exhaust(self):
        ledger = CapacityLedger.in_memory()
        def fail(_pkg, _assignment):
            return ExecutionResult(False, error="local validation reset=2026-08-12T00:00:00Z",
                                   execution_evidence_source="local-validation")
        wrapped = ledger_recording_executor(ledger, inner=mark_executor(fail, WORKER_REAL))
        class Assignment: resolved_logical = "codex"
        wrapped(object(), Assignment())
        self.assertNotEqual(ledger.get("codex").health_state, EXHAUSTED)

    def test_transport_throttle_feeds_failure_and_observed_reset(self):
        ledger = CapacityLedger.in_memory()
        reset = (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0)
        def fail(_pkg, _assignment):
            return ExecutionResult(False, error=f"429 throttle_until={reset.isoformat()}")
        wrapped = ledger_recording_executor(ledger, inner=mark_executor(fail, WORKER_REAL))
        class Assignment: resolved_logical = "codex"
        wrapped(object(), Assignment())
        entry = ledger.get("codex")
        self.assertEqual(entry.health_state, EXHAUSTED)
        self.assertTrue(ledger.capacity_near_reset("codex", window_minutes=60))

    def test_retry_after_parser_uses_observed_window(self):
        now = datetime(2026, 8, 12, tzinfo=timezone.utc)
        self.assertEqual(parse_throttle_reset("Retry-After: 60 seconds", now=now),
                         (now + timedelta(seconds=60)).isoformat())


if __name__ == "__main__":
    unittest.main()
