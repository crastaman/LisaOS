# Workforce Resolver Report

**Status:** Implemented. **Date:** 2026-07-08
**File:** `core/workforce_resolver.py`; CLI: `bin/lisa-workforce`; wired into `core/router.py` as `resolve_work_package()`.

---

## 1. The resolution flow (as built, matches the required design exactly)

```
WorkPackage
  -> Required Capabilities      WorkPackage.required_capabilities
  -> Candidate Employees        EmployeeRegistry.candidates_for()   (capability superset, seniority-sorted)
  -> Preferred Model            Employee.preferred_model            (a LOGICAL provider name)
  -> Provider Resolver          ProviderResolver.resolve()          (fail-closed, unchanged from Phase 0)
  -> Physical Runtime           Resolution.physical_model / .runtime
  -> Evidence Record            WorkAssignment (+ record_assignment_evidence())
```

Each stage is a distinct, independently-testable function/class:

| Stage | Implementation |
|---|---|
| Work package | `WorkPackage` dataclass: `id`, `description`, `required_capabilities`, `risk` (low/normal/critical), `mode` |
| Candidate employees | `EmployeeRegistry.candidates_for(required_capabilities)` — capability superset match, deterministic employees excluded, sorted lowest-seniority-first |
| Preferred model → physical | `WorkforceResolver.resolve()` calls `ProviderResolver.resolve(logical, allow_fallback=False)` per candidate model in the employee's chain |
| Evidence | `WorkAssignment` dataclass, `record_assignment_evidence()` → `reports/lisa/workforce_evidence.jsonl` |

## 2. Routing authority — the main runtime does not control worker routing

Every `WorkAssignment.routed_by` is hard-set to `"workforce_resolver"` and is never settable by a caller. The main runtime's only interaction with this module is calling `resolve_work_package(work_package)` and receiving back an assignment — it cannot inject a different model, cannot bypass the employee/capability match, and cannot see or influence `_is_probation()`. This is the L2/L3 firewall from the V3 architecture (`00 §4`), now implemented in code rather than only described.

## 3. Fail-closed guarantees (extends the provider layer's guarantee)

| Guarantee | Mechanism | Test |
|---|---|---|
| No capable employee → error, not silent default | `candidates_for()` returns `[]` → `WorkforceResolutionError(no_capable_employee)` | `test_no_capable_employee_raises` |
| No available model anywhere in any candidate's chain → error | Loop exhausts all candidates × their full model chain, then raises `no_available_model` | `test_no_available_model_raises_and_never_injects_deepseek` |
| DeepSeek never injected implicitly | DeepSeek only appears if an employee's own `fallback_models`/`preferred_model` names it (e.g. implementation-engineer). chief-architect's chain never mentions it — confirmed unavailable rather than silently substituted | same test + `test_deepseek_orchestration_assignment` |
| Fully unavailable registry still fails closed | every provider down → `no_available_model`, not a crash | `test_fully_unavailable_registry_fails_closed` |

## 4. Explicit, recorded fallback (multi-hop)

The resolver tries an employee's `preferred_model`, then each `fallback_models` entry in order. The **first** available, policy-compliant one wins. If it isn't the preferred model, the assignment records:
- `fallback_from` = the employee's original preferred model
- `fallback_reason` = a human-readable trace, e.g. `"preferred qwen-deepinfra unusable; explicit employee fallback -> claude-haiku"`

Verified with a genuine **multi-hop** case: `documentation-engineer`'s chain is `[qwen-deepinfra, glm, claude-haiku]`. With DeepInfra down, `glm` is a probation-only candidate and is skipped on normal-risk work, landing on `claude-haiku` — and the recorded `fallback_from` correctly names the *original preferred* model (`qwen-deepinfra`), not the intermediate skipped one (`test_multihop_fallback_skips_probation_and_records_reason`).

## 5. Probation restriction (GLM / GLM-turbo)

`WorkforceResolver._is_probation()` reads `probation: true` directly off the **provider** spec in `provider_resolution.yml` (registered there in Phase 0) — trust is a property of the model/provider, not asserted by the employee registry. A probation model is skipped unless `work_package.risk == "low"`. Verified:
- `test_glm_turbo_used_on_low_risk_when_haiku_unavailable` — GLM-turbo *is* used when risk is explicitly low.
- `test_glm_turbo_skipped_and_fails_closed_on_normal_risk` — the same scenario at normal risk **fails closed** rather than silently using GLM.
- `test_glm_never_used_for_critical_risk` — critical risk never touches a probation model.

## 6. The six required assignment scenarios — all verified

| Scenario | Capabilities | Employee | Resolved | Physical model |
|---|---|---|---|---|
| Haiku microtask | `microtask` | operations-microtask-agent | claude-haiku | anthropic/claude-haiku-4-5 |
| Sonnet implementation | `code-implementation, refactor, review, long-context` | senior-software-engineer | claude-sonnet | anthropic/claude-sonnet-4-6 |
| Opus architecture | `architecture` | chief-architect | claude-opus | anthropic/claude-opus-4-8 |
| Qwen-DeepInfra docs | `documentation, long-context, bulk-mechanical` | documentation-engineer | qwen-deepinfra | deepinfra/Qwen/Qwen3.6-35B-A3B |
| Codex implementation | `code-execution, code-implementation, test-authoring` | software-engineer | codex | openai/gpt-5.5 (runtime: codex) |
| DeepSeek orchestration | `code-implementation, bulk-mechanical` | implementation-engineer | deepseek | custom-api-deepseek-com/deepseek-reasoner |

All six pass in `TestRequiredAssignmentScenarios` (`tests/test_workforce_resolver.py`) and were independently re-verified live via `bin/lisa-workforce assign <caps>` against the real registries (see `PHASE1_IMPLEMENTATION_REPORT.md §4`).

## 7. Evidence record shape

```json
{
  "work_package_id": "wp4",
  "employee": "documentation-engineer",
  "department": "research-and-docs",
  "intended_family": "qwen-deepinfra",
  "intended_model": "qwen-deepinfra",
  "resolved_logical": "claude-haiku",
  "physical_model": "anthropic/claude-haiku-4-5",
  "resolved_runtime": "claude-cli",
  "provider_id": "anthropic",
  "available": true,
  "auth_result": "ok",
  "risk": "normal",
  "mode": "balanced",
  "fallback_from": "qwen-deepinfra",
  "fallback_reason": "preferred qwen-deepinfra unusable; explicit employee fallback -> claude-haiku",
  "actual_runtime": null,
  "routed_by": "workforce_resolver",
  "evidence_source": "workforce_resolver",
  "assigned_at": "2026-07-08T..."
}
```
`actual_runtime` is filled in post-execution (Phase 2's dispatcher) and drives `WorkAssignment.matches_actual` / the anti-regression `check_intended_matches_actual` gate.

## 8. CLI surface

```
bin/lisa-workforce employees   # roster
bin/lisa-workforce validate    # registry structural + model-reference validity
bin/lisa-workforce assign <caps> [risk] [mode]   # one-off staffing, JSON out, exit 2 on fail-closed
bin/lisa-workforce gates        # pre-sprint anti-regression gates, exit 3 on failure
```

## 9. What this does NOT do (Phase 2 scope)

- No scheduler: this resolves **one** work package at a time. Building the execution graph, the ready-frontier, and dispatching multiple packages in parallel is Phase 2.
- No actual OpenClaw subagent spawn. `WorkAssignment` gives everything needed to build a spawn payload (physical model, runtime), but wiring it into the spawn path is Phase 2's gated task.
- `mode` is accepted end-to-end but Workforce Modes (Economy/Balanced/Premium/...) are not yet implemented as data bundles that re-bind `preferred_model` — currently every employee has one fixed preferred model regardless of mode. That is Phase 3 (`08`).
