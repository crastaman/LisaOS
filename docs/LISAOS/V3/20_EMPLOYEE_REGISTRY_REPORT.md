# Employee Registry Report

**Status:** Implemented. **Date:** 2026-07-08
**File:** `registry/employees.yml` (schema `lisaos.registry.employees.v1`)

---

## 1. Purpose

Replaces the *provider→model* mental model with *employee (role)→model*. An employee is a durable role with a preferred model **and** explicit fallbacks; models are referenced by LisaOS logical provider name (`registry/provider_resolution.yml`), so hiring a new model is a registry edit, never an orchestration-code change.

## 2. Roster (15/15 required employees present)

| Employee | Dept | Seniority | Preferred model | Cost class | Reliability |
|---|---|---|---|---|---|
| chief-architect | office-of-cto | principal | claude-opus | subscription-scarce | high |
| cto-reviewer | office-of-cto | principal | claude-opus | subscription-scarce | high |
| senior-software-engineer | engineering | senior | claude-sonnet | subscription-abundant | high |
| software-engineer | engineering | standard | codex | subscription-abundant | high |
| implementation-engineer | engineering | bulk | deepseek | elastic-api | medium |
| qa-engineer | quality | standard | claude-sonnet | subscription-abundant | high |
| debugging-specialist | quality | specialist | codex | subscription-abundant | high |
| research-engineer | research-and-docs | specialist | gpt | subscription-abundant | high |
| documentation-engineer | research-and-docs | bulk | qwen-deepinfra | elastic-api | medium |
| operations-microtask-agent | operations | microtask | claude-haiku | subscription-abundant | high |
| release-manager | operations | standard | gpt | subscription-abundant | high |
| platform-engineer | platform | specialist | claude-sonnet | subscription-abundant | high |
| dispatcher-manager | platform | principal | deterministic | subscription-abundant | high |
| context-manager | platform | bulk | qwen-deepinfra | elastic-api | medium |
| provider-manager | platform | principal | deterministic | subscription-abundant | high |

Every field required by the brief is present per employee: department, responsibilities, capabilities, preferred model family, preferred exact model, fallback models, cost/subscription class, reliability class, best tasks, tasks to avoid, failure policy. (`escalates_to` and `execution` are additional fields the resolver needs — seniority ladder and deterministic-employee marking respectively.)

## 3. Seniority ladder (cost discipline)

```
microtask(1) < bulk(2) < standard(3) < specialist(4) < senior(5) < principal(6)
```
The resolver always tries the **lowest-seniority capable employee first** — e.g. a documentation packet prefers `operations-microtask-agent` (rank 1) over `release-manager` (rank 3) if both happen to qualify, matching "don't put Opus on a docstring."

## 4. Two-currency cost classes (extends `docs/LISAOS/V3/06`)

| Class | Meaning | Employees |
|---|---|---|
| `subscription-scarce` | perishable, guarded (Opus) | chief-architect, cto-reviewer |
| `subscription-abundant` | perishable, spend freely | senior/software-engineer, qa, debugging, research, ops-microtask, release-mgr, platform-eng, dispatcher-mgr, provider-mgr |
| `elastic-api` | pay-per-token | implementation-engineer, documentation-engineer, context-manager |

No employee is bound to GLM as its *preferred* model — GLM only appears in `fallback_models` (implementation-engineer, documentation-engineer, ops-microtask-agent), consistent with its probationary status (`04`/`06`).

## 5. Deterministic employees (routing/infra, not LLM workers)

`dispatcher-manager` and `provider-manager` have `preferred_model: deterministic` and `execution: deterministic` — they represent **code** (the scheduler, the `ProviderResolver`), not an LLM to dispatch work to. `EmployeeRegistry.candidates_for()` explicitly excludes any `is_deterministic` employee from capability matching, so a work package can never accidentally be "staffed" to a piece of infrastructure.

## 6. Escalation ladder (`escalates_to`)

```
operations-microtask-agent → software-engineer → senior-software-engineer → chief-architect
implementation-engineer    → software-engineer → senior-software-engineer → chief-architect
debugging-specialist       → senior-software-engineer → chief-architect
qa-engineer                → debugging-specialist
research-engineer          → chief-architect
```
`cto-reviewer`, `chief-architect`, `dispatcher-manager`, `provider-manager`, `context-manager` have no escalation target (`escalates_to: null`) — they are terminal (top of the ladder, or infra with a deterministic-halt policy).

## 7. Failure policies present

| Policy | Meaning | Used by |
|---|---|---|
| `halt-and-surface` | never downgrade; surface the failure | chief-architect, cto-reviewer |
| `fallback-then-escalate` | try fallback chain, else escalate to a senior role | most engineering/quality/research/ops roles |
| `fallback-within-subscription` | fallback but never escalate above software-engineer | operations-microtask-agent, context-manager |
| `deterministic-halt` | code path halts, no LLM substitution | dispatcher-manager, provider-manager |

## 8. Validation

`EmployeeRegistry.validate()` checks: no duplicate employee ids, all required fields present, non-empty `capabilities`, known `seniority` value, and — when given a live `ProviderResolver` — that every `preferred_model`/`fallback_models` entry resolves to a known logical provider.

```
$ python3 bin/lisa-workforce validate
employee registry valid: 15 employees, all fields present, all model references known.
```

Verified programmatically in `tests/test_workforce_resolver.py::TestEmployeeRegistryValidity` (5 tests: count, structural validity, model-reference validity against the real 9-provider config, and two negative-control tests proving `validate()` actually catches an unknown model reference and missing/duplicate fields).

## 9. Relationship to the legacy registries

`registry/employees.yml` is **additive**. It does not replace `registry/agents.yml` or `registry/runtimes.yml` in this phase — those remain for compatibility, now marked SUPERSEDED (see `PHASE1_IMPLEMENTATION_REPORT.md §2.4`). A later phase may migrate `agents.yml`'s `preferred_runtime`/`fallback_runtimes` fields to point at employees instead of the old runtime placeholders.
