"""LisaOS Workforce Resolver (Phase 1).

Turns a WORK PACKAGE into a staffed, evidence-bearing assignment:

    WorkPackage
      -> Required Capabilities
      -> Candidate Employees            (capabilities superset match)
      -> Chosen Employee                (lowest-seniority candidate = cost discipline)
      -> Preferred Model (mode-aware)   (a LOGICAL provider name)
      -> ProviderResolver               (fail-closed logical -> physical)
      -> Physical Runtime               (OpenClaw model + runtime)
      -> Evidence Record

Design guarantees (extend the provider layer's guarantees to the workforce layer):
  * FAIL CLOSED. No capable employee, or no available model in an employee's
    explicit chain, raises WorkforceResolutionError. DeepSeek is NEVER injected
    implicitly — it is only used when it appears in an employee's declared chain.
  * EXPLICIT, RECORDED FALLBACK ONLY. An employee's `fallback_models` are tried
    in order after the preferred model; any fallback taken is recorded
    (fallback_from + fallback_reason).
  * PROBATION RESTRICTION. A model whose provider is `probation: true` (GLM) may
    only be assigned to a LOW-risk work package.
  * ROUTING AUTHORITY. This resolver — not the main runtime — decides the worker
    model. Every assignment records routed_by="workforce_resolver".

This module is ADDITIVE and does not change the legacy provider/cost_tier path.
It has no third-party deps beyond PyYAML and makes no network/provider calls, so
it is safe to unit-test without spending money.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from core.provider_resolver import (
    ProviderResolver,
    ProviderResolutionError,
    Resolution,
)

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
EMPLOYEE_REGISTRY = LISA_BASE / "registry" / "employees.yml"
WORKFORCE_EVIDENCE_LOG = LISA_BASE / "reports" / "lisa" / "workforce_evidence.jsonl"

# Employees that ARE code (routing/infra), not LLM work executors. They are
# never candidates for a normal work package.
DETERMINISTIC_MODEL = "deterministic"

VALID_RISK = ("low", "normal", "critical")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class WorkforceResolutionError(Exception):
    """Raised when a work package cannot be safely staffed (fail closed)."""

    def __init__(self, message: str, evidence: "WorkAssignment | None" = None):
        super().__init__(message)
        self.evidence = evidence


class EmployeeRegistryError(Exception):
    """Raised when the employee registry is structurally invalid."""


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

@dataclass
class WorkPackage:
    """A unit of delegable work with a capability contract.

    `depends_on` (Phase 2) lists the ids of other WorkPackages that must
    complete before this one is eligible to run. Empty by default -- a
    package with no dependencies is immediately part of the ready frontier.
    See core/dependency_graph.py.
    """

    id: str
    description: str
    required_capabilities: list[str]
    risk: str = "normal"          # low | normal | critical
    mode: str = "balanced"
    depends_on: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.risk not in VALID_RISK:
            raise ValueError(f"invalid risk {self.risk!r}; expected one of {VALID_RISK}")


@dataclass
class Employee:
    """A role loaded from registry/employees.yml."""

    id: str
    department: str
    seniority: str
    capabilities: list[str]
    preferred_family: str
    preferred_model: str
    fallback_models: list[str]
    cost_class: str
    reliability_class: str
    failure_policy: str
    responsibilities: str = ""
    best_tasks: list[str] = field(default_factory=list)
    avoid_tasks: list[str] = field(default_factory=list)
    escalates_to: str | None = None
    execution: str | None = None   # "deterministic" => routing/infra, not a work executor

    @property
    def is_deterministic(self) -> bool:
        return self.execution == "deterministic" or self.preferred_model == DETERMINISTIC_MODEL

    def model_chain(self, mode: str = "balanced") -> list[str]:
        """Ordered logical-provider chain: preferred first, then fallbacks."""
        chain = [self.preferred_model]
        for fb in self.fallback_models:
            if fb not in chain:
                chain.append(fb)
        return chain


@dataclass
class WorkAssignment:
    """Evidence-bearing result of staffing one work package."""

    work_package_id: str
    employee: str | None
    department: str | None
    intended_family: str | None
    intended_model: str | None       # employee's preferred logical model
    resolved_logical: str | None     # logical provider actually used (may be a fallback)
    physical_model: str | None
    resolved_runtime: str | None
    provider_id: str | None
    available: bool
    auth_result: str | None
    risk: str
    mode: str
    fallback_from: str | None = None     # intended_model, if a fallback was used
    fallback_reason: str | None = None
    actual_runtime: str | None = None    # filled post-execution by the dispatcher
    duration_seconds: float | None = None  # filled post-execution (Phase 2 dispatcher)
    routed_by: str = "workforce_resolver"   # NEVER "main_runtime"
    evidence_source: str = "workforce_resolver"
    assigned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def matches_actual(self) -> bool | None:
        """True/False once actual_runtime is known; None before execution.

        Compares the runtime intended by resolution against the runtime that
        actually ran (anti-regression: intended must match actual).
        """
        if self.actual_runtime is None:
            return None
        return self.actual_runtime == self.resolved_runtime


# --------------------------------------------------------------------------- #
# Employee registry
# --------------------------------------------------------------------------- #

_REQUIRED_FIELDS = (
    "department", "seniority", "capabilities", "preferred_family",
    "preferred_model", "fallback_models", "cost_class", "reliability_class",
    "failure_policy",
)


class EmployeeRegistry:
    """Loads + validates registry/employees.yml and matches capabilities."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config if config is not None else self._load_config()
        self.seniority_ranks: dict[str, int] = self.config.get("seniority_ranks", {}) or {}
        self.employees: dict[str, Employee] = self._build_employees()

    @staticmethod
    def _load_config() -> dict[str, Any]:
        if not EMPLOYEE_REGISTRY.is_file():
            raise EmployeeRegistryError(f"Employee registry missing: {EMPLOYEE_REGISTRY}")
        return yaml.safe_load(EMPLOYEE_REGISTRY.read_text()) or {}

    def _build_employees(self) -> dict[str, Employee]:
        """Build Employee objects leniently.

        Construction must never crash on a malformed registry -- that would
        prevent validate() from ever running to report the problem cleanly.
        Missing required fields are defaulted to a placeholder here; validate()
        is the source of truth for "is this registry actually valid".
        """
        raw = self.config.get("employees", {}) or {}
        if not raw:
            raise EmployeeRegistryError("employee registry has no employees")
        out: dict[str, Employee] = {}
        for emp_id, spec in raw.items():
            spec = spec or {}
            out[emp_id] = Employee(
                id=emp_id,
                department=spec.get("department", "unknown"),
                seniority=spec.get("seniority", "unknown"),
                capabilities=list(spec.get("capabilities", []) or []),
                preferred_family=spec.get("preferred_family", "unknown"),
                preferred_model=spec.get("preferred_model", "unknown"),
                fallback_models=list(spec.get("fallback_models", []) or []),
                cost_class=spec.get("cost_class", "unknown"),
                reliability_class=spec.get("reliability_class", "unknown"),
                failure_policy=spec.get("failure_policy", "unknown"),
                responsibilities=spec.get("responsibilities", ""),
                best_tasks=list(spec.get("best_tasks", []) or []),
                avoid_tasks=list(spec.get("avoid_tasks", []) or []),
                escalates_to=spec.get("escalates_to"),
                execution=spec.get("execution"),
            )
        return out

    # ---- validation --------------------------------------------------------

    def validate(self, provider_resolver: "ProviderResolver | None" = None) -> list[str]:
        """Return a list of problems; empty means valid.

        Structural checks always run. If a provider_resolver is supplied, also
        checks that every referenced logical model is a known provider.
        """
        problems: list[str] = []
        raw = self.config.get("employees", {}) or {}
        seen_ids = set()
        for emp_id, spec in raw.items():
            if emp_id in seen_ids:
                problems.append(f"duplicate employee id: {emp_id}")
            seen_ids.add(emp_id)
            for f in _REQUIRED_FIELDS:
                if f not in spec:
                    problems.append(f"{emp_id}: missing required field {f!r}")
            if not spec.get("capabilities"):
                problems.append(f"{emp_id}: capabilities must be non-empty")
            sen = spec.get("seniority")
            if sen not in self.seniority_ranks:
                problems.append(f"{emp_id}: unknown seniority {sen!r}")
            # referenced models known?
            if provider_resolver is not None:
                emp = self.employees[emp_id]
                if not emp.is_deterministic:
                    for logical in emp.model_chain():
                        if logical == DETERMINISTIC_MODEL:
                            continue
                        if provider_resolver.normalise(logical) is None:
                            problems.append(
                                f"{emp_id}: references unknown logical model {logical!r}")
        return problems

    def seniority_rank(self, employee: Employee) -> int:
        return self.seniority_ranks.get(employee.seniority, 999)

    # ---- matching ----------------------------------------------------------

    def candidates_for(self, required_capabilities: list[str]) -> list[Employee]:
        """Employees whose provided capabilities cover ALL required ones.

        Deterministic (routing/infra) employees are never candidates for work.
        Returned lowest-seniority first (cost discipline).
        """
        required = set(required_capabilities)
        candidates = [
            e for e in self.employees.values()
            if not e.is_deterministic and required.issubset(set(e.capabilities))
        ]
        candidates.sort(key=self.seniority_rank)
        return candidates


# --------------------------------------------------------------------------- #
# Workforce resolver
# --------------------------------------------------------------------------- #

class WorkforceResolver:
    """Staffs a WorkPackage to an employee + physical runtime, fail-closed."""

    def __init__(
        self,
        employee_registry: EmployeeRegistry | None = None,
        provider_resolver: ProviderResolver | None = None,
    ):
        self.employees = employee_registry or EmployeeRegistry()
        self.providers = provider_resolver or ProviderResolver()

    # ---- probation lookup --------------------------------------------------

    def _is_probation(self, resolved_logical: str | None) -> bool:
        if not resolved_logical:
            return False
        spec = (self.providers.config.get("providers", {}) or {}).get(resolved_logical, {})
        return bool(spec.get("probation"))

    # ---- resolution --------------------------------------------------------

    def resolve(self, work_package: WorkPackage) -> WorkAssignment:
        """Resolve a work package to a staffed, physical assignment or raise."""
        candidates = self.employees.candidates_for(work_package.required_capabilities)
        if not candidates:
            ev = WorkAssignment(
                work_package_id=work_package.id, employee=None, department=None,
                intended_family=None, intended_model=None, resolved_logical=None,
                physical_model=None, resolved_runtime=None, provider_id=None,
                available=False, auth_result="no_capable_employee",
                risk=work_package.risk, mode=work_package.mode,
            )
            raise WorkforceResolutionError(
                f"No employee provides the required capabilities "
                f"{work_package.required_capabilities!r}. Failing closed.",
                ev,
            )

        reasons: list[str] = []
        # Iterate candidates lowest-seniority first; within each, try its model
        # chain (preferred then fallbacks). First available, policy-compliant
        # model wins. Escalate to the next candidate only if a candidate's whole
        # chain is unusable.
        for employee in candidates:
            preferred = employee.preferred_model
            for logical in employee.model_chain(work_package.mode):
                if logical == DETERMINISTIC_MODEL:
                    continue
                try:
                    resolution = self.providers.resolve(logical, allow_fallback=False)
                except ProviderResolutionError as exc:
                    reasons.append(f"{employee.id}:{logical} unresolved "
                                   f"({exc.evidence.auth_result if exc.evidence else 'error'})")
                    continue
                if not resolution.available:
                    reasons.append(f"{employee.id}:{logical} unavailable "
                                   f"({resolution.auth_result})")
                    continue
                # Probation restriction: GLM etc. only on LOW-risk packages.
                if self._is_probation(resolution.resolved_logical) and work_package.risk != "low":
                    reasons.append(f"{employee.id}:{logical} skipped "
                                   f"(probation model on {work_package.risk}-risk work)")
                    continue
                # Accept.
                used_fallback = logical != preferred
                return WorkAssignment(
                    work_package_id=work_package.id,
                    employee=employee.id,
                    department=employee.department,
                    intended_family=employee.preferred_family,
                    intended_model=preferred,
                    resolved_logical=resolution.resolved_logical,
                    physical_model=resolution.physical_model,
                    resolved_runtime=resolution.runtime,
                    provider_id=resolution.provider_id,
                    available=True,
                    auth_result=resolution.auth_result,
                    risk=work_package.risk,
                    mode=work_package.mode,
                    fallback_from=preferred if used_fallback else None,
                    fallback_reason=(f"preferred {preferred} unusable; explicit employee "
                                     f"fallback -> {logical}") if used_fallback else None,
                )

        # No candidate could be staffed with an available, compliant model.
        ev = WorkAssignment(
            work_package_id=work_package.id, employee=candidates[0].id,
            department=candidates[0].department,
            intended_family=candidates[0].preferred_family,
            intended_model=candidates[0].preferred_model, resolved_logical=None,
            physical_model=None, resolved_runtime=None, provider_id=None,
            available=False, auth_result="no_available_model",
            risk=work_package.risk, mode=work_package.mode,
            fallback_reason="; ".join(reasons),
        )
        raise WorkforceResolutionError(
            f"No available, policy-compliant model for work package "
            f"{work_package.id!r}. Failing closed; no silent DeepSeek fallback. "
            f"Tried: {'; '.join(reasons)}",
            ev,
        )


# --------------------------------------------------------------------------- #
# Evidence recording
# --------------------------------------------------------------------------- #

def record_assignment_evidence(assignment: WorkAssignment, *, path: Path | None = None) -> Path:
    """Append one workforce assignment evidence record as JSONL."""
    target = path or WORKFORCE_EVIDENCE_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(assignment.to_dict()) + "\n")
    return target
