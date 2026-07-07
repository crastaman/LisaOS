# Available Model Inventory & Model Family Matrix

**Status:** DESIGN FOR APPROVAL. Inventory inspected live 2026-07-07 (`openclaw models list`, `openclaw models status`, `~/.openclaw/openclaw.json`). No static trust.

---

## 1. How this was gathered

Per the brief's "do not trust static lists blindly", every row below was read from **actual OpenClaw state**, not from documentation:

- `openclaw models list` — full model catalogue (57 models visible).
- `openclaw models status` — default, aliases, configured models, auth overview.
- `openclaw models auth list` — auth profiles and expiry.
- `~/.openclaw/openclaw.json` — provider blocks, base URLs, keys (redacted).

**Aliases live in OpenClaw (verified):** `qwen → codex-model-studio/qwen3.7-plus`, `opus → anthropic/claude-opus-4-8`, `sonnet → anthropic/claude-sonnet-4-6`, `deepseek → custom-api-deepseek-com/deepseek-reasoner`, `qwen-deepinfra → deepinfra/Qwen/Qwen3.6-35B-A3B`.
**Global default (verified):** `custom-api-deepseek-com/deepseek-reasoner`.

## 2. Configured & authenticated models (the working set)

These 8 are tagged `configured` in OpenClaw and have working auth. This is the roster LisaOS 3.0 hires from **today**.

| Physical model | Provider | Ctx | Runtime(s) | Economic class | Auth state (verified) |
|---|---|---|---|---|---|
| `anthropic/claude-opus-4-8` | anthropic | 1024k | claude-cli | Subscription | OAuth ok (~8h) |
| `anthropic/claude-opus-4-7` | anthropic | 1024k | claude-cli | Subscription | OAuth ok |
| `anthropic/claude-sonnet-4-6` | anthropic | 1024k | claude-cli | Subscription | OAuth ok |
| `openai/gpt-5.5` | openai | 195k | codex, openclaw | Subscription | OAuth ok (~41h) |
| `custom-api-deepseek-com/deepseek-reasoner` | custom-api-deepseek-com | 125k | openclaw | Elastic API | key ok (**default**) |
| `deepinfra/Qwen/Qwen3.6-35B-A3B` | deepinfra | 195k | openclaw | Elastic API | key ok |
| `codex-model-studio/qwen3.7-plus` | codex-model-studio | 977k | openclaw | Elastic API (geo-fragile) | key ok — **CN region** |
| `zai/glm-5.2` (+ 4.7, 5-turbo) | zai | 125k | openclaw | Subscription (Z.AI plan) | key ok — **not in LisaOS registry** |

> **Note (GLM — probationary):** `zai` (GLM) is fully configured and authenticated in OpenClaw but **absent from `registry/provider_resolution.yml`** and, critically, **not yet validated**. Authenticated ≠ trusted. It is added only as a *probationary candidate* and retired if it fails reliability validation (see `04`, `06`). LisaOS must not route critical work to GLM pre-validation.

> **⚠️ Identity collision (Codex vs Qwen):** the row `codex-model-studio/qwen3.7-plus` is a trap. The provider block is **named `codex-model-studio` but actually serves Alibaba's Qwen** (`"Qwen 3.7 Plus (Ali Model Studio)"`, CN-region endpoint) — it is **not** OpenAI Codex. Real Codex is `openai/gpt-5.5` (codex runtime) / `openai/gpt-5.3-codex`. Full investigation and Phase-0 fix in [`15_CODEX_QWEN_IDENTITY.md`](15_CODEX_QWEN_IDENTITY.md). **No model is treated as Codex or Qwen without runtime/provider evidence.**

## 3. Available-but-unconfigured models (present in catalogue)

Tagged in `openclaw models list` without `configured` — visible to OpenClaw, not yet wired as usable providers. Candidates for import (`05`).

**Anthropic (would inherit the Claude subscription):**
`anthropic/claude-opus-4-6`, `anthropic/claude-haiku-4-5`, `anthropic/claude-haiku-4-5-20251001`, `anthropic/claude-fable-5`; plus `claude-cli/*` mirror entries (opus-4.6/4.7/4.8, sonnet-4.6).

**OpenAI (would inherit the ChatGPT/Codex subscription):**
`openai/gpt-5.5-pro`, `openai/gpt-5.4`, `openai/gpt-5.4-mini`, `openai/gpt-5.4-nano`, `openai/gpt-5.4-pro`, `openai/gpt-5.3-chat-latest`, `openai/gpt-5.3-codex`, `openai/o1`, `openai/o1-pro`, `openai/o3`, `openai/o3-pro`, `openai/o3-mini`, `openai/o3-deep-research`, `openai/o4-mini`, `openai/o4-mini-deep-research`.

**DeepInfra (elastic, key already works):**
`deepinfra/deepseek-ai/DeepSeek-V3.2`, `deepinfra/deepseek-ai/DeepSeek-V4-Flash` (1024k), `deepinfra/zai-org/GLM-5.1`, `deepinfra/moonshotai/Kimi-K2.5` (text+image, 256k), `deepinfra/meta-llama/Llama-3.3-70B-Instruct`, `deepinfra/MiniMaxAI/MiniMax-M2.5`, `deepinfra/nvidia/NVIDIA-Nemotron-3-Super`, `deepinfra/stepfun-ai/Step-3.5-Flash`.

**DeepSeek native (BROKEN — key corrupt):**
`deepseek/deepseek-chat`, `deepseek/deepseek-reasoner`, `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`. The `deepseek:default` auth profile's key is corrupted (contains WBS text). Do **not** wire these until the key is fixed; the working DeepSeek is `custom-api-deepseek-com/*`.

**Z.AI catalogue (subscription):**
`zai/glm-5.1`, `zai/glm-5`, `zai/glm-4.7`, `zai/glm-4.7-flash`, `zai/glm-4.7-flashx`, `zai/glm-5-turbo`, `zai/glm-5v-turbo` (vision), plus GLM-4.5/4.6 legacy and vision variants.

## 4. Model Family Matrix

Assessment of each family's role in the LisaOS workforce. "Class" = economic currency (see `06`). Ratings are relative, for routing — not benchmarks.

| Family | Best at | Weak / avoid | Ctx | Class | LisaOS role |
|---|---|---|---|---|---|
| **Anthropic Opus** (4.8/4.7/4.6) | Architecture, CTO review, irreversible judgement, security-sensitive analysis | Bulk mechanical work (over-qualified, burns quota) | 1024k | Subscription | **Chief Architect / CTO Reviewer.** Scarce, high-value. |
| **Anthropic Sonnet** (4.6) | First-class engineering: coding, refactoring, testing, reviews | Not needed for trivial microtasks | 1024k | Subscription | **Senior Software Engineer.** The default premium worker. |
| **Anthropic Haiku** (4.5) | Microtasks, summaries, routing, log parsing, dashboard updates | Deep reasoning, architecture | 195k | Subscription | **Microtask / Operations Agent** (subscription-cheap). |
| **OpenAI GPT-5.5 / 5.5-pro** | Short governance bursts, planning, synthesis | **Long-running main** (hits limits fast) | 195k–977k | Subscription | **Governance burst / Planner** — never long-running main. |
| **OpenAI Codex** (gpt-5.5 via codex, gpt-5.3-codex) | Sandboxed implementation, debugging, patch validation, repo ops | Non-code reasoning | 195k–391k | Subscription | **Premium engineering worker** when available. |
| **OpenAI o-series** (o3, o4-mini, o3-deep-research) | Deep/structured reasoning, research | Cost/latency for routine work | 195k | Subscription | **Research Engineer** (deep-research variants) — selective. |
| **DeepSeek** (custom-api reasoner) | Always-on elastic reasoning/orchestration, long-running main | Premium code quality vs Sonnet/Codex | 125k | Elastic API | **Default long-running orchestration main.** |
| **Qwen — DeepInfra** (Qwen3.6-35B-A3B) | Large-context mechanical work, docs, utilities, tests | Reasoning-model quirk: emits `reasoning_content`; needs token budget | 195k | Elastic API | **Standard elastic worker** (reliable Qwen path). |
| **Qwen — Alibaba** (qwen3.7-plus) | Very large context (977k) | **403 / geo-fragility (CN region)** | 977k | Elastic API | **Deprecate as default `qwen`** (see `11`). |
| **GLM / Z.AI** (glm-5.2, 4.7, 5-turbo) | Coding-plan work, bulk, turbo low-latency | Unknown until benched | 125k–200k | **Subscription** | **Underused paid capacity** — promote to elastic-but-prepaid worker. |
| **DeepInfra catalogue** (Kimi-K2.5, Llama-3.3-70B, MiniMax-M2.5, DeepSeek-V4-Flash, Step-3.5-Flash, Nemotron) | Specialised elastic: huge-ctx flash, vision (Kimi), OSS baselines | Varies | 128k–1024k | Elastic API | **On-demand specialist bench** (import as needed). |
| **Local / Ollama** | Offline microtasks, compression, redaction | Anything needing quality or speed at 8GB | small | Free/local | **Constrained ops worker only** (see `10`). |

## 5. Capability tags (used by the resolver)

Each model advertises capabilities; the dispatcher matches packet contracts to these. Proposed tag set:

`irreversible-judgement`, `architecture`, `deep-reasoning`, `code-implementation`, `code-execution` (sandboxed/codex), `refactor`, `test-authoring`, `review`, `security-review`, `long-context` (≥900k), `huge-context` (≥1M), `vision`, `bulk-mechanical`, `documentation`, `microtask`, `research`, `offline-local`.

Example bindings:
- `irreversible-judgement`, `architecture` → Opus family only.
- `code-execution` → Codex runtime.
- `huge-context` → Alibaba Qwen (977k, if healthy), gpt-5.4-pro (1025k), DeepSeek-V4-Flash (1024k), Opus (1024k).
- `vision` → Kimi-K2.5, claude models (text+image), GLM-5v.
- `microtask` → Haiku, GLM-5-turbo, local.

## 6. Data provenance & refresh

This inventory is a **snapshot**. LisaOS 3.0 must treat it as cache: the dispatcher re-reads `openclaw models status` at sprint start (reality check, step 1) so auth expiry (Claude ~8h, OpenAI ~41h) and new/removed models are picked up. A static copy in the repo is a starting map, never the source of truth — **evidence before assumption**.
