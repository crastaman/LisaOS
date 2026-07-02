# L007 — OpenClaw Orchestration Architecture

**Job ID:** L005-L007-LISAOS-ORCHESTRATION-DESIGN-STUDY  
**Repository:** `~/Lisa`  
**Scope:** OpenClaw as the LisaOS execution engine — context loading, agent selection, runtime routing, execution, validation, error recovery.  
**Runtime behaviour:** Unchanged. Documentation only.

---

## 1. Purpose

L007 defines how OpenClaw becomes the LisaOS execution engine. This document describes the orchestration layer that sits between the LisaOS Kernel (what to do) and OpenClaw (how to execute).

**Core model:** The Kernel defines the job lifecycle. OpenClaw provides the execution primitives. This document describes how they connect.

---

## 2. Architecture Model

### 2.1 Layered Responsibilities

```
  ┌──────────────────────────────────────────────────────┐
  │                 LISA WORKFLOW                        │
  │  Governance, policy, approval authority              │
  ├──────────────────────────────────────────────────────┤
  │                 LISAOS KERNEL                        │
  │  Job lifecycle, context, capabilities, resolution    │
  ├──────────────────────────────────────────────────────┤
  │           OPENCLAW ORCHESTRATION                     │
  │  Session management, context loading, dispatch,      │
  │  execution monitoring, error recovery                │
  ├──────────────────────────────────────────────────────┤
  │           OPENCLAW RUNTIME                           │
  │  Agent invocation, tool execution, artifact writing  │
  └──────────────────────────────────────────────────────┘
```

### 2.2 Key Distinctions

| Layer | Role | Owns |
|-------|------|------|
| **Kernel** | What to execute | Job lifecycle, capability policy, runtime selection rules |
| **Orchestration** | How to execute | Context loading, agent dispatch, execution monitoring, session lifecycle |
| **Runtime** | Where to execute | Agent invocation, tool use, model interaction |

The Orchestration layer is the **integration boundary** between the Kernel's declarative model and OpenClaw's imperative execution.

---

## 3. Session Lifecycle

### 3.1 Session Types

| Session Type | Purpose | Duration | Context Budget |
|-------------|---------|----------|---------------|
| **Job session** | Execute a single job | Job duration | Full context budget for the job |
| **Review session** | Run validation pipeline | Per-stage duration | Reduced (primarily reads reports) |
| **Governance session** | Run governance audit | Short (sub-minute) | Minimal (reads summary artifacts) |
| **Approval session** | Present to human | Human-paced | Approval packet only |
| **Memory session** | Curate durable memory | Short (1-5 min) | Decision logs + completed artifacts |

### 3.2 Session Lifecycle

```
CREATE ──► LOAD_CONTEXT ──► DISPATCH ──► EXECUTE ──► VALIDATE ──► COMPLETE
                                            │
                                            └──► RECOVER ──► DISPATCH (retry)
                                            └──► ESCALATE ──► FAIL
```

| Phase | Owner | Description |
|-------|-------|-------------|
| **CREATE** | Orchestrator | Create session with job ID, agent, runtime assignment |
| **LOAD_CONTEXT** | Context Loader | Assemble context packet from sources |
| **DISPATCH** | Orchestrator | Invoke OpenClaw agent with context and capability envelope |
| **EXECUTE** | OpenClaw Runtime | Agent performs work within capability constraints |
| **VALIDATE** | Validation Pipeline | Run per-job validation stages |
| **COMPLETE** | Orchestrator | Record results, produce artifacts, trigger next phase |
| **RECOVER** | Orchestrator | On failure: determine retry, fallback, or escalate |
| **ESCALATE** | Orchestrator | Present escalation to human |

### 3.3 Session Isolation

Each job session is fully isolated:

- **Context isolation:** The Context Packet for job A is not accessible to job B. Sessions do not share context.
- **Artifact isolation:** Each job writes to its own `jobs/active/<job_id>/` directory.
- **Capability isolation:** The capability envelope is fixed at dispatch time and enforced by OpenClaw.
- **Runtime isolation:** Each session executes on a single runtime. Runtime selection is per-job, not per-session.

---

## 4. Context Loading

### 4.1 Context Assembly Process

The Context Loader is the Kernel component responsible for producing the Context Packet. Within the Orchestration layer, this process is:

```
1. Receive job ID from queue
2. Read job packet from jobs/queue/<job_id>/job-packet.yml
3. Identify context sources from job packet's context_files
4. Apply priority chain (per ADR-K002):
   a. Current Job Packet
   b. Current Repository (HEAD)
   c. LisaOS Documentation (MANIFEST, KERNEL, relevant L docs)
   d. Business Rules (docs/BUSINESS_RULES/)
   e. Architecture Documents (ADRs, maps, data flows)
   f. Historical Reports (previous runs, QA reports)
   g. Conversation Context (temporary — truncated to max 4096 tokens)
5. Deduplicate overlapping content
6. Compile into single context text
7. Calculate token budget usage
8. Produce context-packet.yml
9. Store in jobs/active/<job_id>/context-packet.yml
```

### 4.2 Context Priority Chain (Detail)

| Source | Max Tokens | Priority | Notes |
|--------|-----------|----------|-------|
| Job Packet | Entire file | Highest | Always included in full |
| Repository files | Configurable via packet | High | Current HEAD, not branch tip |
| LisaOS docs | 8192 | High | Architecture-adjacent docs |
| Business rules | 4096 | Medium | Domain-specific constraints |
| Architecture docs | 4096 | Medium | ADRs, maps, flow diagrams |
| Historical reports | 4096 | Low | Only if relevant (same job area) |
| Conversation context | 4096 | Temporary | Tagged as non-authoritative |

### 4.3 Context Budget

The context budget is the maximum token allocation for a job's context. It prevents context overflow and ensures consistent behaviour across sessions.

**Default budgets by job type:**

| Job Type | Budget | Rationale |
|----------|--------|-----------|
| ENGINEERING | 64K tokens | Code context requires space |
| QA_BROWSER | 32K tokens | Mostly test definitions |
| GOVERNANCE | 16K tokens | Focused review |
| DOCS | 32K tokens | Document context + guidance |
| PLANNING | 128K tokens | Large context needed for analysis |
| RELEASE | 32K tokens | Job summaries + metadata |
| SECURITY | 48K tokens | Code + security context |
| RESEARCH | 64K tokens | Exploration needs broad context |

**Budget override:** Packets can specify a custom `context_budget` value.

**Budget enforcement:** The Context Loader enforces the budget. If sources exceed the budget, lower-priority sources are truncated or excluded, starting with conversation context.

### 4.4 Context Compaction

Context compaction reduces token consumption without losing essential information:

**Techniques:**

1. **Summarisation:** Replace full conversation history with a structured summary (max 1024 tokens).
2. **Deduplication:** Remove content that appears in multiple sources (same ADR referenced from two places).
3. **Selective inclusion:** Include only sections of documents relevant to the job (e.g., the relevant ADR sections, not the full document).
4. **Reference shortening:** Replace full file paths with relative paths and a single header comment.
5. **Outdated exclusion:** Exclude documentation superseded by newer versions (commit SHAs verify currency).

### 4.5 Context Persistence

- Context Packets persist in `jobs/active/<job_id>/context-packet.yml` for the job's duration.
- They are **not** stored in memory or chat history.
- Any agent reassigned to the job reads the same Context Packet from the artifact store.
- Context Packet is valid for the job's lifetime. If the job is readmitted (after fix), a new Context Packet is assembled.

---

## 5. Agent and Runtime Selection

### 5.1 Selection Flow (Orchestration View)

The Orchestration layer does not make selection decisions — it executes selection decisions made by the Kernel's Resolver components.

```
Orchestrator:
  1. Read job packet → get preferred_agent, job_type
  2. Read routing decision → get assigned agent, resolved runtime
  3. Verify agent exists in registry/agents.yml
  4. Verify runtime exists in registry/runtimes.yml
  5. Load agent identity from agents/system/<agent-id>/ or agents/templates/<template-id>/
  6. Apply policy injection (templates only)
  7. Verify repository boundary (cross-check with job packet)
  8. Dispatch to OpenClaw with {agent_id, runtime, context_pack, capability_envelope}
```

### 5.2 Agent Loading

Agents are loaded from their identity directory:

```
agents/system/planner/
  README.md          # Agent definition
  IDENTITY.md        # Agent identity (loaded as context)
  SOUL.md            # Agent personality/rules
  TOOLS.md           # Agent-specific tool notes

agents/templates/builder-template/
  README.md          # Template definition
  IDENTITY.md        # Template identity (loaded as context)
  SOUL.md            # Template personality/rules
  TOOLS.md           # Template-specific tool notes
```

### 5.3 Policy Injection (Templates Only)

Templates receive project-specific policy injection at dispatch time:

```
Runtime Profiles →    Implementation-runtime (Codex runtime capabilities)
Policy Injection →    {target_repo, allowed_paths, prohibited_paths, validation_rules}
Template Core →        builder-template (general implementation agent)
                      ↓
Final Agent Context →  Codex agent with project-scoped policy constraints
```

Policy injection adds the following to the context packet:

```yaml
policy_injection:
  target_repository: "~/Projects/WBS/healing-events-booking"
  repository_root: "/var/www/heb"
  allowed_paths:
    - "wp-content/plugins/healing-events-booking/"
  prohibited_paths:
    - "wp-config.php"
    - ".env"
  validation_requirements:
    - php_lint_required: true
    - unit_tests_required: true
    - visual_regression_required: false
  approval_rules:
    human_approval_required: true
    automatic_approval_allowed: false
  escalation_contact: "Roshan"
```

Policy injection is read-only metadata applied to the template's context. It does not modify the template's identity files.

---

## 6. Job Execution

### 6.1 Dispatch Contract

The Orchestrator dispatches to OpenClaw with a structured invocation packet:

```yaml
# OpenClaw Invocation Packet (internal — not stored as artifact)
dispatch:
  job_id: "S014-PRACTITIONER-BACKEND-V2"
  agent:
    id: "builder-template"
    identity_path: "agents/templates/builder-template/"
    type: template
  runtime:
    id: "codex-review"
    profile: "implementation-runtime"
    provider: "openai"
  context:
    packet_ref: "jobs/active/S014-PRACTITIONER-BACKEND-V2/context-packet.yml"
    budget_used: 48000
    budget_remaining: 16000
  capabilities:
    allowed:
      - git
      - terminal
      - filesystem
      - repository_read
      - repository_write
    prohibited:
      - deployment
      - runtime_management
      - security_review
  output:
    path: "jobs/active/S014-PRACTITIONER-BACKEND-V2/"
    expected_artifacts:
      - implementation-report.yml
      - decision-log.yml
  constraints:
    ttl_minutes: 30
    repository_boundary: "/var/www/heb"
    allow_destructive_operations: false
```

### 6.2 Execution Monitoring

The Execution Monitor tracks active jobs:

| Monitor | How | Escalation |
|---------|-----|------------|
| Heartbeat | Periodic check from runtime | Stalled >5 min → restart with fallback |
| Timeout | TTL from job packet | Exceeded → kill, save partial output, escalate |
| Artifact production | Watch output directory | No artifacts after 50% TTL → warn agent |
| Capability compliance | Audit tool use against envelope | Violation → kill immediately, escalate |

### 6.3 Artifact Collection

During execution, the Orchestrator collects artifacts as the agent produces them:

- Implementation artifacts → `jobs/active/<job_id>/`
- Additional output (patches, diffs, test outputs) → `jobs/active/<job_id>/output/`

On completion, artifacts are validated against the job packet's `output_expected` list.

---

## 7. Validation Pipeline

### 7.1 Pipeline Architecture

The Validation Pipeline is a sequence of stages run after execution completes. Each stage is an independent validation that produces a standardised result.

```
Execution Complete
      │
      ▼
┌─────────────┐
│ Static      │  ← lisa-reviewer or architecture-guardian-template
│ Review      │     Reviews implementation report + code changes
└──────┬──────┘
       │ PASS / PASS_WITH_WARNINGS
       ▼
┌─────────────┐
│ Tests       │  ← lisa-qa
│             │     Runs unit/integration tests
└──────┬──────┘
       │ PASS / PASS_WITH_WARNINGS
       ▼
┌─────────────┐
│ Browser QA  │  ← OpenClaw Browser (ui-audit-template)
│             │     Headless browser tests (if applicable)
└──────┬──────┘
       │ PASS / PASS_WITH_WARNINGS
       ▼
┌─────────────┐
│ Regression  │  ← lisa-qa
│             │     Compare against baseline
└──────┬──────┘
       │ PASS / PASS_WITH_WARNINGS
       ▼
┌─────────────┐
│ Security    │  ← lisa-security or security-review-template
│             │     Vulnerability scan, permission check
└──────┬──────┘
       │ PASS
       ▼
┌─────────────┐
│ Governance  │  ← lisa-reviewer or architecture-guardian-template
│             │     Scope, capability, artifact compliance
└──────┬──────┘
       │ PASS
       ▼
  Approval Gateway
```

### 7.2 Stage Execution Model

Each validation stage is executed in its own session with its own context:

1. Orchestrator creates a validation session
2. Loads the relevant artifact (implementation report, review report)
3. Assigns the appropriate reviewer agent
4. Sets reduced context budget (validation needs less context than execution)
5. Runs validation within agent's capability envelope (read-only for most stages)
6. Produces validation result (PASS / PASS_WITH_WARNINGS / FAIL)
7. Appends result to job record
8. If FAIL and CRITICAL: abort pipeline, escalate to human
9. If FAIL and non-critical: continue pipeline to gather full feedback, then escalate

### 7.3 Stage Skip Rules

| Stage | Skipped When |
|-------|--------------|
| Static Review | Job type is DOCS or MEMORY (trivial changes) |
| Tests | Job has no `validation_required` flag (research, planning) |
| Browser QA | Job type is not QA_BROWSER and has no browser capability requirement |
| Regression | No baseline exists for this job type or area |
| Security | Job type is DOCS or PLANNING (no code changes) |
| Governance | Never skipped (always verify) |

---

## 8. Error Recovery

### 8.1 Failure Classification

| Failure Type | Classification | Retry Behaviour |
|-------------|---------------|-----------------|
| Runtime unavailable | Transient | → Fallback runtime → immediate retry |
| Rate limited | Transient | → Wait (60s, 120s, 240s) → retry or fallback |
| Timeout | Transient | → Immediate retry with fallback runtime |
| Dependency missing | Configuration | → Escalate to human |
| Capability violation | Security | → Kill immediately → human escalation |
| Validation stage fail | Quality | → Escalate to human with results |
| Agent misbehaviour | Operational | → Kill → fallback agent → retry once |
| Repository boundary violation | Security | → Kill immediately → human escalation |

### 8.2 Retry Policy

```
1. Classify failure type (transient/permanent/security)
2. If transient:
   a. Check retry count ≤ max (see table below)
   b. Apply delay: immediate, short (30s), medium (60s), long (120s), extended (240s)
   c. Re-dispatch: same job ID, same packet, same context
      — do not reload context (use existing context packet)
   d. If retries exhausted: → fallback runtime
3. If permanent:
   a. Save partial output to jobs/active/<job_id>/output/
   b. Set status: FAILED
   c. Escalate to human with partial results
4. If security:
   a. Kill immediately — no retry
   b. Set status: FAILED_SECURITY
   c. Escalate to human with full audit log
```

| Failure Type | Max Retries | Delay Sequence | Fallback Behaviour |
|-------------|-------------|----------------|-------------------|
| Runtime unavailable | 3 | 30s, 60s, immediate | Switch to next healthy fallback |
| Rate limited | 3 | 60s, 120s, 240s | Switch fallback if >240s remains |
| Timeout | 2 | Immediate, immediate | Switch to fallback runtime |
| Agent misbehaviour | 1 | Immediate | Switch agent within same runtime |
| Validation | 0 | — | Escalate (decide: fix, override, reject) |
| Capability violation | 0 | — | Escalate immediately |
| Boundary violation | 0 | — | Escalate immediately |

### 8.3 Escalation Format

```
ORCHESTRATION ESCALATION
=====================
Job ID:     S014-PRACTITIONER-BACKEND-V2
Type:       ENGINEERING
Agent:      builder-template
Runtime:    codex-review
Phase:      EXECUTION

Failure:    RUNTIME_UNAVAILABLE
Detail:     codex-review health check failed (503), retries exhausted

Partial output:
  - jobs/active/S014-PRACTITIONER-BACKEND-V2/output/partial-patch.diff

Fallback attempted:
  - claude-review (available, but capabilities: repository_write not supported)

Recommended actions:
  1. [HUMAN] Wait for codex restoration (estimated 10 min) and re-dispatch
  2. [HUMAN] Manually approve claude-review despite capability gap
  3. [HUMAN] Defer job and review partial output manually

Context: Decision required within 30 minutes or job will be auto-abandoned.
```

---

## 9. Release Pipeline

### 9.1 Release Flow

The release pipeline coordinates multiple jobs into a single release:

```
Release request (human or automated)
      │
      ▼
┌──────────────────────────────────────────┐
│  RELEASE ORCHESTRATOR                    │
│                                          │
│  1. Collect all jobs in release scope    │
│  2. Verify all jobs are COMPLETED        │
│  3. Verify all approvals are APPROVED    │
│  4. Run consolidated regression          │
│  5. Run consolidated security scan       │
│  6. Run full governance audit            │
│  7. Prepare release report               │
│  8. Present for final approval           │
│  9. On approval: record release notes    │
│  10. On rejection: return to queue       │
└──────────────────────────────────────────┘
```

### 9.2 Gating Conditions

A release proceeds only when:

- All included jobs have status `COMPLETED`
- All `approval_required` jobs have `APPROVED` status
- Consolidated regression passes
- Consolidated security scan passes
- Governance audit passes
- All repository boundary checks pass (combined scope of all jobs)

### 9.3 Release Rollback

Rollbacks are human-initiated (per Kernel policy). The Orchestrator supports rollback by:

- Preserving all job artifacts indefinitely (no archival on release rejection)
- Providing a `jobs/rollback/<release_id>/` directory for rollback plans
- Recording the pre-release state (Git commit SHA) in the release report

---

## 10. Multi-Agent Coordination

### 10.1 Coordination Model

Multi-agent jobs are coordination patterns where multiple agents contribute to a single job. The Orchestrator manages the sequence.

**Serial coordination:** Agents execute sequentially, each reading the previous agent's output artifact.

**Fan-out coordination:** One job spawns multiple sub-jobs that execute independently, then merge.

**Pipeline coordination:** Agents execute in a fixed validation pipeline after execution.

### 10.2 Fan-Out Example

```
Job: "Refactor practitioner backend"
  │
  ├── Sub-job 1: Update data models       (builder-template → codex-review)
  ├── Sub-job 2: Update controllers        (builder-template → codex-review)
  ├── Sub-job 3: Update views              (wordpress-plugin-template → codex-review)
  │
  │         (all sub-jobs complete)
  │
  ├── Merge: Combine patches              (builder-template → codex-review)
  ├── Review: Code review                 (architecture-guardian-template → claude-review)
  ├── QA: Browser testing                 (ui-audit-template → openclaw)
  └── Release: Package as release         (release → gpt-governance)
```

The Orchestrator manages fan-out by:

1. Creating sub-job packets from the parent job packet
2. Tracking completion of each sub-job
3. Proceeding to merge step only when all sub-jobs complete
4. Propagating failures: if any sub-job fails, dependents are blocked
5. Collecting decision logs from all sub-jobs for governance audit

### 10.3 Agent Memory Boundaries

Agents have bounded memory:

- **Per-session memory:** Limited to the job's context budget (section 4.3).
- **No cross-session memory:** Agent A's session does not leak into Agent B's session.
- **No agent-specific memory store:** All durable state is in artifacts or LisaOS memory files.
- **Tool availability:** Agents can read any artifact in `jobs/`, but cannot write outside their job's directory.
- **Repository writes:** Constrained by the capability envelope and repository boundary rules.

---

## 11. Session Rotation

### 11.1 Fresh Session Strategy

Each job or sub-job runs in a fresh OpenClaw session. This provides:

- **Clean context:** No history bleed from previous conversations
- **Deterministic behaviour:** Consistent starting state for every job
- **Budget control:** Session ends when the job completes — no accumulated token waste
- **Isolation:** Failed job sessions do not affect other sessions
- **Composable sessions:** Multiple sessions can run in parallel with full independence

### 11.2 When to Rotate

| Trigger | Action |
|---------|--------|
| Job completed | End session immediately |
| Job failed non-recoverable | End session, save partial output |
| Validation stage completed | End validation session |
| Context budget exceeded | Rotate session: checkpoint progress, start new session with checkpoint context |
| Session timeout | Kill and restart with fallback |
| Human escalation | Keep alive until human responds, then end |

### 11.3 Cross-Agent Context Transfer

Cross-agent context is transferred **through artifacts only**:

```
Session A (Builder) completes:
  Writes: implementation-report.yml, decision-log.yml
  Ends session ✓

Session B (Reviewer) starts:
  Reads: job-packet.yml, context-packet.yml, implementation-report.yml, decision-log.yml
  Writes: review-report.yml
  Ends session ✓

No chat history, no conversation dump, no live agent handoff.
Artifact-first handoff ensures full determinism.
```

---

## 12. Weaknesses and Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Orchestrator becomes a bottleneck for parallel jobs | Medium | File-based job states are lock-free for reads; writes use atomic rename. For true parallelism, a distributed queue is deferred (ADR-K010). |
| Session creation overhead for validation stages | Low | Validation sessions are lightweight (short context, focused agent). |
| Heartbeat mechanism introduces coupling | Medium | Heartbeats are advisory, not mandatory. Missing heartbeat triggers investigation, not immediate kill. |
| Multiple simultaneous context pack assemblies conflict | Low | File-based isolation per job ID prevents collision. |
| Large fan-out jobs create management overhead | Medium | 5-10 concurrent sub-jobs is manageable. Beyond that, a workflow agent should coordinate. |

---

## 13. Dependencies on Existing LisaOS Components

| Component | Role in Orchestration |
|-----------|----------------------|
| `registry/agents.yml` | Agent loading, runtime profiles, fallback chains |
| `registry/runtimes.yml` | Runtime definitions for dispatch |
| `registry/jobs.yml` | Job type routing rules |
| `registry/capabilities.yml` | Capability envelope building |
| `lisaos/policies/routing.yml` | Job type → routing rules |
| `runtime/resolver/README.md` | Future resolver specification (L005 builds on this) |
| `runtime/providers/` | Per-runtime provider documentation |
| `lisaos/runtime/registry.yml` | OpenClaw runtime role definitions |

---

## Related Documents

- `docs/LISAOS/L005_RUNTIME_ROUTING_ARCHITECTURE.md` — Runtime resolver design
- `docs/LISAOS/L006_AGENT_COMMUNICATION_ARCHITECTURE.md` — Artifact-driven communication
- `docs/LISAOS/LISAOS_CONTEXT_MANAGEMENT.md` — Detailed context management
- `docs/LISAOS/KERNEL.md` — Kernel architecture (sections 3-7)
- `docs/LISAOS/KERNEL_DECISIONS.md` — ADR-K001 through ADR-K011
- `docs/ARCHITECTURE/LISA_OPENCLAW_INTEGRATION.md` — Lisa-OpenClaw integration boundary
- `runtime/openclaw/ROLE.md` — OpenClaw runtime role
- `runtime/openclaw/QA_OPERATOR.md` — QA operator runtime documentation
