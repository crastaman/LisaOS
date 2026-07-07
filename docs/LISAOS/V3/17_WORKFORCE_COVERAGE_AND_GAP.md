# Workforce Coverage Report & Gap Analysis

**Status:** VALIDATION ARTIFACT. 2026-07-07.
**Question answered:** Does the LisaOS 3.0 Workforce Architecture account for **every useful model family and flavour** actually present in OpenClaw? Where are the gaps, and are they closed?

Cross-checks the complete inventory (`16`) against the Employee Capability Matrix (`02`), Model Family Matrix (`03`), and Workforce Policies/Modes (`08`).

---

## 1. Family-by-family coverage (per the brief's checklist)

| Family / flavour required | Present in OpenClaw? | In workforce design? | Where | Status |
|---|---|---|---|---|
| **Claude Opus** — all variants | 4-8, 4-7, 4-6 | ✓ | `02` Chief Architect/CTO Reviewer (+fallbacks) | **covered** |
| **Claude Sonnet** — all variants | 4-6 (only one) | ✓ | `02` Senior SW Eng, QA | **covered** |
| **Claude Haiku** — all variants | 4-5, 4-5-20251001 | ✓ | `02` Microtask/Ops (Phase-0 hire) | **covered** |
| **GPT family** | 5.5, 5.4, 5.3-chat | ✓ | `02` Release Mgr/Governance burst; `07` | **covered** |
| **GPT Pro** | 5.5-pro, 5.4-pro | ✓ (candidate) | `16 §3` huge-context; `03` | **covered** |
| **GPT Mini** | 5.4-mini | ✓ (candidate) | `16 §3` GPT-side microtask | **covered** |
| **GPT Nano** | 5.4-nano | ✓ (candidate) | `16 §3` cheapest GPT microtask | **covered** |
| **GPT Instant** | **absent** | n/a | — | **N/A (does not exist here)** |
| **GPT Flash** | **absent** (no GPT-Flash) | n/a | — | **N/A (does not exist here)** |
| **Codex family** | gpt-5.5(codex runtime), gpt-5.3-codex | ✓ | `02` SW Eng/Debugging; `15` identity gate | **covered (gated)** |
| **Other OpenAI (o-series)** | o1/o1-pro/o3/o3-pro/o3-mini/o3-deep-research/o4-mini/o4-mini-deep-research | ✓ | `02` Research Engineer; `16 §3` | **covered** |
| **DeepSeek — all** | custom-api reasoner (OK); native chat/reasoner/v4-flash/v4-pro (broken); DeepInfra V3.2/V4-Flash (OK) | ✓ | `02` Implementation Eng; `16 §4` | **covered** |
| **DeepInfra Qwen — all** | Qwen3.6-35B-A3B (only one) | ✓ | `02` Documentation Eng | **covered** |
| **GLM / Z.AI** | 14 models | ✓ (probationary) | `02`/`06` probation; `16 §6` | **covered (probationary)** |
| **Local** | Ollama, 0 models | ✓ (deferred) | `10` future capacity | **covered (deferred)** |

**Result:** every family/flavour the brief asked about is either represented in the workforce design or honestly recorded as **absent** (GPT Instant/Flash) — no silent omissions.

## 2. Gaps found & closed

The inventory surfaced a small number of models present in OpenClaw but not explicitly classified in the earlier matrices. Each is now closed:

| Gap | Was it missing? | Resolution |
|---|---|---|
| **Claude Fable 5** (`anthropic/claude-fable-5`, 1M ctx) | Yes — not in `03`/`02` | Classified in `16 §2` as a **candidate**, creative/long-form; **no default engineering role** (deliberately unhired). Added to `03` family matrix note. |
| **GPT nano** (`gpt-5.4-nano`) | Partially — `02` mentioned mini, not nano | Classified `16 §3` as candidate microtask; `03` GPT row extended. |
| **GLM vision** (`glm-4.5v`, `glm-4.6v`, `glm-5v-turbo`) | Yes — vision capability unclassified | Classified `16 §6` as probationary `vision`; noted in `03`. |
| **Kimi-K2.5 vision** (`deepinfra/moonshotai/Kimi-K2.5`) | Named in `03` but not tied to a capability | Confirmed as the primary non-Anthropic `vision` candidate (`16 §5`). |
| **DeepInfra DeepSeek-V4-Flash (1024k)** | Named but not tied to huge-context role | Now the **designated huge-context (>200k) replacement for the removed Alibaba Qwen** (`16 §4`, `11`). |
| **Nemotron / MiniMax / Step / Llama** | Listed generically | Classified as on-demand specialist bench (`16 §5`). |

**No family-level gap remains.** The remaining items are all *candidate/bench* models correctly left unhired until needed.

## 3. Capability coverage matrix (are all capabilities served?)

| Capability tag | Served by (active/candidate) | Gap? |
|---|---|---|
| irreversible-judgement / architecture | Opus 4.8 (+4.7/4.6) | none |
| code-implementation / refactor | Sonnet, Codex, DeepSeek | none |
| code-execution (sandboxed) | Codex runtime (gpt-5.5, gpt-5.3-codex) | none (gated on identity validation) |
| review / security-review | Opus, Sonnet | none |
| deep-reasoning / research | o3, o4-mini, o-deep-research, Nemotron | none (o-series = Phase 2) |
| long-context (≥900k) | Opus 1M, Sonnet 1M, gpt-5.4-pro 1M, DeepSeek-V4-Flash 1M | none |
| huge-context (>200k, non-premium) | DeepSeek-V4-Flash, gpt-5.4-pro | none (**replaces Alibaba 977k**) |
| vision | Claude (text+image), Kimi-K2.5, GLM-5v | none |
| bulk-mechanical | DeepSeek, Qwen-DeepInfra, GLM (prob.) | none |
| documentation | Qwen-DeepInfra, GLM (prob.), Haiku | none |
| microtask | Haiku, GLM-turbo (prob.), gpt-5.4-mini/nano | none |
| offline-local | *(Ollama — future)* | **deferred, by design** |

Only deliberate deferrals (o-series to Phase 2, local to future). No accidental capability gap.

## 4. Loss from removing Alibaba Qwen — assessed

Removing `qwen-alibaba` (977k ctx) removes one huge-context path. **Is anything lost?** No net capability loss:

| Need Alibaba served | Replacement (approved, healthy) | Ctx |
|---|---|---|
| >200k mechanical context | `deepinfra/deepseek-ai/DeepSeek-V4-Flash` | 1024k |
| >200k premium synthesis | `openai/gpt-5.4-pro` / `anthropic/claude-opus-4-8` | 1050k / 1024k |
| general Qwen work | `deepinfra/Qwen/Qwen3.6-35B-A3B` (approved) | 200k |

The removed backend was the *least reliable* (403-prone CN endpoint) provider of a capability that **three healthier models already cover**. Removal is strictly positive.

## 5. Updated-matrix decision

- **`03_MODEL_INVENTORY_AND_FAMILIES.md`** — updated: Alibaba Qwen row marked **REMOVED**; Fable 5 + vision + huge-context replacements noted; points to `16` for the exhaustive list.
- **`02_EMPLOYEE_CAPABILITY_MATRIX.md`** — no orphaned mapping (no employee used qwen-alibaba); no change to hires required.
- **`11_QWEN_RELIABILITY_PLAN.md`** — updated: Alibaba path removed, huge-context reroutes to DeepSeek-V4-Flash / gpt-5.4-pro.
- No new employee is required; the gaps were all *candidate/bench* classifications, now recorded in `16`.

## 6. Verdict

**Coverage is complete.** Every useful model family and flavour actually present in OpenClaw is classified and placed (active / candidate / probationary / retired). The only "missing" items — GPT Instant, GPT Flash — genuinely do not exist in this install and are recorded as such. Removing Alibaba Qwen costs no capability. The workforce begins from a fully-accounted foundation.
