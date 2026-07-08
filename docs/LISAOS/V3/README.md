# LisaOS 3.0 — Workforce Intelligence & Cleanup Architecture

**Status:** DESIGN FOR APPROVAL — *no implementation performed.*
**Author role:** External LisaOS systems architect
**Date:** 2026-07-07
**Repository:** `~/Lisa` (LisaOS only — WBS untouched)
**Builds on:** S024 architecture (`docs/LISAOS/*.md`) and the provider-resolution fix (`core/provider_resolver.py`, `registry/provider_resolution.yml`).

---

## What this is

LisaOS works, but Lisa still slows down because the **main agent does too much work while capable models sit idle**. LisaOS 3.0 redesigns how Lisa reasons about delegation so that it behaves like an **adaptive engineering organisation**, not a single agent with helpers.

The central shift:

```
OLD:  Provider -> Model
NEW:  Goal -> Execution Graph -> Department -> Employee -> Capability
              -> Model Family -> Exact Model -> Availability -> Cost/Plan -> Runtime
```

Adding a new model must feel like **hiring an employee**, not redesigning the operating system.

## Deliverable map

Every deliverable requested in the brief is covered by the numbered documents below.

| # | Requested deliverable | Document |
|---|---|---|
| 1 | LisaOS 3.0 Workforce Intelligence Architecture | [`00_WORKFORCE_INTELLIGENCE_ARCHITECTURE.md`](00_WORKFORCE_INTELLIGENCE_ARCHITECTURE.md) |
| 2 | Engineering Organisation Design | [`01_ENGINEERING_ORGANISATION_DESIGN.md`](01_ENGINEERING_ORGANISATION_DESIGN.md) |
| 3 | Employee Capability Matrix | [`02_EMPLOYEE_CAPABILITY_MATRIX.md`](02_EMPLOYEE_CAPABILITY_MATRIX.md) |
| 4–5 | Model Family Matrix + Available Model Inventory | [`03_MODEL_INVENTORY_AND_FAMILIES.md`](03_MODEL_INVENTORY_AND_FAMILIES.md) |
| 6 | Missing Model Opportunity Report | [`04_MISSING_MODEL_OPPORTUNITY.md`](04_MISSING_MODEL_OPPORTUNITY.md) |
| 7–8 | Model Import / Integration Plan + OpenClaw Integration Strategy | [`05_MODEL_IMPORT_AND_OPENCLAW_INTEGRATION.md`](05_MODEL_IMPORT_AND_OPENCLAW_INTEGRATION.md) |
| 9 | Subscription & Cost Strategy | [`06_SUBSCRIPTION_AND_COST_STRATEGY.md`](06_SUBSCRIPTION_AND_COST_STRATEGY.md) |
| 10 | Dynamic Main Runtime Strategy | [`07_DYNAMIC_MAIN_RUNTIME.md`](07_DYNAMIC_MAIN_RUNTIME.md) |
| 11 | Delegation-First Operating Model + Workforce Policies (modes) | [`08_DELEGATION_FIRST_AND_WORKFORCE_POLICIES.md`](08_DELEGATION_FIRST_AND_WORKFORCE_POLICIES.md) |
| 12 | Workforce Metrics & Learning Plan | [`09_WORKFORCE_METRICS_AND_LEARNING.md`](09_WORKFORCE_METRICS_AND_LEARNING.md) |
| 13 | Local Ollama Strategy | [`10_LOCAL_OLLAMA_STRATEGY.md`](10_LOCAL_OLLAMA_STRATEGY.md) |
| 14 | Qwen Reliability Plan | [`11_QWEN_RELIABILITY_PLAN.md`](11_QWEN_RELIABILITY_PLAN.md) |
| 15 | LisaOS Cleanup Plan | [`12_CLEANUP_PLAN.md`](12_CLEANUP_PLAN.md) |
| 16 | Implementation Roadmap | [`13_IMPLEMENTATION_ROADMAP.md`](13_IMPLEMENTATION_ROADMAP.md) |
| 17 | CTO Review Report | [`14_CTO_REVIEW.md`](14_CTO_REVIEW.md) |
| + | **Codex/Qwen Identity Ambiguity** (correction investigation) | [`15_CODEX_QWEN_IDENTITY.md`](15_CODEX_QWEN_IDENTITY.md) |
| + | **OpenClaw Model Inventory** (complete, 56 models) | [`16_OPENCLAW_MODEL_INVENTORY.md`](16_OPENCLAW_MODEL_INVENTORY.md) |
| + | **Workforce Coverage Report & Gap Analysis** | [`17_WORKFORCE_COVERAGE_AND_GAP.md`](17_WORKFORCE_COVERAGE_AND_GAP.md) |
| + | **Provider Registry Audit, Cleanup & Integrity Validation** | [`18_PROVIDER_REGISTRY_AUDIT_AND_CLEANUP.md`](18_PROVIDER_REGISTRY_AUDIT_AND_CLEANUP.md) |
| + | **Anti-Regression Framework** | [`19_ANTI_REGRESSION_FRAMEWORK.md`](19_ANTI_REGRESSION_FRAMEWORK.md) |
| + | **Phase 0 Implementation Report** (Alibaba removal, Qwen alias, Haiku, GLM probation, Codex validation) | [`PHASE0_IMPLEMENTATION_REPORT.md`](PHASE0_IMPLEMENTATION_REPORT.md) |
| + | **Phase 1 Implementation Report** (Employee Registry + Workforce Routing Foundation) | [`PHASE1_IMPLEMENTATION_REPORT.md`](PHASE1_IMPLEMENTATION_REPORT.md) |
| + | **Employee Registry Report** | [`20_EMPLOYEE_REGISTRY_REPORT.md`](20_EMPLOYEE_REGISTRY_REPORT.md) |
| + | **Workforce Resolver Report** | [`21_WORKFORCE_RESOLVER_REPORT.md`](21_WORKFORCE_RESOLVER_REPORT.md) |
| + | **Anti-Regression Validation Report** | [`22_ANTI_REGRESSION_VALIDATION_REPORT.md`](22_ANTI_REGRESSION_VALIDATION_REPORT.md) |
| + | **Phase 1 Test Report** (77/77 passing) | [`PHASE1_TEST_REPORT.md`](PHASE1_TEST_REPORT.md) |
| + | **Scheduler Implementation Report** (dependency graph + ready-frontier scheduler) | [`23_SCHEDULER_IMPLEMENTATION_REPORT.md`](23_SCHEDULER_IMPLEMENTATION_REPORT.md) |
| + | **Dispatcher Report** (execution model, concurrency, subscription-first admission, fail-closed, evidence) | [`24_DISPATCHER_REPORT.md`](24_DISPATCHER_REPORT.md) |
| + | **Workforce Utilisation Report** (all required KPIs + a bug found/fixed) | [`25_WORKFORCE_UTILISATION_REPORT.md`](25_WORKFORCE_UTILISATION_REPORT.md) |
| + | **Parallel Execution Report** (measured speedups, success-criterion proof) | [`26_PARALLEL_EXECUTION_REPORT.md`](26_PARALLEL_EXECUTION_REPORT.md) |
| + | **Phase 2 Test Report** (135/135 passing) | [`PHASE2_TEST_REPORT.md`](PHASE2_TEST_REPORT.md) |
| + | **Phase 3 Implementation Report** (Workforce Modes + Capacity Ledger + Policy Engine) | [`PHASE3_IMPLEMENTATION_REPORT.md`](PHASE3_IMPLEMENTATION_REPORT.md) |
| + | **Workforce Modes Report** (9 modes as data, roster/cost policy enforcement) | [`27_WORKFORCE_MODES_REPORT.md`](27_WORKFORCE_MODES_REPORT.md) |
| + | **Capacity Ledger Report** (persistent health/quota memory, thread-safe, no guessing) | [`28_CAPACITY_LEDGER_REPORT.md`](28_CAPACITY_LEDGER_REPORT.md) |
| + | **Subscription Awareness Report** (5 capacity classes, routing preference) | [`29_SUBSCRIPTION_AWARENESS_REPORT.md`](29_SUBSCRIPTION_AWARENESS_REPORT.md) |
| + | **Runtime Health Report** (6 health states, forecasting, fallback recording) | [`30_RUNTIME_HEALTH_REPORT.md`](30_RUNTIME_HEALTH_REPORT.md) |
| + | **Policy Engine Report** (the full mode+ledger flow, zero scheduler changes) | [`31_POLICY_ENGINE_REPORT.md`](31_POLICY_ENGINE_REPORT.md) |
| + | **Phase 3 Test Report** (220/220 passing) | [`PHASE3_TEST_REPORT.md`](PHASE3_TEST_REPORT.md) |
| + | Corrections & validation changelog | [`CHANGELOG.md`](CHANGELOG.md) |

## Ground-truth snapshot (inspected, not assumed) — 2026-07-07

Captured live from `openclaw models list`, `openclaw models status`, `~/.openclaw/openclaw.json`, and host inspection. OpenClaw **2026.6.10**.

**Providers configured & authenticated:**

| OpenClaw provider | Auth (verified) | Economic class | Headline models |
|---|---|---|---|
| `anthropic` (+`claude-cli`) | OAuth, ~8h to expiry | **Subscription** (Claude) | opus-4.8/4.7/4.6, sonnet-4.6, haiku-4.5, fable-5 |
| `openai` | OAuth, ~41h to expiry | **Subscription** (ChatGPT/Codex) | gpt-5.5, gpt-5.5-pro, gpt-5.4(+mini/nano/pro), o1/o3/o4, gpt-5.3-codex |
| `zai` | API key (env `ZAI_API_KEY`) | **Subscription** (Z.AI Coding Plan) — **PROBATIONARY, not yet trusted** | glm-5.2, glm-4.7, glm-5-turbo (+ GLM catalogue) |
| `custom-api-deepseek-com` | API key (ok) | **Elastic API** | deepseek-reasoner (**current global default**) |
| `deepinfra` | API key (ok, `DEEPINFRA_API_KEY`) | **Elastic API** | Qwen3.6-35B-A3B + DeepSeek V3.2/V4-Flash, GLM-5.1, Kimi-K2.5, Llama-3.3-70B, MiniMax-M2.5, Nemotron-3, Step-3.5-Flash |
| `codex-model-studio` | API key (models.json) | **Elastic API (geo-fragile)** | qwen3.7-plus — **Alibaba CN-Hongkong endpoint; alias `qwen`** |
| `deepseek` (native) | **API key CORRUPT** | Broken | deepseek-chat/reasoner/v4-* (unusable — see below) |

**Three defects found during inspection (feed the Cleanup + Qwen + Identity plans):**

1. **Corrupted credential** — the native `deepseek:default` auth profile's API key literally contains the text `"# WBS Do...finement"` (a WBS document was pasted where a key belongs). Native `deepseek/*` models cannot authenticate. The working default is the *separate* `custom-api-deepseek-com` provider, so this has been masked.
2. **`qwen` alias points at the 403-prone backend** — OpenClaw's bare `qwen` alias resolves to `codex-model-studio/qwen3.7-plus` on the Alibaba **China-region** endpoint (`ws-…​.cn-hongkong.maas.aliyuncs.com`), the likely source of the reported Qwen 403s. DeepInfra Qwen (`qwen-deepinfra`) is healthy.
3. **Codex/Qwen identity collision** — the OpenClaw provider block *named* `codex-model-studio` actually serves **Alibaba Qwen** (`qwen3.7-plus`), **not** OpenAI Codex. Real Codex is `openai/gpt-5.5` (codex runtime). This is a misleading-provider-name collision (`15`); Codex is trusted only after runtime-evidence validation.

**Trust posture:** GLM is authenticated but **probationary** (validate before reliance; retire on failure). Codex is validated by **runtime/provider evidence**, never by a label. **No model is trusted on its name.**

**Registry status (validation round, 2026-07-07):** `registry/provider_resolution.yml` cleaned to **6 approved providers** (`deepseek`, `claude-opus`, `claude-sonnet`, `codex`, `gpt`, `qwen-deepinfra`). The **Alibaba Qwen provider was removed** (all `ali-qwen`/`qwen-modelstudio`/`qwen-alibaba` aliases now fail closed); no registry entry references `codex-model-studio`, so `codex` is unambiguously OpenAI. Provider-resolution suite **23/23 green**. Details in `16`–`18`; regression gates in `19`. Live `~/.openclaw` changes (remove Alibaba block, repoint `qwen` alias, fix DeepSeek key) remain Phase-0 tasks.

**Local compute — FUTURE CAPACITY ONLY (not in active workforce):** Ollama **0.30.11** installed, **zero models pulled** — nothing to route to. Host: Apple **M1, 8 GB RAM**, 144 GB free internal SSD, external Thunderbolt SSD (≤1 TB) possible later. Deferred to a future roadmap phase (`10`); Phase 3's `local_future` workforce mode makes this explicit at the policy layer (empty allowed roster — any work routed there fails closed rather than silently substituting a paid employee).

**Phase 3 status (2026-07-08):** `registry/workforce_modes.yml` adds the 9 required workforce modes; `core/capacity_ledger.py` adds a persistent, thread-safe per-provider health/quota/reliability ledger; `core/policy_engine.py` adds a mode- and ledger-aware staffing layer that drops into the Phase 2 `Dispatcher` with **zero changes to `core/dispatcher.py`**. Full suite **220/220 green**. Details in `27`–`31` and `PHASE3_IMPLEMENTATION_REPORT.md`/`PHASE3_TEST_REPORT.md`.

## Reading order

1. Start with **00** (the architecture) and **14** (the CTO review — the honest critique).
2. **03 → 04 → 05** are the model story (what we have, what we're missing, how to add it).
3. **01 → 02 → 07 → 08** are the organisation (employees, dynamic main, delegation & modes).
4. **06 / 09 / 10 / 11** are the economics, learning loop, local strategy, and Qwen fix.
5. **12 → 13** is what to clean up and the order to build it.

**Nothing here is implemented.** All documents describe target state and require approval before any code, registry, or OpenClaw change is made.
