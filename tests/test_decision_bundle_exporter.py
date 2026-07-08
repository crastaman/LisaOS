"""Tests for core.decision_bundle_exporter (Lisa Console v1, Phase C1).

Hermetic: every test builds its own tmp evidence files under
tempfile.mkdtemp() and never reads or writes the real ~/Lisa/reports tree.
See docs/LISAOS/CONSOLE/01_DECISION_BUNDLE_SPEC.md and
docs/LISAOS/CONSOLE/07_TEST_PLAN.md.

Run: PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_decision_bundle_exporter -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.decision_bundle_exporter import (
    DecisionBundleError,
    ProposedAction,
    SCHEMA,
    build_bundle,
    export_bundle,
    write_bundle,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


class DecisionBundleExporterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lisaos-console-test-"))
        self.evidence_path = self.tmp / "workforce_evidence.jsonl"
        self.violations_path = self.tmp / "governance_violations.jsonl"
        self.ack_path = self.tmp / "governance_acknowledgements.jsonl"
        self.bundles_dir = self.tmp / "bundles"
        self.audit_path = self.tmp / "audit.jsonl"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestBuildBundleMatching(DecisionBundleExporterTestCase):
    def test_matches_only_records_with_same_work_package_id(self) -> None:
        _write_jsonl(self.evidence_path, [
            {"work_package_id": "impl-foo", "employee": "software-engineer", "department": "engineering"},
            {"work_package_id": "impl-bar", "employee": "someone-else", "department": "engineering"},
        ])
        bundle = build_bundle(
            "impl-foo",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        self.assertEqual(len(bundle["evidence"]["workforce_evidence"]), 1)
        self.assertEqual(bundle["evidence"]["workforce_evidence"][0]["employee"], "software-engineer")
        self.assertEqual(bundle["job_id"], "impl-foo")
        self.assertEqual(bundle["job_id_source"], "work_package_id")
        self.assertEqual(bundle["schema"], SCHEMA)

    def test_unmatched_job_id_produces_valid_bundle_with_gap_noted(self) -> None:
        _write_jsonl(self.evidence_path, [
            {"work_package_id": "something-else", "employee": "x"},
        ])
        bundle = build_bundle(
            "no-such-job",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        self.assertEqual(bundle["evidence"]["workforce_evidence"], [])
        self.assertTrue(any("no-such-job" in g for g in bundle["gaps"]))

    def test_participating_workers_deduplicated(self) -> None:
        _write_jsonl(self.evidence_path, [
            {"work_package_id": "j1", "employee": "a", "department": "eng"},
            {"work_package_id": "j1", "employee": "a", "department": "eng"},
            {"work_package_id": "j1", "employee": "b", "department": "eng"},
        ])
        bundle = build_bundle(
            "j1",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        self.assertEqual(len(bundle["participating_workers"]), 2)


class TestBuildBundleValidation(DecisionBundleExporterTestCase):
    def test_empty_job_id_rejected(self) -> None:
        with self.assertRaises(DecisionBundleError):
            build_bundle(
                "",
                evidence_path=self.evidence_path,
                violations_path=self.violations_path,
                ack_path=self.ack_path,
            )

    def test_invalid_status_at_export_rejected(self) -> None:
        with self.assertRaises(DecisionBundleError):
            build_bundle(
                "j1",
                status_at_export="not-a-real-status",
                evidence_path=self.evidence_path,
                violations_path=self.violations_path,
                ack_path=self.ack_path,
            )

    def test_missing_status_at_export_noted_as_gap(self) -> None:
        bundle = build_bundle(
            "j1",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        self.assertIsNone(bundle["status_at_export"])
        self.assertTrue(any("status_at_export" in g for g in bundle["gaps"]))

    def test_proposed_actions_serialized(self) -> None:
        bundle = build_bundle(
            "j1",
            proposed_actions=[ProposedAction("a1", "do the thing", risk_tier="low", reversible=True)],
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        self.assertEqual(bundle["proposed_actions"], [
            {"action_id": "a1", "description": "do the thing", "risk_tier": "low", "reversible": True}
        ])

    def test_reserved_fields_are_null_or_empty(self) -> None:
        bundle = build_bundle(
            "j1",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        self.assertIsNone(bundle["advisory"]["recommendation"])
        self.assertIsNone(bundle["advisory"]["confidence"])
        self.assertIsNone(bundle["risk_assessment"]["overall_risk"])
        self.assertIsNone(bundle["decision"])


class TestGovernanceStatus(DecisionBundleExporterTestCase):
    def test_no_violations_files_means_zero_unacknowledged(self) -> None:
        bundle = build_bundle(
            "j1",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        self.assertEqual(bundle["governance_status"]["unacknowledged_violation_count"], 0)

    def test_unacknowledged_violation_counted(self) -> None:
        _write_jsonl(self.violations_path, [
            {
                "violation_id": "v1",
                "subagent_name": "impl-something",
                "session_id": "s1",
                "transcript_path": "/tmp/x",
                "reason": "no governed evidence",
                "detected_at": "2026-07-08T00:00:00+00:00",
            }
        ])
        bundle = build_bundle(
            "j1",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        self.assertEqual(bundle["governance_status"]["unacknowledged_violation_count"], 1)
        self.assertIn("v1", bundle["governance_status"]["unacknowledged_violation_ids"])

    def test_acknowledged_violation_not_counted(self) -> None:
        _write_jsonl(self.violations_path, [
            {
                "violation_id": "v1",
                "subagent_name": "impl-something",
                "session_id": "s1",
                "transcript_path": "/tmp/x",
                "reason": "no governed evidence",
                "detected_at": "2026-07-08T00:00:00+00:00",
            }
        ])
        _write_jsonl(self.ack_path, [
            {"violation_ids": ["v1"], "operator": "roshan", "reason": "reviewed",
             "acknowledged_at": "2026-07-08T00:01:00+00:00"},
        ])
        bundle = build_bundle(
            "j1",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        self.assertEqual(bundle["governance_status"]["unacknowledged_violation_count"], 0)


class TestWriteBundle(DecisionBundleExporterTestCase):
    def test_writes_bundle_json_and_raw_copy(self) -> None:
        _write_jsonl(self.evidence_path, [
            {"work_package_id": "j1", "employee": "a", "department": "eng"},
        ])
        bundle = build_bundle(
            "j1",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        path = write_bundle(bundle, bundles_dir=self.bundles_dir, audit_path=self.audit_path)
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "bundle.json")
        raw_path = path.parent / "raw" / "workforce_evidence.jsonl"
        self.assertTrue(raw_path.is_file())
        self.assertEqual(len(raw_path.read_text().strip().splitlines()), 1)
        # No leftover .tmp file after atomic replace.
        self.assertFalse((path.parent / "bundle.json.tmp").exists())

    def test_write_bundle_appends_audit_entry(self) -> None:
        bundle = build_bundle(
            "j1",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        write_bundle(bundle, bundles_dir=self.bundles_dir, audit_path=self.audit_path)
        lines = self.audit_path.read_text().strip().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["event"], "bundle_created")
        self.assertEqual(record["bundle_id"], bundle["bundle_id"])
        self.assertEqual(record["job_id"], "j1")

    def test_written_bundle_round_trips_as_json(self) -> None:
        bundle = build_bundle(
            "j1",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        path = write_bundle(bundle, bundles_dir=self.bundles_dir, audit_path=self.audit_path)
        reloaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(reloaded["bundle_id"], bundle["bundle_id"])
        self.assertEqual(reloaded["schema"], SCHEMA)

    def test_refuses_to_overwrite_existing_bundle_id(self) -> None:
        bundle = build_bundle(
            "j1",
            bundle_id="db-fixed-id",
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        write_bundle(bundle, bundles_dir=self.bundles_dir, audit_path=self.audit_path)
        with self.assertRaises(DecisionBundleError):
            write_bundle(bundle, bundles_dir=self.bundles_dir, audit_path=self.audit_path)

    def test_export_bundle_end_to_end(self) -> None:
        _write_jsonl(self.evidence_path, [
            {"work_package_id": "j1", "employee": "a", "department": "eng"},
        ])
        path = export_bundle(
            "j1",
            bundles_dir=self.bundles_dir,
            audit_path=self.audit_path,
            evidence_path=self.evidence_path,
            violations_path=self.violations_path,
            ack_path=self.ack_path,
        )
        self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
