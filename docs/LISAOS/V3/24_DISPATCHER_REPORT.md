# Dispatcher Report

**Status:** Complete. **Date:** 2026-07-08
**File:** `core/dispatcher.py`. CLI: `bin/lisa-dispatch`.

---

## 1. Core principle enforced in code, not just design

> **Main runtime coordinates. Workers execute.**

The `Dispatcher` class has **no code path by which it (or a caller) can execute a WorkPackage itself.** Every package that reaches a terminal state does so via the injected `ExecutorFn`, running on a worker thread, staffed by `WorkforceResolver` (Phase 1). `Dispatcher.run()` returns a `DispatchReport` whose every `WorkAssignment.routed_by == "workforce_resolver"` — hard-set by Phase 1's dataclass default and never touched by the dispatcher. Verified directly: `TestDispatchAntiRegressionGates.test_main_never_appears_as_the_executor` asserts `metrics.main_completed == 0` and every assignment's `routed_by` after a real dispatch.

## 2. Execution model

```python
ExecutorFn = Callable[[WorkPackage, WorkAssignment], ExecutionResult]
```
The default, `simulated_executor`, is a **hermetic stand-in**: it sleeps 20ms (so parallel dispatch produces a measurable, real wall-clock speedup — see `26`) and reports `actual_runtime = assignment.resolved_runtime` (no drift, by construction). It makes **no network call and spends nothing**. A real OpenClaw-spawning executor can be injected later — same interface, no dispatcher changes required, e.g. building on `ProviderResolver.build_spawn_payload()` from Phase 0.

`ExecutionResult(success, actual_runtime, error)` is what the dispatcher records back onto the `WorkAssignment` (`actual_runtime`, `duration_seconds`) and what decides `mark_complete` vs `mark_failed` on the graph.

Execution genuinely runs in parallel via `concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency)` — not simulated sequencing dressed up as parallel; see `26_PARALLEL_EXECUTION_REPORT.md` for measured timing proof.

## 3. Concurrency control

Two independent caps, both configurable (`Dispatcher.__init__`):

| Cap | Default | Purpose |
|---|---|---|
| `max_concurrency` | 8 | Global ceiling on simultaneously in-flight packages |
| `max_per_provider` | 3 | Per-provider ceiling — prevents the scheduler from self-throttling a single provider by hammering it with every ready package at once (the self-inflicted-rate-limit risk flagged in `11_QWEN_RELIABILITY_PLAN.md`) |

A candidate whose provider is at its per-provider cap is **skipped for that tick only** (not failed) — it remains ready and is retried next tick once a slot frees. This is recorded distinctly (`provider_capped` per tick) from genuine idling (§5).

## 4. Fail-closed per package (extends Phase 0/1's guarantee to the scheduler)

If `WorkforceResolver.resolve()` raises `WorkforceResolutionError` for a ready package:
1. The partial evidence (`exc.evidence`) is recorded to `report.assignments` and the evidence log.
2. A human-readable line is appended to `report.errors`.
3. `graph.mark_failed(package_id)` — the package becomes terminal; its dependents become `blocked` (Phase 2's dependency graph, § `23`).
4. **The dispatch continues** — independent, resolvable siblings are unaffected.

Verified: `test_unstaffable_package_fails_without_blocking_independent_siblings` (an impossible-capability package fails while a sibling `microtask` package completes normally) and `test_no_available_model_fails_closed_never_silently_uses_deepseek` (chief-architect with no fallback chain, Anthropic subscription down → fails closed, `physical_model` is `None`, never `custom-api-deepseek-com/deepseek-reasoner`). Live CLI demonstration:
```
$ bin/lisa-dispatch run demo_failclosed.json
graph_summary: {"total": 3, "completed": 1, "failed": 1, "blocked": 1, ...}
errors: ["bad: No employee provides the required capabilities ['nonexistent-capability']. Failing closed."]
exit code: 2
```
The dependent-on-`bad` package correctly shows as `blocked` (never staffed, never run) — not silently dropped, not retried forever.

## 5. Subscription-aware admission (requirement #7)

When more ready, resolvable work exists than there is concurrency to admit **this tick**, candidates are sorted by:
```python
_COST_PRIORITY = {
    "subscription-abundant": 0,   # included subscription capacity -- admit first
    "subscription-scarce":   0,   # still non-metered (guarded at employee-selection, not scheduling)
    "subscription-probation": 1,  # reserved slot for a future prepaid-but-unvalidated class
    "elastic-api":            2,  # metered -- admit last under contention
}
```
This does **not** change *who* is assigned (Phase 1's `WorkforceResolver` already decided that deterministically) — only the **order** ready, resolvable work is admitted when capacity is contested, so subscription capacity is consumed before elastic spend accrues. Live proof, `max_concurrency=1` (forces a strict choice between two simultaneously-ready packages):
```
sub (-> claude-haiku, subscription-abundant)   wait = 0.0000s
elastic (-> deepseek, elastic-api)             wait = 0.0228s
```
The subscription-backed package is admitted immediately; the elastic one waits for the freed slot — exactly the "prefer included subscription capacity... do not optimise purely for utilisation" requirement. Verified: `TestSubscriptionAwareness.test_subscription_candidate_admitted_before_elastic_under_contention`.

**Honest gap:** no `preferred` employee model currently maps to a `subscription-probation` cost class (only GLM's `fallback_models` entries are probationary), so priority `1` is presently unreachable in practice — the ordering is correct and ready for when/if that changes, but cannot yet be demonstrated live. Documented, not hidden.

## 6. Runtime evidence (requirement #6)

`WorkAssignment` (Phase 1) gained one field: `duration_seconds: float | None`. Every executed package's evidence record (JSONL, `record_assignment_evidence()`, unchanged from Phase 0/1) now includes, per the brief:

| Required field | Present as |
|---|---|
| assigned employee | `employee` |
| intended model family | `intended_family` |
| intended model | `intended_model` |
| resolved runtime | `resolved_runtime` |
| actual runtime | `actual_runtime` (filled post-execution) |
| execution duration | `duration_seconds` (new, Phase 2) |
| fallback reason | `fallback_reason` |
| evidence source | `evidence_source` |

Verified: `TestRuntimeEvidence.test_evidence_recorded_with_required_fields_for_every_execution` reads back the JSONL and asserts all required keys are present and non-null on every line.

## 7. Anti-regression wiring

`run_dispatch_gates(report, provider_resolver)` (added to `core/anti_regression.py`, Phase 2) runs, in one call, against a completed `DispatchReport`:
- `check_no_silent_fallback` + `check_intended_matches_actual` per assignment
- `check_main_not_majority` (from `metrics.main_work_ratio`)
- `check_deepseek_not_gravity_well` (from `metrics.provider_usage`)
- `check_no_idle_while_ready` (from the corrected `metrics.max_unexplained_idle_ready` — see `25_WORKFORCE_UTILISATION_REPORT.md §4` for why this needed a real fix during implementation)
- `check_no_worker_starvation` (new gate, from `metrics.wait_times`)
- `check_no_stale_alias` (if a resolver is supplied)

Full detail and results in `22_ANTI_REGRESSION_VALIDATION_REPORT.md` (Phase 1) and this phase's live proof in `26_PARALLEL_EXECUTION_REPORT.md`.

## 8. CLI (`bin/lisa-dispatch`)

```
lisa-dispatch run <goal.json> [--max-concurrency N] [--max-per-provider N]
```
Reads a flat JSON list of work packages (with `depends_on`), builds the graph, runs the dispatcher against the **real, live registries**, prints the full `DispatchReport` + gate results. Exit codes: `0` clean pass, `2` fail-closed packages present, `3` gate failure (mirrors `bin/lisa-resolve`/`bin/lisa-workforce`'s posture).

## 9. What this does NOT do

- Does not spawn real OpenClaw subagents (hermetic executor by default; see §2).
- Does not implement Workforce Modes as re-binding data (Phase 3).
- Does not persist a cross-run capacity/health ledger (Phase 3, `06 §4`).
