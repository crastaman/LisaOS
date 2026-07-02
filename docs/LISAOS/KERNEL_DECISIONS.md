# LisaOS v3 — Kernel Architecture Decisions

**File:** `docs/LISAOS/KERNEL_DECISIONS.md`  
**Status:** Active  
**Last updated:** 2026-07-02

This document records architectural decisions made while designing the LisaOS Kernel. Each decision captures the context, options considered, and rationale for the chosen approach.

---

## ADR-K001: File-Based Job Queue

**Context:** The Kernel needs a job queue. Options include a file-based system (YAML files in `lisaos/jobs/`), an in-memory queue, a database-backed queue, or a message broker (Redis, NATS).

**Decision:** Use a file-based job queue with three YAML files: `queue.yml`, `active.yml`, `completed.yml`.

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **File-based** (chosen) | Zero infrastructure, Git-trackable, human-readable, works without network | No concurrency, no built-in TTL, no pub/sub |
| In-memory | Fast | Lost on restart, no durability |
| Database-backed | Durable, queryable, concurrent | Requires database, tight coupling to WBS schema |
| Message broker | Pub/sub, scalable, TTL capable | Infrastructure dependency, over-engineering for current scale |

**Rationale:**
- The file-based queue is appropriate for the current single-operator scale.
- Git history provides free audit trail (every state change is a commit).
- Moving to a distributed queue later is a localised change (only the Queue component).
- The queue interface is defined by `lisaos/bin/lisa-job-create.sh`; swapping the backend does not change the interface.

**Consequences:**
- File locking must be considered for concurrent access (currently single-operator, so not an issue).
- Queue size is bounded by file size; archive jobs must be pruned periodically.
- The Kernel design abstracts the queue behind an interface, making future migration straightforward.

---

## ADR-K002: Context Priority Chain with Temporary Chat Context

**Context:** The Context Loader must assemble relevant context from multiple sources. Chat history is the most immediately available but also the least reliable source of truth.

**Decision:** Establish a fixed priority chain with conversation context at the bottom (temporary only).

**Priority order:**
1. Current Job Packet (highest priority, most specific)
2. Current Repository
3. LisaOS Documentation
4. Business Rules
5. Architecture Documents
6. Historical Reports
7. Conversation Context (lowest priority, temporary)

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **Priority chain** (chosen) | Deterministic, predictable, documentation-driven | Slightly more complex to assemble |
| Flat context dump | Simple | No priority signal, token waste, chat history dominates |
| Context weighted by recency | Catches recent decisions | Rewards recency over documentation — anti-pattern |

**Rationale:**
- Documentation must be authoritative, not conversation history.
- Chat history is ephemeral by nature — it contains dead ends, false starts, and temporary state.
- A fixed priority chain means the Kernel produces the same context for the same job ID, regardless of which session or agent processes it.
- Reproducibility is critical for audit and governance.

**Consequences:**
- Chat history should be truncated aggressively (max 4096 tokens, or fewer).
- The Context Loader must explicitly tag conversation context as "temporary — not authoritative."
- Agents must be instructed to prefer documented sources over conversational hints.

---

## ADR-K003: Capability Resolution at Route Time, Not at Agent Init

**Context:** When should capabilities be resolved? Options include: at agent initialisation (agent self-describes capabilities), at job creation (capabilities locked at queue time), or at route time (resolved when the job is dispatched).

**Decision:** Resolve capabilities at route time, immediately before dispatch.

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **At route time** (chosen) | Fresh capability state, respects routing rule changes, least privilege per dispatch | Slightly more latency at dispatch time |
| At agent init | Simple, agent owns its capabilities | Stale capabilities, agent could self-edit, violates least privilege |
| At job creation | Consistent for job lifetime | Cannot adapt to routing rule updates, capability changes during queue wait |

**Rationale:**
- Capabilities are an OS-level concept, not an agent-level concept. Agents should not self-determine their capabilities.
- Route-time resolution allows the Capability Resolver to enforce least privilege based on the specific job type and packet, not just the agent role.
- If a capability is revoked while a job is queued, the job gets the current (restricted) capability set at dispatch time.

**Consequences:**
- The Capability Resolver must be fast (sub-second).
- `docs/LISAOS/CAPABILITIES.md` + `docs/LISAOS/AGENTS.md` are the authoritative sources; they are read at route time.
- The resolved capability envelope is immutable for the job's execution lifetime.

---

## ADR-K004: Runtime Resolution with Health Checks and Fallback Chain

**Context:** How should the Kernel select which model/runtime to use for a job? Options include: hardcoded per agent, single fallback, or ordered fallback chain with health checks.

**Decision:** Use an ordered fallback chain with health checks and cost awareness.

**Resolution logic:**
1. Look up preferred runtimes from routing rules (ordered by priority)
2. Check each runtime's health (`/status` or equivalent)
3. If healthy: select it; if not: try next in chain
4. When multiple healthy runtimes exist at the same priority: prefer lower-cost

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **Fallback chain with health checks** (chosen) | Most reliable, cost-aware, graceful degradation | Requires health check infrastructure |
| Hardcoded per agent | Simple, zero overhead | Brittle, no adaptation to outages |
| Single fallback | Better than hardcoded | Still fragile, no cost awareness |
| Round-robin across all healthy | Load-balanced | No capability match, no cost awareness |

**Rationale:**
- AI providers have different reliability profiles (rate limits, outages, deprecations). A fallback chain absorbs these gracefully.
- Health checks prevent dispatching to a rate-limited or unavailable runtime, reducing failure retries.
- Cost awareness is essential for long-term sustainability — the Kernel should prefer lower-cost options when capability requirements are met.

**Consequences:**
- Each runtime must expose a health endpoint or CLI command returning availability, rate-limit status, and latency.
- The routing-rules.yml file defines the fallback chains explicitly.
- Health check failures are logged and may trigger alerts if sustained.

---

## ADR-K005: Separate Validation Pipeline Stages, Modular and Job-Type-Aware

**Context:** How should validation be structured? Options include: a single monolithic validation, sequential stages, or parallel modular stages.

**Decision:** Sequential modular validation stages with per-stage skip logic.

**Stages (in order):**
```
Static Review → Tests → Browser QA → Regression → Security → Governance
```

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **Sequential modular stages** (chosen) | Clear progression, failure-isolating, skip-able, extensible | Linear build-up of latency |
| Monolithic validation | Simple, one pass | No granularity, cannot skip, failure in one area blocks others |
| Fully parallel | Fastest | Coordination complexity, race conditions, security must gate others |

**Rationale:**
- Sequential stages allow early failures to be caught before expensive stages run (e.g., fail static review before browser QA).
- Modular stages mean a new validation type (e.g., accessibility audit, performance benchmark) can be added without modifying other stages.
- Skip logic avoids unnecessary execution (e.g., a `CHEAP_ANALYSIS` job does not need Browser QA or Regression).
- Security and Governance are intentionally last — they act as a final check over all preceding work.

**Consequences:**
- Each stage must produce a standardised PASS/FAIL result.
- Stage results are composable into the governance audit.
- Stage ordering is documented in the Kernel, not hardcoded in agents.

---

## ADR-K006: Human Approval as Final Gate for All Risky Operations

**Context:** Which jobs need human approval? Options include: all jobs, only production-impacting jobs, or only security jobs.

**Decision:** Require human approval for all job types except non-impacting documentation and analysis (where automatic approval is allowed if validation passes).

**Approval categories:**
| Category | Jobs | Approver |
|----------|------|----------|
| **Required** | ENGINEERING, ENGINEERING_GLM, RELEASE, SECURITY, GOVERNANCE, QA_BROWSER | Roshan |
| **Automatic** (if validation passes) | DOCS, CHEAP_ANALYSIS, LARGE_ANALYSIS, MEMORY | Pipeline |

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **Required for risky, automatic for safe** (chosen) | Appropriate friction per job type, fast path for low-risk work | Requires classification of "safe" vs "risky" |
| All jobs require human approval | Maximum safety | Bottleneck — human becomes the blocker for everything |
| Fully automatic | Fast, zero friction | Unacceptable risk for production code |
| Approval by agent (automated review as approval) | Fast | Abrogates human authority |

**Rationale:**
- Human (Roshan) retains final authority over the system. No automated gate bypasses this.
- Low-risk jobs (documentation, analysis, memory curation) are gated by the validation pipeline alone, as their failure modes are self-reversing (revert the doc change).
- High-risk jobs (code, security, deployment, governance decisions) require explicit human sign-off because their failure modes have real-world impact.
- The Approval Gateway presents a consistent, structured approval request to minimise friction.

**Consequences:**
- The approval request must be concise but complete (job ID, type, agent, runtime, duration, artifacts, validation results).
- Rejected jobs return to the queue with a reason, not to the garbage.
- A rejected job can be fixed and re-dispatched as the same job ID.

---

## ADR-K007: Agents Are Model-Agnostic — No Runtime Logic Inside Agents

**Context:** Should agents know which model/runtime they are running on? Should they adjust behaviour based on the runtime?

**Decision:** Agents must never contain runtime-specific logic. The Runtime Resolver is the only component that selects runtimes.

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **Agents are model-agnostic** (chosen) | Clean separation of concerns, agents are truly replaceable | Requires the Runtime Resolver to be thorough |
| Agents can suggest runtimes | Flexible | Violates separation of concerns, agents become coupled to runtime specifics |

**Rationale:**
- If an agent contains logic like "if running on Codex, do X; if running on Claude, do Y," then replacing a runtime means changing every agent that references it.
- Model-agnostic agents can be tested with any runtime, proven compatible, and swapped freely.
- All runtime intelligence lives in one place: the Runtime Resolver + routing-rules.yml + runtimes.yml.
- This is consistent with the Kernel principle: the OS selects runtimes, agents perform work.

**Consequences:**
- Agent definitions (AGENTS.md) do not include runtime-specific instructions.
- Agent context packs only specify "required capabilities" and "job type."
- The Runtime Resolver must ensure the selected runtime can satisfy all required capabilities before dispatch.

---

## ADR-K008: Git as Authoritative History — Audit Trail Through Commits

**Context:** How should the Kernel audit trail be stored? Options include: a separate audit database, log files in `logs/`, the YAML job files, or Git commits.

**Decision:** Use Git commits as the authoritative audit trail, augmented by YAML job records and a future audit archive.

**Audit storage layers:**
1. **Git commits** — Every state change (job created, dispatched, completed) leaves a commit or commit-adjacent record
2. **YAML job files** — `queue.yml`, `active.yml`, `completed.yml` provide current state
3. **Future audit archive** — `lisaos/jobs/audit/` for historical records beyond the active job files

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **Git as authority** (chosen) | Immutable, time-stamped, distributed, recoverable | Not queryable without git log |
| Database | Queryable, concurrent | Single point of failure, backup overhead, coupling |
| Log files only | Simple | No structure, easy to lose, no integrity check |

**Rationale:**
- The repository already uses Git for history. Using Git for job state tracking is consistent with the existing model.
- Git commits are immutable — once a job is completed, its record cannot be tampered with without changing Git history.
- Git is distributed — the full audit trail exists in every clone.
- The YAML job files provide the queryable state; Git provides the history.

**Consequences:**
- The Kernel should commit job state changes when practical (not on every heartbeat — only on state transitions).
- `completed.yml` grows over time and should be pruned to an `audit/` archive.
- Future tooling (e.g., job search) will need to index the audit archive.

---

## ADR-K009: Kernel Is the Permanent Operating Model — Not a Temporary Design

**Context:** Is the Kernel a temporary scaffolding that will be replaced, or a permanent architectural foundation?

**Decision:** The Kernel is the permanent operating model for LisaOS v3. It evolves through additive changes, not replacement.

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **Permanent model** (chosen) | Stability, predictability, documented expectations for all components | Must be maintained and kept current |
| Temporary scaffolding | Faster to build, iterate | No foundation, every change risks breaking the model, confusion |

**Rationale:**
- A permanent operating model means everyone (human, agents, OpenClaw, runtimes) knows how work flows through the system. The model is the shared mental model.
- "Permanent" does not mean "static." The Kernel evolves through documented ADRs, new job types, new capabilities, and new runtimes — all without changing the Kernel architecture.
- A temporary model creates uncertainty: "When will this be replaced? Should I design for the new one?" The permanent model removes this uncertainty.

**Consequences:**
- Any change to the Kernel's component architecture or job lifecycle requires an ADR.
- The Kernel documentation is kept current with every evolution.
- New features are added within the Kernel's existing framework, not as parallel systems.

---

## ADR-K010: Future Compatibility Built In, Not Bolted On

**Context:** Should the Kernel design account for future scenarios (distributed workers, cloud execution, commercial LisaOS) now, or wait until they are needed?

**Decision:** Design the Kernel with future compatibility in mind, but do not implement infrastructure for unneeded scenarios.

**What was designed for future:**
- Component interfaces abstracted behind contracts (Queue, Resolver, Dispatcher)
- Runtime resolution is already multi-runtime
- Job type system is extensible
- Context assembly is modular and prioritised
- Validation stages are modular and skip-able
- Audit trail design supports distributed aggregation

**What was NOT implemented for future:**
- No distributed queue infrastructure (Redis, NATS)
- No multi-tenant isolation
- No cloud worker registration
- No commercial billing integration
- No API server

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **Designed for future, implemented for now** (chosen) | Clean evolutionary path, no wasted infrastructure | Slightly more abstract design than minimal viable |
| Implement now for every future scenario | Future-proof | Over-engineering, YAGNI violation |
| Wait until needed, design then | Minimal upfront cost | Risk of architectural mismatch, hard-to-adapt interfaces |

**Rationale:**
- The interface abstraction costs very little (documented contracts, not code). It is not over-engineering.
- Implementing distributed infrastructure now would be a YAGNI violation — no current need.
- The Kernel's job lifecycle, component responsibilities, and interface contracts are future-compatible by design without requiring future-proofing infrastructure.

**Consequences:**
- New deployment scenarios (cloud, distributed, commercial) can use the same Kernel with different backends.
- The Kernel documentation serves as the specification for future implementations.
- No code changes are needed to adopt future scenarios; only infrastructure changes.

---

## ADR-K011: Repository Documentation Is Truth — Always Preferential

**Context:** The Kernel must decide what constitutes "truth" when resolving context. Options include: conversation state, agent memory, repository documentation, or a weighted combination.

**Decision:** Repository documentation (Git-tracked files) is the sole authoritative truth. All other sources are secondary.

**Enforcement:**
- Context Loader ranks repository documentation above conversation context (per ADR-K002).
- Memory Writer only writes to Git-tracked documentation, never to conversation state.
- Agents are instructed to prefer documented sources over conversational hints.
- Chat history is explicitly tagged as "temporary — not authoritative."

**Options considered:**
| Option | Pros | Cons |
|--------|------|------|
| **Repository docs as truth** (chosen) | Durable, reviewable, versioned, consistent across sessions | Requires discipline to keep docs current |
| Agent memory as truth | Fast to access | Fragile, session-scoped, not shared, lost on restart |
| Weighted combination | Flexible | Non-deterministic, inconsistent between sessions |

**Rationale:**
- The repository is the single source that every agent, every session, and every human can access consistently.
- Documentation in Git is versioned (ADR history), reviewable (PRs), and recoverable (reverts).
- If documentation is stale, the fix is to update the documentation — not to work around it with conversation history.
- This principle was established in MANIFEST.md and is now formally encoded in the Kernel.

**Consequences:**
- Outdated documentation causes incorrect context resolution — the fix is always documentation update.
- The Kernel's Context Loader explicitly excludes non-documented sources from durable context.
- Agents must be reminded in every dispatch that repository documentation is authoritative.

---

## Related

- `docs/LISAOS/KERNEL.md` — The Kernel architecture this document supports
- `docs/DECISIONS/` — Other Architecture Decision Records
- `docs/LISAOS/MANIFEST.md` — LisaOS v3 architecture overview
