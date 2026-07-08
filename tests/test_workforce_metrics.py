"""Proof-of-work tests for LisaOS Workforce Utilisation Metrics (Phase 2).

Validates core/workforce_metrics.py's KPI computations directly against
synthetic data (no dispatcher/network needed) -- worker utilisation, idle
time, delegation ratio, parallel efficiency, queue depth, ready frontier
size, main-vs-worker completion counts, and average wait time.

Run with:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_workforce_metrics -v
"""

import unittest

from core.workforce_metrics import DispatchMetrics


class TestDelegationAndMainRatio(unittest.TestCase):
    def test_all_worker_completed_is_full_delegation(self):
        m = DispatchMetrics()
        for _ in range(5):
            m.record_completion(by_main=False, duration_seconds=1.0)
        self.assertEqual(m.delegation_ratio, 1.0)
        self.assertEqual(m.main_work_ratio, 0.0)

    def test_mixed_completion_ratios(self):
        m = DispatchMetrics()
        for _ in range(3):
            m.record_completion(by_main=False, duration_seconds=1.0)
        for _ in range(1):
            m.record_completion(by_main=True, duration_seconds=1.0)
        self.assertAlmostEqual(m.delegation_ratio, 0.75)
        self.assertAlmostEqual(m.main_work_ratio, 0.25)

    def test_no_completions_defaults_safely(self):
        m = DispatchMetrics()
        self.assertEqual(m.delegation_ratio, 1.0)
        self.assertEqual(m.main_work_ratio, 0.0)

    def test_failed_completions_excluded_from_ratio(self):
        m = DispatchMetrics()
        m.record_completion(by_main=False, duration_seconds=1.0)
        m.record_completion(by_main=False, duration_seconds=0.0, failed=True)
        self.assertEqual(m.completed, 1)
        self.assertEqual(m.failed, 1)
        self.assertEqual(m.delegation_ratio, 1.0)  # failed didn't count as main or worker


class TestParallelEfficiency(unittest.TestCase):
    def test_efficiency_above_one_when_parallel(self):
        m = DispatchMetrics()
        m.record_completion(by_main=False, duration_seconds=1.0)
        m.record_completion(by_main=False, duration_seconds=1.0)
        m.record_completion(by_main=False, duration_seconds=1.0)
        m.wall_clock_seconds = 1.1   # ~3 tasks of 1s each ran mostly in parallel
        self.assertGreater(m.parallel_efficiency, 2.5)

    def test_efficiency_near_one_when_serial(self):
        m = DispatchMetrics()
        m.record_completion(by_main=False, duration_seconds=1.0)
        m.record_completion(by_main=False, duration_seconds=1.0)
        m.wall_clock_seconds = 2.0  # ran back-to-back, no overlap
        self.assertAlmostEqual(m.parallel_efficiency, 1.0)

    def test_zero_wall_clock_is_safe(self):
        m = DispatchMetrics()
        self.assertEqual(m.parallel_efficiency, 0.0)


class TestWaitTimes(unittest.TestCase):
    def test_average_wait_time(self):
        m = DispatchMetrics()
        m.record_wait("a", 0.0)
        m.record_wait("b", 2.0)
        self.assertAlmostEqual(m.average_wait_time, 1.0)

    def test_average_wait_time_empty_is_zero(self):
        m = DispatchMetrics()
        self.assertEqual(m.average_wait_time, 0.0)


class TestUtilisationAndIdle(unittest.TestCase):
    def test_full_utilisation(self):
        m = DispatchMetrics(max_concurrency=4)
        m.record_tick(ready_frontier_size=4, in_flight=4, queue_depth=0)
        m.record_tick(ready_frontier_size=4, in_flight=4, queue_depth=0)
        self.assertEqual(m.worker_utilisation, 1.0)
        self.assertEqual(m.idle_time_pct, 0.0)

    def test_partial_utilisation(self):
        m = DispatchMetrics(max_concurrency=4)
        m.record_tick(ready_frontier_size=2, in_flight=2, queue_depth=0)
        self.assertEqual(m.worker_utilisation, 0.5)
        self.assertEqual(m.idle_time_pct, 0.5)

    def test_no_ticks_is_zero_utilisation(self):
        m = DispatchMetrics(max_concurrency=4)
        self.assertEqual(m.worker_utilisation, 0.0)

    def test_ready_frontier_and_queue_depth_samples(self):
        m = DispatchMetrics()
        m.record_tick(ready_frontier_size=3, in_flight=2, queue_depth=5)
        m.record_tick(ready_frontier_size=1, in_flight=1, queue_depth=2)
        self.assertEqual(m.ready_frontier_sizes, [3, 1])
        self.assertEqual(m.queue_depth_sizes, [5, 2])


class TestIdleWhileReadySignal(unittest.TestCase):
    """The genuine scheduling-failure detector, distinct from legitimate
    provider-cap throttling (see workforce_metrics.py docstring)."""

    def test_fully_dispatched_tick_is_not_flagged(self):
        m = DispatchMetrics(max_concurrency=8)
        # 3 ready, all 3 dispatched (waiting_ready=0) -- healthy, not idle.
        m.record_tick(ready_frontier_size=3, in_flight=3, queue_depth=0,
                     waiting_ready=0, provider_capped=0)
        self.assertEqual(m.max_unexplained_idle_ready, 0)

    def test_provider_capped_waiting_is_not_flagged(self):
        m = DispatchMetrics(max_concurrency=8)
        # 5 ready, 3 dispatched, 2 left waiting -- but both explained by the
        # provider cap. Not a scheduling failure.
        m.record_tick(ready_frontier_size=5, in_flight=3, queue_depth=2,
                     waiting_ready=2, provider_capped=2)
        self.assertEqual(m.max_unexplained_idle_ready, 0)

    def test_unexplained_waiting_with_free_capacity_is_flagged(self):
        m = DispatchMetrics(max_concurrency=8)
        # 5 ready, only 3 in flight (5 free slots!), 2 waiting, NEITHER
        # explained by a provider cap -- a genuine scheduling failure.
        m.record_tick(ready_frontier_size=5, in_flight=3, queue_depth=2,
                     waiting_ready=2, provider_capped=0)
        self.assertEqual(m.max_unexplained_idle_ready, 2)

    def test_no_free_capacity_is_never_flagged_even_with_backlog(self):
        m = DispatchMetrics(max_concurrency=3)
        # Fully saturated (in_flight == max_concurrency); a large backlog is
        # fine -- there simply isn't more room, which is correct behaviour.
        m.record_tick(ready_frontier_size=10, in_flight=3, queue_depth=7,
                     waiting_ready=7, provider_capped=0)
        self.assertEqual(m.max_unexplained_idle_ready, 0)

    def test_provider_capacity_limited_events_summed_across_ticks(self):
        m = DispatchMetrics(max_concurrency=8)
        m.record_tick(ready_frontier_size=5, in_flight=3, queue_depth=2,
                     waiting_ready=2, provider_capped=2)
        m.record_tick(ready_frontier_size=3, in_flight=3, queue_depth=0,
                     waiting_ready=0, provider_capped=0)
        self.assertEqual(m.provider_capacity_limited_events, 2)


class TestProviderAndCostClassUsage(unittest.TestCase):
    def test_usage_counters_accumulate(self):
        m = DispatchMetrics()
        m.record_completion(by_main=False, duration_seconds=0.1,
                            resolved_logical="claude-sonnet", cost_class="subscription-abundant")
        m.record_completion(by_main=False, duration_seconds=0.1,
                            resolved_logical="deepseek", cost_class="elastic-api")
        m.record_completion(by_main=False, duration_seconds=0.1,
                            resolved_logical="deepseek", cost_class="elastic-api")
        self.assertEqual(m.provider_usage, {"claude-sonnet": 1, "deepseek": 2})
        self.assertEqual(m.cost_class_usage, {"subscription-abundant": 1, "elastic-api": 2})


class TestToDict(unittest.TestCase):
    def test_to_dict_includes_derived_kpis(self):
        m = DispatchMetrics(max_concurrency=2)
        m.record_completion(by_main=False, duration_seconds=1.0,
                            resolved_logical="claude-sonnet", cost_class="subscription-abundant")
        m.wall_clock_seconds = 1.0
        d = m.to_dict()
        for key in ("delegation_ratio", "main_work_ratio", "parallel_efficiency",
                   "average_wait_time", "worker_utilisation", "idle_time_pct",
                   "total_packages", "completed", "provider_usage", "cost_class_usage"):
            self.assertIn(key, d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
