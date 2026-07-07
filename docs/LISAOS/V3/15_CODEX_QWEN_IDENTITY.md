# Codex / Qwen Model Identity Ambiguity — Investigation

**Status:** DESIGN FOR APPROVAL. Investigation + policy. No implementation.
**Date:** 2026-07-07
**Trigger:** Codex appears associated with Qwen in the OpenClaw model list. Required to resolve before relying on Codex routing.

> **Update (2026-07-07 validation):** the resolution chosen was **stronger than the rename proposed in §4** — the Alibaba Qwen provider (`qwen-alibaba` / `codex-model-studio/qwen3.7-plus`) was **removed entirely** from the LisaOS registry (`18`), so nothing references `codex-model-studio` and `codex` is unambiguously OpenAI (verified live, 23/23 tests). §4 below is retained as the original investigation; the live `~/.openclaw/openclaw.json` rename/removal + `qwen` alias repoint remain Phase-0 tasks 0.2/0.3.

---

## 1. Finding (evidence-based)

Inspected live 2026-07-07 (`openclaw models list`, `~/.openclaw/openclaw.json`, `registry/provider_resolution.yml`).

The ambiguity is a **misleading provider-block name — an alias/naming collision — not a display bug.**

**The offending row:**
```
codex-model-studio/qwen3.7-plus    text   977k   no   yes   configured,alias:qwen
```

**What that provider actually is** (from `openclaw.json`):
```
provider id : codex-model-studio
baseUrl     : https://ws-…​.cn-hongkong.maas.aliyuncs.com/compatible-mode/v1
models      : qwen3.7-plus  =>  "Qwen 3.7 Plus (Ali Model Studio)"
```

So a provider block **named `codex-model-studio`** hosts **Alibaba Model Studio's Qwen** model. The token "codex" in the provider id is what makes "Codex" appear next to a Qwen model. **There is no OpenAI Codex in this provider.**

**Where real Codex actually lives:**
```
openai/gpt-5.5           (used via the `codex` runtime)   provider: openai, OAuth
openai/gpt-5.3-codex     (code-specialised OpenAI model)  provider: openai, OAuth
```

## 2. Classification

The brief asked which of four causes this is. Answer, with evidence:

| Candidate cause | Verdict | Evidence |
|---|---|---|
| OpenClaw **display bug** | ❌ No | The list is accurate — it faithfully shows provider `codex-model-studio` serving `qwen3.7-plus`. Nothing is mis-rendered. |
| **Provider alias / naming collision** | ✅ **Yes — primary cause** | An Alibaba-Qwen provider block was *named* `codex-model-studio`. The shared token "codex" collides with the concept of OpenAI Codex. |
| **Config issue** | ✅ Yes — contributing | The provider id is a misnomer: its name implies Codex; its content is Qwen. This is a configuration-naming defect in `openclaw.json`. |
| **Incorrect model-registry mapping** | ⚠️ Partially — must guard | LisaOS's registry currently maps this correctly (`qwen-alibaba → codex-model-studio/qwen3.7-plus`; `codex → openai/gpt-5.5`). But because both a real `codex` logical name **and** a provider literally named `codex-model-studio` exist, any future hand-mapping could easily bind Codex work to the Qwen backend. |

**Root cause:** a provider block named `codex-model-studio` that in fact serves Alibaba Qwen. The name is the whole problem.

## 3. Why this is dangerous

Two independent, unhealthy properties combine:
- The word "codex" is attached to a **Qwen** model, so a human or a fuzzy match could route *Codex work to Qwen*.
- That same backend is the **CN-region, 403-prone Alibaba endpoint** (see `11_QWEN_RELIABILITY_PLAN.md`). So the worst-case mis-route sends premium engineering work to the least reliable provider.

## 4. Resolution (Phase 0 — required before relying on Codex)

1. **Rename the provider block.** In `openclaw.json`, rename `codex-model-studio` → `alibaba-model-studio` (or `ali-qwen`). Back up first; secrets untouched; never committed. This removes the "codex" token from anything that is actually Qwen.
2. **Update the registry mapping** so `qwen-alibaba.provider_id` / `openclaw_provider` point at the renamed block. Reconcile the credential source at the same time (registry expects `MODEL_STUDIO_API_KEY`; the working key currently lives in the `codex-model-studio` models.json — see `11 §3.2` / `12 §6.3`).
3. **Confirm real Codex identity with runtime evidence.** Resolve `codex` → must be `openai/gpt-5.5` on runtime `codex` (provider `openai`, OAuth), *not* anything under the Alibaba block. Verify with a live one-shot: dispatch a trivial Codex task and confirm from `subagent_runs.model` / the response that the served model and provider are OpenAI, not Qwen.
4. **Assert separation in tests.** Add a resolution test: `resolve("codex").provider_id == "openai"` and `resolve("codex").physical_model` contains `gpt-5.5`/`codex`; `resolve("qwen-alibaba").provider_id != "openai"`. The two must never share a provider id or physical model. (Mirrors the existing `test_two_qwens_never_conflate` pattern.)

## 5. Standing policy

> **LisaOS must not treat any model as Codex or Qwen unless actual runtime/provider evidence confirms it.**

Operationalised:
- Identity is proven by `provider_id` + `physical_model` + (post-run) `subagent_runs.model`, never by a name token or list label.
- A provider whose **name** disagrees with the **model it serves** is a config defect and is flagged (`12`), not trusted.
- Codex routing is **gated**: until step 3's runtime evidence confirms Codex = OpenAI, Codex is not relied upon as the SW-Engineer's preferred model (fall back to Sonnet/DeepSeek).

## 6. Summary

Codex-appearing-as-Qwen is caused by an **Alibaba-Qwen provider block misleadingly named `codex-model-studio`**. It is a naming/config collision, not a display bug. The fix is a rename + registry reconciliation + a runtime-evidence confirmation of real Codex identity, all in Phase 0, with a permanent policy that model identity is established by provider/runtime evidence and never by a label.
