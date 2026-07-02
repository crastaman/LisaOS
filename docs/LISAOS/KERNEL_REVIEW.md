# LisaOS Kernel Architecture Review

**Job ID:** LISAOS-KERNEL-ARCHITECTURE-REVIEW  
**Reviewer:** Lisa Workflow architecture review  
**Status:** Review complete — recommendations only  
**Date:** 2026-07-02  
**Scope:** Documentation review only; no implementation changes.

Reviewed documents:

- `docs/LISAOS/KERNEL.md`
- `docs/LISAOS/KERNEL_DECISIONS.md`
- `docs/LISAOS/MANIFEST.md`
- `docs/LISAOS/AGENTS.md`
- `docs/LISAOS/CAPABILITIES.md`

---

## Executive Summary

The Kernel document is directionally strong and establishes the right architecture principles: model independence, job lifecycle discipline, route-time capability resolution, human governance, validation gates, and durable documentation as truth.

However, the review found several important issues before treating the Kernel as fully authoritative:

1. **Architecture stack inconsistency:** `KERNEL.md` introduces `Lisa Workflow → LisaOS Kernel → OpenClaw`, but `MANIFEST.md` still says `Lisa Workflow → OpenClaw` directly.
2. **Capability taxonomy drift:** `AGENTS.md`, `CAPABILITIES.md`, and `KERNEL.md` use overlapping but non-identical capability names.
3. **Queue/runtime timing conflict:** `KERNEL.md` says `selected_runtime` is resolved at queue time, while ADR-K003 and ADR-K004 imply route-time resolution.
4. **Approval semantics conflict:** Human approval is final authority, but `AUTOMATIC` approval for docs/analysis/memory could conflict with governance expectations.
5. **Git-as-audit is overstated:** Git is useful for history, but not sufficient for enterprise audit, mutable metadata, or tamper-evident operations.
6. **OpenClaw responsibility boundary is underspecified:** Kernel, Scheduler, OpenClaw, Capability Resolver, and Agent Dispatcher responsibilities overlap.
7. **Future scaling concerns are acknowledged but not contractually solved:** Distributed workers, cloud execution, queue locking, artifact sync, and tenant isolation need stronger boundary definitions.

Recommendation: keep the Kernel as the v3 foundation, but treat this review as a required follow-up packet before implementation or operational enforcement.

---

## 1. Internal Inconsistencies

### 1.1 Architecture stack mismatch between Kernel and Manifest

**Finding:**

`MANIFEST.md` defines:

```text
Lisa Workflow (governance)
    │
    OpenClaw (orchestration)
```

`KERNEL.md` defines the Kernel as the execution model governing every job and later implies:

```text
Lisa Workflow → LisaOS Kernel → OpenClaw
```

**Risk:** High.

The Kernel is introduced as a first-class architectural layer, but the Manifest does not include it. This creates ambiguity about whether the Kernel governs OpenClaw or is merely documentation describing OpenClaw behaviour.

**Recommendation:**

Add a follow-up documentation task to align the top-level architecture diagram across `MANIFEST.md`, `README.md`, and `KERNEL.md`. The recommended hierarchy is:

```text
Lisa Workflow (governance)
    │
LisaOS Kernel (execution model / policy)
    │
OpenClaw (orchestration engine)
    │
Agents + Runtimes + Capabilities
```

Do not make the Manifest change inside this review job; track it as a recommendation.

---

### 1.2 Runtime selection timing conflict

**Finding:**

`KERNEL.md` Job Queue fields say:

> `selected_runtime` — Runtime resolved by the Scheduler at queue time

But ADR-K003 says capabilities are resolved at route time, and ADR-K004 says runtime resolution uses health checks and fallback immediately before dispatch. Runtime health, quota, latency, and availability are mutable facts; resolving runtime at queue time can become stale before execution.

**Risk:** High.

A job queued with `selected_runtime: codex` may execute hours later when Codex is unavailable, rate-limited, or no longer preferred. This contradicts dynamic routing and health-aware fallback.

**Recommendation:**

Clarify the state model:

- At queue time: store `preferred_runtime` or `runtime_hint`, not authoritative `selected_runtime`.
- At dispatch time: resolve and persist `selected_runtime` based on current health, capability match, cost, and fallback.
- In audit: record both the original hint and actual selected runtime.

This likely needs an ADR: **Runtime Binding Time**.

---

### 1.3 Registry immutability conflicts with route-time capability resolution

**Finding:**

`KERNEL.md` says:

> The Registry is immutable during a job's lifecycle. If routing rules change while a job is queued, the job uses the rules from when it entered the queue.

ADR-K003 says capability resolution happens at route time so revoked capabilities apply before dispatch.

**Risk:** Medium-High.

If routing rules are frozen at queue time but capabilities are resolved at route time, the Kernel has split-brain state: job-to-agent/runtime mapping is old, capability envelope is current. This can produce a runtime/agent assignment that is no longer allowed by current capability policy.

**Recommendation:**

Define versioned policy snapshots:

- `routing_policy_version`
- `capability_policy_version`
- `runtime_policy_version`

Then explicitly decide whether a queued job uses:

1. full queue-time policy snapshot, or
2. full dispatch-time current policy, or
3. hybrid policy with safety revocations always applied.

Recommended default: **dispatch-time current policy, with queue-time policy recorded only for audit**.

---

### 1.4 Capability source inconsistency

**Finding:**

`KERNEL.md` section 3.4 says capabilities are read from `docs/LISAOS/CAPABILITIES.md`.

`KERNEL.md` section 7.4 says:

> `AGENTS.md` → agent–capability matrix

But the matrix actually lives in `CAPABILITIES.md`; `AGENTS.md` contains per-agent allowed/prohibited lists.

**Risk:** Medium.

Capability resolution depends on a precise authority chain. If two files are treated as matrices, drift becomes likely.

**Recommendation:**

Clarify source-of-truth split:

- `CAPABILITIES.md` = canonical capability definitions + canonical agent–capability matrix.
- `AGENTS.md` = human-readable agent role profiles and output contracts, derived from or checked against capabilities.
- Routing resolver should not infer permissions directly from prose in `AGENTS.md` unless explicitly declared authoritative.

---

### 1.5 Validation pipeline order inconsistency

**Finding:**

The validation pipeline lists:

```text
Static Review → Tests → Browser QA → Regression → Security Review → Governance Audit
```

But the diagram shows Security Review feeding Governance separately, visually implying Security may happen after Regression but before Governance while Governance also receives from Regression. This is broadly acceptable, but not precise.

**Risk:** Low-Medium.

Pipeline ambiguity matters when failures are critical. For example, if Security is critical, should Browser QA continue after a static review fail? Should Security always run even if tests fail?

**Recommendation:**

Define validation execution semantics separately:

- strict sequential
- sequential but gather-on-failure
- critical-stop stages
- parallel review stages
- job-type-specific stage graph

This may belong in a dedicated `VALIDATION.md` rather than the Kernel overview.

---

### 1.6 `AUTOMATIC` approval semantics conflict with human final authority

**Finding:**

The Kernel says human approval is final authority, but also allows `AUTOMATIC` approval for Docs, Analysis, and Memory if validation passes.

**Risk:** Medium.

For low-risk documentation, this is operationally reasonable. For memory curation or architecture-adjacent analysis, automatic approval could still alter durable truth. It may conflict with the principle that documentation defines reality.

**Recommendation:**

Split approval classes:

- `HUMAN_REQUIRED`
- `AUTO_ALLOWED`
- `AUTO_ALLOWED_WITH_AUDIT`
- `HUMAN_ON_FAILURE`
- `HUMAN_ON_DURABLE_TRUTH_CHANGE`

Memory curation and architecture documentation should likely require at least `AUTO_ALLOWED_WITH_AUDIT`, and architecture-facing docs may require human approval.

---

## 2. Missing Concepts

### 2.1 Job state machine is incomplete

**Finding:**

The Kernel lists statuses such as `queued`, `assigned`, `active`, `completed`, `failed`, `partial`, `timed_out`, and `rejected`, but does not define a complete state machine.

**Risk:** High for implementation.

Without valid transitions, agents or schedulers can create invalid states such as `completed → active`, `failed → completed`, or `rejected → active` without explicit remediation.

**Recommendation:**

Create a formal job state model with:

- allowed states
- allowed transitions
- terminal states
- retryable states
- human-gated states
- audit requirements per transition

Suggested states:

```text
requested → queued → blocked | assigned → active → validating → awaiting_approval → approved | rejected | failed | archived
```

---

### 2.2 Artifact contract is underspecified

**Finding:**

The Kernel references artifacts repeatedly, but does not define canonical artifact types, required storage locations, naming conventions, retention policy, or evidence integrity.

**Risk:** Medium-High.

Validation and audit depend on artifacts. Without a contract, reports, screenshots, patches, logs, and review outputs may be scattered or overwritten.

**Recommendation:**

Create an artifact contract document or section defining:

- artifact IDs
- artifact types
- required metadata
- storage roots (`reports/`, `docs/`, `lisaos/jobs/audit/`)
- retention policy
- hash/checksum requirements for enterprise audit
- redaction rules for sensitive logs/screenshots

---

### 2.3 Policy/versioning model is missing

**Finding:**

The Kernel uses multiple policy sources: routing rules, runtime registry, capabilities, agents, Manifest, Kernel, ADRs. It does not define how policy versions are captured per job.

**Risk:** High.

A job audit must answer: "Which policies were in effect when this job ran?"

**Recommendation:**

Add a policy snapshot model to job audit records:

- `kernel_version`
- `routing_rules_commit`
- `runtimes_commit`
- `capabilities_commit`
- `agents_commit`
- `manifest_commit`
- `packet_commit`
- `repo_commit`

For Git-based mode, commit SHA is enough. For future API/database mode, use explicit policy version IDs.

---

### 2.4 Identity, authentication, and authorization are missing

**Finding:**

The Kernel describes approvals but not identity proof. It says Roshan approves, but does not define how the approver is authenticated or how approval is signed.

**Risk:** High for enterprise or cloud deployment.

Approval without identity and tamper-proof evidence is insufficient for audit or compliance.

**Recommendation:**

Define approval identity semantics:

- approver ID
- authentication method
- approval signature or signed event
- timestamp source
- channel/source of approval
- revocation model
- delegated approval rules, if any

This likely belongs in a dedicated ADR: **Approval Identity and Authority**.

---

### 2.5 Secrets and sensitive data handling are missing at the Kernel level

**Finding:**

Capabilities prohibit `manage_secrets`, but the Kernel does not describe what happens when context packs, logs, screenshots, reports, or database reads contain secrets or personal data.

**Risk:** High, especially for cloud runtimes.

Sensitive data can leak through context streaming, screenshots, traces, logs, or audit artifacts even if agents never intentionally manage secrets.

**Recommendation:**

Add a data classification and redaction layer before context leaves the local environment:

- public
- internal
- confidential
- secret
- personal data
- payment-sensitive data

Define runtime eligibility by data class. Example: local-only for secrets; cloud-allowed only after redaction.

---

### 2.6 Environment model is missing

**Finding:**

The Kernel discusses production code, deployment, QA, and browser runs, but does not define environments.

**Risk:** Medium-High.

Actions have different risk profiles depending on whether they target local, staging, production, or customer tenant environments.

**Recommendation:**

Add an environment model:

- local
- development
- staging
- production
- tenant sandbox

Capabilities should be scoped by environment. For example, `query_database` on staging is not equivalent to `query_database` on production.

---

### 2.7 Conflict resolution and dependency graph are missing

**Finding:**

The Scheduler checks dependencies, but the Kernel does not define dependency syntax, conflict detection, repository lock granularity, or deadlock prevention.

**Risk:** Medium-High for multi-worker scaling.

Concurrent builders and reviewers can collide without a formal dependency and lock model.

**Recommendation:**

Define:

- `depends_on`
- `blocks`
- `conflicts_with`
- `locks`
- lock scopes (`repo`, `path`, `package`, `database`, `environment`)
- deadlock handling
- stale lock cleanup

---

### 2.8 Human override and exception handling are missing

**Finding:**

The Kernel says validation failures return to human for decision, including possible override, but does not define override semantics.

**Risk:** Medium.

Overrides can become informal bypasses unless they are explicit, recorded, and scoped.

**Recommendation:**

Define an override model:

- allowed override types
- prohibited overrides (`bypass_gate` remains impossible)
- required justification
- expiration/scope
- audit trail
- follow-up remediation requirement

---

### 2.9 Runtime trust boundaries are missing

**Finding:**

The Kernel treats runtimes uniformly but does not classify trust boundaries between local, OpenClaw-hosted, vendor-hosted, and future cloud workers.

**Risk:** High.

Model-agnostic does not mean trust-agnostic. A cloud runtime, local runtime, and browser QA runtime have different data exposure and capability risks.

**Recommendation:**

Add runtime trust tiers:

- local trusted
- local untrusted/sandboxed
- vendor cloud standard
- vendor cloud restricted-data approved
- enterprise private cloud

Runtime Resolver should check trust tier against context data classification.

---

## 3. Circular Dependencies

### 3.1 Kernel depends on docs that it also governs

**Finding:**

The Kernel reads `MANIFEST.md`, `AGENTS.md`, `CAPABILITIES.md`, and itself as context, but it also governs jobs that may modify these documents.

**Risk:** Medium.

A job modifying `CAPABILITIES.md` changes the rule set that future jobs use. Without policy snapshots, review gates, or bootstrapping rules, the system can self-modify its governance model too easily.

**Recommendation:**

Introduce a protected-document governance rule:

- Kernel, Manifest, Agents, Capabilities, routing rules, runtime registry require `GOVERNANCE` job type.
- Changes require human approval.
- The job must execute under the previous committed policy and only become effective after approval and commit.

---

### 3.2 OpenClaw enforces capabilities, but capabilities depend on documents OpenClaw reads

**Finding:**

`CAPABILITIES.md` says OpenClaw enforces boundaries at route time. But those boundaries come from repository docs. If repository docs are malformed, conflicting, or maliciously changed, enforcement can degrade.

**Risk:** Medium-High.

The enforcement engine must not rely solely on mutable prose documents.

**Recommendation:**

Define a compiled policy artifact:

- source docs remain human-readable truth
- compiled policy (`lisaos/registry/policy.json` or equivalent) is generated and validated
- OpenClaw enforces the compiled artifact
- changes to source docs regenerate and validate policy before activation

---

### 3.3 Memory Writer can alter future context after job completion

**Finding:**

The Memory Writer persists lessons and decisions after archival. Future jobs use memory and docs as context. This is expected, but it creates a feedback loop.

**Risk:** Medium.

Incorrect memory curation can bias future context. Because memory curation may be automatically approved, durable truth can drift.

**Recommendation:**

Require a review gate for memory changes that affect architecture, business rules, security posture, or capability policy. Routine daily notes may remain automatic.

---

## 4. Responsibility Overlap

### 4.1 Scheduler vs Runtime Resolver

**Finding:**

The Scheduler's resource check selects fallback runtime, while Runtime Resolver owns runtime selection.

**Risk:** Medium.

Two components appear to own the same decision.

**Recommendation:**

Scheduler should ask Runtime Resolver for availability and selected runtime. Scheduler should not implement fallback logic directly.

Suggested split:

- Scheduler: dependency readiness, queue movement, dispatch timing
- Runtime Resolver: runtime selection, fallback, cost, health

---

### 4.2 Capability Resolver vs OpenClaw enforcement

**Finding:**

Capability Resolver creates a capability envelope; OpenClaw enforces boundaries. The exact enforcement contract is not defined.

**Risk:** Medium-High.

If the envelope is advisory only, enforcement is weak. If OpenClaw enforces but has no compiled policy, enforcement may be inconsistent.

**Recommendation:**

Define enforcement levels:

- advisory prompt constraints
- tool-level deny rules
- file/path write deny rules
- runtime sandbox constraints
- external-action deny rules

Each capability should map to one enforcement level.

---

### 4.3 Governance Pipeline vs Approval Gateway

**Finding:**

Governance verifies scope, capabilities, artifacts, validation, documentation, and security. Approval Gateway presents results and allows approval. It is unclear whether Approval Gateway can override Governance failure.

**Risk:** Medium.

If human can approve after governance fail, that is an override path. If not, approval is not final authority.

**Recommendation:**

Define distinction:

- Governance Pipeline = objective policy compliance result.
- Approval Gateway = human acceptance decision.
- Human may reject any job.
- Human may override only specific non-critical failures with recorded justification.
- Human may not override critical security or `bypass_gate` violations without a separate governance job.

---

### 4.4 Audit Logger vs Git history

**Finding:**

Audit Logger records job lifecycle, while Git is described as authoritative history. These are different things.

**Risk:** Medium.

Git records file changes, not necessarily runtime events, health checks, approval identity, or validation execution metadata.

**Recommendation:**

Use Git as source-control history, not sole audit authority. Audit Logger should produce structured immutable records; Git commits can store or reference them.

---

## 5. Future Scaling Risks

### 5.1 File queue does not scale to concurrent workers

**Finding:**

ADR-K001 acknowledges no concurrency, no TTL, no pub/sub. Kernel later claims multiple builders and distributed workers require no architecture change.

**Risk:** High.

The interface may survive, but operational architecture changes are non-trivial: locking, ordering, retries, visibility timeout, idempotency, and worker leasing are required.

**Recommendation:**

Document the file queue as **current local implementation**, not generally scalable architecture. Add a future queue contract with required semantics:

- atomic enqueue/dequeue
- visibility timeout
- worker lease
- retry count
- dead-letter queue
- idempotency key
- lock ownership

---

### 5.2 Repository locking is underdefined

**Finding:**

The Kernel says only one `ENGINEERING` job executes at a time, then future compatibility says multiple builders can work with repository locking per scope.

**Risk:** Medium-High.

This is a major behavioural shift. Scope locks require path ownership, merge conflict policy, and dependency tracking.

**Recommendation:**

Add ADR: **Repository Locking and Concurrent Engineering**.

---

### 5.3 Validation pipeline latency will grow linearly

**Finding:**

Sequential validation is simple but slow as stages expand.

**Risk:** Medium.

Enterprise or CI-scale execution will suffer if all validations run serially even when independent.

**Recommendation:**

Define stage graph semantics now:

- static review and security can run in parallel after implementation
- tests and browser QA may run in parallel if isolated
- governance should remain final aggregator

This can preserve current sequential default while allowing future parallelisation.

---

### 5.4 Artifact storage in Git/reports may become unbounded

**Finding:**

Reports and artifacts are referenced but no retention or pruning policy exists.

**Risk:** Medium.

Screenshots, traces, logs, and test reports can bloat the repository and expose sensitive data.

**Recommendation:**

Define retention tiers:

- durable decision artifacts: Git
- temporary raw artifacts: `reports/` with TTL
- large binaries: external object storage or Git LFS
- sensitive artifacts: redacted or local-only

---

## 6. Enterprise Deployment Concerns

### 6.1 Auditability is not enterprise-grade yet

**Finding:**

Git commits and YAML records are insufficient for enterprise compliance.

**Concerns:**

- no signed approval events
- no tamper-evident event chain
- no immutable append-only log
- no access control model
- no separation of duties enforcement beyond documentation
- no retention policy

**Recommendation:**

Add enterprise audit design:

- append-only event log
- cryptographic hashes for artifacts
- signed approvals
- role-based access control
- event correlation IDs
- retention and legal hold policy

---

### 6.2 Multi-tenancy is only mentioned, not designed

**Finding:**

Commercial LisaOS section says jobs carry tenant ID and capabilities/context are tenant-scoped, but no tenant isolation model exists.

**Risk:** High for commercial deployment.

Tenant isolation is not a wrapper; it affects context resolution, artifact storage, runtime selection, logs, approvals, and billing.

**Recommendation:**

Create dedicated ADR: **Tenant Isolation Model**.

Required topics:

- tenant-scoped job queues
- tenant-scoped context stores
- artifact partitioning
- access control
- per-tenant runtime policy
- tenant billing metadata
- cross-tenant leak prevention

---

### 6.3 Access control model is absent

**Finding:**

Capabilities govern agents, but there is no human/admin RBAC model.

**Risk:** Medium-High.

Enterprise deployments need roles beyond Roshan: owner, architect, reviewer, operator, auditor, tenant admin, read-only viewer.

**Recommendation:**

Define RBAC separately from agent capabilities. Human roles should govern who can create, approve, override, archive, or modify policy.

---

### 6.4 Compliance data handling is absent

**Finding:**

Kernel does not address GDPR, data minimisation, PII redaction, data residency, retention, or audit access.

**Risk:** High for cloud/commercial deployment.

**Recommendation:**

Add a Data Governance document before enterprise deployment.

---

## 7. Cloud Deployment Concerns

### 7.1 Context streaming may leak sensitive data

**Finding:**

Cloud execution section says context packs can be serialised and transmitted to remote runtimes.

**Risk:** High.

Context packs may include repository code, logs, database snippets, business rules, payment rules, or personal data.

**Recommendation:**

Before cloud execution, define:

- context redaction
- data classification
- runtime trust tiers
- cloud provider allow/deny lists
- per-runtime data handling policy
- audit of what context was sent where

---

### 7.2 Artifact sync trust and integrity are undefined

**Finding:**

Cloud execution says remote artifacts sync back to local filesystem.

**Risk:** Medium-High.

Remote artifact sync can introduce tampered files, malware, prompt-injected docs, or untrusted binary artifacts.

**Recommendation:**

Define artifact ingestion policy:

- hash verification
- file type allowlist
- quarantine before trust
- scan before merge
- provenance metadata

---

### 7.3 Cloud worker identity is undefined

**Finding:**

Distributed workers register with Scheduler, but no identity or attestation is described.

**Risk:** High.

Untrusted workers could claim jobs, exfiltrate context, or forge results.

**Recommendation:**

Define worker registration:

- worker identity
- credentials
- attestation
- allowed capabilities
- allowed tenants/environments
- revocation
- heartbeat and lease expiration

---

### 7.4 Network failure semantics are missing

**Finding:**

Kernel includes runtime timeout handling but not cloud network partitions, partial uploads/downloads, duplicate job execution, or lost acknowledgements.

**Risk:** Medium-High.

Distributed systems fail in non-local ways. Duplicate execution and lost results must be expected.

**Recommendation:**

Add idempotency and exactly-once/at-least-once semantics to job contract. Practical default: at-least-once execution with idempotent artifact writes and de-duplication by job ID + attempt ID.

---

## 8. Missing ADRs

Recommended new ADRs:

1. **ADR-K012: Runtime Binding Time**  
   Decide whether runtime is selected at queue time, dispatch time, or both.

2. **ADR-K013: Job State Machine**  
   Define legal states, transitions, retries, terminal states, and archival rules.

3. **ADR-K014: Policy Snapshot and Versioning**  
   Define how routing, capability, runtime, and Kernel policy versions are captured per job.

4. **ADR-K015: Protected Governance Documents**  
   Define rules for changing Kernel, Manifest, Agents, Capabilities, routing rules, and runtime registry.

5. **ADR-K016: Approval Identity and Override Policy**  
   Define signed approvals, approver identity, override classes, and non-overridable failures.

6. **ADR-K017: Data Classification and Runtime Trust Tiers**  
   Define what data can be sent to which runtime classes.

7. **ADR-K018: Artifact Contract and Retention**  
   Define artifact storage, IDs, hashing, retention, redaction, and provenance.

8. **ADR-K019: Repository Locking and Concurrent Engineering**  
   Define lock scopes, merge gates, stale locks, deadlock handling, and multi-builder execution.

9. **ADR-K020: Distributed Worker Trust Model**  
   Define worker identity, registration, leases, revocation, and network failure semantics.

10. **ADR-K021: Enterprise Audit and RBAC**  
    Define enterprise-grade access control, tamper-evident logs, retention, and separation of duties.

11. **ADR-K022: Tenant Isolation Model**  
    Define tenant-scoped queues, context, artifacts, approvals, billing, and leak prevention.

---

## 9. Concepts That Should Move Into Separate Documents

The Kernel is becoming a large umbrella document. Some sections should remain summarised in `KERNEL.md` but move detailed design into separate documents.

Recommended extraction:

| Concept | Recommended document | Reason |
|--------|----------------------|--------|
| Validation stages and skip logic | `docs/LISAOS/VALIDATION.md` | Pipeline design will grow independently |
| Job states and queue contract | `docs/LISAOS/JOBS.md` | State machine and queue semantics need precision |
| Runtime health/fallback/cost/trust | `docs/LISAOS/RUNTIMES.md` | Runtime resolution is complex enough for its own spec |
| Capability enforcement levels | `docs/LISAOS/CAPABILITY_ENFORCEMENT.md` | CAPABILITIES defines names; enforcement needs separate mechanics |
| Approval and overrides | `docs/LISAOS/APPROVALS.md` | Human authority, signatures, override classes need precision |
| Artifact contract and retention | `docs/LISAOS/ARTIFACTS.md` | Reports/screenshots/logs/patches need lifecycle rules |
| Audit/event log | `docs/LISAOS/AUDIT.md` | Git history is not enough for enterprise audit |
| Data classification | `docs/LISAOS/DATA_GOVERNANCE.md` | Required before cloud/enterprise execution |
| Distributed workers | `docs/LISAOS/WORKERS.md` | Worker registration, leases, idempotency need dedicated model |
| Tenant isolation | `docs/LISAOS/TENANCY.md` | Commercial LisaOS needs explicit isolation guarantees |

Recommendation: keep `KERNEL.md` as the top-level lifecycle and responsibility model; move detailed operational contracts into companion documents.

---

## 10. Capability Taxonomy Findings

### 10.1 Undefined capabilities used in `AGENTS.md`

The following capability names appear in `AGENTS.md` but are not defined in `CAPABILITIES.md`:

- `change_permissions`
- `change_production_code`
- `edit_production_code`
- `make_scope_decisions`
- `query_db_schema`
- `read_adr`
- `read_implementation_report`
- `restructure_memory`
- `write_report`
- `write_scope_document`

**Risk:** High.

Undefined capabilities cannot be enforced consistently. Some are likely synonyms of existing capabilities, but synonyms create drift.

**Recommendation:**

Normalize the vocabulary:

- Either define these capabilities in `CAPABILITIES.md`, or
- Replace them in `AGENTS.md` with canonical names.

Suggested mappings:

| Current name | Possible canonical mapping |
|--------------|----------------------------|
| `edit_production_code` | `write_production_code` or `edit_repo` |
| `change_production_code` | `write_production_code` |
| `make_scope_decisions` | `change_scope` |
| `query_db_schema` | define separately, or map to `query_database` with schema-only scope |
| `write_scope_document` | `write_plan` or define separately |
| `write_report` | define generic `write_report`, or split into report-specific capabilities |
| `restructure_memory` | define, or use `write_memory` + `prune_stale` |
| `read_adr` | likely included in `read_docs`, but should be explicit if needed |
| `read_implementation_report` | likely included in `read_docs`, but should be explicit if needed |
| `change_permissions` | define as globally prohibited or map to `modify_config` |

---

### 10.2 `rollback` referenced but not a defined capability

**Finding:**

`KERNEL.md` says:

> No agent or automation has the `rollback` capability by default.

But `rollback` is not defined in `CAPABILITIES.md`.

**Risk:** Low-Medium.

If `rollback` is a capability, define it. If it is a process, remove capability-style language.

**Recommendation:**

Create a dedicated rollback ADR and define rollback as either:

- a capability with strict human-only rules, or
- a job type/process, not a capability.

---

## 11. Recommendation Summary

### Priority 0 — must resolve before implementation/enforcement

1. Align architecture stack across Manifest and Kernel.
2. Fix runtime binding timing: queue-time hint vs dispatch-time selection.
3. Normalize capability vocabulary across AGENTS and CAPABILITIES.
4. Define job state machine and legal transitions.
5. Define policy snapshot/versioning model.
6. Define protected governance document rules.

### Priority 1 — should resolve before scaling beyond single operator

1. Define artifact contract and retention.
2. Define repository lock model.
3. Define validation stage graph and critical-stop semantics.
4. Define approval identity and override policy.
5. Define capability enforcement levels.
6. Define audit event model beyond Git history.

### Priority 2 — required before cloud or enterprise deployment

1. Define data classification and redaction.
2. Define runtime trust tiers.
3. Define worker identity and attestation.
4. Define tenant isolation model.
5. Define RBAC and enterprise audit requirements.
6. Define network failure/idempotency semantics.

---

## Final Assessment

The Kernel is a strong architectural foundation, but it is currently best understood as a **conceptual operating model**, not yet a complete operational specification.

It should remain active as the v3 Kernel document, with this review driving the next documentation hardening pass. The most urgent fixes are not implementation details; they are authority boundaries, vocabulary normalization, lifecycle state precision, policy versioning, and cloud/enterprise trust boundaries.

No files were modified during review except this review artifact: `docs/LISAOS/KERNEL_REVIEW.md`.
