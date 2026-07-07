# Phase 1 — Test Report

**Status:** All tests pass. **Date:** 2026-07-08
**Command:**
```
PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_provider_resolution \
    tests.test_workforce_resolver tests.test_anti_regression -v
```
**Result:** `Ran 77 tests in 0.239s — OK` (0 failures, 0 errors, 0 skipped)

Also verified via `python3 -m unittest discover -s tests -v` (full-directory discovery): same 77/77.

---

## 1. Composition

| Module | Tests | New in Phase 1? |
|---|---|---|
| `tests.test_provider_resolution` | 24 | No — pre-existing (Phase 0), re-run to prove no regression |
| `tests.test_workforce_resolver` | 27 | **Yes** |
| `tests.test_anti_regression` | 26 | **Yes** |
| **Total** | **77** | 53 new |

## 2. Hermeticity

Both new modules are fully hermetic:
- `test_workforce_resolver.py` injects a complete 9-provider `ProviderResolver` config (`make_provider_config()`) and multiple `CredentialSource` scenarios (all-available, no-DeepInfra, no-Claude-CLI, none-available) — **no real network/provider calls, no spend**. The one non-injected object is `EmployeeRegistry()` loading the **real, shipped** `registry/employees.yml`, which is intentional: it is what proves the actual registry (not a fixture) is valid and resolvable.
- `test_anti_regression.py` operates on plain `SimpleNamespace` stand-ins and a tiny `_FakeResolver` — the gates are pure functions, so no fixtures beyond simple data are needed.

## 3. Coverage against the brief's required test list

| Required | Covered by |
|---|---|
| Employee registry validity | `TestEmployeeRegistryValidity` (5 tests: count, structural, model-refs, 2 negative controls) |
| Employee resolution | `TestRequiredAssignmentScenarios` (6), `TestFallbackSelection` (2) |
| Capability matching | `TestCapabilityMatching` (4: architecture-only-match, deterministic-excluded, seniority-order, superset-required) |
| Fallback selection | `TestFallbackSelection.test_multihop_fallback_skips_probation_and_records_reason`, `test_no_fallback_when_preferred_available` |
| Fail-closed behavior | `TestFailClosed` (3: no capable employee, no available model + no implicit DeepSeek, fully-unavailable registry) |
| Stale alias rejection | `TestStaleAliasRejection` (2) + `TestNoStaleAlias` in anti-regression (2) |
| GLM probation restriction | `TestGLMProbationRestriction` (3: low-risk uses it, normal-risk fails closed, critical-risk never) |
| Haiku microtask assignment | `test_haiku_microtask_assignment` |
| Sonnet implementation assignment | `test_sonnet_implementation_assignment` |
| Opus architecture assignment | `test_opus_architecture_assignment` |
| Qwen DeepInfra assignment | `test_qwen_deepinfra_documentation_assignment` |
| Codex implementation assignment | `test_codex_implementation_assignment` |
| DeepSeek orchestration assignment | `test_deepseek_orchestration_assignment` |
| Anti-regression: all 7 gates, pass + fail each | `tests/test_anti_regression.py` (26 tests, see `22_ANTI_REGRESSION_VALIDATION_REPORT.md §2`) |

Every item on the brief's test list has a corresponding, passing test.

## 4. Full pass list (workforce + anti-regression, new)

```
test_capability_superset_required ... ok
test_deterministic_employees_never_candidates ... ok
test_only_chief_architect_provides_architecture ... ok
test_seniority_ordering_lowest_first ... ok
test_deterministic_model_chain_excludes_the_sentinel ... ok
test_dispatcher_and_provider_manager_are_deterministic ... ok
test_registry_all_model_references_are_known_providers ... ok
test_registry_detects_duplicate_and_missing_fields ... ok
test_registry_detects_unknown_model_reference ... ok
test_registry_loads_and_has_fifteen_employees ... ok
test_registry_validates_structurally ... ok
test_fully_unavailable_registry_fails_closed ... ok
test_no_available_model_raises_and_never_injects_deepseek ... ok
test_no_capable_employee_raises ... ok
test_multihop_fallback_skips_probation_and_records_reason ... ok
test_no_fallback_when_preferred_available ... ok
test_glm_never_used_for_critical_risk ... ok
test_glm_turbo_skipped_and_fails_closed_on_normal_risk ... ok
test_glm_turbo_used_on_low_risk_when_haiku_unavailable ... ok
test_codex_implementation_assignment ... ok
test_deepseek_orchestration_assignment ... ok
test_haiku_microtask_assignment ... ok
test_opus_architecture_assignment ... ok
test_qwen_deepinfra_documentation_assignment ... ok
test_sonnet_implementation_assignment ... ok
test_employee_referencing_stale_alias_fails_validation ... ok
test_retired_aliases_are_unknown_to_the_hermetic_fixture ... ok

test_assignment_gates_reports_both_checks ... ok
test_post_sprint_gates_fail_on_regressed_sprint ... ok
test_post_sprint_gates_pass_on_healthy_sprint ... ok
test_pre_sprint_gates_fail_on_stale_alias ... ok
test_fail_no_budget_set ... ok
test_fail_overflow ... ok
test_pass_within_budget ... ok
test_fail_deepseek_monoculture ... ok
test_pass_diversified_usage ... ok
test_pass_no_usage_recorded ... ok
test_fail_runtime_drift ... ok
test_pass_actual_matches_resolved ... ok
test_pass_not_yet_executed ... ok
test_fail_majority ... ok
test_pass_low_ratio ... ok
test_warn_trending_high ... ok
test_fail_idle_while_ready_work_exists ... ok
test_pass_no_idle_workers ... ok
test_pass_no_ready_work ... ok
test_fail_fallback_from_without_reason ... ok
test_fail_silent_fallback_no_record ... ok
test_fail_silent_fallback_onto_deepseek_flagged ... ok
test_pass_explicit_recorded_fallback ... ok
test_pass_no_fallback ... ok
test_fail_a_retired_alias_still_resolves ... ok
test_pass_all_retired_aliases_fail_closed ... ok
```

## 5. A defect found and fixed by the test suite

Writing `test_registry_detects_duplicate_and_missing_fields` surfaced a real bug: `EmployeeRegistry._build_employees()` used direct dict indexing (`spec["seniority"]`) and crashed with `KeyError` on a malformed registry, instead of letting `validate()` report the problem. Fixed in `core/workforce_resolver.py` by switching to `spec.get(field, "unknown")` — construction is now lenient (never crashes), and `validate()` remains the single source of truth for whether a registry is actually valid. This is exactly the kind of blocker the task brief anticipated tests might reveal; the fix is minimal and does not change the resolver's design.

## 6. Regression check

The pre-existing 24 provider-resolution tests (Phase 0) were re-run unchanged and still pass, confirming Phase 1's additions did not affect the provider layer:
```
Ran 24 tests ... test_provider_resolution — all ok (unchanged from Phase 0's 24/24)
```

## 7. Live CLI smoke checks (manual, against real registries — not part of the automated suite)

```
$ python3 bin/lisa-workforce validate
employee registry valid: 15 employees, all fields present, all model references known.

$ python3 bin/lisa-workforce assign architecture
  -> chief-architect / claude-opus / anthropic/claude-opus-4-8

$ python3 bin/lisa-workforce assign microtask
  -> operations-microtask-agent / claude-haiku / anthropic/claude-haiku-4-5

$ python3 bin/lisa-workforce assign code-implementation,bulk-mechanical
  -> implementation-engineer / deepseek / custom-api-deepseek-com/deepseek-reasoner

$ python3 bin/lisa-workforce assign documentation,long-context,bulk-mechanical
  -> documentation-engineer / qwen-deepinfra / deepinfra/Qwen/Qwen3.6-35B-A3B

$ python3 bin/lisa-workforce gates
  [OK] no_stale_alias: all 5 retired aliases fail closed   (exit 0)
```

## 8. Conclusion

**77/77 automated tests pass** (53 new + 24 pre-existing, no regressions), every item on the brief's required test list is covered, and the CLI independently confirms the same behaviour live against the real registries. Safe to commit per the "commit only after tests pass" requirement.
