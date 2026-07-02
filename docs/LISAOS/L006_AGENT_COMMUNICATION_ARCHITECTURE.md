# L006 — Agent Communication Architecture

**Job ID:** L005-L007-LISAOS-ORCHESTRATION-DESIGN-STUDY  
**Repository:** `~/Lisa`  
**Scope:** Artifact-driven communication model for LisaOS agents.  
**Runtime behaviour:** Unchanged. Documentation only.

---

## 1. Purpose

L006 defines how LisaOS agents communicate. The fundamental principle:

**Agents communicate through artifacts, not through chat history.**

Every handoff, every decision, every output is a documented, versioned, validated artifact — not a message in a conversation transcript. This ensures:

- **Durability:** Artifacts survive session restarts and agent swaps.
- **Auditability:** Every communication is recorded and referenceable.
- **Determinism:** Any agent can reconstruct the full context from artifacts alone.
- **Scalability:** Artifacts can be indexed, searched, and aggregated across jobs.

---

## 2. Communication Principles

### 2.1 Artifact-First

All inter-agent communication uses structured artifacts. Artifacts are files in predetermined locations with defined schemas. Agents read artifacts to understand context; they write artifacts to produce output or hand off to the next agent.

### 2.2 One Writer, Many Readers

Each artifact has a single owner (the agent that created it) but may be read by any agent in the system. Ownership is tracked in the artifact's metadata.

### 2.3 Immutable After Validation

Once an artifact passes validation and is accepted into the job record, it is immutable. Updates create new versions; the original is preserved in the audit trail.

### 2.4 Schema-Governed

Every artifact type has a defined schema. Required fields are enforced. Optional fields are documented. Versioning tracks schema evolution.

### 2.5 Repository-Bound

All artifacts live in Git-tracked directories. No communication state lives outside the repository. This enforces durability, versioning, and auditability.

---

## 3. Artifact Types

### 3.1 Artifact Taxonomy

```
ARTIFACT TYPES
│
├── Job Artifacts (per-job, stored in job-specific paths)
│   ├── JOB_PACKET         # Job definition and requirements
│   ├── CONTEXT_PACKET     # Assembled execution context
│   ├── IMPLEMENTATION_REPORT  # Engineering output
│   ├── REVIEW_REPORT      # Code/architecture review output
│   ├── QA_REPORT          # Browser/test QA output
│   ├── APPROVAL_PACKET    # Approval presentation
│   ├── DECISION_LOG       # Agent decisions and rationale
│   └── RELEASE_REPORT     # Release readiness and notes
│
├── System Artifacts (cross-job, stored in central paths)
│   ├── MEMORY_NOTES       # Durable knowledge
│   ├── ROUTING_DECISIONS  # Routing history
│   └── AUDIT_RECORDS      # Job lifecycle audit trail
│
└── Reference Artifacts (read-only input)
    ├── REGISTRY_ENTRIES    # Registry definitions
    ├── ADRS               # Architecture decisions
    ├── BUSINESS_RULES      # Domain rules
    └── ARCHITECTURE_DOCS   # Maps, flows, designs
```

### 3.2 Job Packet

**Purpose:** Defines a job — what needs to be done, by whom, with what constraints.

**Owner:** Planner (or human, if created directly)

**Read by:** Router, Agent Dispatcher, Context Loader, selected agent

**Schema:**

```yaml
job_packet:
  version: 1.0
  job_id: string                    # Unique identifier (e.g., S014-PRACTITIONER-BACKEND-V2)
  job_type: string                  # From registry/jobs.yml (e.g., ENGINEERING, DOCS)
  title: string                     # Human-readable title
  objective: string                 # One-paragraph description of what to accomplish
  created_by: string                # Agent or human who created the packet
  created_at: ISO-8601              # Timestamp
  workflow_id: string | null        # Reference to parent workflow if applicable

  target_repository: string         # Repository path (e.g., ~/Projects/WBS/healing-events-booking)
  repository_boundary: string       # Bound path (e.g., /var/www/heb)
  allowed_paths: [string]           # Paths the agent may modify
  prohibited_paths: [string]        # Paths the agent must not modify

  required_capabilities: [string]   # From registry/capabilities.yml
  prohibited_capabilities: [string] # Capabilities the agent must not use

  preferred_agent: string           # Agent ID from registry/agents.yml
  preferred_runtime_profile: string # Runtime profile (optional override)

  context_files: [string]           # File paths to include in context
  context_budget: int               # Max tokens for context (optional)

  validation_required: boolean      # Must validation pipeline run?
  approval_required: boolean        # Must human approve?
  requires_approved_packet: boolean # Is a pre-approved packet required?

  output_expected: [string]         # Artifact types expected as output
  output_path: string               # Directory for output artifacts

  depends_on: [string]              # Job IDs this job depends on
  priority: int                     # 1 (highest) to 5 (lowest)
  ttl_minutes: int                  # Maximum execution time

  status: enum                      # DRAFT | QUEUED | ASSIGNED | IN_PROGRESS
                                    # | VALIDATING | AWAITING_APPROVAL
                                    # | COMPLETED | FAILED | REJECTED
```

**Lifecycle:**

```
DRAFT ──► QUEUED ──► ASSIGNED ──► IN_PROGRESS ──► VALIDATING ──► AWAITING_APPROVAL ──► COMPLETED
                                                                              │
                                                                              └──► REJECTED ──► DRAFT (revision)
                         │
                         └──► FAILED
```

**Validation rules:**

- `job_id` must be unique across all active and completed jobs.
- `job_type` must be defined in `registry/jobs.yml`.
- `required_capabilities` must be defined in `registry/capabilities.yml`.
- `preferred_agent` must be defined in `registry/agents.yml`.
- If `requires_approved_packet: true`, the referenced packet must exist and be approved.
- If `target_repository` differs from the LisaOS repository, a repository boundary check must pass.
- All `output_expected` artifact types must be defined in this document's artifact taxonomy.

**Storage location:** `jobs/queue/<job_id>/job-packet.yml` (queued) or `jobs/active/<job_id>/job-packet.yml` (active)

### 3.3 Context Packet

**Purpose:** The assembled execution context for a job. Produced by the Context Loader (Kernel component).

**Owner:** Context Loader

**Read by:** Assigned agent (as the primary execution context)

**Schema:**

```yaml
context_packet:
  version: 1.0
  job_id: string                    # Reference to the job packet
  assembled_at: ISO-8601

  sources:
    packet: string                  # Path to job packet
    repository:
      path: string                  # Repository root
      head_commit: string           # Current HEAD SHA
      branch: string                # Current branch
    lisaos:
      - path: string                # Path to relevant LisaOS doc
      - ...
    business_rules:
      - path: string
      - ...
    architecture:
      - path: string
      - ...
    reports:
      - path: string
      - ...
    memory:
      - path: string                # Relevant memory files
      - ...

  conversation:                     # TEMPORARY — not authoritative
    status: TRUNCATED | NOT_INCLUDED
    truncated_tokens: int           # How many tokens were removed
    total_tokens: int               # Original conversation token count

  compiled_context: string          # Assembled, prioritised, deduplicated context text
  total_tokens: int                 # Token count of compiled context
  budget_used: int                  # How much of the context budget was consumed
  budget_remaining: int             # Remaining budget for agent's own context

  token_breakdown:
    job_packet: int
    repository: int
    lisaos_docs: int
    business_rules: int
    architecture: int
    reports: int
    memory: int
    conversation: int               # 0 if not included
```

**Storage location:** `jobs/active/<job_id>/context-packet.yml`

**Note:** The Context Packet is an **assembly summary**, not the actual context data. The `compiled_context` field is the assembled text; the `sources` list provides traceability.

### 3.4 Implementation Report

**Purpose:** Documents the output of an engineering or implementation job. Produced by the builder agent after execution.

**Owner:** Builder agent (e.g., builder-template, wordpress-plugin-template)

**Read by:** Reviewer agent, QA agent, Governance pipeline, human approver

**Schema:**

```yaml
implementation_report:
  version: 1.0
  job_id: string
  agent_id: string                  # Agent that produced this report
  runtime_id: string                # Runtime used for execution
  model: string                     # Model identifier
  started_at: ISO-8601
  completed_at: ISO-8601
  duration_seconds: int

  objective_summary: string         # What was attempted
  changes_made:                     # Summary of changes
    - file: string                  # File path (relative to repository)
      action: enum                  # CREATE | MODIFY | DELETE | RENAME
      summary: string               # What changed and why
    - ...

  files_created: [string]
  files_modified: [string]
  files_deleted: [string]

  acceptance_criteria:              # Status of each AC from the job packet
    - criterion: string
      status: enum                  # MET | PARTIALLY_MET | NOT_MET | BLOCKED
      notes: string

  blockers:                         # Any blocking issues encountered
    - description: string
      severity: enum                # CRITICAL | MAJOR | MINOR
      resolution: string | null

  decisions_made:
    - decision: string
      rationale: string
      alternatives_considered: string | null
      impact: string

  validation_results:
    static_review: enum             # PASS | PASS_WITH_WARNINGS | FAIL | NOT_RUN
    tests: enum
    notes: string

  artifacts_produced:
    - path: string                  # Path to patch, diff, or output files
      type: string                  # PATCH | DIFF | MIGRATION | CONFIG
      description: string

  configuration_changes:            # Any config files modified
    - file: string
      old_value: string | null
      new_value: string
      impact: string

  documentation_updated_at: [string] # Paths to updated documentation

  overall_status: enum              # COMPLETED | PARTIAL | FAILED | BLOCKED
  summary: string                   # Executive summary for approver
```

**Storage location:** `jobs/active/<job_id>/implementation-report.yml` → moves to `jobs/completed/<job_id>/implementation-report.yml` on completion.

### 3.5 Review Report

**Purpose:** Documents the output of a code or architecture review. Produced by a reviewer agent.

**Owner:** Reviewer agent (e.g., architecture-guardian-template, security-review-template)

**Read by:** QA agent, Governance pipeline, human approver, builder (for feedback)

**Schema:**

```yaml
review_report:
  version: 1.0
  job_id: string
  reviewer_agent_id: string
  runtime_id: string
  review_type: enum                 # CODE_REVIEW | ARCHITECTURE_REVIEW | SECURITY_REVIEW
                                    # | DOCUMENTATION_REVIEW | UI_AUDIT
  reviewed_at: ISO-8601

  scope: string                     # What was reviewed (files, architecture area, approach)
  artifact_reviewed: string         # Reference to the implementation report or other artifact

  findings:
    - id: string                    # Unique finding identifier
      severity: enum                # CRITICAL | HIGH | MEDIUM | LOW | INFO
      category: enum                # SECURITY | PERFORMANCE | ARCHITECTURE | STYLE
                                    # | LOGIC | TESTING | DOCUMENTATION | GOVERNANCE
      location: string              # File or area where the finding applies
      description: string           # What was found
      recommendation: string        # What to do about it
      recommendation_effort: enum   # TRIVIAL | SMALL | MEDIUM | LARGE
      acceptance: enum | null       # ACCEPTED | REJECTED | DEFERRED (set by builder or human)
    - ...

  summary:
    total_findings: int
    critical: int
    high: int
    medium: int
    low: int
    info: int

  overall_verdict: enum             # APPROVED | APPROVED_WITH_COMMENTS | REVISION_REQUIRED
                                    # | REJECTED
  verdict_rationale: string

  compliance_check:
    scope_compliance: enum          # PASS | FAIL | NOT_CHECKED
    capability_compliance: enum
    architecture_compliance: enum
    repository_boundary_compliance: enum

  governance_recommendation: string # Guidance for the governance pipeline

  artifacts_produced:
    - path: string
      type: string                  # PATCH (suggested fix) | REPORT | DIFF
      description: string
```

**Storage location:** `jobs/active/<job_id>/review-report.yml` → moves to `jobs/completed/<job_id>/review-report.yml` on completion.

### 3.6 QA Report

**Purpose:** Documents the output of a QA or testing job. Produced by a QA agent.

**Owner:** QA agent (e.g., ui-audit-template)

**Read by:** Governance pipeline, human approver, builder (for fix iteration)

**Schema:**

```yaml
qa_report:
  version: 1.0
  job_id: string
  qa_agent_id: string
  runtime_id: string
  qa_type: enum                     # BROWSER_TESTING | UNIT_TEST | INTEGRATION_TEST
                                    # | REGRESSION | SMOKE_TEST | MANUAL_AUDIT
  executed_at: ISO-8601
  duration_seconds: int

  environment:
    url: string                     # Test target URL
    browser: string | null          # Browser used (for browser QA)
    viewport: string | null         # Viewport size
    test_suite: string              # Reference to the test suite used

  test_results:
    total: int
    passed: int
    failed: int
    skipped: int
    warnings: int

  failures:
    - test_name: string
      description: string
      severity: enum                # CRITICAL | MAJOR | MINOR | COSMETIC
      screenshot: string | null     # Path to screenshot evidence
      console_errors: [string]      # Browser console errors if applicable
      reproduction: string          # Steps to reproduce
      regression: boolean           # Was this previously passing?
    - ...

  screenshots:                      # Evidence gallery
    - path: string
      description: string
      timestamp: ISO-8601

  overall_result: enum              # PASS | PASS_WITH_WARNINGS | FAIL

  recommendation: string            # Pass to approval? Needs fixes? Block release?

  artifacts_produced:
    - path: string
      type: string                  # SCREENSHOT | TRACE | VIDEO | LOG | REPORT
      description: string
```

**Storage location:** `jobs/active/<job_id>/qa-report.yml`

### 3.7 Approval Packet

**Purpose:** Presents a completed job for human approval. Produced by the Approval Gateway.

**Owner:** Approval Gateway (Kernel component)

**Read by:** Human approver (Roshan)

**Schema:**

```yaml
approval_packet:
  version: 1.0
  job_id: string
  job_type: string
  title: string
  objective: string                 # Short summary of what was done

  agent: string                     # Agent that executed the job
  runtime: string                   # Runtime used
  model: string                     # Model identifier
  duration: string                  # Human-readable duration (e.g., "12m 34s")

  artifacts_produced:
    - path: string
      description: string
    - ...

  validation_summary:
    static_review: enum             # PASS | PASS_WITH_WARNINGS | FAIL | NOT_RUN
    tests: enum
    browser_qa: enum
    regression: enum
    security: enum
    governance: enum

  review_verdict: enum | null       # From review report, if applicable
  qa_result: enum | null            # From QA report, if applicable

  risk_assessment:
    level: enum                     # LOW | MEDIUM | HIGH | CRITICAL
    reasoning: string
    affected_systems: [string]

  changes_summary:                  # High-level summary of changes
    files_created: int
    files_modified: int
    files_deleted: int
    impact_summary: string

  governance_audit:
    scope_compliance: enum
    capability_compliance: enum
    artifact_completeness: enum
    validation_pass: enum
    documentation_update: enum
    no_scope_creep: enum
    no_security_violation: enum
    overall: enum                   # PASS | FAIL

  presented_at: ISO-8601
  approved_by: string | null
  approved_at: ISO-8601 | null
  status: enum                      # PENDING | APPROVED | REJECTED
  rejection_reason: string | null

  escalation:                       # Present if any escalation occurred
    - reason: string
      resolution: string
```

**Storage location:** `jobs/active/<job_id>/approval-packet.yml`

### 3.8 Decision Log

**Purpose:** Records every significant decision made during job execution. Written incrementally during execution.

**Owner:** Any agent making a decision

**Read by:** Governance pipeline, Memory Writer, audit review

**Schema:**

```yaml
decision_log:
  version: 1.0
  job_id: string
  entries:
    - id: string                    # Sequential ID (e.g., D001)
      timestamp: ISO-8601
      agent_id: string              # Agent that made the decision
      category: enum                # SCOPE | APPROACH | IMPLEMENTATION
                                    # | CONFIGURATION | ARCHITECTURE | ESCALATION
      decision: string              # What was decided
      context: string               # Why this decision was needed
      options_considered: [string]  # Alternatives
      rationale: string             # Why this option was chosen
      impact: string                # What this decision affects
      reviewed: boolean             # Has governance reviewed this?
      adr_created: boolean          # Does this need an ADR?
    - ...
```

**Storage location:** `jobs/active/<job_id>/decision-log.yml`

### 3.9 Release Report

**Purpose:** Documents release readiness and release notes. Produced by the Release agent.

**Owner:** Release agent

**Read by:** Human approver, deployment pipeline, downstream consumers

**Schema:**

```yaml
release_report:
  version: 1.0
  release_id: string                # e.g., RELEASE-2026-07-03
  release_type: enum                # PATCH | MINOR | MAJOR | HOTFIX
  prepared_by: string               # Agent that prepared the release
  prepared_at: ISO-8601

  included_jobs:
    - job_id: string
      title: string
      type: string
      approval_status: enum

  release_notes:
    features:
      - title: string
        description: string
        references: [string]        # Issue or job IDs
    fixes:
      - title: string
        description: string
    changes:
      - title: string
        description: string

  readiness_checks:
    all_jobs_approved: boolean
    all_validation_passed: boolean
    governance_passed: boolean
    regression_passed: boolean
    security_passed: boolean

  deployment_plan:
    strategy: enum                  # ROLLING | BLUE_GREEN | CANARY | FULL
    steps:
      - step: int
        action: string
        verification: string
    rollback_plan:
      trigger: string               # Condition that triggers rollback
      steps:
        - step: int
          action: string
    risk_level: enum                # LOW | MEDIUM | HIGH

  overall_status: enum              # READY | BLOCKED | DEFERRED
  blockers:
    - description: string
      severity: enum
```

**Storage location:** `jobs/release/<release_id>/release-report.yml`

### 3.10 Routing Decision

**Purpose:** Records the routing decision for each job. Produced by the Router agent.

**Owner:** Router agent

**Read by:** Audit Logger, Governance pipeline, human review

**Schema:**

```yaml
routing_decision:
  version: 1.0
  job_id: string
  routed_by: string                 # Router agent or human
  routed_at: ISO-8601

  job_classification:
    job_type: string
    agent: string
    runtime_profile: string

  capability_resolution:
    required: [string]
    prohibited: [string]
    resolved_envelope:
      allowed: [string]
      prohibited: [string]

  runtime_selection:
    candidates_evaluated:
      - runtime: string
        profile: string
        status: string
        score: float
    selection:
      runtime: string
      rationale: string
    fallback_chain:
      - runtime: string
        profile: string

  context_summary:
    files_included: int
    total_tokens: int
    conversation_included: boolean
```

**Storage location:** `jobs/active/<job_id>/routing-decision.yml`

---

## 4. Handoff Rules

### 4.1 Handoff Protocol

An agent handoff occurs when one agent completes its work and the next agent begins. Handoffs are always mediated by artifacts — never by passing messages in a chat transcript.

```
┌──────────┐     writes      ┌──────────────┐     reads      ┌──────────┐
│ Planner  │ ──────────────► │ Job Packet   │ ─────────────► │ Router   │
└──────────┘                 └──────────────┘                └──────────┘
                                   │
                           ┌───────┴────────┐
                           │ Routing        │
                           │ Decision       │
                           └───────┬────────┘
                                   │
                           ┌───────┴────────┐
                           │ Context        │
                           │ Packet         │
                           └───────┬────────┘
                                   │
                     ┌─────────────┼─────────────┐
                     │             │             │
               ┌─────▼────┐ ┌──────▼─────┐ ┌─────▼────┐
               │ Builder  │ │ Reviewer   │ │ QA       │
               │ writes   │ │ writes     │ │ writes   │
               │ Impl.    │ │ Review     │ │ QA       │
               │ Report   │ │ Report     │ │ Report   │
               └──────────┘ └────────────┘ └──────────┘
                     │             │             │
                     └─────────────┼─────────────┘
                                   │
                           ┌───────┴────────┐
                           │ Approval       │
                           │ Packet         │
                           └───────┬────────┘
                                   │
                     ┌─────────────┼─────────────┐
                     │             │             │
               ┌─────▼────┐ ┌──────▼─────┐ ┌─────▼────────┐
               │ Release  │ │ Memory     │ │ Audit       │
               │ Report   │ │ Writer     │ │ Logger      │
               └──────────┘ └────────────┘ └──────────────┘
```

### 4.2 Handoff Rules

1. **Read before write.** An agent must read the job packet, context packet, and any predecessor artifacts before beginning work. Reading without writing is always safe.

2. **One writer per artifact.** Each artifact type has a single owning agent. Two agents never write to the same artifact.

3. **Artifact completion signals readiness.** An agent's completion is signalled by writing its output artifact. Polling or listening for completion events is done on the artifact directory, not on the agent.

4. **Validation before handoff.** An artifact is not considered "handed off" until it passes structural validation (schema check, required fields present). An agent that produces an invalid artifact must fix it before the handoff proceeds.

5. **No chat-history dependencies.** If a job packet, context packet, and all predecessor artifacts are available, the agent must be able to complete its work. The agent should never need to reference the conversation transcript to understand what to do.

6. **Idempotent reads.** Reading an artifact multiple times must produce the same result. Artifacts are immutable once validated.

### 4.3 Ownership Model

| Agent | Owns | Reads |
|-------|------|-------|
| Planner | Job Packet | Context from sources |
| Router | Routing Decision | Job Packet |
| Context Loader | Context Packet | Job Packet, Repository, Docs, Rules |
| Builder (template) | Implementation Report | Job Packet, Context Packet, Routing Decision |
| Reviewer (template) | Review Report | Implementation Report (or Job Packet for pre-review) |
| QA (template) | QA Report | Implementation Report, Review Report |
| Approval Gateway | Approval Packet | Implementation Report, Review Report, QA Report, Routing Decision |
| Release | Release Report | All job artifacts for the release scope |
| Memory | Memory Notes | Decision Log, completed job artifacts |

### 4.4 Validation Ownership

Each artifact has a validation owner responsible for schema compliance:

| Artifact | Validation Owner | When |
|----------|-----------------|------|
| Job Packet | Planner (self-validate) | Before enqueue |
| Context Packet | Context Loader (self-validate) | Before dispatch |
| Implementation Report | Builder (self-validate) + Static Review stage | After write |
| Review Report | Reviewer (self-validate) | After write |
| QA Report | QA Agent (self-validate) | After write |
| Approval Packet | Approval Gateway (self-validate) | Before presentation |
| Routing Decision | Router (self-validate) | After write |
| Release Report | Release Agent (self-validate) + Governance | Before presentation |
| Decision Log | Writing agent (self-validate) | Each entry |

---

## 5. Artifact Lifecycle

### 5.1 Lifecycle States

```
DRAFT ──► VALIDATED ──► PUBLISHED ──► APPROVED ──► ARCHIVED
                │            │
                └──► REJECTED         └──► SUPERSEDED
```

| State | Description |
|-------|-------------|
| `DRAFT` | Being written; not yet complete. |
| `VALIDATED` | Passed schema validation; ready for reading. |
| `PUBLISHED` | Accepted into the job record; immutable. |
| `APPROVED` | Passed human approval (only applies to Approval Packet). |
| `ARCHIVED` | Moved to long-term storage after job completion. |
| `REJECTED` | Failed validation; returned to writer for revision. |
| `SUPERSEDED` | A newer version of this artifact exists. |

### 5.2 Storage Layout

```
jobs/
  queue/<job_id>/
    job-packet.yml
  active/<job_id>/
    job-packet.yml
    context-packet.yml
    routing-decision.yml
    implementation-report.yml
    review-report.yml
    qa-report.yml
    decision-log.yml
    approval-packet.yml
  completed/<job_id>/
    job-packet.yml
    context-packet.yml
    routing-decision.yml
    implementation-report.yml
    review-report.yml
    qa-report.yml
    decision-log.yml
    approval-packet.yml
  release/<release_id>/
    release-report.yml
```

### 5.3 Archival Rules

- Artifacts in `jobs/active/` are deleted after 30 days of inactivity.
- Artifacts in `jobs/completed/` are moved to `jobs/audit/<year>/<month>/` after 90 days.
- Release reports are retained indefinitely.
- Decision logs are retained indefinitely.

---

## 6. Versioning

### 6.1 Artifact Versioning

Each artifact type has its own `version` field (semantic versioning: Major.Minor).

- **Major version increment:** Schema-breaking change (required field added or removed).
- **Minor version increment:** Non-breaking addition (optional field added, documentation updated).

### 6.2 Backward Compatibility

- Agents that write version N+1 should also be able to read version N.
- Agents that only read version N may not understand version N+1.
- The Context Loader should prefer the most recent compatible version of each artifact.

### 6.3 Artifact Evolution Log

Each artifact type should have an evolution log documenting schema changes:

```yaml
# Embedded in artifact type documentation
evolution:
  - version: 1.0
    date: 2026-07-03
    changes: Initial definition
  - version: 1.1
    date: YYYY-MM-DD
    changes: Added escalation field
```

---

## 7. Cross-Agent Context Transfer

### 7.1 Rules

1. **Agents do not pass chat history.** Context transfer is solely through artifacts.
2. **The Context Packet aggregates all predecessor artifacts** for the receiving agent.
3. **Decision logs are always included** in the context for any downstream agent.
4. **Conversation context is explicitly excluded** from forward transfer (per ADR-K002).

### 7.2 Context Transfer Flow

```
Agent A (Builder) ──► writes Implementation Report ──►
                                                         │
Agent B (Reviewer) ◄── reads ────────────────────────── ┘
                    ├── Job Packet (from queue)
                    ├── Context Packet (from Context Loader)
                    ├── Implementation Report (from Agent A)
                    ├── Decision Log (from Agent A)
                    └── Routing Decision (from Router)
```

---

## 8. Weaknesses and Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Artifact schemas drift from actual agent outputs | Medium | Schema validation at write time catches drift; update schemas when agent behaviour changes |
| Agents write partial/invalid artifacts | Low | Validation gates before handoff; cannot proceed with invalid artifact |
| Large job generates too many artifacts | Low | Storage is file-based with archival policy; Git handles versioning |
| Artifact-first slows down simple jobs | Low | For trivial jobs (e.g., single doc update), some artifacts can be optional (e.g., Decision Log can be empty) |
| Agents read stale artifacts | Low | Timestamps and commit SHAs in Context Packet prevent staleness; agents should verify |

---

## Related Documents

- `docs/LISAOS/L007_OPENCLAW_ORCHESTRATION_ARCHITECTURE.md` — How artifacts flow through OpenClaw orchestration
- `docs/LISAOS/LISAOS_ARTIFACT_LIFECYCLE.md` — Detailed artifact lifecycle, storage, and archival policy
- `docs/LISAOS/KERNEL.md` — Kernel architecture (Context Loader, Agent Dispatcher, Validation Pipeline)
- `docs/LISAOS/KERNEL_DECISIONS.md` — ADR-K002 (Context Priority), ADR-K011 (Repository Documentation as Truth)
- `docs/LISAOS/REPOSITORY_BOUNDARIES.md` — Repository boundary enforcement
- `registry/jobs.yml` — Job type definitions that reference artifact outputs
