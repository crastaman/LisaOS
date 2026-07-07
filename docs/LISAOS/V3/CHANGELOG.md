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

---

## Round 2 — Final architecture validation (2026-07-07)

Pre-Phase-0 validation: complete OpenClaw inventory, coverage/gap analysis, registry cleanup + integrity validation, and an Anti-Regression Framework.

### C5 — Complete OpenClaw model inventory
- New doc **`16_OPENCLAW_MODEL_INVENTORY.md`**: all **56** catalogue models (live `openclaw models list --json`), each with provider, exact ID, display name, backend, auth status, availability, runtime, recommended employee + capability, and active/candidate/probationary/retired classification.
- Availability nuance documented: catalogue `available` ≠ authenticated/healthy; OpenAI per-provider live enumeration (3) is narrower than the catalogue (16) — confirm-before-hire.

### C6 — Workforce coverage & gap analysis
- New doc **`17_WORKFORCE_COVERAGE_AND_GAP.md`**: verifies every required family/flavour (Opus/Sonnet/Haiku; GPT/Pro/Mini/Nano/Codex/o-series; DeepSeek; DeepInfra Qwen; GLM; local).
- **Honest negatives:** GPT "Instant" and GPT "Flash" do not exist in this install.
- Gaps closed: Claude Fable 5, GPT nano, GLM/Kimi vision, DeepSeek-V4-Flash huge-context, DeepInfra bench — all now classified.

### C7 — Provider registry cleanup + integrity validation (EXECUTED in repo)
- New doc **`18_PROVIDER_REGISTRY_AUDIT_AND_CLEANUP.md`**.
- **`registry/provider_resolution.yml`**: removed `qwen-alibaba` and all its aliases (`ali-qwen`, `qwen-modelstudio`, `alibaba-qwen`); no entry references `codex-model-studio` → Codex/Qwen ambiguity eliminated; `codex` = OpenAI (verified live). 6 approved providers remain.
- **`tests/test_provider_resolution.py`**: updated to assert the cleanup (removal, single-Qwen, no codex-model-studio, codex=OpenAI). **23/23 pass** (was 20).
- Integrity validated: no duplicate providers, no conflicting aliases, no incorrect identities, no silent fallbacks, no orphaned employee mappings, no stale aliases.
- **Live `~/.openclaw/openclaw.json` NOT mutated** — Alibaba block removal + `qwen` alias repoint + DeepSeek key fix deferred to Phase 0 (0.2/0.3/0.7).

### C8 — Anti-Regression Framework
- New doc **`19_ANTI_REGRESSION_FRAMEWORK.md`**: rules for 12 old habits; 8 KPIs (delegation ratio, main-agent work ratio, provider utilisation, idle worker time, fallback rate, silent-fallback count, parallelism ratio, context safety events); pre-sprint checks (P1–P5); post-sprint checks (Q1–Q5); fail conditions (F1–F5, silent fallback = hard fail); regression test plan (RT1–RT8).
- Gates wired into `13_IMPLEMENTATION_ROADMAP.md` per phase.

### Docs updated this round
`README.md`, `03` (Alibaba removed / Fable / huge-context reroute), `11` (Alibaba removed, chain rerouted), `13` (Phase 0 + anti-regression gates). New: `16`, `17`, `18`, `19`. Registry + tests changed (see C7).

---

---

## Round 3 — Phase 0 implementation (2026-07-07)

Approved and executed. Full detail in `PHASE0_IMPLEMENTATION_REPORT.md`.

- **0.4 Haiku** added to registry (`claude-haiku` → `anthropic/claude-haiku-4-5`); resolves AVAILABLE.
- **0.6 GLM** added as **probationary** (`glm`, `glm-turbo`, `probation: true`, `critical_routing: false`); resolve AVAILABLE.
- **0.5 Codex identity validated** with runtime evidence — live `openclaw infer model run` returned `provider: openai, model: gpt-5.5`; evidence in `provider_resolution_evidence.jsonl`.
- **0.2 Qwen alias repointed (live)** — OpenClaw `qwen` → `deepinfra/Qwen/Qwen3.6-35B-A3B` (was Alibaba). Config backed up + validated.
- **Tests:** 24/24 pass (+1 for Phase-0 providers).
- **0.3 done (operator-authorized, 2026-07-08):** the live Alibaba provider was **used by WBS agent `wbs-worker-qwen`**. Operator authorized repointing that worker → `deepinfra/Qwen/Qwen3.6-35B-A3B` (fixes its 403s), then the `codex-model-studio` provider was **fully removed** from `openclaw.json` + the main agent `models.json`. Verified gone from the catalog; live providers now custom-api-deepseek-com / zai / deepinfra only. WBS **repository** untouched.
- **0.7 deferred (operator choice):** corrupt native `deepseek:default` key — unused, breaks nothing; leave for now, clean later via `openclaw models auth`.

New: `PHASE0_IMPLEMENTATION_REPORT.md`. Changed: `registry/provider_resolution.yml` (+claude-haiku, +glm, +glm-turbo), `tests/test_provider_resolution.py` (+Phase-0 test), `13`, this changelog. Live `~/.openclaw` net change: `qwen` alias only.

---

## Round 4 — Phase 1 implementation: Employee Registry + Workforce Routing Foundation (2026-07-08)

Approved and executed. Full detail in `PHASE1_IMPLEMENTATION_REPORT.md`, `20`, `21`, `22`, `PHASE1_TEST_REPORT.md`.

- **Employee Registry** (`registry/employees.yml`) — all 15 required employees, each with department, responsibilities, capabilities, preferred model family + exact model, fallback models, cost/subscription class, reliability class, best/avoid tasks, and failure policy. Validates (`bin/lisa-workforce validate`).
- **Workforce Resolver** (`core/workforce_resolver.py`) — implements `WorkPackage → capabilities → candidate employees (seniority-sorted) → preferred model → ProviderResolver → physical runtime → WorkAssignment`. Fail-closed (no capable employee / no available model across the whole chain never silently substitutes DeepSeek); explicit recorded fallback; GLM/GLM-turbo probation restriction (low-risk only); `routed_by="workforce_resolver"` on every assignment — the main runtime cannot set this.
- **Anti-Regression Gates** (`core/anti_regression.py`) — 7 pure gates covering all required checks (no silent fallback, intended==actual runtime, main-not-majority, no stale alias, DeepSeek-not-gravity-well, no-idle-while-ready, context safety) + pre/post-sprint aggregators.
- **Router wiring (additive)** — `core/router.py` gains `resolve_work_package()`/`get_workforce_resolver()` under a "WORKFORCE ROUTING LAYER (Phase 1)" section; the legacy `ENGINES`/`choose_engine()` are explicitly marked "LEGACY ROUTING LAYER (superseded — kept for compatibility)". Nothing removed.
- **Legacy registry marked superseded** — `registry/runtimes.yml` header now states it is replaced by `employees.yml` + `provider_resolution.yml` + `workforce_resolver.py`, kept for compatibility only.
- **CLI** (`bin/lisa-workforce`) — `employees` / `validate` / `assign <caps> [risk] [mode]` / `gates`, executable, smoke-tested live against the real registries.
- **Blocker found and fixed (minimal):** `EmployeeRegistry._build_employees()` crashed with `KeyError` on a malformed registry instead of letting `validate()` report it; fixed by using `spec.get(field, "unknown")` so construction never crashes and `validate()` remains the source of truth. No design change.
- **Tests:** 53 new (`tests/test_workforce_resolver.py` ×27, `tests/test_anti_regression.py` ×26); combined with the pre-existing 24, **77/77 pass**. All six required assignment scenarios (Haiku microtask, Sonnet implementation, Opus architecture, Qwen-DeepInfra docs, Codex implementation, DeepSeek orchestration) verified both in tests and live via the CLI.

New: `registry/employees.yml`, `core/workforce_resolver.py`, `core/anti_regression.py`, `bin/lisa-workforce`, `tests/test_workforce_resolver.py`, `tests/test_anti_regression.py`, `PHASE1_IMPLEMENTATION_REPORT.md`, `20_EMPLOYEE_REGISTRY_REPORT.md`, `21_WORKFORCE_RESOLVER_REPORT.md`, `22_ANTI_REGRESSION_VALIDATION_REPORT.md`, `PHASE1_TEST_REPORT.md`. Changed: `core/router.py` (additive), `registry/runtimes.yml` (header only), this changelog. WBS not touched; OpenClaw not restarted.

---

## Standing invariants reaffirmed
- **Fail closed, never silent** — unchanged; now enforced at both the provider layer (Phase 0) and the workforce layer (Phase 1).
- **No secret ever committed** — unchanged.
- **Evidence before assumption** — strengthened: model identity and trust are established by runtime/provider evidence, never by a name or list label.
- **Main runtime does not control worker routing** — now enforced in code: every `WorkAssignment.routed_by == "workforce_resolver"`.
- **Old routing is superseded, not deleted** — the legacy provider/cost_tier abstraction remains functional for compatibility while the employee-based layer takes over new routing.
