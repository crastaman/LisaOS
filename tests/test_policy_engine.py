"""Tests for the LisaOS Policy Engine (Phase 3).

Combines the REAL, shipped registry/employees.yml and registry/
workforce_modes.yml with the hermetic 9-provider ProviderResolver fixture
from tests/test_workforce_resolver.py (imported directly -- no network, no
spend) and an in-memory CapacityLedger (never touches disk).

Run with:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_policy_engine -v
"""

import unittest
from datetime import datetime, timedelta, timezone

from core.workforce_resolver import (
    EmployeeRegistry,
    WorkforceResolutionError,
    WorkPackage,
    DETERMINISTIC_MODEL,
)
from core.workforce_modes import WorkforceModeRegistry
from core.capacity_ledger import CapacityLedger
from core.policy_engine import PolicyEngine

from tests.test_workforce_resolver import (
    resolver_all_available,
    resolver_no_claude_cli,
    real_employees,
    DEEPSEEK_PHYSICAL,
)


def engine(*, ledger=None, resolver=None) -> PolicyEngine:
    return PolicyEngine(
        employee_registry=real_employees(),
        provider_resolver=resolver or resolver_all_available(),
        mode_registry=WorkforceModeRegistry(),
        capacity_ledger=ledger or CapacityLedger.in_memory(),
    )


# --------------------------------------------------------------------------- #
# 1. Parity with Phase 1 WorkforceResolver when everything is healthy
# --------------------------------------------------------------------------- #

class TestParityWithPhase1(unittest.TestCase):
    def test_haiku_microtask_assignment_matches_phase1(self):
        pe = engine()
        wp = WorkPackage(id="p1", description="x", required_capabilities=["microtask"],
                         mode="balanced")
        a = pe.resolve(wp)
        self.assertEqual(a.employee, "operations-microtask-agent")
        self.assertEqual(a.resolved_logical, "claude-haiku")
        self.assertEqual(a.physical_model, "anthropic/claude-haiku-4-5")
        self.assertEqual(a.routed_by, "policy_engine")

    def test_deepseek_orchestration_assignment_matches_phase1(self):
        pe = engine()
        wp = WorkPackage(id="p2", description="x",
                         required_capabilities=["code-implementation", "bulk-mechanical"],
                         mode="balanced")
        a = pe.resolve(wp)
        self.assertEqual(a.employee, "implementation-engineer")
        self.assertEqual(a.resolved_logical, "deepseek")
        self.assertEqual(a.physical_model, DEEPSEEK_PHYSICAL)


# --------------------------------------------------------------------------- #
# 2. Unknown mode fails closed
# --------------------------------------------------------------------------- #

class TestUnknownMode(unittest.TestCase):
    def test_unknown_mode_fails_closed(self):
        pe = engine()
        wp = WorkPackage(id="p3", description="x", required_capabilities=["microtask"],
                         mode="not-a-real-mode")
        with self.assertRaises(WorkforceResolutionError) as ctx:
            pe.resolve(wp)
        self.assertEqual(ctx.exception.evidence.auth_result, "unknown_mode")


# --------------------------------------------------------------------------- #
# 3. Mode roster restriction
# --------------------------------------------------------------------------- #

class TestModeRosterRestriction(unittest.TestCase):
    def test_economy_mode_excludes_chief_architect_and_fails_closed(self):
        pe = engine()
        wp = WorkPackage(id="p4", description="x", required_capabilities=["architecture"],
                         mode="economy")
        with self.assertRaises(WorkforceResolutionError) as ctx:
            pe.resolve(wp)
        self.assertEqual(ctx.exception.evidence.auth_result, "no_capable_employee")

    def test_architecture_mode_succeeds_for_architecture_work(self):
        pe = engine()
        wp = WorkPackage(id="p5", description="x", required_capabilities=["architecture"],
                         mode="architecture")
        a = pe.resolve(wp)
        self.assertEqual(a.employee, "chief-architect")
        self.assertEqual(a.resolved_logical, "claude-opus")

    def test_local_future_mode_always_fails_closed(self):
        pe = engine()
        wp = WorkPackage(id="p6", description="x", required_capabilities=["microtask"],
                         mode="local_future")
        with self.assertRaises(WorkforceResolutionError) as ctx:
            pe.resolve(wp)
        self.assertEqual(ctx.exception.evidence.auth_result, "no_capable_employee")
        self.assertIn("local_future", str(ctx.exception))


# --------------------------------------------------------------------------- #
# 4. Capacity ledger exclusion
# --------------------------------------------------------------------------- #

class TestLedgerExclusion(unittest.TestCase):
    def test_unavailable_ledger_entry_forces_fallback(self):
        ledger = CapacityLedger.in_memory()
        for _ in range(3):
            ledger.record_failure("claude-haiku", reason="500")
        pe = engine(ledger=ledger, resolver=resolver_no_claude_cli())
        # Anthropic subscription is ALSO down at the provider layer here, so
        # this exercises both exclusion paths at once for the low-risk case.
        wp = WorkPackage(id="p7", description="x", required_capabilities=["microtask"],
                         mode="balanced", risk="low")
        a = pe.resolve(wp)
        self.assertEqual(a.employee, "operations-microtask-agent")
        self.assertEqual(a.resolved_logical, "glm-turbo")
        self.assertEqual(a.fallback_from, "claude-haiku")

    def test_unavailable_ledger_entry_alone_forces_fallback_with_all_providers_healthy(self):
        ledger = CapacityLedger.in_memory()
        for _ in range(3):
            ledger.record_failure("claude-haiku", reason="500")
        pe = engine(ledger=ledger, resolver=resolver_all_available())
        wp = WorkPackage(id="p7b", description="x", required_capabilities=["microtask"],
                         mode="balanced", risk="low")
        a = pe.resolve(wp)
        self.assertEqual(a.employee, "operations-microtask-agent")
        # claude-haiku is provider-available but ledger-unavailable -> must
        # skip straight to the fallback despite live credentials being fine.
        self.assertEqual(a.resolved_logical, "glm-turbo")
        self.assertEqual(a.fallback_from, "claude-haiku")
        self.assertIn("ledger", a.fallback_reason.lower())

    def test_exhausted_with_unknown_reset_excluded_by_default(self):
        ledger = CapacityLedger.in_memory()
        ledger.record_exhaustion("claude-sonnet", exhausted_until=None)
        pe = engine(ledger=ledger)
        wp = WorkPackage(id="p8", description="x",
                         required_capabilities=["code-implementation", "refactor",
                                                "review", "long-context"],
                         mode="balanced")
        a = pe.resolve(wp)
        self.assertEqual(a.employee, "senior-software-engineer")
        self.assertEqual(a.fallback_from, "claude-sonnet")
        self.assertIn("codex", a.resolved_logical)

    def test_emergency_mode_allows_exhausted_capacity(self):
        ledger = CapacityLedger.in_memory()
        ledger.record_exhaustion("claude-sonnet", exhausted_until=None)
        pe = engine(ledger=ledger)
        wp = WorkPackage(id="p9", description="x",
                         required_capabilities=["code-implementation", "refactor",
                                                "review", "long-context"],
                         mode="emergency")
        a = pe.resolve(wp)
        self.assertEqual(a.employee, "senior-software-engineer")
        # exhausted, but emergency mode explicitly allows it -> no fallback needed.
        self.assertEqual(a.resolved_logical, "claude-sonnet")
        self.assertIsNone(a.fallback_from)
        self.assertEqual(a.health_state, "exhausted")

    def test_dynamic_quarantine_restricts_to_low_risk(self):
        ledger = CapacityLedger.in_memory()
        ledger.quarantine("qwen-deepinfra", reason="observed low-quality output")
        pe = engine(ledger=ledger)
        wp_normal = WorkPackage(id="p10", description="x",
                                required_capabilities=["documentation", "long-context",
                                                       "bulk-mechanical"],
                                mode="balanced", risk="normal")
        a_normal = pe.resolve(wp_normal)
        self.assertNotEqual(a_normal.resolved_logical, "qwen-deepinfra")

        wp_low = WorkPackage(id="p11", description="x",
                             required_capabilities=["documentation", "long-context",
                                                    "bulk-mechanical"],
                             mode="balanced", risk="low")
        a_low = pe.resolve(wp_low)
        self.assertEqual(a_low.resolved_logical, "qwen-deepinfra")
        self.assertEqual(a_low.health_state, "probationary")


# --------------------------------------------------------------------------- #
# 5. Mode subscription/API-spend policy
# --------------------------------------------------------------------------- #

class TestModeCostPolicy(unittest.TestCase):
    def test_architecture_mode_never_lands_on_elastic_api(self):
        # chief-architect has no fallback chain at all, so this isn't a
        # meaningful api-spend test by itself; use implementation-engineer-
        # shaped work under a hypothetical subscription-only mode instead via
        # release (prefer-subscription, minimize spend) is not hard-blocking,
        # so directly assert architecture's policy predicate here.
        mode = WorkforceModeRegistry().get("architecture")
        ok, _ = mode.permits_cost_class("elastic-api")
        self.assertFalse(ok)


# --------------------------------------------------------------------------- #
# 6. Evidence fields
# --------------------------------------------------------------------------- #

class TestEvidenceFields(unittest.TestCase):
    def test_assignment_carries_capacity_class_and_health_state(self):
        pe = engine()
        wp = WorkPackage(id="p12", description="x", required_capabilities=["microtask"])
        a = pe.resolve(wp)
        self.assertEqual(a.capacity_class, "subscription-abundant")
        self.assertEqual(a.health_state, "healthy")
        self.assertEqual(a.evidence_source, "policy_engine")


if __name__ == "__main__":
    unittest.main(verbosity=2)
