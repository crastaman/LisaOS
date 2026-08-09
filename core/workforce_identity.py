"""LisaOS Workforce Identity (CWO-001).

Canonical worker identity resolution -- the actual model identities Roshan's
cloud workforce uses (Sol, Terra, Luna, Opus, Sonnet, Haiku, deepseek-main),
with a backwards-compatible legacy alias map.

Design guarantees:
  * CANONICAL. Worker ids are the actual model identities; aliases are a
    separate, explicit map. Aliases never mutate canonical ids.
  * FAIL SAFE ON UNKNOWN. An unknown worker name raises WorkforceIdentityError
    rather than silently mapping to a default worker (never accidentally
    route to the wrong model identity).
  * SEPARATION OF CONCEPTS. worker / provider / access_mode / cost_model are
    distinct fields, never conflated.
  * SUBSCRIPTION vs METERED. cost_model distinguishes subscription_capacity
    (already-paid; optimize useful work per allowance) from
    metered_api_capacity (every token has marginal cost; optimize token
    expenditure).
  * DEEPSEEK PRO GUARD. is_deepseek_pro() is always False unless a worker
    explicitly named "deepseek-pro" is added to the registry. The mission
    forbids onboarding DeepSeek Pro; the guard makes accidental treatment as
    available impossible.
  * FUTURE LOCAL. cost_model=local / capacity_model=hardware is schema-
    supported but no local worker is onboarded (onboarded: false).

This module has no third-party deps beyond PyYAML and makes no network/
provider calls -- safe to unit-test without spending money.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
IDENTITY_REGISTRY = LISA_BASE / "registry" / "workforce_identity.yml"

# Cost models (mission: at minimum distinguish subscription vs metered).
SUBSCRIPTION_CAPACITY = "subscription_capacity"
METERED_API_CAPACITY = "metered_api_capacity"
LOCAL_CAPACITY = "local"          # future only

VALID_COST_MODELS = (SUBSCRIPTION_CAPACITY, METERED_API_CAPACITY, LOCAL_CAPACITY)

# Worker tiers.
TIER_PREMIUM = "premium"
TIER_MID = "mid"
TIER_FAST = "fast"
TIER_MAIN = "main"

VALID_TIERS = (TIER_PREMIUM, TIER_MID, TIER_FAST, TIER_MAIN)

# The DeepSeek Pro guard: the string that would name it if ever (wrongly)
# onboarded. is_deepseek_pro() returns False unless this exact worker id
# exists in the registry AND is explicitly marked available.
DEEPSEEK_PRO_IDS = ("deepseek-pro", "deepseek-pro-reasoner", "deepseek-pro-max")


class WorkforceIdentityError(Exception):
    """Raised when a worker name cannot be resolved to a canonical identity."""


@dataclass
class WorkerIdentity:
    """One canonical worker (an actual model identity)."""

    id: str
    family: str
    model: str                    # logical provider name (provider_resolution.yml)
    tier: str
    access: str                   # subscription | metered | local
    cost_model: str               # subscription_capacity | metered_api_capacity | local
    provider: str = ""
    specialization: str = ""
    avoid: list[str] = field(default_factory=list)
    cheapest_for: list[str] = field(default_factory=list)
    onboarded: bool = True        # False => schema-only future capacity

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "family": self.family,
            "model": self.model,
            "tier": self.tier,
            "access": self.access,
            "cost_model": self.cost_model,
            "provider": self.provider,
            "specialization": self.specialization,
            "avoid": self.avoid,
            "cheapest_for": self.cheapest_for,
            "onboarded": self.onboarded,
        }

    @property
    def is_subscription(self) -> bool:
        return self.cost_model == SUBSCRIPTION_CAPACITY

    @property
    def is_metered(self) -> bool:
        return self.cost_model == METERED_API_CAPACITY

    @property
    def is_local(self) -> bool:
        return self.cost_model == LOCAL_CAPACITY

    @property
    def is_premium(self) -> bool:
        return self.tier == TIER_PREMIUM

    @property
    def is_fast(self) -> bool:
        return self.tier == TIER_FAST


class WorkforceIdentityRegistry:
    """Loads + validates registry/workforce_identity.yml."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config if config is not None else self._load_config()
        self.workers: dict[str, WorkerIdentity] = self._build_workers()
        self.aliases: dict[str, str] = self._build_aliases()

    @staticmethod
    def _load_config() -> dict[str, Any]:
        if not IDENTITY_REGISTRY.is_file():
            raise WorkforceIdentityError(
                f"Workforce identity registry missing: {IDENTITY_REGISTRY}")
        return yaml.safe_load(IDENTITY_REGISTRY.read_text()) or {}

    def _build_workers(self) -> dict[str, WorkerIdentity]:
        raw = self.config.get("workers", {}) or {}
        if not raw:
            raise WorkforceIdentityError("workforce identity registry has no workers")
        out: dict[str, WorkerIdentity] = {}
        for wid, spec in raw.items():
            spec = spec or {}
            out[wid] = WorkerIdentity(
                id=wid,
                family=spec.get("family", ""),
                model=spec.get("model", ""),
                tier=spec.get("tier", TIER_MID),
                access=spec.get("access", "subscription"),
                cost_model=spec.get("cost_model", SUBSCRIPTION_CAPACITY),
                provider=spec.get("provider", ""),
                specialization=spec.get("specialization", ""),
                avoid=list(spec.get("avoid", []) or []),
                cheapest_for=list(spec.get("cheapest_for", []) or []),
                onboarded=bool(spec.get("onboarded", True)),
            )
        return out

    def _build_aliases(self) -> dict[str, str]:
        raw = self.config.get("aliases", {}) or {}
        out: dict[str, str] = {}
        for alias, target in raw.items():
            out[alias.lower()] = target.lower()
        return out

    # ---- validation --------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of problems; empty means valid."""
        problems: list[str] = []
        raw = self.config.get("workers", {}) or {}
        seen = set()
        for wid, spec in raw.items():
            if wid in seen:
                problems.append(f"duplicate worker id: {wid}")
            seen.add(wid)
            spec = spec or {}
            if not spec.get("model"):
                problems.append(f"{wid}: missing model (logical provider name)")
            tier = spec.get("tier")
            if tier not in VALID_TIERS:
                problems.append(f"{wid}: unknown tier {tier!r}")
            cm = spec.get("cost_model")
            if cm not in VALID_COST_MODELS:
                problems.append(f"{wid}: unknown cost_model {cm!r}")
            if not spec.get("family"):
                problems.append(f"{wid}: missing family")
            if not spec.get("access"):
                problems.append(f"{wid}: missing access")
        # alias targets must exist
        for alias, target in self.aliases.items():
            if target not in self.workers:
                problems.append(f"alias {alias!r} -> unknown worker {target!r}")
        return problems

    # ---- resolution --------------------------------------------------------

    def normalise(self, worker_name: str) -> str | None:
        """Resolve any worker name/alias to the canonical worker id.

        Case-insensitive. Returns None if unknown (callers may want to
        distinguish "unknown" from "error"; the strict `resolve()` raises).
        """
        if not worker_name:
            return None
        name = worker_name.strip().lower()
        if name in self.workers:
            return name
        return self.aliases.get(name)

    def resolve(self, worker_name: str) -> WorkerIdentity:
        """Strict resolution: canonical worker or raise (fail safe)."""
        canonical = self.normalise(worker_name)
        if canonical is None:
            raise WorkforceIdentityError(
                f"unknown worker identity {worker_name!r} -- no canonical worker "
                f"and no alias mapping. Known workers: "
                f"{', '.join(sorted(self.workers))}")
        worker = self.workers[canonical]
        if not worker.onboarded:
            raise WorkforceIdentityError(
                f"worker {canonical!r} is schema-only future capacity "
                f"(onboarded: false) -- not available for dispatch")
        return worker

    def get(self, worker_name: str) -> WorkerIdentity | None:
        """Lenient lookup: canonical worker or None (no raise)."""
        canonical = self.normalise(worker_name)
        if canonical is None:
            return None
        return self.workers.get(canonical)

    def worker_capacity(self, worker_name: str) -> str | None:
        """Cost model for a worker: subscription_capacity | metered_api_capacity
        | local. None if unknown (graceful degradation -- never invented)."""
        worker = self.get(worker_name)
        if worker is None:
            return None
        return worker.cost_model

    def is_subscription(self, worker_name: str) -> bool | None:
        worker = self.get(worker_name)
        if worker is None:
            return None
        return worker.is_subscription

    def is_deepseek_pro(self, worker_name: str) -> bool:
        """Guard: True ONLY if a worker explicitly named as DeepSeek Pro exists
        in the registry AND is onboarded. Currently always False (DeepSeek Pro
        is not onboarded per mission)."""
        canonical = self.normalise(worker_name)
        if canonical is None:
            return False
        if canonical not in DEEPSEEK_PRO_IDS:
            return False
        worker = self.workers.get(canonical)
        return bool(worker and worker.onboarded)

    def cheapest_worker_for(self, task_type: str) -> str | None:
        """Lowest-tier onboarded worker whose specialization covers task_type.

        Mission: use the lowest-capability worker likely to complete the task
        correctly. Returns the canonical worker id, or None if no worker
        specialises in task_type (graceful degradation).
        """
        tier_order = {TIER_FAST: 0, TIER_MID: 1, TIER_PREMIUM: 2, TIER_MAIN: 3}
        best: WorkerIdentity | None = None
        for worker in self.workers.values():
            if not worker.onboarded:
                continue
            if task_type in worker.cheapest_for:
                if best is None or tier_order.get(worker.tier, 9) < tier_order.get(best.tier, 9):
                    best = worker
        return best.id if best else None

    def premium_prep_opportunity(self, task_type: str) -> dict[str, Any] | None:
        """If a premium worker would normally take this task but a cheaper
        worker can narrow the problem first, return the pre-narrowing hint.

        NOT mechanically forced -- returns a recommendation only; callers
        decide. None when the premium worker is the right first choice.
        """
        cheapest = self.cheapest_worker_for(task_type)
        if cheapest is None:
            return None
        cheapest_worker = self.workers[cheapest]
        if cheapest_worker.is_premium:
            return None                      # already the cheapest capable
        return {
            "prep_worker": cheapest,
            "prep_worker_tier": cheapest_worker.tier,
            "task_type": task_type,
            "rationale": (
                f"{cheapest} ({cheapest_worker.tier}) can narrow the problem "
                f"first (locate files, reproduce, identify tests/constraints, "
                f"build a concise evidence packet) before premium dispatch."),
        }


def get_identity_registry() -> WorkforceIdentityRegistry:
    """Module-level default registry (lazy singleton)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = WorkforceIdentityRegistry()
    return _default_registry


_default_registry: WorkforceIdentityRegistry | None = None


__all__ = [
    "WorkforceIdentityRegistry",
    "WorkforceIdentityError",
    "WorkerIdentity",
    "get_identity_registry",
    "SUBSCRIPTION_CAPACITY",
    "METERED_API_CAPACITY",
    "LOCAL_CAPACITY",
]
