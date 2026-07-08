"""Tests for console.data (Lisa Console v1, Phase C4).

Hermetic: every test builds its own tmp bundles/briefs/registry/evidence
files. Read-only module -- these tests never assert anything about
writes, since data.py performs none.

Run: PYTHONPATH="$HOME/Lisa" .venv/bin/python3 -m unittest tests.test_console_data -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from console import data


def _write_bundle(bundles_dir: Path, bundle_id: str, **overrides) -> None:
    bundle_dir = bundles_dir / bundle_id
    bundle_dir.mkdir(parents=True)
    bundle = {
        "bundle_id": bundle_id, "schema": "lisaos.console.decision_bundle.v1",
        "job_id": f"job-{bundle_id}", "created_at": "2026-07-08T10:00:00+00:00",
        "decision": None, "audit_references": {"source_files": [], "raw_copy": "raw/x"},
    }
    bundle.update(overrides)
    (bundle_dir / "bundle.json").write_text(json.dumps(bundle))


def _write_brief(briefs_dir: Path, brief_id: str, **overrides) -> None:
    briefs_dir.mkdir(parents=True, exist_ok=True)
    brief = {
        "brief_id": brief_id, "schema": "lisaos.console.executive_brief.v1",
        "bundle_id": overrides.get("bundle_id", "db-x"), "status": "ok",
        "created_at": "2026-07-08T10:05:00+00:00",
    }
    brief.update(overrides)
    (briefs_dir / f"{brief_id}.json").write_text(json.dumps(brief))


class ConsoleDataTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lisaos-console-data-test-"))
        self.bundles_dir = self.tmp / "bundles"
        self.briefs_dir = self.tmp / "briefs"
        self.notifications_dir = self.tmp / "notifications"
        self.audit_path = self.tmp / "audit.jsonl"
        self.registry_path = self.tmp / "employees.yml"
        self.evidence_path = self.tmp / "workforce_evidence.jsonl"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestBundles(ConsoleDataTestCase):
    def test_empty_dir_yields_empty_list(self) -> None:
        self.assertEqual(data.list_bundles(self.bundles_dir), [])

    def test_lists_newest_first(self) -> None:
        _write_bundle(self.bundles_dir, "db-1", created_at="2026-07-08T10:00:00+00:00")
        _write_bundle(self.bundles_dir, "db-2", created_at="2026-07-08T12:00:00+00:00")
        bundles = data.list_bundles(self.bundles_dir)
        self.assertEqual([b["bundle_id"] for b in bundles], ["db-2", "db-1"])

    def test_load_bundle_missing_returns_none(self) -> None:
        self.assertIsNone(data.load_bundle("no-such", bundles_dir=self.bundles_dir))

    def test_pending_approvals_excludes_decided_bundles(self) -> None:
        _write_bundle(self.bundles_dir, "db-pending", decision=None)
        _write_bundle(self.bundles_dir, "db-decided", decision={"choice": "approve", "by": "x", "at": "t", "note": "n"})
        pending = data.list_pending_approvals(self.bundles_dir)
        self.assertEqual([b["bundle_id"] for b in pending], ["db-pending"])

    def test_corrupt_bundle_file_skipped_not_crashed(self) -> None:
        bad_dir = self.bundles_dir / "db-corrupt"
        bad_dir.mkdir(parents=True)
        (bad_dir / "bundle.json").write_text("{not json")
        self.assertEqual(data.list_bundles(self.bundles_dir), [])


class TestBriefs(ConsoleDataTestCase):
    def test_briefs_for_bundle_filters_correctly(self) -> None:
        _write_brief(self.briefs_dir, "eb-1", bundle_id="db-a", created_at="2026-07-08T10:00:00+00:00")
        _write_brief(self.briefs_dir, "eb-2", bundle_id="db-b", created_at="2026-07-08T11:00:00+00:00")
        matches = data.briefs_for_bundle("db-a", self.briefs_dir)
        self.assertEqual([b["brief_id"] for b in matches], ["eb-1"])

    def test_latest_brief_for_bundle_picks_newest(self) -> None:
        _write_brief(self.briefs_dir, "eb-old", bundle_id="db-a", created_at="2026-07-08T09:00:00+00:00")
        _write_brief(self.briefs_dir, "eb-new", bundle_id="db-a", created_at="2026-07-08T11:00:00+00:00")
        latest = data.latest_brief_for_bundle("db-a", self.briefs_dir)
        self.assertEqual(latest["brief_id"], "eb-new")

    def test_load_brief_missing_returns_none(self) -> None:
        self.assertIsNone(data.load_brief("no-such", briefs_dir=self.briefs_dir))


class TestNotificationStatus(ConsoleDataTestCase):
    def test_missing_marker_returns_none(self) -> None:
        self.assertIsNone(data.notification_status_for_brief("eb-x", self.notifications_dir))

    def test_marker_present_returns_dict(self) -> None:
        self.notifications_dir.mkdir(parents=True)
        (self.notifications_dir / "eb-x.json").write_text(
            json.dumps({"brief_id": "eb-x", "sent_at": "t", "priority": "high"})
        )
        status = data.notification_status_for_brief("eb-x", self.notifications_dir)
        self.assertEqual(status["priority"], "high")


class TestWorkers(ConsoleDataTestCase):
    def test_parses_registry_and_annotates_participation(self) -> None:
        self.registry_path.write_text(yaml.dump({
            "employees": {
                "senior-software-engineer": {
                    "department": "engineering", "seniority": "senior",
                    "capabilities": ["code-implementation"], "preferred_model": "claude-sonnet",
                },
                "qa-engineer": {
                    "department": "quality-assurance", "seniority": "standard",
                    "capabilities": ["qa"], "preferred_model": "claude-haiku",
                },
            }
        }))
        self.evidence_path.write_text(
            json.dumps({"work_package_id": "j1", "employee": "senior-software-engineer"}) + "\n"
            + json.dumps({"work_package_id": "j2", "employee": "senior-software-engineer"}) + "\n"
        )
        workers = data.list_workers(registry_path=self.registry_path, evidence_path=self.evidence_path)
        by_id = {w["id"]: w for w in workers}
        self.assertEqual(by_id["senior-software-engineer"]["recent_assignments"], 2)
        self.assertEqual(by_id["qa-engineer"]["recent_assignments"], 0)

    def test_missing_registry_returns_empty_list(self) -> None:
        self.assertEqual(data.list_workers(registry_path=self.tmp / "does-not-exist.yml"), [])


class TestAudit(ConsoleDataTestCase):
    def test_tail_returns_newest_first(self) -> None:
        self.audit_path.write_text(
            json.dumps({"event": "a", "at": "1"}) + "\n" + json.dumps({"event": "b", "at": "2"}) + "\n"
        )
        entries = data.tail_audit(audit_path=self.audit_path)
        self.assertEqual([e["event"] for e in entries], ["b", "a"])

    def test_missing_audit_file_returns_empty_list(self) -> None:
        self.assertEqual(data.tail_audit(audit_path=self.tmp / "no-such.jsonl"), [])

    def test_limit_respected(self) -> None:
        lines = "\n".join(json.dumps({"event": str(i), "at": str(i)}) for i in range(10))
        self.audit_path.write_text(lines + "\n")
        entries = data.tail_audit(audit_path=self.audit_path, limit=3)
        self.assertEqual(len(entries), 3)


class TestDashboardSummary(ConsoleDataTestCase):
    def test_counts_are_correct(self) -> None:
        _write_bundle(self.bundles_dir, "db-1", decision=None)
        _write_bundle(self.bundles_dir, "db-2", decision={"choice": "approve", "by": "x", "at": "t", "note": "n"})
        _write_bundle(self.bundles_dir, "db-3", decision={"choice": "reject", "by": "x", "at": "t", "note": "n"})
        _write_brief(self.briefs_dir, "eb-1", status="ok")
        _write_brief(self.briefs_dir, "eb-2", status="degraded")
        self.audit_path.write_text(
            json.dumps({"event": "ntfy_sent", "at": "t"}) + "\n"
            + json.dumps({"event": "ntfy_failed", "at": "t"}) + "\n"
        )
        summary = data.dashboard_summary(
            bundles_dir=self.bundles_dir, briefs_dir=self.briefs_dir, audit_path=self.audit_path,
            registry_path=self.tmp / "no-registry.yml", evidence_path=self.tmp / "no-evidence.jsonl",
        )
        self.assertEqual(summary["bundle_count"], 3)
        self.assertEqual(summary["pending_count"], 1)
        self.assertEqual(summary["approved_count"], 1)
        self.assertEqual(summary["rejected_count"], 1)
        self.assertEqual(summary["brief_ok_count"], 1)
        self.assertEqual(summary["brief_degraded_count"], 1)
        self.assertEqual(summary["notification_sent"], 1)
        self.assertEqual(summary["notification_failed"], 1)


if __name__ == "__main__":
    unittest.main()
