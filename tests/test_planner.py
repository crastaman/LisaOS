"""Unit tests for core/planner.py — Phase 2 Natural Language Mission Planner.

All tests are fully hermetic: stub proposers only, no network, no LLM calls,
no spend.  Temporary directories are used for any artifact checks.

Key principle under test: THE LLM PROPOSES, LISA DECIDES.  Nothing a proposer
returns may bypass the validation gate; fail closed on every violation.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

LISA_HOME = str(Path(__file__).resolve().parent.parent)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_proposer(text: str):
    """Return a stub ProposerFn that echoes `text` regardless of input."""
    def _propose(prompt: str, context: dict) -> str:
        return text
    return _propose


def _make_raising_proposer(exc):
    """Return a stub ProposerFn that always raises `exc`."""
    def _propose(prompt: str, context: dict) -> str:
        raise exc
    return _propose


def _valid_single_pkg(overrides=None) -> dict:
    pkg = {
        "id": "analyze-code",
        "description": "Analyze the repository source files and produce a summary of all modules.",
        "required_capabilities": ["code-implementation"],
        "risk": "normal",
        "mode": "balanced",
        "depends_on": [],
    }
    if overrides:
        pkg.update(overrides)
    return pkg


def _valid_multi_plan() -> list:
    return [
        {
            "id": "read-repo",
            "description": "Read the repository structure and identify all Python source files in the project.",
            "required_capabilities": ["code-implementation"],
            "risk": "low",
            "mode": "balanced",
            "depends_on": [],
        },
        {
            "id": "write-docs",
            "description": "Write a comprehensive documentation page describing the architecture of the project.",
            "required_capabilities": ["documentation"],
            "risk": "low",
            "mode": "balanced",
            "depends_on": ["read-repo"],
        },
    ]


# ── Import under test ─────────────────────────────────────────────────────────

import sys
sys.path.insert(0, LISA_HOME)

from core.planner import (
    PlanError,
    PlanValidationError,
    MissionPlan,
    build_prompt,
    parse_plan_text,
    known_capabilities,
    validate_plan,
    plan_mission,
    MAX_PACKAGES,
    MAX_DESCRIPTION_CHARS,
    MIN_DESCRIPTION_CHARS,
    MAX_ID_CHARS,
)


# ── known_capabilities ────────────────────────────────────────────────────────

class TestKnownCapabilities(unittest.TestCase):

    def test_excludes_deterministic_employees(self):
        caps = known_capabilities()
        # "routing" and "scheduling" belong to dispatcher-manager (deterministic)
        # "provider-resolution" belongs to provider-manager (deterministic)
        self.assertNotIn("routing", caps,
                         "deterministic employee capability leaked into vocabulary")
        self.assertNotIn("scheduling", caps,
                         "deterministic employee capability leaked into vocabulary")
        self.assertNotIn("provider-resolution", caps,
                         "deterministic employee capability leaked into vocabulary")

    def test_includes_known_non_deterministic_caps(self):
        caps = known_capabilities()
        # Spot-check a few capabilities that belong to non-deterministic employees
        for expected in ["code-implementation", "documentation", "review",
                         "deep-reasoning", "research"]:
            self.assertIn(expected, caps,
                          f"expected capability {expected!r} missing from vocabulary")

    def test_returns_sorted_list(self):
        caps = known_capabilities()
        self.assertEqual(caps, sorted(caps))

    def test_matches_employees_yml(self):
        """known_capabilities() must be derived from employees.yml (never agents.yml)."""
        from core.workforce_resolver import EmployeeRegistry
        reg = EmployeeRegistry()
        expected = set()
        for emp in reg.employees.values():
            if not emp.is_deterministic:
                expected.update(emp.capabilities)
        self.assertEqual(set(known_capabilities()), expected)


# ── build_prompt ──────────────────────────────────────────────────────────────

class TestBuildPrompt(unittest.TestCase):

    def _prompt(self):
        caps = ["code-implementation", "documentation", "research"]
        modes = ["balanced", "economy", "premium"]
        return build_prompt("Implement the new user API endpoint.", caps, modes)

    def test_contains_mission(self):
        p = self._prompt()
        self.assertIn("Implement the new user API endpoint.", p)

    def test_contains_all_capabilities(self):
        p = self._prompt()
        for cap in ["code-implementation", "documentation", "research"]:
            self.assertIn(cap, p)

    def test_contains_all_modes(self):
        p = self._prompt()
        for mode in ["balanced", "economy", "premium"]:
            self.assertIn(mode, p)

    def test_forbids_worker_naming(self):
        p = self._prompt()
        # The prompt must instruct not to name workers/models
        lower = p.lower()
        self.assertIn("do not name", lower)

    def test_mentions_max_packages(self):
        p = self._prompt()
        self.assertIn(str(MAX_PACKAGES), p)

    def test_mentions_description_bounds(self):
        p = self._prompt()
        self.assertIn(str(MIN_DESCRIPTION_CHARS), p)
        self.assertIn(str(MAX_DESCRIPTION_CHARS), p)

    def test_mentions_depends_on_acyclic(self):
        p = self._prompt()
        self.assertIn("acyclic", p.lower())

    def test_returns_only_json_array_instruction(self):
        p = self._prompt()
        self.assertIn("JSON array", p)


# ── parse_plan_text ───────────────────────────────────────────────────────────

class TestParsePlanText(unittest.TestCase):

    def _plan_json(self):
        return json.dumps([_valid_single_pkg()])

    def test_bare_array(self):
        result = parse_plan_text(self._plan_json())
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_json_fenced_block(self):
        text = f"```json\n{self._plan_json()}\n```"
        result = parse_plan_text(text)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_unlabelled_fence(self):
        text = f"```\n{self._plan_json()}\n```"
        result = parse_plan_text(text)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_prose_wrapped(self):
        text = (
            "Here is the plan I generated:\n"
            f"{self._plan_json()}\n"
            "I hope this helps!"
        )
        result = parse_plan_text(text)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_prose_before_and_after(self):
        text = f"Sure, here you go: {self._plan_json()} That's my suggestion."
        result = parse_plan_text(text)
        self.assertIsInstance(result, list)

    def test_unparseable_raises(self):
        with self.assertRaises(PlanValidationError) as ctx:
            parse_plan_text("This is not JSON at all.")
        self.assertTrue(ctx.exception.errors)

    def test_empty_string_raises(self):
        with self.assertRaises(PlanValidationError):
            parse_plan_text("")

    def test_json_object_not_array_raises(self):
        with self.assertRaises(PlanValidationError):
            parse_plan_text('{"key": "value"}')

    def test_truncated_json_raises(self):
        with self.assertRaises(PlanValidationError):
            parse_plan_text("[{invalid json")


# ── validate_plan — success paths ─────────────────────────────────────────────

class TestValidatePlanSuccess(unittest.TestCase):

    def test_valid_single_package(self):
        result = validate_plan([_valid_single_pkg()])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_valid_multi_package_with_deps(self):
        result = validate_plan(_valid_multi_plan())
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_normalization_fills_defaults(self):
        pkg = {
            "id": "task-one",
            "description": "Read all configuration files and list their key-value pairs.",
            "required_capabilities": ["code-implementation"],
        }
        result = validate_plan([pkg])
        p = result[0]
        self.assertEqual(p["risk"], "normal")
        self.assertEqual(p["mode"], "balanced")
        self.assertEqual(p["depends_on"], [])

    def test_normalization_key_order(self):
        result = validate_plan([_valid_single_pkg()])
        keys = list(result[0].keys())
        self.assertEqual(
            keys,
            ["id", "description", "required_capabilities", "risk", "mode", "depends_on"],
        )

    def test_normalization_preserves_explicit_values(self):
        pkg = _valid_single_pkg({"risk": "low", "mode": "economy", "depends_on": []})
        result = validate_plan([pkg])
        self.assertEqual(result[0]["risk"], "low")
        self.assertEqual(result[0]["mode"], "economy")


# ── validate_plan — P1 ────────────────────────────────────────────────────────

class TestValidatePlanP1(unittest.TestCase):

    def test_empty_plan_rejected(self):
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([])
        self.assertTrue(any("P1" in e for e in ctx.exception.errors))

    def test_oversized_plan_rejected(self):
        pkg_base = {
            "description": "Do something specific and well-defined in the codebase.",
            "required_capabilities": ["code-implementation"],
        }
        packages = [
            dict(pkg_base, id=f"pkg-{i:02d}", depends_on=[])
            for i in range(MAX_PACKAGES + 1)
        ]
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan(packages)
        self.assertTrue(any("P1" in e for e in ctx.exception.errors))

    def test_not_a_list_raises(self):
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan({"id": "x"})
        self.assertTrue(any("P1" in e for e in ctx.exception.errors))


# ── validate_plan — P2 ────────────────────────────────────────────────────────

class TestValidatePlanP2(unittest.TestCase):

    def test_non_dict_element_rejected(self):
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan(["not-a-dict"])
        self.assertTrue(any("P2" in e for e in ctx.exception.errors))


# ── validate_plan — P3 ────────────────────────────────────────────────────────

class TestValidatePlanP3(unittest.TestCase):

    def _bad(self, **kw):
        pkg = _valid_single_pkg()
        pkg.update(kw)
        return pkg

    def test_missing_id(self):
        pkg = _valid_single_pkg()
        del pkg["id"]
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P3" in e for e in ctx.exception.errors))

    def test_blank_id(self):
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([self._bad(id="")])
        self.assertTrue(any("P3" in e for e in ctx.exception.errors))

    def test_bad_charset_id(self):
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([self._bad(id="BAD ID!")])
        self.assertTrue(any("P3" in e for e in ctx.exception.errors))

    def test_uppercase_id_rejected(self):
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([self._bad(id="MyTask")])
        self.assertTrue(any("P3" in e for e in ctx.exception.errors))

    def test_too_long_id_rejected(self):
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([self._bad(id="a" * (MAX_ID_CHARS + 1))])
        self.assertTrue(any("P3" in e for e in ctx.exception.errors))

    def test_duplicate_id_rejected(self):
        plans = [_valid_single_pkg(), _valid_single_pkg()]  # same id
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan(plans)
        self.assertTrue(any("P3" in e and "duplicate" in e.lower()
                            for e in ctx.exception.errors))


# ── validate_plan — P4 ────────────────────────────────────────────────────────

class TestValidatePlanP4(unittest.TestCase):

    def test_missing_description(self):
        pkg = _valid_single_pkg()
        del pkg["description"]
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P4" in e for e in ctx.exception.errors))

    def test_too_short_description(self):
        pkg = _valid_single_pkg({"description": "short"})  # < MIN_DESCRIPTION_CHARS
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P4" in e for e in ctx.exception.errors))

    def test_too_long_description(self):
        pkg = _valid_single_pkg({"description": "x" * (MAX_DESCRIPTION_CHARS + 1)})
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P4" in e for e in ctx.exception.errors))

    def test_exactly_min_chars_accepted(self):
        pkg = _valid_single_pkg({"description": "x" * MIN_DESCRIPTION_CHARS})
        result = validate_plan([pkg])
        self.assertEqual(len(result), 1)

    def test_exactly_max_chars_accepted(self):
        pkg = _valid_single_pkg({"description": "x" * MAX_DESCRIPTION_CHARS})
        result = validate_plan([pkg])
        self.assertEqual(len(result), 1)


# ── validate_plan — P5 ────────────────────────────────────────────────────────

class TestValidatePlanP5(unittest.TestCase):

    def test_missing_capabilities(self):
        pkg = _valid_single_pkg()
        del pkg["required_capabilities"]
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P5" in e for e in ctx.exception.errors))

    def test_empty_capabilities(self):
        pkg = _valid_single_pkg({"required_capabilities": []})
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P5" in e for e in ctx.exception.errors))


# ── validate_plan — P6 hallucinated capability ───────────────────────────────

class TestValidatePlanP6(unittest.TestCase):

    def test_hallucinated_capability_rejected(self):
        pkg = _valid_single_pkg({"required_capabilities": ["wizardry"]})
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        errors = ctx.exception.errors
        self.assertTrue(any("P6" in e for e in errors),
                        f"expected P6 error; got: {errors}")
        self.assertTrue(any("wizardry" in e for e in errors))

    def test_mix_real_and_hallucinated_rejected(self):
        pkg = _valid_single_pkg(
            {"required_capabilities": ["code-implementation", "mindreading"]}
        )
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P6" in e for e in ctx.exception.errors))


# ── validate_plan — P7 unstaffable ───────────────────────────────────────────

class TestValidatePlanP7(unittest.TestCase):

    def test_unstaffable_combination_rejected(self):
        """architecture + documentation: no single employee holds both.

        Verified against the live registry: chief-architect has 'architecture'
        but not 'documentation'; documentation-engineer has 'documentation'
        but not 'architecture'; no other employee has 'architecture' at all.
        """
        from core.workforce_resolver import EmployeeRegistry
        reg = EmployeeRegistry()
        candidates = reg.candidates_for(["architecture", "documentation"])
        self.assertEqual(
            candidates, [],
            "P7 test precondition failed: found a candidate for "
            "['architecture', 'documentation']; update the test pair",
        )

        pkg = _valid_single_pkg(
            {"required_capabilities": ["architecture", "documentation"]}
        )
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        errors = ctx.exception.errors
        self.assertTrue(any("P7" in e for e in errors),
                        f"expected P7 error; got: {errors}")

    def test_staffable_combination_accepted(self):
        """code-implementation is provided by several employees."""
        pkg = _valid_single_pkg({"required_capabilities": ["code-implementation"]})
        result = validate_plan([pkg])
        self.assertEqual(len(result), 1)


# ── validate_plan — P8 ────────────────────────────────────────────────────────

class TestValidatePlanP8(unittest.TestCase):

    def test_bad_risk_rejected(self):
        pkg = _valid_single_pkg({"risk": "EXTREME"})
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P8" in e for e in ctx.exception.errors))

    def test_valid_risks_accepted(self):
        for risk in ("low", "normal", "critical"):
            pkg = _valid_single_pkg({"risk": risk})
            result = validate_plan([pkg])
            self.assertEqual(result[0]["risk"], risk)


# ── validate_plan — P9 ────────────────────────────────────────────────────────

class TestValidatePlanP9(unittest.TestCase):

    def test_unknown_mode_rejected(self):
        pkg = _valid_single_pkg({"mode": "turbo-overdrive"})
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P9" in e for e in ctx.exception.errors))

    def test_known_modes_accepted(self):
        for mode in ("balanced", "economy", "premium"):
            pkg = _valid_single_pkg({"mode": mode})
            result = validate_plan([pkg])
            self.assertEqual(result[0]["mode"], mode)


# ── validate_plan — P10 ───────────────────────────────────────────────────────

class TestValidatePlanP10(unittest.TestCase):

    def test_depends_on_non_list_rejected(self):
        pkg = _valid_single_pkg({"depends_on": "pkg-a"})  # string, not list
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P10" in e for e in ctx.exception.errors))


# ── validate_plan — P11 ───────────────────────────────────────────────────────

class TestValidatePlanP11(unittest.TestCase):

    def test_unknown_key_rejected(self):
        pkg = _valid_single_pkg({"priority": "high"})  # not in allowed set
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        self.assertTrue(any("P11" in e for e in ctx.exception.errors))


# ── validate_plan — P12 graph integrity ──────────────────────────────────────

class TestValidatePlanP12(unittest.TestCase):

    def _pkg(self, id_, deps=None, caps=None):
        return {
            "id": id_,
            "description": f"Perform the {id_} task with full context and clear output deliverables.",
            "required_capabilities": caps or ["code-implementation"],
            "risk": "normal",
            "mode": "balanced",
            "depends_on": deps or [],
        }

    def test_self_dependency_rejected(self):
        pkg = self._pkg("task-a", deps=["task-a"])
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        errors = ctx.exception.errors
        self.assertTrue(
            any("P12" in e for e in errors),
            f"expected P12 error; got: {errors}",
        )

    def test_unknown_dependency_rejected(self):
        pkg = self._pkg("task-a", deps=["task-z"])
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg])
        errors = ctx.exception.errors
        self.assertTrue(any("P12" in e for e in errors),
                        f"expected P12 error; got: {errors}")

    def test_duplicate_ids_rejected(self):
        """Duplicate ids caught by P3 before P12, but still rejected."""
        pkg_a = self._pkg("task-a")
        pkg_b = self._pkg("task-a")  # duplicate
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg_a, pkg_b])
        errors = ctx.exception.errors
        self.assertTrue(
            any("P3" in e and "duplicate" in e.lower() for e in errors),
            f"expected P3 duplicate error; got: {errors}",
        )

    def test_two_cycle_rejected(self):
        pkg_a = self._pkg("task-a", deps=["task-b"])
        pkg_b = self._pkg("task-b", deps=["task-a"])
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan([pkg_a, pkg_b])
        errors = ctx.exception.errors
        self.assertTrue(any("P12" in e for e in errors),
                        f"expected P12 cycle error; got: {errors}")

    def test_valid_dag_accepted(self):
        pkg_a = self._pkg("task-a", deps=[])
        pkg_b = self._pkg("task-b", deps=["task-a"])
        pkg_c = self._pkg("task-c", deps=["task-a"])
        result = validate_plan([pkg_a, pkg_b, pkg_c])
        self.assertEqual(len(result), 3)


# ── validate_plan — multi-error accumulation ─────────────────────────────────

class TestValidatePlanMultiError(unittest.TestCase):

    def test_three_distinct_violations_all_reported(self):
        """A plan with ≥3 violations must report all of them."""
        packages = [
            {
                "id": "BAD ID!",           # P3: bad charset
                "description": "x",         # P4: too short
                "required_capabilities": ["wizardry"],  # P6: hallucinated
                "risk": "MEGA",            # P8: bad risk
                "mode": "balanced",
                "depends_on": [],
            }
        ]
        with self.assertRaises(PlanValidationError) as ctx:
            validate_plan(packages)
        errors = ctx.exception.errors
        self.assertGreaterEqual(
            len(errors), 3,
            f"expected ≥3 errors; got {len(errors)}: {errors}",
        )


# ── plan_mission ──────────────────────────────────────────────────────────────

class TestPlanMission(unittest.TestCase):

    def _valid_stub(self):
        return _make_proposer(json.dumps([_valid_single_pkg()]))

    def test_success_returns_mission_plan(self):
        plan = plan_mission(
            "Implement a new user API endpoint.",
            proposer=self._valid_stub(),
            proposer_id="stub",
        )
        self.assertIsInstance(plan, MissionPlan)
        self.assertEqual(len(plan.packages), 1)
        self.assertEqual(plan.proposer_id, "stub")
        self.assertEqual(plan.mission, "Implement a new user API endpoint.")

    def test_to_goal_json_is_bare_array(self):
        plan = plan_mission(
            "Implement a new user API endpoint.",
            proposer=self._valid_stub(),
        )
        parsed = json.loads(plan.to_goal_json())
        self.assertIsInstance(parsed, list)

    def test_raising_proposer_becomes_plan_error(self):
        from core.planner import PlanError
        proposer = _make_raising_proposer(RuntimeError("network timeout"))
        with self.assertRaises(PlanError):
            plan_mission("Do something.", proposer=proposer)

    def test_invalid_plan_raises_plan_validation_error(self):
        proposer = _make_proposer(json.dumps([{"id": "BAD!", "description": "x",
                                              "required_capabilities": []}]))
        with self.assertRaises(PlanValidationError):
            plan_mission("Do something.", proposer=proposer)

    def test_never_returns_unvalidated_plan(self):
        """plan_mission with an invalid response must not return a MissionPlan."""
        bad_proposer = _make_proposer("this is not json")
        raised = False
        try:
            plan_mission("Do something.", proposer=bad_proposer)
        except (PlanError, PlanValidationError):
            raised = True
        self.assertTrue(raised, "plan_mission returned without raising on bad proposer output")

    def test_raw_response_preserved(self):
        raw = json.dumps([_valid_single_pkg()])
        plan = plan_mission("Do something.", proposer=_make_proposer(raw))
        self.assertEqual(plan.raw_response, raw)


# ── fail-closed proofs ────────────────────────────────────────────────────────

class TestFailClosedNoArtifact(unittest.TestCase):
    """For every invalid case, no artifact file should be created.

    These tests exercise validate_plan directly; bin/lisa entrypoint tests
    verify the file-not-created assertion at the subprocess level.
    """

    def test_empty_plan_raises_not_returns(self):
        raised = False
        try:
            validate_plan([])
        except PlanValidationError:
            raised = True
        self.assertTrue(raised)

    def test_hallucinated_cap_raises_not_returns(self):
        raised = False
        try:
            validate_plan([_valid_single_pkg({"required_capabilities": ["telekinesis"]})])
        except PlanValidationError:
            raised = True
        self.assertTrue(raised)

    def test_cycle_raises_not_returns(self):
        def _pkg(id_, deps):
            return {
                "id": id_,
                "description": "Perform a specific well-bounded analysis task with no ambiguity.",
                "required_capabilities": ["code-implementation"],
                "risk": "normal",
                "mode": "balanced",
                "depends_on": deps,
            }
        raised = False
        try:
            validate_plan([_pkg("a", ["b"]), _pkg("b", ["a"])])
        except PlanValidationError:
            raised = True
        self.assertTrue(raised)

    def test_bad_risk_raises_not_returns(self):
        raised = False
        try:
            validate_plan([_valid_single_pkg({"risk": "CATASTROPHIC"})])
        except PlanValidationError:
            raised = True
        self.assertTrue(raised)

    def test_unknown_mode_raises_not_returns(self):
        raised = False
        try:
            validate_plan([_valid_single_pkg({"mode": "ludicrous-speed"})])
        except PlanValidationError:
            raised = True
        self.assertTrue(raised)


# ── no agents.yml reference ────────────────────────────────────────────────────

class TestNoAgentsYmlReference(unittest.TestCase):

    def test_planner_source_contains_no_agents_yml(self):
        planner_path = Path(__file__).resolve().parent.parent / "core" / "planner.py"
        src = planner_path.read_text()
        self.assertNotIn(
            "agents.yml",
            src,
            "core/planner.py must never reference agents.yml "
            "(dual-registry drift is explicitly prohibited)",
        )


if __name__ == "__main__":
    unittest.main()
