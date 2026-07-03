# LisaOS Foundation v3 — Complete

**Version:** 3.0  
**Status:** Active — Foundation Complete  
**Created:** 2026-07-03  
**Job ID:** L007A-LISAOS-FOUNDATION-CLOSURE

> The LisaOS Foundation v3 is complete. This document marks the milestone and captures the core engineering and architecture principles established during the foundation phase.

---

## 1. Executive Summary

LisaOS Foundation v3 is a complete, internally consistent design for an AI operating system. It defines how work enters the system, how agents are selected, how runtimes are resolved, how context is managed, how execution happens, how validation occurs, and how knowledge persists.

The Foundation is **design-complete**, not implementation-complete. The architecture, governance, and engineering principles are stable and documented. What remains is production-driven implementation — and that will come from real engineering needs discovered during WBS development.

### Why the Foundation Is Considered Complete

| Criteria | Status | Evidence |
|----------|--------|----------|
| Architecture defined | ✅ | Kernel, Orchestration, Runtime layers fully documented |
| Core decisions captured | ✅ | ADRs cover queue, context, runtime resolution, fallback, artifact-first, error recovery, provider neutrality, release pipeline, memory |
| Governance documented | ✅ | Governance rules, repository boundaries, security, policies |
| Runtime model specified | ✅ | Resolver design, scoring model, health checks, provider strategies |
| Agent framework defined | ✅ | Agent identities, templates, templates, capability routing |
| Communication model specified | ✅ | Artifact-first, 8 artifact types, release pipeline |
| Context management documented | ✅ | Budgets, compaction, priority chain, session rotation |
| Engineering principles stated | ✅ | Model-independence, artifact-first, capability-first, documentation-as-truth, repository discipline |

There are no unresolved architectural questions. Every design decision has been made and documented. The remaining work is implementation and refinement from production experience.

---

## 2. Foundation Timeline

| Milestone | Date | Scope |
|-----------|------|-------|
| L001 — Registry Foundation | 2026-07-02 | Agent registry, capability registry, runtime registry, job type registry |
| L001.5 — Registry Governance Review | 2026-07-02 | Schema governance, policy profiles, policy constraints, ADR framework |
| L002 — Agent Framework | 2026-07-02 | Agent identity, templates, template library, reuse policy |
| L003 — Runtime Execution Framework | 2026-07-02 | Runtime registry, provider documentation, resolver specification, health checks |
| L004 — Release & QA Playbooks | 2026-07-02 | Release pipeline, QA standards, WordPress constraints, migration playbooks |
| Foundation Review | 2026-07-02 | Kernel architecture, Kernel decisions, ecosystem, manifest, governance |
| L005 — Runtime Routing Architecture | 2026-07-02 | Runtime resolver design, scoring model, provider strategies |
| L006 — Agent Communication Architecture | 2026-07-03 | Artifact-driven communication, 8 artifact schemas, handoff rules |
| L007 — OpenClaw Orchestration Architecture | 2026-07-03 | Session lifecycle, context loading, execution monitoring, error recovery |
| L007A — Foundation Closure | 2026-07-03 | Milestone documentation, principle consolidation, production-first direction |

---

## 3. Completed Milestones

### 3.1 Architecture Documents

- `docs/LISAOS/KERNEL.md` — Kernel execution model
- `docs/LISAOS/KERNEL_DECISIONS.md` — 11 architecture decision records
- `docs/LISAOS/KERNEL_REVIEW.md` — Kernel architecture critical review
- `docs/LISAOS/ECOSYSTEM.md` — BAR Technologies ecosystem
- `docs/LISAOS/MANIFEST.md` — LisaOS purpose and scope
- `docs/ARCHITECTURE/LISA_CORE_ARCHITECTURE_V1.md` — Core architecture
- `docs/ARCHITECTURE/LISA_OPENCLAW_INTEGRATION.md` — OpenClaw integration
- `docs/ADR/ADR-0001-ENGINE-ABSTRACTION.md` — Engine abstraction
- `docs/ADR/ADR-0002-CAPABILITY-ROUTING.md` — Capability routing

### 3.2 Design Study Documents (L005-L007)

- `L005_RUNTIME_ROUTING_ARCHITECTURE.md` — Runtime resolver, scoring model, fallback chains
- `L006_AGENT_COMMUNICATION_ARCHITECTURE.md` — 8 artifact types, schemas, handoff rules
- `L007_OPENCLAW_ORCHESTRATION_ARCHITECTURE.md` — Session lifecycle, context loading, error recovery
- `L005_L007_DESIGN_REVIEW.md` — Architecture assessment, risks, recommendations
- `LISAOS_CONTEXT_MANAGEMENT.md` — Context budgets, compaction, memory hierarchy
- `LISAOS_RUNTIME_SELECTION_POLICY.md` — Selection rules, edge cases, enforcement
- `LISAOS_ARTIFACT_LIFECYCLE.md` — Lifecycle states, storage layout, retention
- `LISAOS_TOKEN_EFFICIENCY_GUIDE.md` — Token economics, best practices, anti-patterns
- `LISAOS_IMPLEMENTATION_RECOMMENDATIONS.md` — Implementation phases, complexity, order

### 3.3 Registry Files

- `registry/agents.yml` — Agent definitions with runtime profiles and fallback chains
- `registry/capabilities.yml` — Capability definitions
- `registry/runtimes.yml` — Runtime registrations
- `registry/jobs.yml` — Job type definitions
- `lisaos/policies/routing.yml` — Job type routing rules

### 3.4 Governance Documents

- `governance/GOVERNANCE.md` — 10 governance rules
- `governance/SECURITY.md` — Security policy
- `docs/LISAOS/REPOSITORY_BOUNDARIES.md` — Repository boundary rules

### 3.5 Release & QA Documents

- `workflows/lisaos/release-pipeline.md` — Release pipeline
- `workflows/lisaos/qa-standards.md` — QA standards
- `workflows/lisaos/wordpress-constraints.md` — WordPress constraints
- `workflows/lisaos/playbooks/` — Migration, dual-write, backfill, runtime verification playbooks

---

## 4. Core Engineering Principles

### 4.1 LisaOS Evolves from Production Experience

This is the most important principle of the Foundation.

LisaOS was designed through speculative architecture to establish a coherent operating model. That phase is now complete. Moving forward, LisaOS capabilities must emerge from real engineering needs discovered during WBS development.

**Why:**

- **Real engineering reveals better abstractions.** The file formats, handoff patterns, and workflows that look correct in a design document may need adjustment when faced with real production constraints. Production experience will expose what actually matters.
- **Production uncovers missing capabilities.** A runtime registry covers the runtimes we know about today. WBS development will reveal runtime characteristics we didn't think to track — cost anomalies, reliability patterns, capability gaps. Those discoveries should drive registry evolution.
- **Avoid unnecessary framework complexity.** Speculative architecture tends to over-engineer because it cannot distinguish between essential complexity and imagined edge cases. Production experience acts as a natural filter: only real problems get solutions.
- **WBS is LisaOS' first proving ground.** Every design decision from the Foundation is testable against real WBS work. Capability routing, context management, artifact handoffs — all of these will be validated or invalidated by WBS execution.

**Policy:** No new LisaOS capability should be defined without evidence from production use. Speculative feature development is explicitly deprioritised.

### 4.2 Artifact-First Communication

Inter-agent communication must use structured, versioned, immutable artifacts. Chat history is never used as a durable communication channel between agents.

**What this means in practice:**

- Every agent handoff produces a file in the `jobs/` directory.
- Artifacts follow defined schemas and lifecycle states.
- Artifacts are the durable engineering memory — they persist across sessions, across days, across agent restarts.
- Chat sessions remain temporary working memory. When a session ends, the information worth keeping is already in artifacts.

**Why artifact-first matters:**

| Without Artifacts | With Artifacts |
|------------------|---------------|
| Knowledge lives in chat logs | Knowledge lives in structured files |
| Session restart loses context | Session restart reads artifacts |
| Cross-agent handoff requires shared history | Cross-agent handoff writes and reads files |
| Audit trail is a conversation dump | Audit trail is schematised decision records |
| Token bloat from chat repetition | Compact, structured summaries |

This is not aspirational. It is a standard. Engineering work that transfers context through chat history rather than artifacts is non-compliant with LisaOS Foundation v3.

### 4.3 Context Philosophy

**OpenClaw manages orchestration.** Session lifecycle, tool execution, output capture — these are OpenClaw responsibilities.

**Repository documentation is durable memory.** ADRs, architecture documents, business rules, and governance documents persist in the Git repository. They are the authoritative source of truth. They outlive every session.

**Artifacts are durable execution memory.** The job packets, implementation reports, review reports, and decision logs produced during execution are permanent records. They survive session rotation, agent changes, and provider switches.

**Agent sessions are temporary.** A session begins, executes, and ends. Its working memory (conversation history, tool output, scratch notes) is ephemeral. Anything worth preserving from a session is extracted into an artifact or documentation update before the session ends.

**Fresh sessions are preferred after sprint completion.** Starting clean prevents context bleed, reduces token costs, and ensures deterministic starting state.

**Transcript accumulation should be avoided wherever possible.** Long, meandering conversations that generate large transcripts but produce no artifacts are a sign of process failure, not productivity.

### 4.4 Runtime Philosophy

**LisaOS does not choose models. LisaOS chooses capabilities.**

The Runtime Resolver maps capability requirements to available providers. The agent says "I need repository_write and git," not "I need Claude Code."

**Provider neutrality is an architectural requirement.**

- No critical workflow depends on a single AI provider.
- Every provider can be replaced without architectural change.
- Runtime registrations are data, not code.
- Scoring model weights are configurable, not hardcoded.

**Why provider neutrality matters:**

- Prevents vendor lock-in — no provider becomes irreplaceable.
- Enables cost optimisation — cheaper providers can serve equivalent capabilities.
- Supports resilience — if a provider goes down, the system falls back to another.
- Avoids single-provider policy risk — provider policy changes do not require architecture changes.

### 4.5 How LisaOS Evolves

New LisaOS capabilities should normally originate from:

| Source | Description | Example |
|--------|-------------|---------|
| WBS implementation | A real engineering task reveals a missing capability | "We need a migration report artifact type" |
| QA discoveries | Testing reveals a gap in validation or reporting | "QA needs a diff-summary stage" |
| Production incidents | An operational failure exposes a missing check or process | "We need a pre-deploy security gate" |
| Release retrospectives | Post-release review identifies an improvement | "Release notes should auto-generate from job artifacts" |
| Engineering friction | A repeated pattern of frustration or wasted effort | "Every job manually computes token budgets — needs automation" |
| Recurring patterns | The same work is done differently each time | "Three different jobs each wrote their own diff format — standardise" |

**What is not an acceptable origin for new capabilities:**

- Speculation about future needs
- Hypothetical scaling concerns without evidence
- "Best practice" recommendations from unrelated contexts
- Desire for framework-like features without concrete usage

The operating principle: **LisaOS grows from the bottom up, not the top down.**

---

## 5. Architecture Principles

### 5.1 Layer Separation

```
Kernel       — what to do (declarative lifecycle, policy)
Orchestration — how to execute (session lifecycle, dispatch, monitoring)
Runtime      — where to execute (model provider, health, capabilities)
```

Each layer has clear responsibilities. No layer reaches into another's domain.

### 5.2 Model Independence

No critical workflow depends on a single AI provider. Every provider can be replaced.

### 5.3 Workflow Over Models

Business intelligence resides in architecture, ADRs, governance, documentation, and process — not in AI models.

### 5.4 Documentation Is Truth

Documentation defines reality. AI reads documentation. AI never becomes the source of truth.

### 5.5 Capability-First Security

Agents have explicit allowed and prohibited capabilities. Globally prohibited operations are never delegated.

### 5.6 Human Governance

Humans retain final authority over architecture, security, approvals, repository boundaries, and production-impacting changes.

### 5.7 Independent Verification

Implementation and verification remain separate responsibilities. No agent verifies its own work.

### 5.8 Repository Boundary Discipline

Every job must verify repository, working directory, target path, branch, and output scope before writing files. Cross-repository writes are strictly constrained.

---

## 6. Governance Principles

1. **Respect the Kernel** — honour the execution lifecycle for every job.
2. **Document before implementing** — architecture precedes code.
3. **Enforce repository boundaries** — know which repo you are in before writing.
4. **Use registries** — centralised sources of truth.
5. **Keep code and documentation together** — no orphan decisions.
6. **Favour human-readable formats** — YAML over JSON, Markdown over HTML.
7. **Prefer local execution** — cloud is intentional.
8. **Audit when uncertain** — document the question, not the assumption.
9. **When in doubt, ask Roshan.**

---

## 7. What Comes Next

The Foundation is complete. There is no L008 that extends the architecture. The next phase is production application.

### Recommended Direction

**Use WBS as the first production proving ground for LisaOS.**

Every Foundation design — capability routing, context management, artifact handoffs, runtime resolution — should be validated against real WBS engineering work. The patterns that prove useful become permanent. The patterns that don't are revised or discarded.

**What this looks like in practice:**

- Engineering jobs in WBS should follow the Foundation's job packet pattern.
- Artifacts (implementation reports, decision logs) should be written during WBS work.
- When a handoff between agents is needed, it should use the artifact-first pattern.
- When a runtime choice matters, the capability-first approach should guide selection.
- When context is overloaded, the compaction and rotation strategies should be applied.

**What is explicitly NOT happening:**

- No artifact validation scripts
- No runtime resolver code
- No context loader implementation
- No approval gateway
- No release pipeline tooling

These may all be necessary at some point. But they will be built only when WBS production experience demonstrates a concrete need for them — not because the architecture document says they should exist.

### Definition of Future Work

Future LisaOS work is justified by one of:

- A pattern has appeared three times in WBS work (the Rule of Three).
- A production incident cost measurable time or money.
- A release retrospective identified a specific process gap.
- An engineer (human or AI) explicitly requests a capability with concrete use cases.

When that happens, the work is scoped, designed, and implemented — in that order, and only to the extent justified by the specific need.

---

## 8. Definition of Done

The LisaOS Foundation v3 is considered done when:

| Criteria | Status |
|----------|--------|
| Architecture defined and documented | ✅ |
| Core decisions captured in ADRs | ✅ |
| Registries defined and populated | ✅ |
| Governance rules documented | ✅ |
| Runtime model specified | ✅ |
| Agent framework defined | ✅ |
| Communication model specified | ✅ |
| Context management documented | ✅ |
| Engineering principles codified | ✅ |
| Future development policy stated | ✅ |
| Milestone formally marked | ✅ |

**Closed.** The Foundation is complete. What comes next is production.

---

## Related Documents

- `docs/LISAOS/MANIFEST.md` — LisaOS purpose and scope
- `docs/LISAOS/ECOSYSTEM.md` — BAR Technologies ecosystem
- `docs/LISAOS/KERNEL.md` — Kernel architecture
- `docs/LISAOS/KERNEL_DECISIONS.md` — Architecture decision records
- `docs/LISAOS/L005_L007_DESIGN_REVIEW.md` — Design study review
- `governance/GOVERNANCE.md` — Governance rules
- `docs/LISAOS/REPOSITORY_BOUNDARIES.md` — Repository boundary rules
