"""Proof-of-work tests for the LisaOS Anti-Regression Gates (Phase 1 + 2).

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
    check_no_worker_starvation,
    check_context_safety,
    check_no_unavailable_capacity_selected,
    check_no_exhausted_capacity_unless_allowed,
    check_probationary_not_critical,
    check_mode_policy_respected,
    check_subscription_api_policy_respected,
    check_no_unacknowledged_bypass,
    assignment_gates,
    run_pre_sprint_gates,
    run_post_sprint_gates,
    run_dispatch_gates,
    run_policy_gates,
)
from core.workforce_modes import WorkforceMode


def _assignment(**kwargs):
    defaults = dict(
        work_package_id="wp", employee="senior-software-engineer",
        intended_model="claude-sonnet", resolved_logical="claude-sonnet",
        fallback_from=None, fallback_reason=None,
        actual_runtime=None, resolved_runtime="claude-cli",
        risk="normal", mode="balanced",
        capacity_class="subscription-abundant", health_state="healthy",
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
# F6: no unacknowledged dispatcher-bypass violation (governance hardening patch)
# --------------------------------------------------------------------------- #

class TestNoUnacknowledgedBypass(unittest.TestCase):
    def test_pass_no_violations(self):
        r = check_no_unacknowledged_bypass([])
        self.assertEqual(r.severity, OK)

    def test_fail_one_violation(self):
        violation = SimpleNamespace(subagent_name="impl-fingerprint-engine")
        r = check_no_unacknowledged_bypass([violation])
        self.assertEqual(r.severity, FAIL)
        self.assertIn("impl-fingerprint-engine", r.detail)

    def test_fail_reports_count_of_multiple_violations(self):
        violations = [SimpleNamespace(subagent_name=n) for n in
                     ("impl-backup-manager", "impl-upgrade-executor")]
        r = check_no_unacknowledged_bypass(violations)
        self.assertEqual(r.severity, FAIL)
        self.assertIn("2 unacknowledged", r.detail)


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
# Worker starvation (Phase 2): a specific package waiting too long
# --------------------------------------------------------------------------- #

class TestNoWorkerStarvation(unittest.TestCase):
    def test_pass_no_wait_data(self):
        r = check_no_worker_starvation({})
        self.assertEqual(r.severity, OK)

    def test_pass_short_waits(self):
        r = check_no_worker_starvation({"a": 0.1, "b": 0.5})
        self.assertEqual(r.severity, OK)

    def test_warn_trending_toward_starvation(self):
        r = check_no_worker_starvation({"a": 0.1, "b": 3.0})
        self.assertEqual(r.severity, WARN)

    def test_fail_genuine_starvation(self):
        r = check_no_worker_starvation({"a": 0.1, "b": 8.0})
        self.assertEqual(r.severity, FAIL)
        self.assertIn("b", r.detail)


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

    def test_pre_sprint_gates_pass_with_no_bypass_violations(self):
        resolver = _FakeResolver({})
        report = run_pre_sprint_gates(resolver)
        self.assertTrue(report.passed)

    def test_pre_sprint_gates_fail_on_unacknowledged_bypass(self):
        resolver = _FakeResolver({})
        violation = SimpleNamespace(subagent_name="impl-safety-constitution")
        report = run_pre_sprint_gates(resolver, bypass_violations=[violation])
        self.assertFalse(report.passed)
        names = {r.name for r in report.failures}
        self.assertIn("no_unacknowledged_bypass", names)

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


# --------------------------------------------------------------------------- #
# run_dispatch_gates (Phase 2): the dispatcher-report aggregator
# --------------------------------------------------------------------------- #

def _fake_metrics(**overrides):
    defaults = dict(
        main_work_ratio=0.0,
        provider_usage={"claude-sonnet": 3, "codex": 2},
        max_unexplained_idle_ready=0,
        wait_times={"a": 0.05, "b": 0.1},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_report(assignments=None, **metrics_overrides):
    return SimpleNamespace(
        assignments=assignments or {"a": _assignment(), "b": _assignment()},
        metrics=_fake_metrics(**metrics_overrides),
    )


class TestRunDispatchGates(unittest.TestCase):
    def test_healthy_report_passes(self):
        report = _fake_report()
        gates = run_dispatch_gates(report)
        self.assertTrue(gates.passed, [(r.name, r.detail) for r in gates.failures])

    def test_regressed_report_fails_multiple_gates(self):
        bad_assignment = _assignment(intended_model="claude-sonnet",
                                     resolved_logical="deepseek",
                                     fallback_from=None, fallback_reason=None)
        report = _fake_report(
            assignments={"a": bad_assignment},
            main_work_ratio=0.9,
            provider_usage={"deepseek": 95, "claude-sonnet": 5},
            max_unexplained_idle_ready=3,
            wait_times={"a": 10.0},
        )
        gates = run_dispatch_gates(report)
        self.assertFalse(gates.passed)
        failed_names = {r.name for r in gates.failures}
        self.assertIn("no_silent_fallback", failed_names)
        self.assertIn("main_not_majority", failed_names)
        self.assertIn("deepseek_not_gravity_well", failed_names)
        self.assertIn("no_idle_while_ready", failed_names)
        self.assertIn("no_worker_starvation", failed_names)

    def test_stale_alias_check_included_when_resolver_provided(self):
        report = _fake_report()
        resolver = _FakeResolver({a: "qwen-alibaba" for a in RETIRED_ALIASES})
        gates = run_dispatch_gates(report, provider_resolver=resolver)
        names = {r.name for r in gates.results}
        self.assertIn("no_stale_alias", names)
        self.assertFalse(gates.passed)

    def test_stale_alias_check_omitted_when_no_resolver_given(self):
        report = _fake_report()
        gates = run_dispatch_gates(report)
        names = {r.name for r in gates.results}
        self.assertNotIn("no_stale_alias", names)


# --------------------------------------------------------------------------- #
# Phase 3: capacity-ledger / mode-policy gates
# --------------------------------------------------------------------------- #

class TestNoUnavailableCapacitySelected(unittest.TestCase):
    def test_pass_when_healthy(self):
        r = check_no_unavailable_capacity_selected(_assignment(health_state="healthy"))
        self.assertEqual(r.severity, OK)

    def test_pass_when_no_employee_assigned(self):
        r = check_no_unavailable_capacity_selected(_assignment(employee=None))
        self.assertEqual(r.severity, OK)

    def test_fail_when_unavailable(self):
        r = check_no_unavailable_capacity_selected(_assignment(health_state="unavailable"))
        self.assertEqual(r.severity, FAIL)

    def test_fail_when_disabled(self):
        r = check_no_unavailable_capacity_selected(_assignment(health_state="disabled"))
        self.assertEqual(r.severity, FAIL)


class TestNoExhaustedCapacityUnlessAllowed(unittest.TestCase):
    def test_pass_when_healthy(self):
        r = check_no_exhausted_capacity_unless_allowed(_assignment(health_state="healthy"))
        self.assertEqual(r.severity, OK)

    def test_fail_when_exhausted_and_not_allowed(self):
        r = check_no_exhausted_capacity_unless_allowed(
            _assignment(health_state="exhausted"), allowed=False)
        self.assertEqual(r.severity, FAIL)

    def test_pass_when_exhausted_and_explicitly_allowed(self):
        r = check_no_exhausted_capacity_unless_allowed(
            _assignment(health_state="exhausted"), allowed=True)
        self.assertEqual(r.severity, OK)


class TestProbationaryNotCritical(unittest.TestCase):
    def test_pass_probationary_on_low_risk(self):
        r = check_probationary_not_critical(
            _assignment(health_state="probationary", risk="low"))
        self.assertEqual(r.severity, OK)

    def test_fail_probationary_on_critical_risk(self):
        r = check_probationary_not_critical(
            _assignment(health_state="probationary", risk="critical"))
        self.assertEqual(r.severity, FAIL)

    def test_fail_probation_cost_class_on_critical_risk_even_if_health_healthy(self):
        r = check_probationary_not_critical(
            _assignment(health_state="healthy", capacity_class="subscription-probation",
                       risk="critical"))
        self.assertEqual(r.severity, FAIL)

    def test_pass_non_probationary_on_critical_risk(self):
        r = check_probationary_not_critical(
            _assignment(health_state="healthy", capacity_class="subscription-abundant",
                       risk="critical"))
        self.assertEqual(r.severity, OK)


class _FakeModeRegistry:
    def __init__(self, modes: dict[str, WorkforceMode]):
        self._modes = modes

    def get(self, mode_id: str) -> WorkforceMode:
        if mode_id not in self._modes:
            raise KeyError(f"unknown mode {mode_id!r}")
        return self._modes[mode_id]


_BALANCED = WorkforceMode(id="balanced", allowed_employees=None,
                          subscription_policy="allow-metered", api_spend_policy="allow")
_ARCHITECTURE = WorkforceMode(id="architecture",
                             allowed_employees=["chief-architect", "cto-reviewer"],
                             subscription_policy="subscription-only",
                             api_spend_policy="forbidden")
_EMERGENCY = WorkforceMode(id="emergency", allowed_employees=None,
                          subscription_policy="allow-metered",
                          api_spend_policy="unrestricted",
                          allow_exhausted_capacity=True)

_MODE_REGISTRY = _FakeModeRegistry({
    "balanced": _BALANCED, "architecture": _ARCHITECTURE, "emergency": _EMERGENCY,
})


class TestModePolicyRespected(unittest.TestCase):
    def test_pass_when_employee_in_allowed_roster(self):
        r = check_mode_policy_respected(
            _assignment(employee="chief-architect", mode="architecture"), _MODE_REGISTRY)
        self.assertEqual(r.severity, OK)

    def test_fail_when_employee_not_in_allowed_roster(self):
        r = check_mode_policy_respected(
            _assignment(employee="software-engineer", mode="architecture"), _MODE_REGISTRY)
        self.assertEqual(r.severity, FAIL)

    def test_pass_when_mode_unrestricted(self):
        r = check_mode_policy_respected(
            _assignment(employee="implementation-engineer", mode="balanced"), _MODE_REGISTRY)
        self.assertEqual(r.severity, OK)

    def test_fail_when_mode_unresolvable(self):
        r = check_mode_policy_respected(
            _assignment(employee="chief-architect", mode="not-a-mode"), _MODE_REGISTRY)
        self.assertEqual(r.severity, FAIL)

    def test_pass_when_no_employee_assigned(self):
        r = check_mode_policy_respected(_assignment(employee=None), _MODE_REGISTRY)
        self.assertEqual(r.severity, OK)


class TestSubscriptionApiPolicyRespected(unittest.TestCase):
    def test_pass_when_subscription_class_under_subscription_only_mode(self):
        r = check_subscription_api_policy_respected(
            _assignment(employee="chief-architect", mode="architecture",
                       capacity_class="subscription-scarce"),
            _MODE_REGISTRY)
        self.assertEqual(r.severity, OK)

    def test_fail_when_elastic_api_under_subscription_only_mode(self):
        r = check_subscription_api_policy_respected(
            _assignment(employee="chief-architect", mode="architecture",
                       capacity_class="elastic-api"),
            _MODE_REGISTRY)
        self.assertEqual(r.severity, FAIL)

    def test_pass_when_elastic_api_under_allow_metered_mode(self):
        r = check_subscription_api_policy_respected(
            _assignment(employee="implementation-engineer", mode="balanced",
                       capacity_class="elastic-api"),
            _MODE_REGISTRY)
        self.assertEqual(r.severity, OK)


class TestRunPolicyGates(unittest.TestCase):
    def test_healthy_report_passes_all_policy_gates(self):
        report = _fake_report(assignments={
            "a": _assignment(employee="senior-software-engineer", mode="balanced",
                            capacity_class="subscription-abundant", health_state="healthy"),
        })
        gates = run_policy_gates(report, _MODE_REGISTRY)
        self.assertTrue(gates.passed, [(r.name, r.detail) for r in gates.failures])

    def test_mode_violation_is_caught(self):
        report = _fake_report(assignments={
            "a": _assignment(employee="software-engineer", mode="architecture",
                            capacity_class="subscription-abundant", health_state="healthy"),
        })
        gates = run_policy_gates(report, _MODE_REGISTRY)
        self.assertFalse(gates.passed)
        self.assertIn("mode_policy_respected", {r.name for r in gates.failures})

    def test_exhausted_capacity_caught_unless_emergency_mode(self):
        report_balanced = _fake_report(assignments={
            "a": _assignment(employee="senior-software-engineer", mode="balanced",
                            capacity_class="subscription-abundant", health_state="exhausted"),
        })
        gates_balanced = run_policy_gates(report_balanced, _MODE_REGISTRY)
        self.assertIn("no_exhausted_capacity_unless_allowed",
                     {r.name for r in gates_balanced.failures})

        report_emergency = _fake_report(assignments={
            "a": _assignment(employee="senior-software-engineer", mode="emergency",
                            capacity_class="subscription-abundant", health_state="exhausted"),
        })
        gates_emergency = run_policy_gates(report_emergency, _MODE_REGISTRY)
        self.assertNotIn("no_exhausted_capacity_unless_allowed",
                         {r.name for r in gates_emergency.failures})

    def test_probationary_critical_work_caught(self):
        report = _fake_report(assignments={
            "a": _assignment(employee="senior-software-engineer", mode="balanced",
                            capacity_class="subscription-probation",
                            health_state="probationary", risk="critical"),
        })
        gates = run_policy_gates(report, _MODE_REGISTRY)
        self.assertIn("probationary_not_critical", {r.name for r in gates.failures})

    def test_still_runs_underlying_dispatch_gates(self):
        # run_policy_gates must not drop Phase 2's checks.
        bad_assignment = _assignment(employee="senior-software-engineer", mode="balanced",
                                     intended_model="claude-sonnet",
                                     resolved_logical="deepseek",
                                     fallback_from=None, fallback_reason=None)
        report = _fake_report(assignments={"a": bad_assignment}, main_work_ratio=0.9)
        gates = run_policy_gates(report, _MODE_REGISTRY)
        failed_names = {r.name for r in gates.failures}
        self.assertIn("no_silent_fallback", failed_names)
        self.assertIn("main_not_majority", failed_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
