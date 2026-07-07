# Model Import / Integration Plan & OpenClaw Integration Strategy

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

How LisaOS adds a model safely, and how LisaOS integrates with OpenClaw as the execution substrate. The governing rule: **importing a model is an onboarding procedure, not a code change.**

---

## 1. OpenClaw is the substrate — LisaOS does not replace it

Verified facts (OpenClaw 2026.6.10):
- OpenClaw already resolves providers, honours an explicit `model` per spawn, manages auth profiles (OAuth + API key), and exposes runtimes `claude-cli`, `codex`, `openclaw`, and (via Ollama) local.
- The provider-resolution fix already binds LisaOS logical names → OpenClaw physical models and **fails closed**.

So LisaOS 3.0 integrates *on top of* OpenClaw. It does **not** re-implement provider management. The division of labour:

| Concern | Owner |
|---|---|
| Credential storage, OAuth refresh, HTTP to providers | **OpenClaw** |
| Physical model catalogue, runtimes | **OpenClaw** |
| Logical→physical map, capability tags, fail-closed policy | **LisaOS** (`provider_resolution.yml` + `provider_resolver.py`) |
| Employee→model binding, modes, scheduling | **LisaOS** (3.0 additions) |
| Writing the explicit `model` into each spawn payload | **LisaOS dispatcher** (the deferred wiring) |

## 2. The four integration questions for any model

Before importing a model, answer (this is the "interview"):

1. **Exact model name** — as it appears in `openclaw models list` (e.g. `zai/glm-5.2`). Never a guessed name.
2. **Provider & auth** — which OpenClaw provider block; OAuth vs API key; which env var / profile. Confirmed via `openclaw models status`.
3. **Runtime** — `claude-cli` / `codex` / `openclaw` / `ollama`.
4. **Native vs proxy** — does OpenClaw reach it directly (all current cases), or does it need OpenAI-compatible routing / OpenRouter / a custom provider block?

Decision tree for #4:

```
Is the model in `openclaw models list`?
  ├─ Yes, `configured` + auth ok      -> import: registry entry only.           (GLM, Haiku, Codex, o-series)
  ├─ Yes, not configured              -> configure provider/auth in OpenClaw,   (DeepInfra catalogue)
  │                                       then registry entry.
  └─ No, but OpenAI-compatible API    -> add a custom provider block to
                                          openclaw.json (like custom-api-deepseek-com),
                                          then registry entry.
Needs a non-native, non-OpenAI-compatible endpoint?
  └─ Only then consider OpenRouter/proxy — adds a failure surface; justify explicitly.
```

**Current reality:** every model LisaOS needs is in the first two branches. **No proxy/OpenRouter is required for 3.0.**

## 3. The import runbook (safe, ordered, reversible)

For each model, in order. Steps 1–2 are OpenClaw-side (only if not already configured); 3–6 are LisaOS-side.

1. **Confirm availability** — `openclaw models list | grep <model>`; confirm auth in `openclaw models status`. Evidence before assumption.
2. **(If unconfigured) configure in OpenClaw** — add provider block / run `openclaw models auth login|paste-api-key`. **Secrets via env only; never committed.** Back up `openclaw.json` first (as done for DeepInfra).
3. **Add to `registry/provider_resolution.yml`** — logical name, `physical_model`, `runtime`, `provider_id`, `credential` descriptor, `capabilities`, `role_hint`. Single unambiguous identity (no bare-name collisions — the Qwen lesson).
4. **Verify resolution** — `bin/lisa-resolve resolve <name>` → AVAILABLE, correct physical model, correct runtime. UNAVAILABLE if key absent (fail-closed check).
5. **Smoke test (elastic/new providers)** — one real call via a `smoke_<provider>.py` (pattern from `smoke_deepinfra.py`): logical→physical→backend→response→evidence. Fail-closed on no key.
6. **Hire** — add the model as `preferred`/`fallback` on the relevant employees in `registry/employees.yml`. Probation: low-risk packets first (`09`).

**Reversibility:** every step is a config addition. Remove the registry entry to un-hire; the model reverts to unused. No orchestration code changes.

## 4. Concrete import specs (from `04`)

### Z.AI GLM — import now
```
# registry/provider_resolution.yml (proposed)
glm:                    # Ops/bulk/docs subscription worker
  physical_model: zai/glm-5.2
  runtime: openclaw
  provider_id: zai
  role_hint: bulk-mechanical-subscription
  credential: { type: api_key, env: ZAI_API_KEY, openclaw_provider: zai }
  capabilities: [bulk-mechanical, documentation, microtask]
  aliases: [glm-5, glm-coding]
glm-turbo:              # low-latency ops microtasks
  physical_model: zai/glm-5-turbo
  runtime: openclaw
  provider_id: zai
  credential: { type: api_key, env: ZAI_API_KEY, openclaw_provider: zai }
  capabilities: [microtask, bulk-mechanical]
```
Smoke: `smoke_zai.py` (one call to the Z.AI OpenAI-compatible endpoint). No secret committed.

### Anthropic Haiku — import now
```
claude-haiku:
  physical_model: anthropic/claude-haiku-4-5
  runtime: claude-cli
  provider_id: anthropic
  role_hint: microtask-subscription
  credential: { type: oauth, provider: claude-cli }
  capabilities: [microtask, documentation]
  aliases: [haiku]
```
No smoke call needed (inherits verified Claude OAuth); verify via `lisa-resolve resolve haiku`.

### OpenAI o-series — Phase 2
```
o3:
  physical_model: openai/o3
  runtime: openclaw
  provider_id: openai
  role_hint: deep-research
  credential: { type: oauth, provider: openai }
  capabilities: [deep-reasoning, research, review]
o3-deep-research:
  physical_model: openai/o3-deep-research
  runtime: openclaw
  provider_id: openai
  credential: { type: oauth, provider: openai }
  capabilities: [research, deep-reasoning]
```

### DeepInfra specialists — on demand
`deepseek-v4-flash` (`deepinfra/deepseek-ai/DeepSeek-V4-Flash`, `huge-context, bulk-mechanical`); `kimi-vision` (`deepinfra/moonshotai/Kimi-K2.5`, `vision, long-context`). Same DeepInfra credential already working.

## 5. OpenClaw integration strategy (the wiring — deferred)

The one piece of *execution* wiring still pending approval (from the prior sprint): make the OpenClaw dispatch path call `lisa-resolve payload <employee/provider> "<task>"` and spawn the subagent with the returned payload **verbatim**, preserving the explicit `model`. Contract (unchanged from `PROVIDER_RESOLUTION_FIX_REPORT.md §4`):

1. Resolve per packet → payload with explicit `model` + `_lisa_resolution`.
2. Exit ≠ 0 → **do not spawn** (fail closed).
3. Spawn subagent with payload verbatim.
4. After completion, set `actual_model` from `subagent_runs.model`; record evidence; flag drift.

3.0 adds one thing to this contract: the *employee* and *mode* that produced the resolution are recorded in the evidence, so the learning loop (`09`) can attribute outcomes to roles and policies.

**This wiring remains deferred pending explicit approval** (per the prior sprint's instruction). Everything in this document is design only.

## 6. Import governance

- **No secret ever committed** — env vars / OpenClaw auth store only; `.env.example` documents names, never values.
- **Single unambiguous identity per logical name** — the Qwen disambiguation rule is permanent policy.
- **Fail closed on import** — a newly imported model with no credential resolves UNAVAILABLE, never silently substituted.
- **Probation before promotion** — new models earn `preferred` status through metrics, not assertion.
