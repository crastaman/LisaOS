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
  * EVIDENCE IS THE COMPLETION BOUNDARY. Every reconciled executor outcome is
    normalized into strict JSON evidence and durably appended before graph
    success is finalized. If serialization or append fails, the dispatcher
    enters an explicit systemic halt and represents no unevidenced package as
    successfully complete.

No third-party dependencies beyond the stdlib `concurrent.futures`. There is
no default executor (Phase 5 hardening, R3) -- callers must explicitly pass
either the hermetic, in-process `simulated_executor` (no network, no spend)
or a real OpenClaw-spawning executor (see core/openclaw_bridge.py); omitting
one raises rather than silently simulating.
"""

from __future__ import annotations

import concurrent.futures as cf
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from core.dependency_graph import DependencyGraph
from core.workforce_resolver import (
    EvidenceSerializationError,
    WorkforceResolver,
    WorkforceResolutionError,
    WorkPackage,
    WorkAssignment,
    record_assignment_evidence,
    validate_json_safe_value,
)
from core.workforce_metrics import DispatchMetrics

# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #

@dataclass
class ExecutionResult:
    """What running one WorkPackage on its assigned model actually produced.

    The base three fields (success/actual_runtime/error) are Phase 2's
    original, hermetic contract and are unchanged. The fields below are
    Phase 4 additions (see core/openclaw_bridge.py): they carry real
    execution evidence back from OpenClaw when a real ExecutorFn is used,
    and are simply absent/None for the simulated executor. Additive only --
    no existing field's meaning changed.
    """

    success: bool
    actual_runtime: str | None = None
    error: str | None = None
    observed_model: str | None = None
    observed_provider: str | None = None
    run_id: str | None = None
    agent_id: str | None = None
    tokens: dict | None = None
    mismatch: bool = False
    mismatch_detail: str | None = None
    execution_evidence_source: str | None = None


ExecutorFn = Callable[[WorkPackage, WorkAssignment], ExecutionResult]


# --------------------------------------------------------------------------- #
# Executor provenance (r4, finding B3)
#
# Before r4 the Dispatcher accepted ANY callable as its executor and then
# recorded every completion with a hardcoded `by_main=False` -- i.e. it
# asserted "a worker did this" regardless of what actually ran. A caller
# could pass an in-process function that did the work in the orchestrator's
# own process and the metrics would still report 100% delegation.
#
# The fix is a DECLARED provenance mark. Every executor must declare which
# class of execution it performs; the Dispatcher fails closed on an
# undeclared executor, records the declaration on the evidence record, and
# DERIVES attribution from it instead of assuming.
#
# Honest limits (stated in 06_SUBSTRATE_BINDING.md, not just here): this is a
# declaration, not a proof. A caller can deliberately mis-mark a callable, and
# `functools.wraps` can accidentally copy a valid mark onto a wrapper that
# replaces rather than delegates. Strict validation rejects malformed
# declarations; it cannot establish the semantic truth of a valid declaration.
# --------------------------------------------------------------------------- #

EXECUTOR_PROVENANCE_ATTR = "__lisa_execution_provenance__"

WORKER_REAL = "worker-real"            # real out-of-process worker (OpenClaw bridge)
WORKER_SIMULATED = "worker-simulated"  # hermetic in-process simulation, explicitly labelled
MAIN_INLINE = "main-inline"            # ran in the orchestrator's own process (never worker)

_VALID_PROVENANCE = (WORKER_REAL, WORKER_SIMULATED, MAIN_INLINE)

# Which declarations count as worker execution for attribution purposes.
_WORKER_PROVENANCE = (WORKER_REAL, WORKER_SIMULATED)

SIMULATED_LABEL = "SIMULATED-NOT-EXECUTED"


def _validate_provenance_value(provenance: Any) -> str:
    """Return one canonical provenance value or fail closed.

    This is the single vocabulary check used by marking, Dispatcher
    construction, and every Dispatcher.run(). A merely present attribute is
    not a declaration unless it is a string and an exact member of the
    canonical set.
    """
    if type(provenance) is not str or provenance not in _VALID_PROVENANCE:
        raise ValueError(
            f"invalid declared provenance {provenance!r}; expected an exact "
            f"string member of {_VALID_PROVENANCE}"
        )
    return provenance


def validate_executor_provenance(fn: ExecutorFn) -> str:
    """Read and strictly validate the provenance declared by `fn`."""
    return _validate_provenance_value(
        getattr(fn, EXECUTOR_PROVENANCE_ATTR, None)
    )


def mark_executor(fn: ExecutorFn, provenance: str) -> ExecutorFn:
    """Declare which class of execution `fn` performs, and return `fn`.

    Required before an executor may be passed to `Dispatcher`. Use one of
    `WORKER_REAL`, `WORKER_SIMULATED`, `MAIN_INLINE`.
    """
    setattr(fn, EXECUTOR_PROVENANCE_ATTR, _validate_provenance_value(provenance))
    return fn


def executor_provenance(fn: ExecutorFn) -> Any:
    """Return the raw provenance attribute, without treating it as valid."""
    return getattr(fn, EXECUTOR_PROVENANCE_ATTR, None)


def normalize_execution_result(result: Any) -> ExecutionResult:
    """Validate the dispatcher reconciliation contract, or normalize failure.

    Executor code is outside the dispatcher's trust boundary. Malformed return
    values therefore become ordinary failed ExecutionResults whose evidence can
    be persisted; they never escape reconciliation and never become successful
    graph completions through Python truthiness.
    """
    if not isinstance(result, ExecutionResult):
        return ExecutionResult(
            success=False,
            error=(
                "malformed executor result: expected ExecutionResult, got "
                f"{type(result).__name__}"
            ),
            execution_evidence_source="fail-closed-malformed-executor-result",
        )

    problems: list[str] = []
    if type(result.success) is not bool:
        problems.append(
            f"success must be bool, got {type(result.success).__name__}"
        )

    optional_strings = (
        "actual_runtime",
        "error",
        "observed_model",
        "observed_provider",
        "run_id",
        "agent_id",
        "mismatch_detail",
        "execution_evidence_source",
    )
    for field_name in optional_strings:
        value = getattr(result, field_name)
        if value is not None and type(value) is not str:
            problems.append(
                f"{field_name} must be str or None, got {type(value).__name__}"
            )

    if type(result.mismatch) is not bool:
        problems.append(
            f"mismatch must be bool, got {type(result.mismatch).__name__}"
        )

    if result.tokens is not None:
        if type(result.tokens) is not dict:
            problems.append(
                f"tokens must be dict or None, got {type(result.tokens).__name__}"
            )
        else:
            try:
                validate_json_safe_value(
                    result.tokens, path="ExecutionResult.tokens"
                )
            except EvidenceSerializationError as exc:
                problems.append(str(exc))

    if problems:
        return ExecutionResult(
            success=False,
            error="malformed executor result: " + "; ".join(problems),
            execution_evidence_source="fail-closed-malformed-executor-result",
        )
    return result


def simulated_executor(work_package: WorkPackage, assignment: WorkAssignment) -> ExecutionResult:
    """Hermetic default executor: no network, no spend, no real spawn.

    Simulates work by sleeping briefly (so parallel dispatch produces a
    measurable wall-clock speedup over serial execution in demonstrations
    and tests) and reports the runtime that was actually used as exactly the
    one that was resolved -- i.e. no drift, by construction.

    r4 (B4c): this now stamps `execution_evidence_source` itself. Before r4
    only `core.openclaw_bridge.labelled_simulated_executor` applied the
    label, so a caller using the dispatcher API directly with this function
    produced UNLABELLED simulated evidence. Simulation labelling is no longer
    caller-dependent.
    """
    time.sleep(0.02)
    return ExecutionResult(
        success=True,
        actual_runtime=assignment.resolved_runtime,
        execution_evidence_source=SIMULATED_LABEL,
    )


mark_executor(simulated_executor, WORKER_SIMULATED)


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
    """Raised for a scheduler-internal fault or an explicit systemic halt."""


class EvidenceSinkError(DispatcherError):
    """Systemic halt: governed completion cannot be evidenced durably."""

    def __init__(self, message: str, *, report: DispatchReport):
        super().__init__(message)
        self.report = report


class Dispatcher:
    """Ready-frontier scheduler: stages the workforce, runs it in parallel."""

    def __init__(
        self,
        workforce: WorkforceResolver,
        *,
        executor: ExecutorFn | None = None,
        max_concurrency: int = 8,
        max_per_provider: int = 3,
        poll_interval: float = 0.005,
        evidence_path=None,
        max_ticks: int = 100_000,
    ):
        if executor is None:
            # Phase 5 hardening (R3): simulation must be IMPOSSIBLE to select
            # by omission. An omitted executor used to silently default to
            # `simulated_executor`, so any new/refactored caller that forgot
            # to pass one would silently fabricate evidence. Callers must now
            # choose explicitly: pass `simulated_executor` (hermetic
            # tests/demos) or `core.openclaw_bridge.build_real_executor(...)`
            # (real execution) -- omission is a usage error, not a default.
            raise ValueError(
                "Dispatcher requires an explicit executor -- omission used to "
                "silently simulate. Pass executor=simulated_executor for "
                "hermetic tests/demos, or executor=core.openclaw_bridge."
                "build_real_executor(...) for real execution."
            )
        # r6 (ADV-01): a merely present attribute is not enough. Construction
        # and every run use the same strict type-and-membership validator.
        provenance = validate_executor_provenance(executor)
        self.workforce = workforce
        self.executor = executor
        self.executor_provenance = provenance
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

        # r4 (B3): re-derive provenance from the executor that is about to run,
        # rather than trusting the value captured at construction. `executor`
        # is a plain attribute, so `d = Dispatcher(..., executor=declared);
        # d.executor = undeclared` would otherwise run an undeclared callable
        # while every evidence record carried the originally-declared
        # provenance. Checking here means the declaration recorded on the
        # ledger always belongs to the callable that actually ran.
        # Bind the executor to a local for the whole run, so the callable that
        # is checked below is provably the same object that gets submitted --
        # a mutation of `self.executor` mid-run cannot slip past the check.
        executor = self.executor
        provenance = validate_executor_provenance(executor)
        self.executor_provenance = provenance
        by_main = provenance not in _WORKER_PROVENANCE

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
                            self._record_evidence_or_halt(
                                ev, package_id=pkg.id, graph=graph, report=report,
                            )
                        report.errors.append(f"{pkg.id}: {exc}")
                        graph.mark_failed(pkg.id)
                        # Staffing never happened, so nothing executed and
                        # there is no performer to attribute. `failed=True`
                        # short-circuits before the main/worker split; the
                        # value below is derived rather than a bare literal so
                        # no reader mistakes it for an attribution claim.
                        metrics.record_completion(
                            by_main=by_main, duration_seconds=0.0, failed=True,
                        )
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
                    future = pool.submit(executor, pkg, assignment)
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
                    try:
                        raw_result = future.result()
                    except Exception as exc:
                        # Phase 5 hardening (R2): an executor that raises --
                        # instead of returning a failed ExecutionResult --
                        # must never crash the whole batch or lose evidence
                        # for this package (or any sibling still in flight).
                        # Fail this ONE package closed, with evidence, and
                        # keep the loop going, matching the same
                        # fail-closed-per-package guarantee already given to
                        # WorkforceResolutionError above.
                        raw_result = ExecutionResult(
                            success=False, actual_runtime=None,
                            error=f"executor raised an unexpected exception: {exc!r}",
                            execution_evidence_source="fail-closed-executor-exception",
                        )
                    # r6 (ADV-02/ADV-03): no caller-provided value reaches graph
                    # state or evidence until the complete reconciliation
                    # contract has been validated. Malformed results become a
                    # normalized per-package failure with JSON-safe evidence.
                    result = normalize_execution_result(raw_result)
                    assignment.actual_runtime = result.actual_runtime
                    assignment.duration_seconds = duration
                    # Phase 4: carry real-execution evidence onto the
                    # assignment when the executor provided it (real bridge);
                    # every field is None/False for the simulated executor,
                    # so this is a no-op for existing callers.
                    assignment.observed_model = result.observed_model
                    assignment.observed_provider = result.observed_provider
                    assignment.execution_run_id = result.run_id
                    assignment.execution_agent_id = result.agent_id
                    assignment.tokens = result.tokens
                    assignment.mismatch = result.mismatch
                    assignment.mismatch_detail = result.mismatch_detail
                    assignment.execution_evidence_source = result.execution_evidence_source
                    # r4 (B2): the OUTCOME belongs on the evidence record.
                    # Before r4 success/error lived only in the in-memory
                    # DispatchReport, so the ledger could not distinguish a
                    # failed execution from a successful one.
                    assignment.execution_success = result.success
                    assignment.execution_error = result.error
                    # r4 (B3): record the declared provenance of whatever ran,
                    # as re-derived at the top of this run().
                    assignment.execution_provenance = provenance
                    report.assignments[pkg.id] = assignment
                    # r6 (ADV-03): persist evidence before finalizing graph
                    # success or failure. A sink failure is systemic: no
                    # package is represented as successfully completed without
                    # its durable append.
                    self._record_evidence_or_halt(
                        assignment, package_id=pkg.id, graph=graph, report=report,
                    )

                    emp = employees.get(assignment.employee)
                    cost_class = emp.cost_class if emp else None

                    # ---- Merge ---- #
                    # r4 (B3): attribution is DERIVED from the executor's
                    # declared provenance (computed at the top of run()),
                    # never hardcoded. A MAIN_INLINE executor is counted as
                    # main work and drags the delegation ratio down, which is
                    # exactly what it should do -- before r4 it was silently
                    # reported as delegated.
                    if result.success:
                        graph.mark_complete(pkg.id)
                        metrics.record_completion(
                            by_main=by_main, duration_seconds=duration,
                            resolved_logical=assignment.resolved_logical,
                            cost_class=cost_class,
                        )
                    else:
                        graph.mark_failed(pkg.id)
                        report.errors.append(f"{pkg.id}: execution failed: {result.error}")
                        metrics.record_completion(by_main=by_main, duration_seconds=duration,
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

    def _record_evidence_or_halt(
        self,
        assignment: WorkAssignment,
        *,
        package_id: str,
        graph: DependencyGraph,
        report: DispatchReport,
    ) -> None:
        """Persist evidence or place all non-terminal work in systemic failure."""
        try:
            self._record_evidence(assignment)
        except Exception as exc:
            message = (
                f"{package_id}: systemic evidence-sink failure; governed work "
                f"halted before successful completion: {type(exc).__name__}: {exc}"
            )
            report.errors.append(message)
            # Evidence is the completion boundary. Anything not already
            # completed with a persisted record is failed in memory, including
            # in-flight siblings. Their executor calls may already have begun,
            # but the dispatcher will not reconcile them as successful work.
            for remaining in list(graph.remaining()):
                graph.mark_failed(remaining.id)
            report.graph_summary = graph.summary()
            raise EvidenceSinkError(message, report=report) from exc
