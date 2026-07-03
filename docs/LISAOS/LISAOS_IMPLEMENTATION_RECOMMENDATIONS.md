# LisaOS Implementation Recommendations

**Job ID:** L005-L007-LISAOS-ORCHESTRATION-DESIGN-STUDY  
**Repository:** `~/Lisa`  
**Scope:** Implementation order, complexity estimates, engineering guidance for bringing the orchestration architecture to life.  
**Runtime behaviour:** Unchanged. Documentation only.

---

## 1. Purpose

This document provides recommendations for implementing the designs described in L005, L006, L007, and the supporting documents. It is an engineering roadmap — not a commitment to ship dates or specific implementation details.

---

## 2. Recommended Implementation Order

### Phase 0: Foundation (L001-L004 already complete)

Existing foundation:

- `registry/agents.yml` — Agent definitions, runtime profiles, fallback chains
- `registry/capabilities.yml` — Capability definitions
- `registry/runtimes.yml` — Runtime registrations
- `registry/jobs.yml` — Job type definitions
- `runtime/` — Runtime provider documentation
- `jobs/schema.yml` — Job packet schema
- `lisaos/policies/routing.yml` — Job type routing rules

**Verification:** Before Phase 1, validate that all registry files are internally consistent and cross-reference correctly.

### Phase 1: Artifact Infrastructure

| # | Component | Description | Dependencies |
|---|-----------|-------------|--------------|
| 1.1 | Artifact directory structure | Create `jobs/active/`, `jobs/completed/`, `jobs/audit/`, `jobs/release/` directories | None |
| 1.2 | Artifact schema YAML files | Create standalone schema files for each artifact type (Job Packet, Context Packet, Implementation Report, etc.) | 1.1 |
| 1.3 | Schema validation tool | CLI tool that validates an artifact file against its schema | 1.2 |
| 1.4 | Job lifecycle state machine | Define state transitions, implement as documented state checks | 1.2 |

**Complexity:** Medium  
**Risk:** Low  
**Estimated effort:** 1-2 sprints  
**Output:** Validated artifact schemas, directory structure, validation tooling

### Phase 2: Runtime Resolver

| # | Component | Description | Dependencies |
|---|-----------|-------------|--------------|
| 2.1 | Runtime resolver specification | Formal specification for resolver logic | Phase 1 |
| 2.2 | Health check interface | Define health check contract, implement probes for each runtime | 1.2 |
| 2.3 | Capability matching engine | Implement capability filtering logic | Phase 1, 2.2 |
| 2.4 | Scoring model | Implement scoring model per L005 section 5 | 2.3 |
| 2.5 | Fallback chain executor | Implement fallback traversal logic | 2.2, 2.4 |
| 2.6 | Decision packet generator | Produce structured resolution decision | 2.5 |
| 2.7 | Escalation report generator | Produce escalation for unresolved selections | 2.6 |

**Complexity:** High  
**Risk:** Medium — scoring model weights may need tuning  
**Estimated effort:** 2-3 sprints  
**Output:** Runtime resolver that can evaluate candidates, score them, and produce decision packets

### Phase 3: Context Loader

| # | Component | Description | Dependencies |
|---|-----------|-------------|--------------|
| 3.1 | Context source reader | Read configured context sources (job packet, repo, docs, etc.) | Phase 1 |
| 3.2 | Priority chain enforcer | Apply priority ordering per ADR-K002 | 3.1 |
| 3.3 | Selective inclusion engine | Extract relevant sections from large documents | 3.1 |
| 3.4 | Context budget tracker | Allocate, track, and enforce token budget | 3.2 |
| 3.5 | Deduplication | Detect and remove duplicate content across sources | 3.2 |
| 3.6 | Context packet generator | Produce context-packet.yml with assembly summary | 3.3, 3.4, 3.5 |

**Complexity:** High  
**Risk:** Medium — selective inclusion quality depends on section parsing  
**Estimated effort:** 2-3 sprints  
**Output:** Context Loader that produces fully assembled context packets

### Phase 4: Agent Dispatch

| # | Component | Description | Dependencies |
|---|-----------|-------------|--------------|
| 4.1 | Agent identity loader | Load agent identity from `agents/` directory | Phase 1 |
| 4.2 | Policy injection engine | Apply project-specific policy to templates | 4.1 |
| 4.3 | Capability envelope builder | Build allowed/prohibited list from registry + job | Phase 2 |
| 4.4 | Dispatch coordinator | Combine agent identity + context + capabilities into dispatch payload | 3.6, 4.3, Phase 2 |

**Complexity:** Medium  
**Risk:** Low  
**Estimated effort:** 1 sprint  
**Output:** Dispatch coordinator that produces clean invocation packets

### Phase 5: OpenClaw Integration

| # | Component | Description | Dependencies |
|---|-----------|-------------|--------------|
| 5.1 | Session manager | Create, track, and lifecycle OpenClaw sessions per job | Phase 4 |
| 5.2 | Execution monitor | Heartbeat tracking, timeout detection, partial output save | 5.1 |
| 5.3 | Artifact collector | Watch for artifact output, validate and publish | Phase 1, 5.2 |
| 5.4 | Validation pipeline orchestrator | Sequence validation stages per job type | 5.3 |
| 5.5 | Error recovery | Retry, fallback, escalation dispatch | 5.4 |

**Complexity:** Very High  
**Risk:** High — closest to executable behaviour  
**Estimated effort:** 3-4 sprints  
**Output:** Full job execution pipeline through OpenClaw

### Phase 6: Validation Pipeline

| # | Component | Description | Dependencies |
|---|-----------|-------------|--------------|
| 6.1 | Static review runner | Invoke reviewer agent with implementation report | Phase 5 |
| 6.2 | Test runner | Invoke QA agent for unit/integration tests | Phase 5 |
| 6.3 | Browser QA runner | Invoke OpenClaw browser automation | Phase 5 |
| 6.4 | Security review runner | Invoke security agent for code/configuration review | Phase 5 |
| 6.5 | Governance audit runner | Compile governance checks, produce audit report | 6.1-6.4 |

**Complexity:** Medium  
**Risk:** Medium — individual stages are independent but integration matters  
**Estimated effort:** 2-3 sprints  
**Output:** Complete validation pipeline

### Phase 7: Approval Gateway

| # | Component | Description | Dependencies |
|---|-----------|-------------|--------------|
| 7.1 | Approval packet presenter | Compile and present approval packets | Phase 6 |
| 7.2 | Approval/rejection handler | Process human response, update job status | 7.1 |
| 7.3 | Re-queue handler | Return rejected jobs to queue with notes | 7.2 |

**Complexity:** Low  
**Risk:** Low  
**Estimated effort:** 1 sprint  
**Output:** Human approval workflow

### Phase 8: Audit and Memory

| # | Component | Description | Dependencies |
|---|-----------|-------------|--------------|
| 8.1 | Audit logger | Capture job lifecycle data, produce audit records | Phase 7 |
| 8.2 | Job archiver | Move completed jobs to archive directory | 8.1 |
| 8.3 | Memory writer | Curate durable knowledge from completed jobs | 8.2 |
| 8.4 | Benchmark registry | Collect and store runtime performance data | 8.1 |

**Complexity:** Low  
**Risk:** Low  
**Estimated effort:** 1-2 sprints  
**Output:** Full audit trail, memory curation, benchmark data

### Phase 9: Release Pipeline

| # | Component | Description | Dependencies |
|---|-----------|-------------|--------------|
| 9.1 | Release collector | Gather jobs for release, verify readiness gates | Phase 7 |
| 9.2 | Release report generator | Produce release report with notes and verification | 9.1 |
| 9.3 | Consolidated validation | Run cross-job validation (regression, security) | 9.1 |
| 9.4 | Release approval | Present release for human approval | 9.2, 9.3 |

**Complexity:** Medium  
**Risk:** Low — mostly aggregation of existing phases  
**Estimated effort:** 1-2 sprints  
**Output:** Release orchestration

---

## 3. Complexity Estimates

| Phase | Components | Complexity | Risk | Effort | Dependencies |
|-------|-----------|------------|------|--------|--------------|
| 1 | Artifact Infrastructure | Medium | Low | 1-2 sprints | None |
| 2 | Runtime Resolver | High | Medium | 2-3 sprints | Phase 1 |
| 3 | Context Loader | High | Medium | 2-3 sprints | Phase 1 |
| 4 | Agent Dispatch | Medium | Low | 1 sprint | Phase 2, 3 |
| 5 | OpenClaw Integration | Very High | High | 3-4 sprints | Phase 4 |
| 6 | Validation Pipeline | Medium | Medium | 2-3 sprints | Phase 5 |
| 7 | Approval Gateway | Low | Low | 1 sprint | Phase 6 |
| 8 | Audit & Memory | Low | Low | 1-2 sprints | Phase 7 |
| 9 | Release Pipeline | Medium | Low | 1-2 sprints | Phase 7 |

**Total estimated effort:** 15-21 sprints (2-3 months full-time, longer part-time)

---

## 4. Key Engineering Decisions

### 4.1 Language: Shell + YAML + Python

**Recommendation:** Use shell scripts for orchestration (file management, invocations), YAML for configuration and data, and Python for complex logic (scoring, parsing, validation).

**Rationale:** The system is file-based; shell scripts are the natural interface. YAML is already the data format. Python provides structured parsing and computation where needed.

**Avoid:** Full application framework (Rails, Django, Express) — over-engineering for a file-based system.

### 4.2 Validation: YAML Schema Files

**Recommendation:** Use standalone YAML schema files (e.g., `schemas/job-packet.schema.yml`) with a lightweight validator.

**Rationale:** Documenting schemas in separate files keeps artefacts clean and validates without code changes.

### 4.3 State: File-Based (Continue Current Model)

**Recommendation:** Continue with file-based job state. Do not introduce a database or message broker until job volume exceeds what files can handle.

**Rationale:** The current single-operator scale does not justify the infrastructure overhead of distributed queues or databases.

### 4.4 OpenClaw Integration: Invocation Wrapper

**Recommendation:** Create a thin wrapper that takes a dispatch packet (agent, runtime, context, capabilities) and invokes OpenClaw with the correct arguments.

**Rationale:** OpenClaw's interface is powerful but LisaOS needs a consistent invocation pattern. The wrapper is the interface boundary.

### 4.5 Testing: Job Execution in Scratch Mode

**Recommendation:** Before running real engineering jobs, test the pipeline with a "scratch mode" that validates all steps without executing underlying tools.

**Rationale:** The pipeline has many moving parts. Scratch mode verifies routing, validation, and approval without risking real code changes.

---

## 5. Risk Mitigation

| Risk | Phase | Mitigation |
|------|-------|------------|
| Runtime resolver scoring model is wrong | 2 | Make weights configurable. Use default weights initially, calibrate with real benchmark data. |
| Context Loader produces bloated context | 3 | Start with generous budgets and ratchet down. Let real usage data guide tightening. |
| OpenClaw integration reveals missing features | 5 | Design thin wrapper that abstracts OpenClaw interface. If OpenClaw can't support a feature, the wrapper can simulate it. |
| Validation pipeline becomes sequential bottleneck | 6 | Stages that are independent (static review + security review) can run in parallel if needed. |
| File-based job queue creates concurrency issues | 5, 6 | Single-operator scale prevents this. If concurrency arises, switch to atomic file operations or a simple lock file. |
| Agent performance varies dramatically | 2 | Benchmark registry captures this. Adjust scoring weights to reflect real-world performance. |
| Context budget too restrictive | 3 | Default budgets are guidance; job packets can override. Monitor and adjust defaults quarterly. |

---

## 6. Pre-Implementation Checklist

Before any implementation begins:

- [ ] Registry files (`registry/agents.yml`, `runtimes.yml`, `capabilities.yml`, `jobs.yml`) are validated and consistent
- [ ] All referenced agent directories exist under `agents/`
- [ ] All referenced runtime profiles are defined in `registry/runtimes.yml`
- [ ] Agent fallback chains are consistent (no dead-end fallbacks)
- [ ] Capability references match capabilities.yml definitions
- [ ] Job type required capabilities match agent capabilities
- [ ] Repository boundary rules are documented
- [ ] Artifact schemas are defined and validated against expected agent outputs

---

## 7. Future Direction — Production First

**The Foundation is complete. There is no L008._

LisaOS capabilities should now emerge from real production experience, not speculative architecture. The first production proving ground is WBS.

### What This Means

The implementation phases described in sections 2-6 are architectural guidance for what may eventually be needed. They are not a build plan. Each component should be implemented only when WBS production experience demonstrates a concrete, recurring need.

### When to Implement

| Phase | Trigger | Current Status |
|-------|---------|---------------|
| Artifact Infrastructure | When an artifact format error costs time in WBS | Wait |
| Runtime Resolver | When runtime selection becomes a recurring pain point | Wait |
| Context Loader | When context budgets are regularly exceeded | Wait |
| Agent Dispatch | When manual dispatch becomes a bottleneck | Wait |
| OpenClaw Integration | When session management becomes unwieldy | Wait |
| Validation Pipeline | When review/QA stages lack structure | Wait |
| Approval Gateway | When release needs structured approval routing | Wait |
| Audit & Memory | When audit trail gaps cause problems | Wait |
| Release Pipeline | When releases need coordinated orchestration | Wait |

**The Rule of Three:** A pattern must appear three times in real WBS work before it justifies a LisaOS abstraction.

### Core Engineering Principle

> LisaOS evolves from production experience, not speculative architecture.

- Real engineering reveals better abstractions than any design document.
- Production uncovers missing capabilities with concrete evidence.
- Avoiding unnecessary framework complexity means waiting until the need is proven.
- WBS is LisaOS' first proving ground — every Foundation design will be validated or invalidated by real use.

---

## Related Documents

- `docs/LISAOS/L005_RUNTIME_ROUTING_ARCHITECTURE.md` — Runtime resolver design
- `docs/LISAOS/L006_AGENT_COMMUNICATION_ARCHITECTURE.md` — Artifact-driven communication
- `docs/LISAOS/L007_OPENCLAW_ORCHESTRATION_ARCHITECTURE.md` — OpenClaw orchestration
- `docs/LISAOS/L005_L007_DESIGN_REVIEW.md` — Design review and architecture assessment
- `docs/LISAOS/KERNEL.md` — Kernel architecture
- `docs/LISAOS/KERNEL_DECISIONS.md` — ADR-K001 through ADR-K011
