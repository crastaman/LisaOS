# LisaOS v3 — Manifest

**Version:** 3.0  
**Status:** Active  
**Last updated:** 2026-07-02

> LisaOS is not WBS. LisaOS is the operating system for coordinating agents, runtimes, governance, workflow, memory, and execution. WBS is a product repository governed by LisaOS workflows.

---

## 1. Architecture

```text
Lisa Workflow (governance)
    │
LisaOS Kernel (execution model)
    │
OpenClaw (orchestration engine)
    │
Agents + Runtimes + Capabilities
```

---

## 2. Repository Ownership

LisaOS and WBS are separate projects with separate repositories.

| Repository | Purpose | Owns |
|-----------|---------|------|
| `~/Lisa` | LisaOS operating system | LisaOS architecture, Kernel, registries, governance, workflow engine, memory system, OpenClaw integration, security, future LisaOS source code |
| `~/Projects/WBS/healing-events-booking` | Wellness Business Suite product | Plugin code, WBS documentation, sprint packets, technical debt, QA reports, product architecture, business rules, release notes |

Repository boundary rules are defined in:

- `docs/LISAOS/REPOSITORY_BOUNDARIES.md`

**Governance rule:** before every documentation or implementation task, agents must identify the target repository, verify the current Git root, and confirm the destination path. If the requested path belongs to another repository, stop and request clarification.

---

## 3. Core Principles

### Model Independence

No critical workflow depends on a single AI provider. Every provider can be replaced.

### Workflow Over Models

Business intelligence resides in architecture, ADRs, governance, documentation, and process — not in AI models.

### Repository Boundary Discipline

LisaOS documentation belongs in `~/Lisa`. WBS documentation belongs in `~/Projects/WBS/healing-events-booking`. Agents must never silently create files in the wrong repository.

### Specialist Intelligence

Each task is assigned to the most appropriate agent and runtime.

### Dynamic Routing

Runtime selection is based on capability, availability, cost, context window, and historical performance.

### Independent Verification

Implementation and verification remain separate responsibilities.

### Human Governance

Roshan retains responsibility for vision, ethics, product direction, commercial decisions, and final approval.

### Documentation is Truth

Documentation defines reality. AI reads documentation. AI never becomes the source of truth.

### Capability-Based Security

Agents have explicit allowed and prohibited capabilities. Globally prohibited operations are never delegated.

---

## 4. Key Files

| File | Purpose |
|------|---------|
| `docs/LISAOS/MANIFEST.md` | This file — LisaOS v3 architecture and repository ownership overview |
| `docs/LISAOS/REPOSITORY_BOUNDARIES.md` | Permanent governance policy for LisaOS/WBS repository boundaries |
| `docs/LISAOS/KERNEL.md` | LisaOS Kernel — execution model governing job lifecycle |
| `docs/LISAOS/KERNEL_DECISIONS.md` | Architectural decisions made during Kernel design |
| `docs/LISAOS/KERNEL_REVIEW.md` | Critical architecture review of the Kernel documentation |
| `docs/ADR/` | LisaOS architecture decision records |
| `docs/ARCHITECTURE/` | LisaOS architecture documents |
| `governance/` | LisaOS governance and security rules |
| `core/` | LisaOS core source code |
| `engines/` | Runtime engine integrations |
| `jobs/` | LisaOS job definitions and job artifacts |
| `capabilities/` | LisaOS capability descriptions |

---

## 5. Repository Boundary Validation

Every future job that writes files must report:

```text
Repository boundary check:
- Target repository: <repo>
- Git root: <verified-root>
- Destination path: <path>
- Boundary result: PASS
```

If the boundary result is not `PASS`, the job must stop before writing files.

---

## 6. Related

- `docs/LISAOS/REPOSITORY_BOUNDARIES.md`
- `docs/LISAOS/KERNEL.md`
- `docs/LISAOS/KERNEL_DECISIONS.md`
- `docs/LISAOS/KERNEL_REVIEW.md`
- `governance/GOVERNANCE.md`
- `governance/SECURITY.md`
