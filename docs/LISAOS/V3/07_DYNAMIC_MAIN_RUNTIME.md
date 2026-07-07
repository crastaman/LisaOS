# Dynamic Main Runtime Strategy (MAIN-001)

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

The main runtime is the model currently running the coordination loop. Today it is fixed to `custom-api-deepseek-com/deepseek-reasoner` (the verified global default). LisaOS 3.0 makes it **dynamic — selected by sprint phase** — while enforcing the hard rule that **the main runtime never routes workers.**

---

## 1. Two jobs that must not be confused

| Job | Who does it | 3.0 rule |
|---|---|---|
| **Coordinate** the sprint (read graph, sequence phases, merge, converse with operator) | The main runtime (MAIN-001) | Selected by phase |
| **Route workers** (which model runs each packet) | The Workforce Manager / Provider Resolver (L3) | **Never** the main runtime |

The failure mode 3.0 prevents: the main model, being the thing "in charge", also decides worker models — so routing quality tracks whichever model is main, and a cheap main produces cheap routing (the monoculture). **Decoupling these is the single most important control in the architecture** (the L2/L3 firewall, `00 §4`).

## 2. MAIN-001 is a slot, not a model

MAIN-001 is a *role* — "the coordinator for this phase" — filled by different models as the sprint moves through phases. Selection inputs: current phase, active Workforce Mode (`08`), provider health, subscription state.

### Phase → main runtime map

| Phase | Preferred main | Why | Never |
|---|---|---|---|
| Architecture / kernel design | **Opus** (`claude-opus-4-8`) | Irreversible judgement; worth the scarce quota | — |
| CTO review / final approval | **Opus** | Approval gate | — |
| Implementation-heavy session | **Sonnet** (`claude-sonnet-4-6`) or **Codex** | Premium engineering coordination close to the work | GPT (limits) |
| Long-running orchestration (default) | **DeepSeek** (`deepseek-reasoner`) | Always-on, cheap elastic; tolerates long sessions | — |
| Microtask / ops session | **Haiku** (GLM-turbo only if validated) | Cheap coordination for cheap work | Opus (waste); GLM pre-validation; local (not active) |
| Short governance / planning burst | **GPT-5.5** | Strong planning in short bursts | GPT as *long-running* main |
| Research session | **o3 / GPT** | Deep reasoning coordination | — |

### Hard constraints (verified rationale)
- **GPT is never long-running main.** OpenAI OAuth + GPT usage limits hit fast on long sessions (observed ~41h token to expiry, and GPT limit behaviour). GPT is a *burst* coordinator only.
- **Opus is guarded.** Only architecture/review phases justify Opus-as-main; otherwise it coordinates via delegation from a cheaper main.
- **DeepSeek remains the safe default main** for ordinary long-running work — but as an *explicit phase choice*, not an unexamined fallback.

## 3. Selection algorithm

```
select_main(phase, mode, health):
    candidate = MODE_MAIN[mode].get(phase)             # mode may override the phase map
    candidate = candidate or PHASE_MAIN[phase]         # default phase map
    if not ProviderResolver.resolve(candidate, mode).available:
        candidate = next healthy in MAIN_FALLBACK[phase]   # explicit, recorded
    if candidate is GPT and session.is_long_running:
        candidate = DeepSeek                            # hard guard
    record_main_selection(phase, mode, candidate, reason)
    return candidate
```

`MAIN_FALLBACK` chains are explicit and recorded — a main switch is evidence, never silent. Example: architecture phase fallback `opus-4-8 → opus-4-7 → sonnet-4-6 (+flag: degraded-architecture, surface to operator)`.

## 4. Mid-sprint main switching

A sprint can change main between phases. Rules:
- **Switch on phase boundaries**, not mid-packet.
- Carry a **compact handoff** (Context Manager, `02`) — the incoming main gets the graph state + decisions, not the full transcript (token discipline, `LISAOS_TOKEN_EFFICIENCY_GUIDE.md`).
- Every switch recorded: `{from, to, phase, reason}` for the learning loop.
- **Worker routing is unaffected** by a main switch — because L3, not main, routes workers. This is what makes switching safe.

## 5. Why this is safe (invariant restated)

Because worker routing is L3's job:
- Swapping main for cost (Opus→DeepSeek at end of an architecture phase) does not change how workers are chosen.
- A degraded main (fallback to a lesser model) still dispatches workers via the same deterministic resolver.
- Routing quality is **invariant to the main model.** The main can be optimised purely for coordination cost/quality of the current phase.

## 6. Operator visibility

The active main and the reason are surfaced (e.g. in the morning brief / status): `MAIN-001 = claude-sonnet-4-6 (phase: implementation, mode: balanced)`. The operator can pin a main for a session (mode override) but **cannot make the main route workers** — that path does not exist by design.
