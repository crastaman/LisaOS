# CTO Review Report — LisaOS 3.0

**Status:** DESIGN FOR APPROVAL. No implementation.
**Reviewer role:** Acting CTO / external systems architect (self-critical review of the 3.0 design).
**Date:** 2026-07-07

This is the honest critique of the design in documents `00`–`13`. Its job is to find where the design is wrong, over-built, or risky — not to praise it.

---

## 1. Verdict

**Approve the direction; stage the build tightly; do not over-engineer the org.**

The core diagnosis is correct and evidence-backed: LisaOS is slow because the workforce is idle, not because models are slow, and the fix is a delegation-first scheduler with employees decoupled from the main runtime. Phase 0 is nearly pure upside and should proceed on approval. The heavier phases (2–4) carry real complexity risk and must be gated and measured.

## 2. What the design gets right

- **Correct root cause.** "Idle workforce, not slow models" is supported by the architecture, not asserted. The L2/L3 firewall (main coordinates, dispatcher routes) attacks the actual coupling that produced the monoculture.
- **Evidence-based inventory.** Every model/auth claim was read from live OpenClaw state. The three highest-value opportunities (GLM, Haiku, Codex) are **already paid for** — the design correctly reframes the problem as *hiring*, not *spending*. **With the applied corrections, "paid for" is now firmly separated from "trusted":** GLM is probationary, Codex must pass identity validation, and neither is relied upon on the strength of a label.
- **Fail-closed preserved.** Nothing in 3.0 weakens the provider resolver's guarantee. Modes may relax cost, never safety.
- **Reversibility.** Almost everything is additive data (registry entries, mode bundles). The risky parts are explicitly isolated to gated phases.

## 3. Where the design is at risk (the honest part)

### 3.1 🔴 Org elaboration risk — 15 employees is a lot
Sixteen roles across six departments is more org than a solo-operator system may need. **Risk:** ceremony without payoff; roles that never get packets. **Mitigation:** ship Phase 1 with a *minimal* employee set (Chief Architect, Senior/Impl Engineer, QA, Documentation, Microtask, + the three Platform citizens) and let the metrics (`09`) justify adding the rest. Do not build all 15 up front. The org should *grow into* its chart.

### 3.2 🔴 Dispatcher/scheduler is the hardest, riskiest component
The ready-frontier scheduler and graph builder (Phase 2) are where most engineering risk lives, and they gate the spawn-path wiring (already deferred). **Risk:** a buggy scheduler is worse than none — it could deadlock the frontier or over-spawn and self-throttle providers. **Mitigation:** ship behind a flag; keep the current DeepSeek-default path as the fallback until the scheduler proves out on real sprints; hard per-provider concurrency caps from day one.

### 3.3 🟡 "Keep the workforce busy" can fight cost discipline
Maximising utilisation and minimising spend are in tension — spreading packets to keep employees busy can pull work onto more/pricier models than needed. **Mitigation:** utilisation is a *ready-frontier* metric (busy *only when work exists*), never a reason to manufacture work. Cost rules (subscription-first, Opus-guard) dominate utilisation in the assignment algorithm. This ordering must be explicit in code, or the two KPIs will quietly conflict.

### 3.4 🟡 Quota awareness without real meters
The cost strategy leans on "subscription-first", but providers don't expose clean quota meters. **Risk:** the dispatcher *believes* it's spending subscription capacity while actually being throttled onto errors. **Mitigation:** directional health ledger from observed responses (throttle/limit events), not guessed budgets; treat throttling as a fail-closed health signal, not a silent downgrade.

### 3.5 🟡 Learning loop could self-harm if automated
An automatic router that rewires `preferred` bindings from noisy sprint data can oscillate or entrench a lucky early result. **Mitigation:** learning **proposes**, humans/CTO-mode **confirm** (already specified). Keep it that way; do not let scores auto-mutate production routing.

### 3.6 🟡 Dependency on OpenClaw internals
3.0 reads `openclaw.sqlite` tables and alias/auth behaviour that are OpenClaw-version-specific (2026.6.10). **Risk:** an OpenClaw upgrade shifts schema/behaviour. **Mitigation:** treat OpenClaw reads through a thin adapter; the reality-check step re-inspects each sprint rather than caching assumptions.

### 3.7 🟢 Local Ollama is honestly scoped — good
The local strategy correctly refuses to oversell 8 GB. No change needed; just don't let enthusiasm promote local above microtasks later.

## 4. Things I explicitly pushed back on

| Temptation | Ruling |
|---|---|
| Add OpenRouter/proxy for "future models" | **Rejected.** No current capability need; adds a failure surface. Revisit only for a specific unavailable model. |
| Make an 8 GB local model a cheap `main` | **Rejected.** Slower coordination = opposite of the goal. |
| Fix the Alibaba Qwen 403 to keep it as default | **Rejected.** Route to the healthy DeepInfra path; keep Alibaba only as guarded huge-context. |
| Build all 15 employees + all 10 modes in Phase 1 | **Rejected.** Start minimal; grow by evidence. |
| Auto-tuning router | **Constrained.** Propose-only, human-gated. |

## 5. Unresolved questions for the operator

1. **Solo vs team scale** — is LisaOS intended to stay a solo-operator system? If so, trim the org (3.1) more aggressively.
2. **Z.AI plan limits** — GLM is subscription; are there call/rate limits that make "spend freely" unwise at volume? (Ledger will learn this, but a known limit helps.)
3. **DeepSeek credential** — fix the corrupt native key, or abandon native DeepSeek entirely and standardise on `custom-api-deepseek-com`? (Recommend the latter — simpler.)
4. **Approval scope for Phase 2** — the spawn-path wiring is still deferred; 3.0 needs an explicit go/no-go on when that gate opens.

## 5a. Corrections applied (2026-07-07)

Post-review corrections were folded into the design (see `CHANGELOG.md`), all tightening the evidence-before-trust posture this review argued for:
- **GLM → probationary**, with an explicit *retire-on-failure* policy; no critical work pre-validation.
- **Codex/Qwen identity ambiguity** investigated and documented (`15`): the `codex-model-studio` provider is actually Alibaba Qwen. Codex routing is gated on runtime-evidence identity validation.
- **Local AI → future capacity only**, removed from every active-workforce binding and mode rotation.
- **Phase 0 reworked** into an 8-task verify-and-guard phase (identity checks + credential cleanup), not a "quick wins" grab.

These are exactly the guardrails §3 asked for; the design is stronger for them.

## 6. Recommendation

- **Approve Phase 0 now** — but note it is now a *verify-and-guard* phase (identity validation, Qwen-alias fix, credential cleanup, probationary GLM), not an unconditional capacity grab. Highest ROI, lowest risk, and nothing is trusted without runtime evidence.
- **Approve Phase 1 as a scoped sprint** with the *minimal* employee set and the `cost_tier` retirement under tests.
- **Hold Phases 2–4** for explicit, individual approval — especially the spawn-path wiring, which remains deferred by prior instruction.
- **Keep the two guarantees inviolate:** fail-closed, and no secret committed.

The design is sound and honest about its own risks. Its biggest danger is not being wrong — it is being *too much*. Build the smallest version that keeps the workforce busy, measure it, and let the organisation earn its complexity.
