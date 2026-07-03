# BAR Technologies Ecosystem Architecture

**Canonical repository:** `~/Lisa`  
**Document role:** Highest-level architecture entry point for BAR Technologies, LisaOS, and applications built on LisaOS.

## 1. BAR Technologies

BAR Technologies is the umbrella technology organisation for the BAR platform ecosystem.

**Mission:** Build intelligent platforms and AI operating systems for wellness, transformational, and future business ecosystems.

BAR Technologies exists to create reusable technology foundations that can power multiple commercial products without forcing every product team to reinvent architecture, orchestration, governance, automation, or AI operating patterns.

The organisation owns the platform vision. LisaOS owns the operating system. Applications own their business implementations.

## 2. Platform Hierarchy

```text
BAR Technologies
    ↓
LisaOS
    ↓
Applications
    ├── Wellness Business Suite (WBS)
    ├── BAR — flagship implementation
    ├── Realign
    ├── Energetic Art
    └── Future products
```

### Hierarchy meaning

- **BAR Technologies** defines the organisation, mission, commercial ecosystem, and platform direction.
- **LisaOS** provides the reusable AI operating system and engineering platform.
- **Applications** consume LisaOS capabilities and implement specific business domains.

## 3. LisaOS

LisaOS is the AI operating system for the BAR Technologies ecosystem.

It is simultaneously:

- an AI operating system
- a governance platform
- an orchestration layer
- a reusable engineering platform

LisaOS exists so that each product can inherit mature engineering, governance, automation, memory, security, and workflow patterns without duplicating platform architecture inside application repositories.

LisaOS owns:

- Kernel
- Agent Library
- System Agents
- Template Library
- Capability Registry
- Runtime Registry
- Governance
- Security
- Memory
- Workflow Engine

LisaOS is product-aware but not product-specific. It defines reusable operating principles, templates, and capabilities. Product-specific behaviour is added through policy injection.

## 4. Applications

Applications are products built on LisaOS.

Current and planned applications include:

- Wellness Business Suite (WBS)
- BAR — flagship implementation
- Realign
- Energetic Art
- Future products

Applications inherit platform capabilities through **Policy Injection**.

Applications own:

- business rules
- product workflows
- customer experience
- specialised agents
- implementation
- product data models
- project-specific QA and release evidence

Applications do **not** own platform architecture. They may reference LisaOS, instantiate LisaOS templates, and inject project policies, but they should not become duplicate sources of truth for LisaOS architecture.

## 5. Repository Ownership

Canonical Lisa repository:

```text
~/Lisa
```

Canonical WBS repository:

```text
~/Projects/WBS/healing-events-booking
```

Repository ownership rules:

- LisaOS documentation belongs only in the Lisa repository.
- WBS documentation belongs only in the WBS repository.
- Application repositories should not contain canonical LisaOS architecture.
- Cross-repository references should use pointers rather than duplicate architecture.
- Migration may temporarily create overlap, but the final state must preserve a single source of truth.

### Ownership boundary

| Repository | Owns | Does not own |
|---|---|---|
| `~/Lisa` | LisaOS architecture, governance, templates, capabilities, runtime concepts, workflow engine | WBS product code or WBS business implementation |
| `~/Projects/WBS/healing-events-booking` | WBS product code, product docs, implementation history, QA evidence, business rules | Canonical LisaOS architecture |

## 6. Reusable Asset Flow

Reusable knowledge flows through the ecosystem as follows:

```text
Knowledge
    ↓
LisaOS Template
    ↓
Project Policy Injection
    ↓
Project Agent
    ↓
Execution
    ↓
Feedback
    ↓
Template Improvement
```

### Flow explanation

1. **Knowledge** begins as experience from product work, architecture review, QA, incident response, implementation, or research.
2. **LisaOS Template** captures the reusable part in a product-neutral form.
3. **Project Policy Injection** adapts the template to a specific repository, coding standard, approval model, business convention, and runtime preference.
4. **Project Agent** is the project-specific instantiation used by an application.
5. **Execution** produces real implementation, review, QA, planning, or operational work.
6. **Feedback** identifies what should improve in either the project policy or reusable template.
7. **Template Improvement** feeds generic lessons back into LisaOS while project-specific knowledge remains in the project.

Reusable knowledge flows back into LisaOS. Product-specific knowledge remains inside the product repository.

## 7. Platform Principles

### Production-Driven Evolution

LisaOS evolves from production experience, not speculative architecture. The Foundation is design-complete. Future capabilities emerge from real engineering needs discovered during WBS development — never from hypothetical requirements. The Rule of Three applies: a pattern must appear three times before it justifies an abstraction.

### Artifact-First Communication

Inter-agent communication must use structured, versioned, immutable artifacts. Chat history is never used as a durable communication channel. Artifacts are the durable engineering memory. Sessions are temporary working memory.

### Runtime Philosophy

LisaOS does not choose models. LisaOS chooses capabilities. The Runtime Resolver maps capability requirements to available providers. Maintain provider neutrality. Avoid vendor lock-in.

### Evolution over replacement

LisaOS evolves from real product work. It should generalise proven patterns rather than replace product systems prematurely.

### Repository boundaries

Every job must verify repository, working directory, target path, branch, and output scope before writing files. Cross-repository writes are not allowed without explicit scope.

### Single source of truth

Canonical LisaOS architecture lives in `~/Lisa`. Application repositories may keep pointers, migration notes, or historical references, not duplicate canonical architecture.

### Model-agnostic architecture

LisaOS should not depend on one AI model or provider. Runtimes, routing, delegation, and benchmarks should support multiple models and providers.

### Agent responsibilities

Agents must have clear ownership, scope, permissions, and expected outputs. System agents belong to LisaOS. Project agents belong to applications.

### Capability-based security

Tools, agents, and runtimes should be governed by capabilities. Access should be explicit, scoped, auditable, and revocable.

### Human governance

Humans retain final authority over architecture, security, approvals, repository boundaries, and production-impacting changes.

### Reusable templates

Templates must remain generic. Projects customise templates through policy injection rather than editing the canonical template into a product-specific shape.

### Enterprise scalability

LisaOS should support multiple applications, teams, agents, models, environments, and governance levels without losing clarity or control.

### Long-term maintainability

The ecosystem should favour clear ownership, durable documentation, controlled evolution, and reversible migration steps.

## 8. Future Vision

BAR Technologies becomes a platform company.

LisaOS powers multiple commercial applications while keeping those applications independent. WBS, BAR, Realign, Energetic Art, and future products share the same operating system without sharing product-specific code, business rules, or customer experience assumptions.

The long-term goal is an ecosystem where:

- LisaOS provides the operating system.
- Applications provide specialised commercial experiences.
- Reusable knowledge improves the platform.
- Project-specific knowledge stays with the project.
- Human governance remains explicit.
- AI agents operate inside clear repository, capability, and policy boundaries.

In that future, BAR Technologies is not just a collection of products. It is a platform organisation with a reusable AI operating system at its centre.
