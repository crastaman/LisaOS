# LisaOS 3.0 Design — Corrections Changelog

Corrections applied to the V3 design set before commit, per operator direction (2026-07-07).
All changes tighten the **evidence-before-trust** posture: authenticated ≠ trusted; identity is proven by runtime/provider evidence, never by a label.

---

## C1 — GLM / Z.AI: probationary, not a guaranteed member
- GLM is **authenticated but not yet trusted**. Reclassified from "highest-ROI quick win" to **candidate / probationary capacity**.
- **Explicit policy added:** if GLM remains unstable or fails reliability validation, it is **retired from the active workforce**.
- **No critical work routes to GLM** until it passes validation; probation runs low-risk packets only.
- **Docs updated:** `README.md`, `03` (inventory note), `04` (opportunity #1 rewritten + closing meta-point), `06` (capacity table + KPI), `02` (trust-guard header, Ops/Microtask cards, summary table), `08` (mode re-binding note), `07` (main phase map).

## C2 — Codex / Qwen model-list identity ambiguity
- **Investigated and documented** in new doc **`15_CODEX_QWEN_IDENTITY.md`**.
- **Finding:** the OpenClaw provider block named `codex-model-studio` actually serves **Alibaba Qwen** (`qwen3.7-plus`, CN-region), **not** OpenAI Codex. Classified as a **provider alias / naming collision + config defect** — *not* a display bug. Real Codex = `openai/gpt-5.5` (codex runtime) / `openai/gpt-5.3-codex`.
- **Policy added:** LisaOS must not treat a model as Codex or Qwen unless **actual runtime/provider evidence** confirms it.
- **Phase 0 task added:** resolve the identity ambiguity (rename provider block, reconcile registry, confirm Codex identity with a live run) **before relying on Codex routing**.
- **Docs updated:** `README.md` (3rd defect + trust posture), `03`, `04` (#3 Codex guard), `11` (cross-ref rename), `12` (cleanup item 6.5), `02` (Codex-gated markers), `13` (Phase 0), `14` (§5a).

## C3 — Local AI / Ollama: future capacity only
- Local AI is **not installed/configured** (Ollama present, **zero models pulled**). Reclassified to **future planned capacity**; **removed from the active workforce**.
- Removed from all active employee `preferred`/`fallback` bindings and mode rotations; `Local-First` mode marked **inert until local is installed + validated** (runs on Haiku/subscription meanwhile).
- Hardware constraint reaffirmed: Mac mini **M1, 8 GB RAM**, external SSD possible later (does not lift the RAM ceiling).
- **Docs updated:** `10` (status banner + recommendation), `02` (local removed from cards/table), `07`, `08` (Local-First inert), `README.md`.

## C4 — Phase 0 redefined
Phase 0 (in `13_IMPLEMENTATION_ROADMAP.md`) rewritten from a "quick wins" grab to a **verify-and-guard** phase with 8 explicit tasks:
1. Commit V3 doc set.
2. Fix Qwen alias → DeepInfra explicit path.
3. Investigate Codex/Qwen identity ambiguity.
4. Add Haiku as microtask worker **if available**.
5. Validate Codex **as Codex** with runtime evidence.
6. Validate GLM **only as probationary**.
7. Clean corrupted native DeepSeek credential.
8. Leave Local AI as future capacity.

## Files touched
`README.md`, `02`, `03`, `04`, `06`, `07`, `08`, `10`, `11`, `12`, `13`, `14`, **new** `15_CODEX_QWEN_IDENTITY.md`, **new** `CHANGELOG.md`.
Unchanged: `00`, `01`, `05`, `09` (no correction needed; the delegation/org/import/metrics designs already accommodate probation + evidence gating).

## Standing invariants reaffirmed
- **Fail closed, never silent** — unchanged.
- **No secret ever committed** — unchanged.
- **Evidence before assumption** — strengthened: model identity and trust are established by runtime/provider evidence, never by a name or list label.
- **Phase 0 is not implemented under this change** — design only, awaiting approval.
