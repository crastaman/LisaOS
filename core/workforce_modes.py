"""LisaOS Workforce Modes (Phase 3).

Loads registry/workforce_modes.yml -- workforce modes AS DATA. A mode
re-binds which employees are eligible and how cost/subscription/quality
should be traded off for a class of work; adding or tuning a mode is a
registry edit, never an orchestration-code change (the same discipline
Phase 1 established for employees).

This module has no dependency on core.dispatcher, core.policy_engine, or
core.capacity_ledger -- it is a pure data loader + a couple of small,
side-effect-free policy predicates that core.policy_engine consumes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
WORKFORCE_MODES_REGISTRY = LISA_BASE / "registry" / "workforce_modes.yml"

REQUIRED_MODES = (
    "economy", "balanced", "premium", "overnight", "release",
    "research", "emergency", "architecture", "local_future",
)


class WorkforceModeError(Exception):
    """Raised when a mode is unknown or the mode registry is invalid."""


@dataclass
class WorkforceMode:
    """One workforce policy bundle, loaded from registry/workforce_modes.yml."""

    id: str
    description: str = ""
    preferred_employees: list[str] = field(default_factory=list)
    allowed_employees: list[str] | None = None   # None = unrestricted; [] = none allowed
    preferred_models: list[str] = field(default_factory=list)
    fallback_models: list[str] = field(default_factory=list)
    cost_policy: str = "balanced"
    subscription_policy: str = "allow-metered"
    api_spend_policy: str = "allow"
    concurrency_limits: dict[str, int] = field(default_factory=dict)
    main_runtime_preference: str = "rare"
    worker_routing_priority: list[str] = field(default_factory=list)
    review_requirements: str = "none"
    allow_probationary_capacity: bool = False
    allow_exhausted_capacity: bool = False
    notes: str = ""

    # ---- policy predicates (pure; no I/O) ----------------------------------

    def filter_employees(self, candidates: list[Any]) -> list[Any]:
        """Apply this mode's roster restriction + preference ordering.

        `candidates` are already capability-matched and seniority-sorted
        (EmployeeRegistry.candidates_for); this only restricts/reorders, it
        never re-ranks by seniority.
        """
        out = candidates
        if self.allowed_employees is not None:
            allowed = set(self.allowed_employees)
            out = [c for c in out if c.id in allowed]
        if self.preferred_employees:
            preferred_set = set(self.preferred_employees)
            preferred = [c for c in out if c.id in preferred_set]
            rest = [c for c in out if c.id not in preferred_set]
            out = preferred + rest
        return out

    def permits_cost_class(self, cost_class: str | None) -> tuple[bool, str]:
        """Does this mode's subscription/API-spend policy allow this cost class?"""
        if cost_class is None:
            return True, "no cost class to check"
        if self.subscription_policy == "subscription-only" and cost_class.startswith("elastic"):
            return False, f"mode {self.id!r} is subscription-only; {cost_class!r} is metered API"
        if self.api_spend_policy == "forbidden" and cost_class.startswith("elastic"):
            return False, f"mode {self.id!r} forbids API spend; {cost_class!r} is metered API"
        return True, "ok"


class WorkforceModeRegistry:
    """Loads + validates registry/workforce_modes.yml."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config if config is not None else self._load_config()
        self.modes: dict[str, WorkforceMode] = self._build_modes()

    @staticmethod
    def _load_config() -> dict[str, Any]:
        if not WORKFORCE_MODES_REGISTRY.is_file():
            raise WorkforceModeError(f"Workforce modes registry missing: {WORKFORCE_MODES_REGISTRY}")
        return yaml.safe_load(WORKFORCE_MODES_REGISTRY.read_text()) or {}

    def _build_modes(self) -> dict[str, WorkforceMode]:
        raw = self.config.get("modes", {}) or {}
        if not raw:
            raise WorkforceModeError("workforce modes registry has no modes")
        out: dict[str, WorkforceMode] = {}
        for mode_id, spec in raw.items():
            spec = spec or {}
            out[mode_id] = WorkforceMode(
                id=mode_id,
                description=spec.get("description", ""),
                preferred_employees=list(spec.get("preferred_employees", []) or []),
                allowed_employees=(
                    list(spec["allowed_employees"])
                    if spec.get("allowed_employees") is not None else None
                ),
                preferred_models=list(spec.get("preferred_models", []) or []),
                fallback_models=list(spec.get("fallback_models", []) or []),
                cost_policy=spec.get("cost_policy", "balanced"),
                subscription_policy=spec.get("subscription_policy", "allow-metered"),
                api_spend_policy=spec.get("api_spend_policy", "allow"),
                concurrency_limits=dict(spec.get("concurrency_limits", {}) or {}),
                main_runtime_preference=spec.get("main_runtime_preference", "rare"),
                worker_routing_priority=list(spec.get("worker_routing_priority", []) or []),
                review_requirements=spec.get("review_requirements", "none"),
                allow_probationary_capacity=bool(spec.get("allow_probationary_capacity", False)),
                allow_exhausted_capacity=bool(spec.get("allow_exhausted_capacity", False)),
                notes=spec.get("notes", ""),
            )
        return out

    # ---- lookup --------------------------------------------------------------

    def get(self, mode_id: str) -> WorkforceMode:
        mode = self.modes.get(mode_id)
        if mode is None:
            raise WorkforceModeError(
                f"unknown workforce mode {mode_id!r}; known modes: "
                f"{sorted(self.modes)}"
            )
        return mode

    # ---- validation ------------------------------------------------------------

    def validate(self, employee_registry: Any = None) -> list[str]:
        """Return a list of problems; empty means valid.

        Structural checks always run. If an employee_registry is supplied,
        also checks that every referenced employee id actually exists (catches
        typos in preferred_employees/allowed_employees before they cause a
        confusing "no candidates" failure at resolution time).
        """
        problems: list[str] = []
        for required in REQUIRED_MODES:
            if required not in self.modes:
                problems.append(f"missing required mode: {required!r}")
        for mode_id, mode in self.modes.items():
            if employee_registry is not None:
                known_ids = set(employee_registry.employees)
                for emp_id in mode.preferred_employees:
                    if emp_id not in known_ids:
                        problems.append(
                            f"{mode_id}: preferred_employees references unknown employee {emp_id!r}")
                if mode.allowed_employees:
                    for emp_id in mode.allowed_employees:
                        if emp_id not in known_ids:
                            problems.append(
                                f"{mode_id}: allowed_employees references unknown employee {emp_id!r}")
        return problems
