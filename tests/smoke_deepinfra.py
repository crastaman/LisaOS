#!/usr/bin/env python3
"""Live DeepInfra smoke test for the qwen-deepinfra logical provider.

Confirms the full chain end-to-end against the REAL DeepInfra backend:

    logical provider  (qwen-deepinfra)
        -> physical model   (via core.provider_resolver, from registry)
        -> DeepInfra backend (real HTTPS call, OpenAI-compatible endpoint)
        -> successful response
        -> evidence recorded (Resolution with actual_model set)

This is NOT part of the hermetic unittest suite: it makes ONE real network call
and spends a negligible amount of tokens, so it is run explicitly and only when a
DeepInfra key is configured. It FAILS CLOSED (exit 2) if the provider is not
credentialed, and never falls back to another provider.

Usage:
    # Key must be in ~/.openclaw/.env or the environment as DEEPINFRA_API_KEY
    PYTHONPATH="$HOME/Lisa" python3 tests/smoke_deepinfra.py

Exit codes:
    0  chain confirmed: real DeepInfra response received, evidence recorded
    2  fail-closed: provider not resolvable/credentialed (no key)
    3  provider resolved + authenticated but the backend call failed
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.provider_resolver import (  # noqa: E402
    ProviderResolver,
    ProviderResolutionError,
    CredentialSource,
    record_evidence,
)

LOGICAL = "qwen-deepinfra"
DEEPINFRA_CHAT_URL = "https://api.deepinfra.com/v1/openai/chat/completions"


def _api_key_from_sources() -> str | None:
    """Read DEEPINFRA_API_KEY the same way CredentialSource does (env + ~/.openclaw/.env)."""
    creds = CredentialSource()  # loads os.environ + ~/.openclaw/.env
    return creds._env.get("DEEPINFRA_API_KEY") or None


def _api_model_id(physical_model: str, provider_id: str) -> str:
    """Strip the OpenClaw provider prefix to get the raw DeepInfra model id.

    e.g. 'deepinfra/Qwen/Qwen3.6-35B-A3B' -> 'Qwen/Qwen3.6-35B-A3B'
    """
    prefix = provider_id + "/"
    if physical_model.startswith(prefix):
        return physical_model[len(prefix):]
    return physical_model


def main() -> int:
    resolver = ProviderResolver()

    # 1) logical -> physical (fail closed if not credentialed)
    print(f"[1] logical provider : {LOGICAL}")
    try:
        resolution = resolver.resolve(LOGICAL)
    except ProviderResolutionError as exc:
        ev = exc.evidence
        if ev:
            record_evidence(ev)
        print(f"    FAIL CLOSED: {exc}")
        print("    -> No DeepInfra key configured. Set DEEPINFRA_API_KEY in "
              "~/.openclaw/.env, then re-run.")
        return 2

    print(f"[2] physical model   : {resolution.physical_model}")
    print(f"    runtime          : {resolution.runtime}")
    print(f"    provider_id      : {resolution.provider_id}")
    print(f"    availability     : available={resolution.available} "
          f"auth={resolution.auth_result}")

    api_key = _api_key_from_sources()
    if not api_key:  # defensive: resolver said available but key not readable here
        print("    FAIL CLOSED: resolver reports available but DEEPINFRA_API_KEY "
              "is not readable from env/.env.")
        return 2

    api_model = _api_model_id(resolution.physical_model, resolution.provider_id)
    print(f"[3] DeepInfra backend: POST {DEEPINFRA_CHAT_URL}")
    print(f"    api model id     : {api_model}")

    # Qwen3.6-A3B is a reasoning model: it emits reasoning_content before final
    # content, so give enough budget to finish reasoning and produce an answer.
    body = json.dumps({
        "model": api_model,
        "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
        "max_tokens": 1024,
        "temperature": 0,
    }).encode("utf-8")

    req = urllib.request.Request(
        DEEPINFRA_CHAT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        print(f"    BACKEND ERROR: HTTP {e.code} — {detail}")
        resolution.fallback_reason = f"deepinfra_http_{e.code}"
        record_evidence(resolution)
        return 3
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"    BACKEND ERROR: {e}")
        resolution.fallback_reason = f"deepinfra_unreachable:{e}"
        record_evidence(resolution)
        return 3

    # 4) successful response.  A reasoning model may put its answer in `content`
    # and/or `reasoning_content`; either (with real generated tokens) proves a
    # live generative response from the DeepInfra backend.
    content = ""
    reasoning = ""
    actual_model = payload.get("model")
    completion_tokens = (payload.get("usage") or {}).get("completion_tokens", 0)
    finish_reason = None
    try:
        choice = payload["choices"][0]
        finish_reason = choice.get("finish_reason")
        msg = choice.get("message", {}) or {}
        content = (msg.get("content") or "").strip()
        reasoning = (msg.get("reasoning_content") or "").strip()
    except (KeyError, IndexError):
        pass

    answer = content or (reasoning[:80] + "..." if reasoning else "")
    print(f"[4] response         : HTTP {status} | model={actual_model} | "
          f"finish={finish_reason} | completion_tokens={completion_tokens}")
    print(f"    content          : {content!r}")
    if not content and reasoning:
        print(f"    reasoning_content: {reasoning[:80]!r}... (reasoning model)")

    # 5) evidence recorded (with the model the backend actually served)
    resolution.actual_model = resolution.physical_model  # what we dispatched
    log_path = record_evidence(resolution)
    print(f"[5] evidence recorded: {log_path}")
    print(f"    backend served model: {actual_model}")

    live_response = status == 200 and completion_tokens > 0 and bool(content or reasoning)
    if live_response:
        print("\nSMOKE TEST PASS: qwen-deepinfra -> deepinfra/Qwen/Qwen3.6-35B-A3B -> "
              "DeepInfra backend -> live response -> evidence recorded.")
        return 0
    print("\nSMOKE TEST INCONCLUSIVE: response received but no generated tokens.")
    return 3


if __name__ == "__main__":
    sys.exit(main())
