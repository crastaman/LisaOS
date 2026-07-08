# Policy Engine Report

**Status:** Complete. **Date:** 2026-07-08
**File:** `core/policy_engine.py`.

---

## 1. The required flow, implemented exactly

```
Work Package -> Required Capability -> Workforce Mode -> Capacity Ledger
             -> Candidate Employees -> Workforce Resolver -> Provider Resolver
             -> Runtime Evidence
```

`PolicyEngine.resolve(work_package)`:

1. **Workforce Mode** — `self.modes.get(work_package.mode)`; an unknown mode
   fails closed immediately (`auth_result="unknown_mode"`), never defaults to
   `balanced` silently.
2. **Required Capability -> Candidate Employees** — delegates to the REAL,
   unmodified `EmployeeRegistry.candidates_for()` (Phase 1), then applies
   `mode.filter_employees()` (roster restriction + preference reordering).
   Empty result -> fail closed, with a message that distinguishes "no one
   provides this capability at all" from "someone provides it, but this
   mode's roster excludes them."
3. **Capacity Ledger** — for each candidate's model chain (Phase 1's own
   `preferred_model` + `fallback_models` order, unchanged), `CapacityLedger.
   is_usable()` gates every step before any live call is made.
4. **Mode cost policy** — `mode.permits_cost_class()` gates on
   subscription/API-spend policy.
5. **Workforce Resolver / Provider Resolver** — the SAME `ProviderResolver.
   resolve(logical, allow_fallback=False)` call Phase 1's `WorkforceResolver`
   makes; static probation-on-critical-risk restriction (Phase 0/1) still
   applies unchanged.
6. **Runtime Evidence** — returns a `WorkAssignment` (Phase 1's dataclass,
   additively extended with `capacity_class` + `health_state`), with
   `routed_by="policy_engine"` / `evidence_source="policy_engine"` so it is
   distinguishable in the evidence log from a plain Phase 1 resolution.

## 2. What's reused vs. new — the additive contract

| Layer | Status |
|---|---|
| `core.provider_resolver.ProviderResolver` | **Unchanged.** Same fail-closed auth check. |
| `core.workforce_resolver.EmployeeRegistry` | **Unchanged.** Same capability matching, seniority ordering, validation. |
| `core.workforce_resolver.WorkforceResolver` | **Unchanged, still used directly** wherever mode/ledger awareness isn't needed (e.g. `tests/test_workforce_resolver.py`'s 27 Phase-1 tests all still pass, untouched). |
| `core.dispatcher.Dispatcher` | **Unchanged.** Zero lines modified this phase. |
| `core.workforce_modes` / `core.capacity_ledger` / `core.policy_engine` | **New**, purely additive modules. |

`tests/test_policy_engine.py::TestParityWithPhase1` proves the "everything
healthy" case produces **identical** staffing decisions through PolicyEngine
as through plain `WorkforceResolver` — Phase 3 changes nothing about the
happy path; it only adds new, narrower ways to say no.

## 3. Duck-type integration with the Phase 2 scheduler — no scheduler changes

`core.dispatcher.Dispatcher` depends on its `workforce` argument for exactly
two things: `.employees` (an `EmployeeRegistry`-shaped object, used for
`cost_class` lookups in admission-order sorting) and `.resolve(work_package)`
(raising `WorkforceResolutionError` on failure). `PolicyEngine` exposes both:

```python
class PolicyEngine:
    def __init__(self, employee_registry, provider_resolver, mode_registry, capacity_ledger):
        self.employees = employee_registry or EmployeeRegistry()   # <- same attribute name
        ...
    def resolve(self, work_package) -> WorkAssignment: ...          # <- same signature, same exception type
```

So `Dispatcher(workforce=policy_engine, executor=ledger_recording_executor
(ledger))` works with **zero changes** to `core/dispatcher.py` — verified in
`tests/test_dispatcher.py::TestCapacityLedgerSchedulerIntegration` (3 tests)
and live via `bin/lisa-dispatch`, which now builds a `PolicyEngine` instead of
a bare `WorkforceResolver` (the only file touched to wire this in).

## 4. Evidence-rich fallback reasons

Because `PolicyEngine` is a new code path (not an edit to `WorkforceResolver`),
it can afford to record *why* the preferred model was skipped, not just that
it was — see `30_RUNTIME_HEALTH_REPORT.md §3` for real examples. This
required deliberately choosing NOT to alter Phase 1's own fallback_reason
format, per the "additive, don't redesign" instruction.

## 5. Concurrency-limit propagation — an honest gap

`WorkforceMode.concurrency_limits` (e.g. `architecture: {max_concurrency: 2,
max_per_provider: 1}`) is **not yet automatically applied** by `bin/lisa-
dispatch` when packages of that mode are present — `Dispatcher(max_concurrency=
..., max_per_provider=...)` is still set once, globally, per CLI invocation
(`--max-concurrency`/`--max-per-provider` flags), not derived per-mode. This
matters when a goal mixes packages across modes with different concurrency
postures (as `demo_mixed_modes.json` does). Flagging this explicitly rather
than silently ignoring it: a correct per-mode concurrency application would
need either (a) per-mode sub-dispatches merged afterward, or (b) a per-
package concurrency budget inside the Dispatcher's admission loop — the
latter would be a Phase 2 scheduler change, which this phase was told not to
make. Recommended as a named Phase 4 item, not attempted here.

## 6. Live demonstrations (real registries, real dispatch, no mocking)

| Demo | Mode(s) | Result |
|---|---|---|
| Architecture-shaped work routed to `economy` | economy | fails closed: `"no employee provides ['architecture'] within mode 'economy''s allowed roster"`, exit 2, all gates still OK |
| Architecture-shaped work + review, routed to `architecture` | architecture | both packages staffed via `chief-architect`; exit 0, all gates OK |
| Any work routed to `local_future` | local_future | fails closed every time, by design (Ollama has zero models pulled) |
| 4 packages, 4 different modes, 1 merge step | economy/overnight/premium/release | all correctly staffed per mode; `parallel_efficiency: 1.727×`; 4/4 completed, 0 failed |
| Ledger-unavailable `claude-haiku`, fresh CLI process | balanced | correctly excluded despite valid live credentials; explicit fallback to `glm-turbo` |
| Ledger-exhausted `claude-sonnet` | balanced vs. emergency | excluded under balanced (falls back to codex); explicitly allowed under emergency (uses claude-sonnet, health_state=exhausted) |

## 7. Test summary

`tests/test_policy_engine.py` — **13/13 passing**: Phase-1 parity (2),
unknown-mode fail-closed (1), mode roster restriction (3, including
`local_future`), ledger exclusion (5, including dynamic quarantine and the
emergency escape hatch), mode cost policy (1), evidence fields (1). Plus 3
scheduler-integration tests in `tests/test_dispatcher.py` proving the
duck-type contract holds under a real `Dispatcher.run()`.
