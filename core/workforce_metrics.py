"""LisaOS Workforce Utilisation Metrics (Phase 2).

Tracks the KPIs the dispatcher must report per dispatch run:
  * worker utilisation %      -- average in-flight/capacity across ticks
  * idle time %                -- 1 - worker utilisation
  * delegation ratio            -- worker-completed / (worker+main)-completed
  * parallel efficiency         -- serial-sum(durations) / wall-clock
  * queue depth                 -- backlog size sampled per tick
  * ready frontier size         -- sampled per tick
  * work completed by main      -- count
  * work completed by workers   -- count
  * average worker wait time    -- mean(dispatch_time - ready_time) per package

Pure, dependency-free accounting object: the Dispatcher feeds it events as
a dispatch progresses; nothing here performs I/O or makes provider calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class TickSample:
    """A snapshot of scheduler state at one scheduling tick.

    `waiting_ready` is how many ready candidates were NOT dispatched this
    tick (left waiting despite being ready) -- distinct from
    `ready_frontier_size`, which is how many were ready to CONSIDER before
    admission ran (most of which are typically dispatched immediately).
    `provider_capped` is how many of those waiting candidates were skipped
    purely because their provider hit its per-provider concurrency cap -- a
    deliberate, documented throttle, not a scheduling failure.
    """

    tick: int
    ready_frontier_size: int
    in_flight: int
    queue_depth: int
    waiting_ready: int = 0
    provider_capped: int = 0


@dataclass
class DispatchMetrics:
    """Accumulates workforce utilisation KPIs across one dispatch run."""

    max_concurrency: int = 1
    total_packages: int = 0
    completed: int = 0
    failed: int = 0
    blocked: int = 0
    main_completed: int = 0
    worker_completed: int = 0
    wall_clock_seconds: float = 0.0
    serial_sum_seconds: float = 0.0
    wait_times: dict[str, float] = field(default_factory=dict)
    ticks: list[TickSample] = field(default_factory=list)
    provider_usage: dict[str, int] = field(default_factory=dict)
    cost_class_usage: dict[str, int] = field(default_factory=dict)

    # ---- recording -----------------------------------------------------------

    def record_tick(self, ready_frontier_size: int, in_flight: int, queue_depth: int,
                    waiting_ready: int = 0, provider_capped: int = 0) -> None:
        self.ticks.append(TickSample(
            tick=len(self.ticks),
            ready_frontier_size=ready_frontier_size,
            in_flight=in_flight,
            queue_depth=queue_depth,
            waiting_ready=waiting_ready,
            provider_capped=provider_capped,
        ))

    def record_wait(self, package_id: str, wait_seconds: float) -> None:
        self.wait_times[package_id] = wait_seconds

    def record_completion(
        self,
        *,
        by_main: bool,
        duration_seconds: float,
        resolved_logical: str | None = None,
        cost_class: str | None = None,
        failed: bool = False,
    ) -> None:
        if failed:
            self.failed += 1
            return
        self.completed += 1
        self.serial_sum_seconds += max(duration_seconds, 0.0)
        if by_main:
            self.main_completed += 1
        else:
            self.worker_completed += 1
        if resolved_logical:
            self.provider_usage[resolved_logical] = self.provider_usage.get(resolved_logical, 0) + 1
        if cost_class:
            self.cost_class_usage[cost_class] = self.cost_class_usage.get(cost_class, 0) + 1

    # ---- derived KPIs ----------------------------------------------------------

    @property
    def delegation_ratio(self) -> float:
        total = self.main_completed + self.worker_completed
        if total == 0:
            return 1.0
        return self.worker_completed / total

    @property
    def main_work_ratio(self) -> float:
        total = self.main_completed + self.worker_completed
        if total == 0:
            return 0.0
        return self.main_completed / total

    @property
    def parallel_efficiency(self) -> float:
        if self.wall_clock_seconds <= 0:
            return 0.0
        return self.serial_sum_seconds / self.wall_clock_seconds

    @property
    def average_wait_time(self) -> float:
        if not self.wait_times:
            return 0.0
        return sum(self.wait_times.values()) / len(self.wait_times)

    @property
    def worker_utilisation(self) -> float:
        if not self.ticks or self.max_concurrency <= 0:
            return 0.0
        return sum(min(t.in_flight, self.max_concurrency) for t in self.ticks) / (
            len(self.ticks) * self.max_concurrency
        )

    @property
    def idle_time_pct(self) -> float:
        return 1.0 - self.worker_utilisation

    @property
    def ready_frontier_sizes(self) -> list[int]:
        return [t.ready_frontier_size for t in self.ticks]

    @property
    def queue_depth_sizes(self) -> list[int]:
        return [t.queue_depth for t in self.ticks]

    @property
    def provider_capacity_limited_events(self) -> int:
        """Count of ready candidates skipped purely by a per-provider cap.

        Expected and ACCEPTABLE (a deliberate throttle to avoid hammering one
        provider) -- informational, not a scheduling failure.
        """
        return sum(t.provider_capped for t in self.ticks)

    @property
    def max_unexplained_idle_ready(self) -> int:
        """The genuine "idle capable slot while ready work exists" signal.

        Positive only when a tick had FREE capacity (in_flight < max_concurrency)
        AND ready candidates were left waiting for a reason OTHER than a
        provider cap (waiting_ready > provider_capped). Under correct
        scheduler operation this is always 0 -- dependency-blocked waiting
        and provider-cap throttling are both excluded by construction. See
        core/anti_regression.py::check_no_idle_while_ready /
        run_dispatch_gates().
        """
        worst = 0
        for t in self.ticks:
            free_capacity = self.max_concurrency - t.in_flight
            unexplained_waiting = t.waiting_ready - t.provider_capped
            if free_capacity > 0 and unexplained_waiting > 0:
                worst = max(worst, unexplained_waiting)
        return worst

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["delegation_ratio"] = self.delegation_ratio
        d["main_work_ratio"] = self.main_work_ratio
        d["parallel_efficiency"] = self.parallel_efficiency
        d["average_wait_time"] = self.average_wait_time
        d["worker_utilisation"] = self.worker_utilisation
        d["idle_time_pct"] = self.idle_time_pct
        return d
