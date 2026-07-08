"""Tests for advisors.notify (Lisa Console v1, Phase C3).

No test in this file makes a real network call to ntfy.sh -- either
publish_fn is injected directly, or urllib.request.urlopen is
monkeypatched (mirroring tests/test_openai_client.py's approach).
Hermetic: every test uses tempfile.mkdtemp() for notifications_dir/audit_path.

Run: PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_notify -v
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from advisors.notify import (
    CATEGORY_NOT_CONFIGURED,
    CATEGORY_RATE_LIMITED,
    CATEGORY_TIMEOUT,
    CATEGORY_UNAVAILABLE,
    _send_once,
    build_payload,
    send_notification,
)

FORBIDDEN_MARKERS = [
    "SECRET_API_KEY_MARKER",
    "/Users/lisa/Lisa/secret-path",
    "customer-ssn-123-45-6789",
    "WORKER_TRANSCRIPT_MARKER",
    "STACK_TRACE_MARKER",
]


def _ok_brief(**overrides) -> dict:
    brief = {
        "brief_id": "eb-2026-07-08-test0001",
        "schema": "lisaos.console.executive_brief.v1",
        "bundle_id": "db-2026-07-08-test0001",
        "status": "ok",
        "headline": "Fix looks safe to merge",
        "summary": "A long evidence-grounded summary that should never leave LisaOS.",
        "recommendation": "approve",
        "confidence": "high",
        "key_risks": ["deploy-prod touches production"],
        "suggested_actions": ["Merge after CI"],
        "missing_information": [],
        "escalation_recommendation": {"level": "none", "reason": None},
    }
    brief.update(overrides)
    return brief


class NotifyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lisaos-notify-test-"))
        self.notifications_dir = self.tmp / "notifications"
        self.audit_path = self.tmp / "audit.jsonl"
        # Make sure ambient env vars never leak into a hermetic test.
        for var in ("LISA_CONSOLE_NTFY_TOPIC", "LISA_CONSOLE_NTFY_TOKEN",
                    "LISA_CONSOLE_NTFY_SERVER", "LISA_CONSOLE_BASE_URL"):
            os.environ.pop(var, None)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestBuildPayloadAllowlist(NotifyTestCase):
    def test_payload_has_exactly_the_allowed_keys(self) -> None:
        payload = build_payload(_ok_brief())
        self.assertEqual(
            set(payload.keys()),
            {"brief_id", "headline", "recommendation_summary", "confidence",
             "priority", "timestamp", "console_deep_link"},
        )

    def test_forbidden_content_never_reaches_payload_even_when_present_on_brief(self) -> None:
        brief = _ok_brief(
            summary="Contains SECRET_API_KEY_MARKER and /Users/lisa/Lisa/secret-path",
            key_risks=["customer-ssn-123-45-6789", "WORKER_TRANSCRIPT_MARKER"],
            evidence={"raw": "STACK_TRACE_MARKER"},
        )
        payload = build_payload(brief)
        payload_text = json.dumps(payload)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, payload_text, f"forbidden marker {marker!r} leaked into payload")

    def test_bundle_id_never_in_payload(self) -> None:
        payload = build_payload(_ok_brief())
        self.assertNotIn("bundle_id", payload)

    def test_degraded_brief_produces_safe_fallback_text(self) -> None:
        brief = {
            "brief_id": "eb-degraded",
            "status": "degraded",
            "headline": None,
            "recommendation": None,
            "confidence": None,
            "degraded_category": "unavailable",
            "degraded_reason": "OpenAI API unavailable (500): <internal error detail that must not leak>",
        }
        payload = build_payload(brief)
        self.assertNotIn("internal error detail", payload["recommendation_summary"])
        self.assertNotIn("internal error detail", payload["headline"])
        self.assertEqual(payload["confidence"], None)

    def test_deep_link_uses_base_url_and_brief_id(self) -> None:
        payload = build_payload(_ok_brief(), base_url="https://lisa.example.ts.net")
        self.assertEqual(payload["console_deep_link"], "https://lisa.example.ts.net/brief/eb-2026-07-08-test0001")

    def test_deep_link_omitted_when_no_base_url(self) -> None:
        payload = build_payload(_ok_brief(), base_url="")
        self.assertIsNone(payload["console_deep_link"])

    def test_priority_high_on_reject(self) -> None:
        payload = build_payload(_ok_brief(recommendation="reject"))
        self.assertEqual(payload["priority"], "high")

    def test_priority_urgent_on_escalation(self) -> None:
        payload = build_payload(_ok_brief(escalation_recommendation={"level": "urgent", "reason": "x"}))
        self.assertEqual(payload["priority"], "urgent")

    def test_headline_truncated_to_140_chars(self) -> None:
        payload = build_payload(_ok_brief(headline="x" * 500))
        self.assertEqual(len(payload["headline"]), 140)

    def test_missing_brief_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_payload({"headline": "no id"})


class TestNotConfigured(NotifyTestCase):
    def test_missing_topic_never_attempts_network_and_is_audited(self) -> None:
        called = {"n": 0}

        def publish_fn(**kwargs):
            called["n"] += 1

        result = send_notification(
            _ok_brief(), publish_fn=publish_fn,
            notifications_dir=self.notifications_dir, audit_path=self.audit_path,
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.category, CATEGORY_NOT_CONFIGURED)
        self.assertEqual(called["n"], 0)
        lines = self.audit_path.read_text().strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["category"], CATEGORY_NOT_CONFIGURED)


class TestDuplicateSuppression(NotifyTestCase):
    def test_second_send_for_same_brief_id_is_suppressed(self) -> None:
        calls = {"n": 0}

        def publish_fn(**kwargs):
            calls["n"] += 1

        first = send_notification(
            _ok_brief(), topic="test-topic", publish_fn=publish_fn,
            notifications_dir=self.notifications_dir, audit_path=self.audit_path,
        )
        second = send_notification(
            _ok_brief(), topic="test-topic", publish_fn=publish_fn,
            notifications_dir=self.notifications_dir, audit_path=self.audit_path,
        )
        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "duplicate_suppressed")
        self.assertEqual(calls["n"], 1)

    def test_failed_send_is_not_marked_as_sent_and_can_retry_later(self) -> None:
        def always_fail(**kwargs):
            from advisors.notify import CATEGORY_UNAVAILABLE, _NotifyAPIError
            raise _NotifyAPIError("down", category=CATEGORY_UNAVAILABLE)

        first = send_notification(
            _ok_brief(), topic="test-topic", publish_fn=always_fail, max_attempts=1, backoff_seconds=0,
            notifications_dir=self.notifications_dir, audit_path=self.audit_path,
        )
        self.assertEqual(first.status, "failed")

        calls = {"n": 0}

        def now_succeeds(**kwargs):
            calls["n"] += 1

        second = send_notification(
            _ok_brief(), topic="test-topic", publish_fn=now_succeeds,
            notifications_dir=self.notifications_dir, audit_path=self.audit_path,
        )
        self.assertEqual(second.status, "sent")
        self.assertEqual(calls["n"], 1)


class TestRetryLogic(NotifyTestCase):
    def test_retries_up_to_max_attempts_then_succeeds(self) -> None:
        from advisors.notify import CATEGORY_UNAVAILABLE, _NotifyAPIError

        attempts = {"n": 0}

        def flaky(**kwargs):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise _NotifyAPIError("transient", category=CATEGORY_UNAVAILABLE)

        sleeps: list[float] = []
        result = send_notification(
            _ok_brief(), topic="test-topic", publish_fn=flaky, max_attempts=5,
            backoff_seconds=0.01, sleep_fn=sleeps.append,
            notifications_dir=self.notifications_dir, audit_path=self.audit_path,
        )
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.attempts, 3)
        self.assertEqual(len(sleeps), 2)  # slept before attempt 2 and attempt 3

    def test_exhausting_all_attempts_fails_and_is_audited(self) -> None:
        from advisors.notify import CATEGORY_TIMEOUT, _NotifyAPIError

        def always_timeout(**kwargs):
            raise _NotifyAPIError("slow", category=CATEGORY_TIMEOUT)

        result = send_notification(
            _ok_brief(), topic="test-topic", publish_fn=always_timeout, max_attempts=3,
            backoff_seconds=0, sleep_fn=lambda s: None,
            notifications_dir=self.notifications_dir, audit_path=self.audit_path,
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.category, CATEGORY_TIMEOUT)
        self.assertEqual(result.attempts, 3)
        lines = self.audit_path.read_text().strip().splitlines()
        record = json.loads(lines[-1])
        self.assertEqual(record["event"], "ntfy_failed")
        self.assertEqual(record["attempts"], 3)


class TestAuditLogging(NotifyTestCase):
    def test_successful_send_writes_one_audit_line(self) -> None:
        send_notification(
            _ok_brief(), topic="test-topic", publish_fn=lambda **k: None,
            notifications_dir=self.notifications_dir, audit_path=self.audit_path,
        )
        lines = self.audit_path.read_text().strip().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["event"], "ntfy_sent")
        self.assertEqual(record["brief_id"], "eb-2026-07-08-test0001")

    def test_audit_never_contains_forbidden_markers(self) -> None:
        brief = _ok_brief(key_risks=["customer-ssn-123-45-6789"])
        send_notification(
            brief, topic="test-topic", publish_fn=lambda **k: None,
            notifications_dir=self.notifications_dir, audit_path=self.audit_path,
        )
        audit_text = self.audit_path.read_text()
        self.assertNotIn("customer-ssn-123-45-6789", audit_text)


class TestSendOnceHTTP(unittest.TestCase):
    """Direct tests of the provider function, mirroring test_openai_client.py."""

    def _http_error(self, code: int, body: bytes) -> urllib.error.HTTPError:
        return urllib.error.HTTPError(
            url="https://ntfy.sh/test-topic", code=code, msg="error", hdrs=None, fp=io.BytesIO(body)
        )

    def test_token_used_only_in_authorization_header(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout=None):
            captured["auth"] = request.get_header("Authorization")
            captured["url"] = request.full_url
            captured["body"] = request.data.decode("utf-8")
            return io.BytesIO(b"{}")

        payload = build_payload(_ok_brief())
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            _send_once(
                server="https://ntfy.sh", topic="test-topic", token="super-secret-token",
                payload=payload, timeout_seconds=5,
            )
        self.assertEqual(captured["auth"], "Bearer super-secret-token")
        self.assertNotIn("super-secret-token", captured["url"])
        self.assertNotIn("super-secret-token", captured["body"])

    def test_429_is_rate_limited(self) -> None:
        from advisors.notify import _NotifyAPIError
        payload = build_payload(_ok_brief())
        with patch("urllib.request.urlopen", side_effect=self._http_error(429, b"slow down")):
            with self.assertRaises(_NotifyAPIError) as ctx:
                _send_once(server="https://ntfy.sh", topic="t", token=None, payload=payload, timeout_seconds=5)
        self.assertEqual(ctx.exception.category, CATEGORY_RATE_LIMITED)

    def test_503_is_unavailable(self) -> None:
        from advisors.notify import _NotifyAPIError
        payload = build_payload(_ok_brief())
        with patch("urllib.request.urlopen", side_effect=self._http_error(503, b"down")):
            with self.assertRaises(_NotifyAPIError) as ctx:
                _send_once(server="https://ntfy.sh", topic="t", token=None, payload=payload, timeout_seconds=5)
        self.assertEqual(ctx.exception.category, CATEGORY_UNAVAILABLE)

    def test_url_error_timeout(self) -> None:
        from advisors.notify import _NotifyAPIError
        payload = build_payload(_ok_brief())
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
            with self.assertRaises(_NotifyAPIError) as ctx:
                _send_once(server="https://ntfy.sh", topic="t", token=None, payload=payload, timeout_seconds=5)
        self.assertEqual(ctx.exception.category, CATEGORY_TIMEOUT)

    def test_connection_refused_is_unavailable(self) -> None:
        from advisors.notify import _NotifyAPIError
        payload = build_payload(_ok_brief())
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            with self.assertRaises(_NotifyAPIError) as ctx:
                _send_once(server="https://ntfy.sh", topic="t", token=None, payload=payload, timeout_seconds=5)
        self.assertEqual(ctx.exception.category, CATEGORY_UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
