# Phase 1 — Implementation Report

**Status:** Complete. Tests pass. Ready to commit.
**Date:** 2026-07-08
**Scope:** Employee Registry + Workforce Routing Foundation. **No dispatcher/scheduler built** (Phase 2, still gated).
**Repository:** `~/Lisa` only. WBS not touched. OpenClaw not restarted.

---

## 1. Summary

| Deliverable | File | Status |
|---|---|---|
| Employee Registry | `registry/employees.yml` | ✅ 15 employees, validates |
| Workforce Resolver | `core/workforce_resolver.py` | ✅ WorkPackage→employee→physical runtime, fail-closed |
| Anti-Regression Gates | `core/anti_regression.py` | ✅ 7 gates + aggregators |
| Router wiring (additive) | `core/router.py` | ✅ `resolve_work_package()` alongside legacy `choose_engine()` |
| Legacy deprecation marker | `registry/runtimes.yml` | ✅ header marked SUPERSEDED |
| CLI | `bin/lisa-workforce` | ✅ `employees`/`validate`/`assign`/`gates` |
| Tests | `tests/test_workforce_resolver.py`, `tests/test_anti_regression.py` | ✅ 53 new tests |
| **Full suite** | 3 test modules | ✅ **77/77 pass** |

## 2. What was built

### 2.1 Employee Registry (`registry/employees.yml`)
All 15 required employees, each with department, responsibilities, capabilities, preferred model family + exact logical model, fallback models, cost/subscription class, reliability class, best/avoid tasks, and failure policy. Full detail in `20_EMPLOYEE_REGISTRY_REPORT.md`.

### 2.2 Workforce Resolver (`core/workforce_resolver.py`)
Implements exactly the required flow:

```
WorkPackage → Required Capabilities → Candidate Employees (lowest-seniority first)
            → Preferred Model → ProviderResolver → Physical Runtime → Evidence Record (WorkAssignment)
```

- **Capability matching**: candidate = employee whose `capabilities` is a superset of the package's `required_capabilities`.
- **Cost discipline**: candidates sorted lowest-seniority-first (`seniority_ranks` in the registry); the cheapest capable employee is tried first.
- **Fail-closed**: no capable employee → `WorkforceResolutionError` (`no_capable_employee`); no available/compliant model across every candidate's whole chain → `WorkforceResolutionError` (`no_available_model`). DeepSeek is never injected — it only appears when an employee's own declared chain lists it.
- **Explicit, recorded fallback**: an employee's `fallback_models` are tried in order after its preferred model; every fallback taken is recorded (`fallback_from` + `fallback_reason`) on the `WorkAssignment`.
- **Probation enforcement**: a model flagged `probation: true` in `provider_resolution.yml` (GLM, GLM-turbo) is skipped unless `WorkPackage.risk == "low"`.
- **Routing authority**: every `WorkAssignment.routed_by == "workforce_resolver"` — never the main runtime. Full detail in `21_WORKFORCE_RESOLVER_REPORT.md`.

### 2.3 Anti-Regression Gates (`core/anti_regression.py`)
7 pure, independently-testable gates implementing the framework's fail conditions (F1–F5 plus the DeepSeek-gravity-well and idle-worker checks). Pre-sprint and post-sprint aggregators. Full detail in `22_ANTI_REGRESSION_VALIDATION_REPORT.md`.

### 2.4 Retiring the old routing abstraction (in progress, not removed)
- `core/router.py`: the legacy `ENGINES` / `choose_engine()` are now explicitly commented **"LEGACY ROUTING LAYER (superseded — kept for compatibility)"**. The new `resolve_work_package()` / `get_workforce_resolver()` are added alongside, under a **"WORKFORCE ROUTING LAYER (Phase 1 — the new, employee-based path)"** section, with an explicit migration-boundary comment.
- `registry/runtimes.yml`: header block marked **SUPERSEDED**, naming the replacement files and stating it is kept for compatibility only, not for new routing.
- Nothing was deleted. `choose_engine()` and the runtime/cost_tier placeholders still work exactly as before — this is additive, not a breaking change.

### 2.5 CLI (`bin/lisa-workforce`)
Mirrors `bin/lisa-resolve`'s posture (fail-closed, JSON output, exit codes): `employees` (list roster), `validate` (registry validity + model-reference check against the real `ProviderResolver`), `assign <caps> [risk] [mode]` (staff a one-off work package), `gates` (run pre-sprint anti-regression gates). Exit 2 = fail-closed, exit 3 = gate failure.

## 3. Runtime evidence — every work assignment records

Per the brief's requirement, each `WorkAssignment` carries:

| Field | Meaning |
|---|---|
| `employee` | assigned employee |
| `intended_family`, `intended_model` | intended model family / exact logical model (employee's preferred) |
| `resolved_logical` | the logical model actually used (may be a fallback) |
| `physical_model`, `resolved_runtime`, `provider_id` | resolved physical runtime |
| `actual_runtime` | filled post-execution by the dispatcher (Phase 2); drives drift detection |
| `fallback_from`, `fallback_reason` | set only when an explicit fallback was taken |
| `routed_by` | always `"workforce_resolver"` — proof the main runtime didn't choose |
| `evidence_source`, `assigned_at` | provenance / timestamp |

`record_assignment_evidence()` appends each assignment as JSONL to `reports/lisa/workforce_evidence.jsonl` (gitignored, mirrors the existing `provider_resolution_evidence.jsonl` pattern).

## 4. Live verification against the real config

```
$ python3 bin/lisa-workforce validate
employee registry valid: 15 employees, all fields present, all model references known.

$ python3 bin/lisa-workforce assign architecture
  chief-architect -> claude-opus -> anthropic/claude-opus-4-8

$ python3 bin/lisa-workforce assign microtask
  operations-microtask-agent -> claude-haiku -> anthropic/claude-haiku-4-5

$ python3 bin/lisa-workforce assign code-implementation,bulk-mechanical
  implementation-engineer -> deepseek -> custom-api-deepseek-com/deepseek-reasoner

$ python3 bin/lisa-workforce assign documentation,long-context,bulk-mechanical
  documentation-engineer -> qwen-deepinfra -> deepinfra/Qwen/Qwen3.6-35B-A3B

$ python3 bin/lisa-workforce gates
  [OK] no_stale_alias: all 5 retired aliases fail closed
```

## 5. A blocker found and fixed (minimal, not a redesign)

While writing tests for registry-validity failure cases, `EmployeeRegistry._build_employees()` was found to **crash with `KeyError`** on a malformed employee entry (direct `spec["field"]` access) instead of letting `validate()` report the problem cleanly. This defeats the purpose of having a `validate()` method. **Fixed minimally**: construction now uses `spec.get(field, "unknown")` so a malformed registry loads (with placeholder values) and `validate()` — the actual source of truth for validity — reports the missing fields as structured problems instead of the program crashing. No architectural change; this is a robustness fix revealed by test-writing, as anticipated by "do not redesign unless implementation reveals a blocker."

## 6. Test evidence

```
PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_provider_resolution \
    tests.test_workforce_resolver tests.test_anti_regression -v
...
Ran 77 tests in 0.239s
OK
```

24 (provider, pre-existing) + 27 (workforce, new) + 26 (anti-regression, new) = **77/77 pass**. Full detail in `PHASE1_TEST_REPORT.md`.

## 7. Definition of Done — status

| Criterion | Status |
|---|---|
| Employee registry exists and validates | ✅ |
| Work packages resolve to employees, not just providers | ✅ `resolve_work_package()` |
| Provider resolver still produces exact physical runtimes | ✅ unchanged, reused as-is |
| Old routing remains compatible but is clearly superseded | ✅ marked in both `router.py` and `runtimes.yml` |
| Anti-regression checks exist | ✅ 7 gates, tested |
| Tests pass | ✅ 77/77 |
| Repository clean | ✅ only Phase 1 files touched |
| Phase 1 committed | pending this report's commit |

## 8. What Phase 1 deliberately does NOT do

- No scheduler/dispatcher (ready-frontier assignment, parallel execution) — that is Phase 2, still gated pending approval.
- No removal of the legacy `runtimes.yml`/`agents.yml` abstraction — marked superseded, not deleted.
- No OpenClaw spawn-path wiring — `WorkAssignment` produces the physical runtime; actually spawning subagents with it is Phase 2.
- No WBS repository or agent modification.
- No secret committed; no network/provider calls in any test (fully hermetic except the live CLI smoke checks run manually against the real config).

## 9. Files changed

```
A  registry/employees.yml
A  core/workforce_resolver.py
A  core/anti_regression.py
A  bin/lisa-workforce
A  tests/test_workforce_resolver.py
A  tests/test_anti_regression.py
M  core/router.py                (additive: resolve_work_package + legacy marked superseded)
M  registry/runtimes.yml         (header marked superseded, no functional change)
A  docs/LISAOS/V3/PHASE1_IMPLEMENTATION_REPORT.md
A  docs/LISAOS/V3/20_EMPLOYEE_REGISTRY_REPORT.md
A  docs/LISAOS/V3/21_WORKFORCE_RESOLVER_REPORT.md
A  docs/LISAOS/V3/22_ANTI_REGRESSION_VALIDATION_REPORT.md
A  docs/LISAOS/V3/PHASE1_TEST_REPORT.md
M  docs/LISAOS/V3/CHANGELOG.md
```
