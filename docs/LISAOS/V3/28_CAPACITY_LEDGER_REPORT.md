# Capacity Ledger Report

**Status:** Complete. **Date:** 2026-07-08
**File:** `core/capacity_ledger.py`. Persisted to `reports/lisa/capacity_ledger.json`
(gitignored, like the existing evidence logs — every test uses
`CapacityLedger.in_memory()` or `CapacityLedger.at_path(tmp)`; no test ever
touches operator state).

---

## 1. What the ledger adds that ProviderResolver cannot

`core.provider_resolver.ProviderResolver` (Phase 0/1) answers "is this
provider credentialed **right now**?" — a point-in-time check with no memory.
It has no way to know that a provider which authenticates fine has, in fact,
been failing or hitting quota for the last hour. `CapacityLedger` is the
persistent memory layer that closes that gap: every logical provider has a
`LedgerEntry` recording health state, cost class, exhaustion forecast,
last-success evidence, failure history, and reliability status — surviving
process restarts.

The two layers are **complementary, not competing**: `PolicyEngine.resolve()`
(see `31_POLICY_ENGINE_REPORT.md`) checks the ledger first (cheap, no network)
and only calls `ProviderResolver.resolve()` for candidates the ledger hasn't
already ruled out.

## 2. Required fields — all present

| Required field | Implementation |
|---|---|
| provider/model availability | `LedgerEntry.health_state` (+ live check remains ProviderResolver's job) |
| health state | `health_state`: `healthy \| degraded \| unavailable \| exhausted \| probationary \| disabled` |
| quota exhaustion | `health_state == "exhausted"` |
| reset time if known | `exhausted_until` (ISO8601 or `None` = unknown) |
| subscription/prepaid status, metered API status | `cost_class`: `subscription-abundant \| subscription-scarce \| subscription-probation \| elastic-api` (same taxonomy `core.dispatcher._COST_PRIORITY` already used — the ledger and the scheduler's admission ordering can never disagree about what "subscription" means) |
| estimated cost class | same `cost_class` field |
| last successful runtime evidence | `last_success_at`, `last_success_runtime` |
| failure history | `failure_history` (bounded to the most recent 20 entries, each `{at, reason}`) |
| reliability status | `reliability_status`: `unknown \| reliable \| degraded \| unreliable \| probation` |
| probationary status | `probationary: bool` (seeded from the static `provider_resolution.yml` flag; can also be set dynamically via `quarantine()`) |

## 3. Health state machine

```
                 3 consecutive record_failure()
  healthy/degraded ─────────────────────────────► unavailable
        ▲                                              │
        │ record_success()                             │ record_success()
        │                                               ▼
        └───────────────────── probationary ◄───(seeded, or quarantine())
                                     │
                          risk != "low" → excluded
                          risk == "low" → usable

  record_exhaustion(exhausted_until=T) ──► exhausted ──(now >= T, if T known)──► healthy/probationary
                                                │
                                    T unknown → NEVER auto-recovers;
                                    only record_success() or enable() clears it

  disable()/enable() ──► manual override, independent of the above
```

A single failure moves a healthy provider to `degraded` (still usable — a
degraded provider is still working, just flagged); three **consecutive**
failures escalate to `unavailable` (excluded). Any real success immediately
resets `consecutive_failures` to 0 and recovers the state — a probationary
provider recovers to `probationary`, not `healthy` (its probation doesn't
evaporate just because one call succeeded).

## 4. No guessing — the exhaustion forecasting contract

Per the brief: *"If reset time is unknown, mark unknown rather than
guessing."* `record_exhaustion(logical, exhausted_until=None)` records exactly
that — `None`, not a fabricated time. `effective_health()` only auto-recovers
from `exhausted` when `exhausted_until` is **both known and has actually
passed**; an unknown reset time never auto-recovers, no matter how many times
it is checked. Verified directly:

```
test_unknown_reset_time_never_auto_recovers   — checked twice, stays exhausted both times
test_known_past_reset_time_auto_recovers      — auto-recovers to healthy
test_known_future_reset_time_stays_exhausted  — stays exhausted until the time passes
test_explicit_success_clears_exhaustion_regardless_of_forecast — a real success always wins
```

## 5. Persistence — proven across an actual process boundary

Every unit test uses an in-memory or tmp-path ledger, so the persistence claim
is separately verified by driving the real `bin/lisa-dispatch` CLI as two
**independent OS processes** sharing one ledger file:

```
$ python3 -c "... ledger.record_failure('claude-haiku', ...) x3 ..."   # process A
  seeded: unavailable 3

$ bin/lisa-dispatch run demo_microtask_lowrisk.json --ledger-path ledger.json   # process B (fresh process)
  employee: operations-microtask-agent
  resolved_logical: glm-turbo          # NOT claude-haiku
  fallback_from: claude-haiku
  fallback_reason: "claude-haiku unusable (ledger: health_state=unavailable); explicit employee fallback -> glm-turbo"
  health_state: probationary
```

Process B never called `record_failure` itself — it read process A's
persisted JSON from disk and correctly excluded `claude-haiku` before even
asking `ProviderResolver` whether it was credentialed (it was; the exclusion
is ledger-driven, not auth-driven). After the run, the on-disk ledger shows
`claude-haiku` untouched at `unavailable` (it was never used this run) and a
fresh, genuine success recorded for `glm-turbo`:

```json
"claude-haiku": {"health_state": "unavailable", "consecutive_failures": 3, ...},
"glm-turbo":     {"health_state": "probationary", "total_successes": 1,
                  "last_success_runtime": "openclaw", ...}
```

## 6. Thread safety

Dispatcher work packages execute on worker threads (`concurrent.futures.
ThreadPoolExecutor`); `ledger_recording_executor` (§7) runs its ledger writes
from inside those worker threads. Every mutating `CapacityLedger` method
acquires an internal `threading.Lock`. Verified with a genuine concurrency
test: 4 threads × 50 `record_failure()` calls each on the same entry, no lost
updates — `total_failures == 200` exactly, every run.

## 7. Executor integration — zero Dispatcher changes required

`ledger_recording_executor(ledger, inner=simulated_executor)` wraps any
`core.dispatcher.ExecutorFn` (duck-typed; no import of `core.dispatcher`, kept
one-directional exactly like `core.anti_regression`'s established pattern).
Real execution outcomes feed the ledger through the **same** injectable
executor seam Phase 2 already designed for a future real-spawn executor:

```python
Dispatcher(workforce=policy_engine, executor=ledger_recording_executor(ledger))
```

`core/dispatcher.py` required no modification for the scheduler to become
capacity-ledger-aware — verified in
`tests/test_dispatcher.py::TestCapacityLedgerSchedulerIntegration`.

## 8. Test summary

`tests/test_capacity_ledger.py` — **23/23 passing**: seeding (known cost
classes/probation match ground truth), persistence (save/reload, in-memory
never touches disk), health transitions (degrade/unavailable/recover,
probation-aware recovery, bounded failure history, disable/enable,
quarantine), exhaustion forecasting (all 4 scenarios above), `is_usable()`
(healthy/unavailable/disabled/exhausted-allowed/exhausted-denied/probation-by-
risk), and the concurrency test.
