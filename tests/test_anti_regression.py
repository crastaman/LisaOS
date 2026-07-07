"""Proof-of-work tests for the LisaOS Anti-Regression Gates (Phase 1).

Validates docs/LISAOS/V3/19_ANTI_REGRESSION_FRAMEWORK.md's enforceable checks
against core/anti_regression.py. Each gate gets at least one PASS case and one
FAIL case. Fully hermetic: pure functions on plain data / simple stand-ins, no
network/provider calls, no spend.

Run with:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_anti_regression -v
"""

import unittest
from types import SimpleNamespace

from core.anti_regression import (
    OK, WARN, FAIL,
    RETIRED_ALIASES,
    check_no_silent_fallback,
    check_intended_matches_actual,
    check_main_not_majority,
    check_no_stale_alias,
    check_deepseek_not_gravity_well,
    check_no_idle_while_ready,
    check_context_safety,
    assignment_gates,
    run_pre_sprint_gates,
    run_post_sprint_gates,
)


def _assignment(**kwargs):
    defaults = dict(
        intended_model="claude-sonnet", resolved_logical="claude-sonnet",
        fallback_from=None, fallback_reason=None,
        actual_runtime=None, resolved_runtime="claude-cli",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# --------------------------------------------------------------------------- #
# F1: no silent fallback
# --------------------------------------------------------------------------- #

class TestNoSilentFallback(unittest.TestCase):
    def test_pass_no_fallback(self):
        a = _assignment()
        r = check_no_silent_fallback(a)
        self.assertEqual(r.severity, OK)

    def test_pass_explicit_recorded_fallback(self):
        a = _assignment(intended_model="qwen-deepinfra", resolved_logical="claude-haiku",
                        fallback_from="qwen-deepinfra",
                        fallback_reason="qwen-deepinfra unavailable; fallback -> claude-haiku")
        r = check_no_silent_fallback(a)
        self.assertEqual(r.severity, OK)

    def test_fail_silent_fallback_no_record(self):
        a = _assignment(intended_model="qwen-deepinfra", resolved_logical="claude-haiku",
                        fallback_from=None, fallback_reason=None)
        r = check_no_silent_fallback(a)
        self.assertEqual(r.severity, FAIL)

    def test_fail_silent_fallback_onto_deepseek_flagged(self):
        a = _assignment(intended_model="claude-sonnet",
                        resolved_logical="custom-api-deepseek-com/deepseek-reasoner",
                        fallback_from=None, fallback_reason=None)
        r = check_no_silent_fallback(a)
        self.assertEqual(r.severity, FAIL)
        self.assertIn("DeepSeek", r.detail)

    def test_fail_fallback_from_without_reason(self):
        a = _assignment(fallback_from="claude-sonnet", fallback_reason=None,
                        resolved_logical="claude-sonnet")
        r = check_no_silent_fallback(a)
        self.assertEqual(r.severity, FAIL)


# --------------------------------------------------------------------------- #
# F3: intended provider/model must match actual runtime evidence
# --------------------------------------------------------------------------- #

class TestIntendedMatchesActual(unittest.TestCase):
    def test_pass_not_yet_executed(self):
        a = _assignment(actual_runtime=None)
        r = check_intended_matches_actual(a)
        self.assertEqual(r.severity, OK)

    def test_pass_actual_matches_resolved(self):
        a = _assignment(resolved_runtime="claude-cli", actual_runtime="claude-cli")
        r = check_intended_matches_actual(a)
        self.assertEqual(r.severity, OK)

    def test_fail_runtime_drift(self):
        a = _assignment(resolved_runtime="claude-cli", actual_runtime="openclaw")
        r = check_intended_matches_actual(a)
        self.assertEqual(r.severity, FAIL)
        self.assertIn("drift", r.detail)


# --------------------------------------------------------------------------- #
# F2: main agent must not perform the majority of delegable work
# --------------------------------------------------------------------------- #

class TestMainNotMajority(unittest.TestCase):
    def test_pass_low_ratio(self):
        r = check_main_not_majority(0.15)
        self.assertEqual(r.severity, OK)

    def test_warn_trending_high(self):
        r = check_main_not_majority(0.45)
        self.assertEqual(r.severity, WARN)

    def test_fail_majority(self):
        r = check_main_not_majority(0.61)
        self.assertEqual(r.severity, FAIL)


# --------------------------------------------------------------------------- #
# F4: stale aliases must not resolve
# --------------------------------------------------------------------------- #

class _FakeResolver:
    def __init__(self, resolvable: dict[str, str | None]):
        self._resolvable = resolvable

    def normalise(self, name: str) -> str | None:
        return self._resolvable.get(name)


class TestNoStaleAlias(unittest.TestCase):
    def test_pass_all_retired_aliases_fail_closed(self):
        resolver = _FakeResolver({a: None for a in RETIRED_ALIASES})
        r = check_no_stale_alias(resolver)
        self.assertEqual(r.severity, OK)

    def test_fail_a_retired_alias_still_resolves(self):
        resolver = _FakeResolver({a: None for a in RETIRED_ALIASES[:-1]}
                                 | {RETIRED_ALIASES[-1]: "qwen-alibaba"})
        r = check_no_stale_alias(resolver)
        self.assertEqual(r.severity, FAIL)
        self.assertIn(RETIRED_ALIASES[-1], r.detail)


# --------------------------------------------------------------------------- #
# DeepSeek must not become the gravity well again
# --------------------------------------------------------------------------- #

class TestDeepSeekNotGravityWell(unittest.TestCase):
    def test_pass_diversified_usage(self):
        usage = {"claude-sonnet": 10, "codex": 8, "deepseek": 6, "qwen-deepinfra": 6}
        r = check_deepseek_not_gravity_well(usage)
        self.assertEqual(r.severity, OK)

    def test_pass_no_usage_recorded(self):
        r = check_deepseek_not_gravity_well({})
        self.assertEqual(r.severity, OK)

    def test_fail_deepseek_monoculture(self):
        usage = {"deepseek": 90, "claude-sonnet": 5, "codex": 5}
        r = check_deepseek_not_gravity_well(usage)
        self.assertEqual(r.severity, FAIL)
        self.assertIn("monoculture", r.detail)


# --------------------------------------------------------------------------- #
# Workers should not sit idle while ready work exists
# --------------------------------------------------------------------------- #

class TestNoIdleWhileReady(unittest.TestCase):
    def test_pass_no_idle_workers(self):
        r = check_no_idle_while_ready(idle_capable_count=0, ready_unassigned_count=5)
        self.assertEqual(r.severity, OK)

    def test_pass_no_ready_work(self):
        r = check_no_idle_while_ready(idle_capable_count=3, ready_unassigned_count=0)
        self.assertEqual(r.severity, OK)

    def test_fail_idle_while_ready_work_exists(self):
        r = check_no_idle_while_ready(idle_capable_count=2, ready_unassigned_count=4)
        self.assertEqual(r.severity, FAIL)


# --------------------------------------------------------------------------- #
# F5: context safety checks must run before large reports
# --------------------------------------------------------------------------- #

class TestContextSafety(unittest.TestCase):
    def test_pass_within_budget(self):
        r = check_context_safety(tokens_used=4000, budget=8000)
        self.assertEqual(r.severity, OK)

    def test_fail_overflow(self):
        r = check_context_safety(tokens_used=9000, budget=8000)
        self.assertEqual(r.severity, FAIL)

    def test_fail_no_budget_set(self):
        r = check_context_safety(tokens_used=100, budget=0)
        self.assertEqual(r.severity, FAIL)


# --------------------------------------------------------------------------- #
# Aggregators
# --------------------------------------------------------------------------- #

class TestAggregators(unittest.TestCase):
    def test_assignment_gates_reports_both_checks(self):
        a = _assignment()
        report = assignment_gates(a)
        names = {r.name for r in report.results}
        self.assertEqual(names, {"no_silent_fallback", "intended_matches_actual"})
        self.assertTrue(report.passed)

    def test_pre_sprint_gates_fail_on_stale_alias(self):
        resolver = _FakeResolver({a: "qwen-alibaba" for a in RETIRED_ALIASES})
        report = run_pre_sprint_gates(resolver)
        self.assertFalse(report.passed)
        self.assertEqual(len(report.failures), 1)

    def test_post_sprint_gates_pass_on_healthy_sprint(self):
        assignments = [_assignment(), _assignment(resolved_runtime="codex")]
        report = run_post_sprint_gates(
            assignments, main_work_ratio=0.10,
            provider_usage={"claude-sonnet": 5, "codex": 5, "deepseek": 2},
            idle_capable_count=0, ready_unassigned_count=0,
        )
        self.assertTrue(report.passed)

    def test_post_sprint_gates_fail_on_regressed_sprint(self):
        # Silent fallback + main doing everything + DeepSeek monoculture +
        # idle workers while ready work exists -- a fully regressed sprint.
        bad_assignment = _assignment(intended_model="claude-sonnet",
                                     resolved_logical="deepseek",
                                     fallback_from=None, fallback_reason=None)
        report = run_post_sprint_gates(
            [bad_assignment], main_work_ratio=0.9,
            provider_usage={"deepseek": 95, "claude-sonnet": 5},
            idle_capable_count=2, ready_unassigned_count=3,
        )
        self.assertFalse(report.passed)
        failed_names = {r.name for r in report.failures}
        self.assertIn("no_silent_fallback", failed_names)
        self.assertIn("main_not_majority", failed_names)
        self.assertIn("deepseek_not_gravity_well", failed_names)
        self.assertIn("no_idle_while_ready", failed_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
