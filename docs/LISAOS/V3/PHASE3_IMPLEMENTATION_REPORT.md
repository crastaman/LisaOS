# Phase 3 Implementation Report — Workforce Modes + Capacity Ledger

**Status:** Complete. **Date:** 2026-07-08
**Repository:** LisaOS only. WBS not touched. OpenClaw not restarted.

---

## 1. Objective (restated)

Enable LisaOS to dynamically choose the correct workforce configuration
according to available capacity, subscriptions, costs, quotas, runtime
health, work type, and policy mode — without redesigning the Phase 2
scheduler.

## 2. What was built

| Component | File(s) | Summary |
|---|---|---|
| Workforce Modes | `registry/workforce_modes.yml`, `core/workforce_modes.py` | 9 required modes as data; `WorkforceMode` dataclass + registry loader/validator |
| Capacity Ledger | `core/capacity_ledger.py` | Persistent, thread-safe, per-provider health/quota/reliability memory; 6 health states; exhaustion forecasting with no guessing; executor-integration hook |
| Policy Engine | `core/policy_engine.py` | Mode- and ledger-aware staffing; duck-type compatible with `Dispatcher`; implements the full required flow |
| Anti-regression | `core/anti_regression.py` (extended) | 5 new gates + `run_policy_gates()` aggregator |
| CLI integration | `bin/lisa-dispatch` (updated) | Now builds a `PolicyEngine` + `CapacityLedger` + `ledger_recording_executor`; `--ledger-path` flag added |
| `WorkAssignment` | `core/workforce_resolver.py` (2 fields added) | `capacity_class`, `health_state` — additive, default `None`, zero impact on Phase 1/2 call sites |

**Files explicitly NOT modified:** `core/dispatcher.py`, `core/dependency_
graph.py`, `core/workforce_metrics.py`, `core/provider_resolver.py`,
`core/workforce_resolver.py` (except the two additive fields above),
`registry/employees.yml`, `registry/provider_resolution.yml`. The Phase 2
scheduler was not redesigned — confirmed by `git diff` showing zero line
changes to `core/dispatcher.py`.

## 3. Scope checklist against the brief

| # | Requirement | Status |
|---|---|---|
| 1 | Workforce Modes (9 required, each with the 11 named fields) | ✅ `27_WORKFORCE_MODES_REPORT.md` |
| 2 | Capacity Ledger (11 named fields) | ✅ `28_CAPACITY_LEDGER_REPORT.md` |
| 3 | Subscription Awareness (5 classes distinguished, preference order) | ✅ `29_SUBSCRIPTION_AWARENESS_REPORT.md` |
| 4 | Runtime Health Tracking (6 states, influences selection, no silent fallback) | ✅ `30_RUNTIME_HEALTH_REPORT.md` |
| 5 | Availability Forecasting (`exhausted_until`, `next_available_at`, `last_checked_at`, unknown ≠ guessed) | ✅ `28 §4`, `30 §4` |
| 6 | Policy Engine (the exact required flow) | ✅ `31_POLICY_ENGINE_REPORT.md` |
| 7 | Anti-Regression (7 named conditions) | ✅ §4 below |
| 8 | Tests (11 named scenarios) | ✅ `PHASE3_TEST_REPORT.md` |
| 9 | Reports (7 named deliverables) | ✅ this document + 6 others |

## 4. Anti-regression, item by item

| Required check | Gate |
|---|---|
| Unavailable models never selected | `check_no_unavailable_capacity_selected` |
| Exhausted models never selected unless explicitly allowed | `check_no_exhausted_capacity_unless_allowed` |
| Probationary models not used for critical work | `check_probationary_not_critical` |
| Mode policy respected | `check_mode_policy_respected` |
| Subscription/API policy respected | `check_subscription_api_policy_respected` |
| Fallback recorded, no silent fallback | `check_no_silent_fallback` (Phase 1, reused — still runs via `run_policy_gates`) |
| No DeepSeek gravity, no main-runtime gravity | `check_deepseek_not_gravity_well`, `check_main_not_majority` (Phase 1/2, reused) |

`run_policy_gates(report, mode_registry, provider_resolver)` runs
`run_dispatch_gates()` (everything Phase 2 already checked) **plus** all five
new Phase 3 gates, in one call — the single aggregator `bin/lisa-dispatch`
now uses for every dispatch.

## 5. Definition of Done

| Item | Status |
|---|---|
| Workforce modes exist as data | ✅ `registry/workforce_modes.yml`, 9 modes, zero orchestration-code coupling |
| Capacity ledger persists state | ✅ proven across an actual OS process boundary, not just save/reload in one process (`28 §5`) |
| Scheduler can select workforce based on mode + capacity | ✅ `PolicyEngine` drops into `Dispatcher(workforce=...)` with **zero** `core/dispatcher.py` changes; live 4-mode mixed dispatch (`27 §5`) |
| Subscription/API distinction is enforced | ✅ `29`, enforced at `CapacityLedger.is_usable` + `WorkforceMode.permits_cost_class` |
| Unavailable/exhausted/probationary models handled correctly | ✅ `30`, all three demonstrated live both ways (excluded / explicitly allowed where applicable) |
| Runtime evidence remains mandatory | ✅ every `WorkAssignment` still carries full evidence (`routed_by="policy_engine"`, `capacity_class`, `health_state` added) |
| Tests pass | ✅ 220/220 (`PHASE3_TEST_REPORT.md`) |
| Repository clean | ✅ only Phase 3 files staged (see commit) |
| Phase 3 committed | ✅ this commit |

## 6. Honest gaps, flagged rather than hidden

- **`concurrency_limits` per mode is not yet auto-applied** by the CLI when a
  goal mixes packages across modes with different concurrency postures —
  applying it correctly would require either per-mode sub-dispatches or a
  Dispatcher admission-loop change, the latter being exactly the kind of
  scheduler redesign this phase was told to avoid. Recommended for Phase 4.
  (`31_POLICY_ENGINE_REPORT.md §5`)
- **`main_runtime_preference` and `review_requirements`** are complete as data
  but not yet consumed by any enforcement code — no review/approval pipeline
  exists yet to read them, and main-runtime exclusion remains a Phase 2
  structural invariant rather than a mode-gated one. (`27_WORKFORCE_MODES_
  REPORT.md §3`)
- **Rule 3 of subscription awareness** ("expensive API capacity only when
  justified") has no live case to enforce today — the registry has only one
  API cost tier (`elastic-api`). The taxonomy has room for a future
  `elastic-api-expensive` tier without further code changes.
  (`29_SUBSCRIPTION_AWARENESS_REPORT.md §2`)

None of these gaps affect the Definition of Done above; each is a forward-
compatible extension point, not a missing enforcement the brief required.

## 7. Test suite

**220/220 passing** (85 new this phase, 135 pre-existing unchanged). Full
detail in `PHASE3_TEST_REPORT.md`.
