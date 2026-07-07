# LisaOS 3.0 — Workforce Intelligence Architecture

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

---

## 1. The problem, stated precisely

LisaOS today has a working execution layer (after the provider-resolution fix) but its **scheduling intelligence is single-threaded in practice**. The main agent — whatever model is currently running as `main` — tends to do the work itself instead of decomposing it and handing packets to other models. The symptom the operator feels is *Lisa is slow*. The cause is not model speed; it is **idle workforce**.

Three structural facts produce this:

1. **No delegation-first reflex.** A sprint begins with the main agent *doing*, not *decomposing and assigning*. There is no step that forces "who should own each packet, and can they run in parallel?"
2. **The main runtime conflates coordination with labour.** Whatever model is `main` becomes both the dispatcher and the primary worker. When `main` is a heavy reasoning model, everything it touches is slow and serial.
3. **The organisation is described as `provider → model`.** There is no concept of an *employee* with a role, a preferred model family, fallbacks, and a utilisation target. So there is nothing for a scheduler to *keep busy*.

LisaOS 3.0 fixes the scheduling model, not the execution layer (which the provider resolver already fixed).

## 2. The resolution chain

The core redesign is a single, explicit resolution chain. Every unit of work flows through it:

```
Goal
  └─> Execution Graph        (decompose into work packets + dependencies)
        └─> Department        (which part of the org owns this class of work)
              └─> Employee    (a named role with responsibilities + utilisation target)
                    └─> Capability   (what the packet actually requires)
                          └─> Model Family    (Anthropic / OpenAI / DeepSeek / Qwen / GLM / local)
                                └─> Exact Model      (claude-sonnet-4-6, gpt-5.5, …)
                                      └─> Availability   (auth valid? provider healthy?)
                                            └─> Cost/Plan   (subscription capacity vs API spend)
                                                  └─> Runtime   (claude-cli / codex / openclaw / ollama)
```

Two properties matter more than the chain itself:

- **Employee before model.** Work is assigned to a *role*, and the role resolves to a model. This is what makes "adding a model = hiring an employee" true: a new model slots in as a candidate for existing roles without changing any orchestration logic.
- **Capability before provider.** The packet declares what it *needs* (long context, code execution, cheap bulk, irreversible judgement); the resolver picks the cheapest healthy model that satisfies it. Providers are interchangeable behind capabilities.

## 3. Ten principles (and how the architecture honours each)

| Principle | Architectural mechanism |
|---|---|
| **Delegate First** | Every sprint runs the 11-step delegation loop (§5). The main agent is forbidden from executing packets it could assign. |
| **Employee Before Model** | Roles are first-class registry objects; models are candidates bound at resolve time (`02`, `07`). |
| **Capability Before Provider** | Packets carry a capability contract; the resolver matches capability → model, not name → model (`08`). |
| **Subscription Before API Spend** | The cost model has **two currencies**; the scheduler spends perishable subscription capacity before elastic API tokens (`06`). |
| **Evidence Before Assumption** | Availability, cost, and utilisation come from inspected runtime state (`openclaw models status`, evidence JSONL), never static lists (`09`). |
| **Fail Closed, Never Silent** | Inherited from the provider resolver: an unresolved/unhealthy provider raises; it never silently becomes DeepSeek (`05`, `11`). |
| **Keep the Workforce Busy** | The dispatcher tracks idle capable employees against the ready frontier of the graph; idle-while-work-exists is a measured failure (`08`, `09`). |
| **Repository Truth Over Memory** | Every sprint starts with a repository reality check; registries on disk are authoritative over anything remembered (`08`). |
| **Main Runtime Does Not Control Worker Routing** | Worker routing always goes through the Workforce Manager / Provider Resolver, never the main model's own judgement (§4, `07`). |
| **Learn From Every Sprint** | Sprint metrics feed a learning store that tunes model/employee scores over time (`09`). |

## 4. Layered architecture

LisaOS 3.0 is five layers. The critical design rule is the **firewall between L2 and L3**: the main runtime coordinates but does not route workers.

```
┌───────────────────────────────────────────────────────────────────┐
│ L0  INTENT          Operator goal + active Workforce Mode           │
├───────────────────────────────────────────────────────────────────┤
│ L1  PLANNING        Repository reality check -> execution graph      │
│                     (packets, dependencies, capability contracts)    │
├───────────────────────────────────────────────────────────────────┤
│ L2  MAIN RUNTIME    Coordinates the graph. Selected *by phase*.      │
│     (MAIN-001)      MAY NOT decide which model a worker uses.        │
│        ┃  (firewall — main cannot route workers)                    │
├───────────────────────────────────────────────────────────────────┤
│ L3  WORKFORCE MGR   Employee assignment + Provider Resolver.         │
│     + DISPATCHER    Capability->employee->model->availability->cost. │
│                     Emits explicit `model` per spawn. Fails closed.  │
├───────────────────────────────────────────────────────────────────┤
│ L4  EXECUTION       OpenClaw subagents on claude-cli / codex /       │
│                     openclaw / ollama runtimes. Evidence recorded.   │
└───────────────────────────────────────────────────────────────────┘
                          │
                    ┌─────┴─────┐
                    │ L5 LEARN  │  metrics -> scores -> next-sprint tuning
                    └───────────┘
```

**Why the firewall matters.** If the main model chooses worker models, then routing quality is hostage to whichever model happens to be `main` this session — exactly the coupling that produces the monoculture. By forcing all worker routing through L3 (the deterministic Workforce Manager built on the existing `provider_resolver.py`), routing quality is invariant to the main model. The main model can be swapped for cost or phase reasons without changing how workers are chosen.

## 5. The delegation-first sprint loop

Every sprint executes these 11 steps. Steps 5–8 are the part LisaOS does not currently do reflexively.

1. **Repository reality check** — inspect registries, git state, OpenClaw availability. Truth over memory.
2. **Goal analysis** — restate the goal, define done, define the active Mode.
3. **Dependency graph** — build the execution graph: packets + edges.
4. **Work-packet decomposition** — each packet gets a capability contract + acceptance test.
5. **Employee assignment** — map each packet to a department/employee.
6. **Provider/model resolution** — L3 resolves each employee → exact model → runtime, fail-closed.
7. **Parallel execution** — dispatch every packet on the ready frontier concurrently; keep the workforce busy.
8. **Merge** — integrate worker outputs; resolve conflicts.
9. **Testing** — QA employee validates against acceptance tests.
10. **CTO review** — Opus reviews irreversible/architectural decisions before acceptance.
11. **Metrics & learning** — record utilisation, cost, defects, fallbacks; update scores.

**Scheduling invariant:** *If a capable employee is idle while a packet on the ready frontier is unassigned, that is a scheduling failure and is counted as one.* This single invariant is what forces parallelism.

## 6. What changes vs. what is preserved

**Preserved (already correct):**
- The provider resolver (`core/provider_resolver.py`) and `registry/provider_resolution.yml` — the fail-closed logical→physical binding. L3 is built *on* this, not instead of it.
- The two-currency economic insight from S024 (`COST_OPTIMISATION_REPORT.md`).
- Repository boundaries and capability/policy governance.

**Changed / added:**
- **Employees** become first-class (`registry/employees.yml`, proposed) replacing the thin runtime placeholders in `runtimes.yml`.
- **Dynamic main runtime** (MAIN-001) selected by phase, decoupled from worker routing.
- **Workforce Modes** (Economy/Balanced/Premium/Overnight/…) as named policy bundles.
- **A scheduler** that measures and enforces utilisation.
- **A learning store** that tunes routing from sprint outcomes.
- **A cleanup** removing the competing old abstraction (`cost_tier` runtime placeholders) and dead artifacts.

## 7. Non-goals (explicit)

- This is **not** a rewrite of OpenClaw. OpenClaw already honours explicit `model` and provides the runtimes we need.
- This does **not** touch WBS or any other repository.
- Local models are **not** assumed to replace any hosted worker (see `10` for the honest assessment).
- No code, registry, or OpenClaw change is made under this document. It is a design for approval.

## 8. Success criteria for 3.0

| Criterion | Target |
|---|---|
| Delegation ratio (packets delegated ÷ delegable packets) | ≥ 0.8 in Balanced mode |
| Worker utilisation during active sprints | ≥ 60% of capable employees busy on the ready frontier |
| Silent DeepSeek monoculture | Eliminated (already true at execution layer; extend to scheduling) |
| Subscription-before-API adherence | ≥ 90% of subscription-eligible packets run on subscription capacity |
| Adding a new model | No orchestration code change — registry entry only |
| Idle-while-work-exists incidents | Trending to zero across sprints (learning loop) |

The rest of the document set specifies each layer.
