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
from core.workforce_resolver import (
    WorkforceResolver,
    WorkforceResolutionError,
    WorkPackage,
    WorkAssignment,
)

# ===========================================================================
# LEGACY ROUTING LAYER (superseded — kept for compatibility).
#
# `ENGINES` + `choose_engine` are the original engine-preference routing and
# the runtime/cost_tier abstraction (registry/runtimes.yml, registry/agents.yml).
# They are SUPERSEDED by the Workforce layer below (Phase 1) and will be retired
# in a later phase. Do not build new routing on this path.
# ===========================================================================

ENGINES = {
    "claude": ClaudeEngine(),
    "codex": CodexEngine(),
    "gpt": GPTEngine(),
    "openclaw": OpenClawEngine(),
}

def choose_engine(skill):
    """LEGACY. Engine-preference routing. Superseded by resolve_work_package()."""
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


# --------------------------------------------------------------------------- #
# WORKFORCE ROUTING LAYER (Phase 1 — the new, employee-based path).
#
# This is the SUPERSEDING layer. Work is routed to an EMPLOYEE by capability,
# then the employee's preferred model is resolved to a physical runtime via the
# fail-closed ProviderResolver. The MAIN RUNTIME does not choose worker models —
# this resolver does (every WorkAssignment records routed_by="workforce_resolver").
#
# Migration boundary: legacy callers use resolve_provider()/choose_engine();
# new callers use resolve_work_package(). Both coexist until the legacy path is
# retired in a later phase.
# --------------------------------------------------------------------------- #

_default_workforce: WorkforceResolver | None = None


def get_workforce_resolver() -> WorkforceResolver:
    global _default_workforce
    if _default_workforce is None:
        _default_workforce = WorkforceResolver()
    return _default_workforce


def resolve_work_package(
    work_package: WorkPackage,
    *,
    workforce: WorkforceResolver | None = None,
) -> WorkAssignment:
    """Staff a WorkPackage to an employee + physical runtime, fail-closed.

    Raises WorkforceResolutionError if no capable employee or no available,
    policy-compliant model exists — never a silent DeepSeek fallback.
    """
    return (workforce or get_workforce_resolver()).resolve(work_package)


__all__ = [
    # legacy (superseded)
    "ENGINES",
    "choose_engine",
    # provider layer
    "resolve_provider",
    "spawn_payload_for",
    "ProviderResolutionError",
    "Resolution",
    # workforce layer (Phase 1)
    "resolve_work_package",
    "get_workforce_resolver",
    "WorkPackage",
    "WorkAssignment",
    "WorkforceResolutionError",
]
