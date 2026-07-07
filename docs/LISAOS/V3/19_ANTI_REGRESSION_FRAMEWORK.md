# Anti-Regression Framework

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07
**Objective:** Ensure Lisa does not regress into old habits after Workforce Intelligence is implemented. Complements the metrics/learning loop (`09`) with hard **gates** — pre-sprint checks, post-sprint checks, and fail conditions that make regression *detectable and blocking*, not silent.

---

## 1. The old habits, and the rule that prevents each

Every regression is a specific old behaviour. Each gets an explicit rule and the mechanism/KPI that enforces it.

| # | Old habit (regression) | Anti-regression rule | Enforced by |
|---|---|---|---|
| R1 | Main agent does most work directly | Main **coordinates**, does not execute delegable packets | `main_agent_work_ratio` KPI + fail condition F2 |
| R2 | DeepSeek becomes the gravity well again | DeepSeek is one explicit choice, never a default sink; subscription-first | `provider_utilisation` + Opus/subscription KPIs; F1 |
| R3 | Provider labels don't match actual runtimes | Every dispatch verified: intended provider == actual runtime | `intended_vs_actual` post-check; F3 |
| R4 | Workers idle while useful work exists | Ready-frontier packets must be assigned to idle capable workers | `idle_worker_time` + `worker_utilisation`; scheduling-failure metric |
| R5 | Sequential execution when parallel possible | Independent frontier packets dispatched concurrently | `parallelism_ratio` KPI |
| R6 | Silent fallback to DeepSeek | Fail closed; any fallback explicit + recorded | `silent_fallback_count` (must be 0); **F1** |
| R7 | Trusting memory over repository truth | Every sprint starts with a repository/inventory reality check | Pre-sprint check P1/P2 |
| R8 | Large reports without context budget checks | Context budget checked before large generation | `context_safety_events`; **F5** |
| R9 | Stale provider aliases left in registry | Registry has no stale/removed aliases | Pre-sprint check P3; **F4** |
| R10 | Opus treated as the only Claude worker; Sonnet/Haiku ignored | Sonnet = first-class engineer; Haiku = microtasks; Opus guarded | `provider_utilisation` spread; Opus-guard KPI |
| R11 | Codex ignored when available | Codex hired for SW-Eng/Debug once identity-validated | `provider_utilisation` (codex share > 0 when available) |
| R12 | Qwen treated as available without live health evidence | Qwen usable only with live health evidence; else fail closed | Pre-sprint check P2 + health ledger; **F3** |

## 2. Measurable KPIs

Computed per sprint from `provider_resolution_evidence.jsonl`, OpenClaw `subagent_runs`, and the sprint ledger (`09`).

| KPI | Definition | Green | Amber | Red |
|---|---|---|---|---|
| **delegation_ratio** | delegated packets ÷ delegable packets | ≥0.80 | 0.60–0.79 | <0.60 |
| **main_agent_work_ratio** | delegable work done by main ÷ total delegable work | ≤0.20 | 0.21–0.40 | >0.40 |
| **provider_utilisation** | distinct providers used ÷ providers that were apt; + per-provider share | ≥3 providers, no single >60% | 1 provider 60–80% | 1 provider >80% (monoculture) |
| **idle_worker_time** | employee-minutes idle while ready work existed | ~0 | some | sustained idle + backlog |
| **fallback_rate** | resolutions using a fallback ÷ total | <0.10 | 0.10–0.25 | >0.25 |
| **silent_fallback_count** | resolutions where actual ≠ intended with no recorded reason | **0** | — | ≥1 (**always red**) |
| **parallelism_ratio** | serial-sum(packet durations) ÷ wall-clock | ≥2.0 | 1.3–1.9 | <1.3 (effectively serial) |
| **context_safety_events** | generations proceeding past the context budget without a check | **0** | — | ≥1 (**always red**) |

Supporting (from `09`): worker_utilisation, subscription_utilisation, opus_guard_ratio, drift count, defect/retry rate.

## 3. Pre-sprint checks (gate: sprint may not start until all pass)

| ID | Check | Pass condition | Maps to |
|---|---|---|---|
| **P1** | **Refresh provider inventory** | `openclaw models list/status` re-read this sprint; snapshot fresh | R7 |
| **P2** | **Verify active workforce** | Every active employee's model resolves AVAILABLE with live auth; Qwen/GLM confirmed by live health, not label | R12, R2 |
| **P3** | **Verify no stale aliases** | No removed alias resolves (`qwen-alibaba`/`ali-qwen`/… → unknown); no provider references `codex-model-studio` | R9 |
| **P4** | **Verify main-runtime policy** | Main selected by phase (`07`); GPT not chosen as long-running main | R1 |
| **P5** | **Verify worker routing independence** | Worker routing goes through the resolver/dispatcher, not the main model (L2/L3 firewall intact) | R1, R3 |

A failed pre-sprint check **blocks the sprint** and surfaces the reason (fail closed at the planning layer).

## 4. Post-sprint checks (gate: sprint not accepted until evaluated)

| ID | Check | Output |
|---|---|---|
| **Q1** | **Intended vs actual runtime** | For every packet: `resolved_model` vs `subagent_runs.model`. Any mismatch → drift report; unexplained mismatch → **F3**. |
| **Q2** | **Worker utilisation report** | worker_utilisation, idle_worker_time, parallelism_ratio; flag R4/R5. |
| **Q3** | **Main vs delegated work** | main_agent_work_ratio + delegation_ratio; flag R1. |
| **Q4** | **Underused prepaid capacity** | Subscription (Claude/OpenAI/GLM) idle while elastic API was billed → flag (wasted-quota event). |
| **Q5** | **Unnecessary API spend** | Elastic spend on work an in-quota subscription model could have done → flag. |

Post-sprint results append to the sprint scorecard (`09`) and drive the learning loop.

## 5. Fail conditions

Severity-graded. **Fail** = sprint marked failed (must remediate/re-run). **Warn** = recorded, escalates to fail on repetition.

| ID | Condition | Severity |
|---|---|---|
| **F1** | **Any silent fallback** (actual ≠ intended, no recorded reason; or implicit DeepSeek substitution) | **FAIL** (hard) |
| **F2** | Main agent performs the **majority of delegable work** (`main_agent_work_ratio` > 0.50) | **FAIL**; 0.40–0.50 = **WARN** |
| **F3** | **Provider label without runtime evidence** — a packet claims a provider not confirmed by `subagent_runs.model`/health | **FAIL** |
| **F4** | **Stale alias selected** — dispatch used a removed/legacy alias | **FAIL** |
| **F5** | **Context overflow** — generation exceeded the context budget without a safety check | **FAIL** |

Escalation: F2-WARN twice in a rolling window promotes to FAIL. All fail conditions are surfaced to the operator with the offending evidence lines.

## 6. Regression test plan

A repeatable, hermetic-where-possible test that simulates a sprint and asserts the workforce behaves. Runs in CI/pre-merge for any dispatcher change; a live variant runs on demand.

**Scenario:** a synthetic sprint with **parallelisable work** — e.g. a goal decomposing into 4 independent implementation packets + 1 dependent QA packet.

| Step | Assertion |
|---|---|
| RT1 | **Work is decomposed** — the graph has >1 packet and a correct dependency edge (QA depends on the 4). |
| RT2 | **Workers assigned by employee/capability** — each packet's employee's capabilities ⊇ its contract; assignment came from the dispatcher, not the main model. |
| RT3 | **Actual runtimes match assignments** — `subagent_runs.model` == resolved model for every packet (drift = 0). |
| RT4 | **Main does not do all implementation** — main_agent_work_ratio ≤ 0.20 in the simulated run; the 4 packets ran on workers. |
| RT5 | **Parallel, not serial** — the 4 independent packets were dispatched on the same frontier tick (parallelism_ratio ≥ 2). |
| RT6 | **No silent fallback** — silent_fallback_count == 0; any fallback has a recorded reason. |
| RT7 | **Completion reports include evidence** — the sprint scorecard contains per-packet intended/actual model, employee, utilisation, and KPI values. |
| RT8 | **Stale-alias guard** — attempting to dispatch a removed alias fails closed (exit 2), reusing the provider-resolution suite. |

Hermetic portions (RT1–RT2, RT6, RT8) use injected fixtures/mocks like `tests/test_provider_resolution.py` (no spend). RT3–RT5, RT7 require a live dispatcher and run as an on-demand smoke sprint once Phase 2 exists.

## 7. Where the gates live in the lifecycle

```
PRE-SPRINT GATE (P1–P5) ──> sprint runs (delegation loop) ──> POST-SPRINT GATE (Q1–Q5)
     │ any fail = block                                            │ any FAIL = sprint failed
     └── refresh inventory, verify workforce, no stale aliases,    └── drift check, utilisation,
         main policy, routing independence                            main-vs-delegated, capacity waste
                                   │
                          KPIs + fail conditions ──> learning loop (09) ──> tuning proposals
```

## 8. Relationship to the metrics plan (`09`)

`09` *measures and learns*; this framework *gates and blocks*. `09`'s scores tune routing over time; the anti-regression gates stop a regressing sprint from being accepted at all. Together: measurement (soft, continuous) + gates (hard, per-sprint). Both draw from the same evidence sources — no new telemetry required beyond the sprint ledger.

## 9. Integration into the roadmap

Anti-regression is not a phase; it is a **cross-cutting gate** added incrementally (see `13`):
- **Phase 0:** pre-sprint checks P1–P3 (inventory refresh, workforce verify, stale-alias guard) are runnable now — P3 is already enforced by the provider-resolution suite (`18`).
- **Phase 1:** F4 (stale alias) + F3 (label without evidence) become CI assertions on the registry/resolver.
- **Phase 2:** P4/P5 + F1/F2 + Q1–Q3 + RT1–RT8 land with the dispatcher (they need the graph/scheduler to exist).
- **Phase 3:** Q4/Q5 (capacity-waste) + full KPI scorecard join the metrics ledger.

No sprint is accepted post-Phase-2 without passing its gates.
