"""Proof-of-work tests for LisaOS provider resolution.

Validates the execution-layer fix from reports/lisa/EXECUTION_LAYER_AUDIT.md:

  * DeepSeek resolves to the DeepSeek physical model.
  * Claude / Opus / Sonnet resolve to a Claude runtime + model.
  * Qwen (DeepInfra) fails CLOSED when no DeepInfra key exists.
  * No silent DeepSeek fallback ever occurs.
  * Spawn payloads explicitly carry the resolved model.
  * Resolution evidence is recorded.

Fully hermetic: credentials and config are injected, so there are NO real
provider/network calls and NO spend. Run with:

    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_provider_resolution -v
"""

import json
import tempfile
import unittest
from pathlib import Path

from core.provider_resolver import (
    ProviderResolver,
    ProviderResolutionError,
    CredentialSource,
    Resolution,
    record_evidence,
)

# The physical model we must never silently substitute (audit Defect B).
DEEPSEEK_PHYSICAL = "custom-api-deepseek-com/deepseek-reasoner"


# --------------------------------------------------------------------------- #
# Shared fixtures: a config mirroring registry/provider_resolution.yml and two
# credential scenarios (with and without a DeepInfra key).
# --------------------------------------------------------------------------- #

def make_config() -> dict:
    return {
        "version": 1,
        "providers": {
            "deepseek": {
                "physical_model": DEEPSEEK_PHYSICAL,
                "runtime": "openclaw",
                "provider_id": "custom-api-deepseek-com",
                "credential": {"type": "inline_api_key",
                               "openclaw_provider": "custom-api-deepseek-com"},
                "aliases": ["deepseek-reasoner", "ds"],
            },
            "claude": {
                "physical_model": "anthropic/claude-opus-4-8",
                "runtime": "claude-cli",
                "provider_id": "anthropic",
                "credential": {"type": "oauth", "provider": "claude-cli"},
                "aliases": ["opus", "claude-opus"],
            },
            "sonnet": {
                "physical_model": "anthropic/claude-sonnet-4-6",
                "runtime": "claude-cli",
                "provider_id": "anthropic",
                "credential": {"type": "oauth", "provider": "claude-cli"},
                "aliases": ["claude-sonnet"],
            },
            "qwen": {
                "physical_model": "deepinfra/Qwen/Qwen3.6-35B-A3B",
                "runtime": "openclaw",
                "provider_id": "deepinfra",
                "credential": {"type": "api_key", "env": "DEEPINFRA_API_KEY",
                               "openclaw_provider": "deepinfra"},
                "aliases": ["qwen-deepinfra", "deepinfra-qwen"],
            },
            "qwen-ali": {
                "physical_model": "codex-model-studio/qwen3.7-plus",
                "runtime": "openclaw",
                "provider_id": "codex-model-studio",
                "credential": {"type": "api_key", "env": "MODEL_STUDIO_API_KEY",
                               "openclaw_provider": "codex-model-studio"},
                "aliases": ["ali-qwen"],
            },
        },
        "fallback_policy": {"enabled": False, "chains": {}},
    }


# openclaw.json-shaped config for the credential source.
def openclaw_config(with_deepinfra_key: bool) -> dict:
    providers = {
        "custom-api-deepseek-com": {"apiKey": "sk-deepseek-inline-key"},
        "deepinfra": {"baseUrl": "https://api.deepinfra.com/v1/openai"},  # NO apiKey
        "codex-model-studio": {"apiKey": "${MODEL_STUDIO_API_KEY}"},
    }
    if with_deepinfra_key:
        providers["deepinfra"]["apiKey"] = "di-key-present"
    return {
        "models": {"providers": providers},
        "auth": {"profiles": {
            "anthropic:claude-cli": {"provider": "claude-cli", "mode": "oauth"},
            "openai:user": {"provider": "openai", "mode": "oauth"},
        }},
    }


def resolver_without_deepinfra() -> ProviderResolver:
    creds = CredentialSource(
        env={"MODEL_STUDIO_API_KEY": "ms-key"},          # Ali key present, DeepInfra absent
        openclaw_config=openclaw_config(with_deepinfra_key=False),
    )
    return ProviderResolver(config=make_config(), credentials=creds)


def resolver_with_deepinfra() -> ProviderResolver:
    creds = CredentialSource(
        env={"MODEL_STUDIO_API_KEY": "ms-key", "DEEPINFRA_API_KEY": "di-key"},
        openclaw_config=openclaw_config(with_deepinfra_key=True),
    )
    return ProviderResolver(config=make_config(), credentials=creds)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

class TestDeepSeekResolves(unittest.TestCase):
    def test_deepseek_resolves_to_deepseek(self):
        r = resolver_without_deepinfra().resolve("deepseek")
        self.assertTrue(r.available)
        self.assertEqual(r.physical_model, DEEPSEEK_PHYSICAL)
        self.assertEqual(r.auth_result, "ok")
        self.assertIsNone(r.fallback_from)

    def test_deepseek_alias_resolves(self):
        r = resolver_without_deepinfra().resolve("ds")
        self.assertEqual(r.resolved_logical, "deepseek")
        self.assertEqual(r.physical_model, DEEPSEEK_PHYSICAL)


class TestClaudeResolves(unittest.TestCase):
    def test_claude_resolves_to_claude_runtime(self):
        r = resolver_without_deepinfra().resolve("claude")
        self.assertTrue(r.available)
        self.assertEqual(r.physical_model, "anthropic/claude-opus-4-8")
        self.assertEqual(r.runtime, "claude-cli")

    def test_opus_alias_resolves_to_claude(self):
        r = resolver_without_deepinfra().resolve("opus")
        self.assertEqual(r.resolved_logical, "claude")
        self.assertEqual(r.physical_model, "anthropic/claude-opus-4-8")

    def test_sonnet_resolves(self):
        r = resolver_without_deepinfra().resolve("sonnet")
        self.assertTrue(r.available)
        self.assertEqual(r.physical_model, "anthropic/claude-sonnet-4-6")
        self.assertEqual(r.runtime, "claude-cli")


class TestQwenFailsClosed(unittest.TestCase):
    def test_qwen_unavailable_without_deepinfra_key(self):
        with self.assertRaises(ProviderResolutionError) as ctx:
            resolver_without_deepinfra().resolve("qwen")
        ev = ctx.exception.evidence
        self.assertIsInstance(ev, Resolution)
        self.assertFalse(ev.available)
        self.assertEqual(ev.auth_result, "missing_credentials")
        # It must NOT have silently become DeepSeek.
        self.assertNotEqual(ev.physical_model, DEEPSEEK_PHYSICAL)

    def test_qwen_available_when_key_present(self):
        r = resolver_with_deepinfra().resolve("qwen")
        self.assertTrue(r.available)
        self.assertEqual(r.physical_model, "deepinfra/Qwen/Qwen3.6-35B-A3B")

    def test_ali_qwen_is_a_distinct_provider(self):
        # The working Ali Qwen must never be conflated with DeepInfra Qwen.
        r = resolver_without_deepinfra().resolve("qwen-ali")
        self.assertTrue(r.available)
        self.assertEqual(r.provider_id, "codex-model-studio")


class TestNoSilentDeepSeekFallback(unittest.TestCase):
    def test_unknown_provider_raises_not_deepseek(self):
        with self.assertRaises(ProviderResolutionError) as ctx:
            resolver_without_deepinfra().resolve("some-model-that-does-not-exist")
        self.assertEqual(ctx.exception.evidence.auth_result, "unknown_provider")

    def test_unavailable_provider_never_returns_deepseek(self):
        # Sweep every provider; any that is unavailable must RAISE, never return DeepSeek
        # as a substitute for a non-deepseek intent.
        resolver = resolver_without_deepinfra()
        for name in resolver.config["providers"]:
            try:
                r = resolver.resolve(name)
            except ProviderResolutionError as exc:
                # Failing closed is the correct behaviour.
                self.assertFalse(exc.evidence.available)
                continue
            if r.resolved_logical != "deepseek":
                self.assertNotEqual(
                    r.physical_model, DEEPSEEK_PHYSICAL,
                    f"{name} silently resolved to DeepSeek",
                )

    def test_fallback_disabled_by_default(self):
        # Even sweeping, an unavailable qwen must not fall back (policy disabled).
        with self.assertRaises(ProviderResolutionError):
            resolver_without_deepinfra().resolve("qwen", allow_fallback=True)


class TestExplicitRecordedFallback(unittest.TestCase):
    def test_policy_fallback_is_taken_and_recorded(self):
        config = make_config()
        config["fallback_policy"] = {"enabled": True, "chains": {"qwen": ["qwen-ali"]}}
        creds = CredentialSource(
            env={"MODEL_STUDIO_API_KEY": "ms-key"},  # DeepInfra absent, Ali present
            openclaw_config=openclaw_config(with_deepinfra_key=False),
        )
        r = ProviderResolver(config=config, credentials=creds).resolve("qwen")
        self.assertTrue(r.available)
        self.assertEqual(r.resolved_logical, "qwen-ali")
        self.assertEqual(r.fallback_from, "qwen")
        self.assertIsNotNone(r.fallback_reason)

    def test_fallback_to_deepseek_only_if_explicitly_listed(self):
        # DeepSeek may be a fallback ONLY when the policy explicitly lists it,
        # and then it is recorded (never implicit).
        config = make_config()
        config["fallback_policy"] = {"enabled": True, "chains": {"qwen": ["deepseek"]}}
        r = ProviderResolver(config=config, credentials=resolver_without_deepinfra().credentials).resolve("qwen")
        self.assertEqual(r.resolved_logical, "deepseek")
        self.assertEqual(r.fallback_from, "qwen")
        self.assertIn("policy fallback", r.fallback_reason)


class TestSpawnPayload(unittest.TestCase):
    def test_payload_carries_explicit_model(self):
        payload = resolver_without_deepinfra().build_spawn_payload(
            "opus", "do the thing", agent_dir="/x/agent",
        )
        self.assertEqual(payload["model"], "anthropic/claude-opus-4-8")
        self.assertEqual(payload["task"], "do the thing")
        self.assertEqual(payload["agentDir"], "/x/agent")
        self.assertIn("_lisa_resolution", payload)
        self.assertEqual(payload["_lisa_resolution"]["intended_provider"], "opus")

    def test_payload_fails_closed_for_unavailable(self):
        with self.assertRaises(ProviderResolutionError):
            resolver_without_deepinfra().build_spawn_payload("qwen", "task")

    def test_actual_model_match_detection(self):
        r = resolver_without_deepinfra().resolve("claude")
        self.assertIsNone(r.matches_actual)          # unknown before execution
        r.actual_model = r.physical_model
        self.assertTrue(r.matches_actual)
        r.actual_model = DEEPSEEK_PHYSICAL           # drift!
        self.assertFalse(r.matches_actual)


class TestEvidenceRecording(unittest.TestCase):
    def test_evidence_is_written_as_jsonl(self):
        r = resolver_without_deepinfra().resolve("deepseek")
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "evidence.jsonl"
            record_evidence(r, path=log)
            record_evidence(r, path=log)
            lines = log.read_text().strip().splitlines()
            self.assertEqual(len(lines), 2)
            parsed = json.loads(lines[0])
            self.assertEqual(parsed["physical_model"], DEEPSEEK_PHYSICAL)
            self.assertIn("resolved_at", parsed)


class TestRealConfigLoads(unittest.TestCase):
    """Smoke test that the shipped YAML config is well-formed and loadable."""

    def test_registry_yaml_parses_and_has_required_providers(self):
        resolver = ProviderResolver(credentials=resolver_without_deepinfra().credentials)
        providers = resolver.config.get("providers", {})
        for required in ("deepseek", "claude", "sonnet", "qwen"):
            self.assertIn(required, providers, f"missing provider {required}")
        # aliases index built
        self.assertEqual(resolver.normalise("opus"), "claude")


if __name__ == "__main__":
    unittest.main(verbosity=2)
