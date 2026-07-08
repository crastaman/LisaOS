# Runtime Health Report

**Status:** Complete. **Date:** 2026-07-08

---

## 1. The six required health states, implemented

`core/capacity_ledger.py`: `healthy`, `degraded`, `unavailable`, `exhausted`,
`probationary`, `disabled` — exactly the six named in the brief
(`VALID_HEALTH_STATES`). Transitions are covered in full in
`28_CAPACITY_LEDGER_REPORT.md §3`; this report focuses on how health
**influences employee selection**, and on the "never silently fallback /
always record" requirement.

## 2. Health influences selection — where, precisely

`PolicyEngine.resolve()` (`core/policy_engine.py`) calls
`CapacityLedger.is_usable(logical, risk=..., allow_exhausted=mode.
allow_exhausted_capacity)` as the **first** check on every step of an
employee's model chain — before any live `ProviderResolver` call. The
decision table:

| `health_state` | Usable? | Condition |
|---|---|---|
| `healthy` | Yes | always |
| `degraded` | Yes | always (informational only in Phase 3 — still working, just flagged; not excluded, since the brief only names unavailable/exhausted/probationary as exclusionary) |
| `unavailable` | **No** | never |
| `disabled` | **No** | never |
| `exhausted` | No, unless `allow_exhausted=True` | mode-gated escape hatch |
| `probationary` | No, unless `risk == "low"` | risk-gated, never mode-overridable |

## 3. No silent fallback — every skip is recorded

Every ledger-driven skip is appended to the resolver's `reasons` list AND, if
it was the employee's **preferred** model that got skipped, captured as
`preferred_skip_reason` so the final `WorkAssignment.fallback_reason` names
the actual cause (not just "unusable"):

```
"claude-haiku unusable (ledger: health_state=unavailable); explicit employee fallback -> glm-turbo"
"claude-sonnet unusable (ledger: exhausted (reset=unknown)); explicit employee fallback -> codex"
```

This is checked by `check_no_silent_fallback` (Phase 1, reused unchanged —
`run_policy_gates` always runs it) and is a strict upgrade over Phase 1's
plain WorkforceResolver, which only records "preferred X unusable" without
saying why; PolicyEngine's fallback_reason is more evidence-rich because it
is a *new*, separately-tested code path (`core/policy_engine.py`), not a
modification of `core/workforce_resolver.py` (untouched, Phase 1's existing
tests for it still pass unmodified).

## 4. Availability forecasting

| Field | Behaviour |
|---|---|
| `exhausted_until` | Set explicitly by `record_exhaustion(..., exhausted_until=...)`. `None` means unknown — **never guessed**. |
| `next_available_at` | Mirrors `exhausted_until` today (same forecast, exposed under the name the brief asked for). |
| `last_checked_at` | Updated on every `record_success`/`record_failure`/`record_exhaustion`/`effective_health()` call — always reflects the last time this provider's health was actually examined. |

`effective_health()` is the single place auto-recovery happens, and only when
both pieces of information are present: a known `exhausted_until` **and** the
current time being past it. See `28_CAPACITY_LEDGER_REPORT.md §4` for the
four tests proving this exactly (unknown-never-recovers,
known-past-recovers, known-future-stays, explicit-success-always-clears).

## 5. Runtime health gates (anti-regression)

Three new gates in `core/anti_regression.py`, all run by `run_policy_gates()`:

- `check_no_unavailable_capacity_selected` — FAILs if any accepted assignment
  carries `health_state` of `unavailable`/`disabled`. Defence-in-depth: by the
  time an assignment exists, `PolicyEngine` should already have excluded
  these; this gate exists so a future code change that broke that guarantee
  would be caught by CI, not by an operator noticing bad output.
- `check_no_exhausted_capacity_unless_allowed` — FAILs if `health_state ==
  "exhausted"` was selected without the acting mode's `allow_exhausted_
  capacity` being true. Verified both ways live: `balanced` mode blocks it
  (falls back to `codex`); `emergency` mode allows it (uses `claude-sonnet`
  directly, gate reports `[OK] ... allowed=True`).
- `check_probationary_not_critical` — FAILs if probationary capacity (by
  either `health_state` or `cost_class`) was used for `risk == "critical"`
  work, regardless of mode.

## 6. Live demonstration — both sides of the exhaustion gate

```
$ ledger.record_exhaustion("claude-sonnet", exhausted_until=None)   # unknown reset

$ bin/lisa-dispatch run hotfix.json --mode balanced
  resolved_logical: codex            # exhausted-excluded, explicit fallback
  fallback_from: claude-sonnet
  health_state: healthy              # codex's health, not sonnet's

$ bin/lisa-dispatch run hotfix.json --mode emergency
  resolved_logical: claude-sonnet    # exhausted, but emergency explicitly allows it
  fallback_from: None
  health_state: exhausted
  gate [no_exhausted_capacity_unless_allowed]: OK — "health_state='exhausted', allowed=True"
```

Both runs pass every anti-regression gate — the system is not merely
permissive or merely restrictive; it enforces exactly the policy the active
mode declares, and records which one applied.

## 7. Test summary

Runtime health behaviour is covered across three test files rather than one,
reflecting its layered implementation: `tests/test_capacity_ledger.py`
(state machine correctness, 23 tests), `tests/test_policy_engine.py`
(health-influenced selection during real resolution, 6 of its 13 tests touch
ledger exclusion directly), and `tests/test_anti_regression.py` (the three
gates above, 11 dedicated tests: `TestNoUnavailableCapacitySelected` ×4,
`TestNoExhaustedCapacityUnlessAllowed` ×3, `TestProbationaryNotCritical` ×4).
