# Qwen Reliability Plan

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

Diagnoses the reported Qwen "403 / reliability" issues from inspected evidence and specifies the fix. **Root cause: the default `qwen` alias points at a geo-fragile China-region Alibaba endpoint, while a healthy DeepInfra Qwen path already exists and is verified working.**

---

## 1. Evidence (inspected, not assumed)

From `openclaw models status` and `openclaw.json` on 2026-07-07:

| Fact | Value |
|---|---|
| OpenClaw alias `qwen` → | `codex-model-studio/qwen3.7-plus` |
| `codex-model-studio` base URL | `https://ws-yfqpamco1k5x90bp.cn-hongkong.maas.aliyuncs.com/compatible-mode/v1` |
| `codex-model-studio` auth | API key present (models.json), `sk-ws-…` |
| Alias `qwen-deepinfra` → | `deepinfra/Qwen/Qwen3.6-35B-A3B` |
| DeepInfra auth | API key present (env `DEEPINFRA_API_KEY` + profile) |
| DeepInfra live smoke test | **PASS** (HTTP 200, real completion) — `QWEN_DEEPINFRA_CONFIGURATION_REPORT.md` |

**Two Qwen backends exist, and the *default* one is the fragile one.**

## 2. Root-cause analysis of the 403s

The `qwen` alias resolves to the **Alibaba Model Studio** endpoint in the **cn-hongkong** region. 403 (Forbidden) from such an endpoint is characteristically caused by:

1. **Geographic / network access control** — CN-region MaaS endpoints frequently reject or restrict requests originating outside permitted regions, or via certain network paths. This produces intermittent/consistent 403s independent of key validity.
2. **Key/region binding** — the `sk-ws-…` key may be scoped to conditions (region, model, quota) that yield 403 rather than 401.
3. **Model-name / compat drift** — `qwen3.7-plus` with `compat.thinkingFormat: openai` on a non-standard endpoint is a fragile combination.

Crucially, **this is not a Qwen-capability problem** — it's a *backend-selection* problem. The DeepInfra Qwen path is healthy and verified. LisaOS was reaching Qwen through the wrong door.

This mirrors the earlier disambiguation lesson: a bare logical name (`qwen`) silently bound to a specific, fragile backend. The provider-resolution fix already removed bare `qwen` from the **LisaOS** registry, but **OpenClaw's own alias still maps `qwen → Alibaba`.**

## 3. The plan

### 3.1 Make DeepInfra the canonical Qwen (primary fix)
- **LisaOS side (already done):** `registry/provider_resolution.yml` has no bare `qwen`; `qwen-deepinfra` is the healthy provider, `qwen-alibaba` is a distinct optional backend. Keep this.
- **Employee hiring:** the Documentation Engineer, QA fallback, and Implementation fallback all use `qwen-deepinfra`, never `qwen-alibaba` (already reflected in `02`).
- **OpenClaw side (proposed, deferred):** repoint or retire OpenClaw's `qwen` alias so it no longer silently means Alibaba:
  - Option A (recommended): `openclaw models aliases set qwen deepinfra/Qwen/Qwen3.6-35B-A3B` — make the bare alias mean the healthy path.
  - Option B: delete the `qwen` alias entirely so a bare `qwen` fails closed and forces an explicit choice.
  - Either way, **no LisaOS routing should ever emit the bare `qwen` alias** — it emits `qwen-deepinfra` explicitly.

### 3.2 Treat Alibaba Qwen as explicit, guarded, optional
- Keep `qwen-alibaba` in the registry (977k context is genuinely useful) **but**:
  - Only reachable by explicit request for `huge-context` when DeepInfra can't satisfy it.
  - Guarded by a health check (§3.3); on 403 it fails closed to a recorded error, never a silent monoculture fallback.
  - Requires its credential env (`MODEL_STUDIO_API_KEY`) — note the current registry expects this env but the working key is in OpenClaw's models.json under `codex-model-studio`; reconcile during cleanup (`12`) so the resolver's availability check matches reality.
  - **Provider rename (see `15`):** the backing OpenClaw provider is misleadingly named `codex-model-studio` while actually serving Alibaba Qwen — this is the Codex/Qwen identity collision. Phase 0 renames it to `alibaba-model-studio` and repoints `qwen-alibaba` accordingly, so "codex" is never attached to a Qwen backend.

### 3.3 Health-aware Qwen routing
- Before dispatching to `qwen-alibaba`, the Provider Manager consults the capacity ledger (`06 §4`): if recent 403s were recorded, mark it degraded and prefer `qwen-deepinfra` or another `huge-context` model (gpt-5.4-pro, DeepSeek-V4-Flash 1024k).
- Record every 403 as a `provider_health` event so the learning loop (`09`) demotes the fragile path automatically over time.

### 3.4 Reasoning-model correctness (already solved, keep)
`Qwen3.6-35B-A3B` emits `reasoning_content` before `content` and needs adequate `max_tokens` (the earlier empty-content bug at `max_tokens=5`). The smoke test fix (`max_tokens≥1024`, accept content OR reasoning_content) is the standing rule; any employee using Qwen-DeepInfra must set a sufficient token budget. Document this on the Documentation Engineer's config.

## 4. Fallback chain for Qwen-class work

Explicit and recorded (fail-closed, no silent DeepSeek):

```
large-context mechanical packet:
    1. qwen-deepinfra        (healthy, verified)
    2. glm-5.2               (subscription, if capable)
    3. deepseek-v4-flash     (elastic, 1024k) — on demand import
    huge-context (>200k) only:
    1. qwen-alibaba          (if health-ledger clean)
    2. gpt-5.4-pro / opus-4-8 (1M-class subscription)
    on all-unavailable: FAIL CLOSED (surface; never silent DeepSeek)
```

## 5. Validation

- **Resolution test:** `bin/lisa-resolve resolve qwen-deepinfra` → AVAILABLE, `deepinfra/Qwen/Qwen3.6-35B-A3B`. `resolve qwen` → UNAVAILABLE/unknown (fail closed). (Already covered by the disambiguation test suite, 20/20.)
- **Live smoke:** `smoke_deepinfra.py` — PASS on record.
- **Alibaba health probe (new, optional):** a `smoke_qwen_alibaba.py` that makes one call and classifies 403 vs 200, feeding the health ledger — run only when `qwen-alibaba` is actually needed.
- **Regression:** no LisaOS routing path emits the bare `qwen` alias (assert in dispatcher tests once wired).

## 6. Summary

The Qwen problem is solved by **backend selection, not by fixing Alibaba**: route Qwen work to the verified DeepInfra path, keep Alibaba as an explicit health-guarded huge-context option, and stop any code path (LisaOS or OpenClaw alias) from silently meaning "Alibaba" when it says "qwen". The reasoning-model token-budget rule stays. All fail-closed.
