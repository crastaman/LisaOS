# LisaOS Artifact Lifecycle

**Job ID:** L005-L007-LISAOS-ORCHESTRATION-DESIGN-STUDY  
**Repository:** `~/Lisa`  
**Scope:** Artifact lifecycle, storage layout, archival policy, ownership, and versioning rules.  
**Runtime behaviour:** Unchanged. Documentation only.

---

## 1. Purpose

This document defines the complete lifecycle of artifacts in LisaOS — from creation through validation, publication, archival, and deletion. It extends the artifact taxonomy defined in L006 with operational lifecycle rules.

---

## 2. Artifact Lifecycle States

### 2.1 State Machine

```
                  ┌─────────────────────────────────────────────┐
                  │              ARTIFACT LIFECYCLE              │
                  └─────────────────────────────────────────────┘

  DRAFT ────────────────────────────────────────────────────────────┐
    │  Agent is writing the artifact                                │
    │  Not yet ready for reading by other agents                    │
    ▼                                                               │
  PENDING_VALIDATION                                                 │
    │  Agent has signalled completion                               │
    │  Schema validation runs                                        │
    ├── VALIDATION_PASSED ──────────────────────────────────────────┤
    │    Artifact is structurally valid                             │
    │    Moves to VALIDATED state                                     │
    ▼                                                               │
  VALIDATED                                                          │
    │  Artifact is complete and valid                               │
    │  Available for reading by other agents and pipeline stages      │
    ├── PUBLISHED (for artifacts that need explicit publication) ───┤
    │    Artifact is acknowledged in the job record                 │
    │    Immutable after this point                                 │
    ▼                                                               │
  PUBLISHED ────────────────────────────────────────────────────────┤
    │  Final state for most artifacts                               │
    │  Cannot be modified                                            │
    │  May be SUPERSEDED by a newer version                           │
    │  After archival period: moves to ARCHIVED                       │
    ▼                                                               │
  ARCHIVED                                                           │
    │  Moved to long-term storage                                   │
    │  Not in active job directories                                │
    │  Still readable for audit and reference                         │
    ▼                                                               │
  DELETED (after retention period)                                   │
    │  No longer stored anywhere                                    │
    │  Metadata record kept in audit index                           │
    └───────────────────────────────────────────────────────────────┘

  Alternative paths:

  VALIDATION_FAILED ──► REJECTED ──► DRAFT (revision by same agent)
  PUBLISHED ──► SUPERSEDED (when a newer version is published)
  PUBLISHED ──► ARCHIVED ──► DELETED
```

### 2.2 State Transitions

| From | To | Trigger | Notes |
|------|----|---------|-------|
| DRAFT | PENDING_VALIDATION | Agent signals completion | Artifact is saved to disk |
| PENDING_VALIDATION | VALIDATED | Schema validation passes | Automated check |
| PENDING_VALIDATION | REJECTED | Schema validation fails | Returned to writer agent |
| VALIDATED | PUBLISHED | Acknowledged in job record | Immutable from this point |
| PUBLISHED | SUPERSEDED | Newer version published | Old version preserved in job record |
| PUBLISHED | ARCHIVED | Job is completed and archived | Moved to long-term storage |
| ARCHIVED | DELETED | Retention period expires | Metadata preserved |
| REJECTED | DRAFT | Returned to writer agent | Agent fixes and resubmits |

---

## 3. Storage Layout

### 3.1 Active Jobs

```
jobs/active/<job_id>/
  ├── job-packet.yml                 # Immutable after dispatch
  ├── context-packet.yml             # Immutable after dispatch
  ├── routing-decision.yml           # Immutable after dispatch
  ├── implementation-report.yml      # Created during execution
  ├── decision-log.yml               # Incrementally written during execution
  ├── review-report.yml              # Created during review (if applicable)
  ├── qa-report.yml                  # Created during QA (if applicable)
  ├── approval-packet.yml            # Created at approval stage
  └── output/                        # Raw output (patches, screenshots, test results)
      ├── patch.diff
      ├── screenshots/
      ├── test-output.log
      └── errors.log
```

### 3.2 Completed Jobs

```
jobs/completed/<job_id>/
  ├── job-packet.yml                 # Copy from active
  ├── context-packet.yml             # Copy from active
  ├── routing-decision.yml           # Copy from active
  ├── implementation-report.yml      # Copy from active
  ├── decision-log.yml               # Copy from active
  ├── review-report.yml              # Copy from active (if created)
  ├── qa-report.yml                  # Copy from active (if created)
  ├── approval-packet.yml            # Copy from active
  └── output/                        # Copy from active
      └── ...
```

### 3.3 Audit Archive

```
jobs/audit/<year>/<month>/
  ├── <job_id>/
  │   ├── job-packet.yml
  │   ├── decision-log.yml
  │   ├── approval-packet.yml
  │   └── output/
  └── index.yml                       # Master index of archived jobs
```

### 3.4 Release Artifacts

```
jobs/release/<release_id>/
  ├── release-report.yml
  └── included-jobs/
      ├── <job_id>/
      │   └── approval-packet.yml     # Copy of approval status for each job
      └── ...
```

---

## 4. Lifecycle Rules

### 4.1 Immutability

**Rule:** Once an artifact reaches `PUBLISHED` state, it is immutable.

**Enforcement:**
- Files are written once and not modified.
- If an update is needed, a new version is created.
- The old version is marked `SUPERSEDED` but preserved.
- File permissions may be set to read-only after publication.

### 4.2 Versioning

- Each artifact type has a `version` field (semantic: Major.Minor).
- A major version increment means the schema has changed (required fields added or removed).
- A minor version increment means optional fields were added.
- Artifacts of the same type with different major versions may not be fully compatible.

### 4.3 Ownership

| Artifact | Owner | Can Read | Can Write |
|----------|-------|----------|-----------|
| Job Packet | Planner | All agents | Planner only |
| Context Packet | Context Loader | All agents | Context Loader only |
| Routing Decision | Router | All agents | Router only |
| Implementation Report | Builder agent | All agents | Builder agent only |
| Review Report | Reviewer agent | All agents | Reviewer agent only |
| QA Report | QA agent | All agents | QA agent only |
| Decision Log | Any agent | All agents | Creating agent (appends only) |
| Approval Packet | Approval Gateway | All agents + Human | Approval Gateway only |
| Release Report | Release agent | All agents + Human | Release agent only |

### 4.4 Retention

| Artifact | Active Retention | Archived Retention | Total Retention |
|----------|-----------------|-------------------|-----------------|
| Job Packet | Job duration | 1 year | 1 year + job duration |
| Context Packet | Job duration | 1 year | 1 year + job duration |
| Routing Decision | Job duration | 1 year | 1 year + job duration |
| Implementation Report | Job duration | 2 years | 2 years + job duration |
| Decision Log | Job duration | 3 years | 3 years + job duration |
| Review Report | Job duration | 2 years | 2 years + job duration |
| QA Report | Job duration | 2 years | 2 years + job duration |
| Approval Packet | Job duration | 3 years | 3 years + job duration |
| Release Report | Indefinite | Indefinite | Indefinite |
| Raw output (diffs, screenshots) | Job duration | 90 days | Job duration + 90 days |

### 4.5 Archival Trigger

Artifacts are archived when:

1. **Job completed:** Move from `jobs/active/<job_id>/` to `jobs/completed/<job_id>/` immediately on completion.
2. **Job rejected:** Move to `jobs/completed/<job_id>/` with `status: rejected` in the job packet.
3. **Job abandoned:** If a job remains in `active` state with no activity for >24 hours, it is moved to `completed/<job_id>/` with `status: abandoned`.
4. **Audit archival:** After the active retention period, move from `jobs/completed/<job_id>/` to `jobs/audit/<year>/<month>/<job_id>/`.

### 4.6 Deletion Trigger

Artifacts are deleted when:

1. The total retention period expires.
2. The metadata record is kept in the audit index (index.yml) for searchability.
3. Deletion is logged in the system audit.

---

## 5. Cross-Job Artifact Sharing

### 5.1 When Artifacts Cross Job Boundaries

Artifacts may be read by jobs other than their creating job in these scenarios:

- **Release assembly:** Release agent reads approval packets from multiple jobs.
- **Memory curation:** Memory agent reads decision logs from completed jobs.
- **Regression baseline:** QA agent reads previous QA reports to compare results.
- **Governance audit:** Governance pipeline reads routing decisions and capability envelopes.

### 5.2 Sharing Rules

1. **Read-only access:** Cross-job artifact access is always read-only.
2. **Referenced by ID:** Artifacts are referenced by job ID + artifact type, not by file path.
3. **Explicit in scope:** The referencing job's context packet must list which external artifacts are needed.
4. **Immutable source:** The source artifacts must be in `PUBLISHED` or `ARCHIVED` state.

---

## 6. Artifact Naming Conventions

| Convention | Rule | Example |
|-----------|------|---------|
| File names | lowercase with hyphens | `implementation-report.yml` |
| Job ID format | `<project-code>-<sequence>-<description>` | `S014-PRACTITIONER-BACKEND-V2` |
| Release ID format | `RELEASE-YYYY-MM-DD` | `RELEASE-2026-07-03` |
| Version suffix | `-v<major>` for superseded versions | `approval-packet-v1.yml` |
| Output files | Descriptive, lowercase | `practitioner-model-diff.patch` |

---

## 7. Lifecycle Diagram (Complete View)

```
JOB CREATED
    │
    ▼
JOB QUEUED
    │  Job Packet → DRAFT → VALIDATED → PUBLISHED
    ▼
JOB DISPATCHED
    │  Context Packet → DRAFT → VALIDATED → PUBLISHED
    │  Routing Decision → DRAFT → VALIDATED → PUBLISHED
    ▼
JOB EXECUTING
    │  Decision Log → DRAFT → VALIDATED (incremental)
    │  Implementation Report → DRAFT → VALIDATED → PUBLISHED
    ▼ (if applicable)
REVIEW
    │  Review Report → DRAFT → VALIDATED → PUBLISHED
    ▼ (if applicable)
QA
    │  QA Report → DRAFT → VALIDATED → PUBLISHED
    ▼
APPROVAL
    │  Approval Packet → DRAFT → VALIDATED → PUBLISHED
    │  (human marks APPROVED or REJECTED)
    ▼
JOB COMPLETED
    │  All artifacts → PUBLISHED → ARCHIVED (per retention policy)
    │  Job → `completed/<job_id>/`
    ▼ (if release-scoped)
RELEASE
    │  Release Report → DRAFT → VALIDATED → PUBLISHED
    │  Release artifacts → `release/<release_id>/`
    ▼
AUDIT ARCHIVE
    │  After retention period → `audit/<year>/<month>/<job_id>/`
    ▼
DELETION
    │  After total retention expires
    │  Metadata preserved in audit index
```

---

## Related Documents

- `docs/LISAOS/L006_AGENT_COMMUNICATION_ARCHITECTURE.md` — Artifact taxonomy and schemas
- `docs/LISAOS/L007_OPENCLAW_ORCHESTRATION_ARCHITECTURE.md` — Artifact-driven orchestration
- `docs/LISAOS/KERNEL.md` — Kernel architecture (sections 3.11-3.12 Audit Logger, Memory Writer)
