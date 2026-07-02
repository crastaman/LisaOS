# L005 — Runtime Routing Architecture

**Job ID:** L005-LISAOS-ORCHESTRATION-DESIGN-STUDY  
**Repository:** `~/Lisa`  
**Scope:** Runtime resolver architecture, routing models, capability matching, and provider integration strategies.  
**Runtime behaviour:** Unchanged. Documentation only.

---

## 1. Purpose

L005 defines how LisaOS selects the optimal runtime for every job. The Runtime Resolver is the intelligence layer between a job's requirements and the execution engine that will fulfil them.

This document covers:

- Runtime selection policy (the rules that govern choice)
- Runtime profiles (the characteristics that define each runtime)
- Resolver architecture (the system that applies policy to profiles)
- Scoring model (the quantitative framework for comparison)
- Provider integration strategies (how new runtimes join the system)

---

## 2. Runtime Selection Policy

### 2.1 Governing Principles

**Principle 1: Capability-first matching.** The primary constraint is whether a runtime can satisfy every required capability for the job. Cost, latency, and availability are secondary filters applied within the capability-constrained set.

**Principle 2: Provider neutrality.** No runtime receives preferential treatment beyond what its capability profile, health status, and cost justify. Every runtime competes on merit in every resolution cycle.

**Principle 3: Graceful degradation.** When the optimal runtime is unavailable, the system degrades to the next-best healthy runtime. It never fails because a single provider is down.

**Principle 4: Cost-awareness as a soft constraint.** Lower cost is preferred when multiple runtimes provide equivalent capabilities. Cost is a tiebreaker, not a primary selector.

**Principle 5: Deterministic resolution.** Given the same job type, capability requirements, runtime health state, and cost configuration, the resolver must produce the same result. Determinism enables reproducible audit trails.

### 2.2 Resolution Order

```
  ┌─────────────────────────────────────────────────────────┐
  │                  RUNTIME RESOLUTION                      │
  │                                                          │
  │  1. CLASSIFY JOB                                         │
  │     └─ Read job type from job packet                     │
  │                                                          │
  │  2. RESOLVE CAPABILITY REQUIREMENTS                      │
  │     └─ Required capabilities from job type + job packet  │
  │     └─ Prohibited capabilities from job type + agent     │
  │                                                          │
  │  3. IDENTIFY RUNTIME CANDIDATES                          │
  │     └─ Match runtime_profiles from registry/runtimes.yml │
  │     └─ Apply agent fallback chain from registry/agents   │
  │                                                          │
  │  4. CAPABILITY FILTER                                    │
  │     └─ Retain runtimes that satisfy all required caps    │
  │     └─ Exclude runtimes with any prohibited cap          │
  │                                                          │
  │  5. HEALTH CHECK                                         │
  │     └─ Query each candidate's health/status endpoint     │
  │     └─ Exclude unavailable, rate-limited, exhausted      │
  │                                                          │
  │  6. SCORE CANDIDATES                                     │
  │     └─ Apply scoring model: cost, latency, confidence    │
  │     └─ Prefer lower cost among equal-capability runners  │
  │                                                          │
  │  7. SELECT BEST                                          │
  │     └─ Highest scoring healthy runtime wins              │
  │     └─ Log selection decision with rationale             │
  │                                                          │
  │  8. FALLBACK IF SELECTION FAILS                          │
  │     └─ Widen candidate pool to fallback runtimes         │
  │     └─ Repeat steps 4-7                                  │
  │     └─ If all fallbacks fail: escalate to human          │
  └─────────────────────────────────────────────────────────┘
```

### 2.3 Fallback Chain Behaviour

The fallback chain operates at two levels:

**Level 1 — Runtime Profile fallback.** If a runtime exists within the same profile but is unhealthy, try other runtimes in the same profile before falling back to a different profile.

**Level 2 — Agent-level fallback.** If no runtime in the primary profile is available, use the agent's `fallback_runtimes` list from `registry/agents.yml`.

| Level | Scope | Example |
|-------|-------|---------|
| L1 — Profile | Same runtime_profile | `governance-runtime`: gpt-governance → deepseek-planning |
| L2 — Agent | Agent fallbacks | planner: gpt-governance → deepseek-planning → claude-review |

### 2.4 Escalation Conditions

The resolver escalates to human when:

1. **All healthy candidates are exhausted** — no runtime in any fallback chain has the required capabilities.
2. **Capability gap on fallback** — a fallback runtime is healthy but missing a required capability.
3. **Health check failure on all candidates** — every candidate is unavailable or rate-limited.
4. **Ambiguous capability requirements** — the job type or packet specifies capabilities that cannot be mapped to any known runtime profile.

Escalation produces a structured report (see L006 — `Approval Packet`) rather than a raw error message.

---

## 3. Runtime Profiles

### 3.1 Profile Architecture

A runtime profile is a named set of characteristics that defines what a runtime can be expected to do, how it performs, and what it costs. Profiles are the abstraction that makes provider replacement transparent.

```
Runtime Profile
  ├── name                  — unique identifier
  ├── capability_set        — what the runtime can do
  ├── cost_tier             — operating cost category
  ├── latency_class         — expected response speed
  ├── context_window        — maximum context capacity
  └── reliability_class     — expected uptime/stability
```

### 3.2 Defined Profiles

#### governance-runtime

| Attribute | Value |
|-----------|-------|
| Name | `governance-runtime` |
| Capabilities | documentation, governance, planning, decision_support, design_review |
| Cost Tier | medium |
| Latency Class | interactive (2-10s) |
| Context Window | large (128K+ tokens) |
| Reliability | high (cloud provider SLA) |
| Typical Models | GPT-5+, Claude Sonnet 4 |

**Primary use:** Planning, architecture, routing decisions, governance review, memory curation.

#### review-runtime

| Attribute | Value |
|-----------|-------|
| Name | `review-runtime` |
| Capabilities | review, code_review, security_review, architecture_review, documentation |
| Cost Tier | medium-high |
| Latency Class | interactive (5-20s) |
| Context Window | large (128K+ tokens) |
| Reliability | high (cloud provider SLA) |
| Typical Models | Claude Sonnet 4+, GPT-5 |

**Primary use:** Code review, security audit, validation pipeline stages, architecture guardrails.

#### planning-runtime

| Attribute | Value |
|-----------|-------|
| Name | `planning-runtime` |
| Capabilities | planning, architecture_review, documentation, migration_strategy |
| Cost Tier | low |
| Latency Class | reflective (10-60s) |
| Context Window | very large (256K+ tokens) |
| Reliability | medium |
| Typical Models | DeepSeek R1+, Kimi K2+ |

**Primary use:** Deep structured reasoning, migration planning, large-context analysis, job decomposition.

#### implementation-runtime

| Attribute | Value |
|-----------|-------|
| Name | `implementation-runtime` |
| Capabilities | implementation, code_review, repository_analysis, refactoring, debugging, validation |
| Cost Tier | medium-high |
| Latency Class | interactive (5-30s) |
| Context Window | large (128K+ tokens) |
| Reliability | medium-high |
| Typical Models | Codex, Claude Code, GPT Codex |

**Primary use:** Code changes, debugging, file operations, patch generation, test writing.

#### operator-runtime

| Attribute | Value |
|-----------|-------|
| Name | `operator-runtime` |
| Capabilities | browser_testing, qa, regression, screenshots, workflow_execution, cron, tasks |
| Cost Tier | low-medium |
| Latency Class | operational (10-120s) |
| Context Window | small (16K-32K) |
| Reliability | high (local execution) |
| Typical Models | OpenClaw (orchestration agent), Playwright runner |

**Primary use:** Browser QA, scheduled tasks, workflow execution, operational monitoring.

#### lightweight-runtime

| Attribute | Value |
|-----------|-------|
| Name | `lightweight-runtime` |
| Capabilities | summarization, local_analysis, documentation, lightweight_code_review |
| Cost Tier | very low (free/local) |
| Latency Class | variable (10-300s) |
| Context Window | medium (32K-128K) |
| Reliability | variable (local hardware dependent) |
| Typical Models | Ollama (Qwen 2.5+, Llama 3+), local inference |

**Primary use:** Private analysis, first-pass summarization, offline-capable tasks, cost-sensitive operations.

### 3.3 Profile-to-Runtime Mapping

The profile-to-runtime mapping is stored in `registry/runtimes.yml` via the `runtime_profile` field. Multiple runtimes can share a profile, creating an internal fallback pool.

```yaml
# Conceptual mapping
governance-runtime:
  - gpt-governance (primary)
  - deepseek-planning (fallback)

review-runtime:
  - claude-review (primary)
  - gpt-governance (fallback)

planning-runtime:
  - deepseek-planning (primary)
  - gpt-governance (fallback)

implementation-runtime:
  - codex-review (primary)
  - claude-review (fallback)
  - glm-builder-future (experimental)

operator-runtime:
  - openclaw (primary)

lightweight-runtime:
  - ollama (primary)
  - deepseek-planning (cost filter)
```

---

## 4. Resolver Architecture

### 4.1 Component Diagram

```
  ┌─────────────┐     ┌──────────────────────┐
  │ Job Packet  │────►│ Job Type Classifier  │
  └─────────────┘     └──────────┬───────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────┐
  │         CAPABILITY RESOLVER                 │
  │  ┌─────────────┐  ┌─────────────────────┐  │
  │  │ Required    │  │ Prohibited          │  │
  │  │ Capabilities│  │ Capabilities        │  │
  │  └─────────────┘  └─────────────────────┘  │
  └────────────────────┬───────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────┐
  │         RUNTIME CANDIDATE ENGINE            │
  │  ┌─────────────┐  ┌─────────────────────┐  │
  │  │ Profile     │  │ Agent Fallback      │  │
  │  │ Matching    │  │ Chain               │  │
  │  └─────────────┘  └─────────────────────┘  │
  └────────────────────┬───────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────┐
  │         CAPABILITY FILTER                   │
  │  For each candidate:                        │
  │    │                                        │
  │    ├── Has ALL required capabilities? ──► KEEP
  │    └── Has ANY prohibited capabilities? ──► REMOVE
  └────────────────────┬───────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────┐
  │         HEALTH CHECKER                      │
  │  For each remaining candidate:              │
  │    ├── Query /status endpoint               │
  │    ├── Check latency, rate limits, quotas   │
  │    └── Remove unhealthy candidates          │
  └────────────────────┬───────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────┐
  │         SCORING ENGINE                      │
  │  Score each candidate:                      │
  │    S = w1*C + w2*L + w3*R + w4*A           │
  │    where:                                   │
  │      C = capability_match_score             │
  │      L = latency_score                      │
  │      R = reliability_score                  │
  │      A = cost_advantage_score               │
  └────────────────────┬───────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────┐
  │         SELECTOR                            │
  │  ┌─────────────────┐  ┌─────────────────┐  │
  │  │ Best Candidate  │  │ Fallback Logic  │  │
  │  │ (score > 0)     │  │ (score = 0)     │  │
  │  └────────┬────────┘  └────────┬────────┘  │
  │           │                    │            │
  │           ▼                    ▼            │
  │     Decision Packet      Escalation Report  │
  └─────────────────────────────────────────────┘
```

### 4.2 Decision Packet

The resolver produces a decision packet — not an execution command. The decision packet is consumed by the Agent Dispatcher (Kernel component) which makes the final dispatch.

```yaml
# Runtime Resolution Decision Packet
resolution:
  job_id: "S014-PRACTITIONER-BACKEND-V2"
  job_type: ENGINEERING
  resolved_at: "2026-07-03T01:52:00Z"

  candidates_evaluated:
    - runtime: codex-review
      profile: implementation-runtime
      status: HEALTHY
      score: 0.92
    - runtime: claude-review
      profile: review-runtime
      status: HEALTHY
      score: 0.78           # Higher cost, same capability gap
    - runtime: glm-builder-future
      profile: implementation-runtime
      status: UNHEALTHY     # Not available

  selection:
    runtime: codex-review
    profile: implementation-runtime
    rationale: "Primary implementation runtime, healthy, best capability match within budget"
    capability_coverage: 1.0       # Fraction of required capabilities matched
    estimated_cost_tier: medium_high
    estimated_latency: "5-30s"

  fallback_available: true
  fallback_chain:
    - claude-review (review-runtime)
    - gpt-governance (governance-runtime)
```

### 4.3 Escalation Report

When no healthy runtime can be selected:

```yaml
# Runtime Resolution Escalation Report
escalation:
  job_id: "S014-PRACTITIONER-BACKEND-V2"
  resolved_at: "2026-07-03T01:52:00Z"
  reason: ALL_CANDIDATES_EXHAUSTED

  candidates_evaluated:
    - runtime: codex-review
      status: RATE_LIMITED
      retry_after: "2026-07-03T02:00:00Z"
    - runtime: claude-review
      status: UNAVAILABLE
      detail: "Authentication error"
    - runtime: glm-builder-future
      status: NOT_CONFIGURED

  recommendation:
    - action: WAIT
      description: "Retry codex-review after rate limit reset (estimated 8 minutes)"
    - action: OVERRIDE
      description: "Manually select alternate runtime or override health check"
    - action: RESCHEDULE
      description: "Defer job to next available slot"
```

---

## 5. Runtime Scoring Model

### 5.1 Scoring Formula

The scoring model produces a normalised score (0.0–1.0) for each candidate runtime:

```
S = w₁·C + w₂·L + w₃·R + w₄·A

Where:
  C = capability_match_score
  L = latency_score
  R = reliability_score
  A = cost_advantage_score

Weights:  w₁ = 0.50 (capability match is primary)
          w₂ = 0.15 (latency matters for interactive jobs)
          w₃ = 0.15 (reliability prevents rework)
          w₄ = 0.20 (cost awareness prevents budget bloat)
```

Weight adjustments per job type:

| Job Type | w₁ (Cap) | w₂ (Lat) | w₃ (Rel) | w₄ (Cost) | Rationale |
|----------|----------|----------|----------|----------|-----------|
| ENGINEERING | 0.50 | 0.15 | 0.15 | 0.20 | Balanced |
| QA_BROWSER | 0.35 | 0.10 | 0.25 | 0.30 | Reliability + cost important |
| GOVERNANCE | 0.40 | 0.25 | 0.20 | 0.15 | Latency matters for interactive review |
| DOCS | 0.40 | 0.10 | 0.15 | 0.35 | Cost-sensitive |
| PLANNING | 0.55 | 0.10 | 0.15 | 0.20 | Capability match critical |
| SECURITY | 0.50 | 0.10 | 0.30 | 0.10 | Reliability critical |
| RELEASE | 0.40 | 0.15 | 0.30 | 0.15 | Reliability critical |
| RESEARCH | 0.45 | 0.10 | 0.15 | 0.30 | Cost-aware exploration |

### 5.2 Sub-Score Definitions

**Capability Match Score (C)**

Ratio of required capabilities that the runtime satisfies:

```
C = matched_required_capabilities / total_required_capabilities

Range: 0.0 to 1.0
```

If capability score is 0.0, the runtime is excluded. Partial matches (e.g., 0.75) are retained as fallback candidates only.

**Latency Score (L)**

Based on observed or expected latency class:

| Latency Class | Expected | Score |
|---------------|----------|-------|
| interactive | < 10s | 1.0 |
| responsive | 10-30s | 0.8 |
| reflective | 30-120s | 0.5 |
| operational | 120s+ | 0.3 |

Score is adjusted downward by 10% for every health-check latency reading above the class threshold.

**Reliability Score (R)**

Based on observed uptime and error rate over the past 7 days:

```
R = (uptime_pct / 100) × (1 - error_rate)

Default values when no data exists:
  cloud_provider:    0.90
  local_instance:    0.80
  experimental:      0.50
```

**Cost Advantage Score (A)**

Normalised inverse of cost tier:

| Cost Tier | Raw Cost | Score |
|-----------|----------|-------|
| very_low | 0 (free) | 1.0 |
| low | 1 | 0.8 |
| low_medium | 2 | 0.6 |
| medium | 3 | 0.4 |
| medium_high | 4 | 0.2 |
| high | 5 | 0.0 |

### 5.3 Scoring Example

Job type: `ENGINEERING` → weights: w₁=0.50, w₂=0.15, w₃=0.15, w₄=0.20

| Runtime | Cap (C) | Lat (L) | Rel (R) | Cost (A) | Score |
|---------|---------|---------|---------|----------|-------|
| codex-review | 1.0 × 0.50 = 0.50 | 0.8 × 0.15 = 0.12 | 0.90 × 0.15 = 0.135 | 0.2 × 0.20 = 0.04 | **0.795** |
| claude-review | 1.0 × 0.50 = 0.50 | 0.8 × 0.15 = 0.12 | 0.90 × 0.15 = 0.135 | 0.0 × 0.20 = 0.00 | **0.755** |
| deepseek-planning | 0.6 × 0.50 = 0.30 | 0.5 × 0.15 = 0.075 | 0.75 × 0.15 = 0.1125 | 0.8 × 0.20 = 0.16 | **0.648** |

**codex-review wins** with the highest composite score.

### 5.4 Benchmark Registry (Future)

The scoring model improves over time through a benchmark registry (`registry/benchmarks.yml`, future). Benchmarks track:

| Metric | How Measured |
|--------|--------------|
| Capability accuracy | Did the runtime produce correct results for its stated capabilities? |
| Execution speed | Time per standardised job type |
| Cost per job | Tokens consumed × price per token |
| Rate-limit frequency | How often the runtime rejects requests |
| Error rate | Non-rate-limit failures per 100 jobs |
| Output quality | Human-rated quality score (Roshan feedback) |

Benchmarks recalibrate the scoring model's default values to reflect real-world performance rather than theoretical estimates.

---

## 6. Provider Integration Strategies

### 6.1 Integration Contract

Every runtime provider must define:

1. **Capability profile** — What capabilities does this runtime offer?
2. **Health check interface** — How does the resolver know it's available?
3. **Cost model** — How does pricing work? (per-token, per-job, flat-rate)
4. **Context window** — Maximum context the runtime can process
5. **Latency characteristics** — Expected response time for different job types

### 6.2 Strategy: GPT Integration

| Aspect | Detail |
|--------|--------|
| Profile | governance-runtime |
| Primary role | Governance, planning, routing decisions |
| Integration | API-based, health check via status probe |
| Cost model | Per-token (current: medium tier) |
| Fallback chain | → deepseek-planning → claude-review |

**Recommendation:** GPT remains the default governance runtime. Its strength in structured reasoning and policy adherence makes it ideal for routing decisions and architecture review. Migrate to a governance-runtime profile abstraction so OpenAI-specific references in code routes are replaced.

### 6.3 Strategy: Claude Integration

| Aspect | Detail |
|--------|--------|
| Profile | review-runtime |
| Primary role | Review, security audit, deep analysis |
| Integration | API-based (Claude Code tool), health check via CLI status |
| Cost model | Per-token (current: high tier) |
| Fallback chain | → gpt-governance → codex-review |

**Recommendation:** Claude is the primary review runtime. Its strength in nuanced analysis and security review justifies the higher cost. Use sparingly for cost-sensitive jobs that GPT or DeepSeek can handle equivalently. The `claude-review` runtime profile supports this without hardcoding Anthropic references.

### 6.4 Strategy: Codex Integration

| Aspect | Detail |
|--------|--------|
| Profile | implementation-runtime |
| Primary role | Engineering implementation and code changes |
| Integration | CLI-based (codex exec), health check via `--version` probe |
| Cost model | Per-token (current: medium_high tier) |
| Fallback chain | → claude-review → glm-builder-future (experimental) |

**Recommendation:** Codex remains the primary implementation runtime. Its sandboxed workspace and Git-aware execution model are ideal for engineering work. The `implementation-runtime` profile abstraction ensures that future replacement (e.g., a dedicated engineering runtime) is transparent.

### 6.5 Strategy: GLM Integration

| Aspect | Detail |
|--------|--------|
| Profile | implementation-runtime (experimental) |
| Primary role | Future implementation and code transformation |
| Integration | API-based, requires credential setup |
| Cost model | Unknown (per-token, potentially low_medium) |
| Fallback chain | → codex-review → claude-review |

**Recommendation (deferred):** GLM (Zhipu) is registered as `experimental` status. Before activating:

1. Benchmark GLM against codex-review on 10 representative engineering tasks
2. Confirm capability parity for `implementation`, `code_review`, `repository_analysis`
3. Determine cost per token and compare with existing runtimes
4. Add health check endpoint
5. Document credential management in `runtime/providers/glm.md`
6. Change status to `active` only after passing all gates

### 6.6 Strategy: DeepSeek Integration

| Aspect | Detail |
|--------|--------|
| Profile | planning-runtime |
| Primary role | Deep reasoning, planning, large-context analysis |
| Integration | API-based (current: low cost tier) |
| Cost model | Per-token (low tier) |
| Fallback chain | → gpt-governance → claude-review |

**Recommendation:** DeepSeek is the primary planning runtime. Its low cost and large context window make it ideal for migration planning and architecture analysis where budget is a concern. It serves as both primary for planning-runtime and fallback for governance-runtime.

### 6.7 Strategy: Ollama Integration

| Aspect | Detail |
|--------|--------|
| Profile | lightweight-runtime |
| Primary role | Private analysis, offline-capable summarization |
| Integration | Local API (localhost), health check via model list probe |
| Cost model | Free (local hardware) |
| Fallback chain | → deepseek-planning → gpt-governance |

**Recommendation:** Ollama is the privacy-preserving and cost-free option. Use for:

- First-pass analysis on sensitive data
- Offline-capable documentation summarization
- Cost-sensitive exploration
- Benchmark baseline for other runtimes

### 6.8 Strategy: OpenClaw Integration

| Aspect | Detail |
|--------|--------|
| Profile | operator-runtime |
| Primary role | Browser QA, scheduled tasks, workflow execution |
| Integration | Built-in (OpenClaw runtime), health check via `openclaw status` |
| Cost model | Low (local execution) |
| Fallback chain | None (unique capabilities) |

**Recommendation:** OpenClaw is the operator runtime — LisaOS's execution engine for operational work. Unlike other runtimes, OpenClaw is not primarily an AI model runtime; it's a task execution engine that coordinates other tools (Playwright, Cron, Skills). Its profile is unique: no other runtime provides browser automation or scheduled task execution.

---

## 7. Future Runtime Addition Process

Adding a new runtime follows a standardised process:

1. **Define capability profile** — Document what the runtime can do in `runtime/providers/<name>.md`
2. **Register in runtimes registry** — Add to `registry/runtimes.yml` with profile, capabilities, cost tier
3. **Define health check** — Document how the resolver queries availability
4. **Set fallback chain** — Determine which existing runtimes this runtime falls back to
5. **Update agent fallbacks** — If the runtime fills an existing profile, update agents that should use it
6. **Benchmark** — Run the standardised benchmark suite to establish baseline performance
7. **Set initial status** — `experimental` until proven
8. **Promote to active** — After benchmark pass, health check stability, and capability verification

Each addition requires an ADR documenting the integration decision.

---

## 8. Weaknesses and Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Health check failure provides false positive | Medium | Implement staggered health checks with timeout, cache results for 30s |
| Scoring weights biased toward GPT | Low | Weights are documented and adjustable; benchmark data will correct bias |
| New runtime credential management | Medium | Credentials stored in environment variables, not registry files; document in provider docs |
| Cost model shifts mid-job (e.g., price increase) | Low | Cost tier is a static registry value; price changes require registry update |
| Fallback chain creates cascade failure | Medium | Implement circuit breaker: if primary + first fallback fail, wait before trying more fallbacks |
| Benchmark data never collected | Medium | Include benchmark collection as a default step in the nightly health job |

---

## 9. Dependencies on Existing Registries

| Registry | Field Used | Resolution Step |
|----------|-----------|-----------------|
| `registry/jobs.yml` | `default_agent`, `required_capabilities` | Step 1-2 |
| `registry/agents.yml` | `preferred_runtime`, `runtime_profile`, `fallback_runtimes` | Step 3 |
| `registry/capabilities.yml` | `risk_level`, `allowed_by_default` | Step 2 |
| `registry/runtimes.yml` | `runtime_profile`, `capabilities`, `cost_tier` | Step 3-4 |
| `lisaos/policies/routing.yml` | `job_types` | Step 1 |

---

## Related Documents

- `docs/LISAOS/LISAOS_RUNTIME_SELECTION_POLICY.md` — Detailed runtime selection policy
- `docs/LISAOS/KERNEL.md` — LisaOS Kernel (section 3.5 Runtime Resolver)
- `docs/LISAOS/KERNEL_DECISIONS.md` — ADR-K004 (Runtime Resolution), ADR-K007 (Model Agnostic)
- `registry/runtimes.yml` — Runtime definitions
- `registry/agents.yml` — Agent runtime profiles and fallbacks
- `runtime/resolver/README.md` — Future resolver specification
- `runtime/providers/` — Per-runtime provider documentation
- `docs/ADR/ADR-0001-ENGINE-ABSTRACTION.md` — Engine abstraction ADR
- `docs/ADR/ADR-0002-CAPABILITY-ROUTING.md` — Capability routing ADR
