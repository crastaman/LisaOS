# L005-L007 Design Review

**Job ID:** L005-L007-LISAOS-ORCHESTRATION-DESIGN-STUDY  
**Repository:** `~/Lisa`  
**Scope:** Executive summary, architecture assessment, open questions, implementation risks, and recommendations.

---

## 1. Executive Summary

This design study completes the architecture and design phase for LisaOS L005 (Runtime Routing Architecture), L006 (Agent Communication Architecture), and L007 (OpenClaw Orchestration Architecture). Nine supporting documents were produced, totalling approximately 150KB of architectural specification.

### Major Deliverables

| Document | Size | Focus |
|----------|------|-------|
| `L005_RUNTIME_ROUTING_ARCHITECTURE.md` | ~27KB | Runtime resolver design, scoring model, provider strategies |
| `L006_AGENT_COMMUNICATION_ARCHITECTURE.md` | ~30KB | Artifact-driven communication, 8 artifact schemas, handoff rules |
| `L007_OPENCLAW_ORCHESTRATION_ARCHITECTURE.md` | ~25KB | Session lifecycle, context loading, execution, error recovery |
| `LISAOS_CONTEXT_MANAGEMENT.md` | ~16KB | Context budgets, compaction, session rotation, memory hierarchy |
| `LISAOS_RUNTIME_SELECTION_POLICY.md` | ~11KB | Selection rules, edge cases, enforcement, governance checks |
| `LISAOS_ARTIFACT_LIFECYCLE.md` | ~12KB | Lifecycle states, storage layout, retention policies |
| `LISAOS_TOKEN_EFFICIENCY_GUIDE.md` | ~13KB | Token economics, 8 core practices, anti-patterns |
| `LISAOS_IMPLEMENTATION_RECOMMENDATIONS.md` | ~14KB | Implementation phases, complexity, risk, order |
| `L005_L007_DESIGN_REVIEW.md` | This document | Assessment, open questions, recommendations |

### Key Architectural Decisions

1. **Artifact-first communication** is the single most impactful decision in this study. All handoffs, decisions, and outputs are versioned, validated artifacts — not chat history. This eliminates the single worst source of token bloat and non-determinism.

2. **Capability-first runtime selection** ensures provider neutrality. The scoring model weights capability match at 50%, cost at 20%, latency and reliability at 15% each. No runtime has special status.

3. **Fresh sessions per job** eliminate context bleed and token accumulation. Every job, validation stage, and governance audit runs in its own session.

4. **Explicit context budgets** (16K-128K tokens depending on job type) with priority-chain enforcement prevent context overflow and enforce documentation-first truth.

5. **Production-driven evolution** — The Foundation is design-complete. Future LisaOS capabilities emerge from real WBS engineering experience, not speculative architecture.

---

## 2. Architecture Assessment

### 2.1 Strengths

1. **Strong separation of concerns.** Kernel (what to do), Orchestration (how to execute), Runtime (where to execute). Each layer has a clear responsibility.

2. **Provider-neutral design.** The scoring model and capability-first resolution ensure no single-runtime dependency. The existing registry architecture supports this without modification.

3. **Deterministic and auditable.** Artifact-first, immutable artifacts, and structured decision logs create a complete, searchable audit trail for every job.

4. **Graceful degradation.** Fallback chains at profile level (runtime) and agent level (runtime profile) ensure the system continues even when primary runtimes fail.

5. **Scalable to BAR Technologies scale.** The model supports multiple builders, concurrent jobs, distributed workers (without needing them now), and cloud execution. No architecture change needed for scale; only infrastructure.

### 2.2 Weaknesses

1. **File-based job queue has no built-in concurrency control.** For a single operator, this is fine. For concurrent multi-agent execution, file locking must be added or a distributed queue adopted.

2. **Context budgets are estimates.** The token budgets per job type (16K-128K) are educated guesses. Real usage data may require adjustment.

3. **Scoring model weights are untuned.** The current weights (capability=0.50, cost=0.20, latency=0.15, reliability=0.15) are logical but not calibrated against actual runtime performance.

4. **Health check infrastructure is assumed but not implemented.** Each runtime must expose a health endpoint. For CLI-based runtimes (Codex, Claude Code), this needs to be a thin wrapper or CLI probe.

5. **The system is documentation-heavy.** The artifact schemas, lifecycle rules, and handoff protocols add documentation surface area. This is intentional, but it requires discipline to maintain.

### 2.3 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Runtime provider deprecation | Medium | High | Provider-neutral design absorbs this. ADR-K007 ensures no runtime-specific logic in agents. |
| Context Loader becomes too slow | Medium | Medium | Selective inclusion means loading only relevant sections, not full documents. Performance should be acceptable. |
| Artifact schemas drift from agent outputs | Medium | Medium | Validation gates at write time catch drift. Scheduled schema compliance audits. |
| Single-operator scale exceeded | Low | Medium | File-based queue handles current scale. Migration to distributed queue is localised (Queue interface). |

---

## 3. Improvements Over L001-L004

| Area | L001-L004 State | L005-L007 Design |
|------|----------------|-----------------|
| Runtime selection | Hardcoded in routing rules (per-job-type) | Dynamic scoring model with health checks and fallback chains |
| Agent communication | Implicit (agents share chat context) | Explicit (artifact-first, schematised handoffs) |
| Context management | Informal priority list in KERNEL | Formal budgets, compaction, selective inclusion, summarisation |
| Token efficiency | Not documented | Comprehensive guide with 8 practices and token economics |
| Error recovery | Basic retry policy | Classification by failure type, retry tables, escalation reports |
| Provider integration | ADR-0001 engine abstraction | Per-provider strategy, 6-step integration process |

---

## 4. Open Questions

1. **Scoring model calibration:** How do we verify the scoring weights produce optimal runtime selection? Proposal: Run 50 benchmark jobs through each runtime, measure actual cost, latency, and quality; adjust weights accordingly.

2. **Context budget validation:** Are the per-job-type budgets appropriate? Proposal: Start with generous budgets, monitor actual consumption for 30 days, then ratchet down.

3. **Health check implementation for CLI runtimes:** How does Codex or Claude Code expose a health status endpoint? Proposal: CLI probes (`codex --version`, `claude --version` combined with connectivity check) with a 5-second timeout.

4. **Artifact schema evolution:** How do we manage schema changes without breaking backward compatibility? Proposal: Major version increments require an ADR. Schema validation tools alert when an artifact's version is incompatible.

5. **Concurrent job execution:** For how many concurrent jobs is the file-based queue viable? Proposal: Benchmarks at 1, 3, 5, and 10 concurrent jobs to identify the breaking point.

6. **Memory curation automation:** How automated should memory curation be? Proposal: Start manually-driven (weekly human review), add semi-automated curation (agent proposes, human approves) after 3 months.

7. **OpenClaw task vs. skill vs. job delineation:** When should work be an OpenClaw task vs. a LisaOS job? Proposal: OpenClaw tasks for operational/scheduled work; LisaOS jobs for intentional, planned engineering work.

---

## 5. Implementation Risks

| Risk | Phase | Severity | Mitigation |
|------|-------|----------|------------|
| OpenClaw integration reveals API limitations | 5 | High | Design the dispatch wrapper as a thin abstraction. If OpenClaw lacks a feature, simulate in wrapper. |
| Scoring model produces bad initial selections | 2 | Medium | Start with conservative weights. Monitor selection decisions for first 50 jobs; adjust before Phase 5. |
| Artifact validation becomes a bottleneck | 1 | Low | Validation is fast (schema check is <100ms). No performance concern. |
| Registry files drift from code | All | Low | Validation scripts catch inconsistencies. Include in CI if CI is adopted. |
| Agent behaviour varies between runtimes | 5 | Medium | Capability-based routing ensures runtimes that can't handle the job aren't selected. |

---

## 6. Recommendations

### 6.1 Immediate — Production Application

The Foundation is complete. There is no L008._

**Use WBS as the first production proving ground for LisaOS.**

1. Apply JOB-PACKET pattern to real WBS engineering jobs.
2. Write artifacts (implementation reports, decision logs) during WBS execution.
3. Use artifact-first handoffs when agent handoffs are needed.
4. Apply context compaction and session rotation strategies during WBS development.
5. When a capability gap is discovered during real work, document it with concrete evidence.

### 6.2 Short-term (Phases 1-3)

1. **Implement artifact infrastructure** (Phase 1) — directories, schemas, validation.
2. **Implement Runtime Resolver** (Phase 2) — scoring model, health checks, fallback chains.
3. **Implement Context Loader** (Phase 3) — selective inclusion, priority chain, budgets.

### 6.3 Medium-term (Phases 4-6)

1. **Implement Agent Dispatch** (Phase 4) — identity loading, policy injection, capability envelopes.
2. **Implement OpenClaw Integration** (Phase 5) — session management, execution monitoring.
3. **Implement Validation Pipeline** (Phase 6) — sequential stages, per-job-type skip logic.

### 6.4 Long-term (Phases 7-9)

1. **Approval Gateway** — structured approval presentation, human response handling.
2. **Audit and Memory** — audit logger, job archiver, memory curation.
3. **Release Pipeline** — release orchestration, consolidated validation.

### 6.5 Future Direction

**The Foundation is design-complete. Future LisaOS capabilities should emerge from real WBS production experience, not speculative architecture.**

What this means in practice:

- Build artifact validation tools only when WBS work shows a concrete need (e.g., an artifact error cost time).
- Implement the runtime resolver only when runtime selection becomes a recurring pain point in WBS.
- Create the context loader only when context budgets are regularly exceeded in real WBS sessions.
- Develop the approval gateway only when WBS release process needs structured approval routing.

**When to build a LisaOS capability:**

1. A pattern has appeared three times in WBS work (Rule of Three).
2. A production incident cost measurable time or money.
3. A release retrospective identified a specific process gap.
4. An engineer explicitly requests it with concrete use cases.

**Core principle:** LisaOS evolves from production experience, not speculative architecture.

---

## 7. The BAR Technologies Scale Test

Every recommendation in this study was evaluated against the question:

**"Will this still make sense when BAR Technologies is ten times larger?"**

| Design | Ten-X Verdict |
|--------|--------------|
| **Artifact-first communication** | ✅ Still valid. Artifacts scale better than chat history at any size. |
| **Capability-first routing** | ✅ More important at scale — provider lock-in becomes expensive. |
| **Fresh sessions per job** | ✅ Even more important at scale — context isolation prevents cross-contamination. |
| **Context budgets** | ✅ Critical at scale — without budgets, costs grow linearly with usage. |
| **File-based job queue** | ⚠️ Will need replacement at 10x. Acceptable now; distributed queue (Redis, NATS) is a localised swap. |
| **Documentation-heavy design** | ✅ Essential at scale — institutional knowledge must be durable. |
| **Scoring model** | ✅ More valuable at scale — optimising runtime costs on 10x volume saves real money. |
| **Health checks** | ✅ Required at scale — reliability demands knowing which runtimes are healthy. |
| **Approval gateway** | ✅ More nuanced at scale — may need tiered approval (team lead → Roshan for production). |

**Conclusion:** The architecture is designed for scale. The only component that needs replacement at 10x is the job queue, and that is a localised swap behind a defined interface.

---

## Related Documents

- `docs/LISAOS/L005_RUNTIME_ROUTING_ARCHITECTURE.md`
- `docs/LISAOS/L006_AGENT_COMMUNICATION_ARCHITECTURE.md`
- `docs/LISAOS/L007_OPENCLAW_ORCHESTRATION_ARCHITECTURE.md`
- `docs/LISAOS/LISAOS_CONTEXT_MANAGEMENT.md`
- `docs/LISAOS/LISAOS_RUNTIME_SELECTION_POLICY.md`
- `docs/LISAOS/LISAOS_ARTIFACT_LIFECYCLE.md`
- `docs/LISAOS/LISAOS_TOKEN_EFFICIENCY_GUIDE.md`
- `docs/LISAOS/LISAOS_IMPLEMENTATION_RECOMMENDATIONS.md`
- `docs/LISAOS/KERNEL.md`
- `docs/LISAOS/KERNEL_DECISIONS.md`
