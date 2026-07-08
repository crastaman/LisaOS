"""LisaOS Policy Engine (Phase 3).

Implements the required flow end to end:

    Work Package -> Required Capability -> Workforce Mode -> Capacity Ledger
                  -> Candidate Employees -> Workforce Resolver
                  -> Provider Resolver -> Runtime Evidence

`PolicyEngine` is a MODE- AND LEDGER-AWARE FRONT END to Phase 1's
WorkforceResolver contract. It does not replace or re-implement provider
resolution (core.provider_resolver.ProviderResolver) or employee capability
matching (core.workforce_resolver.EmployeeRegistry) -- it adds two new,
purely SUBTRACTIVE filtering steps ahead of them:

  1. MODE FILTER: which employees are even eligible, and in what preference
     order, for this work package's mode (core.workforce_modes).
  2. LEDGER FILTER: does recorded runtime health rule out a candidate model
     before we even ask ProviderResolver whether it is credentialed right
     now (core.capacity_ledger)?

Everything else -- the employee's own preferred_model/fallback_models order,
the probation-on-critical-risk restriction, fail-closed-never-DeepSeek -- is
Phase 1's WorkforceResolver contract, UNCHANGED and untouched by this module.

DUCK-TYPE COMPATIBILITY WITH core.dispatcher.Dispatcher: a PolicyEngine
exposes the same shape the Dispatcher already depends on (`.employees`
:: EmployeeRegistry, `.resolve(work_package) -> WorkAssignment`, raising
`WorkforceResolutionError` on failure) so `Dispatcher(workforce=policy_engine)`
requires ZERO changes to core/dispatcher.py. This is how Phase 3 satisfies
"the scheduler can select workforce based on mode + capacity" without
redesigning the Phase 2 scheduler.
"""

from __future__ import annotations

from core.provider_resolver import ProviderResolver, ProviderResolutionError
from core.workforce_resolver import (
    EmployeeRegistry,
    WorkforceResolutionError,
    WorkPackage,
    WorkAssignment,
    DETERMINISTIC_MODEL,
)
from core.workforce_modes import WorkforceModeRegistry, WorkforceModeError
from core.capacity_ledger import CapacityLedger


class PolicyEngine:
    """Mode- and capacity-ledger-aware workforce staffing, fail-closed."""

    def __init__(
        self,
        employee_registry: EmployeeRegistry | None = None,
        provider_resolver: ProviderResolver | None = None,
        mode_registry: WorkforceModeRegistry | None = None,
        capacity_ledger: CapacityLedger | None = None,
    ):
        self.employees = employee_registry or EmployeeRegistry()
        self.providers = provider_resolver or ProviderResolver()
        self.modes = mode_registry or WorkforceModeRegistry()
        self.ledger = capacity_ledger or CapacityLedger.in_memory()

    # ---- probation lookup (static provider flag; Phase 0/1 behaviour) --------

    def _is_static_probation(self, resolved_logical: str | None) -> bool:
        if not resolved_logical:
            return False
        spec = (self.providers.config.get("providers", {}) or {}).get(resolved_logical, {})
        return bool(spec.get("probation"))

    # ---- resolution -----------------------------------------------------------

    def resolve(self, work_package: WorkPackage) -> WorkAssignment:
        """Resolve a work package to a staffed, physical assignment or raise.

        Flow: Work Package -> Required Capability -> Workforce Mode ->
        Capacity Ledger -> Candidate Employees -> [Workforce Resolver logic
        inline below] -> Provider Resolver -> Runtime Evidence.
        """
        try:
            mode = self.modes.get(work_package.mode)
        except WorkforceModeError as exc:
            ev = WorkAssignment(
                work_package_id=work_package.id, employee=None, department=None,
                intended_family=None, intended_model=None, resolved_logical=None,
                physical_model=None, resolved_runtime=None, provider_id=None,
                available=False, auth_result="unknown_mode",
                risk=work_package.risk, mode=work_package.mode,
                fallback_reason=str(exc),
            )
            raise WorkforceResolutionError(
                f"Cannot staff {work_package.id!r}: {exc}. Failing closed.", ev,
            )

        raw_candidates = self.employees.candidates_for(work_package.required_capabilities)
        candidates = mode.filter_employees(raw_candidates)

        if not candidates:
            reason = (
                f"no employee provides {work_package.required_capabilities!r} "
                f"within mode {mode.id!r}'s allowed roster"
                if raw_candidates else
                f"no employee provides the required capabilities "
                f"{work_package.required_capabilities!r}"
            )
            ev = WorkAssignment(
                work_package_id=work_package.id, employee=None, department=None,
                intended_family=None, intended_model=None, resolved_logical=None,
                physical_model=None, resolved_runtime=None, provider_id=None,
                available=False, auth_result="no_capable_employee",
                risk=work_package.risk, mode=work_package.mode,
                fallback_reason=reason,
            )
            raise WorkforceResolutionError(f"{reason}. Failing closed.", ev)

        reasons: list[str] = []
        for employee in candidates:
            preferred = employee.preferred_model
            preferred_skip_reason: str | None = None
            for logical in employee.model_chain(work_package.mode):
                if logical == DETERMINISTIC_MODEL:
                    continue

                # ---- Capacity Ledger filter (Phase 3, NEW) ---- #
                usable, ledger_reason = self.ledger.is_usable(
                    logical, risk=work_package.risk,
                    allow_exhausted=mode.allow_exhausted_capacity,
                )
                if not usable:
                    msg = f"{employee.id}:{logical} ledger-excluded ({ledger_reason})"
                    reasons.append(msg)
                    if logical == preferred and preferred_skip_reason is None:
                        preferred_skip_reason = f"ledger: {ledger_reason}"
                    continue

                entry = self.ledger.get(logical)

                # ---- Mode subscription/API-spend policy (Phase 3, NEW) ---- #
                permitted, why = mode.permits_cost_class(entry.cost_class)
                if not permitted:
                    msg = f"{employee.id}:{logical} mode-excluded ({why})"
                    reasons.append(msg)
                    if logical == preferred and preferred_skip_reason is None:
                        preferred_skip_reason = f"mode policy: {why}"
                    continue

                # ---- Provider Resolver (Phase 0/1, unchanged) ---- #
                try:
                    resolution = self.providers.resolve(logical, allow_fallback=False)
                except ProviderResolutionError as exc:
                    auth = exc.evidence.auth_result if exc.evidence else "error"
                    reasons.append(f"{employee.id}:{logical} unresolved ({auth})")
                    if logical == preferred and preferred_skip_reason is None:
                        preferred_skip_reason = f"unresolved ({auth})"
                    continue
                if not resolution.available:
                    reasons.append(f"{employee.id}:{logical} unavailable "
                                   f"({resolution.auth_result})")
                    if logical == preferred and preferred_skip_reason is None:
                        preferred_skip_reason = f"unavailable ({resolution.auth_result})"
                    continue

                # ---- Static probation flag (Phase 0/1, unchanged) ---- #
                if self._is_static_probation(resolution.resolved_logical) and work_package.risk != "low":
                    msg = f"{employee.id}:{logical} skipped (probation model on " \
                          f"{work_package.risk}-risk work)"
                    reasons.append(msg)
                    if logical == preferred and preferred_skip_reason is None:
                        preferred_skip_reason = "probation model restricted to low-risk work"
                    continue

                # ---- Accept: build evidence-bearing assignment ---- #
                used_fallback = logical != preferred
                assignment = WorkAssignment(
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
                    fallback_reason=(
                        f"{preferred} unusable ({preferred_skip_reason}); "
                        f"explicit employee fallback -> {logical}"
                    ) if used_fallback else None,
                    capacity_class=entry.cost_class,
                    health_state=self.ledger.effective_health(logical),
                    routed_by="policy_engine",
                    evidence_source="policy_engine",
                )
                return assignment

        # No candidate could be staffed with an available, compliant, healthy model.
        ev = WorkAssignment(
            work_package_id=work_package.id, employee=candidates[0].id,
            department=candidates[0].department,
            intended_family=candidates[0].preferred_family,
            intended_model=candidates[0].preferred_model, resolved_logical=None,
            physical_model=None, resolved_runtime=None, provider_id=None,
            available=False, auth_result="no_available_model",
            risk=work_package.risk, mode=work_package.mode,
            fallback_reason="; ".join(reasons),
            routed_by="policy_engine",
            evidence_source="policy_engine",
        )
        raise WorkforceResolutionError(
            f"No available, policy-compliant, healthy model for work package "
            f"{work_package.id!r} in mode {mode.id!r}. Failing closed; no "
            f"silent DeepSeek fallback. Tried: {'; '.join(reasons)}",
            ev,
        )
