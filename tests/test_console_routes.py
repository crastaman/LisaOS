"""Tests for console.app (Lisa Console v1, Phase C4) -- full route
coverage via Flask's test client. No real server is started; no test
makes a real network call.

console.app imports Flask, a console/-scoped dependency (see
console/requirements.txt) deliberately not installed for the bare
`python3 -m unittest discover` regression command used throughout Phases
C0-C3. This whole module is skipped (not failed) when Flask isn't
importable, so that standing command stays green; run it for real with
the project-local venv:

  PYTHONPATH="$HOME/Lisa" .venv/bin/python3 -m unittest tests.test_console_routes -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

try:
    from console.app import create_app

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

_SKIP_REASON = "flask not installed -- run under .venv (see console/requirements.txt)"

IDENTITY = "roshan@example.ts.net"
HEADERS = {"Tailscale-User-Login": IDENTITY}


def _write_bundle(bundles_dir: Path, bundle_id: str, **overrides) -> None:
    bundle_dir = bundles_dir / bundle_id
    bundle_dir.mkdir(parents=True)
    bundle = {
        "bundle_id": bundle_id, "schema": "lisaos.console.decision_bundle.v1",
        "job_id": f"job-{bundle_id}", "created_at": "2026-07-08T10:00:00+00:00",
        "decision": None, "approval_required": True, "objective": "demo",
        "participating_workers": [], "gaps": [],
        "audit_references": {"source_files": [], "raw_copy": "raw/x"},
    }
    bundle.update(overrides)
    (bundle_dir / "bundle.json").write_text(json.dumps(bundle))


def _write_brief(briefs_dir: Path, brief_id: str, **overrides) -> None:
    briefs_dir.mkdir(parents=True, exist_ok=True)
    brief = {
        "brief_id": brief_id, "schema": "lisaos.console.executive_brief.v1",
        "bundle_id": overrides.get("bundle_id", "db-x"), "status": "ok",
        "created_at": "2026-07-08T10:05:00+00:00", "headline": "demo",
        "recommendation": "approve", "confidence": "high",
        "key_risks": [], "suggested_actions": [], "missing_information": [],
        "escalation_recommendation": {"level": "none", "reason": None},
        "degraded_category": None, "degraded_reason": None,
    }
    brief.update(overrides)
    (briefs_dir / f"{brief_id}.json").write_text(json.dumps(brief))


@unittest.skipUnless(FLASK_AVAILABLE, _SKIP_REASON)
class ConsoleRoutesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lisaos-console-routes-test-"))
        self.bundles_dir = self.tmp / "bundles"
        self.briefs_dir = self.tmp / "briefs"
        self.notifications_dir = self.tmp / "notifications"
        self.audit_path = self.tmp / "audit.jsonl"
        self.registry_path = self.tmp / "employees.yml"
        self.registry_path.write_text(yaml.dump({"employees": {}}))
        self.evidence_path = self.tmp / "workforce_evidence.jsonl"

        import os
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = IDENTITY

        self.app = create_app(config={
            "BUNDLES_DIR": self.bundles_dir, "BRIEFS_DIR": self.briefs_dir,
            "NOTIFICATIONS_DIR": self.notifications_dir, "AUDIT_PATH": self.audit_path,
            "REGISTRY_PATH": self.registry_path, "EVIDENCE_PATH": self.evidence_path,
        })
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestAuthGating(ConsoleRoutesTestCase):
    def test_every_screen_requires_identity(self) -> None:
        for path in ["/", "/bundles", "/briefs", "/approvals", "/workers", "/audit"]:
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 403)

    def test_correct_identity_grants_access(self) -> None:
        r = self.client.get("/", headers=HEADERS)
        self.assertEqual(r.status_code, 200)


class TestEmptyStateRendersCleanly(ConsoleRoutesTestCase):
    def test_all_list_screens_200_when_empty(self) -> None:
        for path in ["/", "/bundles", "/briefs", "/approvals", "/workers", "/audit"]:
            with self.subTest(path=path):
                r = self.client.get(path, headers=HEADERS)
                self.assertEqual(r.status_code, 200)

    def test_missing_bundle_and_brief_404(self) -> None:
        self.assertEqual(self.client.get("/bundles/no-such", headers=HEADERS).status_code, 404)
        self.assertEqual(self.client.get("/brief/no-such", headers=HEADERS).status_code, 404)
        self.assertEqual(self.client.get("/approvals/no-such", headers=HEADERS).status_code, 404)


class TestPopulatedScreens(ConsoleRoutesTestCase):
    def setUp(self) -> None:
        super().setUp()
        _write_bundle(self.bundles_dir, "db-1")
        _write_brief(self.briefs_dir, "eb-1", bundle_id="db-1")

    def test_bundle_detail_200(self) -> None:
        r = self.client.get("/bundles/db-1", headers=HEADERS)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"db-1", r.data)

    def test_brief_detail_uses_singular_route_matching_ntfy_deep_link(self) -> None:
        # advisors.notify.build_payload() constructs f"{base_url}/brief/{brief_id}"
        # (singular) -- this route must match that exact shape.
        r = self.client.get("/brief/eb-1", headers=HEADERS)
        self.assertEqual(r.status_code, 200)

    def test_approval_detail_200(self) -> None:
        r = self.client.get("/approvals/db-1", headers=HEADERS)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Approve", r.data)
        self.assertIn(b"Reject", r.data)

    def test_pending_bundle_appears_in_approvals_list(self) -> None:
        r = self.client.get("/approvals", headers=HEADERS)
        self.assertIn(b"db-1", r.data)

    def test_decided_bundle_absent_from_approvals_list(self) -> None:
        self.client.post(
            "/approvals/db-1/decide", data={"choice": "approve", "note": "fine"}, headers=HEADERS
        )
        r = self.client.get("/approvals", headers=HEADERS)
        self.assertNotIn(b"db-1", r.data)


class TestDecideFlow(ConsoleRoutesTestCase):
    def setUp(self) -> None:
        super().setUp()
        _write_bundle(self.bundles_dir, "db-1")

    def test_approve_with_note_redirects_to_bundle_detail(self) -> None:
        r = self.client.post(
            "/approvals/db-1/decide", data={"choice": "approve", "note": "looks good"}, headers=HEADERS
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("/bundles/db-1", r.headers["Location"])

    def test_reject_requires_nonempty_note(self) -> None:
        r = self.client.post(
            "/approvals/db-1/decide", data={"choice": "reject", "note": ""}, headers=HEADERS
        )
        self.assertEqual(r.status_code, 400)

    def test_invalid_choice_rejected(self) -> None:
        r = self.client.post(
            "/approvals/db-1/decide", data={"choice": "execute", "note": "n"}, headers=HEADERS
        )
        self.assertEqual(r.status_code, 400)

    def test_second_decision_attempt_rejected(self) -> None:
        self.client.post("/approvals/db-1/decide", data={"choice": "approve", "note": "first"}, headers=HEADERS)
        r = self.client.post("/approvals/db-1/decide", data={"choice": "reject", "note": "second"}, headers=HEADERS)
        self.assertEqual(r.status_code, 400)

    def test_decide_route_requires_identity_too(self) -> None:
        r = self.client.post("/approvals/db-1/decide", data={"choice": "approve", "note": "n"})
        self.assertEqual(r.status_code, 403)

    def test_decision_appears_in_audit_tail(self) -> None:
        self.client.post("/approvals/db-1/decide", data={"choice": "approve", "note": "fine"}, headers=HEADERS)
        r = self.client.get("/audit", headers=HEADERS)
        self.assertIn(b"decision_recorded", r.data)


class TestNoExecutionCapableRoutes(ConsoleRoutesTestCase):
    """Structural proof: no 'run', 'execute', 'retry', or 'force' route
    exists anywhere in the app, and the only two POST-able form values on
    the decide route are approve/reject.
    """

    FORBIDDEN_WORDS = ("run", "execute", "retry", "force", "dispatch")

    def test_no_route_rule_contains_a_forbidden_action_word(self) -> None:
        for rule in self.app.url_map.iter_rules():
            rule_text = rule.rule.lower()
            for word in self.FORBIDDEN_WORDS:
                self.assertNotIn(
                    word, rule_text,
                    f"route {rule.rule!r} contains forbidden action word {word!r}",
                )

    def test_only_one_post_route_exists_and_it_is_decide(self) -> None:
        post_routes = [
            rule.rule for rule in self.app.url_map.iter_rules()
            if "POST" in rule.methods and rule.rule != "/static/<path:filename>"
        ]
        self.assertEqual(post_routes, ["/approvals/<bundle_id>/decide"])


if __name__ == "__main__":
    unittest.main()
