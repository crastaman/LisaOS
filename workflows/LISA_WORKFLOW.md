# Lisa Workflow

## Purpose

The Lisa Workflow is the permanent governance model for WBS development.

Lisa defines HOW work flows between people and AI runtimes.

The workflow is independent of any specific AI model.

Individual runtimes may change over time without changing the workflow.

---

# Core Principle

Roles are permanent.

Runtimes are replaceable.

The workflow governs the work.

The runtime executes the work.

---

# Chain of Operations

Roshan
(Product Owner)

↓

GPT
(Architecture • Governance • Strategy • Engineering Review)

↓

Lisa
(Planner • Capability Router • Job Manager)

↓

Selected Runtime

↓

Execution

↓

QA / Engineering Report

↓

GPT Review

↓

Roshan Approval

---

# Governance Rules

- Lisa supports the workflow.
- Lisa never replaces Roshan's approval.
- GPT remains architecture authority.
- Runtime selection is based on capability, availability and limits.
- The workflow never changes because a runtime becomes unavailable.

---

# Runtime Types

## QA Runtime

Responsibilities

- Browser automation
- Playwright
- Screenshots
- Videos
- Traces
- Console logs
- Technical investigation
- QA reports

Current Preferred Runtime

- OpenClaw

Alternative QA runtimes may be substituted without changing the workflow.

---

## Engineering Runtime

Responsibilities

- Source code implementation
- Bug fixes
- Features
- Refactoring
- Tests
- Documentation updates

Possible Runtimes

- Codex
- Claude Code
- Qwen Code
- Future engineering models

Lisa selects the best available runtime.

The engineering packet is identical regardless of runtime.

---

## Analysis Runtime

Responsibilities

- Architecture analysis
- Large repository inspection
- Local reasoning
- Research

Possible Runtimes

- Ollama
- Future local models

---

# Runtime Selection

Lisa selects runtimes according to:

1. Capability
2. Availability
3. Current usage limits
4. Cost efficiency
5. User preference (when explicitly specified)

If one runtime becomes unavailable, Lisa reassigns the same job packet to another suitable runtime.

The workflow never changes.
Only the runtime changes.

---

# Runtime Status

Lisa routes jobs based on runtime availability.

A runtime may become temporarily unavailable due to:

- usage limits
- API limits
- maintenance
- local outages

This does not interrupt the Lisa Workflow.

Lisa reassigns the job to the next suitable runtime where appropriate.

---

# Job Types

Lisa routes work using standardized job packets.

Examples:

- QA Job
- Engineering Job
- Analysis Job
- Review Job

Each job receives:

- Job ID
- Objective
- Constraints
- Acceptance Criteria
- Deliverables

Job packets are runtime-agnostic.

The same job packet should execute correctly regardless of whether the assigned runtime is Codex, Claude Code, Qwen Code, or a future engineering runtime.

The runtime executes the packet without redefining its scope.

---

# Standard Development Cycle

1. GPT defines architecture.
2. Lisa prepares the job.
3. Runtime executes.
4. QA evidence is collected.
5. GPT reviews findings.
6. Roshan approves.
7. Engineering runtime implements.
8. OpenClaw retests.
9. GPT signs off.

---

# QA Philosophy

OpenClaw is the preferred QA Runtime.

Its responsibilities are:

- browser automation
- end-to-end testing
- technical investigation
- evidence collection
- regression testing

OpenClaw never implements production code.

Each QA job must produce:

- PASS/FAIL report
- Screenshots
- Traces
- Videos (where available)
- Console errors
- Root cause analysis
- Recommended engineering packet

QA investigates.

QA does not fix code.

QA produces evidence.

Engineering produces fixes.

These responsibilities must remain separate.

---

# QA Batch Execution

QA work should be organised into numbered jobs:

QA-001
QA-002
QA-003
...

Each job should:

- have one objective
- produce its own report
- produce screenshots
- produce traces
- stop at first blocker
- continue to the next independent job

Large QA efforts should finish with a combined batch summary and prioritised defect list.

---

# Checkpointing

Each completed QA job is considered complete once:

- report is written
- screenshots are saved
- evidence is archived

If execution stops due to limits or runtime failure, the next session resumes from the first incomplete QA job.

Previously completed jobs must not be repeated unless explicitly requested.

---

# Engineering Philosophy

Engineering runtimes implement only approved work.

Engineering must:

- follow the engineering packet
- make the smallest safe change
- avoid architectural drift
- preserve backwards compatibility where appropriate

Engineering packets must include:

- objective
- root cause
- evidence
- affected files
- constraints
- acceptance criteria
- regression risks
- retest instructions

---

### Token Budget Mode

Default mode for all Lisa Workflow jobs.

Rules:

1. Read only the documents explicitly referenced by the current job.
2. Do not reload `LISA_WORKFLOW.md` if already loaded in the current session.
3. Search `DEFECT-BACKLOG.md` for the relevant defect only.
4. Do not scan the repository unless required.
5. Reuse cached sprint context.
6. Return concise responses.
7. Complete one job, then end the session.
8. Start a fresh session for the next job where practical.