# Implementation Roadmap

**Status:** DESIGN FOR APPROVAL. No implementation performed. Sequencing only.
**Date:** 2026-07-07

The order to build LisaOS 3.0, chosen so each phase is independently valuable, testable, reversible, and never regresses the fail-closed guarantee. **Nothing here runs without approval; the OpenClaw spawn-path wiring remains explicitly deferred.**

---

## Guiding rules
- **Additive first.** New registry/data before any behavioural change.
- **Every phase ships tests** (hermetic + one live smoke where a provider is touched).
- **Fail-closed is never weakened** at any phase.
- **Reversible** — each phase is a config/data addition or a guarded code path.

## Phase 0 — Foundation, identity verification & guarded quick wins
*Goal: capture only **evidence-verified** capacity, remove the fragile/ambiguous paths; nothing trusted without runtime proof.*

> **EXECUTED 2026-07-07 — see [`PHASE0_IMPLEMENTATION_REPORT.md`](PHASE0_IMPLEMENTATION_REPORT.md).** 6/8 done (0.1, 0.2, 0.4, 0.5, 0.6, 0.8); tests 24/24. **0.3 partial** — LisaOS registry clean, but live Alibaba-provider removal is **blocked by a WBS dependency** (`wbs-worker-qwen` is pinned to it) and surfaced for decision. **0.7 deferred** — corrupt DeepSeek credential has no safe CLI removal; recommendation recorded.

| # | Task | Deliverable | Risk |
|---|---|---|---|
| 0.1 | **Commit the V3 doc set** | this `docs/LISAOS/V3/` (this action) | 🟢 |
| 0.2 | **Fix Qwen alias → DeepInfra explicit path** (`11`) | OpenClaw `qwen` alias no longer means Alibaba | 🟡 |
| 0.3 | **Investigate & resolve Codex/Qwen identity ambiguity** (`15`) | **LisaOS registry cleaned ✅ (done in validation, `18`)**; live `openclaw.json` rename `codex-model-studio`→`alibaba-model-studio` still pending | 🟡 |
| 0.4 | **Add Haiku as microtask worker — if available** | `claude-haiku` registry entry, `lisa-resolve resolve haiku` = AVAILABLE (else deferred) | 🟢 |
| 0.5 | **Validate Codex *as Codex* with runtime evidence** (`15 §4.3`) | live one-shot proves `codex` = `openai/gpt-5.5`, provider OpenAI (not Qwen) | 🟡 |
| 0.6 | **Add GLM only as PROBATIONARY capacity** (`04`, `06`) | `glm`/`glm-turbo` entries flagged `probation: true`; no critical routing; retire-if-fails policy recorded | 🟡 |
| 0.7 | **Clean corrupted native DeepSeek credential** (`12 §6.1`) | broken `deepseek:default` key fixed or profile removed (fail-closed) | 🔴 |
| 0.8 | **Leave Local AI as future capacity** (`10`) | explicitly NOT installed/hired; roadmap-only | 🟢 |

**Value delivered:** the fragile Qwen path and the Codex/Qwen naming collision are removed; Haiku (if verified) and probationary GLM become hireable under guard; Codex is trusted only after runtime evidence; the corrupt DeepSeek credential is cleaned. **No model is trusted on a label — only on runtime/provider evidence.** No orchestration change yet.

> **Note vs. earlier draft:** GLM is no longer a "🟢 quick win" — it is authenticated but **not yet trusted** (probationary). Codex is not auto-hired; it must pass identity validation (0.5) first. These are the corrections applied in the CHANGELOG.

## Phase 1 — The employee registry (the org becomes real)
*Goal: replace the old runtime abstraction with employees.*

| Task | Deliverable | Risk |
|---|---|---|
| Author `registry/employees.yml` from `02` | employee registry | 🟡 |
| Add `economic_class` + `scarcity` fields; deprecate `cost_tier` | two-currency data (`06`) | 🟡 |
| Migrate `agents.yml` to reference employees, not runtime placeholders | repointed agents | 🔴 |
| Extend `provider_resolver.py` with capability tags + mode-aware `preferred_model` | resolver v3 (additive) | 🟡 |
| Tests: employee→model resolution per mode, fail-closed preserved | passing suite | 🟡 |

**Value delivered:** "hiring a model = registry entry" becomes true; the monoculture-causing `cost_tier` layer retired under tests.

## Phase 2 — Dispatcher & delegation-first loop
*Goal: keep the workforce busy. This is where speed appears.*

| Task | Deliverable | Risk |
|---|---|---|
| Execution-graph builder (packets + deps + capability contracts) | planner v3 | 🔴 |
| Scheduler: ready-frontier assignment + "keep busy" invariant | dispatcher | 🔴 |
| **Wire `lisa-resolve` into the OpenClaw spawn path** (the deferred wiring, `05 §5`) | explicit `model` per spawn, verbatim | 🔴 |
| L2/L3 firewall: main coordinates, dispatcher routes | enforced separation (`07`) | 🔴 |
| Tests: parallel dispatch, scheduling-failure metric, drift = 0 | passing suite + one live multi-provider run | 🔴 |

**Gate:** Phase 2 requires explicit approval to touch the spawn path (currently deferred). Ships behind a flag; DeepSeek-default behaviour remains until the flag is on and tests pass.

## Phase 3 — Dynamic main + modes + metrics
*Goal: phase-aware coordination, policy bundles, and the learning loop.*

| Task | Deliverable | Risk |
|---|---|---|
| MAIN-001 phase→main selection + GPT-not-long-main guard (`07`) | dynamic main | 🔴 |
| Workforce Modes as data (Economy…Local-First) (`08`) | mode bundles | 🟡 |
| Sprint metrics ledger + scorecard in morning brief (`09`) | `sprint_metrics.jsonl` + report | 🟡 |
| Capacity ledger (provider health/quota-direction) (`06 §4`) | health-aware routing | 🟡 |
| o-series import (Research Engineer) (`05`) | registry entries | 🟢 |

**Value delivered:** cost-optimal coordination, situational modes, and measurement of whether delegation is actually happening.

## Phase 4 — Learning, local, and hardening (optional/ongoing)

| Task | Deliverable | Risk |
|---|---|---|
| Learning loop: EMA scores → *proposed* tuning (human-gated) (`09`) | learning store | 🟡 |
| Local Ollama microtask worker (`qwen2.5:3b`), `Local-First` mode (`10`) | local provider (fallback) | 🟡 |
| Retire remaining dead code/docs (🔴 items from `12`) under tests | clean repo | 🟡 |
| Fix corrupt DeepSeek credential (`12 §6.1`) | working/removed profile | 🔴 |

## Dependency graph

```
Phase 0 ──> Phase 1 ──> Phase 2 ──> Phase 3 ──> Phase 4
 (verify &  (employees) (dispatch   (main+modes  (learning,
  guard      +wiring*)    +metrics)   local*)
  capacity)
        \___ cleanup 🟢 ___/        \__ cleanup 🟡/🔴 __/
* spawn-path wiring gated on explicit approval
```

## Anti-regression gates (cross-cutting — `19`)

Regression prevention is not a phase; it is a set of gates woven into every phase so Lisa cannot slide back into old habits (main-does-everything, DeepSeek gravity well, silent fallback, idle workers, stale aliases).

| Phase | Anti-regression capability added |
|---|---|
| **0** | Pre-sprint checks P1–P3 (inventory refresh, workforce verify, **stale-alias guard — already enforced by the resolver suite, `18`**). |
| **1** | Fail conditions F3 (label-without-evidence) + F4 (stale alias) become CI assertions on registry/resolver. |
| **2** | Pre-checks P4/P5 + fail conditions F1 (silent fallback) / F2 (main-does-majority) + post-checks Q1–Q3 + regression tests RT1–RT8 land with the dispatcher. |
| **3** | Post-checks Q4/Q5 (capacity waste) + full KPI scorecard join the metrics ledger (`09`). |

**Gate rule:** post-Phase-2, no sprint is accepted without passing its pre- and post-sprint gates; any hard fail condition (F1/F3/F4/F5) fails the sprint.

## What must NOT happen before approval
- No OpenClaw spawn-path wiring (Phase 2) until explicitly approved — carried over from the prior sprint's standing instruction.
- No 🔴 cleanup (retiring `cost_tier`/runtime layer, fixing the DeepSeek key) outside a tested migration.
- No secret ever committed at any phase.

## Definition of done for 3.0
The success criteria in `00 §8` are met and *held across ≥5 sprints* per the learning loop: delegation ratio ≥0.8, utilisation ≥60%, subscription-first ≥90%, adding a model = registry-only, scheduling failures → 0.
