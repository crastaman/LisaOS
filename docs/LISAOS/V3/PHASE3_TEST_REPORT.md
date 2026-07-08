# Phase 3 — Test Report

**Status:** All tests pass. **Date:** 2026-07-08
**Command:**
```
PYTHONPATH="$HOME/Lisa" python3 -m unittest discover -s tests -v
```
**Result:** `Ran 220 tests in 1.346s — OK` (0 failures, 0 errors, 0 skipped)

---

## 1. Composition

| Module | Tests | Phase |
|---|---|---|
| `tests.test_provider_resolution` | 24 | Phase 0 (pre-existing, re-run for regression) |
| `tests.test_workforce_resolver` | 27 | Phase 1 (pre-existing, re-run for regression) |
| `tests.test_anti_regression` | 58 | Phase 1 base (26) + Phase 2 (8) + **Phase 3 (24, new)** |
| `tests.test_dependency_graph` | 17 | Phase 2 (pre-existing, re-run for regression) |
| `tests.test_workforce_metrics` | 20 | Phase 2 (pre-existing, re-run for regression) |
| `tests.test_dispatcher` | 16 | Phase 2 base (13) + **Phase 3 (3, new)** |
| `tests.test_capacity_ledger` | 23 | **New (Phase 3)** |
| `tests.test_workforce_modes` | 22 | **New (Phase 3)** |
| `tests.test_policy_engine` | 13 | **New (Phase 3)** |
| **Total** | **220** | 85 new this phase (135 pre-existing, unchanged and still green) |

## 2. Hermeticity

Every new test file uses hermetic fixtures: `CapacityLedger.in_memory()` or
`CapacityLedger.at_path(tmp)` (never the real default path), the same
9-provider hermetic `ProviderResolver` fixture from `tests/test_workforce_
resolver.py` (imported directly), and the REAL, shipped `registry/employees.
yml` + `registry/workforce_modes.yml` (loaded via their real registry
classes, not fixtures — these two files are the actual configuration LisaOS
runs with). No test performs network I/O, spends money, or writes to any
path outside a `tempfile.TemporaryDirectory()`.

## 3. Coverage against the brief's required test list

| Required to demonstrate | Covered by |
|---|---|
| Each workforce mode | `tests/test_workforce_modes.py` (all 9 present, structurally valid, cross-referenced against the real employee registry; mode-specific roster/policy assertions for economy/premium/architecture/local_future/emergency) |
| Capacity ledger persistence | `TestPersistence` (save+reload via `CapacityLedger.at_path`) + live cross-process CLI demonstration (`28_CAPACITY_LEDGER_REPORT.md §5`) |
| Health state transitions | `TestHealthTransitions` (6 tests: degrade, unavailable-after-3, recovery, probation-aware-recovery, bounded history, disable/enable, quarantine) |
| Subscription vs API routing | `TestSeeding` (cost-class ground truth) + `tests/test_workforce_modes.py::TestPermitsCostClass` (5 tests) + `tests/test_policy_engine.py::TestModeCostPolicy` |
| Exhausted runtime exclusion | `TestExhaustionForecasting` (4 tests) + `tests/test_policy_engine.py::test_exhausted_with_unknown_reset_excluded_by_default` / `test_emergency_mode_allows_exhausted_capacity` |
| Probationary GLM restrictions | `TestIsUsable::test_probationary_only_usable_for_low_risk` + `tests/test_policy_engine.py::test_dynamic_quarantine_restricts_to_low_risk` (generalises beyond just GLM) |
| Unavailable provider exclusion | `TestIsUsable::test_unavailable_never_usable` + `tests/test_policy_engine.py::test_unavailable_ledger_entry_alone_forces_fallback_with_all_providers_healthy` (ledger excludes even when the provider is live-credentialed) |
| Mode policy enforcement | `tests/test_policy_engine.py::TestModeRosterRestriction` (3) + `tests/test_anti_regression.py::TestModePolicyRespected` (5) + `TestSubscriptionApiPolicyRespected` (3) |
| Fallback recording | `tests/test_policy_engine.py` fallback_reason assertions throughout + `check_no_silent_fallback` (Phase 1, reused, still enforced via `run_policy_gates`) |
| Fail-closed behaviour | `TestUnknownMode`, `TestModeRosterRestriction` (including `local_future` always failing), `TestFailClosed` (Phase 1, unchanged) |
| Scheduler integration with capacity ledger | `tests/test_dispatcher.py::TestCapacityLedgerSchedulerIntegration` (3 tests: real `Dispatcher.run()` through `PolicyEngine` + `ledger_recording_executor`, mode-restricted dispatch, ledger-exclusion-under-real-dispatch) |

## 4. Full new-test list (Phase 3)

### `test_capacity_ledger.py` (23)
```
TestSeeding: unknown_provider_seeds_healthy_elastic_api, known_seed_cost_classes_match_ground_truth,
  glm_seeds_probationary, repeat_get_returns_same_entry_object
TestPersistence: save_and_reload_preserves_entries, in_memory_ledger_never_touches_disk
TestHealthTransitions: single_failure_degrades, three_consecutive_failures_marks_unavailable,
  success_resets_consecutive_failures_and_recovers, probationary_provider_recovers_to_probationary_not_healthy,
  failure_history_bounded, disable_and_enable, quarantine_marks_dynamic_probation
TestExhaustionForecasting: unknown_reset_time_never_auto_recovers, known_past_reset_time_auto_recovers,
  known_future_reset_time_stays_exhausted, explicit_success_clears_exhaustion_regardless_of_forecast
TestIsUsable: healthy_is_usable, unavailable_never_usable, disabled_never_usable,
  exhausted_not_usable_unless_allowed, probationary_only_usable_for_low_risk
TestThreadSafety: concurrent_failure_recording_is_exact
```

### `test_workforce_modes.py` (22)
```
TestRegistryLoadsAndValidates: all_nine_required_modes_present, exactly_nine_modes_shipped,
  validates_structurally_with_no_problems, all_referenced_employees_exist_in_real_registry,
  unknown_mode_raises, validate_detects_missing_required_mode, validate_detects_unknown_employee_reference
TestModeSpecificPolicy: local_future_allows_no_employees, architecture_restricted_to_office_of_cto,
  economy_excludes_chief_architect, premium_excludes_bulk_employees, balanced_has_no_roster_restriction,
  only_emergency_allows_exhausted_capacity
TestFilterEmployees: architecture_mode_filters_candidates_to_office_of_cto,
  local_future_mode_filters_everything_out, balanced_mode_is_a_no_op_filter,
  preferred_employees_ordered_first_without_excluding_others
TestPermitsCostClass: subscription_only_mode_rejects_elastic_api, forbidden_api_spend_rejects_elastic_api,
  allow_metered_mode_permits_elastic_api, subscription_classes_always_permitted, none_cost_class_is_permitted
```

### `test_policy_engine.py` (13)
```
TestParityWithPhase1: haiku_microtask_assignment_matches_phase1, deepseek_orchestration_assignment_matches_phase1
TestUnknownMode: unknown_mode_fails_closed
TestModeRosterRestriction: economy_mode_excludes_chief_architect_and_fails_closed,
  architecture_mode_succeeds_for_architecture_work, local_future_mode_always_fails_closed
TestLedgerExclusion: unavailable_ledger_entry_forces_fallback,
  unavailable_ledger_entry_alone_forces_fallback_with_all_providers_healthy,
  exhausted_with_unknown_reset_excluded_by_default, emergency_mode_allows_exhausted_capacity,
  dynamic_quarantine_restricts_to_low_risk
TestModeCostPolicy: architecture_mode_never_lands_on_elastic_api
TestEvidenceFields: assignment_carries_capacity_class_and_health_state
```

### `test_anti_regression.py` — Phase 3 additions (24, on top of Phase 1+2's 34)
```
TestNoUnavailableCapacitySelected: pass_when_healthy, pass_when_no_employee_assigned,
  fail_when_unavailable, fail_when_disabled
TestNoExhaustedCapacityUnlessAllowed: pass_when_healthy, fail_when_exhausted_and_not_allowed,
  pass_when_exhausted_and_explicitly_allowed
TestProbationaryNotCritical: pass_probationary_on_low_risk, fail_probationary_on_critical_risk,
  fail_probation_cost_class_on_critical_risk_even_if_health_healthy, pass_non_probationary_on_critical_risk
TestModePolicyRespected: pass_when_employee_in_allowed_roster, fail_when_employee_not_in_allowed_roster,
  pass_when_mode_unrestricted, fail_when_mode_unresolvable, pass_when_no_employee_assigned
TestSubscriptionApiPolicyRespected: pass_when_subscription_class_under_subscription_only_mode,
  fail_when_elastic_api_under_subscription_only_mode, pass_when_elastic_api_under_allow_metered_mode
TestRunPolicyGates: healthy_report_passes_all_policy_gates, mode_violation_is_caught,
  exhausted_capacity_caught_unless_emergency_mode, probationary_critical_work_caught,
  still_runs_underlying_dispatch_gates
```

### `test_dispatcher.py` — Phase 3 additions (3, on top of Phase 2's 13)
```
TestCapacityLedgerSchedulerIntegration: dispatch_through_policy_engine_updates_ledger_on_real_execution,
  mode_restricted_dispatch_never_uses_disallowed_employee,
  ledger_exclusion_prevents_selection_even_when_provider_credentialed
```

## 5. Regression check (Phase 0 + Phase 1 + Phase 2)

All three pre-existing suites were re-run **unchanged** and remain fully
green: `test_provider_resolution` (24), `test_workforce_resolver` (27),
`test_dependency_graph` (17), `test_workforce_metrics` (20). The two new
additive `WorkAssignment` fields introduced this phase (`capacity_class`,
`health_state`) both default to `None`, so every Phase 1/2 call site is
unaffected — confirmed by these suites passing without any modification.
`core/dispatcher.py` was not modified at all this phase (verified by `git
diff` showing zero changes to that file).

## 6. No structural bug found this phase

Unlike Phase 2 (which surfaced and fixed a real idle-while-ready false
positive), Phase 3's new modules passed their full test suites on first
execution with no design correction required. The one issue encountered was
a demo-script mistake during live verification (passing a `str` instead of a
`Path` to `CapacityLedger.at_path`, which raised `AttributeError` immediately
and loudly — exactly the fail-closed behaviour wanted from a type contract,
not a defect in the library). Recorded here for completeness rather than
silently omitted.

## 7. Live CLI verification (manual, not part of the automated suite)

See `27_WORKFORCE_MODES_REPORT.md §5`, `28_CAPACITY_LEDGER_REPORT.md §5`,
`30_RUNTIME_HEALTH_REPORT.md §6`, and `31_POLICY_ENGINE_REPORT.md §6` for the
full set of real, reproducible `bin/lisa-dispatch` runs (mode-blocked,
mode-succeeded, local_future-always-fails, mixed-mode dispatch, ledger-
persistence-across-processes, exhausted-blocked-vs-explicitly-allowed) — every
one against the real `registry/employees.yml`, `registry/provider_resolution.
yml`, and `registry/workforce_modes.yml`, with every anti-regression gate
checked and reported `OK` in every case where staffing succeeded.

## 8. Conclusion

**220/220 tests pass** (85 new, 135 pre-existing unchanged), every validation
item in the brief is demonstrated with real, reproducible evidence (not
asserted), and `core/dispatcher.py` required zero modification. Safe to
commit per "commit only when tests pass, anti-regression gates pass,
repository is stable."
