# Phase 2 — Test Report

**Status:** All tests pass. **Date:** 2026-07-08
**Command:**
```
PYTHONPATH="$HOME/Lisa" python3 -m unittest discover -s tests -v
```
**Result:** `Ran 135 tests in 0.731s — OK` (0 failures, 0 errors, 0 skipped)

---

## 1. Composition

| Module | Tests | Phase |
|---|---|---|
| `tests.test_provider_resolution` | 24 | Phase 0 (pre-existing, re-run for regression) |
| `tests.test_workforce_resolver` | 27 | Phase 1 (pre-existing, re-run for regression) |
| `tests.test_anti_regression` | 34 | Phase 1 base (26) + Phase 2 additions (8: 4 worker-starvation + 4 run_dispatch_gates) |
| `tests.test_dependency_graph` | 17 | **New (Phase 2)** |
| `tests.test_workforce_metrics` | 20 | **New (Phase 2)** |
| `tests.test_dispatcher` | 13 | **New (Phase 2)** |
| **Total** | **135** | 58 new this phase (78 pre-existing, unchanged and still green) |

## 2. Hermeticity

`test_dependency_graph.py` and `test_workforce_metrics.py` are pure — plain dataclasses, no I/O, no config. `test_dispatcher.py` reuses the hermetic 9-provider `ProviderResolver` fixtures from `tests/test_workforce_resolver.py` (imported directly — `resolver_all_available`, `resolver_no_claude_cli`, `real_employees`) combined with the **real, shipped** `registry/employees.yml`: no network/provider calls, no spend. The default `simulated_executor` used by every dispatcher test sleeps 20ms in-process and never contacts a real model.

## 3. Coverage against the brief's validation requirements

| Required to demonstrate | Covered by |
|---|---|
| Dependency graph generation | `test_dependency_graph.py` (17 tests: construction validation, ready-frontier evolution, failure propagation, summary) |
| Ready frontier scheduling | `TestReadyFrontier` (diamond-graph evolution) + `TestDependencyBlockedWaiting` (dispatcher-level, real dispatch) |
| Parallel execution | `TestParallelExecution` (2 tests: 4-way parallel dispatch, measured `parallel_efficiency > 1.5`; zero unexplained idle) |
| Workforce utilisation tracking | `test_workforce_metrics.py` (20 tests: every required KPI — utilisation, idle%, delegation ratio, parallel efficiency, queue depth, frontier size, main/worker split, wait time) |
| Anti-regression enforcement | `test_anti_regression.py` (34 tests, all 7+2 gates incl. new worker-starvation and `run_dispatch_gates`) + `TestDispatchAntiRegressionGates` (real-dispatch proof) |
| Fail-closed behaviour | `TestFailClosedDispatch` (3 tests: unstaffable package, no-available-model never-DeepSeek, failed-dependency blocks dependents) + `TestExecutorFailure` |

## 4. Full new-test list (Phase 2)

### `test_dependency_graph.py` (17)
```
TestConstructionValidation: valid_graph_constructs, duplicate_id_raises,
  unknown_dependency_raises, self_dependency_raises, two_node_cycle_raises,
  longer_cycle_raises, diamond_shaped_graph_is_valid
TestReadyFrontier: independent_packages_all_ready_immediately,
  dependent_package_not_ready_until_deps_complete,
  in_progress_package_excluded_from_frontier, diamond_frontier_evolution
TestFailurePropagation: failed_package_blocks_direct_dependent,
  failure_propagates_transitively, is_done_true_once_failed_and_blocked_cover_all,
  independent_sibling_unaffected_by_unrelated_failure
TestSummary: summary_counts, remaining_excludes_terminal_states
```

### `test_workforce_metrics.py` (20)
```
TestDelegationAndMainRatio: all_worker_completed_is_full_delegation,
  mixed_completion_ratios, no_completions_defaults_safely,
  failed_completions_excluded_from_ratio
TestParallelEfficiency: efficiency_above_one_when_parallel,
  efficiency_near_one_when_serial, zero_wall_clock_is_safe
TestWaitTimes: average_wait_time, average_wait_time_empty_is_zero
TestUtilisationAndIdle: full_utilisation, partial_utilisation,
  no_ticks_is_zero_utilisation, ready_frontier_and_queue_depth_samples
TestIdleWhileReadySignal: fully_dispatched_tick_is_not_flagged,
  provider_capped_waiting_is_not_flagged,
  unexplained_waiting_with_free_capacity_is_flagged,
  no_free_capacity_is_never_flagged_even_with_backlog,
  provider_capacity_limited_events_summed_across_ticks
TestProviderAndCostClassUsage: usage_counters_accumulate
TestToDict: to_dict_includes_derived_kpis
```

### `test_dispatcher.py` (13)
```
TestParallelExecution: independent_work_dispatched_in_parallel,
  no_unexplained_idle_capacity_while_ready_work_exists
TestDependencyBlockedWaiting: dependent_package_only_completes_after_its_dependencies
TestFailClosedDispatch: unstaffable_package_fails_without_blocking_independent_siblings,
  no_available_model_fails_closed_never_silently_uses_deepseek,
  dependents_of_a_failed_package_become_blocked_not_silently_dropped
TestSubscriptionAwareness: subscription_candidate_admitted_before_elastic_under_contention
TestProviderCapThrottling: provider_cap_throttle_does_not_trip_idle_gate
TestRuntimeEvidence: evidence_recorded_with_required_fields_for_every_execution,
  actual_runtime_matches_resolved_with_default_executor
TestDispatchAntiRegressionGates: healthy_dispatch_passes_all_gates,
  main_never_appears_as_the_executor
TestExecutorFailure: execution_failure_marks_package_failed_and_records_error
```

### `test_anti_regression.py` — Phase 2 additions (8, on top of Phase 1's 26)
```
TestNoWorkerStarvation: pass_no_wait_data, pass_short_waits,
  warn_trending_toward_starvation, fail_genuine_starvation
TestRunDispatchGates: healthy_report_passes, regressed_report_fails_multiple_gates,
  stale_alias_check_included_when_resolver_provided,
  stale_alias_check_omitted_when_no_resolver_given
```

## 5. A real defect found and fixed during test-writing

Building `TestParallelExecution` against a live 4-package dispatch first surfaced that the idle-while-ready detector flagged **every** fully-parallel-dispatched tick as a failure (see `25_WORKFORCE_UTILISATION_REPORT.md §4` for the full root-cause analysis). This was caught precisely *because* the test suite exercised a **real** `Dispatcher.run()` against the **real** registries rather than only unit-testing the gate function with hand-picked inputs — validating the value of the integration-level tests in `test_dispatcher.py`, not just the pure-function tests in `test_workforce_metrics.py`. Fixed in `core/workforce_metrics.py`/`core/dispatcher.py` (see `24 §7`, `25 §4`); five dedicated regression tests (`TestIdleWhileReadySignal`) now pin the corrected behaviour so it cannot silently recur.

## 6. Regression check (Phase 0 + Phase 1)

Both pre-existing suites were re-run **unchanged** and remain fully green:
```
tests.test_provider_resolution: Ran 24 ... OK   (unchanged since Phase 0)
tests.test_workforce_resolver:  Ran 27 ... OK   (unchanged since Phase 1)
```
The two additive dataclass fields introduced this phase (`WorkPackage.depends_on`, `WorkAssignment.duration_seconds`) both default such that every existing call site is unaffected — confirmed by these suites passing without modification.

## 7. Live CLI verification (manual, not part of the automated suite)

```
$ bin/lisa-dispatch run demo_goal.json            # 4 independent + 1 merge step
  graph_summary: completed=5, failed=0
  parallel_efficiency: ~2.16
  gates: all OK
  exit code: 0

$ bin/lisa-dispatch run demo_goal_big.json         # 7 independent + 1 merge step
  graph_summary: completed=8, failed=0
  parallel_efficiency: 3.459
  gates: all OK
  exit code: 0

$ bin/lisa-dispatch run demo_failclosed.json       # 1 impossible capability + 1 blocked dependent
  graph_summary: completed=1, failed=1, blocked=1
  errors: ["bad: No employee provides the required capabilities [...]. Failing closed."]
  exit code: 2
```

## 8. Anti-regression gate status (per the brief's "commit only when anti-regression checks pass")

Every real dispatch run performed for this validation (demonstrations above, plus every automated `test_dispatcher.py` case using the real registries) passed `run_dispatch_gates()` with **zero failures**. The one deliberately-failing scenario (`demo_failclosed.json`) fails on **fail-closed staffing** (exit 2, expected and correct), not on any anti-regression gate (all 9 gates still reported `OK` for that run — the system correctly distinguished "a package couldn't be staffed" from "a regression occurred").

## 9. Conclusion

**135/135 tests pass** (58 new, 77 pre-existing unchanged), every validation item in the brief is demonstrated with real, reproducible numbers (not asserted), and the live CLI independently confirms the same behaviour against the real registries. Safe to commit per "commit only when tests pass, anti-regression checks pass, repository clean."
