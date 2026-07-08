"""Proof-of-work tests for the LisaOS Governance Guard (post-closure hardening
patch — dispatcher-bypass detection).

Validates docs/LISAOS/V3/33_WORKFORCE_GOVERNANCE_HARDENING.md against
core/governance_guard.py. Fully hermetic: every scan/record/acknowledge
operation runs against a tmp directory tree, never the real
~/.claude/projects or ~/Lisa/reports.

Run with:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_governance_guard -v
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.governance_guard import (
    GovernanceGuardError,
    detect_bypass_violations,
    find_subagent_invocations,
    record_acknowledgement,
    record_violations,
    require_clean,
    unacknowledged,
    violation_id,
)


def _make_subagent(project_dir: Path, session_id: str, name: str) -> Path:
    subagents_dir = project_dir / session_id / "subagents"
    subagents_dir.mkdir(parents=True, exist_ok=True)
    f = subagents_dir / f"{name}.jsonl"
    f.write_text('{"type": "subagent_transcript"}\n')
    return f


def _write_evidence(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


class GovernanceGuardTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project_dir = self.tmp / "claude-project"
        self.evidence_path = self.tmp / "reports" / "workforce_evidence.jsonl"
        self.violations_path = self.tmp / "reports" / "governance_violations.jsonl"
        self.ack_path = self.tmp / "reports" / "governance_acknowledgements.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Scanning
# --------------------------------------------------------------------------- #

class TestFindSubagentInvocations(GovernanceGuardTestCase):
    def test_finds_subagent_transcripts_under_project_dirs(self):
        _make_subagent(self.project_dir, "session-1", "impl-safety-constitution")
        _make_subagent(self.project_dir, "session-1", "impl-fingerprint-engine")
        invocations = find_subagent_invocations([self.project_dir])
        names = {i.name for i in invocations}
        self.assertEqual(names, {"impl-safety-constitution", "impl-fingerprint-engine"})

    def test_missing_project_dir_yields_no_invocations(self):
        self.assertEqual(find_subagent_invocations([self.tmp / "nonexistent"]), [])

    def test_project_dir_with_no_subagents_dir_yields_no_invocations(self):
        (self.project_dir / "session-1").mkdir(parents=True)
        self.assertEqual(find_subagent_invocations([self.project_dir]), [])


# --------------------------------------------------------------------------- #
# Detection: production-shaped name + no governed evidence => violation
# --------------------------------------------------------------------------- #

class TestDetectBypassViolations(GovernanceGuardTestCase):
    def test_production_shaped_subagent_with_no_evidence_is_a_violation(self):
        _make_subagent(self.project_dir, "session-1", "impl-backup-manager")
        invocations = find_subagent_invocations([self.project_dir])
        violations = detect_bypass_violations(invocations, evidence_path=self.evidence_path)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].subagent_name, "impl-backup-manager")

    def test_production_shaped_subagent_matching_governed_evidence_is_not_a_violation(self):
        _make_subagent(self.project_dir, "session-1", "impl-backup-manager")
        _write_evidence(self.evidence_path, [
            {"work_package_id": "impl-backup-manager", "employee": "software-engineer"},
        ])
        invocations = find_subagent_invocations([self.project_dir])
        violations = detect_bypass_violations(invocations, evidence_path=self.evidence_path)
        self.assertEqual(violations, [])

    def test_non_production_shaped_name_is_never_a_violation(self):
        # e.g. a research/Explore subagent -- out of scope by design, it never
        # needed WorkforceResolver staffing in the first place.
        _make_subagent(self.project_dir, "session-1", "explore-repo-structure")
        invocations = find_subagent_invocations([self.project_dir])
        violations = detect_bypass_violations(invocations, evidence_path=self.evidence_path)
        self.assertEqual(violations, [])

    def test_governed_evidence_matched_by_employee_id_also_clears_violation(self):
        _make_subagent(self.project_dir, "session-1", "fix-upgrade-executor")
        _write_evidence(self.evidence_path, [
            {"work_package_id": "wp-9", "employee": "fix-upgrade-executor"},
        ])
        invocations = find_subagent_invocations([self.project_dir])
        violations = detect_bypass_violations(invocations, evidence_path=self.evidence_path)
        self.assertEqual(violations, [])


# --------------------------------------------------------------------------- #
# Acknowledgement + fail-closed require_clean()
# --------------------------------------------------------------------------- #

class TestAcknowledgementAndRequireClean(GovernanceGuardTestCase):
    def test_require_clean_passes_when_no_violations(self):
        violations = require_clean(
            [self.project_dir], evidence_path=self.evidence_path,
            ack_path=self.ack_path, violations_path=self.violations_path,
        )
        self.assertEqual(violations, [])

    def test_require_clean_raises_on_unacknowledged_violation(self):
        _make_subagent(self.project_dir, "session-1", "impl-upgrade-executor")
        with self.assertRaises(GovernanceGuardError) as ctx:
            require_clean(
                [self.project_dir], evidence_path=self.evidence_path,
                ack_path=self.ack_path, violations_path=self.violations_path,
            )
        self.assertIn("impl-upgrade-executor", str(ctx.exception))

    def test_require_clean_records_violations_to_disk(self):
        _make_subagent(self.project_dir, "session-1", "impl-upgrade-executor")
        with self.assertRaises(GovernanceGuardError):
            require_clean(
                [self.project_dir], evidence_path=self.evidence_path,
                ack_path=self.ack_path, violations_path=self.violations_path,
            )
        self.assertTrue(self.violations_path.is_file())
        recorded = json.loads(self.violations_path.read_text().splitlines()[0])
        self.assertEqual(recorded["subagent_name"], "impl-upgrade-executor")

    def test_require_clean_passes_once_acknowledged(self):
        f = _make_subagent(self.project_dir, "session-1", "impl-upgrade-executor")
        vid = violation_id("impl-upgrade-executor", str(f))
        record_acknowledgement(
            [vid], operator="roshan", reason="Qwen unavailable; reviewed",
            path=self.ack_path,
        )
        violations = require_clean(
            [self.project_dir], evidence_path=self.evidence_path,
            ack_path=self.ack_path, violations_path=self.violations_path,
        )
        self.assertEqual(len(violations), 1)  # still detected...
        self.assertEqual(unacknowledged(violations, ack_path=self.ack_path), [])  # ...but cleared

    def test_acknowledgement_requires_a_named_operator(self):
        with self.assertRaises(ValueError):
            record_acknowledgement(["abc123"], operator="", reason="x", path=self.ack_path)

    def test_record_violations_appends_without_truncating(self):
        _make_subagent(self.project_dir, "session-1", "impl-a")
        _make_subagent(self.project_dir, "session-1", "impl-b")
        invocations = find_subagent_invocations([self.project_dir])
        violations = detect_bypass_violations(invocations, evidence_path=self.evidence_path)
        record_violations(violations[:1], path=self.violations_path)
        record_violations(violations[1:], path=self.violations_path)
        lines = self.violations_path.read_text().splitlines()
        self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
