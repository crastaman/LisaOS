# Scheduler Implementation Report

**Status:** Complete. **Date:** 2026-07-08
**Scope:** Phase 2 — Dependency Graph Engine + Ready-Frontier Scheduler.
**Files:** `core/dependency_graph.py`, `core/dispatcher.py` (scheduling half), `core/workforce_resolver.py` (extended).
**Builds on:** Phase 1 (`core/workforce_resolver.py`, `registry/employees.yml`) unchanged in its resolution semantics.

---

## 1. Objective restated

Transform Lisa from an employee-aware **router** (Phase 1: resolves one work package to one employee/model) into an active **Engineering Organisation**: a goal decomposes into many work packages with dependencies, and the scheduler keeps as much of the ready, independent work moving in parallel as capacity allows. **Main runtime coordinates. Workers execute.**

## 2. The required flow, as built

```
Goal -> Dependency Graph -> Ready Frontier -> Employee Assignment
     -> Workforce Resolver -> Runtime Resolution -> Parallel Execution
     -> Merge -> Review
```

| Stage | Implementation |
|---|---|
| Goal | A list of `WorkPackage` objects (extended in Phase 2 with `depends_on: list[str]`) |
| Dependency Graph | `DependencyGraph.from_packages()` — validates and indexes |
| Ready Frontier | `DependencyGraph.ready_frontier()` — continuously recomputed |
| Employee Assignment + Workforce Resolver + Runtime Resolution | `WorkforceResolver.resolve()` (Phase 1, unchanged) |
| Parallel Execution | `Dispatcher.run()` — `concurrent.futures.ThreadPoolExecutor` |
| Merge | Graph state transition (`mark_complete`/`mark_failed`) unblocks dependents |
| Review | Anti-regression gates (`run_dispatch_gates()`) evaluated on the completed `DispatchReport` |

## 3. Dependency Graph Engine (`core/dependency_graph.py`)

### 3.1 Data model
`WorkPackage` gained one field: `depends_on: list[str] = []` (additive, defaults to empty — every Phase 1 call site is unaffected). `DependencyGraph` wraps a `dict[str, WorkPackage]` plus three state sets: `completed`, `failed`, `in_progress`.

### 3.2 Fail-closed construction
An unschedulable graph is rejected **at construction**, before any dispatch begins:

| Defect | Detection |
|---|---|
| Duplicate package id | `from_packages()` raises `GraphError` |
| Reference to an unknown dependency id | `_validate_references()` raises `GraphError` |
| Self-dependency | `_validate_references()` raises `GraphError` |
| Dependency cycle (any length) | `_detect_cycles()` — DFS 3-colour (white/grey/black) algorithm, raises `GraphError` naming the cycle |

Verified: `tests/test_dependency_graph.py::TestConstructionValidation` (6 tests) — duplicate id, unknown dep, self-dep, 2-node cycle, 3-node cycle, and a valid diamond-shaped graph (positive control).

### 3.3 Continuously maintained ready frontier
`ready_frontier()` recomputes from current state on every call — nothing is cached staleley. A package is ready iff: not completed, not failed, not blocked, not in-progress, and **all** its `depends_on` ids are in `completed`.

Verified frontier evolution through a 4-node diamond (`a -> b,c -> d`): frontier starts at `{a}`, becomes `{b,c}` once `a` completes, narrows to `{c}` once only `b` completes (proving `d` correctly waits for **both** `b` and `c`), then `{d}` once both are done (`TestReadyFrontier.test_diamond_frontier_evolution`).

### 3.4 Failure propagation (blocked state)
A package whose dependency **failed** (not just "not yet complete") becomes **blocked** — a distinct, permanent terminal state, computed transitively (`blocked()` walks the failure frontier until fixed point). This is deliberately different from "waiting": blocked packages will *never* become ready, so `is_done()` correctly terminates a dispatch even when some packages can never run, without infinite-looping.

Verified: failure propagates through 3 levels of transitive dependency (`test_failure_propagates_transitively`); an **independent sibling of a failed package is unaffected** — proving failures don't leak across unrelated branches (`test_independent_sibling_unaffected_by_unrelated_failure`).

## 4. Ready-Frontier Scheduler (the admission loop in `Dispatcher.run()`)

Each tick:
1. Read the current `ready_frontier()`.
2. For each ready package not yet resolved, call `WorkforceResolver.resolve()` (Phase 1) — **failing closed per package** on error (§ see `24_DISPATCHER_REPORT.md`).
3. Sort resolved candidates by admission priority (subscription-first — see `24`).
4. Fill every available concurrency slot (global cap + per-provider cap) with the highest-priority ready, resolvable candidates.
5. Record a `TickSample` (ready size, in-flight count, queue depth, waiting-ready, provider-capped) for the utilisation report.
6. Block (efficiently, via `concurrent.futures.wait(..., return_when=FIRST_COMPLETED)`) until at least one dispatched package finishes, then repeat from step 1 — newly-freed capacity and newly-unblocked dependents are picked up on the very next tick.

This is what makes the frontier "continuously maintained": every completion immediately re-opens the loop rather than waiting for a fixed batch to finish.

## 5. Validation summary (full detail in the other 4 reports)

| Requirement | Demonstrated by |
|---|---|
| Dependency graph generation | `test_dependency_graph.py` (11 tests, all pass) |
| Ready frontier scheduling | Diamond-graph frontier evolution tests + live dispatch trace (`26_PARALLEL_EXECUTION_REPORT.md`) |
| Parallel execution | Real dispatch: 8 independent packages, **parallel_efficiency = 3.46×** (see `26`) |
| Fail-closed behaviour | `TestFailClosedDispatch` (3 tests) + live CLI run (exit code 2) |

## 6. What Phase 2 deliberately does not change

- **Phase 1's employee-resolution semantics are untouched.** `WorkforceResolver.resolve()` is called exactly as it was; the scheduler only decides *when* and *in what order* to call it, never *how* it resolves.
- **No OpenClaw subagent spawning wired yet.** The default executor (`simulated_executor`) is a hermetic, in-process stand-in (see `24_DISPATCHER_REPORT.md §2`). Real spawning is a future, explicitly separate integration behind the same `ExecutorFn` interface.
- **No mode-driven re-binding of preferred models.** `WorkPackage.mode` is threaded through but Workforce Modes (Economy/Balanced/Premium/...) as data bundles remain future work (`08_DELEGATION_FIRST_AND_WORKFORCE_POLICIES.md`).
