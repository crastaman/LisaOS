# OpenClaw Model Inventory (Complete)

**Status:** VALIDATION ARTIFACT. Inspected live 2026-07-07.
**Source:** `openclaw models list --json` (56 models), `openclaw models list --provider <p>`, `openclaw models status`, `openclaw models auth list`, `~/.openclaw/openclaw.json`. OpenClaw **2026.6.10**.

Every model OpenClaw exposes, classified for the LisaOS workforce. **Availability nuance:** the JSON `available` flag means *known to the catalogue*, **not** *authenticated & healthy*. Auth is resolved per-provider from `models status`. Classification uses the stricter, evidence-based view.

---

## 1. Auth reality per provider (from `models status`)

| Provider prefix | Backend | Auth (verified) | Class |
|---|---|---|---|
| `anthropic`, `claude-cli` | Anthropic API (via Claude CLI) | **OAuth OK** (~8h to expiry) | Subscription |
| `openai` | OpenAI API | **OAuth OK** (~41h to expiry) | Subscription |
| `custom-api-deepseek-com` | api.deepseek.com | **API key OK** (default) | Elastic API |
| `deepinfra` | api.deepinfra.com | **API key OK** (`DEEPINFRA_API_KEY`) | Elastic API |
| `zai` | open.bigmodel.cn (Z.AI/Zhipu) | **API key OK** (`ZAI_API_KEY`) | Subscription — **probationary** |
| `codex-model-studio` | Alibaba Model Studio (cn-hongkong) | API key present, **403-prone** | **RETIRED** (removed from registry) |
| `deepseek` (native) | api.deepseek.com | **KEY CORRUPT** (`"# WBS Do…"`) | **BROKEN** |

**Classification legend:** **active** = hired to an employee now · **candidate** = available/useful, importable, not yet hired · **probationary** = authenticated but not trusted (validate first) · **retired** = removed/unusable.

---

## 2. Anthropic — Claude family (7 catalogue + 4 CLI mirror)

| OpenClaw model ID | Display name | Backend | Runtime | Auth | Ctx | Recommended employee | Capability | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `anthropic/claude-opus-4-8` | claude-opus-4-8 | Anthropic | claude-cli | OK | 1024k | Chief Architect / CTO Reviewer | irreversible-judgement, architecture | **active** | Alias `opus`; guarded/scarce |
| `anthropic/claude-opus-4-7` | claude-opus-4-7 | Anthropic | claude-cli | OK | 1024k | Chief Architect (fallback) | architecture | candidate | Opus fallback |
| `anthropic/claude-opus-4-6` | claude-opus-4-6 | Anthropic | claude-cli | OK | 195k | Chief Architect (fallback) | architecture | candidate | Older Opus; smaller ctx |
| `anthropic/claude-sonnet-4-6` | claude-sonnet-4-6 | Anthropic | claude-cli | OK | 1024k | Senior SW Eng / QA | code-implementation, review | **active** | Alias `sonnet`; premium engineering default |
| `anthropic/claude-haiku-4-5` | Claude Haiku 4.5 | Anthropic | claude-cli | OK | 200k | Microtask / Ops Engineer | microtask, documentation | **candidate → Phase 0** | Subscription-cheap microtasks; add if `resolve haiku` AVAILABLE |
| `anthropic/claude-haiku-4-5-20251001` | Claude Haiku 4.5 | Anthropic | claude-cli | OK | 200k | Microtask (pinned) | microtask | candidate | Dated pin of Haiku 4.5 |
| `anthropic/claude-fable-5` | Claude Fable 5 | Anthropic | claude-cli | OK | 1000k | *(none — narrative/creative)* | long-context, narrative | candidate | Creative/long-form; no default engineering role — **newly classified** |
| `claude-cli/claude-opus-4-8` | Claude Opus 4.8 (Claude CLI) | Anthropic | claude-cli | OK | 1024k | = opus-4-8 | — | (mirror) | CLI-runtime view of the same model |
| `claude-cli/claude-opus-4-7` | Claude Opus 4.7 (CLI) | Anthropic | claude-cli | OK | 195k | = opus-4-7 | — | (mirror) | |
| `claude-cli/claude-opus-4-6` | Claude Opus 4.6 (CLI) | Anthropic | claude-cli | OK | 195k | = opus-4-6 | — | (mirror) | |
| `claude-cli/claude-sonnet-4-6` | Claude Sonnet 4.6 (CLI) | Anthropic | claude-cli | OK | 195k | = sonnet-4-6 | — | (mirror) | |

**Coverage:** Opus 4.8/4.7/4.6 ✓ · Sonnet 4.6 ✓ (only Sonnet variant) · Haiku 4.5 (+dated) ✓ · Fable 5 ✓ (now classified).

## 3. OpenAI — GPT / Codex / o-series (16)

> **Availability caveat:** the aggregate catalogue lists 16 OpenAI models, but `openclaw models list --provider openai` (live plugin enumeration) returned only **gpt-5.4, gpt-5.4-mini, gpt-5.5**. Treat the rest as *catalogue-known, confirm-before-hire* — verify live availability against the OAuth plan before relying on them (evidence before assumption).

| OpenClaw model ID | Display name | Runtime | Auth | Ctx | Recommended employee | Capability | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| `openai/gpt-5.5` | gpt-5.5 | codex / openclaw | OK | 200k | SW Eng (codex) / Release Mgr (burst) | code-execution, governance | **active** | Live-confirmed; alias none; `codex` logical → this via codex runtime |
| `openai/gpt-5.5-pro` | gpt-5.5-pro | openclaw | OK | 1000k | huge-context synthesis | huge-context | candidate | Confirm live |
| `openai/gpt-5.4` | GPT-5.4 | openclaw | OK | 272k | Governance burst | governance, planning | candidate | Live-confirmed |
| `openai/gpt-5.4-mini` | GPT-5.4 mini | openclaw | OK | 400k | Microtask (GPT-side) | microtask | candidate | Live-confirmed; **"GPT Mini"** |
| `openai/gpt-5.4-nano` | GPT-5.4 nano | openclaw | OK | 400k | cheapest GPT microtask | microtask | candidate | **"GPT Nano"**; confirm live |
| `openai/gpt-5.4-pro` | GPT-5.4 Pro | openclaw | OK | 1050k | huge-context premium | huge-context | candidate | **"GPT Pro"**; confirm live |
| `openai/gpt-5.3-chat-latest` | GPT-5.3 Chat (latest) | openclaw | OK | 128k | governance | governance | candidate | Confirm live |
| `openai/gpt-5.3-codex` | GPT-5.3 Codex | codex | OK | 400k | SW Eng / Debugging (code-specialised) | code-execution | candidate | **Codex family** alt to gpt-5.5 |
| `openai/o1` | o1 | openclaw | OK | 200k | Research | deep-reasoning | candidate | Confirm live |
| `openai/o1-pro` | o1-pro | openclaw | OK | 200k | Research (premium) | deep-reasoning | candidate | Confirm live |
| `openai/o3` | o3 | openclaw | OK | 200k | Research Engineer | deep-reasoning, research | **candidate → Phase 2** | Research role home |
| `openai/o3-pro` | o3-pro | openclaw | OK | 200k | Research (premium) | deep-reasoning | candidate | |
| `openai/o3-mini` | o3-mini | openclaw | OK | 200k | Research (cheap) | deep-reasoning | candidate | |
| `openai/o3-deep-research` | o3-deep-research | openclaw | OK | 200k | Research Engineer (deep) | research | candidate | |
| `openai/o4-mini` | o4-mini | openclaw | OK | 200k | Research (cheap) | deep-reasoning | candidate | |
| `openai/o4-mini-deep-research` | o4-mini-deep-research | openclaw | OK | 200k | Research (deep, cheap) | research | candidate | |

**Coverage:** GPT family ✓ · GPT Pro (5.5-pro/5.4-pro) ✓ · GPT Mini (5.4-mini) ✓ · GPT Nano (5.4-nano) ✓ · Codex family (gpt-5.5-via-codex, gpt-5.3-codex) ✓ · o-series ✓. **GPT "Instant" and GPT "Flash": NOT present in this OpenClaw install** — no OpenAI model with those names exists in the catalogue (honest negative). "Flash" tiers exist only for DeepSeek/DeepInfra/GLM, not GPT.

## 4. DeepSeek (3 backends)

| OpenClaw model ID | Display name | Backend | Runtime | Auth | Ctx | Employee | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| `custom-api-deepseek-com/deepseek-reasoner` | deepseek-reasoner (Custom) | api.deepseek.com | openclaw | **OK** | 125k | Implementation Eng / default main | **active** | **Global default**; alias `deepseek` |
| `deepseek/deepseek-reasoner` | DeepSeek Reasoner | api.deepseek.com (native) | openclaw | **BROKEN** | 131k | — | **retired** | Native provider key corrupt (`"# WBS Do…"`) |
| `deepseek/deepseek-chat` | DeepSeek Chat | native | openclaw | BROKEN | 131k | — | retired | Broken auth |
| `deepseek/deepseek-v4-flash` | DeepSeek V4 Flash | native | openclaw | BROKEN | 1000k | — | retired | Broken auth; 1M ctx (attractive once fixed) |
| `deepseek/deepseek-v4-pro` | DeepSeek V4 Pro | native | openclaw | BROKEN | 1000k | — | retired | Broken auth |
| `deepinfra/deepseek-ai/DeepSeek-V3.2` | DeepSeek V3.2 | DeepInfra | openclaw | OK | 160k | Implementation (elastic alt) | candidate | Working DeepSeek via DeepInfra |
| `deepinfra/deepseek-ai/DeepSeek-V4-Flash` | DeepSeek V4 Flash | DeepInfra | openclaw | OK | 1024k | huge-context bulk | **candidate** | **Huge-ctx elastic; replaces Alibaba for >200k work** |

**Coverage:** all DeepSeek flavours accounted for. The **working** DeepSeek is `custom-api-deepseek-com` (+ DeepInfra-hosted V3.2/V4-Flash). Native `deepseek/*` is retired pending the credential fix (`12 §6.1`).

## 5. DeepInfra — Qwen + specialist bench (9)

| OpenClaw model ID | Display name | Runtime | Auth | Ctx | Employee | Capability | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| `deepinfra/Qwen/Qwen3.6-35B-A3B` | Qwen 3.6 35B-A3B | openclaw | OK | 200k | Documentation Eng / QA fallback | long-context, bulk-mechanical | **active** | **The ONLY approved Qwen**; alias `qwen-deepinfra`; reasoning model (needs max_tokens ≥1024) |
| `deepinfra/deepseek-ai/DeepSeek-V4-Flash` | DeepSeek V4 Flash | openclaw | OK | 1024k | huge-context bulk | huge-context | candidate | See §4 |
| `deepinfra/deepseek-ai/DeepSeek-V3.2` | DeepSeek V3.2 | openclaw | OK | 160k | Implementation (elastic) | bulk-mechanical | candidate | |
| `deepinfra/zai-org/GLM-5.1` | GLM-5.1 | openclaw | OK | 198k | bulk (elastic GLM) | bulk-mechanical | candidate | GLM via DeepInfra (elastic, not the Z.AI subscription) |
| `deepinfra/moonshotai/Kimi-K2.5` | Kimi K2.5 | openclaw | OK | 256k | vision packets | **vision**, long-context | candidate | Only strong non-Anthropic vision path |
| `deepinfra/meta-llama/Llama-3.3-70B-Instruct-Turbo` | Llama 3.3 70B | openclaw | OK | 128k | OSS baseline / fallback diversity | bulk-mechanical | candidate | Bench |
| `deepinfra/MiniMaxAI/MiniMax-M2.5` | MiniMax M2.5 | openclaw | OK | 192k | specialist bench | bulk-mechanical | candidate | Bench |
| `deepinfra/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B` | Nemotron 3 Super | openclaw | OK | 256k | specialist bench | deep-reasoning | candidate | Bench |
| `deepinfra/stepfun-ai/Step-3.5-Flash` | Step 3.5 Flash | openclaw | OK | 256k | cheap flash bulk | bulk-mechanical | candidate | Bench |

**Coverage:** DeepInfra Qwen ✓ (single, approved). Specialist bench catalogued as on-demand candidates (import per `05`).

## 6. Z.AI / GLM (14) — PROBATIONARY

All `zai/*` are **probationary** (authenticated, not trusted; validate before reliance, retire on failure — `04`/`06`).

| OpenClaw model ID | Display name | Ctx | Employee (potential) | Capability | Status |
|---|---|---|---|---|---|
| `zai/glm-5.2` | GLM-5.2 (Coding Plan) | 977k* | Documentation / bulk | bulk-mechanical, documentation | probationary |
| `zai/glm-5-turbo` | GLM-5-Turbo | 198k | Ops Engineer (low-latency) | microtask | probationary |
| `zai/glm-5.1` | GLM-5.1 | 203k | bulk | bulk-mechanical | probationary |
| `zai/glm-5` | GLM-5 | 203k | bulk | bulk-mechanical | probationary |
| `zai/glm-4.7` | GLM-4.7 (Fallback) | 200k | bulk fallback | bulk-mechanical | probationary |
| `zai/glm-4.7-flash` | GLM-4.7 Flash | 195k | microtask | microtask | probationary |
| `zai/glm-4.7-flashx` | GLM-4.7 FlashX | 195k | microtask | microtask | probationary |
| `zai/glm-5v-turbo` | GLM-5V Turbo | 203k | vision microtask | vision | probationary |
| `zai/glm-4.6` | GLM-4.6 | 205k | bulk (legacy) | bulk-mechanical | probationary |
| `zai/glm-4.6v` | GLM-4.6V | 128k | vision (legacy) | vision | probationary |
| `zai/glm-4.5` | GLM-4.5 | 131k | bulk (legacy) | bulk-mechanical | probationary |
| `zai/glm-4.5-air` | GLM-4.5 Air | 131k | microtask (legacy) | microtask | probationary |
| `zai/glm-4.5-flash` | GLM-4.5 Flash | 131k | microtask (legacy) | microtask | probationary |
| `zai/glm-4.5v` | GLM-4.5V | 64k | vision (legacy) | vision | probationary |

*Note: `glm-5.2` shows 977k in `--provider zai` but 128k in the JSON catalogue — metadata inconsistency; confirm live before relying on the large context. **Recommendation:** during probation validate only `glm-5.2`, `glm-4.7`, `glm-5-turbo` (the Coding-Plan trio); treat the GLM-4.5/4.6 legacy line as retired-by-default (don't hire the whole catalogue).

## 7. Retired / removed

| OpenClaw model ID | Reason | Action taken |
|---|---|---|
| `codex-model-studio/qwen3.7-plus` | Alibaba Qwen on 403-prone CN endpoint; provider mis-named "codex-model-studio" → Codex/Qwen ambiguity; **not an approved workforce provider** | **Removed** from `registry/provider_resolution.yml` (this validation). Live `openclaw.json` removal + `qwen` alias repoint = Phase 0 task 0.2/0.3. |
| `deepseek/*` (native) | Auth key corrupt (WBS text pasted) | Marked retired; credential fix/removal = Phase 0 task 0.7. |

## 8. Local

Ollama **0.30.11** installed, **0 models pulled**. Nothing to inventory. **Future capacity only** (`10`) — not in the active workforce.

---

## 9. Inventory summary

| Bucket | Count | Examples |
|---|---|---|
| **Active** (hired now) | 5 | opus-4-8, sonnet-4-6, deepseek-reasoner(custom-api), gpt-5.5, qwen3.6(deepinfra) |
| **Active pending Phase-0 validation** | 2 | codex (gpt-5.5, identity-check), haiku-4-5 (availability-check) |
| **Candidate** (available, not yet hired) | ~28 | o-series, gpt-pro/nano, opus-4-7/4-6, DeepInfra bench, Fable 5, DeepSeek-V4-Flash |
| **Probationary** (auth ≠ trust) | 14 | all `zai/*` GLM |
| **Retired / broken** | 5 | codex-model-studio/qwen3.7-plus, native `deepseek/*` |
| **Total catalogue** | **56** | (JSON `count`) |

Full coverage confirmed in `17_WORKFORCE_COVERAGE_AND_GAP.md`; registry integrity in `18_PROVIDER_REGISTRY_AUDIT_AND_CLEANUP.md`.
