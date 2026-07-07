"""Proof-of-work tests for LisaOS provider resolution (v2 — disambiguated).

Validates the execution-layer fix from reports/lisa/EXECUTION_LAYER_AUDIT.md plus the
S024 provider disambiguation:

  * DeepSeek resolves to the DeepSeek physical model.
  * claude-opus / opus resolve to the Claude Opus runtime + model.
  * claude-sonnet resolves to the Claude Sonnet runtime + model.
  * qwen-deepinfra fails CLOSED when no DeepInfra key exists; AVAILABLE when it does.
  * qwen-alibaba is a DISTINCT provider (never conflated with DeepInfra).
  * Bare `qwen` is NOT a provider -> deterministic, unambiguous identities only.
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
# Shared fixtures: a config mirroring registry/provider_resolution.yml (v2) and
# two credential scenarios (with and without a DeepInfra key).
# --------------------------------------------------------------------------- #

def make_config() -> dict:
    return {
        "version": 2,
        "providers": {
            "deepseek": {
                "physical_model": DEEPSEEK_PHYSICAL,
                "runtime": "openclaw",
                "provider_id": "custom-api-deepseek-com",
                "credential": {"type": "inline_api_key",
                               "openclaw_provider": "custom-api-deepseek-com"},
                "aliases": ["deepseek-reasoner", "ds"],
            },
            "claude-opus": {
                "physical_model": "anthropic/claude-opus-4-8",
                "runtime": "claude-cli",
                "provider_id": "anthropic",
                "credential": {"type": "oauth", "provider": "claude-cli"},
                "aliases": ["opus", "claude", "claude-opus-4-8"],
            },
            "claude-sonnet": {
                "physical_model": "anthropic/claude-sonnet-4-6",
                "runtime": "claude-cli",
                "provider_id": "anthropic",
                "credential": {"type": "oauth", "provider": "claude-cli"},
                "aliases": ["sonnet", "claude-sonnet-4-6"],
            },
            "qwen-deepinfra": {
                "physical_model": "deepinfra/Qwen/Qwen3.6-35B-A3B",
                "runtime": "openclaw",
                "provider_id": "deepinfra",
                "credential": {"type": "api_key", "env": "DEEPINFRA_API_KEY",
                               "openclaw_provider": "deepinfra"},
                "aliases": ["deepinfra-qwen"],
            },
            # Codex = OpenAI. There is NO codex-model-studio provider anywhere
            # (Alibaba Qwen removed in the V3 registry cleanup), so `codex` is
            # unambiguously OpenAI, never the mis-named Qwen backend.
            "codex": {
                "physical_model": "openai/gpt-5.5",
                "runtime": "codex",
                "provider_id": "openai",
                "credential": {"type": "oauth", "provider": "openai"},
                "aliases": ["openai-codex"],
            },
            # qwen-alibaba (codex-model-studio/qwen3.7-plus) is intentionally ABSENT:
            # removed from the approved workforce. See tests below asserting removal.
        },
        "fallback_policy": {"enabled": False, "chains": {}},
    }


# openclaw.json-shaped config for the credential source.
def openclaw_config(with_deepinfra_key: bool) -> dict:
    providers = {
        "custom-api-deepseek-com": {"apiKey": "sk-deepseek-inline-key"},
        # Mirrors the real fix: deepinfra apiKey is a ${ENV} placeholder.
        "deepinfra": {"baseUrl": "https://api.deepinfra.com/v1/openai",
                      "apiKey": "${DEEPINFRA_API_KEY}"},
        "codex-model-studio": {"apiKey": "${MODEL_STUDIO_API_KEY}"},
    }
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
    def test_claude_opus_resolves(self):
        r = resolver_without_deepinfra().resolve("claude-opus")
        self.assertTrue(r.available)
        self.assertEqual(r.physical_model, "anthropic/claude-opus-4-8")
        self.assertEqual(r.runtime, "claude-cli")

    def test_opus_alias_resolves_to_claude_opus(self):
        r = resolver_without_deepinfra().resolve("opus")
        self.assertEqual(r.resolved_logical, "claude-opus")
        self.assertEqual(r.physical_model, "anthropic/claude-opus-4-8")

    def test_claude_sonnet_resolves(self):
        r = resolver_without_deepinfra().resolve("claude-sonnet")
        self.assertTrue(r.available)
        self.assertEqual(r.physical_model, "anthropic/claude-sonnet-4-6")
        self.assertEqual(r.runtime, "claude-cli")


class TestQwenDisambiguation(unittest.TestCase):
    def test_bare_qwen_is_not_a_provider(self):
        # The whole point of the clean-up: 'qwen' must NOT resolve to anything.
        resolver = resolver_with_deepinfra()
        self.assertIsNone(resolver.normalise("qwen"))
        with self.assertRaises(ProviderResolutionError) as ctx:
            resolver.resolve("qwen")
        self.assertEqual(ctx.exception.evidence.auth_result, "unknown_provider")

    def test_qwen_deepinfra_unavailable_without_key(self):
        with self.assertRaises(ProviderResolutionError) as ctx:
            resolver_without_deepinfra().resolve("qwen-deepinfra")
        ev = ctx.exception.evidence
        self.assertIsInstance(ev, Resolution)
        self.assertFalse(ev.available)
        self.assertEqual(ev.auth_result, "missing_credentials")
        self.assertNotEqual(ev.physical_model, DEEPSEEK_PHYSICAL)

    def test_qwen_deepinfra_available_with_key(self):
        r = resolver_with_deepinfra().resolve("qwen-deepinfra")
        self.assertTrue(r.available)
        self.assertEqual(r.physical_model, "deepinfra/Qwen/Qwen3.6-35B-A3B")
        self.assertEqual(r.provider_id, "deepinfra")

    def test_qwen_alibaba_is_removed(self):
        # Cleanup: the Alibaba Qwen provider and ALL its aliases must be gone.
        resolver = resolver_with_deepinfra()
        for name in ("qwen-alibaba", "ali-qwen", "qwen-modelstudio", "alibaba-qwen"):
            self.assertIsNone(resolver.normalise(name), f"{name} should not resolve")
            with self.assertRaises(ProviderResolutionError) as ctx:
                resolver.resolve(name)
            self.assertEqual(ctx.exception.evidence.auth_result, "unknown_provider")

    def test_single_qwen_backend_only(self):
        # There is exactly one Qwen provider, and it is DeepInfra.
        providers = resolver_with_deepinfra().config["providers"]
        qwen_like = [p for p in providers if "qwen" in p]
        self.assertEqual(qwen_like, ["qwen-deepinfra"])

    def test_no_registry_entry_references_codex_model_studio(self):
        # The mis-named Alibaba provider must not be referenced anywhere ->
        # eliminates the Codex/Qwen identity ambiguity.
        providers = resolver_with_deepinfra().config["providers"]
        for name, spec in providers.items():
            self.assertNotIn("codex-model-studio", spec.get("physical_model", ""),
                             f"{name} still references codex-model-studio")
            self.assertNotEqual(spec.get("provider_id"), "codex-model-studio",
                                f"{name} still uses provider_id codex-model-studio")

    def test_codex_is_openai_not_qwen(self):
        r = resolver_with_deepinfra().resolve("codex")
        self.assertEqual(r.provider_id, "openai")
        self.assertNotIn("qwen", r.physical_model.lower())
        self.assertNotEqual(r.provider_id, "codex-model-studio")


class TestNoSilentDeepSeekFallback(unittest.TestCase):
    def test_unknown_provider_raises_not_deepseek(self):
        with self.assertRaises(ProviderResolutionError) as ctx:
            resolver_without_deepinfra().resolve("some-model-that-does-not-exist")
        self.assertEqual(ctx.exception.evidence.auth_result, "unknown_provider")

    def test_unavailable_provider_never_returns_deepseek(self):
        resolver = resolver_without_deepinfra()
        for name in resolver.config["providers"]:
            try:
                r = resolver.resolve(name)
            except ProviderResolutionError as exc:
                self.assertFalse(exc.evidence.available)
                continue
            if r.resolved_logical != "deepseek":
                self.assertNotEqual(
                    r.physical_model, DEEPSEEK_PHYSICAL,
                    f"{name} silently resolved to DeepSeek",
                )

    def test_fallback_disabled_by_default(self):
        with self.assertRaises(ProviderResolutionError):
            resolver_without_deepinfra().resolve("qwen-deepinfra", allow_fallback=True)


class TestExplicitRecordedFallback(unittest.TestCase):
    def test_policy_fallback_is_taken_and_recorded(self):
        # Explicit, recorded fallback still works via an approved provider
        # (claude-sonnet), now that the Alibaba backend is removed.
        config = make_config()
        config["fallback_policy"] = {"enabled": True,
                                     "chains": {"qwen-deepinfra": ["claude-sonnet"]}}
        creds = CredentialSource(
            env={},  # DeepInfra absent -> chain fallback engages
            openclaw_config=openclaw_config(with_deepinfra_key=False),
        )
        r = ProviderResolver(config=config, credentials=creds).resolve("qwen-deepinfra")
        self.assertTrue(r.available)
        self.assertEqual(r.resolved_logical, "claude-sonnet")
        self.assertEqual(r.fallback_from, "qwen-deepinfra")
        self.assertIsNotNone(r.fallback_reason)

    def test_fallback_to_deepseek_only_if_explicitly_listed(self):
        config = make_config()
        config["fallback_policy"] = {"enabled": True,
                                     "chains": {"qwen-deepinfra": ["deepseek"]}}
        r = ProviderResolver(
            config=config,
            credentials=resolver_without_deepinfra().credentials,
        ).resolve("qwen-deepinfra")
        self.assertEqual(r.resolved_logical, "deepseek")
        self.assertEqual(r.fallback_from, "qwen-deepinfra")
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
        self.assertEqual(payload["_lisa_resolution"]["resolved_logical"], "claude-opus")

    def test_payload_fails_closed_for_unavailable(self):
        with self.assertRaises(ProviderResolutionError):
            resolver_without_deepinfra().build_spawn_payload("qwen-deepinfra", "task")

    def test_actual_model_match_detection(self):
        r = resolver_without_deepinfra().resolve("claude-opus")
        self.assertIsNone(r.matches_actual)
        r.actual_model = r.physical_model
        self.assertTrue(r.matches_actual)
        r.actual_model = DEEPSEEK_PHYSICAL
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
    """Smoke test that the shipped v2 YAML config is well-formed and disambiguated."""

    def test_registry_yaml_parses_and_is_disambiguated(self):
        resolver = ProviderResolver(credentials=resolver_without_deepinfra().credentials)
        providers = resolver.config.get("providers", {})
        for required in ("deepseek", "claude-opus", "claude-sonnet",
                         "codex", "qwen-deepinfra"):
            self.assertIn(required, providers, f"missing provider {required}")
        # Determinism: bare 'qwen' is not a canonical provider and not an alias.
        self.assertNotIn("qwen", providers)
        self.assertIsNone(resolver.normalise("qwen"))
        # Friendly aliases still resolve deterministically to ONE backend.
        self.assertEqual(resolver.normalise("opus"), "claude-opus")
        self.assertEqual(resolver.normalise("deepinfra-qwen"), "qwen-deepinfra")

    def test_shipped_registry_has_no_alibaba_and_no_codex_model_studio(self):
        # V3 cleanup on the REAL shipped YAML: Alibaba Qwen fully removed,
        # nothing references codex-model-studio -> no Codex/Qwen ambiguity.
        resolver = ProviderResolver(credentials=resolver_without_deepinfra().credentials)
        providers = resolver.config.get("providers", {})
        self.assertNotIn("qwen-alibaba", providers)
        for alias in ("ali-qwen", "qwen-modelstudio", "alibaba-qwen"):
            self.assertIsNone(resolver.normalise(alias), f"stale alias {alias} present")
        qwen_like = sorted(p for p in providers if "qwen" in p)
        self.assertEqual(qwen_like, ["qwen-deepinfra"])
        for name, spec in providers.items():
            self.assertNotIn("codex-model-studio", spec.get("physical_model", ""))
            self.assertNotEqual(spec.get("provider_id"), "codex-model-studio")
        # Codex on the shipped registry is OpenAI.
        self.assertEqual(providers["codex"]["provider_id"], "openai")

    def test_phase0_haiku_and_glm_providers(self):
        # Phase 0.4 / 0.6 additions on the REAL shipped registry.
        resolver = ProviderResolver(credentials=resolver_without_deepinfra().credentials)
        providers = resolver.config.get("providers", {})
        # Haiku: subscription microtask worker.
        self.assertIn("claude-haiku", providers)
        self.assertEqual(providers["claude-haiku"]["physical_model"],
                         "anthropic/claude-haiku-4-5")
        self.assertEqual(providers["claude-haiku"]["runtime"], "claude-cli")
        self.assertEqual(resolver.normalise("haiku"), "claude-haiku")
        # GLM: PROBATIONARY, not critical-routable.
        for name, model in (("glm", "zai/glm-5.2"), ("glm-turbo", "zai/glm-5-turbo")):
            self.assertIn(name, providers)
            self.assertEqual(providers[name]["physical_model"], model)
            self.assertEqual(providers[name]["provider_id"], "zai")
            self.assertTrue(providers[name].get("probation") is True,
                            f"{name} must be flagged probation")
            self.assertFalse(providers[name].get("critical_routing", False),
                             f"{name} must not be critical-routable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
