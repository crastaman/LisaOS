# LisaOS Repository Boundary Governance

**Status:** Active  
**Last updated:** 2026-07-02  
**Job ID:** LISAOS-REPOSITORY-BOUNDARY-RULE

This document defines permanent repository boundary rules for LisaOS and WBS. It is a governance rule for LisaOS, OpenClaw-assisted tasks, and all agents operating under Lisa Workflow.

---

## 1. Purpose

LisaOS and WBS are separate projects with separate repositories.

A documentation or implementation task must never silently write files into the wrong repository. Before any file creation, edit, move, implementation, documentation update, or generated artifact write, the agent must identify the target repository and confirm that the destination path belongs to that repository.

---

## 2. Repository Ownership

### 2.1 LisaOS Repository

**Repository:**

```text
~/Lisa
```

**Purpose:**

The LisaOS operating system.

**Owns:**

- LisaOS architecture
- Kernel
- Agent registry
- Capability registry
- Runtime registry
- OpenClaw integration
- Governance
- Memory system
- Security
- Workflow engine
- Future LisaOS source code

**Examples of LisaOS-owned paths:**

```text
docs/LISAOS/
registry/
runtime/
governance/
jobs/
memory/
skills/
core/
```

**Rule:** LisaOS documentation must never be written into WBS.

---

### 2.2 WBS Repository

**Repository:**

```text
~/Projects/WBS/healing-events-booking
```

**Purpose:**

Wellness Business Suite product.

**Owns:**

- Plugin code
- WBS documentation
- Sprint packets
- Technical debt
- QA reports
- Product architecture
- Business rules
- Release notes

**Examples of WBS-owned paths:**

```text
docs/IMPLEMENTATION/
docs/ARCHITECTURE/
reports/
admin/
includes/
assets/
```

**Rule:** WBS documentation must never be written into LisaOS unless it is explicitly LisaOS-related.

---

## 3. Mandatory Repository Boundary Check

Before every documentation or implementation task, the agent must complete this check:

1. **Identify the target repository.**
   - Is the task LisaOS governance/runtime/workflow work?
   - Is the task WBS product/plugin/business-rule work?

2. **Verify the current working directory.**
   - Confirm the active Git repository root.
   - Do not rely on chat history or assumed paths.

3. **Confirm the destination path.**
   - Confirm the requested output path is inside the target repository.
   - Confirm the path belongs to the project type being modified.

4. **Stop if the path belongs to another repository.**
   - Do not create the file.
   - Do not create a parallel directory to make the path work.
   - Do not silently reinterpret the path.
   - Request clarification from Roshan / Lisa Workflow.

---

## 4. Hard Rules

- Never silently create LisaOS files inside WBS.
- Never silently create WBS files inside LisaOS.
- Never use WBS as the default workspace for LisaOS governance documents.
- Never use LisaOS as the default workspace for WBS product documents.
- Never move existing files between LisaOS and WBS automatically.
- Never modify WBS production code as part of a LisaOS governance task.
- If a request names a path that conflicts with repository ownership, stop and ask for clarification.

---

## 5. OpenClaw Agent Repository Selection Guidance

OpenClaw agents operating under Lisa Workflow must treat repository selection as a preflight gate.

### 5.1 Target Classification

| Task type | Target repository |
|----------|-------------------|
| LisaOS architecture | `~/Lisa` |
| LisaOS Kernel | `~/Lisa` |
| LisaOS agent registry | `~/Lisa` |
| LisaOS capability registry | `~/Lisa` |
| LisaOS runtime registry | `~/Lisa` |
| LisaOS governance | `~/Lisa` |
| LisaOS workflow engine | `~/Lisa` |
| LisaOS memory system | `~/Lisa` |
| OpenClaw integration policy | `~/Lisa` |
| WBS plugin code | `~/Projects/WBS/healing-events-booking` |
| WBS sprint packet | `~/Projects/WBS/healing-events-booking` |
| WBS QA report | `~/Projects/WBS/healing-events-booking` |
| WBS product architecture | `~/Projects/WBS/healing-events-booking` |
| WBS business rule | `~/Projects/WBS/healing-events-booking` |
| WBS release note | `~/Projects/WBS/healing-events-booking` |

### 5.2 Preflight Decision Rule

```text
If task concerns LisaOS itself:
    target repo = ~/Lisa
elif task concerns WBS product/runtime/code/business rules:
    target repo = ~/Projects/WBS/healing-events-booking
else:
    ask for clarification before writing files
```

### 5.3 Stop Conditions

An agent must stop and request clarification when:

- The requested output path is in WBS but the task is LisaOS governance or architecture.
- The requested output path is in LisaOS but the task is WBS product work.
- The current working directory does not match the target repository.
- The target repository cannot be verified with Git.
- The requested destination path is ambiguous.
- The task asks for cross-repository movement without explicit approval.

---

## 6. Validation Requirements

For every future job that writes files, the completion report must confirm:

- Target repository identified.
- Git repository root verified.
- Destination path confirmed.
- No files written into the wrong repository.

Minimum validation output:

```text
Repository boundary check:
- Target repository: <repo>
- Git root: <verified-root>
- Destination path: <path>
- Boundary result: PASS
```

---

## 7. Boundary Examples

### 7.1 Correct: LisaOS Kernel update

```text
Task: Update Kernel governance rules
Target repository: ~/Lisa
Destination: docs/LISAOS/KERNEL.md
Result: allowed
```

### 7.2 Incorrect: LisaOS Kernel inside WBS

```text
Task: Update Kernel governance rules
Target repository should be: ~/Lisa
Requested destination: ~/Projects/WBS/healing-events-booking/docs/LISAOS/KERNEL.md
Result: STOP — request clarification
```

### 7.3 Correct: WBS QA report

```text
Task: Write QA report for appointment booking regression
Target repository: ~/Projects/WBS/healing-events-booking
Destination: reports/wbs/qa-*.json or docs/QA/reports/*.md
Result: allowed
```

### 7.4 Incorrect: WBS business rules inside LisaOS

```text
Task: Update coupon business rules for WBS
Target repository should be: ~/Projects/WBS/healing-events-booking
Requested destination: ~/Lisa/docs/BUSINESS_RULES/coupons.md
Result: STOP — request clarification
```

---

## 8. Governance Status

This rule is part of LisaOS governance. Any change to repository ownership, boundary rules, or stop conditions requires a LisaOS governance review and human approval.
