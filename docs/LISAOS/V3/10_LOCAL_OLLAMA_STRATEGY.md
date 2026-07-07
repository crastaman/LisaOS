# Local Ollama Strategy

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

An honest assessment of local models on the operator's hardware. **Conclusion up front: Local AI is FUTURE PLANNED CAPACITY ONLY. It is not installed, not configured, and is NOT part of the active workforce.** Ollama the runtime is installed but **zero models are pulled**, so there is nothing to route to today. When (if) it is set up, it is a constrained microtask/offline worker — never a main runtime and never a replacement for any hosted model.

> **Status: NOT ACTIVE.** Local AI does not appear in any active-workforce table, mode default, or employee `preferred`/`fallback` binding in this design. It is scheduled to the **future roadmap (post-install + validation)**. All content below is contingent on a future, approved installation.

---

## 1. Verified hardware & software reality

Inspected 2026-07-07:

| Fact | Value | Implication |
|---|---|---|
| Machine | Apple **M1** (Mac mini class) | Good NPU/GPU for small models; unified memory |
| **RAM** | **8 GB** | **The binding constraint.** Shared by macOS + apps + model |
| Internal SSD free | 144 GB | Plenty for a few model files |
| External storage | Thunderbolt SSD ≤1 TB possible | Solves *storage*, not *RAM* |
| Ollama | **0.30.11 installed** | Ready |
| Models pulled | **none** | Clean slate |

**The honest truth about 8 GB:** macOS itself uses ~3–4 GB. That leaves ~4–4.5 GB usable for a model + its KV cache. External SSD does **not** help — models must fit in **RAM** to run at usable speed; a model that spills to swap is unusably slow. So the external Thunderbolt SSD is irrelevant to model *size*; it only helps store many model files.

## 2. Realistic model options at 8 GB

| Model | Quant | RAM footprint | Verdict |
|---|---|---|---|
| `qwen2.5:3b` / `qwen3:4b` | Q4 | ~2.5–3 GB | ✅ Viable — best small all-rounder |
| `llama3.2:3b` | Q4 | ~2.5 GB | ✅ Viable microtask |
| `gemma2:2b` / `phi` (small) | Q4 | ~2 GB | ✅ Viable — fastest, lowest quality |
| `qwen2.5:7b` / `llama3.1:8b` | Q4 | ~4.5–5 GB | ⚠️ Marginal — squeezes the whole system; slow; risks swap |
| DeepSeek local (any useful size) | — | ≥ RAM | ❌ Not viable — real DeepSeek variants exceed 8 GB usefulness |
| Anything ≥13B | — | ≫ RAM | ❌ Not viable |

**Qwen local:** `qwen2.5:3b` (or `qwen3:4b`) is the recommended local model — good quality-per-GB, aligns with the Qwen role LisaOS already understands. A 7B is *technically* runnable but not *comfortably* — it degrades the whole machine and is slow; not worth it as a routine worker.

**DeepSeek local:** not viable. The hosted `custom-api-deepseek-com` path is cheap and vastly more capable; local DeepSeek offers nothing at 8 GB.

## 3. Role in the workforce (honest)

Local is a **fallback/offline specialist**, mapped to the lowest-seniority roles only:

| Can do (viable) | Cannot do (be honest) |
|---|---|
| Offline microtasks (summaries, extraction) | Be a main runtime (too slow, too small) |
| Text compression / context pre-summarisation | Replace DeepSeek/Sonnet/Codex/Opus |
| PII redaction before sending to hosted models (privacy) | Architecture, deep reasoning, quality code |
| Cheap-when-network-down operations | Large context (small ctx windows at 8 GB) |
| Last-resort Microtask Agent fallback | Anything latency-sensitive at scale |

**Cheap main runtime?** No. Considered and rejected: an 8 GB local model as `main` would make coordination *slower*, not faster — the opposite of the goal. Local coordination is only justified in `Local-First` mode (offline/privacy), and even then it delegates real work to hosted models when network returns.

## 4. Integration path (Phase 3, optional)

Ollama exposes an OpenAI-compatible endpoint (`http://localhost:11434/v1`), so integration mirrors the DeepInfra pattern — no proxy needed:

1. `ollama pull qwen2.5:3b` (and optionally `llama3.2:3b`).
2. Add an `ollama` provider block to `openclaw.json` (OpenAI-compatible, `baseUrl: http://localhost:11434/v1`, no key). Back up first.
3. Confirm in `openclaw models list` (would appear as `Local yes`).
4. Add `local-micro` to `registry/provider_resolution.yml`: `physical_model: ollama/qwen2.5:3b`, `runtime: ollama`, `credential: { type: none }` (local, no auth), `capabilities: [microtask, offline-local]`.
5. `bin/lisa-resolve resolve local-micro` → AVAILABLE (local, no key needed).
6. Hire onto Microtask Agent / Ops Engineer as a **fallback only**, `Local-First` mode as `preferred`.

## 5. Validation strategy

- **Latency budget test:** measure tokens/sec for `qwen2.5:3b` on the M1; only keep it in rotation if it beats a defined floor (else it's slower than a cheap hosted call and pointless).
- **RAM headroom test:** run under normal load; confirm no swap thrash (else it degrades the whole machine — disqualifying).
- **Quality gate:** local output only accepted for `microtask`-tagged packets; never promoted to higher-seniority roles regardless of score.
- **Fail-closed:** if Ollama isn't running, `local-micro` resolves UNAVAILABLE and the Microtask Agent falls back to Haiku/GLM — never a silent hang.

## 6. Recommendation

- **Future capacity only — do not include in the active workforce.** Local AI is deferred to a later roadmap phase, contingent on installation + validation. No employee, mode, or routing path in LisaOS 3.0 depends on it. `Local-First` mode is defined for completeness but is **inert until local models exist and pass validation** (until then it degrades to Haiku/GLM).
- **When set up (later): do it small and late.** Pull `qwen2.5:3b` as an offline/privacy microtask fallback only.
- **Do not** treat local as cost-saving for routine work — abundant subscription capacity (Haiku/GLM) is already ≈£0 and far better. Local's value is **offline/privacy/degraded-network resilience**, not cost.
- **Do not** buy the external SSD for this — it doesn't lift the 8 GB RAM ceiling that actually binds. (An external SSD is fine for storing several small model files, nothing more.)
