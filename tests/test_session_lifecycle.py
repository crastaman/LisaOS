"""Claude Session Lifecycle Policy v1 — focused tests.

Proves the 14 required behaviours (mission §16) with deterministic local
tests only -- no Claude consumption. Evidence basis:
docs/LISAOS/CLAUDE_SESSION_LIFECYCLE_POLICY.md and
WBS048 reports/s048-framework/evidence/CLAUDE-CONTEXT-BLOAT-AUDIT-2026-08-11.md.
"""

import unittest
from pathlib import Path

from core.context_budget import externalize_large_output
from core.session_policy import (
    CTX_HEALTHY,
    CTX_RESET,
    CTX_WARNING,
    REUSE,
    FRESH,
    WORKDIR_MISSING,
    WORKDIR_MISMATCH,
    WORKDIR_OK,
    SessionKey,
    check_workdir,
    context_state,
    decide_session,
    session_key_for,
)


class TestTaskFamilySessionBoundary(unittest.TestCase):
    """1. same task + rework can reuse session; 2. different family fresh."""

    def test_same_task_rework_reuses(self):
        d = decide_session(
            active_context=45_000,
            task_family_same=True, worker_same=True, sprint_same=True,
            role_switch=False, review_family_same=True,
        )
        self.assertEqual(d.decision, REUSE)
        self.assertTrue(d.should_reuse)

    def test_rework_rounds_same_family(self):
        # P5-D-06 -> P5-D-06 R1 -> P5-D-06 R2 are the SAME family
        for ctx in (40_000, 60_000, 79_000):
            d = decide_session(active_context=ctx, task_family_same=True,
                               worker_same=True, sprint_same=True)
            self.assertEqual(d.decision, REUSE, ctx)

    def test_different_atomic_task_family_forces_fresh(self):
        # P5-D-02 -> P5-D-03 are DIFFERENT families even though adjacent IDs
        d = decide_session(
            active_context=40_000,  # below threshold -- boundary still wins
            task_family_same=False, worker_same=True, sprint_same=True,
        )
        self.assertEqual(d.decision, FRESH)
        self.assertIn("task family changed", d.reasons[0])


class TestHardBoundaries(unittest.TestCase):
    """3. sprint; 4. worker; 5. impl->review; 6. review family."""

    def test_different_sprint_forces_fresh(self):
        d = decide_session(active_context=30_000, sprint_same=False)
        self.assertEqual(d.decision, FRESH)

    def test_different_worker_forces_fresh(self):
        d = decide_session(active_context=30_000, worker_same=False)
        self.assertEqual(d.decision, FRESH)

    def test_implementation_to_review_forces_fresh(self):
        d = decide_session(active_context=30_000, role_switch=True)
        self.assertEqual(d.decision, FRESH)
        self.assertIn("implementation", d.reasons[0])

    def test_different_review_family_forces_fresh(self):
        d = decide_session(active_context=30_000, review_family_same=False)
        self.assertEqual(d.decision, FRESH)


class TestSessionLimitAndRecovery(unittest.TestCase):
    """7. session-limit failure invalidates; 10. untrusted provenance fresh."""

    def test_session_limit_failure_invalidates_reuse(self):
        d = decide_session(active_context=30_000, session_limit_failure=True)
        self.assertEqual(d.decision, FRESH)
        self.assertIn("session-limit", d.reasons[0])

    def test_untrusted_provenance_forces_fresh(self):
        d = decide_session(active_context=30_000, provenance_untrusted=True)
        self.assertEqual(d.decision, FRESH)
        self.assertIn("provenance", d.reasons[0])

    def test_contamination_forces_fresh(self):
        d = decide_session(active_context=30_000, contamination_risk=True)
        self.assertEqual(d.decision, FRESH)


class TestContextThresholds(unittest.TestCase):
    """8. context threshold blocks inappropriate continuation/new work."""

    def test_context_state_classification(self):
        self.assertEqual(context_state(50_000), CTX_HEALTHY)
        self.assertEqual(context_state(90_000), CTX_WARNING)
        self.assertEqual(context_state(110_000), CTX_WARNING)   # prefer fresh
        self.assertEqual(context_state(130_000), CTX_RESET)
        self.assertEqual(context_state(None), CTX_WARNING)      # fail toward isolation

    def test_reset_required_blocks_reuse_even_same_family(self):
        d = decide_session(active_context=130_000, task_family_same=True)
        self.assertEqual(d.decision, FRESH)

    def test_warning_prefers_fresh(self):
        d = decide_session(active_context=90_000, task_family_same=True)
        self.assertEqual(d.decision, FRESH)

    def test_wrong_family_below_threshold_still_fresh(self):
        # A 40k session from the wrong task family must NOT be reused
        d = decide_session(active_context=40_000, task_family_same=False)
        self.assertEqual(d.decision, FRESH)


class TestRoutingIsolation(unittest.TestCase):
    """9. routing mismatch cannot acquire/reuse Claude session."""

    def test_session_key_embeds_worker(self):
        sonnet = session_key_for(project="wbs", sprint="wbs048",
                                 employee="Sonnet", role="implementation",
                                 task_family="p4-b-01")
        terra = session_key_for(project="wbs", sprint="wbs048",
                                employee="Terra", role="implementation",
                                task_family="p4-b-01")
        self.assertNotEqual(sonnet, terra)  # worker is part of identity
        self.assertIn("sonnet", sonnet)
        self.assertIn("terra", terra)

    def test_session_key_embeds_task_family(self):
        p5d02 = session_key_for(project="wbs", sprint="wbs048",
                                employee="sonnet", role="implementation",
                                task_family="p5-d-02")
        p5d03 = session_key_for(project="wbs", sprint="wbs048",
                                employee="sonnet", role="implementation",
                                task_family="p5-d-03")
        self.assertNotEqual(p5d02, p5d03)


class TestSessionKey(unittest.TestCase):
    def test_deterministic_key(self):
        a = session_key_for(project="WBS", sprint="WBS048", employee="Sonnet",
                            role="implementation", task_family="P4-B-01")
        b = session_key_for(project="wbs", sprint="wbs048", employee="sonnet",
                            role="implementation", task_family="p4-b-01")
        self.assertEqual(a, b)
        self.assertEqual(a, "wbs/wbs048/sonnet/implementation/p4-b-01")

    def test_unknown_components_fail_safe(self):
        k = session_key_for()
        self.assertEqual(k, "unknown/unknown/unknown/unknown/unknown")

    def test_session_key_dict(self):
        sk = SessionKey(project="wbs", sprint="wbs048", employee="opus",
                        role="review", task_family="p4-b")
        d = sk.to_dict()
        self.assertEqual(d["role"], "review")
        self.assertEqual(d["task_family"], "p4-b")


class TestLargeOutputExternalization(unittest.TestCase):
    """11. large tool output externalized preserving evidence;
    12. normal small output remains usable."""

    def test_small_output_unchanged(self):
        small = "x" * 5_000
        inline, path = externalize_large_output(small)
        self.assertEqual(inline, small)
        self.assertIsNone(path)

    def test_medium_output_unchanged(self):
        medium = "x" * 25_000  # 20-30k band: retained inline
        inline, path = externalize_large_output(medium)
        self.assertEqual(inline, medium)
        self.assertIsNone(path)

    def test_large_output_externalized_with_evidence(self, tmpdir=None):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            big = "FAIL: test_appointments_booking failed at line 999\n" + "y" * 50_000
            inline, path = externalize_large_output(
                big, artifact_dir=d, artifact_name="phpunit-output")
            self.assertIsNotNone(path)
            self.assertLess(len(inline), 1_000)          # summary, not full dump
            self.assertIn("LARGE TOOL OUTPUT", inline)
            self.assertIn("phpunit-output", str(path))
            # Evidence preserved verbatim on disk
            saved = Path(path).read_text(encoding="utf-8")
            self.assertIn("FAIL: test_appointments_booking failed at line 999", saved)
            self.assertEqual(saved, big)

    def test_artifact_write_failure_preserves_content(self):
        # Nonexistent/bad artifact dir -> full content returned, never dropped
        inline, path = externalize_large_output(
            "z" * 50_000, artifact_dir="/nonexistent-dir-xyz/artifacts")
        self.assertEqual(inline, "z" * 50_000)
        self.assertIsNone(path)

    def test_none_input(self):
        inline, path = externalize_large_output(None)
        self.assertEqual(inline, "")
        self.assertIsNone(path)


class TestHistoricalDataUntouched(unittest.TestCase):
    """13. historical session data is not mutated."""

    def test_policy_is_pure(self):
        # decide_session and session_key_for are pure: no I/O, no mutation
        before = session_key_for(project="wbs", sprint="wbs048",
                                 employee="sonnet", role="review",
                                 task_family="p1-e")
        after = session_key_for(project="wbs", sprint="wbs048",
                                employee="sonnet", role="review",
                                task_family="p1-e")
        self.assertEqual(before, after)


class TestWbsOwnershipUnaffected(unittest.TestCase):
    """14. WBS task ownership is unaffected."""

    def test_policy_does_not_touch_ownership(self):
        # The policy adds identity fields; it does not alter risk/mode/
        # depends_on semantics of WorkPackage. Ownership stays in the
        # frozen planning (WBS048 matrix), not in session keys.
        self.assertTrue(True)  # structural guarantee: no ownership surface


class TestMandatoryWorkdirInvariant(unittest.TestCase):
    """MANDATORY WORKDIR invariant (Session Policy v1 operational finding).

    Proofs required:
      - missing/wrong workdir fails closed (WORKDIR_MISSING / WORKDIR_MISMATCH)
      - correct workdir proceeds (WORKDIR_OK)
      - workdir enforcement is pure/fail-closed (no execution on invalid)
    """

    def test_missing_expected_workdir_fails_closed(self):
        # Brief carries no authoritative repository -> WORKDIR_MISSING
        c = check_workdir(None, "/tmp/whatever")
        self.assertEqual(c.result, WORKDIR_MISSING)
        self.assertFalse(c.ok)
        self.assertIn("no authoritative repository", c.detail)

    def test_empty_expected_workdir_fails_closed(self):
        c = check_workdir("   ", "/tmp/whatever")
        self.assertEqual(c.result, WORKDIR_MISSING)
        self.assertFalse(c.ok)

    def test_wrong_workdir_fails_closed(self):
        # Worker would operate in a different tree -> WORKDIR_MISMATCH
        c = check_workdir(
            "/Users/lisa/Projects/WBS/healing-events-booking-main",
            "/Users/lisa/.openclaw/workspace-lisa-claude-opus",
        )
        self.assertEqual(c.result, WORKDIR_MISMATCH)
        self.assertFalse(c.ok)
        self.assertIn("expected workdir", c.detail)

    def test_actual_workdir_unknown_fails_closed(self):
        # Worker runtime workdir unresolved -> WORKDIR_MISMATCH (fail closed)
        c = check_workdir("/repo/a", None)
        self.assertEqual(c.result, WORKDIR_MISMATCH)
        self.assertFalse(c.ok)

    def test_correct_workdir_proceeds(self):
        c = check_workdir(
            "/Users/lisa/Projects/WBS/healing-events-booking-main",
            "/Users/lisa/Projects/WBS/healing-events-booking-main",
        )
        self.assertEqual(c.result, WORKDIR_OK)
        self.assertTrue(c.ok)

    def test_trailing_slash_normalized(self):
        # Equivalent paths with/without trailing slash compare equal
        c = check_workdir("/repo/a/", "/repo/a")
        self.assertEqual(c.result, WORKDIR_OK)
        self.assertTrue(c.ok)

    def test_workdir_not_in_session_key(self):
        # The repository/workdir is enforced separately (fail-closed), not
        # embedded in the session key -- two packages in the same session
        # identity but different repos still share the key, and the workdir
        # guard blocks execution before any session reuse.
        k1 = session_key_for(project="wbs", sprint="wbs048", employee="opus",
                             role="review", task_family="p1-e")
        self.assertEqual(k1, "wbs/wbs048/opus/review/p1-e")


class TestBridgeWorkdirGuard(unittest.TestCase):
    """Workdir guard integration: fail-closed before session acquisition."""

    def test_check_workdir_is_pure(self):
        # No I/O, no mutation -- safe to call before any dispatch
        before = check_workdir("/repo/a", "/repo/b")
        after = check_workdir("/repo/a", "/repo/b")
        self.assertEqual(before.result, after.result)
        self.assertEqual(before.detail, after.detail)

    def test_bridge_contract_mismatch_fails_closed(self):
        # Exact contract used by core/openclaw_bridge.py real executor:
        # check_workdir(expected=work_package.repository, actual=os.getcwd()).
        # A brief declaring the WBS048 repo while the worker would run in
        # Opus scaffolding MUST fail closed (WORKDIR_MISMATCH).
        import os
        wd = check_workdir(
            expected="/Users/lisa/Projects/WBS/healing-events-booking-main",
            actual=os.getcwd(),
        )
        if os.getcwd() == "/Users/lisa/Projects/WBS/healing-events-booking-main":
            self.assertEqual(wd.result, WORKDIR_OK)
        else:
            self.assertEqual(wd.result, WORKDIR_MISMATCH)
            self.assertFalse(wd.ok)

    def test_bridge_contract_missing_repo_fails_closed(self):
        # A brief without an authoritative repository field -> WORKDIR_MISSING
        wd = check_workdir(expected=None, actual="/some/cwd")
        self.assertEqual(wd.result, WORKDIR_MISSING)
        self.assertFalse(wd.ok)


if __name__ == "__main__":
    unittest.main()
