# Subscription & Cost Strategy

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

Extends the S024 two-currency insight (`docs/LISAOS/COST_OPTIMISATION_REPORT.md`) into an operational spending policy for the 3.0 workforce.

---

## 1. Two currencies, not one number

The root cause of the DeepSeek monoculture was a single `cost_tier` scalar that treated all spend as the same money. It is not. LisaOS has **two economically distinct currencies**:

| | **Perishable subscription capacity** | **Elastic API spend** |
|---|---|---|
| Providers | Claude (claude-cli), OpenAI (ChatGPT/Codex), Z.AI Coding Plan | DeepSeek (custom-api), DeepInfra |
| Marginal cost in-quota | ≈ £0 | pay-per-token |
| If unused | **destroyed at reset** (lost forever) | nothing lost |
| If over-used | throttled / limited | linear £ |
| Correct instinct | **spend it — idle quota is waste** | conserve — every token is £ |

**The scalar was wrong because it made subscription look "expensive" (high tier) and DeepSeek look "free" (zero tier).** In reality subscription in-quota is the *cheapest* money and idle quota is *pure loss*. 3.0 encodes both currencies explicitly.

## 2. The spend order (policy)

Per packet, the dispatcher spends in this order, subject to capability and mode:

```
1. Subscription capacity that would otherwise perish   (Claude, OpenAI, GLM — if in quota & capable)
2. Cheapest elastic API that satisfies the capability   (DeepInfra/GLM-if-metered/DeepSeek)
3. Premium subscription for irreversible/architecture    (Opus — scarce, guarded)
```

Rule of thumb: **"Subscription Before API Spend"** — but with a nuance the scalar missed: *guard the scarce premium subscription (Opus) while freely spending the abundant ones (Sonnet/Haiku/GLM/Codex)*. Not all subscription capacity is equally scarce.

## 3. Capacity classes (verified providers)

| Provider | Currency | Scarcity | Spend posture |
|---|---|---|---|
| Claude Opus | Subscription | **Scarce** (high-value, quota-limited) | Guard — irreversible/architecture only |
| Claude Sonnet | Subscription | Abundant | Spend freely for engineering |
| Claude Haiku | Subscription | Abundant | Spend freely for microtasks |
| OpenAI GPT/Codex | Subscription | Moderate (**GPT limits fast** on long runs) | Bursts + sandboxed code; not long-running main |
| Z.AI GLM | Subscription | Abundant (under-used) | **PROBATIONARY** — validate before reliance; low-risk packets only; **retire if it fails validation**; no critical work until proven |
| DeepSeek (custom-api) | Elastic API | n/a | Default long-running main; cheap per token |
| DeepInfra | Elastic API | n/a | Large-context mechanical; metered |
| ~~Alibaba Qwen~~ | — | — | **REMOVED** from workforce (`18`) — 403-prone; huge-context → DeepSeek-V4-Flash / gpt-5.4-pro |

## 4. Quota awareness (evidence-driven)

The dispatcher cannot spend subscription-first without knowing subscription state. Inputs (all inspectable):
- `openclaw models status` → OAuth expiry (Claude ~8h, OpenAI ~41h observed). Near-expiry → prefer completing subscription work before refresh gap.
- Observed limit/throttle responses → back off a provider, record as a `capacity` event.
- A lightweight **capacity ledger** (per provider: last-seen-healthy, recent throttles, rough remaining budget) updated from runtime evidence, not guessed.

3.0 does **not** need exact quota meters (providers don't expose them cleanly). It needs *directional* awareness: is this provider healthy, near reset, or throttling? — enough to order spend.

## 5. Cost model per employee (Balanced mode)

| Employee | Model | Currency | Relative £/packet |
|---|---|---|---|
| Chief Architect / CTO Reviewer | Opus | Sub (scarce) | high-value, low-volume |
| Senior SW Eng / QA | Sonnet | Sub (abundant) | ≈0 marginal |
| SW Eng / Debugging | Codex (gpt-5.5) | Sub (moderate) | ≈0 marginal, watch limits |
| Microtask / Ops | Haiku / GLM-turbo | Sub (abundant) | ≈0 marginal |
| Documentation | Qwen-DeepInfra | API | low £ |
| Implementation Eng (bulk) | DeepSeek | API | low £ |

**Target mix:** the majority of packets on abundant subscription capacity (Sonnet/Haiku/Codex/GLM), elastic API only for genuine bulk/large-context overflow, Opus only for irreversible judgement.

## 6. Cost KPIs (feed `09`)

| KPI | Definition | Target |
|---|---|---|
| Subscription utilisation | subscription packets ÷ subscription-eligible packets | ≥90% |
| API spend / sprint | £ on elastic providers | trend ↓ per unit work |
| Opus guard ratio | Opus packets ÷ total | ≤10%, all irreversible |
| Wasted-quota events | sprints ending with idle subscription while API was billed | → 0 |
| GLM utilisation | GLM packets ÷ total (was 0) | >0 on **low-risk** packets during probation; only promote if reliability validation passes, else → 0 (retired) |

## 7. The one-line policy

> **Spend perishable capacity before elastic tokens; guard the scarce premium subscription; never let idle quota expire while paying per-token elsewhere.**

This replaces the single `cost_tier` scalar wherever it appears in the registries (see cleanup, `12`).
