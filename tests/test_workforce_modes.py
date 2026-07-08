"""Tests for LisaOS Workforce Modes (Phase 3).

Validates the REAL, shipped registry/workforce_modes.yml (loaded via
WorkforceModeRegistry(), no injection) cross-checked against the REAL,
shipped registry/employees.yml -- both are the actual files LisaOS will run
with, not fixtures.

Run with:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_workforce_modes -v
"""

import unittest

from core.workforce_modes import (
    WorkforceModeRegistry,
    WorkforceModeError,
    WorkforceMode,
    REQUIRED_MODES,
)
from core.workforce_resolver import EmployeeRegistry


def real_modes() -> WorkforceModeRegistry:
    return WorkforceModeRegistry()


class TestRegistryLoadsAndValidates(unittest.TestCase):
    def test_all_nine_required_modes_present(self):
        modes = real_modes()
        self.assertEqual(set(REQUIRED_MODES),
                         {"economy", "balanced", "premium", "overnight", "release",
                          "research", "emergency", "architecture", "local_future"})
        for name in REQUIRED_MODES:
            self.assertIn(name, modes.modes)

    def test_exactly_nine_modes_shipped(self):
        self.assertEqual(len(real_modes().modes), 9)

    def test_validates_structurally_with_no_problems(self):
        modes = real_modes()
        problems = modes.validate()
        self.assertEqual(problems, [], f"structural problems: {problems}")

    def test_all_referenced_employees_exist_in_real_registry(self):
        modes = real_modes()
        employees = EmployeeRegistry()
        problems = modes.validate(employees)
        self.assertEqual(problems, [], f"unknown employee references: {problems}")

    def test_unknown_mode_raises(self):
        modes = real_modes()
        with self.assertRaises(WorkforceModeError):
            modes.get("nonexistent-mode")

    def test_validate_detects_missing_required_mode(self):
        cfg = {"modes": {"balanced": {}}}
        modes = WorkforceModeRegistry(config=cfg)
        problems = modes.validate()
        self.assertTrue(any("economy" in p for p in problems))

    def test_validate_detects_unknown_employee_reference(self):
        cfg = {"modes": {name: {} for name in REQUIRED_MODES}}
        cfg["modes"]["economy"]["allowed_employees"] = ["not-a-real-employee"]
        modes = WorkforceModeRegistry(config=cfg)
        problems = modes.validate(EmployeeRegistry())
        self.assertTrue(any("not-a-real-employee" in p for p in problems))


class TestModeSpecificPolicy(unittest.TestCase):
    def test_local_future_allows_no_employees(self):
        mode = real_modes().get("local_future")
        self.assertEqual(mode.allowed_employees, [])

    def test_architecture_restricted_to_office_of_cto(self):
        mode = real_modes().get("architecture")
        self.assertEqual(set(mode.allowed_employees), {"chief-architect", "cto-reviewer"})

    def test_economy_excludes_chief_architect(self):
        mode = real_modes().get("economy")
        self.assertNotIn("chief-architect", mode.allowed_employees)

    def test_premium_excludes_bulk_employees(self):
        mode = real_modes().get("premium")
        for excluded in ("implementation-engineer", "documentation-engineer",
                        "operations-microtask-agent", "context-manager"):
            self.assertNotIn(excluded, mode.allowed_employees)

    def test_balanced_has_no_roster_restriction(self):
        mode = real_modes().get("balanced")
        self.assertIsNone(mode.allowed_employees)

    def test_only_emergency_allows_exhausted_capacity(self):
        modes = real_modes()
        for name in REQUIRED_MODES:
            mode = modes.get(name)
            expected = (name == "emergency")
            self.assertEqual(mode.allow_exhausted_capacity, expected,
                             f"mode {name!r} allow_exhausted_capacity unexpectedly {mode.allow_exhausted_capacity}")


class TestFilterEmployees(unittest.TestCase):
    def setUp(self):
        self.employees = EmployeeRegistry()

    def test_architecture_mode_filters_candidates_to_office_of_cto(self):
        mode = real_modes().get("architecture")
        candidates = self.employees.candidates_for(["architecture"])
        filtered = mode.filter_employees(candidates)
        self.assertEqual([c.id for c in filtered], ["chief-architect"])

    def test_local_future_mode_filters_everything_out(self):
        mode = real_modes().get("local_future")
        candidates = self.employees.candidates_for(["microtask"])
        self.assertGreater(len(candidates), 0)   # sanity: real candidates do exist
        filtered = mode.filter_employees(candidates)
        self.assertEqual(filtered, [])

    def test_balanced_mode_is_a_no_op_filter(self):
        mode = real_modes().get("balanced")
        candidates = self.employees.candidates_for(["documentation"])
        filtered = mode.filter_employees(candidates)
        self.assertEqual([c.id for c in filtered], [c.id for c in candidates])

    def test_preferred_employees_ordered_first_without_excluding_others(self):
        mode = real_modes().get("economy")
        candidates = self.employees.candidates_for(["documentation"])
        filtered = mode.filter_employees(candidates)
        ids = [c.id for c in filtered]
        # operations-microtask-agent is both a preferred AND allowed economy
        # employee for 'documentation' -- it must come first.
        self.assertEqual(ids[0], "operations-microtask-agent")


class TestPermitsCostClass(unittest.TestCase):
    def test_subscription_only_mode_rejects_elastic_api(self):
        mode = real_modes().get("architecture")
        ok, why = mode.permits_cost_class("elastic-api")
        self.assertFalse(ok)
        self.assertIn("subscription-only", why)

    def test_forbidden_api_spend_rejects_elastic_api(self):
        mode = real_modes().get("architecture")
        ok, _ = mode.permits_cost_class("elastic-api")
        self.assertFalse(ok)

    def test_allow_metered_mode_permits_elastic_api(self):
        mode = real_modes().get("balanced")
        ok, _ = mode.permits_cost_class("elastic-api")
        self.assertTrue(ok)

    def test_subscription_classes_always_permitted(self):
        mode = real_modes().get("architecture")
        for cc in ("subscription-abundant", "subscription-scarce"):
            ok, _ = mode.permits_cost_class(cc)
            self.assertTrue(ok, f"{cc} should be permitted by architecture mode")

    def test_none_cost_class_is_permitted(self):
        mode = real_modes().get("architecture")
        ok, _ = mode.permits_cost_class(None)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
