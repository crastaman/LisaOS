"""LisaOS Ready-Frontier Scheduler / Dispatcher (Phase 2).

Implements the required flow end to end:

    Goal -> Dependency Graph -> Ready Frontier -> Employee Assignment
         -> Workforce Resolver -> Runtime Resolution -> Parallel Execution
         -> Merge -> Review

Core principle: MAIN RUNTIME COORDINATES, WORKERS EXECUTE. The Dispatcher
never executes a WorkPackage itself -- every package in the graph is, by
definition, delegable, and is staffed via WorkforceResolver (Phase 1) and
run on a worker thread through an injectable executor. There is no code
path here by which "main" can grab a package.

Design guarantees:
  * PARALLEL BY DEFAULT. Every tick, the dispatcher fills all available
    concurrency slots (subject to a per-provider cap) with ready,
    resolvable work. A capable slot is never left idle while resolvable
    ready work exists -- that is the scheduling-failure criterion from the
    brief ("a worker waiting while independent work exists is a scheduling
    failure").
  * DEPENDENCY-BLOCKED WAITING IS ACCEPTABLE. A package waiting because its
    dependencies are not yet complete is not a failure; it simply is not on
    the ready frontier yet.
  * FAIL CLOSED PER PACKAGE. If a ready package cannot be staffed (no
    capable employee / no available model), it is marked FAILED with
    evidence recorded -- it never silently vanishes and never blocks the
    rest of the graph from proceeding.
  * SUBSCRIPTION-FIRST ADMISSION. When more ready work exists than there is
    concurrency to admit this tick, packages whose resolved employee sits on
    subscription capacity are admitted before ones on metered elastic APIs
    (see `06_SUBSCRIPTION_AND_COST_STRATEGY.md`). This does not change WHO
    is assigned (Phase 1's WorkforceResolver already decided that) -- only
    the ORDER in which ready, resolvable work is admitted under contention.
  * EVIDENCE ON EVERY EXECUTION. Every WorkAssignment that actually executes
    gets `actual_runtime` and `duration_seconds` filled in and is appended
    to the workforce evidence log.

No third-party dependencies beyond the stdlib `concurrent.futures`. The
default executor is a hermetic, in-process simulation (no network, no
spend); a real OpenClaw-spawning executor can be injected later without
changing this module.
"""

from __future__ import annotations

import concurrent.futures as cf
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from core.dependency_graph import DependencyGraph
from core.workforce_resolver import (
    WorkforceResolver,
    WorkforceResolutionError,
    WorkPackage,
    WorkAssignment,
    record_assignment_evidence,
)
from core.workforce_metrics import DispatchMetrics

# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #

@dataclass
class ExecutionResult:
    """What running one WorkPackage on its assigned model actually produced."""

    success: bool
    actual_runtime: str | None = None
    error: str | None = None


ExecutorFn = Callable[[WorkPackage, WorkAssignment], ExecutionResult]


def simulated_executor(work_package: WorkPackage, assignment: WorkAssignment) -> ExecutionResult:
    """Hermetic default executor: no network, no spend, no real spawn.

    Simulates work by sleeping briefly (so parallel dispatch produces a
    measurable wall-clock speedup over serial execution in demonstrations
    and tests) and reports the runtime that was actually used as exactly the
    one that was resolved -- i.e. no drift, by construction.
    """
    time.sleep(0.02)
    return ExecutionResult(success=True, actual_runtime=assignment.resolved_runtime)


# --------------------------------------------------------------------------- #
# Cost-class admission priority (subscription-first, see docs/LISAOS/V3/06)
# --------------------------------------------------------------------------- #

_COST_PRIORITY = {
    "subscription-abundant": 0,   # included subscription capacity -- spend first
    "subscription-scarce": 0,     # still non-metered; guarded at the employee-selection layer
    "subscription-probation": 1,  # prepaid-but-unvalidated capacity (reserved slot; none hired as
                                   # `preferred` today, but the ordering is ready for it)
    "elastic-api": 2,             # metered -- admit last under contention
}


def _cost_priority(cost_class: str | None) -> int:
    return _COST_PRIORITY.get(cost_class or "", 1)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #

@dataclass
class DispatchReport:
    """Everything produced by one dispatch run: evidence + metrics + errors."""

    assignments: dict[str, WorkAssignment] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    metrics: DispatchMetrics = field(default_factory=DispatchMetrics)
    graph_summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignments": {k: v.to_dict() for k, v in self.assignments.items()},
            "errors": self.errors,
            "metrics": self.metrics.to_dict(),
            "graph_summary": self.graph_summary,
        }


# --------------------------------------------------------------------------- #
# Dispatcher
# --------------------------------------------------------------------------- #

class DispatcherError(Exception):
    """Raised only for a scheduler-internal logic fault (should not occur)."""


class Dispatcher:
    """Ready-frontier scheduler: stages the workforce, runs it in parallel."""

    def __init__(
        self,
        workforce: WorkforceResolver,
        *,
        executor: ExecutorFn = simulated_executor,
        max_concurrency: int = 8,
        max_per_provider: int = 3,
        poll_interval: float = 0.005,
        evidence_path=None,
        max_ticks: int = 100_000,
    ):
        self.workforce = workforce
        self.executor = executor
        self.max_concurrency = max_concurrency
        self.max_per_provider = max_per_provider
        self.poll_interval = poll_interval
        self.evidence_path = evidence_path
        self.max_ticks = max_ticks

    # ---- the flow: graph -> ready frontier -> assignment -> resolution ---- #
    #      -> parallel execution -> merge -------------------------------- #

    def run(self, graph: DependencyGraph) -> DispatchReport:
        report = DispatchReport()
        metrics = DispatchMetrics(max_concurrency=self.max_concurrency,
                                  total_packages=len(graph.packages))
        report.metrics = metrics

        first_ready_at: dict[str, float] = {}
        assignment_cache: dict[str, WorkAssignment] = {}
        provider_in_flight: dict[str, int] = defaultdict(int)
        in_flight: dict[cf.Future, tuple[WorkPackage, WorkAssignment, float, str]] = {}

        wall_start = time.monotonic()
        ticks = 0

        with cf.ThreadPoolExecutor(max_workers=max(self.max_concurrency, 1)) as pool:
            while not graph.is_done() or in_flight:
                ticks += 1
                if ticks > self.max_ticks:
                    raise DispatcherError(
                        "exceeded max_ticks -- possible scheduler logic fault"
                    )

                now = time.monotonic()
                frontier = graph.ready_frontier()
                for pkg in frontier:
                    first_ready_at.setdefault(pkg.id, now)

                # ---- Employee Assignment -> Workforce Resolver ---- #
                # Resolve (or reuse a cached resolution for) every ready,
                # not-yet-dispatched package so we can rank admission order.
                candidates: list[tuple[WorkPackage, WorkAssignment]] = []
                for pkg in frontier:
                    if pkg.id in assignment_cache:
                        candidates.append((pkg, assignment_cache[pkg.id]))
                        continue
                    try:
                        assignment = self.workforce.resolve(pkg)
                    except WorkforceResolutionError as exc:
                        # FAIL CLOSED, per package: record evidence, mark
                        # failed, keep the rest of the graph moving.
                        ev = exc.evidence
                        if ev is not None:
                            report.assignments[pkg.id] = ev
                            self._record_evidence(ev)
                        report.errors.append(f"{pkg.id}: {exc}")
                        graph.mark_failed(pkg.id)
                        metrics.record_completion(by_main=False, duration_seconds=0.0,
                                                  failed=True)
                        continue
                    assignment_cache[pkg.id] = assignment
                    candidates.append((pkg, assignment))

                # ---- Subscription-first admission ordering ---- #
                employees = self.workforce.employees.employees
                def sort_key(item):
                    pkg, assignment = item
                    emp = employees.get(assignment.employee)
                    cost_class = emp.cost_class if emp else None
                    return (_cost_priority(cost_class), first_ready_at[pkg.id])
                candidates.sort(key=sort_key)

                # ---- Parallel Execution: fill capacity, respecting caps ---- #
                available_slots = self.max_concurrency - len(in_flight)
                dispatched_ids: set[str] = set()
                provider_capped_ids: set[str] = set()
                for pkg, assignment in candidates:
                    if available_slots <= 0:
                        break
                    provider_key = assignment.provider_id or assignment.resolved_logical or "unknown"
                    if provider_in_flight[provider_key] >= self.max_per_provider:
                        provider_capped_ids.add(pkg.id)
                        continue  # provider-capacity-limited this tick, not idle
                    graph.mark_in_progress(pkg.id)
                    wait = now - first_ready_at[pkg.id]
                    metrics.record_wait(pkg.id, wait)
                    dispatch_start = time.monotonic()
                    future = pool.submit(self.executor, pkg, assignment)
                    in_flight[future] = (pkg, assignment, dispatch_start, provider_key)
                    provider_in_flight[provider_key] += 1
                    available_slots -= 1
                    dispatched_ids.add(pkg.id)

                # ---- Tick bookkeeping (for utilisation + idle-while-ready proof) ---- #
                # `waiting_ready`: candidates that WERE ready this tick but were
                # NOT dispatched (neither newly dispatched nor already running).
                # `provider_capped`: how many of those were skipped purely by
                # the per-provider cap (a deliberate, acceptable throttle) --
                # NOT a scheduling failure. Anything left over in
                # `waiting_ready` beyond `provider_capped` while capacity was
                # free is the genuine "idle capable slot" signal.
                candidate_ids = {pkg.id for pkg, _ in candidates}
                waiting_ready_ids = candidate_ids - dispatched_ids
                remaining_backlog = len(graph.remaining()) - len(in_flight)
                metrics.record_tick(
                    ready_frontier_size=len(frontier),
                    in_flight=len(in_flight),
                    queue_depth=max(remaining_backlog, 0),
                    waiting_ready=len(waiting_ready_ids),
                    provider_capped=len(provider_capped_ids),
                )

                if not in_flight:
                    if graph.is_done():
                        break
                    # Nothing in flight and nothing ready: everything left is
                    # blocked (already reflected in graph.is_done()) or the
                    # graph has no further schedulable work this instant.
                    continue

                # ---- Wait for at least one completion, then loop ---- #
                done, _ = cf.wait(list(in_flight.keys()), timeout=self.poll_interval,
                                  return_when=cf.FIRST_COMPLETED)
                for future in done:
                    pkg, assignment, dispatch_start, provider_key = in_flight.pop(future)
                    provider_in_flight[provider_key] -= 1
                    duration = time.monotonic() - dispatch_start
                    result = future.result()
                    assignment.actual_runtime = result.actual_runtime
                    assignment.duration_seconds = duration
                    report.assignments[pkg.id] = assignment
                    self._record_evidence(assignment)

                    emp = employees.get(assignment.employee)
                    cost_class = emp.cost_class if emp else None

                    # ---- Merge ---- #
                    if result.success:
                        graph.mark_complete(pkg.id)
                        metrics.record_completion(
                            by_main=False, duration_seconds=duration,
                            resolved_logical=assignment.resolved_logical,
                            cost_class=cost_class,
                        )
                    else:
                        graph.mark_failed(pkg.id)
                        report.errors.append(f"{pkg.id}: execution failed: {result.error}")
                        metrics.record_completion(by_main=False, duration_seconds=duration,
                                                  failed=True)

        metrics.wall_clock_seconds = time.monotonic() - wall_start
        report.graph_summary = graph.summary()
        return report

    # ---- evidence -------------------------------------------------------------

    def _record_evidence(self, assignment: WorkAssignment) -> None:
        if self.evidence_path is not None:
            record_assignment_evidence(assignment, path=self.evidence_path)
        else:
            record_assignment_evidence(assignment)
