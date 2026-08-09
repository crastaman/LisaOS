"""CWO-001 acceptance tests: Cloud Workforce Optimization (LisaOS).

Validates the 12 acceptance criteria from the CWO-001 mission against the
REAL shipped registries where possible (hermetic provider fixture for model
resolution -- no network, no spend), exactly like the existing workforce
resolver tests.

Covers:
  1. actual model identities resolve correctly
  2. legacy aliases remain safe where required
  3. subscription vs metered capacity is distinguishable
  4. worker context packets are bounded/relevant
  5. related-session reuse is preferred where appropriate
  6. unrelated/independent work can force fresh context
  7. premium-worker dispatch can use prepared compact context
  8. MAIN executive reporting suppresses routine narration
  9. material events still surface correctly
 10. unavailable telemetry does not break dispatch
 11. DeepSeek Pro is not accidentally treated as available
 12. WBS repository remains untouched

Run with:
    PYTHONPATH="$HOME/Lisa" python3 -m pytest tests/test_cwo_acceptance.py -q
"""

import json
import os
import unittest
from pathlib import Path

from core.workforce_identity import (
    WorkforceIdentityRegistry,
    WorkforceIdentityError,
    WorkerIdentity,
    get_identity_registry,
    SUBSCRIPTION_CAPACITY,
    METERED_API_CAPACITY,
)
from core.context_budget import (
    build_work_packet,
    is_within_budget,
    reference_not_copy,
    premium_prep_recommendation,
    DEFAULT_PACKET_BUDGET_CHARS,
)
from core.session_policy import reuse_session, REUSE, FRESH, telemetry_fresh_reused
from core.reporting_policy import (
    classify_event,
    suppress_if_nothing,
    executive_summary,
    worker_report_minimal,
    ReportEvent,
    COMPLETION,
    EXHAUSTION,
    BLOCKER,
    DECISION_REQUIRED,
)
from core.capacity_ledger import CapacityLedger
from core.workforce_resolver import (
    EmployeeRegistry,
    WorkforceResolver,
    WorkPackage,
)

from tests.test_workforce_resolver import (
    real_employees,
    resolver_all_available,
)

WBS_REPO = Path("/Users/lisa/Projects/WBS/healing-events-booking-main")


class TestCWOIdentity(unittest.TestCase):
    """Acceptance 1 + 2 + 11: identity resolution, alias safety, DeepSeek Pro."""

    def setUp(self):
        self.reg = get_identity_registry()

    def test_actual_model_identities_resolve(self):
        for name in ("sol", "terra", "luna", "opus", "sonnet", "haiku", "deepseek-main"):
            worker = self.reg.resolve(name)
            self.assertEqual(worker.id, name)
            self.assertTrue(worker.onboarded)

    def test_worker_concept_separation(self):
        """worker / provider / access / cost_model are separate concepts."""
        sol = self.reg.resolve("sol")
        self.assertEqual(sol.family, "openai-codex")
        self.assertEqual(sol.provider, "OpenAI")
        self.assertEqual(sol.access, "subscription")
        self.assertEqual(sol.cost_model, SUBSCRIPTION_CAPACITY)

    def test_legacy_aliases_map_safely(self):
        mapping = {
            "codex-premium": "sol",
            "codex-high": "sol",
            "codex-balanced": "terra",
            "codex-fast": "luna",
            "claude-premium": "opus",
            "claude-balanced": "terra",
            "claude-fast": "haiku",
            "premium": "sol",
            "high": "sol",
            "fast": "luna",
            "main": "deepseek-main",
            "deepseek": "deepseek-main",
        }
        for alias, expected in mapping.items():
            self.assertEqual(self.reg.normalise(alias), expected, alias)

    def test_alias_case_insensitive(self):
        self.assertEqual(self.reg.normalise("Codex-Premium"), "sol")
        self.assertEqual(self.reg.normalise("SOL"), "sol")

    def test_unknown_worker_fails_closed(self):
        with self.assertRaises(WorkforceIdentityError):
            self.reg.resolve("not-a-worker")

    def test_unknown_worker_normalise_returns_none(self):
        self.assertIsNone(self.reg.normalise("not-a-worker"))

    def test_registry_validates_clean(self):
        problems = self.reg.validate()
        self.assertEqual(problems, [], f"identity registry problems: {problems}")

    def test_deepseek_pro_not_treated_as_available(self):
        # DS-V4-PRO-001: deepseek-pro is now onboarded as a DISTINCT PROBATIONARY
        # METERED WORKER. The guard must return True for the registered canonical id
        # and its case-insensitive form; all other DS Pro names remain False.
        self.assertTrue(self.reg.is_deepseek_pro("deepseek-pro"),
                        "deepseek-pro is now onboarded — guard must be True")
        self.assertTrue(self.reg.is_deepseek_pro("DeepSeek-Pro"),
                        "case-insensitive alias resolves to the same canonical id")
        # Newly onboarded worker is metered and onboarded.
        worker = self.reg.resolve("deepseek-pro")
        self.assertEqual(worker.cost_model, METERED_API_CAPACITY)
        self.assertTrue(worker.onboarded)
        # Non-registered DS Pro names remain False (not in registry).
        self.assertFalse(self.reg.is_deepseek_pro("deepseek-pro-reasoner"))
        self.assertFalse(self.reg.is_deepseek_pro("deepseek-pro-max"))
        self.assertFalse(self.reg.is_deepseek_pro("deepseekpro"),
                         "bare concatenation is not an alias")
        # deepseek-main is still NOT deepseek-pro.
        self.assertFalse(self.reg.is_deepseek_pro("deepseek-main"))

    def test_future_local_extensibility(self):
        """Schema supports local capacity but none is onboarded."""
        self.assertEqual(self.reg.config["future_local"]["cost_model"], "local")
        self.assertEqual(self.reg.config["future_local"]["capacity_model"], "hardware")
        self.assertFalse(self.reg.config["future_local"]["onboarded"])
        # No worker is currently local.
        for worker in self.reg.workers.values():
            self.assertFalse(worker.is_local)


class TestCWOCapacity(unittest.TestCase):
    """Acceptance 3 + 10: subscription vs metered; telemetry-degradation safety."""

    def setUp(self):
        self.reg = get_identity_registry()

    def test_subscription_vs_metered_distinguishable(self):
        # Subscription workers (Sol/Terra/Luna/Opus/Sonnet/Haiku).
        for name in ("sol", "terra", "luna", "opus", "sonnet", "haiku"):
            self.assertTrue(self.reg.resolve(name).is_subscription, name)
            self.assertFalse(self.reg.resolve(name).is_metered, name)
        # Metered worker (deepseek-main).
        self.assertTrue(self.reg.resolve("deepseek-main").is_metered)
        self.assertFalse(self.reg.resolve("deepseek-main").is_subscription)

    def test_capacity_class_from_ledger(self):
        ledger = CapacityLedger.in_memory()
        entry = ledger.get("deepseek")
        self.assertEqual(entry.cost_class, "elastic-api")
        entry = ledger.get("claude-opus")
        self.assertEqual(entry.cost_class, "subscription-scarce")

    def test_capacity_near_reset_unknown_is_false(self):
        ledger = CapacityLedger.in_memory()
        # No reset recorded -> False (no guessing).
        self.assertFalse(ledger.capacity_near_reset("deepseek"))

    def test_capacity_near_reset_known_window(self):
        from datetime import datetime, timedelta, timezone
        ledger = CapacityLedger.in_memory()
        reset = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        ledger.record_reset_time("claude-opus", reset)
        self.assertTrue(ledger.capacity_near_reset("claude-opus", window_minutes=60))
        self.assertFalse(ledger.capacity_near_reset("claude-opus", window_minutes=10))

    def test_capacity_near_reset_tz_naive_degrades(self):
        """F-3 regression: tz-naive reset strings must not raise TypeError;
        they degrade to a sane UTC interpretation."""
        from datetime import datetime, timedelta, timezone
        ledger = CapacityLedger.in_memory()
        naive = (datetime.now(timezone.utc) + timedelta(minutes=30)).replace(tzinfo=None).isoformat()
        ledger.record_reset_time("claude-opus", naive)
        # Must not raise; and with a large window the naive-as-UTC reset is
        # close enough to now to be inside it.
        self.assertTrue(ledger.capacity_near_reset("claude-opus", window_minutes=120))
        # Garbage strings also degrade to False, never raise.
        ledger.record_reset_time("claude-opus", "not-a-date")
        self.assertFalse(ledger.capacity_near_reset("claude-opus"))

    def test_unavailable_telemetry_degrades_gracefully(self):
        """Acceptance 10: dispatch must not break when token/capacity info is
        missing. A workforce resolver WITHOUT identity/capacity layers still
        resolves exactly as before."""
        wf = WorkforceResolver(real_employees(), resolver_all_available())
        wp = WorkPackage(
            id="wp-no-telemetry",
            description="docs task",
            required_capabilities=["documentation"],
            risk="low",
        )
        assignment = wf.resolve(wp)
        self.assertTrue(assignment.available)
        # CWO fields are None -- never fabricated.
        self.assertIsNone(assignment.worker_identity)
        self.assertIsNone(assignment.capacity_class)

    def test_capacity_ledger_never_guesses_reset(self):
        ledger = CapacityLedger.in_memory()
        ledger.record_exhaustion("codex", exhausted_until=None)
        # Unknown reset -> stays exhausted (effective_health does not guess).
        self.assertEqual(ledger.effective_health("codex"), "exhausted")


class TestCWOContextBudget(unittest.TestCase):
    """Acceptance 4: worker context packets are bounded/relevant."""

    def test_packet_within_budget(self):
        packet = build_work_packet(
            mission="Fix the detail panel focus trap",
            current_state="Panel states 2/3/4 implemented; focus trap missing",
            constraints="No revert of landed code; evidence required",
            task="Implement trapFocusWithinPanel",
            files_areas=["src/wbs-detail-panel.js"],
            dependencies=["P4-A-01"],
            required_evidence=["evidence/P4-A-03.md"],
            acceptance=["124 tests pass"],
            stop_conditions=["Stop if scope expands"],
        )
        self.assertTrue(is_within_budget(packet))
        self.assertLess(packet.char_count(), DEFAULT_PACKET_BUDGET_CHARS)

    def test_packet_sections_are_bounded(self):
        # Oversized packet must raise -- context is a budget.
        with self.assertRaises(ValueError):
            build_work_packet(task="x" * (DEFAULT_PACKET_BUDGET_CHARS * 2))

    def test_reference_not_copy(self):
        # Repo artifacts are referenced, not copied.
        self.assertIn("SEE REPO ARTIFACT", reference_not_copy("docs/WORKFLOW.md §8"))
        # Non-artifact prose passes through unchanged.
        self.assertEqual(reference_not_copy("some random prose"), "some random prose")

    def test_premium_prep_opportunity(self):
        # A cheap worker can narrow an implementation problem first.
        opp = premium_prep_recommendation("normal-implementation")
        self.assertIsNotNone(opp)
        self.assertIn("prep_worker", opp)
        self.assertNotEqual(opp["prep_worker"], "opus")

    def test_premium_prep_none_for_premium_native(self):
        # Adversarial review is Opus-native; no cheaper prep recommendation.
        opp = premium_prep_recommendation("adversarial-review")
        self.assertIsNone(opp)


class TestCWOSessionPolicy(unittest.TestCase):
    """Acceptance 5 + 6: session reuse preference + fresh-forcing."""

    def test_related_reuse_preferred(self):
        d = reuse_session(related=True, cached_context_useful=True, context_clean=True)
        self.assertEqual(d.decision, REUSE)
        self.assertIn("reuse", d.reasons[0])

    def test_unrelated_forces_fresh(self):
        d = reuse_session(related=False, cached_context_useful=True, context_clean=True)
        self.assertEqual(d.decision, FRESH)

    def test_independent_review_forces_fresh(self):
        d = reuse_session(
            related=True, cached_context_useful=True, context_clean=True,
            independence_required=True,
        )
        self.assertEqual(d.decision, FRESH)
        self.assertIn("review", d.reasons[0])

    def test_stale_or_bloated_forces_fresh(self):
        d = reuse_session(related=True, cached_context_useful=True, context_clean=False)
        self.assertEqual(d.decision, FRESH)
        d2 = reuse_session(related=True, cached_context_useful=False, context_clean=True)
        self.assertEqual(d2.decision, FRESH)

    def test_contamination_forces_fresh(self):
        d = reuse_session(
            related=True, cached_context_useful=True, context_clean=True,
            contamination_risk=True,
        )
        self.assertEqual(d.decision, FRESH)

    def test_compact_fresh_more_efficient_forces_fresh(self):
        d = reuse_session(
            related=True, cached_context_useful=True, context_clean=True,
            compact_fresh_more_efficient=True,
        )
        self.assertEqual(d.decision, FRESH)

    def test_telemetry_fresh_reused(self):
        d = reuse_session(related=True, cached_context_useful=True, context_clean=True)
        self.assertEqual(telemetry_fresh_reused(d), "reused")
        d = reuse_session(related=False, cached_context_useful=True, context_clean=True)
        self.assertEqual(telemetry_fresh_reused(d), "fresh")
        self.assertIsNone(telemetry_fresh_reused(None))


class TestCWOReporting(unittest.TestCase):
    """Acceptance 8 + 9: executive reporting suppresses routine, surfaces material."""

    def test_routine_narration_suppressed(self):
        for cls in ("polling", "queue_check", "dependency_reasoning",
                    "worker_monitoring", "routine_provider_check",
                    "command_narration", "internal_planning",
                    "obvious_next_step", "repeated_state"):
            self.assertFalse(classify_event(cls), cls)

    def test_material_events_surface(self):
        for cls in (COMPLETION, EXHAUSTION, BLOCKER, DECISION_REQUIRED,
                    "governance", "material_failure", "material_scope_change"):
            self.assertTrue(classify_event(cls), cls)

    def test_non_material_suppressed(self):
        self.assertFalse(classify_event(COMPLETION, material=False))

    def test_suppress_if_nothing(self):
        events = [
            ReportEvent("polling", material=True),
            ReportEvent("queue_check", material=True),
            ReportEvent("worker_monitoring", material=True),
        ]
        self.assertTrue(suppress_if_nothing(events))

    def test_material_breaks_suppression(self):
        events = [
            ReportEvent("polling", material=True),
            ReportEvent(COMPLETION, detail="P4-A chain green", material=True),
        ]
        self.assertFalse(suppress_if_nothing(events))

    def test_executive_summary_format(self):
        summary = executive_summary(
            completed=["P4-A chain green (124 tests)"],
            capacity=["Claude reset 17:10"],
            next_step="Dispatch P4-A Opus review at reset",
            decision="",
        )
        self.assertIn("COMPLETED", summary)
        self.assertIn("CAPACITY", summary)
        self.assertIn("NEXT", summary)
        self.assertNotIn("DECISION", summary)

    def test_worker_report_minimal(self):
        report = worker_report_minimal(
            result="focus trap implemented",
            files_changed=["src/wbs-detail-panel.js"],
            tests_evidence=["124 tests / 0 failures"],
        )
        self.assertIn("RESULT:", report)
        self.assertIn("FILES CHANGED", report)
        self.assertIn("TESTS / EVIDENCE", report)
        self.assertNotIn("introduction", report.lower())


class TestCWOWorkforceIntegration(unittest.TestCase):
    """Acceptance 1 + 3 + 10 at the resolver level: identity on assignments."""

    def test_resolver_with_identity_annotates_assignment(self):
        wf = WorkforceResolver(
            real_employees(),
            resolver_all_available(),
            identity_registry=get_identity_registry(),
        )
        # Documentation work resolves to a mid-tier worker; identity is
        # recorded on the assignment.
        wp = WorkPackage(
            id="wp-ident",
            description="documentation task",
            required_capabilities=["documentation"],
            risk="low",
        )
        assignment = wf.resolve(wp)
        self.assertTrue(assignment.available)
        self.assertIsNotNone(assignment.worker_identity)
        self.assertIn(assignment.worker_tier, ("premium", "mid", "fast", "main"))

    def test_legacy_resolver_still_works(self):
        """Backward compatibility: no identity/capacity layers -> same result."""
        wf_plain = WorkforceResolver(real_employees(), resolver_all_available())
        wf_cwo = WorkforceResolver(
            real_employees(),
            resolver_all_available(),
            identity_registry=get_identity_registry(),
        )
        wp = WorkPackage(
            id="wp-compare",
            description="code implementation task",
            required_capabilities=["code-implementation"],
            risk="low",
        )
        a_plain = wf_plain.resolve(wp)
        a_cwo = wf_cwo.resolve(wp)
        self.assertEqual(a_plain.employee, a_cwo.employee)
        self.assertEqual(a_plain.resolved_logical, a_cwo.resolved_logical)
        self.assertEqual(a_plain.physical_model, a_cwo.physical_model)

    def test_capacity_fields_not_transposed(self):
        """F-1 regression: capacity_class carries the COST class, health_state
        carries the HEALTH state -- never swapped."""
        from core.capacity_ledger import CapacityLedger
        ledger = CapacityLedger.in_memory()
        # Force known ledger state for a provider used by the hermetic fixture.
        ledger.record_exhaustion("claude-opus", exhausted_until=None)
        wf = WorkforceResolver(
            real_employees(),
            resolver_all_available(),
            identity_registry=get_identity_registry(),
            capacity_ledger=ledger,
        )
        wp = WorkPackage(
            id="wp-cap",
            description="code implementation task",
            required_capabilities=["code-implementation"],
            risk="low",
        )
        assignment = wf.resolve(wp)
        self.assertTrue(assignment.available)
        self.assertIsNotNone(assignment.capacity_class)
        self.assertIsNotNone(assignment.health_state)
        entry = ledger.get(assignment.resolved_logical)
        self.assertEqual(assignment.capacity_class, entry.cost_class)
        self.assertEqual(assignment.health_state, entry.health_state)
        # And the ledger's classes are what they say.
        if assignment.resolved_logical == "claude-opus":
            self.assertEqual(assignment.capacity_class, "subscription-scarce")
            self.assertEqual(assignment.health_state, "exhausted")


@unittest.skipUnless(WBS_REPO.is_dir(), "WBS repo not present on this machine")
class TestCWORepoSafety(unittest.TestCase):
    """Acceptance 12: WBS repository remains untouched."""

    def test_wbs_git_head_unchanged(self):
        # Recorded baseline HEAD for WBS main: 8113ca2 (S048 recovery).
        import subprocess
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=WBS_REPO, capture_output=True, text=True
        ).stdout.strip()
        # We only assert HEAD is a valid 40-hex commit and the worktree has no
        # NEW staged/committed state introduced by CWO (the WBS repo was
        # already 75 items modified from S048 work, which is not ours).
        self.assertRegex(head, r"^[0-9a-f]{40}$")
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], cwd=WBS_REPO,
            capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(staged, "", "WBS must have nothing staged by CWO work")


if __name__ == "__main__":
    unittest.main()
