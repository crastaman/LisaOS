# Workforce Modes Report

**Status:** Complete. **Date:** 2026-07-08
**Files:** `registry/workforce_modes.yml`, `core/workforce_modes.py`.

---

## 1. Modes as data, not code

Adding, tuning, or retiring a workforce mode is a `registry/workforce_modes.yml`
edit — never a change to `core/policy_engine.py`, `core/dispatcher.py`, or any
orchestration code. This mirrors the discipline Phase 1 established for
employees ("hiring a model = registry edit").

`core/workforce_modes.py` is a pure loader: `WorkforceMode` (a dataclass) +
`WorkforceModeRegistry` (loads, validates, looks up by id). It has no
dependency on `core.dispatcher`, `core.policy_engine`, or `core.capacity_ledger`.

## 2. The 9 required modes, shipped

| Mode | Roster restriction | Cost posture | Notable policy |
|---|---|---|---|
| `economy` | excludes principal/senior judgement roles | prefer-cheapest, allow-metered | forces architecture-shaped work to fail closed rather than downgrade it |
| `balanced` | none (`allowed_employees: null`) | balanced | the Phase 1/2 default posture, unchanged |
| `premium` | excludes bulk/microtask/probation-leaning roles | prefer-quality, prefer-subscription | |
| `overnight` | none, but bulk/cheap roles preferred | prefer-cheapest, allow-metered | highest concurrency (12/4) for unattended throughput |
| `release` | release/quality/senior roles only | prefer-quality, api-spend minimize | |
| `research` | research-engineer-led, long-context roles | balanced | probation tolerated (exploratory, always reviewed) |
| `emergency` | none (all hands) | api-spend unrestricted | **the only mode with `allow_exhausted_capacity: true`** |
| `architecture` | office of the CTO only (`chief-architect`, `cto-reviewer`) | subscription-only, api-spend forbidden | no probation, no exhausted, ever |
| `local_future` | **deliberately empty** (`allowed_employees: []`) | n/a | any work routed here fails closed — Ollama has zero models pulled (see `10_LOCAL_OLLAMA_STRATEGY.md`); enabling it later is a data edit to this one field |

`WorkforceModeRegistry.validate()` confirms all 9 required modes are present
and (when given the real `EmployeeRegistry`) that every id referenced in
`preferred_employees`/`allowed_employees` actually exists — catching a typo'd
employee id before it causes a confusing "no candidates" failure at resolution
time. Run against the real shipped registries: **zero problems**.

## 3. Field semantics and what's enforced vs. descriptive

| Field | Enforced by | Phase 3 status |
|---|---|---|
| `allowed_employees` / `preferred_employees` | `WorkforceMode.filter_employees()`, consumed by `PolicyEngine.resolve()` | **Enforced** |
| `subscription_policy` / `api_spend_policy` | `WorkforceMode.permits_cost_class()`, consumed by `PolicyEngine.resolve()` | **Enforced** |
| `allow_probationary_capacity` / `allow_exhausted_capacity` | `CapacityLedger.is_usable()`, consumed by `PolicyEngine.resolve()` | **Enforced** |
| `concurrency_limits` | advisory defaults for `Dispatcher(max_concurrency=..., max_per_provider=...)` | Documented; **not yet auto-applied** by the CLI without an explicit flag (see `31_POLICY_ENGINE_REPORT.md §5`) — an honest, flagged gap, not a silent no-op |
| `main_runtime_preference` | none — the Phase 2 Dispatcher structurally never lets main execute, regardless of mode | **Descriptive only**, intentionally not mode-gated (see rationale below) |
| `review_requirements` | none yet | **Descriptive only** — data model complete, no review/approval pipeline consumes it in Phase 3 |
| `worker_routing_priority` | none — `core.dispatcher._COST_PRIORITY` already implements subscription-first admission ordering structurally | **Descriptive**, documents intended order per mode |

**Why `main_runtime_preference` is deliberately not enforced per-mode:** the
Phase 2 invariant "main coordinates, workers execute" is structural — there is
no code path in `Dispatcher.run()` by which main can grab a package, in any
mode. Making `emergency` "allow" main execution would require a scheduler
change, which the brief explicitly said not to do ("do not redesign the Phase
2 scheduler"). The field is preserved as an honest statement of organisational
intent for a future human/approval layer, not wired to a code path that
doesn't exist.

## 4. Test evidence

`tests/test_workforce_modes.py` — **22/22 passing**:
- All 9 required modes present; exactly 9 shipped; structural validation clean.
- Cross-validation against the real `EmployeeRegistry`: zero unknown references.
- Mode-specific assertions: `local_future.allowed_employees == []`,
  `architecture.allowed_employees == {chief-architect, cto-reviewer}`,
  `economy` excludes `chief-architect`, `premium` excludes all 4 bulk/microtask
  roles, only `emergency` sets `allow_exhausted_capacity`.
- `filter_employees()` behaviour: architecture narrows a 1-candidate result
  correctly; `local_future` empties a non-empty candidate list; `balanced` is
  a true no-op; `economy`'s preference reordering puts a preferred-and-allowed
  employee first without excluding non-preferred allowed ones.
- `permits_cost_class()`: subscription-only/forbidden-api-spend modes reject
  `elastic-api`; `allow-metered` modes permit it; subscription cost classes
  are always permitted regardless of mode.

## 5. Live demonstration

A single dispatch of 4 packages, each in a **different** mode, staffed
correctly per mode and merged by a 5th `release`-mode package depending on all
three others (`demo_mixed_modes.json`, real registries, `bin/lisa-dispatch`):

| Package | Mode | Employee | Resolved | Capacity class |
|---|---|---|---|---|
| `bulk-a` | economy | implementation-engineer | deepseek | elastic-api |
| `bulk-b` | overnight | documentation-engineer | qwen-deepinfra | elastic-api |
| `premium-review` | premium | senior-software-engineer | claude-sonnet | subscription-abundant |
| `release-gate` | release | release-manager | gpt | subscription-abundant |

`graph_summary: completed=4, failed=0`, `parallel_efficiency: 1.727×`, all 18
anti-regression gate checks `OK`. One dispatch run, four independent policy
regimes, correctly enforced simultaneously — proof that mode is a per-work-
package property the scheduler already threads through correctly (Phase 2's
scheduler required zero changes).
