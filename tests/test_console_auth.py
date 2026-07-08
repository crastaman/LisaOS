"""Tests for console.auth (Lisa Console v1, Phase C4).

console.auth imports Flask, which is a console/-scoped dependency (see
console/requirements.txt), not a LisaOS core dependency -- it is
deliberately not installed for the bare `python3 -m unittest discover`
regression command used throughout Phases C0-C3. This whole module is
skipped (not failed) when Flask isn't importable, so that standing
command stays green; run it for real with the project-local venv:

  PYTHONPATH="$HOME/Lisa" .venv/bin/python3 -m unittest tests.test_console_auth -v
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

    from console.auth import allowed_identities, init_app

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

_SKIP_REASON = "flask not installed -- run under .venv (see console/requirements.txt)"


@unittest.skipUnless(FLASK_AVAILABLE, _SKIP_REASON)
class ConsoleAuthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lisaos-console-auth-test-"))
        self.audit_path = self.tmp / "audit.jsonl"
        self._old_env = os.environ.get("LISA_CONSOLE_OWNER_IDENTITY")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self._old_env is None:
            os.environ.pop("LISA_CONSOLE_OWNER_IDENTITY", None)
        else:
            os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = self._old_env

    def _app(self) -> Flask:
        app = Flask(__name__)
        init_app(app, audit_path=self.audit_path)

        @app.route("/ping")
        def ping():
            return "pong"

        return app


@unittest.skipUnless(FLASK_AVAILABLE, _SKIP_REASON)
class TestAllowedIdentities(unittest.TestCase):
    def test_empty_string_yields_empty_set(self) -> None:
        self.assertEqual(allowed_identities(""), set())

    def test_single_identity(self) -> None:
        self.assertEqual(allowed_identities("roshan@example.ts.net"), {"roshan@example.ts.net"})

    def test_comma_separated_list_with_whitespace(self) -> None:
        self.assertEqual(
            allowed_identities(" a@x.ts.net , b@x.ts.net ,c@x.ts.net"),
            {"a@x.ts.net", "b@x.ts.net", "c@x.ts.net"},
        )


class TestCheckAccess(ConsoleAuthTestCase):
    def test_missing_header_denied_and_audited(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        client = self._app().test_client()
        r = client.get("/ping")
        self.assertEqual(r.status_code, 403)
        record = json.loads(self.audit_path.read_text().strip().splitlines()[0])
        self.assertEqual(record["event"], "access_denied")
        self.assertIsNone(record["identity"])

    def test_wrong_identity_denied_and_audited(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        client = self._app().test_client()
        r = client.get("/ping", headers={"Tailscale-User-Login": "intruder@other.ts.net"})
        self.assertEqual(r.status_code, 403)
        record = json.loads(self.audit_path.read_text().strip().splitlines()[0])
        self.assertEqual(record["event"], "access_denied")
        self.assertEqual(record["identity"], "intruder@other.ts.net")

    def test_correct_identity_granted_and_audited(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        client = self._app().test_client()
        r = client.get("/ping", headers={"Tailscale-User-Login": "roshan@example.ts.net"})
        self.assertEqual(r.status_code, 200)
        record = json.loads(self.audit_path.read_text().strip().splitlines()[0])
        self.assertEqual(record["event"], "access_granted")
        self.assertEqual(record["identity"], "roshan@example.ts.net")

    def test_empty_allowlist_fails_closed_even_with_a_header(self) -> None:
        os.environ.pop("LISA_CONSOLE_OWNER_IDENTITY", None)
        client = self._app().test_client()
        r = client.get("/ping", headers={"Tailscale-User-Login": "anyone@example.ts.net"})
        self.assertEqual(r.status_code, 403)

    def test_every_request_is_audited_including_repeated_ones(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        client = self._app().test_client()
        client.get("/ping", headers={"Tailscale-User-Login": "roshan@example.ts.net"})
        client.get("/ping", headers={"Tailscale-User-Login": "roshan@example.ts.net"})
        client.get("/ping")
        lines = self.audit_path.read_text().strip().splitlines()
        self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
