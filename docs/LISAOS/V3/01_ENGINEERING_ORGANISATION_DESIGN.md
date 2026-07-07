# Engineering Organisation Design

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

LisaOS 3.0 is modelled as an engineering organisation. This document defines the **departments**, the **org chart**, and the **assignment rules** that turn a goal into staffed work. Individual employee specs are in `02_EMPLOYEE_CAPABILITY_MATRIX.md`.

---

## 1. Why an org, not a model pool

A model pool answers "which model is cheapest that can do this?". An organisation answers "who **owns** this, who reviews it, who is idle, and who do we escalate to?". The org abstraction gives LisaOS the three things a pool lacks:

- **Ownership** — every packet has a responsible employee, so accountability and utilisation are measurable.
- **Escalation** — roles form a seniority ladder (Implementation → Senior → Chief Architect → CTO Reviewer) so hard problems escalate instead of being under-served or over-served.
- **Substitutability** — an employee is a role bound to a *preferred* model with *fallbacks*; swapping the model behind a role is a config change, not a redesign. **Hiring a model = adding a candidate to a role.**

## 2. Departments

Six departments. Each owns a class of work and a set of employees.

```
                      ┌──────────────────────────┐
                      │  OFFICE OF THE CTO        │
                      │  Chief Architect          │  Opus  (architecture, irreversible)
                      │  CTO Reviewer             │  Opus  (final approval gate)
                      └────────────┬─────────────┘
                                   │ escalation / approval
      ┌───────────────┬───────────┼───────────────┬───────────────┐
      ▼               ▼           ▼               ▼               ▼
┌───────────┐  ┌───────────┐ ┌──────────┐  ┌───────────┐  ┌────────────┐
│ENGINEERING│  │  QUALITY  │ │RESEARCH &│  │OPERATIONS │  │  PLATFORM  │
│           │  │           │ │   DOCS   │  │           │  │            │
│Sr SW Eng  │  │QA Engineer│ │Research  │  │Ops Engineer│  │Platform Eng│
│SW Eng     │  │Debugging  │ │ Engineer │  │Microtask   │  │Provider Mgr│
│Impl Eng   │  │Specialist │ │Doc Eng   │  │ Agent      │  │Dispatcher  │
│           │  │           │ │          │  │Release Mgr │  │ Manager    │
│           │  │           │ │          │  │            │  │Context Mgr │
└───────────┘  └───────────┘ └──────────┘  └───────────┘  └────────────┘
```

| Department | Owns | Primary employees | Default model class |
|---|---|---|---|
| **Office of the CTO** | Architecture, irreversible decisions, final approval | Chief Architect, CTO Reviewer | Opus (subscription, scarce) |
| **Engineering** | Building, refactoring, implementing | Senior SW Engineer, SW Engineer, Implementation Engineer | Sonnet / Codex / DeepSeek |
| **Quality** | Correctness, tests, debugging | QA Engineer, Debugging Specialist | Sonnet / Codex |
| **Research & Docs** | Investigation, synthesis, documentation | Research Engineer, Documentation Engineer | o-series / GPT-burst / Qwen / GLM |
| **Operations** | Microtasks, ops, releases, dashboards | Ops Engineer, Microtask Agent, Release Manager | Haiku / GLM-turbo / local |
| **Platform** | Routing, providers, context, dispatch | Provider Manager, Dispatcher Manager, Context Manager | deterministic (code) + GPT-burst |

**Platform is special:** its "employees" are largely deterministic LisaOS components (the Provider Resolver *is* the Provider Manager). They are org citizens so the chart is complete, but they are not LLM roles that burn capacity — critically, the **Dispatcher Manager routes workers and the main runtime does not** (the L2/L3 firewall from `00`).

## 3. Seniority ladder & escalation

```
Microtask Agent  <  Implementation Eng  <  SW Eng  <  Senior SW Eng  <  Chief Architect  <  CTO Reviewer
   (Haiku/GLM)       (DeepSeek/Qwen)       (Sonnet)     (Sonnet/Codex)      (Opus)            (Opus)
```

Escalation rules:
- A packet is assigned to the **lowest-seniority employee whose capabilities satisfy the contract** (cost discipline — don't put Opus on a docstring).
- If an employee fails its acceptance test twice (retry budget), the packet **escalates one rung**. Recorded as a `retry`/`escalation` metric.
- **Irreversible or architectural** packets skip the ladder and go straight to the CTO office (capability tag `irreversible-judgement`).
- The **CTO Reviewer is an approval gate, not a worker** — it reviews others' output; it does not implement.

## 4. Assignment algorithm (per packet)

```
assign(packet):
  contract   = packet.capability_contract            # required capabilities
  dept       = department_for(contract)               # class of work -> department
  candidates = employees(dept) filtered by capabilities ⊇ contract
  employee   = lowest_seniority(candidates)           # cost discipline
  resolution = ProviderResolver.resolve(employee.preferred_model, mode)  # L3, fail-closed
  if not resolution.available:
      resolution = try_fallbacks(employee.fallback_models, mode)  # explicit, recorded
  if not resolution.available:
      FAIL CLOSED  (surface; never silently downgrade to DeepSeek)
  return Assignment(packet, employee, resolution)
```

Two rules make it an *organisation* rather than a lookup table:

1. **Mode-aware preferred model.** The same employee resolves to different models under different Workforce Modes (`08`). In Economy mode the Senior SW Engineer might resolve to DeepSeek; in Premium mode to Sonnet. The *role* is stable; the *hire* flexes with policy.
2. **Utilisation feedback.** The Dispatcher Manager will prefer spreading packets across idle employees over queueing them all on one, when capabilities allow — this is what "keep the workforce busy" means in practice (`09`).

## 5. Adding a new model = onboarding

The onboarding runbook (detailed in `05`) is deliberately org-shaped:

1. **Interview** — add the model to `registry/provider_resolution.yml` with capability tags and credential descriptor. Resolver reports it AVAILABLE/UNAVAILABLE honestly.
2. **Job description** — list it as a candidate (`preferred` or `fallback`) on one or more employees in `registry/employees.yml`.
3. **Probation** — first N sprints it runs only on low-risk packets; metrics accrue a model performance score (`09`).
4. **Confirmation** — if its score clears threshold, it may become a `preferred` model for its role.

No orchestration code changes at any step. That is the whole point of the design.

## 6. Org invariants

- Every packet has exactly one responsible employee.
- No employee both implements and approves the same packet (separation of duties: CTO Reviewer ≠ author).
- Worker model selection is **always** L3's decision, never the main runtime's.
- An idle capable employee while ready work exists is a **scheduling defect**, logged as such.
