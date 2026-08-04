"""Tests for core/task_classifier.py — hermetic, stdlib unittest, no I/O."""

import unittest

from core.task_classifier import classify, Classification


class TestB1EmptyMission(unittest.TestCase):
    def test_empty_string_blocked(self):
        c = classify("")
        self.assertEqual(c.classification, "BLOCKED")
        self.assertIn("B1_EMPTY_MISSION", c.matched_rules)

    def test_whitespace_only_blocked(self):
        c = classify("   \t\n  ")
        self.assertEqual(c.classification, "BLOCKED")
        self.assertIn("B1_EMPTY_MISSION", c.matched_rules)

    def test_nonempty_not_blocked(self):
        c = classify("hello")
        self.assertNotEqual(c.classification, "BLOCKED")


class TestG5SprintReference(unittest.TestCase):
    def test_S0xx_code(self):
        c = classify("S046 — perform a production-readiness audit of the Appointments module.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G5_SPRINT_REFERENCE", c.matched_rules)
        # also G3 should match (production-readiness audit)
        self.assertIn("G3_WORK_TYPE", c.matched_rules)

    def test_wp_dash(self):
        c = classify("WP-12 implement the new feature")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G5_SPRINT_REFERENCE", c.matched_rules)

    def test_sprint_word(self):
        c = classify("This sprint we should review dependencies.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G5_SPRINT_REFERENCE", c.matched_rules)

    def test_lisa_i(self):
        c = classify("LISA-I003 entrypoint work")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G5_SPRINT_REFERENCE", c.matched_rules)

    def test_no_sprint_reference(self):
        c = classify("Explain what the Lisa dispatcher does.")
        self.assertNotIn("G5_SPRINT_REFERENCE", c.matched_rules)


class TestG1RepoWrite(unittest.TestCase):
    def test_implement(self):
        c = classify("implement the new login flow")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G1_REPO_WRITE", c.matched_rules)

    def test_fix(self):
        c = classify("Check the booking code and fix anything necessary.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G1_REPO_WRITE", c.matched_rules)

    def test_delete(self):
        c = classify("Delete the old migration file.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G1_REPO_WRITE", c.matched_rules)

    def test_no_g1_explanatory(self):
        c = classify("Explain what the Lisa dispatcher does.")
        self.assertNotIn("G1_REPO_WRITE", c.matched_rules)


class TestG2ExecutionMutation(unittest.TestCase):
    def test_run_tests(self):
        c = classify("run tests for the booking module")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G2_EXECUTION_MUTATION", c.matched_rules)

    def test_build(self):
        c = classify("build the release artefact")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G2_EXECUTION_MUTATION", c.matched_rules)

    def test_migration(self):
        c = classify("execute the database migration")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G2_EXECUTION_MUTATION", c.matched_rules)

    def test_no_g2(self):
        c = classify("Explain what the Lisa dispatcher does.")
        self.assertNotIn("G2_EXECUTION_MUTATION", c.matched_rules)


class TestG3WorkType(unittest.TestCase):
    def test_audit(self):
        c = classify("Audit the authentication layer.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G3_WORK_TYPE", c.matched_rules)

    def test_production_readiness(self):
        c = classify("Perform a production readiness check.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G3_WORK_TYPE", c.matched_rules)

    def test_independent_review(self):
        c = classify("Conduct an independent review of the PR.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G3_WORK_TYPE", c.matched_rules)

    def test_release(self):
        c = classify("Prepare the v2.0 release.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G3_WORK_TYPE", c.matched_rules)

    def test_no_g3_explanatory(self):
        c = classify("Explain what the Lisa dispatcher does.")
        self.assertNotIn("G3_WORK_TYPE", c.matched_rules)


class TestG4MultiDomain(unittest.TestCase):
    def test_three_domains(self):
        # lifecycle, permissions, notifications, payments, tests, independent review, report
        c = classify(
            "Audit appointment lifecycle, permissions, notifications, payments and tests, "
            "then produce an independent readiness report."
        )
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G3_WORK_TYPE", c.matched_rules)
        self.assertIn("G4_MULTI_DOMAIN", c.matched_rules)

    def test_exactly_two_domains_no_g4(self):
        # only "payment" and "test"
        c = classify("Check payment and test coverage.")
        self.assertNotIn("G4_MULTI_DOMAIN", c.matched_rules)

    def test_five_domains(self):
        c = classify("Review api capacity payment migration schema booking.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G4_MULTI_DOMAIN", c.matched_rules)


class TestD1Explanatory(unittest.TestCase):
    def test_explain(self):
        c = classify("Explain what the Lisa dispatcher does.")
        self.assertEqual(c.classification, "DIRECT")
        self.assertIn("D1_EXPLANATORY", c.matched_rules)

    def test_what_prefix(self):
        c = classify("What does the workforce resolver return?")
        self.assertEqual(c.classification, "DIRECT")
        self.assertIn("D1_EXPLANATORY", c.matched_rules)

    def test_how(self):
        c = classify("How does the capacity ledger work?")
        self.assertEqual(c.classification, "DIRECT")
        self.assertIn("D1_EXPLANATORY", c.matched_rules)

    def test_list(self):
        c = classify("List all the available capabilities.")
        self.assertEqual(c.classification, "DIRECT")
        self.assertIn("D1_EXPLANATORY", c.matched_rules)

    def test_d1_overridden_by_g1(self):
        # "explain" present but also "fix" — must be GOVERNED
        c = classify("Explain and then fix the broken endpoint.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertNotIn("D1_EXPLANATORY", c.matched_rules)


class TestDefaultGoverned(unittest.TestCase):
    def test_gibberish(self):
        c = classify("xyzzy plugh zork quux corge")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("DEFAULT_GOVERNED_AMBIGUOUS", c.matched_rules)

    def test_ambiguous_short(self):
        c = classify("the thing")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("DEFAULT_GOVERNED_AMBIGUOUS", c.matched_rules)


class TestAcceptanceCases(unittest.TestCase):
    """Verbatim acceptance inputs from the implementation brief."""

    def test_s046_production_readiness(self):
        c = classify("S046 — perform a production-readiness audit of the Appointments module.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G5_SPRINT_REFERENCE", c.matched_rules)
        self.assertIn("G3_WORK_TYPE", c.matched_rules)

    def test_multi_domain_audit(self):
        c = classify(
            "Audit appointment lifecycle, permissions, notifications, payments and tests, "
            "then produce an independent readiness report."
        )
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G3_WORK_TYPE", c.matched_rules)
        self.assertIn("G4_MULTI_DOMAIN", c.matched_rules)

    def test_explain_dispatcher(self):
        c = classify("Explain what the Lisa dispatcher does.")
        self.assertEqual(c.classification, "DIRECT")
        self.assertIn("D1_EXPLANATORY", c.matched_rules)

    def test_fix_booking(self):
        c = classify("Check the booking code and fix anything necessary.")
        self.assertEqual(c.classification, "GOVERNED")
        self.assertIn("G1_REPO_WRITE", c.matched_rules)


class TestMiscBehaviours(unittest.TestCase):
    def test_to_dict(self):
        c = Classification(classification="DIRECT", matched_rules=["D1_EXPLANATORY"], reason="x")
        d = c.to_dict()
        self.assertEqual(d["classification"], "DIRECT")
        self.assertIn("D1_EXPLANATORY", d["matched_rules"])

    def test_g_wins_over_d(self):
        # D1 word + G1 word → GOVERNED
        c = classify("explain and implement the new flow")
        self.assertEqual(c.classification, "GOVERNED")

    def test_internal_error_default(self):
        # Simulate by passing a non-str; classifier should not raise
        try:
            c = classify(None)  # type: ignore[arg-type]
            self.assertEqual(c.classification, "GOVERNED")
            self.assertIn("INTERNAL_ERROR_DEFAULT_GOVERNED", c.matched_rules)
        except Exception:
            self.fail("classify() raised on None input")


if __name__ == "__main__":
    unittest.main()
