"""Tests for console.actions (Lisa Console v1, Phase C4) -- the Safe
Action Model. This is the only write path in the Console besides
console.auth's access-attempt logging.

Run: PYTHONPATH="$HOME/Lisa" .venv/bin/python3 -m unittest tests.test_console_actions -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from console.actions import (
    AlreadyDecidedError,
    BundleNotFoundError,
    InvalidDecisionError,
    record_decision,
)


def _write_bundle(bundles_dir: Path, bundle_id: str, **overrides) -> Path:
    bundle_dir = bundles_dir / bundle_id
    bundle_dir.mkdir(parents=True)
    bundle = {
        "bundle_id": bundle_id, "schema": "lisaos.console.decision_bundle.v1",
        "job_id": "job-x", "created_at": "2026-07-08T10:00:00+00:00", "decision": None,
    }
    bundle.update(overrides)
    path = bundle_dir / "bundle.json"
    path.write_text(json.dumps(bundle))
    return path


class ConsoleActionsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lisaos-console-actions-test-"))
        self.bundles_dir = self.tmp / "bundles"
        self.audit_path = self.tmp / "audit.jsonl"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestRecordDecisionSuccess(ConsoleActionsTestCase):
    def test_approve_writes_decision_field(self) -> None:
        _write_bundle(self.bundles_dir, "db-1")
        bundle = record_decision(
            "db-1", choice="approve", actor="roshan", note="looks fine",
            bundles_dir=self.bundles_dir, audit_path=self.audit_path,
        )
        self.assertEqual(bundle["decision"]["choice"], "approve")
        self.assertEqual(bundle["decision"]["by"], "roshan")
        self.assertEqual(bundle["decision"]["note"], "looks fine")

    def test_reject_writes_decision_field(self) -> None:
        _write_bundle(self.bundles_dir, "db-1")
        bundle = record_decision(
            "db-1", choice="reject", actor="roshan", note="too risky",
            bundles_dir=self.bundles_dir, audit_path=self.audit_path,
        )
        self.assertEqual(bundle["decision"]["choice"], "reject")

    def test_decision_persisted_to_disk(self) -> None:
        path = _write_bundle(self.bundles_dir, "db-1")
        record_decision(
            "db-1", choice="approve", actor="roshan", note="ok",
            bundles_dir=self.bundles_dir, audit_path=self.audit_path,
        )
        reloaded = json.loads(path.read_text())
        self.assertEqual(reloaded["decision"]["choice"], "approve")
        self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_appends_audit_entry(self) -> None:
        _write_bundle(self.bundles_dir, "db-1")
        record_decision(
            "db-1", choice="approve", actor="roshan", note="ok",
            bundles_dir=self.bundles_dir, audit_path=self.audit_path,
        )
        record = json.loads(self.audit_path.read_text().strip().splitlines()[0])
        self.assertEqual(record["event"], "decision_recorded")
        self.assertEqual(record["choice"], "approve")
        self.assertEqual(record["actor"], "roshan")


class TestRecordDecisionValidation(ConsoleActionsTestCase):
    def test_invalid_choice_rejected(self) -> None:
        _write_bundle(self.bundles_dir, "db-1")
        with self.assertRaises(InvalidDecisionError):
            record_decision(
                "db-1", choice="execute", actor="roshan", note="n",
                bundles_dir=self.bundles_dir, audit_path=self.audit_path,
            )

    def test_empty_note_rejected_on_approve(self) -> None:
        _write_bundle(self.bundles_dir, "db-1")
        with self.assertRaises(InvalidDecisionError):
            record_decision(
                "db-1", choice="approve", actor="roshan", note="",
                bundles_dir=self.bundles_dir, audit_path=self.audit_path,
            )

    def test_empty_note_rejected_on_reject(self) -> None:
        _write_bundle(self.bundles_dir, "db-1")
        with self.assertRaises(InvalidDecisionError):
            record_decision(
                "db-1", choice="reject", actor="roshan", note="   ",
                bundles_dir=self.bundles_dir, audit_path=self.audit_path,
            )

    def test_missing_actor_rejected(self) -> None:
        _write_bundle(self.bundles_dir, "db-1")
        with self.assertRaises(InvalidDecisionError):
            record_decision(
                "db-1", choice="approve", actor="", note="ok",
                bundles_dir=self.bundles_dir, audit_path=self.audit_path,
            )

    def test_missing_bundle_raises(self) -> None:
        with self.assertRaises(BundleNotFoundError):
            record_decision(
                "no-such", choice="approve", actor="roshan", note="ok",
                bundles_dir=self.bundles_dir, audit_path=self.audit_path,
            )

    def test_invalid_attempts_never_touch_the_bundle_file(self) -> None:
        path = _write_bundle(self.bundles_dir, "db-1")
        original = path.read_text()
        try:
            record_decision(
                "db-1", choice="execute", actor="roshan", note="n",
                bundles_dir=self.bundles_dir, audit_path=self.audit_path,
            )
        except InvalidDecisionError:
            pass
        self.assertEqual(path.read_text(), original)


class TestAlreadyDecided(ConsoleActionsTestCase):
    def test_second_decision_on_same_bundle_rejected(self) -> None:
        _write_bundle(self.bundles_dir, "db-1")
        record_decision(
            "db-1", choice="approve", actor="roshan", note="first",
            bundles_dir=self.bundles_dir, audit_path=self.audit_path,
        )
        with self.assertRaises(AlreadyDecidedError):
            record_decision(
                "db-1", choice="reject", actor="roshan", note="changed my mind",
                bundles_dir=self.bundles_dir, audit_path=self.audit_path,
            )

    def test_first_decision_not_overwritten_by_failed_second_attempt(self) -> None:
        _write_bundle(self.bundles_dir, "db-1")
        record_decision(
            "db-1", choice="approve", actor="roshan", note="first",
            bundles_dir=self.bundles_dir, audit_path=self.audit_path,
        )
        try:
            record_decision(
                "db-1", choice="reject", actor="roshan", note="changed my mind",
                bundles_dir=self.bundles_dir, audit_path=self.audit_path,
            )
        except AlreadyDecidedError:
            pass
        bundle_path = self.bundles_dir / "db-1" / "bundle.json"
        reloaded = json.loads(bundle_path.read_text())
        self.assertEqual(reloaded["decision"]["choice"], "approve")
        self.assertEqual(reloaded["decision"]["note"], "first")


if __name__ == "__main__":
    unittest.main()
