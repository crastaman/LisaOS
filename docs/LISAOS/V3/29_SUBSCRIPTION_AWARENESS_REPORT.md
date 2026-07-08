# Subscription Awareness Report

**Status:** Complete. **Date:** 2026-07-08

---

## 1. The five capacity classes, distinguished

| Class | How it's identified | Example logical providers |
|---|---|---|
| Prepaid/subscription | `LedgerEntry.cost_class` in `{subscription-abundant, subscription-scarce}` | claude-opus, claude-sonnet, claude-haiku, codex, gpt |
| Metered API | `cost_class == "elastic-api"` | deepseek, qwen-deepinfra |
| Probationary | `health_state == "probationary"` (from the static `provision_resolution.yml` flag OR a dynamic `CapacityLedger.quarantine()`) **or** `cost_class == "subscription-probation"` | glm, glm-turbo (statically); any provider dynamically quarantined |
| Unavailable | `health_state` in `{unavailable, disabled}`, or a live `ProviderResolver` auth failure | any provider after 3 consecutive observed failures, or lacking credentials |
| Local/future | not yet a routable logical provider at all — the `local_future` mode's `allowed_employees: []` makes this explicit rather than silently falling through to a paid employee | Ollama (0 models pulled; see `10_LOCAL_OLLAMA_STRATEGY.md`) |

These are exactly the five distinctions the brief calls for. The seed mapping
in `core/capacity_ledger.py::_SEED_COST_CLASS` mirrors the README's ground-
truth provider table so the ledger and reality start in agreement.

## 2. Routing preference, as actually implemented (not re-ranked, layered)

The brief's preference order:

```
1. healthy prepaid/subscription capacity when appropriate
2. healthy low-cost API capacity
3. expensive API capacity only when justified
4. probationary capacity only for non-critical work
5. unavailable capacity never
```

This is implemented across **two existing, cooperating layers** rather than a
new re-ranking pass, by design (the brief said not to redesign the Phase 2
scheduler, and Phase 1's employee-authored fallback-chain order is itself a
deliberate business choice that Phase 3 must not silently override):

- **Employee-authored chain order (Phase 1, unchanged):** each employee's
  `preferred_model` + `fallback_models` already encodes a considered
  preference (e.g. `senior-software-engineer`: claude-sonnet (subscription) →
  codex (subscription) → deepseek (elastic-api) — cost-preferring by
  construction for that role). `documentation-engineer` deliberately leads
  with `qwen-deepinfra` (elastic-api) ahead of `claude-haiku` (subscription)
  because large-context bulk summarisation is qwen's actual strength — a
  considered capability trade-off, not a cost mistake, and Phase 3 does not
  reorder it.
- **Ledger + mode exclusion (Phase 3, new):** `PolicyEngine.resolve()` walks
  that SAME authored order, but before accepting any step, asks: is this
  capacity ruled out by recorded health (`CapacityLedger.is_usable`) or by
  the active mode's policy (`WorkforceMode.permits_cost_class`)? Rule 5
  ("unavailable never") and rule 4 ("probationary only non-critical") are
  enforced exactly here — see `30_RUNTIME_HEALTH_REPORT.md`.
- **Admission-order-under-contention (Phase 2, unchanged):**
  `core.dispatcher._COST_PRIORITY` already ranks subscription capacity ahead
  of elastic-api when concurrency is contended — this is rules 1–2 in
  practice, proven in Phase 2 (`24_DISPATCHER_REPORT.md §5`,
  `26_PARALLEL_EXECUTION_REPORT.md §6`) and untouched here.

Rule 3 ("expensive API capacity only when justified") is a reserved future
distinction: the current registry has only one API cost tier (`elastic-api`);
there is no fabricated "expensive vs cheap API" split in `provider_resolution.
yml` today, so this rule has no live case to enforce yet. This is stated
honestly rather than invented — the `_COST_PRIORITY`/`cost_class` taxonomy
already has room for an `elastic-api-expensive` tier if one is ever added,
requiring no further code change.

## 3. Never never never

Rule 5 is checked in three independent places, all covered by tests:
`CapacityLedger.is_usable()` (excludes `unavailable`/`disabled` unconditionally,
`tests/test_capacity_ledger.py::TestIsUsable`), `PolicyEngine.resolve()` (never
even attempts a `ProviderResolver.resolve()` call for a ledger-excluded
candidate), and `check_no_unavailable_capacity_selected()` (a defence-in-depth
anti-regression gate that would catch it if the first two somehow failed).

## 4. Live demonstration — ledger overrides live credentials

The strongest proof that "unavailable" is about **recorded health**, not just
live auth: `claude-haiku` marked unavailable by 3 recorded failures, while its
`ProviderResolver` credentials are perfectly healthy (`resolver_all_available()`).
The scheduler still skips it:

```
employee: operations-microtask-agent
resolved_logical: glm-turbo         # not claude-haiku, despite valid credentials
fallback_from: claude-haiku
fallback_reason: claude-haiku unusable (ledger: health_state=unavailable); ...
```

(`tests/test_policy_engine.py::test_unavailable_ledger_entry_alone_forces_fallback_with_all_providers_healthy`)

## 5. Probationary-only-for-non-critical, generalised

Phase 1 already enforced this for the two statically-flagged providers (glm,
glm-turbo). Phase 3 generalises it to **any** provider the ledger has
dynamically quarantined, with the same restriction:

```
ledger.quarantine("qwen-deepinfra", reason="observed low-quality output")
# risk="normal" -> excluded, falls back
# risk="low"    -> used, health_state="probationary"
```

(`tests/test_policy_engine.py::test_dynamic_quarantine_restricts_to_low_risk`)
and never for `risk="critical"`, regardless of mode
(`check_probationary_not_critical`, `core/anti_regression.py`).
