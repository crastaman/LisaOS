"""Tests for advisors.openai_client (Lisa Console v1, Phase C2).

No test in this file makes a real network call -- urllib.request.urlopen is
monkeypatched throughout. Credentials tests rely on
LISA_CONSOLE_OPENAI_API_KEY being genuinely unset in the test environment.

Run: PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_openai_client -v
"""

from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from advisors.openai_client import (
    AdvisorAPIError,
    AdvisorCredentialsError,
    CATEGORY_CONTEXT_OVERFLOW,
    CATEGORY_INVALID_RESPONSE,
    CATEGORY_RATE_LIMITED,
    CATEGORY_TIMEOUT,
    CATEGORY_UNAVAILABLE,
    call_chat_completion,
)


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _chat_completion_body(content_obj: dict) -> bytes:
    return json.dumps({
        "choices": [{"message": {"content": json.dumps(content_obj)}}]
    }).encode("utf-8")


class TestCredentialsFailClosed(unittest.TestCase):
    def test_missing_key_raises_before_any_network_call(self) -> None:
        self.assertNotIn("LISA_CONSOLE_OPENAI_API_KEY", os.environ)
        with patch("urllib.request.urlopen") as mock_urlopen:
            with self.assertRaises(AdvisorCredentialsError):
                call_chat_completion(system_prompt="s", user_prompt="u")
            mock_urlopen.assert_not_called()


class TestSuccessPath(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LISA_CONSOLE_OPENAI_API_KEY"] = "test-key-not-real"

    def tearDown(self) -> None:
        del os.environ["LISA_CONSOLE_OPENAI_API_KEY"]

    def test_parses_json_content_from_response(self) -> None:
        body = _chat_completion_body({"headline": "ok", "recommendation": "approve"})
        with patch("urllib.request.urlopen", return_value=_FakeResponse(body)):
            result = call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(result["headline"], "ok")

    def test_key_never_appears_in_request_url_only_header(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout=None):
            captured["auth_header"] = request.get_header("Authorization")
            captured["url"] = request.full_url
            return _FakeResponse(_chat_completion_body({"x": 1}))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(captured["auth_header"], "Bearer test-key-not-real")
        self.assertNotIn("test-key-not-real", captured["url"])


class TestFailureCategorization(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LISA_CONSOLE_OPENAI_API_KEY"] = "test-key-not-real"

    def tearDown(self) -> None:
        del os.environ["LISA_CONSOLE_OPENAI_API_KEY"]

    def _http_error(self, code: int, body: bytes) -> urllib.error.HTTPError:
        return urllib.error.HTTPError(
            url="https://api.openai.com/v1/chat/completions", code=code,
            msg="error", hdrs=None, fp=io.BytesIO(body),
        )

    def test_429_is_rate_limited(self) -> None:
        with patch("urllib.request.urlopen", side_effect=self._http_error(429, b"rate limited")):
            with self.assertRaises(AdvisorAPIError) as ctx:
                call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(ctx.exception.category, CATEGORY_RATE_LIMITED)

    def test_500_is_unavailable(self) -> None:
        with patch("urllib.request.urlopen", side_effect=self._http_error(500, b"server error")):
            with self.assertRaises(AdvisorAPIError) as ctx:
                call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(ctx.exception.category, CATEGORY_UNAVAILABLE)

    def test_400_context_length_is_context_overflow(self) -> None:
        body = b'{"error": {"message": "maximum context_length exceeded"}}'
        with patch("urllib.request.urlopen", side_effect=self._http_error(400, body)):
            with self.assertRaises(AdvisorAPIError) as ctx:
                call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(ctx.exception.category, CATEGORY_CONTEXT_OVERFLOW)

    def test_400_other_is_invalid_response(self) -> None:
        with patch("urllib.request.urlopen", side_effect=self._http_error(400, b"bad request")):
            with self.assertRaises(AdvisorAPIError) as ctx:
                call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(ctx.exception.category, CATEGORY_INVALID_RESPONSE)

    def test_url_error_is_unavailable(self) -> None:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            with self.assertRaises(AdvisorAPIError) as ctx:
                call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(ctx.exception.category, CATEGORY_UNAVAILABLE)

    def test_url_error_timeout_reason_is_timeout(self) -> None:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
            with self.assertRaises(AdvisorAPIError) as ctx:
                call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(ctx.exception.category, CATEGORY_TIMEOUT)

    def test_direct_timeout_error_is_timeout(self) -> None:
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(AdvisorAPIError) as ctx:
                call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(ctx.exception.category, CATEGORY_TIMEOUT)

    def test_malformed_json_content_is_invalid_response(self) -> None:
        body = json.dumps({"choices": [{"message": {"content": "not valid json"}}]}).encode()
        with patch("urllib.request.urlopen", return_value=_FakeResponse(body)):
            with self.assertRaises(AdvisorAPIError) as ctx:
                call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(ctx.exception.category, CATEGORY_INVALID_RESPONSE)

    def test_missing_choices_key_is_invalid_response(self) -> None:
        body = json.dumps({"no_choices_here": True}).encode()
        with patch("urllib.request.urlopen", return_value=_FakeResponse(body)):
            with self.assertRaises(AdvisorAPIError) as ctx:
                call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(ctx.exception.category, CATEGORY_INVALID_RESPONSE)

    def test_json_content_not_an_object_is_invalid_response(self) -> None:
        body = _chat_completion_body_raw_content("[1, 2, 3]")
        with patch("urllib.request.urlopen", return_value=_FakeResponse(body)):
            with self.assertRaises(AdvisorAPIError) as ctx:
                call_chat_completion(system_prompt="s", user_prompt="u")
        self.assertEqual(ctx.exception.category, CATEGORY_INVALID_RESPONSE)


def _chat_completion_body_raw_content(raw_content: str) -> bytes:
    return json.dumps({"choices": [{"message": {"content": raw_content}}]}).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
