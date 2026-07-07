# LisaOS Cleanup Plan

**Status:** DESIGN FOR APPROVAL. **Nothing is deleted.** This is a risk-rated plan only.
**Date:** 2026-07-07

Audit of LisaOS for obsolete/duplicated/stale/conflicting artifacts, from live inspection. Each item has a **risk level** for *acting* on it. Deletion/change happens only after approval, per-item.

Risk key: **🟢 Low** (safe, reversible, no behaviour change) · **🟡 Medium** (verify first; may touch behaviour) · **🔴 High** (behavioural/architectural; do under a sprint with tests).

---

## 1. Conflicting registries / abstractions (highest-value cleanup)

| # | Item | Evidence | Issue | Risk | Action |
|---|---|---|---|---|---|
| 1.1 | **`registry/runtimes.yml`** — old logical-runtime placeholders (`gpt-governance`, `deepseek-planning`, `claude-review`, `codex-review`) with `cost_tier` scalars | Read live; never bound to physical models | **Superseded** by `provider_resolution.yml` (+ proposed `employees.yml`). This IS the abstraction that caused the monoculture (`cost_tier` conflated the two currencies). | 🔴 | Migrate roles → `employees.yml`; retire `runtimes.yml` or reduce to runtime-profile definitions only |
| 1.2 | **`registry/agents.yml`** `preferred_runtime`/`fallback_runtimes` pointing at 1.1's placeholders | Read live | Agents reference the dead runtime layer, not employees/models | 🔴 | Repoint agents to employees during the org migration |
| 1.3 | **`registry/agents.json`** alongside `agents.yml` | Both present in `registry/` | Duplicate formats for the same concept | 🟡 | Confirm which is authoritative (yml); archive/remove the json |
| 1.4 | **`cost_tier` scalar** wherever it appears | `runtimes.yml`, docs | Single scalar conflates subscription vs API currencies (`06`) | 🔴 | Replace with two-currency `economic_class` + `scarcity` fields |

## 2. Dead / stub code

| # | Item | Evidence | Issue | Risk | Action |
|---|---|---|---|---|---|
| 2.1 | **`engines/openclaw.py`, `claude.py`, `codex.py`, `gpt.py`** | `OpenClawEngine is a stub for now` (read) | Stubs superseded by OpenClaw execution + `provider_resolver.py`. `router.py` still has legacy `choose_engine`. | 🟡 | Confirm no live caller; then remove `engines/` or fold into a single documented adapter |
| 2.2 | **`core/` legacy** (`aggregator.py`, `engine.py`, `planner.py`, `registry.py`, `result.py`, `lisa_core.py`) | Small pre-resolver modules | Some predate the resolver; may be unused | 🟡 | Trace imports; keep what `lisa_core`/`router` use, archive the rest |
| 2.3 | **`bin/lisa-core`** (96 bytes) | Tiny shim | Possibly obsolete vs `bin/lisa` | 🟢 | Verify; remove if unused |

## 3. Build artifacts (should never be tracked)

| # | Item | Evidence | Risk | Action |
|---|---|---|---|---|
| 3.1 | `__pycache__/` ×3 (`core`, `tests`, `engines`), 14 `.pyc` | `find` | 🟢 | Ensure `__pycache__/` + `*.pyc` in `.gitignore`; remove from tree if tracked |

## 4. Empty / placeholder directories

| # | Item | Evidence | Risk | Action |
|---|---|---|---|---|
| 4.1 | `src/`, `memory/`, `logs/`, `configs/`, `knowledge/` — **0 files each** | `find` | 🟢 | Decide: keep with `.gitkeep` + purpose note, or remove. `memory/` + `knowledge/` overlap conceptually — consolidate. |

## 5. Documentation sprawl (`docs/LISAOS/` — 30 files)

| # | Item | Evidence | Issue | Risk | Action |
|---|---|---|---|---|---|
| 5.1 | KERNEL family: `KERNEL.md`, `KERNEL_REVIEW.md`, `KERNEL_DECISIONS.md` | 3 large overlapping docs | Overlapping kernel narrative | 🟡 | Keep `KERNEL.md` + `KERNEL_DECISIONS.md`; fold `KERNEL_REVIEW.md` into an archive |
| 5.2 | `L005_L007_DESIGN_REVIEW.md` vs individual `L005/L006/L007` | Review doc duplicates content | Review superseded once individuals are final | 🟡 | Archive the combined review |
| 5.3 | `FOUNDATION_V3_COMPLETE.md`, `ECOSYSTEM.md`, `MANIFEST.md`, `README.md` | Multiple index/overview docs | Multiple competing "front doors" | 🟡 | Make `README.md` the single index; archive redundant overviews |
| 5.4 | S024 docs (`AI_WORKFORCE_FRAMEWORK.md`, `ARCHITECTURAL_CRITIQUE.md`, …) vs this `V3/` set | Two architecture generations coexist | 3.0 supersedes parts of S024 | 🟡 | Cross-link; mark superseded sections; keep `ARCHITECTURAL_CRITIQUE.md` (still the diagnosis) |
| 5.5 | Uncommitted S024 docs + this set | `git status`: many `??` | Untracked architecture on disk | 🟢 | Commit the architecture docs as a documented set (see roadmap) |

## 6. Configuration hygiene (`~/.openclaw/` — outside repo, do not commit)

| # | Item | Evidence | Issue | Risk | Action |
|---|---|---|---|---|---|
| 6.1 | **Corrupt `deepseek:default` auth key** | `openclaw models status`: key = `"# WBS Do...finement"` | A WBS document was pasted where an API key belongs; native `deepseek/*` cannot auth | 🔴 | Fix credential (re-paste real key) **or** delete the broken profile so it fails closed cleanly. Never commit the key. |
| 6.2 | **`qwen` alias → Alibaba CN endpoint** | `openclaw models status` | Bare alias silently means the 403-prone backend (`11`) | 🟡 | Repoint alias to DeepInfra or delete it |
| 6.3 | **`MODEL_STUDIO_API_KEY` mismatch** | Registry `qwen-alibaba` expects this env; working key is in `codex-model-studio` models.json | Resolver availability check may not match reality | 🟡 | Reconcile credential descriptor with actual source (`11 §3.2`) |
| 6.5 | **Misleading provider name `codex-model-studio`** (hosts Alibaba **Qwen**, not Codex) | `openclaw.json`: provider `codex-model-studio` → `qwen3.7-plus` "Ali Model Studio"; alias `qwen` | **Codex/Qwen identity collision** — "codex" attached to a Qwen backend; risk of routing Codex work to the 403-prone Qwen (`15`) | 🟡 | Rename block → `alibaba-model-studio`; repoint `qwen-alibaba`; add Codex-identity test. **Required before relying on Codex routing.** |
| 6.4 | Stale `openclaw.json.pre-deepinfra-*.bak` backups | Created during DeepInfra config | Accumulating backups | 🟢 | Keep newest; prune old (outside repo) |

## 7. Reports / experiments

| # | Item | Evidence | Issue | Risk | Action |
|---|---|---|---|---|---|
| 7.1 | `reports/` fully gitignored (evidence JSONL, audit, morning-brief) | `.gitignore` line 34 | Runtime logs correctly ignored — **no action**, noted so it isn't "lost" | 🟢 | Keep; ensure evidence JSONL rotation policy |
| 7.2 | `reports/openclaw/*-help.txt` (captured CLI help) | Static snapshots | Stale vs live CLI (now 2026.6.10) | 🟢 | Regenerate on demand or drop; not a source of truth |
| 7.3 | `lisaos/` skeleton (agents/jobs/packets/policies/… mostly empty) | `ls` | Parallel half-built structure vs top-level dirs | 🟡 | Decide: is `lisaos/` the future home or dead scaffolding? Consolidate. |

## 8. Execution order (when approved)

1. **🟢 first** — build artifacts (3.1), empty dirs (4.1), stale help/backups (7.2, 6.4), commit architecture docs (5.5). Zero behavioural risk.
2. **🟡 next** — dedupe docs (5.x), confirm/remove stub code (2.x), reconcile creds (6.2, 6.3), agents.json (1.3).
3. **🔴 last, under a tested migration sprint** — retire the `cost_tier`/runtime-placeholder abstraction (1.1, 1.2, 1.4) and fix the corrupt DeepSeek key (6.1). These change behaviour and must land with tests.

**No item is executed under this document.** Each is a proposal awaiting per-item approval.
