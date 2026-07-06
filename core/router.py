from engines.claude import ClaudeEngine
from engines.codex import CodexEngine
from engines.gpt import GPTEngine
from engines.openclaw import OpenClawEngine

from core.provider_resolver import (
    ProviderResolver,
    ProviderResolutionError,
    Resolution,
    get_resolver,
)

ENGINES = {
    "claude": ClaudeEngine(),
    "codex": CodexEngine(),
    "gpt": GPTEngine(),
    "openclaw": OpenClawEngine(),
}

def choose_engine(skill):
    preferred = skill.get("preferred_engine", "codex")
    if preferred == "auto":
        return ENGINES["codex"]
    return ENGINES.get(preferred, ENGINES["codex"])


# --------------------------------------------------------------------------- #
# Provider resolution (execution-layer fix -- see EXECUTION_LAYER_AUDIT.md).
#
# The functions below bind a *logical* provider (deepseek, claude, opus, sonnet,
# qwen, ...) to a *physical* OpenClaw model and produce the explicit `model` for a
# subagent spawn payload. They FAIL CLOSED: an unavailable provider raises rather
# than silently defaulting to DeepSeek.
# --------------------------------------------------------------------------- #

def resolve_provider(logical_provider: str, *, resolver: ProviderResolver | None = None) -> Resolution:
    """Resolve a logical provider to a physical model, or raise (fail closed)."""
    return (resolver or get_resolver()).resolve(logical_provider)


def spawn_payload_for(
    logical_provider: str,
    task: str,
    *,
    resolver: ProviderResolver | None = None,
    **kwargs,
) -> dict:
    """Build an OpenClaw spawn payload with an explicit, resolved `model`.

    Raises ProviderResolutionError before any spawn if the provider is unknown,
    unavailable, or unauthenticated -- so a work packet is never dispatched onto
    the wrong engine or silently onto DeepSeek.
    """
    return (resolver or get_resolver()).build_spawn_payload(logical_provider, task, **kwargs)


__all__ = [
    "ENGINES",
    "choose_engine",
    "resolve_provider",
    "spawn_payload_for",
    "ProviderResolutionError",
]
