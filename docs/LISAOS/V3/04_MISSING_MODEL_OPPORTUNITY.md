# Missing Model Opportunity Report

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

"Missing" here means: **useful capacity that OpenClaw can see or reach but LisaOS cannot currently hire**, or that is worth importing. Ranked by value-to-effort. The biggest opportunities are not new purchases — they are **already-paid-for models LisaOS is ignoring.**

---

## 1. Priority ladder (value ÷ effort)

| Rank | Opportunity | Type | Why it matters | Effort | Add when |
|---|---|---|---|---|---|
| **1** | **Z.AI GLM (glm-5.2 / 4.7 / 5-turbo)** — **PROBATIONARY** | Authenticated, **not yet trusted** | Paid subscription that *may* be wasted capacity — but **authenticated ≠ validated.** Add as candidate/probationary only; prove reliability before any real reliance. | Low (registry entry, flagged `probation`) | **Now, as candidate only** |
| **2** | **Anthropic Haiku 4.5** | In catalogue, subscription | Subscription-cheap microtask worker → keeps Opus/Sonnet free. Fills the "cheap but subscription" gap DeepSeek currently mis-fills. | Low | **Now** |
| **3** | **OpenAI Codex (gpt-5.5 via codex runtime / gpt-5.3-codex)** | Configured runtime, under-used | Premium sandboxed engineering worker already available via `codex` runtime. Under-hired today. | Low (already resolvable) | **Now** |
| **4** | **DeepInfra Qwen (qwen-deepinfra)** | Configured, healthy | The *reliable* Qwen path vs the 403-prone Alibaba one. Already in registry — needs promotion to default `qwen` role. | None | **Now** (see `11`) |
| **5** | **OpenAI o-series (o3, o4-mini, o3-deep-research)** | In catalogue, subscription | Deep-reasoning + research capability the org currently lacks a home for (Research Engineer). | Low | Phase 2 |
| **6** | **DeepInfra DeepSeek-V4-Flash (1024k)** | In catalogue, elastic | Huge-context elastic worker; cheap flash tier for large-doc mechanical work. | Low | Phase 2 (on demand) |
| **7** | **DeepInfra Kimi-K2.5 (vision, 256k)** | In catalogue, elastic | Only strong non-Anthropic **vision** option; enables image/screenshot packets off subscription. | Medium | On demand |
| **8** | **GPT-5.5-pro / gpt-5.4-pro (≈1M ctx)** | In catalogue, subscription | Huge-context premium for rare giant-context synthesis. | Low | On demand |
| **9** | **DeepInfra Llama-3.3-70B / MiniMax-M2.5 / Nemotron-3 / Step-3.5-Flash** | In catalogue, elastic | OSS/specialist bench for benchmarking + fallback diversity (avoid monoculture). | Low each | As needed |
| **10** | **Local Ollama models** (qwen2.5:3b, llama3.2:3b) | Not pulled | Offline microtask/redaction fallback. Constrained by 8GB (see `10`). | Medium | Phase 3 (optional) |

## 2. Detail on the top opportunities

### #1 — Z.AI GLM (highest *potential* value — but PROBATIONARY, not trusted)
- **Models:** `zai/glm-5.2` (default), `zai/glm-4.7` (fallback), `zai/glm-5-turbo` (low-latency), plus GLM-5.1/5/4.7-flash catalogue.
- **Provider:** `zai`, base `https://open.bigmodel.cn/api/coding/paas/v4`, auth via `ZAI_API_KEY` (**already set** in env + models.json).
- **Trust status:** **Authenticated but NOT validated.** GLM is a *candidate*, not a confirmed workforce member. Being logged-in proves nothing about reliability, quality, or rate limits.
- **Expected (potential) role, once validated:** Ops Engineer (glm-5-turbo), Documentation Engineer fallback, bulk Implementation fallback.
- **Value *if it passes*:** It is a subscription (Z.AI Coding Plan) — marginal cost ≈ £0 per call. Every packet GLM absorbs is a packet not billed to elastic API. But this benefit is only real if GLM proves stable.
- **How to add (as probation):** Add `glm` / `glm-turbo` to `registry/provider_resolution.yml` with `credential.type: api_key, env: ZAI_API_KEY`, capability tags `bulk-mechanical, microtask, documentation`, and **`probation: true`**.
- **Explicit policy — retire on failure:** GLM runs only low-risk, non-critical packets during probation. Its model performance score accrues (`09`). **If GLM remains unstable or fails reliability validation, it is retired from the active workforce** (removed from employee bindings; provider entry left UNAVAILABLE/disabled). **Never route critical work to GLM until it passes validation.**
- **Add now?** As a *probationary candidate only* — yes. As a trusted worker — not yet.

### #2 — Anthropic Haiku 4.5
- **Model:** `anthropic/claude-haiku-4-5`, runtime `claude-cli`, inherits the Claude OAuth subscription.
- **Role:** Microtask Agent, Ops fallback.
- **Value:** Fills the "cheap *and* subscription" cell. Today microtasks either burn Sonnet/Opus quota or go to elastic DeepSeek. Haiku is near-zero marginal and keeps premium quota for real work.
- **OpenClaw native?** Yes (catalogue, `claude-cli/*` runtime present).
- **How to add:** Provider entry `claude-haiku` → `anthropic/claude-haiku-4-5`, `credential.type: oauth, provider: claude-cli`.
- **Add now?** Yes.

### #3 — OpenAI Codex (hire only after identity validation)
- **Models:** `openai/gpt-5.5` via `codex` runtime (already the `codex` provider in the registry); `openai/gpt-5.3-codex` as a code-specialised alternative in the catalogue.
- **Role:** SW Engineer (preferred), Debugging Specialist.
- **Value:** Sandboxed code execution + patch validation the DeepSeek-heavy org under-uses. Subscription-class.
- **⚠️ Identity guard (`15`):** the OpenClaw provider *named* `codex-model-studio` is actually **Alibaba Qwen**, not Codex. Before hiring Codex, confirm with **runtime evidence** that `codex` resolves to `openai/gpt-5.5` (provider OpenAI), never to the Qwen backend. Do not treat any model as Codex on the strength of a name.
- **Add now?** Only after the runtime-evidence validation in Phase 0 (task 0.5). Until then, the SW-Eng role stays on Sonnet/DeepSeek.

### #5 — OpenAI o-series (Research Engineer's home)
- **Models:** `openai/o3`, `openai/o4-mini`, `openai/o3-deep-research`, `openai/o3-pro`.
- **Role:** Research Engineer, deep Debugging.
- **Value:** LisaOS has no deep-reasoning/research specialist today; o-series fills it on subscription.
- **Add when:** Phase 2 (after the org + modes land).

## 3. Deliberately NOT importing (yet)

| Model | Why deferred |
|---|---|
| Native `deepseek/*` | **Auth key corrupt** (WBS text pasted as key). Fix the credential first (`12`); the working DeepSeek is `custom-api-deepseek-com`. Importing native DeepSeek now would add a broken provider. |
| Alibaba `qwen3.7-plus` (any form) | **REMOVED entirely** from the registry (`18`) — 403/geo-fragile CN endpoint + Codex/Qwen naming collision. Huge-context need covered by DeepSeek-V4-Flash / gpt-5.4-pro. |
| OpenRouter / new external proxies | Not needed — every capability we need is reachable via existing providers. Adding a proxy adds a failure surface for no new capability. Revisit only if a specific unavailable model becomes required. |
| Large local models (≥13B) | 8GB RAM cannot host them usefully (`10`). |

## 4. The meta-point

Of the top four opportunities, **three cost nothing new** — they are capacity LisaOS already pays for (GLM subscription, Haiku/Codex on the Claude/OpenAI subscriptions) but never hired. The monoculture was never a budget problem; it was a **hiring** problem.

But "already paid for" is **not** the same as "trusted." Two guards apply before this capacity is relied upon:
- **GLM is probationary** — validated on low-risk work first, retired if it fails.
- **Codex must prove its identity** — the `codex-model-studio` provider is actually Qwen (`15`); Codex is only hired after runtime evidence confirms it is genuinely `openai/gpt-5.5`.

LisaOS 3.0's employee model lets this capacity finally be used — *once each piece is evidence-verified.*
