# Delegation-First Operating Model & Workforce Policies

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

The behavioural core of LisaOS 3.0: how a sprint runs delegation-first, and the **Workforce Modes** that re-bind employees to models for different situations.

---

## Part A — Delegation-First Operating Model

### A1. The reflex to install

Today a sprint begins with the main agent *doing*. 3.0 begins every sprint by *decomposing and assigning*. The main agent's first question is never "how do I do this?" — it is **"what is the execution graph, and who owns each node?"**

### A2. The 11-step loop (from `00 §5`, operationalised)

| # | Step | Owner | Output |
|---|---|---|---|
| 1 | Repository reality check | Main + Provider Mgr | fresh registry/git/OpenClaw state |
| 2 | Goal analysis | Main | goal, definition-of-done, active mode |
| 3 | Dependency graph | Main (+GPT burst assist) | DAG of packets |
| 4 | Work-packet decomposition | Main | packets + capability contracts + acceptance tests |
| 5 | Employee assignment | Dispatcher Mgr | packet→employee map |
| 6 | Provider/model resolution | Provider Mgr (L3) | packet→model, fail-closed |
| 7 | Parallel execution | Dispatcher Mgr | concurrent subagent spawns |
| 8 | Merge | Main | integrated result |
| 9 | Testing | QA Engineer | acceptance results |
| 10 | CTO review | CTO Reviewer (Opus) | approval / rework |
| 11 | Metrics & learning | Dispatcher Mgr | scores updated |

### A3. The scheduling invariant (the whole point)

> **If a capable employee is idle while a packet on the ready frontier is unassigned, that is a scheduling failure — counted, surfaced, and driven to zero.**

The "ready frontier" = packets whose graph dependencies are satisfied. The dispatcher's job each tick:

```
tick():
    frontier = packets with all deps done and not yet assigned
    idle     = employees with capacity, not currently running a packet
    for packet in frontier (priority order):
        emp = best idle employee whose capabilities ⊇ packet.contract
        if emp: assign+spawn(packet, emp)
        else:   record blocked(packet)   # no capable idle worker -> maybe escalate/import
    if idle_capable_employees and frontier_nonempty_but_unassigned:
        record scheduling_failure   # the metric that must trend to 0
```

### A4. What the main agent may and may not do

| May | May not |
|---|---|
| Decompose, sequence, merge, converse | Execute a packet it could delegate |
| Decide phase & mode | Choose worker models (L3 does) |
| Escalate to CTO office | Approve its own output |
| Hold the graph + decisions | Hoard context that should be handed off |

Anti-pattern flagged by metrics: **"main did it itself."** If the main runtime executes a delegable packet, delegation ratio drops and it is logged.

### A5. Parallelism discipline
- Spawn the **whole ready frontier**, not one packet at a time (subject to a concurrency cap for provider health).
- Independent branches of the graph run simultaneously across different employees/providers — this is where the speed comes from.
- A concurrency cap per provider prevents self-inflicted throttling (e.g. don't fire 20 DeepInfra calls at once); the cap is per-provider health-aware.

---

## Part B — Workforce Policies (Modes)

A **Mode** is a named bundle that re-binds employees to models and sets cost/health rules. The org chart is constant; the *hires* flex by mode. Selected per sprint (operator or phase-driven).

### B1. Mode definitions

Each mode specifies: main-runtime policy, allowed employees, preferred/fallback model bias, cost rules, subscription-usage rules, API-spend rules, provider-health requirements.

| Mode | Main runtime | Model bias | API spend | When |
|---|---|---|---|---|
| **Economy** | DeepSeek | Elastic + abundant-subscription only; **no Opus**, minimal premium | Prefer cheapest capable (DeepSeek/Qwen/GLM) | Routine bulk work, cost-sensitive |
| **Balanced** *(default)* | Phase-driven | Subscription-first; Opus for irreversible only | Elastic for bulk overflow | Normal sprints |
| **Premium** | Sonnet/Codex | Premium subscription throughout; Opus reviews | Minimal | High-stakes delivery |
| **Overnight** | DeepSeek | Elastic-heavy, high concurrency, no operator-blocking gates | Elastic OK (cheap, unattended) | Unattended batch runs |
| **Release** | GPT burst / Sonnet | Sonnet build + Opus gate + Release Mgr | Low | Release readiness |
| **Architecture** | Opus | Opus main; workers Sonnet/Codex | Low | Design/kernel sprints |
| **Research** | o3 / GPT | o-series + Qwen large-ctx | Moderate elastic | Investigations |
| **Emergency** | Best-available healthy | Whatever is healthy & fastest; relax cost rules | Allowed | Incident/outage |
| **CTO Review** | Opus | Opus only, read-mostly | None | Approval gates |
| **Local-First** | Haiku *(local = future)* | Haiku + subscription; **local models are future capacity, currently inert** (`10`) | Minimal | Offline/privacy/degraded network — **defined but not operational until local AI is installed + validated** |

### B2. Mode → employee re-binding (examples)

Same employee, different hire by mode:

| Employee | Economy | Balanced | Premium |
|---|---|---|---|
| Senior SW Eng | DeepSeek | Sonnet | Sonnet |
| SW Eng | Qwen-DeepInfra | Codex (gpt-5.5) | Codex |
| Implementation Eng | DeepSeek | DeepSeek | Sonnet |
| QA Engineer | Qwen-DeepInfra | Sonnet | Sonnet |
| Microtask Agent | Haiku (GLM ‡) | Haiku | Haiku |
| Chief Architect | *(disabled)* | Opus (irreversible only) | Opus |

‡ **GLM is probationary** — it only enters a mode's rotation on **low-risk** packets while under validation, and is retired if it fails (`04`, `06`). No mode routes critical work to GLM pre-validation. **Codex** entries across modes are likewise gated on identity validation (`15`). **Local AI** appears in no mode's active rotation (future capacity, `10`).

The Provider Resolver already takes a mode-aware `preferred_model`; modes are the policy layer feeding it. **No orchestration change to switch modes — a mode is data.**

### B3. Mode selection

```
mode = operator_override
    or phase_default(phase)          # Architecture->Architecture mode, Release->Release mode
    or time_default()                # unattended window -> Overnight
    or health_default(health)        # major provider outage -> Emergency/Local-First
    or Balanced                      # fallback default
```

### B4. Mode invariants
- Every mode still routes workers via L3 and still fails closed.
- No mode may make the main runtime route workers.
- `Emergency` may relax **cost** rules but never the **fail-closed** or **irreversible→Opus** rules.
- `Local-First` degrades gracefully to hosted models on capability escalation (local can't do it) — recorded, not silent. **Until local AI is installed and validated, `Local-First` runs entirely on hosted subscription models (Haiku) — the "local" tier is inert future capacity (`10`).**

---

## Part C — Why this produces speed

The operator's felt problem ("Lisa is slow") is an **idle-workforce** problem, not a model-speed problem. Delegation-first + the scheduling invariant + parallel frontier execution mean: at any moment, as many capable employees as possible are working in parallel, coordinated by a phase-appropriate (often cheap) main. The wall-clock time of a sprint approaches the **critical path of the graph**, not the sum of all packets run serially by one overworked main.
