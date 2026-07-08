"""Tests for the LisaOS Capacity Ledger (Phase 3).

All tests use CapacityLedger.in_memory() or CapacityLedger.at_path(tmp) --
never the real default path -- so no test ever touches operator state.

Run with:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_capacity_ledger -v
"""

import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.capacity_ledger import (
    CapacityLedger,
    HEALTHY,
    DEGRADED,
    UNAVAILABLE,
    EXHAUSTED,
    PROBATIONARY,
    DISABLED,
)


class TestSeeding(unittest.TestCase):
    def test_unknown_provider_seeds_healthy_elastic_api(self):
        ledger = CapacityLedger.in_memory()
        entry = ledger.get("some-new-provider")
        self.assertEqual(entry.health_state, HEALTHY)
        self.assertEqual(entry.cost_class, "elastic-api")
        self.assertFalse(entry.probationary)

    def test_known_seed_cost_classes_match_ground_truth(self):
        ledger = CapacityLedger.in_memory()
        self.assertEqual(ledger.get("deepseek").cost_class, "elastic-api")
        self.assertEqual(ledger.get("claude-opus").cost_class, "subscription-scarce")
        self.assertEqual(ledger.get("claude-sonnet").cost_class, "subscription-abundant")
        self.assertEqual(ledger.get("codex").cost_class, "subscription-abundant")
        self.assertEqual(ledger.get("qwen-deepinfra").cost_class, "elastic-api")
        self.assertEqual(ledger.get("glm").cost_class, "subscription-probation")
        self.assertEqual(ledger.get("glm-turbo").cost_class, "subscription-probation")

    def test_glm_seeds_probationary(self):
        ledger = CapacityLedger.in_memory()
        for logical in ("glm", "glm-turbo"):
            entry = ledger.get(logical)
            self.assertTrue(entry.probationary)
            self.assertEqual(entry.health_state, PROBATIONARY)

    def test_repeat_get_returns_same_entry_object(self):
        ledger = CapacityLedger.in_memory()
        a = ledger.get("claude-sonnet")
        a.notes = "touched"
        b = ledger.get("claude-sonnet")
        self.assertEqual(b.notes, "touched")


class TestPersistence(unittest.TestCase):
    def test_save_and_reload_preserves_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            ledger1 = CapacityLedger.at_path(path)
            ledger1.record_failure("claude-sonnet", reason="timeout")
            ledger1.record_exhaustion("deepseek", exhausted_until=None)

            ledger2 = CapacityLedger.at_path(path)
            self.assertEqual(ledger2.get("claude-sonnet").consecutive_failures, 1)
            self.assertEqual(ledger2.get("deepseek").health_state, EXHAUSTED)

    def test_in_memory_ledger_never_touches_disk(self):
        ledger = CapacityLedger.in_memory()
        self.assertFalse(ledger._persist)
        self.assertIsNone(ledger.path)
        ledger.record_failure("claude-sonnet", reason="x")  # must not raise / must not write


class TestHealthTransitions(unittest.TestCase):
    def test_single_failure_degrades(self):
        ledger = CapacityLedger.in_memory()
        ledger.record_failure("claude-sonnet", reason="500")
        self.assertEqual(ledger.get("claude-sonnet").health_state, DEGRADED)

    def test_three_consecutive_failures_marks_unavailable(self):
        ledger = CapacityLedger.in_memory()
        for _ in range(3):
            ledger.record_failure("claude-sonnet", reason="500")
        self.assertEqual(ledger.get("claude-sonnet").health_state, UNAVAILABLE)
        self.assertEqual(ledger.get("claude-sonnet").reliability_status, "unreliable")

    def test_success_resets_consecutive_failures_and_recovers(self):
        ledger = CapacityLedger.in_memory()
        for _ in range(3):
            ledger.record_failure("claude-sonnet", reason="500")
        self.assertEqual(ledger.get("claude-sonnet").health_state, UNAVAILABLE)
        ledger.record_success("claude-sonnet", runtime="claude-cli")
        entry = ledger.get("claude-sonnet")
        self.assertEqual(entry.health_state, HEALTHY)
        self.assertEqual(entry.consecutive_failures, 0)

    def test_probationary_provider_recovers_to_probationary_not_healthy(self):
        ledger = CapacityLedger.in_memory()
        for _ in range(3):
            ledger.record_failure("glm", reason="500")
        ledger.record_success("glm", runtime="openclaw")
        self.assertEqual(ledger.get("glm").health_state, PROBATIONARY)

    def test_failure_history_bounded(self):
        ledger = CapacityLedger.in_memory()
        for i in range(25):
            ledger.record_failure("deepseek", reason=f"failure {i}")
        self.assertLessEqual(len(ledger.get("deepseek").failure_history), 20)

    def test_disable_and_enable(self):
        ledger = CapacityLedger.in_memory()
        ledger.disable("codex", reason="manual maintenance")
        self.assertEqual(ledger.get("codex").health_state, DISABLED)
        ledger.enable("codex")
        self.assertEqual(ledger.get("codex").health_state, HEALTHY)

    def test_quarantine_marks_dynamic_probation(self):
        ledger = CapacityLedger.in_memory()
        self.assertEqual(ledger.get("qwen-deepinfra").health_state, HEALTHY)
        ledger.quarantine("qwen-deepinfra", reason="suspicious output pattern")
        entry = ledger.get("qwen-deepinfra")
        self.assertEqual(entry.health_state, PROBATIONARY)
        self.assertTrue(entry.probationary)


class TestExhaustionForecasting(unittest.TestCase):
    def test_unknown_reset_time_never_auto_recovers(self):
        ledger = CapacityLedger.in_memory()
        ledger.record_exhaustion("deepseek", exhausted_until=None)
        # "checking" repeatedly must not guess a recovery.
        self.assertEqual(ledger.effective_health("deepseek"), EXHAUSTED)
        self.assertEqual(ledger.effective_health("deepseek"), EXHAUSTED)

    def test_known_past_reset_time_auto_recovers(self):
        ledger = CapacityLedger.in_memory()
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        ledger.record_exhaustion("deepseek", exhausted_until=past)
        self.assertEqual(ledger.effective_health("deepseek"), HEALTHY)

    def test_known_future_reset_time_stays_exhausted(self):
        ledger = CapacityLedger.in_memory()
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        ledger.record_exhaustion("deepseek", exhausted_until=future)
        self.assertEqual(ledger.effective_health("deepseek"), EXHAUSTED)

    def test_explicit_success_clears_exhaustion_regardless_of_forecast(self):
        ledger = CapacityLedger.in_memory()
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        ledger.record_exhaustion("deepseek", exhausted_until=future)
        ledger.record_success("deepseek", runtime="openclaw")
        self.assertEqual(ledger.get("deepseek").health_state, HEALTHY)
        self.assertIsNone(ledger.get("deepseek").exhausted_until)


class TestIsUsable(unittest.TestCase):
    def test_healthy_is_usable(self):
        ledger = CapacityLedger.in_memory()
        usable, _ = ledger.is_usable("claude-sonnet")
        self.assertTrue(usable)

    def test_unavailable_never_usable(self):
        ledger = CapacityLedger.in_memory()
        for _ in range(3):
            ledger.record_failure("claude-sonnet", reason="x")
        usable, reason = ledger.is_usable("claude-sonnet")
        self.assertFalse(usable)
        self.assertIn("unavailable", reason)

    def test_disabled_never_usable(self):
        ledger = CapacityLedger.in_memory()
        ledger.disable("codex")
        usable, _ = ledger.is_usable("codex")
        self.assertFalse(usable)

    def test_exhausted_not_usable_unless_allowed(self):
        ledger = CapacityLedger.in_memory()
        ledger.record_exhaustion("deepseek", exhausted_until=None)
        usable, reason = ledger.is_usable("deepseek")
        self.assertFalse(usable)
        self.assertIn("exhausted", reason)
        usable_allowed, reason_allowed = ledger.is_usable("deepseek", allow_exhausted=True)
        self.assertTrue(usable_allowed)
        self.assertIn("explicitly allowed", reason_allowed)

    def test_probationary_only_usable_for_low_risk(self):
        ledger = CapacityLedger.in_memory()
        usable_normal, _ = ledger.is_usable("glm", risk="normal")
        usable_low, _ = ledger.is_usable("glm", risk="low")
        usable_critical, _ = ledger.is_usable("glm", risk="critical")
        self.assertFalse(usable_normal)
        self.assertTrue(usable_low)
        self.assertFalse(usable_critical)


class TestThreadSafety(unittest.TestCase):
    def test_concurrent_failure_recording_is_exact(self):
        ledger = CapacityLedger.in_memory()

        def hammer():
            for _ in range(50):
                ledger.record_failure("deepseek", reason="concurrent")

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(ledger.get("deepseek").total_failures, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
