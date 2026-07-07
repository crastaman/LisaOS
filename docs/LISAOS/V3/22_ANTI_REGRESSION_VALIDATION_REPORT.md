# Anti-Regression Validation Report

**Status:** Implemented. **Date:** 2026-07-08
**File:** `core/anti_regression.py`. Design reference: `19_ANTI_REGRESSION_FRAMEWORK.md`.

---

## 1. What was implemented

Seven enforceable, pure gate functions (each returns a `GateResult` with severity `OK`/`WARN`/`FAIL`), plus `GateReport` (a collection with `.failures`/`.warnings`/`.passed`) and three aggregators (`assignment_gates`, `run_pre_sprint_gates`, `run_post_sprint_gates`). This is Phase 1's slice of the framework — the subset that doesn't require a live scheduler (Phase 2) to evaluate.

## 2. Gate-by-gate mapping to the required checks

| Required check (brief) | Gate | Severity | Verified |
|---|---|---|---|
| No silent fallback | `check_no_silent_fallback` | FAIL | 5 tests (pass ×2, fail ×3 incl. DeepSeek-labelled sink) |
| Intended provider/model must match actual runtime evidence | `check_intended_matches_actual` | FAIL | 3 tests (not-yet-executed=OK, match=OK, drift=FAIL) |
| Main agent must not perform majority of delegable work | `check_main_not_majority` | FAIL/WARN | 3 tests (OK <40%, WARN 40–50%, FAIL >50%) |
| Stale aliases must not resolve | `check_no_stale_alias` | FAIL | 2 tests (all-fail-closed=OK, one-resolves=FAIL) |
| DeepSeek must not become gravity well | `check_deepseek_not_gravity_well` | FAIL | 3 tests (diversified=OK, no-usage=OK, 90%-share=FAIL) |
| Workers should not sit idle while ready work exists | `check_no_idle_while_ready` | FAIL | 3 tests (no-idle=OK, no-ready-work=OK, both-present=FAIL) |
| Context safety checks must run before large reports | `check_context_safety` | FAIL | 3 tests (within-budget=OK, overflow=FAIL, no-budget=FAIL) |

**26 tests total** in `tests/test_anti_regression.py`, each gate with at least one PASS and one FAIL case, as required.

## 3. Design notes on each gate

### 3.1 `check_no_silent_fallback`
Compares `resolved_logical` to `intended_model`. If they differ, a fallback happened — legitimate only if `fallback_from` **and** `fallback_reason` are both recorded. An unexplained substitution is FAIL; the message flags explicitly if the sink looks like DeepSeek (`_looks_like_deepseek`), directly targeting the historical monoculture failure mode. A `fallback_from` set without a `fallback_reason` is also FAIL (half-recorded is still a silent fallback).

### 3.2 `check_intended_matches_actual`
Compares `resolved_runtime` (what the resolver decided) to `actual_runtime` (what the dispatcher observed post-execution, e.g. from `subagent_runs.model`). `None` (`actual_runtime` not yet known) is OK — this gate only fires post-execution, matching the framework's Q1 post-sprint check. Drift is a hard FAIL: a provider label unconfirmed by runtime evidence.

### 3.3 `check_main_not_majority`
Pure threshold function on a ratio (0.0–1.0), not tied to any specific accounting mechanism — the framework's F2/main_agent_work_ratio KPI, computed however Phase 2's dispatcher chooses to measure it. Thresholds match the framework exactly: FAIL >50%, WARN 40–50%, OK ≤40%.

### 3.4 `check_no_stale_alias`
Takes anything with a `.normalise(name)` method (duck-typed — works with the real `ProviderResolver` or a test stand-in) and checks the five aliases retired in Phase 0 (`RETIRED_ALIASES = qwen, qwen-alibaba, ali-qwen, qwen-modelstudio, alibaba-qwen`) all fail to resolve. This is the one gate already wired into the live CLI (`bin/lisa-workforce gates`) and verified against the real `ProviderResolver`.

### 3.5 `check_deepseek_not_gravity_well`
Takes a `{provider: usage_count}` dict; FAILs if DeepSeek's share exceeds 80%. Threshold is a parameter, not hardcoded, so it can be tuned per Workforce Mode later (Phase 3) without changing the gate's logic.

### 3.6 `check_no_idle_while_ready`
The literal "keep the workforce busy" invariant from `00 §5`/`08 A3`: FAILs only when **both** idle capable employees **and** ready unassigned work exist simultaneously — either alone is fine (nothing to do, or fully staffed).

### 3.7 `check_context_safety`
FAILs on overflow (`tokens_used > budget`) **and** on a missing/zero budget (`budget <= 0`) — a report generated with no budget check at all is exactly the "large reports without context budget checks" regression the framework calls out, so "no budget set" is treated as unsafe, not permissive.

## 4. Aggregators

- `assignment_gates(assignment)` — the two per-assignment gates (F1, F3), for checking a single `WorkAssignment` as it's produced.
- `run_pre_sprint_gates(provider_resolver)` — Phase 1's pre-sprint subset: stale-alias check. (P1/P2/P4/P5 from the framework need a live scheduler and are Phase 2.)
- `run_post_sprint_gates(assignments, main_work_ratio, provider_usage, idle_capable_count, ready_unassigned_count)` — runs F1/F3 over every assignment plus F2, DeepSeek-gravity-well, and idle-while-ready at the sprint level.

Verified with both a healthy-sprint case (`test_post_sprint_gates_pass_on_healthy_sprint`, all OK) and a **fully regressed sprint** case (`test_post_sprint_gates_fail_on_regressed_sprint`) that simultaneously trips silent-fallback, main-majority, DeepSeek-monoculture, and idle-while-ready — confirming the aggregator surfaces all four independently rather than stopping at the first failure.

## 5. Live wiring

```
$ python3 bin/lisa-workforce gates
[OK] no_stale_alias: all 5 retired aliases fail closed
```
Exit code 0 (would be 3 on any FAIL). This is the first anti-regression gate running against live state, not just tests.

## 6. What is deferred to later phases

Per the framework's own phasing (`19 §9`, `13`):
- **Phase 2**: pre-sprint checks P4 (main-runtime policy)/P5 (routing independence — already structurally true via the L2/L3 separation, but not yet gate-checked live); post-sprint checks Q1–Q3 wired to a real dispatcher; the full regression test plan RT1–RT8 (needs the scheduler to exist).
- **Phase 3**: post-sprint Q4/Q5 (capacity-waste) and the full KPI scorecard joining the metrics ledger (`09`).

Phase 1 delivers the gate **logic**, fully tested in isolation; wiring it to run automatically every sprint is Phase 2's job once the dispatcher produces the data (assignments, main/worker split, provider usage counts) these gates consume.
