"""LisaOS provider resolution.

Turns a *logical* provider name (claude, opus, sonnet, deepseek, qwen, ...) into a
*physical* OpenClaw model + runtime, verifies the provider is actually credentialed,
and produces the explicit `model` field that MUST be written into a subagent spawn
payload.

This is the fix for reports/lisa/EXECUTION_LAYER_AUDIT.md:
  * Defect A -- routing decisions were never bound to the spawn `model`.
  * Defect B -- spawns silently inherited the global DeepSeek default.
  * Defect C -- DeepInfra/Qwen was mislabelled as usable despite having no key.

Design guarantees:
  * FAIL CLOSED. An unknown, unavailable, or unauthenticated provider raises
    ProviderResolutionError. The resolver NEVER silently returns DeepSeek.
  * Fallback only when the policy explicitly enables it, and every fallback is
    recorded in the resolution evidence.
  * Every resolution is evidence-bearing: intended provider, resolved physical
    model/runtime, availability, auth result, and any fallback reason.

The module has no third-party dependencies beyond PyYAML (already used by
core.registry) and does not make any network/provider calls, so it is safe to run
and to unit-test without spending money.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
RESOLUTION_CONFIG = LISA_BASE / "registry" / "provider_resolution.yml"

OPENCLAW_HOME = Path(os.environ.get("OPENCLAW_HOME", Path.home() / ".openclaw"))
OPENCLAW_CONFIG = OPENCLAW_HOME / "openclaw.json"
OPENCLAW_ENV = OPENCLAW_HOME / ".env"

EVIDENCE_LOG = LISA_BASE / "reports" / "lisa" / "provider_resolution_evidence.jsonl"

# The one model we must never silently substitute in (audit Defect B).
_DEEPSEEK_PHYSICAL = "custom-api-deepseek-com/deepseek-reasoner"


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class ProviderResolutionError(Exception):
    """Raised when a logical provider cannot be safely resolved.

    Carries the partial evidence so callers can record *why* resolution failed
    instead of guessing or falling back.
    """

    def __init__(self, message: str, evidence: "Resolution | None" = None):
        super().__init__(message)
        self.evidence = evidence


# --------------------------------------------------------------------------- #
# Resolution record (evidence)
# --------------------------------------------------------------------------- #

@dataclass
class Resolution:
    """The evidence-bearing result of resolving one logical provider."""

    intended_provider: str            # what the caller asked for (raw, pre-alias)
    resolved_logical: str | None      # canonical logical name after alias normalisation
    physical_model: str | None        # concrete OpenClaw model id for the spawn payload
    runtime: str | None               # OpenClaw runtime id (claude-cli, codex, openclaw)
    provider_id: str | None           # provider block id in openclaw.json
    available: bool                   # credentialed + authenticated?
    auth_result: str                  # ok | missing_credentials | unknown_profile | unknown_provider
    fallback_from: str | None = None  # set only when an explicit policy fallback was taken
    fallback_reason: str | None = None
    actual_model: str | None = None   # filled in post-execution by the dispatcher
    resolved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def matches_actual(self) -> bool | None:
        """True/False once actual_model is known; None before execution."""
        if self.actual_model is None:
            return None
        return self.actual_model == self.physical_model


# --------------------------------------------------------------------------- #
# Credential detection (reads real OpenClaw config; injectable for tests)
# --------------------------------------------------------------------------- #

def _looks_like_placeholder(value: str) -> bool:
    v = value.strip()
    return v.startswith("${") and v.endswith("}")


def _placeholder_var(value: str) -> str | None:
    v = value.strip()
    if _looks_like_placeholder(v):
        return v[2:-1]
    return None


class CredentialSource:
    """Answers "is this provider actually credentialed?" from real config.

    All inputs are injectable so unit tests can construct hermetic scenarios
    (no filesystem, no env, no network, no spend).
    """

    def __init__(
        self,
        env: dict[str, str] | None = None,
        openclaw_config: dict[str, Any] | None = None,
    ):
        self._env = dict(env) if env is not None else self._load_env()
        self._config = openclaw_config if openclaw_config is not None else self._load_config()

    # ---- loaders (only used when nothing is injected) ----------------------

    @staticmethod
    def _load_env() -> dict[str, str]:
        merged: dict[str, str] = {}
        # 1) ~/.openclaw/.env (KEY=VALUE lines)
        if OPENCLAW_ENV.is_file():
            for line in OPENCLAW_ENV.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                merged[key.strip()] = val.strip().strip('"').strip("'")
        # 2) process environment wins over file
        merged.update(os.environ)
        return merged

    @staticmethod
    def _load_config() -> dict[str, Any]:
        if OPENCLAW_CONFIG.is_file():
            try:
                return json.loads(OPENCLAW_CONFIG.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    # ---- checks ------------------------------------------------------------

    def has_env(self, name: str) -> bool:
        val = self._env.get(name)
        return bool(val and val.strip())

    def has_inline_key(self, openclaw_provider: str | None) -> bool:
        if not openclaw_provider:
            return False
        providers = (self._config.get("models", {}) or {}).get("providers", {}) or {}
        block = providers.get(openclaw_provider, {}) or {}
        api_key = block.get("apiKey")
        if not api_key or not str(api_key).strip():
            return False
        var = _placeholder_var(str(api_key))
        if var is not None:
            # ${ENV} inline key is only real if the env var is actually set.
            return self.has_env(var)
        return True

    def has_oauth(self, provider: str | None) -> bool:
        if not provider:
            return False
        profiles = (self._config.get("auth", {}) or {}).get("profiles", {}) or {}
        for prof in profiles.values():
            if (prof or {}).get("provider") == provider and (prof or {}).get("mode") == "oauth":
                return True
        return False

    # ---- top-level availability decision -----------------------------------

    def evaluate(self, credential: dict[str, Any]) -> str:
        """Return an auth_result string for a provider's credential descriptor."""
        ctype = credential.get("type")
        if ctype == "oauth":
            return "ok" if self.has_oauth(credential.get("provider")) else "unknown_profile"
        if ctype == "inline_api_key":
            return "ok" if self.has_inline_key(credential.get("openclaw_provider")) else "missing_credentials"
        if ctype == "api_key":
            if credential.get("env") and self.has_env(credential["env"]):
                return "ok"
            if self.has_inline_key(credential.get("openclaw_provider")):
                return "ok"
            return "missing_credentials"
        return "unknown_credential_type"


# --------------------------------------------------------------------------- #
# Resolver
# --------------------------------------------------------------------------- #

class ProviderResolver:
    """Resolves logical provider names to physical OpenClaw models, fail-closed."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        credentials: CredentialSource | None = None,
    ):
        self.config = config if config is not None else self._load_config()
        self.credentials = credentials if credentials is not None else CredentialSource()
        self._alias_index = self._build_alias_index()

    # ---- construction ------------------------------------------------------

    @staticmethod
    def _load_config() -> dict[str, Any]:
        if not RESOLUTION_CONFIG.is_file():
            raise ProviderResolutionError(
                f"Provider resolution config missing: {RESOLUTION_CONFIG}"
            )
        return yaml.safe_load(RESOLUTION_CONFIG.read_text()) or {}

    def _build_alias_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for canonical, spec in (self.config.get("providers", {}) or {}).items():
            index[canonical.lower()] = canonical
            for alias in (spec.get("aliases", []) or []):
                index[str(alias).lower()] = canonical
        return index

    # ---- public API --------------------------------------------------------

    def normalise(self, logical_provider: str) -> str | None:
        if not logical_provider:
            return None
        return self._alias_index.get(logical_provider.strip().lower())

    def resolve(self, logical_provider: str, *, allow_fallback: bool = True) -> Resolution:
        """Resolve a logical provider to a physical model, or raise (fail closed)."""
        canonical = self.normalise(logical_provider)

        if canonical is None:
            evidence = Resolution(
                intended_provider=logical_provider,
                resolved_logical=None,
                physical_model=None,
                runtime=None,
                provider_id=None,
                available=False,
                auth_result="unknown_provider",
            )
            raise ProviderResolutionError(
                f"Unknown logical provider '{logical_provider}'. "
                f"Refusing to guess or fall back to DeepSeek.",
                evidence,
            )

        spec = self.config["providers"][canonical]
        credential = spec.get("credential", {}) or {}
        auth_result = self.credentials.evaluate(credential)
        available = auth_result == "ok"

        resolution = Resolution(
            intended_provider=logical_provider,
            resolved_logical=canonical,
            physical_model=spec.get("physical_model"),
            runtime=spec.get("runtime"),
            provider_id=spec.get("provider_id"),
            available=available,
            auth_result=auth_result,
        )

        if available:
            return resolution

        # Unavailable -> try an explicit, recorded policy fallback, else fail closed.
        if allow_fallback:
            fb = self._try_fallback(canonical, reason=auth_result)
            if fb is not None:
                return fb

        raise ProviderResolutionError(
            f"Provider '{logical_provider}' (-> {canonical}, "
            f"{spec.get('physical_model')}) is unavailable: {auth_result}. "
            f"Failing closed; no silent DeepSeek fallback.",
            resolution,
        )

    def build_spawn_payload(
        self,
        logical_provider: str,
        task: str,
        *,
        agent_dir: str | None = None,
        spawn_mode: str = "run",
        cleanup: str = "keep",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build an OpenClaw subagent spawn payload with an EXPLICIT model.

        Raises ProviderResolutionError before any spawn if the provider cannot be
        resolved -- so a work packet can never be dispatched onto the wrong engine
        or silently onto DeepSeek.
        """
        resolution = self.resolve(logical_provider)
        payload: dict[str, Any] = {
            "task": task,
            "model": resolution.physical_model,   # <-- the fix: explicit, resolved
            "spawnMode": spawn_mode,
            "cleanup": cleanup,
            "_lisa_resolution": resolution.to_dict(),
        }
        if agent_dir:
            payload["agentDir"] = agent_dir
        if extra:
            payload.update(extra)
        return payload

    # ---- fallback (explicit + recorded only) -------------------------------

    def _try_fallback(self, canonical: str, *, reason: str) -> Resolution | None:
        policy = self.config.get("fallback_policy", {}) or {}
        if not policy.get("enabled"):
            return None
        chain = (policy.get("chains", {}) or {}).get(canonical, []) or []
        for candidate in chain:
            cand_canonical = self.normalise(candidate)
            if cand_canonical is None:
                continue
            spec = self.config["providers"][cand_canonical]
            credential = spec.get("credential", {}) or {}
            auth_result = self.credentials.evaluate(credential)
            if auth_result == "ok":
                return Resolution(
                    intended_provider=canonical,
                    resolved_logical=cand_canonical,
                    physical_model=spec.get("physical_model"),
                    runtime=spec.get("runtime"),
                    provider_id=spec.get("provider_id"),
                    available=True,
                    auth_result=auth_result,
                    fallback_from=canonical,
                    fallback_reason=f"{canonical} unavailable ({reason}); "
                                    f"policy fallback -> {cand_canonical}",
                )
        return None


# --------------------------------------------------------------------------- #
# Evidence recording
# --------------------------------------------------------------------------- #

def record_evidence(resolution: Resolution, *, path: Path | None = None) -> Path:
    """Append one resolution evidence record as JSONL. Returns the log path."""
    target = path or EVIDENCE_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(resolution.to_dict()) + "\n")
    return target


# --------------------------------------------------------------------------- #
# Module-level convenience
# --------------------------------------------------------------------------- #

_default_resolver: ProviderResolver | None = None


def get_resolver() -> ProviderResolver:
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = ProviderResolver()
    return _default_resolver


def resolve_provider(logical_provider: str) -> Resolution:
    return get_resolver().resolve(logical_provider)
