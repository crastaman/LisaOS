"""Minimal OpenAI Chat Completions client (Lisa Console v1, Phase C2).

Stdlib only (urllib) -- no external dependency. This repo has no pinned
Python dependencies at all; tests/smoke_deepinfra.py uses the identical
urllib-only pattern against a different OpenAI-compatible endpoint, so this
follows established convention rather than introducing an SDK.

This module makes the one real network call anywhere in the GPT Advisor
pipeline. Everything upstream (advisors.context_pack, advisors.gpt_advisor)
is pure/file-only. No LisaOS runtime imports (core/, engines/) -- advisory
only, by construction: nothing in this module can execute, dispatch, or
schedule anything.

Security:
  * The API key is read from LISA_CONSOLE_OPENAI_API_KEY only -- never
    accepted as a parameter with a hardcoded fallback, never logged, never
    included in any exception message or return value. _api_key() is the
    only place this module touches the key; it is used solely to build the
    Authorization header for one outbound request.
  * Fails closed: no network call is attempted at all if the key is
    missing or empty.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_TOKENS = 1500

# Failure categories -- advisors.gpt_advisor maps these directly onto
# Executive Brief degraded_category values. Every value here corresponds to
# one of the required failure modes: unavailable, timeout, rate limiting,
# invalid responses, context overflow. "credentials" is raised as a
# separate exception type (AdvisorCredentialsError) since it's a fail-closed
# precondition, not an API failure.
CATEGORY_UNAVAILABLE = "unavailable"
CATEGORY_TIMEOUT = "timeout"
CATEGORY_RATE_LIMITED = "rate_limited"
CATEGORY_INVALID_RESPONSE = "invalid_response"
CATEGORY_CONTEXT_OVERFLOW = "context_overflow"


class AdvisorCredentialsError(Exception):
    """No API key configured. Fail closed -- never call out without one."""


class AdvisorAPIError(Exception):
    """Any OpenAI API failure. `category` is one of the CATEGORY_* constants."""

    def __init__(self, message: str, *, category: str):
        super().__init__(message)
        self.category = category


def _api_key() -> str:
    key = os.environ.get("LISA_CONSOLE_OPENAI_API_KEY", "").strip()
    if not key:
        raise AdvisorCredentialsError(
            "LISA_CONSOLE_OPENAI_API_KEY is not set -- failing closed. "
            "The GPT Advisor will not contact the OpenAI API without an "
            "explicit credential."
        )
    return key


def _safe_error_detail(exc: urllib.error.HTTPError) -> str:
    """Best-effort error body extraction. Never includes request headers/key."""
    try:
        return exc.read().decode("utf-8", errors="replace")[:500]
    except Exception:
        return "<no response body>"


def call_chat_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """One JSON-mode Chat Completions call. Returns the parsed JSON content dict.

    Raises AdvisorCredentialsError before any network call if no key is
    configured. Raises AdvisorAPIError, categorized, for every other
    failure mode. Callers are expected to catch both and enter degraded
    mode -- never let either propagate as an unhandled crash.
    """
    key = _api_key()
    model = model or os.environ.get("LISA_CONSOLE_OPENAI_MODEL", DEFAULT_MODEL)

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    request = urllib.request.Request(
        OPENAI_CHAT_COMPLETIONS_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = _safe_error_detail(exc)
        if exc.code == 429:
            raise AdvisorAPIError(
                f"OpenAI API rate limited (429): {detail}", category=CATEGORY_RATE_LIMITED
            ) from None
        if exc.code >= 500:
            raise AdvisorAPIError(
                f"OpenAI API unavailable ({exc.code}): {detail}", category=CATEGORY_UNAVAILABLE
            ) from None
        if exc.code == 400 and "context_length" in detail.lower():
            raise AdvisorAPIError(
                f"OpenAI API context overflow: {detail}", category=CATEGORY_CONTEXT_OVERFLOW
            ) from None
        raise AdvisorAPIError(
            f"OpenAI API error ({exc.code}): {detail}", category=CATEGORY_INVALID_RESPONSE
        ) from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            raise AdvisorAPIError(f"OpenAI API timed out: {reason}", category=CATEGORY_TIMEOUT) from None
        raise AdvisorAPIError(f"OpenAI API unavailable: {reason}", category=CATEGORY_UNAVAILABLE) from None
    except TimeoutError as exc:
        raise AdvisorAPIError(f"OpenAI API timed out: {exc}", category=CATEGORY_TIMEOUT) from None

    try:
        payload = json.loads(raw)
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
        raise AdvisorAPIError(
            f"OpenAI API returned an unparseable response: {exc}", category=CATEGORY_INVALID_RESPONSE
        ) from None

    if not isinstance(parsed, dict):
        raise AdvisorAPIError(
            "OpenAI API JSON content was not a JSON object", category=CATEGORY_INVALID_RESPONSE
        )

    return parsed
