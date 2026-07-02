# LisaOS v3 — Kernel Architecture

**Version:** 3.0  
**Status:** Active  
**Last updated:** 2026-07-02  
**Supersedes:** All previous ad-hoc execution models

> The LisaOS Kernel is the execution model that governs how every job moves through the operating system. It is the permanent operating model for LisaOS v3.

---

## 1. Purpose

The Kernel defines the complete execution lifecycle for every job in LisaOS:

- How work enters the system
- How work is classified
- How agents are selected
- How capabilities are resolved
- How runtimes are selected
- How execution occurs
- How validation occurs
- How governance occurs
- How approval occurs
- How work is archived

The Kernel is **model-agnostic**. No critical workflow depends on a single AI provider. Every runtime can be replaced without changing the Kernel design.

---

## 2. Kernel Responsibilities

| Responsibility | Description |
|---|---|
| **Classification** | Determine the job type from the request |
| **Context** | Assemble the relevant context for execution |
| **Capability resolution** | Determine which capabilities the job requires, allow lists, prohibit lists |
| **Runtime selection** | Choose a runtime based on capability, availability, cost, and health |
| **Agent dispatch** | Assign the job to the correct agent via OpenClaw |
| **Execution monitoring** | Track progress, duration, and output |
| **Validation** | Run static review, tests, browser QA, regression, security, governance |
| **Governance audit** | Verify every job against Lisa Workflow governance rules |
| **Approval gateway** | Present results for human approval |
| **Archival** | Persist job output, decisions, and artifacts to durable memory |

---

## 3. Core Components

### 3.1 Job Queue

**Location:** `jobs/queue.yml`

The Job Queue is a file-based FIFO queue. Jobs enter via `lisa-job-create.sh` or direct YAML entry.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique job identifier (e.g., `S014-PRACTITIONER-BACKEND-V2`) |
| `type` | string | Job type from routing rules (e.g., `ENGINEERING`, `QA_BROWSER`) |
| `title` | string | Human-readable title |
| `status` | enum | `queued` → `assigned` → `active` → `completed` / `failed` |
| `selected_runtime` | string | Runtime resolved by the Scheduler at queue time |
| `created_at` | ISO-8601 | When the job entered the system |
| `assigned_agent` | string (optional) | Agent assigned by OpenClaw |
| `packet_ref` | string (optional) | Reference to the approved implementation packet |
| `approved` | boolean (optional) | Human approval status |

**File states:**

| File | Purpose |
|------|---------|
| `queue.yml` | Incoming jobs awaiting assignment |
| `active.yml` | Jobs currently in execution |
| `completed.yml` | Finished jobs with outcome summary |

**Rules:**
- A job must have a unique ID.
- A job must reference an approved packet for `ENGINEERING` and `ENGINEERING_GLM` types.
- OpenClaw reads from `queue.yml` at route time and moves jobs to `active.yml`.
- On completion, jobs move to `completed.yml` with validation outcomes.

**Interface:**

```
bin/lisa-job-create.sh JOB_ID JOB_TYPE TITLE
  → appends to queue.yml with selected_runtime
```

---

### 3.2 Scheduler

The Scheduler determines when a queued job can proceed.

**Resolution order:**

1. **Pre-requisite check** — Does the job require an approved packet? If `ENGINEERING` or `ENGINEERING_GLM`, the packet must exist and be approved.
2. **Dependency check** — Does the job depend on another job completing first?
3. **Resource check** — Is the preferred runtime available? If not, select fallback.
4. **Assignment** — Move from `queue.yml` → `active.yml` with `assigned_agent`.
5. **Handoff** — Provide OpenClaw with job ID, type, agent, runtime, context pack.

**Rules:**
- Only one `ENGINEERING` job executes at a time (repository lock).
- `QA_BROWSER` jobs can run concurrently with analysis or documentation jobs.
- `GOVERNANCE` and `SECURITY` jobs gate release; they must complete before a release job proceeds.
- The Scheduler never skips dependency resolution.

---

### 3.3 Context Loader

The Context Loader assembles the execution context before dispatching a job.

**Priority order (highest to lowest):**

```
1. Current Job Packet         — The approved implementation packet
2. Current Repository         — Active codebase state
3. LisaOS Documentation       — MANIFEST.md, AGENTS.md, CAPABILITIES.md, KERNEL.md
4. Business Rules             — docs/BUSINESS_RULES/ (coupons, payments, waitlist, etc.)
5. Architecture Documents     — ADRs, maps, data flows, notes
6. Historical Reports         — QA reports, audits, implementation reports
7. Conversation Context       — Current session history (temporary only)
```

**Critical rule:** Conversation context (item 7) is **temporary only**. Chat history must never be treated as authoritative memory. All durable state must be in Git-tracked documentation.

**Context pack structure:**

The Context Loader produces a `context pack` — a reference to the specific files needed:

```
job_id: S014-PRACTITIONER-BACKEND-V2
sources:
  - packet: docs/PACKETS/PACKET-001.md
  - repo: /var/www/heb (current HEAD)
  - lisaos:
      - docs/LISAOS/MANIFEST.md
      - docs/LISAOS/AGENTS.md
      - docs/LISAOS/CAPABILITIES.md
  - business_rules:
      - docs/BUSINESS_RULES/appointments.md
  - architecture:
      - docs/ARCHITECTURE/maps/
      - docs/ARCHITECTURE/data-flows/
  - reports:
      - reports/previous-run.md
conversation:              # NOT included in durable context
  - truncated after 4096 tokens
```

---

### 3.4 Capability Resolver

The Capability Resolver determines what a job is allowed and required to do.

**Resolution process:**

1. **Classify job type** — Look up `job_routes` in `registry/routing-rules.yml`.
2. **Identify assigned agent** — Determine which agent handles this job type.
3. **Read agent capabilities** — Look up allowed and prohibited capabilities from `docs/LISAOS/CAPABILITIES.md`.
4. **Apply job-specific constraints** — Some capabilities may be further restricted by the job packet (e.g., "read-only migration review").
5. **Verify least privilege** — Confirm the capability set is no broader than necessary.
6. **Return capability envelope** — A set of `{allowed, prohibited}` constraints passed to OpenClaw.

**Least privilege principle:**

Every job receives the minimum set of capabilities needed to complete it. No agent inherits capabilities beyond its assigned scope.

**Examples:**

- A `docs` job → agent `lisa-docs` → allowed `{read_repo, read_docs, write_doc, restructure_docs, audit_ia}`, prohibited `{write_production_code, manage_secrets, trigger_deployment}`
- An `ENGINEERING` job → agent `lisa-builder` → allowed `{write_production_code, edit_repo, create_migrations, refactor, write_patch, run_tests}`, prohibited `{make_architecture_decisions, change_scope, modify_adr, manage_secrets, trigger_deployment}`

**Capability inheritance:**

Agents inherit capabilities from their role type:

```
Role types:
  ├── engineering (builder)
  │     └── all code capabilities
  ├── analysis (architect, planner, research)
  │     └── read + write analysis/plan capabilities
  ├── verification (qa, reviewer, security)
  │     └── test + review + report capabilities
  ├── documentation (docs, memory-curator)
  │     └── read + write doc/memory capabilities
  └── operations (release)
        └── packaging + version + smoke test capabilities
```

Globally prohibited capabilities are never inherited:

```
change_scope        → Roshan/GPT governance only
manage_secrets      → Roshan only
modify_schema       → Roshan only (except builder with approved packet)
trigger_deployment  → Roshan only
modify_config       → Roshan only
modify_adr          → Roshan/GPT governance only
bypass_gate         → no agent ever
```

**Future expansion:**

New capabilities are added by:
1. Defining the capability in `docs/LISAOS/CAPABILITIES.md`
2. Assigning it to agents via the agent–capability matrix
3. Updating routing rules if a new job type is needed
4. Recording the decision in an ADR

---

### 3.5 Runtime Resolver

The Runtime Resolver selects the execution runtime for a job.

**Resolution order:**

```
1. Look up job type in routing rules        → preferred runtimes (ordered)
2. Check health of preferred runtime        → /status or health probe
3. Check availability of preferred runtime  → rate limit? quota exhausted?
4. Check cost awareness                     → prefer lower cost if capabilities equal
5. Select first healthy, available runtime  → selected_runtime
6. If none available, try fallback         → next preferred runtime
```

**Present state (routing-rules.yml):**

| Job Type | Preferred Runtime(s) | Fallback |
|----------|---------------------|----------|
| ENGINEERING | codex, claude_code | — |
| ENGINEERING_GLM | glm | claude_code, codex |
| QA_BROWSER | openclaw | — |
| LARGE_ANALYSIS | kimi, deepseek, ollama | — |
| CHEAP_ANALYSIS | ollama, deepseek | — |
| GOVERNANCE | gpt | — |
| DOCS | openclaw, any_available | — |
| RELEASE | openclaw | — |
| SECURITY | gpt | — |
| MEMORY | deepseek, any_available | — |

**Health check interface:**

Each runtime should expose a `/status` endpoint or CLI command returning:
- `available`: boolean
- `rate_limited`: boolean
- `quota_exhausted`: boolean
- `rate_limit_reset_at`: ISO-8601 or null
- `latency_ms`: integer (current observed)
- `model`: string (active model name)

**Cost awareness:**

When multiple runtimes support the same capabilities, prefer the lower-cost option:

```
Cost tiers (lowest first):
  very_low   → ollama (local)
  low        → deepseek
  low_medium → kimi
  medium     → openclaw, gpt
  medium_high → codex
  high       → claude_code
  tbd        → glm (not yet configured)
```

**Future benchmarking:**

A benchmark registry will track runtime performance across:
- Capability match accuracy
- Execution speed (time per task type)
- Cost per successful job
- Rate-limit frequency
- Error rate

Benchmarks are stored in `registry/benchmarks.yml` (future).

**Critical rule:** No runtime-specific logic inside agents. Agents request capabilities; the Runtime Resolver selects the runtime. Agents are model-agnostic by design.

---

### 3.6 Agent Dispatcher

The Agent Dispatcher assigns the resolved agent and runtime to the job.

**Dispatch flow:**

```
1. Receive: {job_id, job_type, packet_ref, context_pack}
2. Request from Runtime Resolver: {runtime, model}
3. Receive from Capability Resolver: {capability_envelope}
4. Build agent invocation:
     agent:        <assigned_agent>
     runtime:      <selected_runtime>
     capabilities: <allowed>  (prohibited are enforced by OpenClaw)
     context:      <context_pack.sources>
     job_id:       <job_id>
     output:       <expected_artifact_path>
5. Hand to OpenClaw for execution
```

The Agent Dispatcher does not execute anything itself — it delegates to OpenClaw, which invokes the selected runtime with the specified agent context.

---

### 3.7 Execution Monitor

The Execution Monitor tracks running jobs.

**Tracking fields:**

| Field | Source |
|-------|--------|
| `job_id` | From queue |
| `runtime` | From Runtime Resolver |
| `agent` | From Agent Dispatcher |
| `started_at` | Timestamp at dispatch |
| `last_heartbeat` | Periodic tick from runtime |
| `duration_seconds` | Elapsed since start |
| `artifacts_produced` | Output files produced |
| `status` | `running` / `completed` / `failed` / `timed_out` |

**Monitoring responsibilities:**
- Detect stalled jobs (no heartbeat > 5 minutes)
- Detect timeouts (job exceeds its TTL)
- Log artifacts produced to the job record
- Update `active.yml` with progress

---

### 3.8 Validation Pipeline

The Validation Pipeline runs after execution completes. It is modular — stages can be added, removed, or reordered per job type.

**Stages (in order):**

```
Static Review
    ↓
Tests (unit + integration)
    ↓
Browser QA (if applicable)
    ↓
Regression Check
    ↓
Security Review
    ↓
Governance Audit
```

**Stage details:**

| Stage | Agent | Description |
|-------|-------|-------------|
| Static Review | lisa-reviewer | Code review, architecture compliance, acceptance criteria check |
| Tests | lisa-qa | Run unit tests, integration tests, WP-CLI eval |
| Browser QA | lisa-qa | Headless browser interaction, screenshots (if job has `browser_qa` requirement) |
| Regression | lisa-qa | Run regression test suite, compare against baseline |
| Security | lisa-security | Vulnerability scan, permission check, data handling review |
| Governance | lisa-reviewer | Verify against Lisa Workflow rules, check all artifacts exist |

**Stage results:**

Each stage produces one of:
- `PASS` — No issues found
- `PASS_WITH_WARNINGS` — Minor issues, non-blocking
- `FAIL` — Blocking issue; job cannot proceed to approval

**Skip rules:**

- If a job type does not require a stage (e.g., `CHEAP_ANALYSIS` does not need Browser QA), the stage is skipped.
- If a stage fails, subsequent stages may still run to gather full feedback, unless the failure is `CRITICAL` (security, governance).

---

### 3.9 Governance Pipeline

The Governance Pipeline ensures every completed job meets Lisa Workflow standards before human review.

**Governance checks:**

| Check | Description |
|-------|-------------|
| **Scope compliance** | Did the job stay within its approved packet? |
| **Capability compliance** | Did the agent only use allowed capabilities? |
| **Artifact completeness** | Are all required output artifacts present? |
| **Validation pass** | Did all required validation stages pass? |
| **Documentation update** | Were docs updated if required by the job type? |
| **No scope creep** | No unplanned changes introduced |
| **No security violation** | No prohibited operations attempted |

Governance produces a report appended to the job record:

```yaml
governance:
  status: PASS/FAIL
  checks:
    scope_compliance: PASS
    capability_compliance: PASS
    artifact_completeness: PASS
    validation_pass: PASS
    documentation_update: SKIPPED
    no_scope_creep: PASS
    no_security_violation: PASS
  reviewed_by: lisa-reviewer
  reviewed_at: "2026-07-02T12:00:00Z"
```

---

### 3.10 Approval Gateway

The Approval Gateway is the final gate before work is archived.

**Approval types:**

| Type | Approver | Description |
|------|----------|-------------|
| `ENGINEERING` | Roshan | Code changes, migrations, feature implementation |
| `RELEASE` | Roshan | Deployment to production |
| `GOVERNANCE` | Roshan | Architecture decisions, scope changes |
| `SECURITY` | Roshan | Security-sensitive changes |
| `QA_BROWSER` | Roshan | Pre-release QA sign-off |
| `AUTOMATIC` | Pipeline | Docs, analysis, memory curation — approval only if validation fails |

**Approval presentation:**

The Approval Gateway presents to the human approver:

```
Job ID:      S014-PRACTITIONER-BACKEND-V2
Type:        ENGINEERING
Agent:       lisa-builder
Runtime:     codex
Duration:    12m 34s
Artifacts:
  - docs/IMPLEMENTATION/IMPLEMENTATION_REPORT.md
  - diff/practitioner-backend-v2.patch
Validation:
  static_review:   PASS
  tests:           PASS
  browser_qa:      PASS
  regression:      PASS
  security:        PASS
  governance:      PASS
→ Approve? (Y/N)
```

**Rules:**
- Human approval is the **final authority**. No automated gate bypasses human review for `ENGINEERING`, `RELEASE`, `GOVERNANCE`, `SECURITY`, or `QA_BROWSER`.
- `AUTOMATIC` approval is only valid if all validation stages pass.
- A rejected job returns to the queue with `status: rejected` and a note explaining why.

---

### 3.11 Audit Logger

The Audit Logger records every job's complete lifecycle for traceability.

**Audit record:**

```yaml
audit:
  job_id: S014-PRACTITIONER-BACKEND-V2
  created_at: "2026-07-02T10:00:00Z"
  type: ENGINEERING
  agent: lisa-builder
  runtime: codex
  model: <selected-model>
  started_at: "2026-07-02T10:02:00Z"
  completed_at: "2026-07-02T10:15:00Z"
  duration_seconds: 780
  capabilities_used:
    - write_production_code
    - edit_repo
    - run_tests
    - write_patch
  artifacts:
    - docs/IMPLEMENTATION/IMPLEMENTATION_REPORT.md
    - reports/engineering/s014-patch.diff
  validation:
    static_review: PASS
    tests: PASS
    browser_qa: PASS
    regression: PASS
    security: PASS
    governance: PASS
  governance:
    status: PASS
    reviewed_by: lisa-reviewer
  approval:
    status: approved
    approved_by: Roshan
    approved_at: "2026-07-02T10:20:00Z"
  cost_estimate:
    runtime_cost: medium_high
    duration_seconds: 780
    approximate_tokens: 125000
```

Audit records are stored in `jobs/audit/` (future), or appended to `completed.yml` in the current file-based model.

---

### 3.12 Memory Writer

The Memory Writer persists durable knowledge from completed jobs.

**What gets written:**
- Implementation decisions that should be documented
- Lessons learned from failures
- Validation results that change quality baselines
- Configuration changes that affect future jobs
- New business rules discovered during execution

**What does NOT get written:**
- Raw conversation history
- Intermediate debugging output
- Temporary artifacts
- Reproducible test outputs

**Priority for memory curation:**

```
1. Architecture decisions → ADR
2. New/modified business rules → docs/BUSINESS_RULES/
3. Lessons learned → docs/LESSONS_LEARNED/
4. Quality baselines → docs/QA/QA_MATRIX.md
5. Daily operational notes → memory/YYYY-MM-DD.md (lisa-memory-curator)
```

The Memory Writer is invoked by `lisa-memory-curator` after job archival, not during execution.

---

## 4. Job Lifecycle

### 4.1 Lifecycle Diagram

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                         LISAOS KERNEL                              │
  │                                                                     │
  │   REQUEST                                                           │
  │     │                                                               │
  │     ▼                                                               │
  │   ┌──────────┐    ┌──────────────┐    ┌──────────────────┐         │
  │   │ CLASSIFY │───►│ RESOLVE      │───►│ CAPABILITY       │         │
  │   │ job type │    │ CONTEXT      │    │ RESOLUTION       │         │
  │   └──────────┘    └──────────────┘    └──────────────────┘         │
  │                                                    │               │
  │                                                    ▼               │
  │   ┌──────────┐    ┌──────────────┐    ┌──────────────────┐         │
  │   │ EXECUTE  │◄───│ DISPATCH     │◄───│ RUNTIME          │         │
  │   │          │    │ AGENT        │    │ SELECTION        │         │
  │   └──────────┘    └──────────────┘    └──────────────────┘         │
  │        │                                                            │
  │        ▼                                                            │
  │   ┌──────────────────────────────────────────────────────────┐     │
  │   │                VALIDATION PIPELINE                       │     │
  │   │  ┌─────────┐  ┌──────┐  ┌──────────┐  ┌──────────┐    │     │
  │   │  │STATIC   │  │TESTS │  │BROWSER   │  │REGRESSION│    │     │
  │   │  │REVIEW   │─►│      │─►│QA        │─►│          │    │     │
  │   │  └─────────┘  └──────┘  └──────────┘  └──────────┘    │     │
  │   │                                  │                     │     │
  │   │  ┌──────────┐  ┌────────────┐   ▼                     │     │
  │   │  │SECURITY  │  │GOVERNANCE  │◄────────────────────────│     │
  │   │  │REVIEW    │─►│AUDIT       │                          │     │
  │   │  └──────────┘  └────────────┘                          │     │
  │   └──────────────────────────────────────────────────────────┘     │
  │        │                                                            │
  │        ▼                                                            │
  │   ┌──────────────────┐                                             │
  │   │ APPROVAL GATEWAY │───── Human approves? ───► YES               │
  │   └──────────────────┘                            │                │
  │        │ NO                                       │                │
  │        ▼                                          ▼                │
  │   ┌──────────┐                             ┌──────────┐            │
  │   │ REJECT   │                             │ ARCHIVE  │            │
  │   │ (re-     │                             │          │            │
  │   │  queue)  │                             └────┬─────┘            │
  │   └──────────┘                                  │                  │
  │                                                  ▼                  │
  │                                           ┌──────────────┐         │
  │                                           │ MEMORY       │         │
  │                                           │ WRITER       │         │
  │                                           └──────────────┘         │
  └─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Lifecycle Steps

| Step | Component | Description |
|------|-----------|-------------|
| **1. Request** | Human / Lisa Workflow | Work enters the system as a job request with a type and packet |
| **2. Classification** | Scheduler | Determine job type from routing rules |
| **3. Context Resolution** | Context Loader | Assemble context pack from packet, repo, docs, rules, architecture, history |
| **4. Capability Resolution** | Capability Resolver | Enumerate required, optional, and prohibited capabilities |
| **5. Runtime Selection** | Runtime Resolver | Select runtime based on capability, health, cost, fallback chain |
| **6. Agent Dispatch** | Agent Dispatcher | Assign agent + runtime, build capability envelope, hand to OpenClaw |
| **7. Execution** | Selected Runtime | Agent executes the job within capability constraints |
| **8. Validation** | Validation Pipeline | Static review → Tests → Browser QA → Regression → Security → Governance |
| **9. Governance Audit** | Governance Pipeline | Verify scope, capability, artifact, and validation compliance |
| **10. Human Approval** | Approval Gateway | Present to Roshan for final sign-off |
| **11. Archive** | Audit Logger + Memory Writer | Persist job record, update completed.yml, curate durable knowledge |

---

## 5. Failure Handling

### 5.1 Retry Policy

| Failure Type | Retry Count | Delay | Notes |
|-------------|-------------|-------|-------|
| Runtime unavailable | 2 | 30s, 60s | Try fallback runtime on third attempt |
| Rate limited | 3 | 60s, 120s, 240s | Wait for reset or use fallback |
| Timeout | 1 | Immediate | Retry with fallback runtime |
| Validation failure | 0 | — | Return to human for decision (reject, fix, or override) |
| Security violation | 0 | — | Immediate escalation; no retry |

### 5.2 Fallback Runtime

When the preferred runtime fails:

1. Run capabililty check on next preferred runtime
2. If capabilities match: dispatch with fallback, same job ID
3. If capabilities do not match: log capability gap, escalate to human
4. Preserve all completed work — do not restart unless packet context is invalid

### 5.3 Human Escalation

Jobs are escalated to human (Roshan) when:

- All runtimes are unavailable
- Retry policy exhausted
- Validation failure (static review, security, governance)
- Capability gap in fallback runtime
- Scope was exceeded or packet is invalid
- Any `GOVERNANCE` or `SECURITY` job fails

**Escalation format:**

```
ESCALATION: Job S014-PRACTITIONER-BACKEND-V2
Reason: Fallback runtime lacks capability [capability_name]
Preferred: codex (rate_limited for 120s)
Fallback: claude_code (available, capabilities match: false)
Details: claude_code is missing capability "query_database"
→ Action required: Wait for codex reset, or manually override runtime
```

### 5.4 Partial Completion

If a job completes partially:

1. Record what was completed in `completed.yml` with `status: partial`
2. Return to queue as a new job for the incomplete portion
3. Reference the original job ID in the new job's `depends_on` field

### 5.5 Rollback Principles

Rollbacks are **always human-initiated**. No agent or automation has the `rollback` capability by default. If a rollback is needed:

1. Human creates a `GOVERNANCE` job with `type: rollback`
2. Governance verifies that rollback is appropriate (data safety, user impact)
3. Human creates an `ENGINEERING` job referencing the rollback plan
4. Standard validation and approval gates apply

### 5.6 Timeout Handling

| Job Type | Default TTL | Notes |
|----------|-------------|-------|
| ENGINEERING | 30 minutes | Long-running code tasks |
| QA_BROWSER | 20 minutes | Browser interaction suites |
| LARGE_ANALYSIS | 30 minutes | Deep context analysis |
| GOVERNANCE | 10 minutes | Review should be quick |
| DOCS | 15 minutes | Documentation writing |
| RELEASE | 20 minutes | Packaging and deployment |
| MEMORY | 10 minutes | Curation operations |

On timeout:
1. Execution Monitor kills the job
2. Partial output is saved
3. Job status set to `timed_out`
4. Human receives escalation with partial results

---

## 6. Observability

Every job produces a complete observability record:

| Field | Description | Source |
|-------|-------------|--------|
| `job_id` | Unique identifier | Queue |
| `type` | Job classification | Routing rules |
| `agent` | Assigned agent | Agent Dispatcher |
| `runtime` | Selected runtime | Runtime Resolver |
| `model` | Active model name | Runtime health check |
| `created_at` | Enqueue time | Queue |
| `started_at` | Dispatch time | Execution Monitor |
| `completed_at` | Completion time | Execution Monitor |
| `duration_seconds` | Wall clock duration | Execution Monitor |
| `capabilities_used` | Capabilities exercised | Agent output analysis |
| `artifacts` | Output file paths | Execution Monitor |
| `validation_results` | Per-stage PASS/FAIL | Validation Pipeline |
| `governance_status` | Governance PASS/FAIL | Governance Pipeline |
| `approval_status` | Approved/rejected/pending | Approval Gateway |
| `cost_estimate` | Approximate cost | Runtime Resolver (cost tier) |
| `audit_trail` | Full lifecycle log | Audit Logger |

Observability data is stored in `jobs/completed.yml` for active jobs and archived to `jobs/audit/` for historical records.

---

## 7. Kernel Interfaces

### 7.1 Interface to OpenClaw

```
OpenClaw ←→ Kernel

Kernel → OpenClaw:
  {job_id, agent, runtime, capabilities, context_pack}

OpenClaw → Kernel:
  {job_id, status, artifacts, duration, error}
```

OpenClaw is the execution engine. The Kernel defines what to execute; OpenClaw defines how.

### 7.2 Interface to Git

```
Kernel → Git:
  - Read context (packets, docs, ADRs, architecture)
  - Read business rules
  - Read historical reports

Agent → Git (via capability):
  - Write production code (lisa-builder only)
  - Write documentation (lisa-docs)
  - Write reports (lisa-qa, lisa-reviewer, lisa-security)
  - Write plans (lisa-planner)

Git → Kernel:
  - Commit history for context
  - File tree for analysis
```

Git is authoritative history. The Kernel reads from Git; agents write to Git through capability-constrained operations.

### 7.3 Interface to Registry

```
Kernel → Registry:
  - registry/routing-rules.yml → job_route
  - registry/runtimes.yml → runtime definitions
  - registry/benchmarks.yml → runtime performance (future)

Registry → Kernel:
  - Routing rules for job → agent → runtime mapping
  - Runtime definitions with capabilities, cost, priority
```

The Registry is immutable during a job's lifecycle. If routing rules change while a job is queued, the job uses the rules from when it entered the queue.

### 7.4 Interface to Capabilities

```
Kernel → Capabilities:
  - docs/LISAOS/CAPABILITIES.md → capability definitions
  - AGENTS.md → agent–capability matrix

Capabilities → Kernel:
  - Allowed capability set for agent
  - Prohibited capability set for agent
  - Globally prohibited capabilities
```

The Capability Resolver is the only consumer of the capabilities framework. Agents never self-determine their capabilities.

### 7.5 Interface to Memory

```
Kernel → Memory:
  - Read MEMORY.md and memory/*.md for context
  - Write curated memory after job completion (via lisa-memory-curator)

Memory → Kernel:
  - Previous decisions and lessons learned for context assembly
```

Memory is durable knowledge, not conversation history.

### 7.6 Interface to Jobs

```
Kernel → Jobs:
  - jobs/queue.yml → create, read
  - jobs/active.yml → create, update, read
  - jobs/completed.yml → append, read
  - jobs/audit/ → archive (future)

Jobs → Kernel:
  - Job definitions with type, packet reference, status
```

The Jobs store is the Kernel's primary state.

### 7.7 Interface to Reports

```
Kernel → Reports:
  - reports/ → execution artifacts (screenshots, traces, JSON)

Reports → Kernel:
  - Validation evidence for audit logger
  - Baseline for regression checks
```

Reports are raw artifacts generated during execution. They are referenced by job records but stored separately from jobs for size management.

### 7.8 Future API Interface

The future LisaOS API will expose:

```
POST /api/v1/jobs              → Create job
GET  /api/v1/jobs/:id          → Get job status
GET  /api/v1/jobs/:id/audit    → Get audit trail
GET  /api/v1/runtimes          → List runtimes with health
GET  /api/v1/capabilities      → List capabilities
POST /api/v1/approve/:id       → Approve job
POST /api/v1/reject/:id        → Reject job
```

The API is a read/write facade over the Kernel's interfaces. It is not part of the current Kernel but is architecturally compatible.

---

## 8. Future Compatibility

### 8.1 Multiple Builders

The Kernel supports multiple concurrent builders by:

1. **Repository locking per scope** — Different packages can be built concurrently
2. **Agent isolation** — Each builder instance is an independent agent dispatch
3. **Job type expansion** — New job types (e.g., `ENGINEERING_FRONTEND`, `ENGINEERING_BACKEND`) can route to different builder instances
4. **Merge gate** — Independent outputs merged by a coordinating job

No architecture change needed. The existing `lisa-builder` agent can be instantiated multiple times as long as scope doesn't overlap.

### 8.2 Multiple Reviewers

The Kernel supports multiple reviewers by:

1. **Parallel validation stages** — Static review, security review, and governance audit can run concurrently
2. **Reviewer pools** — Each agent (lisa-reviewer, lisa-security) can have multiple instances
3. **Aggregation** — Validation Pipeline aggregates results from concurrent review stages

No architecture change needed. The existing stages are already modular.

### 8.3 Cloud Execution

The Kernel supports cloud execution by:

1. **Runtime abstraction** — Local runtimes (`ollama`) and cloud runtimes (`codex`, `gpt`, `kimi`) already coexist
2. **Context streaming** — Context packs can be serialised and transmitted to remote runtimes
3. **Artifact sync** — Remote execution artifacts sync back to the local file system
4. **Health check extension** — Cloud runtime health checks use API probes instead of CLI

No architecture change needed. The Runtime Resolver already treats all runtimes equally.

### 8.4 Distributed Workers

The Kernel supports distributed workers by:

1. **Job queue as message bus** — The file-based queue becomes a distributed queue (e.g., Redis, NATS)
2. **Worker registration** — Workers register with the Scheduler, not with agents
3. **Agent mobility** — Agents are definitions, not processes; any worker can run any agent
4. **Result aggregation** — Distributed execution produces distributed artifacts; the Audit Logger aggregates

Architecture impact: The Job Queue and Execution Monitor need network-aware implementations, but the Kernel design stays unchanged.

### 8.5 Commercial LisaOS

The Kernel supports commercial deployment by:

1. **Multi-tenant job isolation** — Jobs carry a tenant ID; capabilities and context are scoped to the tenant
2. **Billing integration** — The cost tier in runtime definitions maps to billing SKUs
3. **API facade** — The future API (section 7.8) provides the commercial interface
4. **Observability SLAs** — Audit Logger produces tenant-scoped compliance records
5. **Custom agents** — The agent catalogue can be extended per tenant

Architecture impact: The Kernel remains the same; only the interfaces (API, billing, tenant isolation) need commercial wrappers.

---

## 9. Related Documents

| Document | Relationship |
|----------|-------------|
| `docs/LISAOS/MANIFEST.md` | LisaOS v3 architecture overview — Kernel is defined in context of this manifest |
| `docs/LISAOS/AGENTS.md` | Standard agent catalogue — Kernel dispatches to these agents |
| `docs/LISAOS/CAPABILITIES.md` | Capability definitions — Kernel resolves capabilities at route time |
| `docs/LISAOS/KERNEL_DECISIONS.md` | Architectural decisions made while designing the Kernel |
| `registry/routing-rules.yml` | Job type → agent → runtime mapping — Kernel reads at route time |
| `registry/runtimes.yml` | Runtime definitions — Kernel reads for health and selection |
| `jobs/queue.yml`, `active.yml`, `completed.yml` | Job state — Kernel orchestrates lifecycle |
| `bin/lisa-job-create.sh` | Job creation script — entry point for new work |
| `bin/lisa-route.sh` | Route resolver — current implementation of Runtime Resolver |
| `docs/LISAOS/REPOSITORY_CONSOLIDATION_REPORT.md` | Repository consolidation record |

---

## 10. Kernel Evolution

The Kernel is the permanent operating model for LisaOS v3. It evolves through:

1. **ADRs** — Architecture Decision Records capture any change to the Kernel design
2. **New job types** — Added to routing rules without changing the Kernel
3. **New capabilities** — Added to CAPABILITIES.md without changing the Kernel
4. **New runtimes** — Added to runtimes.yml and routing-rules.yml without changing the Kernel
5. **Stage additions** — New validation stages added to the pipeline without changing the Kernel

What does change the Kernel: changes to the job lifecycle, component responsibilities, or interface contracts. These require an ADR and manifest update.
