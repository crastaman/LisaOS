# LisaOS Runtime Selection Policy

**Job ID:** L005-L007-LISAOS-ORCHESTRATION-DESIGN-STUDY  
**Repository:** `~/Lisa`  
**Scope:** Detailed runtime selection rules, policy enforcement, and operational guidelines.  
**Runtime behaviour:** Unchanged. Documentation only.

---

## 1. Purpose

This document defines the formal policy for selecting AI runtimes within LisaOS. It extends the Runtime Resolver architecture (L005) with operational rules, edge-case handling, and policy enforcement mechanisms.

---

## 2. Policy Scope

This policy applies to:

- All jobs dispatched through the LisaOS Kernel
- All agents that require a runtime for execution
- All validation and governance stages that reference runtime selection

It does not apply to:

- The human manually selecting a runtime (human override always permitted)
- OpenClaw's internal runtime management (Cron, Tasks, Skills are OpenClaw primitives, not LisaOS job runtime selections)

---

## 3. Selection Rules

### 3.1 Rule 1: Capability First

**Statement:** A runtime must satisfy all required capabilities for the job. If no runtime can meet all capability requirements, the job may not proceed without human override.

**Enforcement:**
- The Capability Resolver produces the full list of required capabilities.
- The Runtime Candidate Engine filters to runtimes that advertise matching capabilities.
- The scoring model assigns a `C` (capability match) score of 0.0 to any runtime missing a required capability.

**Override:** Human may override capability constrains by explicitly approving a capability-gapped runtime. The override is logged in the decision log and audit trail.

### 3.2 Rule 2: Health Before Selection

**Statement:** A runtime may only be selected if it passes its health check at selection time.

**Enforcement:**
- Health status is checked immediately before selection — not cached from a previous check.
- Health status is valid for 30 seconds. After 30 seconds, the check must be re-run.
- Unhealthy, rate-limited, or quota-exhausted runtimes are excluded from the candidate pool.

**Edge case — intermittent health:** If a runtime passes health check but fails during execution (transient outage), the retry policy applies. The runtime is not rechecked until after the job is completed — the Execution Monitor handles in-flight failures.

### 3.3 Rule 3: Cost Preference Among Equals

**Statement:** When multiple healthy runtimes satisfy all capability requirements at the same priority level, prefer the lower-cost option.

**Enforcement:**
- The scoring model's `A` (cost advantage) score breaks ties.
- If scores are equal after all weighting, the lower per-token cost wins.
- If costs are equal, choose by hardware affinity (same provider is preferred to avoid additional credential endpoints).

**Exception:** For security-sensitive jobs, reliability is weighted above cost (per security job type weights in L005 section 5.1).

### 3.4 Rule 4: Fallback Before Failure

**Statement:** Before failing a job due to runtime unavailability, attempt every runtime in the fallback chain.

**Enforcement:**
- The resolver iterates the fallback chain defined in `registry/agents.yml`.
- At each fallback level, all runtimes of that profile are checked for health.
- If all fallbacks fail, an escalation report is produced (not a silent failure).

### 3.5 Rule 5: Preferred Runtime Profile over Agent Fallback

**Statement:** When selecting a runtime, the agent's `preferred_runtime` from `registry/agents.yml` takes precedence over generic profile matching.

**Enforcement:**
- First, look for the agent's `preferred_runtime` in the agent registry.
- If the preferred runtime is healthy and capability-matching: select it.
- If not, look at the agent's `runtime_profile` and match against `registry/runtimes.yml` with the same profile.
- If nothing in the profile is healthy, use the agent's `fallback_runtimes` list.

### 3.6 Rule 6: Experimental Runtime Isolation

**Statement:** Runtimes with `status: experimental` in `registry/runtimes.yml` may only be selected when:

1. The job packet explicitly lists an experimental runtime as `preferred_runtime`, OR
2. All active runtimes are unhealthy and the experimental runtime is the only remaining option, OR
3. A human explicitly overrides the selection

**Enforcement:**
- The resolver excludes experimental runtimes from the candidate pool by default.
- Experimental runtimes are listed separately in the resolution decision packet so the rationale is clear.

---

## 4. Edge Cases

### 4.1 All Runtimes Unhealthy

**Situation:** Every runtime in the primary profile AND fallback chain returns an unhealthy status.

**Response:**
1. Wait 30 seconds and retry the full health check cycle
2. If still all unhealthy: generate escalation report
3. The escalation report recommends:
   - Wait and retry (if transient)
   - Use experimental runtime (if any are active)
   - Defer the job to next maintenance window
   - Manual human override

### 4.2 Partial Capability Match

**Situation:** The primary runtime matches 7 of 8 required capabilities. A fallback runtime matches all 8 but costs significantly more.

**Response:**
1. The fallback runtime is selected (capability-first rule)
2. The decision packet records the capability gap of the primary runtime as a finding
3. The gap is logged in the benchmark registry for capability coverage tracking

### 4.3 Rate-Limited Preferred Runtime

**Situation:** The preferred runtime is healthy but rate-limited with a 60-second reset.

**Response:**
1. If the retry policy has capacity remaining and the reset is <30 seconds: wait, retry
2. If the reset is >30 seconds: fall back to next candidate
3. If all candidates are rate-limited: escalate

### 4.4 New Runtime Added Mid-Queue

**Situation:** A new runtime is registered while a job is queued.

**Response:**
- Jobs use the routing and runtime rules from when they entered the queue (per KERNEL.md — registry is immutable during job lifecycle)
- The new runtime is available for jobs queued after registration

### 4.5 Runtime Cost Model Changes

**Situation:** A runtime provider changes pricing.

**Response:**
1. Update the `cost_tier` field in `registry/runtimes.yml`
2. The next resolution cycle picks up the new cost tier automatically
3. No code change needed — only a registry update

---

## 5. Policy Enforcement

### 5.1 Enforcement Points

| Point | What Is Enforced | Enforcer |
|-------|-----------------|----------|
| Registry validation | Runtimes.yml schema compliance | Registry validation scripts |
| Pre-dispatch | Health check, capability match, cost preference | Runtime Candidate Engine |
| Dispatch | Capability envelope (allowed/prohibited) | Agent Dispatcher |
| Execution | Tool use within capability envelope | OpenClaw runtime |
| Post-execution | Actual runtime used vs. selected runtime | Audit Logger |
| Governance | Runtime selection rationale, capability compliance | Governance Pipeline |

### 5.2 Governance Checks on Runtime Selection

The Governance Pipeline includes these checks for every job:

```yaml
governance_runtime_checks:
  runtime_selection_documented: boolean   # Was a reason recorded?
  capability_coverage: float             # What fraction of capabilities were matched?
  fallback_used: boolean                 # Was a fallback necessary?
  cost_tier_adhered: boolean             # Was the lowest-cost option selected?
  experimental_used: boolean             # Was an experimental runtime used? (flagged)
  human_override_required: boolean      # Did the selection require human override?
  override_approved: boolean | null      # If override was needed, was it approved?
```

### 5.3 Violation Handling

| Violation | Severity | Response |
|-----------|----------|----------|
| Runtime selected without health check | High | Flagged in audit. Policy violation. |
| Capability-gapped runtime selected without override | High | Escalated to human. Job blocked. |
| Experimental runtime selected without documented rationale | Medium | Flagged in governance. |
| Cost preference ignored when equal capabilities | Low | Logged as warning. Governance note. |
| Fallback chain skipped | Medium | Flagged in audit. Requires ADR. |

---

## 6. Operational Guidelines

### 6.1 Runtime Maintenance

- **Adding a runtime:** Follow the process in L005 section 7 (define capability profile, register, health check, benchmark).
- **Removing a runtime:** Update `registry/runtimes.yml` with `status: deprecated`. Existing queued jobs using this runtime must be re-routed.
- **Updating a runtime:** Change fields in `registry/runtimes.yml`. The resolver picks up changes on next resolution cycle.
- **Health check maintenance:** Each runtime's health check must be verified monthly. Document the procedure in `runtime/health/README.md`.

### 6.2 Cost Management

- Review runtime cost tiers quarterly against actual bills.
- Adjust `cost_tier` in `registry/runtimes.yml` to reflect negotiated rates or new pricing.
- If a runtime's cost becomes prohibitive, lower its priority in agent fallback chains.
- Prefer local/private runtimes (Ollama) for cost-sensitive or privacy-sensitive work.

### 6.3 Human Override Protocol

When a human overrides the runtime selection:

1. The human specifies which runtime to use.
2. The rationale for override is recorded in the decision log.
3. The override is flagged in the governance audit.
4. The human may also override capability constraints (e.g., "use this runtime even though it lacks capability X").
5. Overrides are recorded in the audit trail and reviewed weekly.

---

## 7. Runtime Selection Matrix

| Job Type | Primary Profile | Primary Runtime | First Fallback | Second Fallback |
|----------|----------------|-----------------|---------------|-----------------|
| ENGINEERING | implementation-runtime | codex-review | claude-review | glm-builder-future (experimental) |
| QA_BROWSER | operator-runtime | openclaw | — | — |
| GOVERNANCE | governance-runtime | gpt-governance | deepseek-planning | claude-review |
| SECURITY | review-runtime | claude-review | gpt-governance | deepseek-planning |
| PLANNING | planning-runtime | deepseek-planning | gpt-governance | claude-review |
| DOCS | governance-runtime | gpt-governance | deepseek-planning | openclaw (any_available) |
| RELEASE | governance-runtime | gpt-governance | claude-review | — |
| RESEARCH | planning-runtime | deepseek-planning | gpt-governance | ollama (lightweight) |
| REVIEW | review-runtime | claude-review | gpt-governance | codex-review |

---

## Related Documents

- `docs/LISAOS/L005_RUNTIME_ROUTING_ARCHITECTURE.md` — Runtime resolver design and scoring model
- `docs/LISAOS/KERNEL.md` — Kernel architecture (section 3.5 Runtime Resolver)
- `docs/LISAOS/KERNEL_DECISIONS.md` — ADR-K004 (Runtime Resolution with Health Checks and Fallback Chain)
- `registry/runtimes.yml` — Runtime definitions
- `registry/agents.yml` — Agent runtime profiles and fallback chains
- `lisaos/policies/routing.yml` — Job type routing rules
- `runtime/resolver/README.md` — Future resolver specification
