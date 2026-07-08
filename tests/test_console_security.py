"""Phase C5 hardening tests: negative-path auth, replay, audit integrity,
and secret-handling proofs that go beyond Phase C4's baseline coverage
(tests.test_console_auth, tests.test_console_actions).

console.auth/console.app import Flask -- skipped (not failed) on the
bare system Python, same convention as tests.test_console_auth. Run for
real with: PYTHONPATH="$HOME/Lisa" .venv/bin/python3 -m unittest
tests.test_console_security -v
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

try:
    from flask import Flask

    from console.app import create_app
    from console.auth import IDENTITY_HEADER, MAX_IDENTITY_LENGTH, init_app

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

_SKIP_REASON = "flask not installed -- run under .venv (see console/requirements.txt)"

IDENTITY = "roshan@example.ts.net"


def _write_bundle(bundles_dir: Path, bundle_id: str, **overrides) -> None:
    bundle_dir = bundles_dir / bundle_id
    bundle_dir.mkdir(parents=True)
    bundle = {
        "bundle_id": bundle_id, "schema": "lisaos.console.decision_bundle.v1",
        "job_id": f"job-{bundle_id}", "created_at": "2026-07-08T10:00:00+00:00",
        "decision": None,
    }
    bundle.update(overrides)
    (bundle_dir / "bundle.json").write_text(json.dumps(bundle))


@unittest.skipUnless(FLASK_AVAILABLE, _SKIP_REASON)
class ConsoleSecurityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lisaos-console-security-test-"))
        self.audit_path = self.tmp / "audit.jsonl"
        self.bundles_dir = self.tmp / "bundles"
        self._old_env = os.environ.get("LISA_CONSOLE_OWNER_IDENTITY")
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = IDENTITY

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self._old_env is None:
            os.environ.pop("LISA_CONSOLE_OWNER_IDENTITY", None)
        else:
            os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = self._old_env

    def _bare_app(self) -> Flask:
        app = Flask(__name__)
        init_app(app, audit_path=self.audit_path)

        @app.route("/ping")
        def ping():
            return "pong"

        return app


class TestMalformedHeaders(ConsoleSecurityTestCase):
    def test_header_present_but_empty_denied(self) -> None:
        r = self._bare_app().test_client().get("/ping", headers={IDENTITY_HEADER: ""})
        self.assertEqual(r.status_code, 403)

    def test_header_whitespace_only_denied(self) -> None:
        r = self._bare_app().test_client().get("/ping", headers={IDENTITY_HEADER: "   "})
        self.assertEqual(r.status_code, 403)

    def test_oversized_header_denied_not_matched(self) -> None:
        huge = IDENTITY + ("x" * 10_000)
        r = self._bare_app().test_client().get("/ping", headers={IDENTITY_HEADER: huge})
        self.assertEqual(r.status_code, 403)

    def test_oversized_header_truncated_before_audit_write(self) -> None:
        huge = "x" * 50_000
        self._bare_app().test_client().get("/ping", headers={IDENTITY_HEADER: huge})
        record = json.loads(self.audit_path.read_text().strip().splitlines()[0])
        # The raw 50,000-char value must never be written verbatim -- only
        # a bounded prefix plus a truncation marker.
        self.assertLess(len(record["identity"]), MAX_IDENTITY_LENGTH + 50)
        self.assertIn("truncated", record["identity"])

    def test_header_exactly_at_limit_can_still_match(self) -> None:
        exact_identity = "a" * MAX_IDENTITY_LENGTH
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = exact_identity
        r = self._bare_app().test_client().get("/ping", headers={IDENTITY_HEADER: exact_identity})
        self.assertEqual(r.status_code, 200)

    def test_unicode_identity_handled_without_crashing(self) -> None:
        r = self._bare_app().test_client().get("/ping", headers={IDENTITY_HEADER: "wörker@tst.net "})
        self.assertEqual(r.status_code, 403)  # not on the allowlist, but must not 500

    def test_identity_value_safely_json_encoded_in_audit(self) -> None:
        # json.dumps() escapes any content -- a value containing quotes or
        # backslashes cannot corrupt the JSONL audit format.
        tricky = 'weird"value\\with/slashes'
        self._bare_app().test_client().get("/ping", headers={IDENTITY_HEADER: tricky})
        record = json.loads(self.audit_path.read_text().strip().splitlines()[0])
        self.assertEqual(record["identity"], tricky)


class TestReplay(ConsoleSecurityTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.briefs_dir = self.tmp / "briefs"
        _write_bundle(self.bundles_dir, "db-1")
        self.app = create_app(config={
            "BUNDLES_DIR": self.bundles_dir, "BRIEFS_DIR": self.briefs_dir,
            "NOTIFICATIONS_DIR": self.tmp / "notifications", "AUDIT_PATH": self.audit_path,
            "REGISTRY_PATH": self.tmp / "no-registry.yml", "EVIDENCE_PATH": self.tmp / "no-evidence.jsonl",
        })
        self.client = self.app.test_client()

    def test_replaying_the_same_decide_request_is_harmless(self) -> None:
        headers = {IDENTITY_HEADER: IDENTITY}
        body = {"choice": "approve", "note": "captured and replayed"}

        first = self.client.post("/approvals/db-1/decide", data=body, headers=headers)
        self.assertEqual(first.status_code, 302)

        # Replay the identical request verbatim.
        second = self.client.post("/approvals/db-1/decide", data=body, headers=headers)
        self.assertEqual(second.status_code, 400)

        bundle = json.loads((self.bundles_dir / "db-1" / "bundle.json").read_text())
        self.assertEqual(bundle["decision"]["note"], "captured and replayed")

        decision_events = [
            json.loads(line) for line in self.audit_path.read_text().strip().splitlines()
            if json.loads(line).get("event") == "decision_recorded"
        ]
        self.assertEqual(len(decision_events), 1)

    def test_repeated_get_requests_are_naturally_idempotent(self) -> None:
        headers = {IDENTITY_HEADER: IDENTITY}
        for _ in range(3):
            r = self.client.get("/bundles/db-1", headers=headers)
            self.assertEqual(r.status_code, 200)
        bundle = json.loads((self.bundles_dir / "db-1" / "bundle.json").read_text())
        self.assertIsNone(bundle["decision"])


class TestAuditIntegrity(ConsoleSecurityTestCase):
    def test_audit_file_only_ever_grows(self) -> None:
        app = self._bare_app()
        client = app.test_client()
        sizes = []
        for _ in range(5):
            client.get("/ping", headers={IDENTITY_HEADER: IDENTITY})
            sizes.append(self.audit_path.stat().st_size)
        self.assertEqual(sizes, sorted(sizes))
        self.assertLess(sizes[0], sizes[-1])

    def test_earlier_audit_lines_never_change(self) -> None:
        app = self._bare_app()
        client = app.test_client()
        client.get("/ping", headers={IDENTITY_HEADER: IDENTITY})
        first_line_v1 = self.audit_path.read_text().splitlines()[0]
        for _ in range(4):
            client.get("/ping", headers={IDENTITY_HEADER: "someone-else"})
        first_line_v2 = self.audit_path.read_text().splitlines()[0]
        self.assertEqual(first_line_v1, first_line_v2)

    def test_every_source_module_opens_audit_in_append_mode_only(self) -> None:
        # Structural proof, not just a runtime sample: grep every module
        # that touches audit.jsonl and confirm none opens it for
        # truncating write ("w" mode).
        repo_root = Path(__file__).resolve().parent.parent
        candidates = [
            repo_root / "console" / "auth.py",
            repo_root / "console" / "actions.py",
            repo_root / "core" / "decision_bundle_exporter.py",
            repo_root / "advisors" / "gpt_advisor.py",
            repo_root / "advisors" / "notify.py",
        ]
        for path in candidates:
            audit_open_lines = [
                line for line in path.read_text(encoding="utf-8").splitlines()
                if "audit_path.open(" in line or "AUDIT_LOG.open(" in line
            ]
            self.assertTrue(audit_open_lines, f"{path} never opens the audit log at all")
            for line in audit_open_lines:
                self.assertIn(
                    'open("a"', line,
                    f"{path} opens the audit log in a mode other than append: {line.strip()!r}",
                )


class TestSecretHandling(ConsoleSecurityTestCase):
    def test_openai_key_never_appears_in_audit_log(self) -> None:
        sentinel = "sk-SENTINEL-DO-NOT-LEAK-0000000000"
        os.environ["LISA_CONSOLE_OPENAI_API_KEY"] = sentinel
        try:
            from advisors.gpt_advisor import generate_and_write_brief
            from advisors.context_pack import ContextPack, ContextPackFile

            bundle = {
                "bundle_id": "db-1", "schema": "lisaos.console.decision_bundle.v1",
                "job_id": "job-1", "evidence": {"workforce_evidence": []}, "decision": None,
            }
            pack = ContextPack(text="fake", files=(ContextPackFile(path=Path("x"), order=1, mtime=0.0, size=0),))
            generate_and_write_brief(
                bundle, context_pack=pack,
                call_fn=lambda **k: {"headline": "h", "summary": "s", "recommendation": "approve",
                                       "confidence": "high", "key_risks": [], "suggested_actions": [],
                                       "missing_information": [], "escalation_recommendation": {"level": "none", "reason": None}},
                briefs_dir=self.tmp / "briefs", audit_path=self.audit_path,
            )
        finally:
            del os.environ["LISA_CONSOLE_OPENAI_API_KEY"]

        self.assertNotIn(sentinel, self.audit_path.read_text())

    def test_ntfy_token_never_appears_in_audit_log(self) -> None:
        sentinel = "ntfy-token-SENTINEL-DO-NOT-LEAK"
        from advisors.notify import send_notification

        send_notification(
            {"brief_id": "eb-1", "status": "ok", "headline": "h", "recommendation": "approve", "confidence": "high"},
            topic="test-topic", token=sentinel, publish_fn=lambda **k: None,
            notifications_dir=self.tmp / "notifications", audit_path=self.audit_path,
        )
        self.assertNotIn(sentinel, self.audit_path.read_text())


if __name__ == "__main__":
    unittest.main()
