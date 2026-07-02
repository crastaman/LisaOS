# LisaOS Context Management

**Job ID:** L005-L007-LISAOS-ORCHESTRATION-DESIGN-STUDY  
**Repository:** `~/Lisa`  
**Scope:** Context loading, context budgets, context compaction, session rotation, artifact-first workflows.  
**Runtime behaviour:** Unchanged. Documentation only.

---

## 1. Purpose

Context management is the most impactful operational practice for AI-assisted development. Every token of context comes at a cost — in latency, in cost per job, and in cognitive load on the model. This document captures lessons learned during WBS development and formalises best practices for LisaOS.

---

## 2. First Principles

### 2.1 Why Context Matters

Each token in the context window:

- **Increases latency** — Models process linearly through the context window.
- **Increases cost** — Tokens are billed per-thousand for both input and output.
- **Reduces signal-to-noise ratio** — Important instructions buried in irrelevant history degrade output quality.
- **Clogs the "attention" budget** — Models have finite attention; irrelevant tokens compete with relevant ones.

### 2.2 The Diminishing Returns Curve

```
Quality
  ↑
  |   ████████████████░░░░░░           High value zone
  |   ██████████████░░░░░░░░░          (core context: instructions, schema, examples)
  |   ██████████░░░░░░░░░░░░░          Medium value zone
  |   ██████░░░░░░░░░░░░░░░░░░         (reference docs, business rules)
  |   ██░░░░░░░░░░░░░░░░░░░░░░░        Low value zone
  |   ░░░░░░░░░░░░░░░░░░░░░░░░░░       Waste zone (chat history, irrelevant logs)
  └──────────────────────────────────► Tokens
```

**Lesson:** 80% of useful context fits in 20% of the budget. The key is identifying that 20%.

### 2.3 Core Principles

1. **Documentation is memory, not chat history.**
2. **Context is a limited resource — budget it explicitly.**
3. **Every token must earn its place in the context window.**
4. **Small, focused sessions beat large, general sessions.**
5. **Artifact-first workflows eliminate the need for conversational context.**

---

## 3. Context Budgets

### 3.1 Per-Job-Type Budgets

| Job Type | Context Budget | Core Content | Optional Content |
|----------|---------------|--------------|------------------|
| ENGINEERING | 64K tokens | Job packet, target files, architecture adjacencies | Business rules, historical reports |
| PLANNING | 128K tokens | Full context — job packet, all docs, memory | Conversation (truncated to 4K) |
| REVIEW | 32K tokens | Implementation report, job packet | Architecture docs (relevant sections) |
| QA_BROWSER | 24K tokens | QA scope, test definitions, environment info | Implementation report |
| GOVERNANCE | 16K tokens | Job artifacts (reports, validation results) | Conversation (not needed) |
| DOCS | 32K tokens | Documentation context, style guide, examples | Historical reports |
| SECURITY | 48K tokens | Code changes, security rules, threat models | Business rules |
| RELEASE | 24K tokens | Job statuses, approval states, release notes | Historical reports |

### 3.2 Budget Enforcement

- **Hard cap:** The context budget is a hard cap. If total assembled context exceeds the budget, low-priority sources are truncated.
- **Truncation order (least important first):**
  1. Conversation context
  2. Historical reports
  3. Architecture documents (non-adjacent)
  4. Business rules (if not directly relevant)
  5. LisaOS documentation (general sections only)
- **Warning threshold:** If context exceeds 80% of budget, log a warning with token breakdown.

### 3.3 Budget Negotiation

Agents can request additional context budget, but:

1. The request must be specific ("I need the migration history for practitioner model").
2. The request must include the source reference.
3. The Context Loader evaluates and includes if source is available and budget remaining.
4. The request is logged in the decision log.

---

## 4. Context Assembly

### 4.1 Priority Chain

Per KERNEL.md and KERNEL_DECISIONS.md ADR-K002, the Context Loader uses a fixed priority chain:

```
Highest priority ────────────────────────────────────────────── Lowest priority
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Job     │ │ Current │ │ LisaOS  │ │ Business │ │Arch.    │ │Historical│ │Convo.   │
│  Packet  │ │ Repo    │ │ Docs    │ │ Rules    │ │ Docs    │ │ Reports  │ │Context  │
│ (always  │ │ (HEAD)  │ │(MANIFEST│ │(BUSINESS │ │(ADRs,   │ │(prev.    │ │(tempor- │
│  include)│ │         │ │ KERNEL) │ │_RULES/) │ │maps)    │ │runs)     │ │ary)     │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### 4.2 Selective Inclusion

Rather than dumping entire files into context, the Context Loader uses selective inclusion:

```yaml
# Instead of including the full KERNEL.md (15K tokens):
selective_inclusion:
  - source: docs/LISAOS/KERNEL.md
    sections:
      - "3.5 Runtime Resolver"      # Relevant to this job
      - "3.6 Agent Dispatcher"       # Relevant to this job
    excluded:
      - "3.1 Job Queue"              # Not relevant (job already queued)
      - "3.8 Validation Pipeline"    # Not relevant (planning phase)
    token_count: 2048                # Instead of 15000
```

Selective inclusion is guided by the job's `context_files` field and the job type's known interests.

### 4.3 Deduplication

The Context Loader detects and removes duplicate content:

- **Exact duplicates:** Same file referenced from multiple context sources.
- **Semantic duplicates:** Same information expressed in different files (e.g., an ADR's decision also documented in KERNEL_DECISIONS.md).
- **Overlapping content:** Two files that cover the same architecture area.

When duplicates are detected, the higher-priority source is retained and the duplicate is logged.

---

## 5. Context Compaction

### 5.1 Compaction Techniques

| Technique | Token Savings | Risk | When to Use |
|-----------|--------------|------|-------------|
| Summarisation | 60-80% | Loss of nuance | Conversation history, verbose reports |
| Selective inclusion | 40-60% | Missing context | Large documents where only sections are relevant |
| Deduplication | 5-20% | None | Always |
| Reference shortening | 5-10% | None | Always |
| Outdated exclusion | 10-30% | Missing recent changes | Documentation with multiple versions |
| Example removal | 10-40% | Harder to understand patterns | When patterns are well-known |
| Code diff instead of full file | 50-80% (code) | Lack of surrounding context | When only the changed function matters |

### 5.2 Summarisation Best Practice

Conversation context should be summarised, not dumped:

```yaml
# Bad — 12K tokens of raw chat
conversation: |
  [12:01] Roshan: Can we refactor the practitioner model?
  [12:02] Agent: Let me check the current structure...
  [12:05] Agent: I found the model at /app/Models/Practitioner.php
  ...

# Good — 800 token summary
conversation_summary:
  topic: "Practitioner model refactoring"
  key_decisions:
    - "Split Practitioner model into Practitioner + PractitionerProfile"
    - "Move address fields to PractitionerAddress model"
    - "Keep migration backward-compatible for 30 days"
  unresolved_questions:
    - "Should PractitionerProfile be nullable for existing practitioners?"
  rejected_options:
    - "Single table with JSON columns (ruled out for query performance)"
  source_duration: 12 minutes
  summary_tokens: 800
  original_tokens: 12000
```

### 5.3 Automatic Compaction Rules

| Rule | Trigger | Action |
|------|---------|--------|
| Conversation > 4K tokens | At context assembly | Summarise to 1K tokens |
| Report > 8K tokens | At context assembly | Include summary section only |
| Full document > 16K tokens | At context assembly | Selective inclusion of relevant sections |
| Multiple references to same topic | At context assembly | Deduplicate, retain highest-priority |
| File modified > 30 days ago | At context assembly | Mark as "possibly stale" and deprioritise |

---

## 6. Session Rotation

### 6.1 Fresh Session Strategy

**Rule:** Every job, sub-job, validation stage, and governance audit runs in a fresh session.

**Benefits:**
- Zero context bleed between unrelated work
- Deterministic starting state for every execution
- Session length matches job length — no accumulated bloat
- Failed sessions don't pollute future work

### 6.2 Session Rotation Triggers

| Trigger | Action | Rationale |
|---------|--------|-----------|
| Job completed | End session | Natural endpoint |
| Job failed non-recoverable | End + escalate | Save partial output, release resources |
| Validation stage starts | New session | Clean context for reviewer |
| Context budget at 90% | Warn agent | May choose to checkpoint + rotate |
| Context budget exhausted | Rotate session | Checkpoint progress, start fresh |
| >10 minutes idle | Consider rotation | If no progress, might be context-cramped |
| Runtime changes | Rotate session | Different runtime = different session |
| Human escalation opened | Keep alive | Don't lose context before human responds |

### 6.3 Checkpoint and Rotate

When rotating sessions mid-job:

1. **Checkpoint:** Save all current work to `jobs/active/<job_id>/`
   - Patches, diffs, partial reports
   - Decision log entries to date
   - Current status field
2. **Summarise:** Produce a checkpoint summary (max 1K tokens)
   - What was accomplished
   - What remains
   - Any blockers or decisions made
3. **Rotate:** End current session
4. **Resume:** Start new session with:
   - Original job packet + context packet
   - Checkpoint summary (replaces old conversation context)
   - Remaining context budget (recalculated)

---

## 7. Artifact-First Workflows

### 7.1 The Artifact-First Principle

**Artifacts replace chat history as the carrier of context between sessions.**

Every handoff between agents, every stage transition, every checkpoint is documented as an artifact. No information is transferred through conversational context.

### 7.2 What Artifacts Carry

| Information | Where It Lives | How It Transfers |
|-------------|---------------|------------------|
| Job definition | Job Packet | File in `jobs/queue/<job_id>/` |
| Execution context | Context Packet | File in `jobs/active/<job_id>/` |
| Decisions made | Decision Log | Incrementally written file |
| Implementation output | Implementation Report | Written at completion |
| Review findings | Review Report | Written at completion |
| QA results | QA Report | Written at completion |
| Approval state | Approval Packet | Updated by gateway |
| Release notes | Release Report | Written at release |

### 7.3 Why Artifact-First Works

| Problem | Chat-History Approach | Artifact-First Approach |
|---------|----------------------|------------------------|
| Session restart loses state | Cannot recover without replaying | All state in files; read and resume |
| Token bloat from conversation | Every message adds tokens | Artifacts are compact and structured |
| Cross-agent handoff | Must share session or pass transcript | Write artifact → read artifact |
| Audit trail | "Check the conversation log" | Schematised, searchable records |
| Determinism | No — depends on conversation flow | Yes — same artifacts = same context |

---

## 8. Repository Documentation as Durable Memory

### 8.1 Memory Hierarchy

```
TEMPORARY (Ephemeral)
  ├── Chat history              → Summarised or discarded after session
  ├── Session logs              → Available for short-term reference
  ├── Agent scratch notes       → Discarded after job completion
  │
WORKING (Job-scoped)
  ├── Decision log              → Immutable artifact (job record)
  ├── Implementation report     → Immutable artifact
  ├── Review report             → Immutable artifact
  │
DURABLE (Repository-scoped)
  ├── ADRs                      → Architecture decisions (docs/ADR/)
  ├── Business rules            → Domain knowledge (docs/BUSINESS_RULES/)
  ├── Architecture docs         → System design (docs/ARCHITECTURE/)
  ├── LisaOS docs               → OS design (docs/LISAOS/)
  └── Memory notes              → Curated knowledge (MEMORY.md, memory/*.md)
```

### 8.2 What Belongs in Durable Memory

| Content Type | Write To | When |
|-------------|----------|------|
| Architecture decision | docs/ADR/ | When a significant choice is made |
| Business rule discovered | docs/BUSINESS_RULES/ | When implementation reveals domain logic |
| System design insight | docs/ARCHITECTURE/ | When understanding deepens |
| Operational lesson | docs/LESSONS_LEARNED/ | After a failure or significant mistake |
| Quality baseline update | docs/QA/QA_MATRIX.md | After QA reveals new patterns |
| Daily context | memory/YYYY-MM-DD.md | End of day, or after significant events |
| Long-term context | MEMORY.md | Periodic distillation from daily notes |

### 8.3 What Does Not Belong in Memory

- Raw conversation history (summarise or discard)
- Reproducible test outputs (re-run to get fresh results)
- Temporary debugging state (diagnose, document the lesson, discard the state)
- Implementation details that are already in Git (Git is authoritative for code)

---

## 9. Avoiding Transcript Bloat

### 9.1 The Bloat Sources

| Source | Typical Token Cost | Prevention |
|--------|-------------------|------------|
| Full file reads into conversation | 2K-50K per read | Artifact-first: reference file paths |
| Repeated tool outputs | 1K-10K per repeat | Suppress verbose tool output in agent prompts |
| Excessive conversation turns | 500-2K per turn | Session rotation: don't let sessions run long |
| Large error stacks | 2K-20K | Capture to file, only include summary in context |
| Agent self-review loops | 5K-50K | Define clear completion criteria |

### 9.2 Transcript Hygiene Rules

1. **Reference files, don't re-read them into context.** If an agent already read a file, reference it by path rather than displaying its contents again.

2. **Capture errors to files.** Console errors go to `jobs/active/<job_id>/output/errors.log`. Only the error summary goes into context.

3. **Prefer structured data over prose.** A YAML decision log is more compact and more parseable than a paragraph describing the same decision.

4. **Cap conversation turns.** If a job requires more than 10 conversational turns, it should be broken into sub-jobs or re-planned.

5. **End sessions decisively.** Don't let an agent "stick around" after a job completes to answer follow-ups. Create a new job for follow-ups.

---

## 10. Agent Context Budgets

### 10.1 Budget Allocation

Each agent has a total context budget for its session. This is allocated across:

| Allocation | Share | Purpose |
|-----------|-------|---------|
| Core identity | 2K tokens | Agent IDENTITY.md, SOUL.md, TOOLS.md |
| Job context | 60% of remaining | Job packet, context packet, repository files |
| Capability envelope | 1K tokens | Allowed/prohibited capabilities, policy injection |
| Output requirements | 1K tokens | Expected artifacts, schema references |
| Agent scratch space | 20% of remaining | For the agent's own working context |

### 10.2 Budget Monitoring

- The agent receives its initial budget with the context packet.
- The agent is responsible for tracking its own consumption.
- If the agent exceeds its budget, it should request a checkpoint-and-rotate.

---

## 11. Weaknesses and Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Context budget too small for complex jobs | Medium | Default budgets are guidance; packet can override |
| Summarisation loses critical nuance | Medium | Summaries should include "key decisions" and "unresolved questions" explicitly |
| Selective inclusion misses relevant sections | Low | Agent can request additional sections from Context Loader |
| Session rotation overhead | Low | Rotations are rare (when budget exhausted). Checkpoint is lightweight. |
| Memory never gets curated | Medium | Schedule a weekly memory curation job |

---

## Related Documents

- `docs/LISAOS/L007_OPENCLAW_ORCHESTRATION_ARCHITECTURE.md` — Context loading in orchestration (sections 4-5)
- `docs/LISAOS/LISAOS_TOKEN_EFFICIENCY_GUIDE.md` — Token efficiency best practices
- `docs/LISAOS/LISAOS_ARTIFACT_LIFECYCLE.md` — Artifact lifecycle and storage
- `docs/LISAOS/KERNEL.md` — Kernel architecture (section 3.3 Context Loader)
- `docs/LISAOS/KERNEL_DECISIONS.md` — ADR-K002 (Context Priority Chain)
- `docs/LISAOS/MANIFEST.md` — LisaOS v3 architecture (Documentation-first principle)
