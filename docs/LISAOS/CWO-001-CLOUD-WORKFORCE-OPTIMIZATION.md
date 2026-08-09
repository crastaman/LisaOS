# CWO-001 — Cloud Workforce Optimization (LisaOS Policy)

**Status:** ACTIVE · **Owner:** LisaOS · **Date:** 2026-08-09
**Repository:** `~/Lisa` (branch `feature/lisa-console`)
**Applies to:** all LisaOS workforce dispatch, MAIN orchestration, worker briefs

---

## 1. Objective

MAXIMUM USEFUL ENGINEERING THROUGHPUT FROM THE CLOUD CAPACITY ROSHAN IS ALREADY
PAYING FOR — while minimizing unnecessary metered API spend, token consumption,
context, cache reconstruction, premium-capacity waste, duplicate work, MAIN
verbosity, worker verbosity, and rework caused by poor routing.

## 2. Active Cloud Workforce

| Worker | Family | Provider | Access | Cost model | Tier |
|--------|--------|----------|--------|-----------|------|
| Sol | OpenAI/Codex | OpenAI | subscription | subscription_capacity | premium |
| Terra | Anthropic | Anthropic | subscription | subscription_capacity | mid |
| Luna | OpenAI/Codex | OpenAI | subscription | subscription_capacity | fast |
| Opus | Anthropic | Anthropic | subscription | subscription_capacity | premium |
| Sonnet | Anthropic | Anthropic | subscription | subscription_capacity | mid |
| Haiku | Anthropic | Anthropic | subscription | subscription_capacity | fast |
| deepseek-main | DeepSeek | DeepSeek | metered | metered_api_capacity | main |

DeepSeek Pro: **NOT onboarded.** Local models: **NOT available** (schema
extensible; `local_future` mode fails closed).

## 3. Worker Identity Normalization

- LisaOS reasons in actual worker identities: **Sol, Terra, Luna, Opus, Sonnet,
  Haiku, deepseek-main**.
- Legacy/operational aliases (`premium`, `high`, `fast`, `codex-premium`,
  `codex-high`, `claude-premium`, ...) resolve through the explicit alias map in
  `registry/workforce_identity.yml` — backwards compatible, aliases never mutate
  canonical ids.
- **Concept separation:** worker ≠ provider ≠ access_mode ≠ cost_model.
- Unknown worker names fail closed (`WorkforceIdentityError`), never silently
  remapped to a default worker.

## 4. Cost / Capacity Model

### Subscription capacity (Codex, Claude)
- Already-paid → optimize **useful work per available allowance**, not public
  API price.
- Scarce even when marginal monetary cost is effectively zero:
  - do not unnecessarily conserve capacity that would otherwise expire
  - do not waste premium capacity on trivial work
  - use the lowest-capability worker likely to complete the task correctly
  - reserve stronger workers where their capability materially improves success
  - prioritize high-value eligible work as provider capacity approaches/reset
    windows (`CapacityLedger.capacity_near_reset`)

### Metered API capacity (DeepSeek MAIN)
- Optimize actual token expenditure aggressively — every unnecessary MAIN token
  has marginal monetary cost.

### Future local capacity
- Not active. Architecture supports clean future `cost_model: local` /
  `capacity_model: hardware`; no local workers onboarded.

## 5. Worker Specialization (initial routing hypotheses)

| Worker(s) | Best for |
|-----------|----------|
| Luna / Haiku | inventory, extraction, repetitive, evidence preparation, mechanical verification, simple tests, context preparation |
| Terra / Sonnet | normal production implementation, integration, investigation, routine review, medium-complexity engineering |
| Sol | complex implementation, risky refactoring, difficult debugging, lifecycle/integrity work, high-value engineering |
| Opus | independent architectural review, adversarial review, difficult reasoning, high-value independent verification |

- Do NOT assume same-tier workers are interchangeable — preserve model-family
  diversity (Codex↔Claude cross-family review used deliberately).
- Future telemetry/outcomes may refine specialization (CWO telemetry fields).

## 6. Context Budgeting — MAIN KNOWS BROADLY, WORKERS KNOW NARROWLY

Every worker dispatch uses the smallest sufficient work packet:

```
MISSION
RELEVANT CURRENT STATE
RELEVANT CONSTRAINTS
EXACT TASK
FILES / AREAS TO INSPECT
DEPENDENCIES
REQUIRED EVIDENCE
ACCEPTANCE CONDITION
STOP CONDITIONS
```

- Do NOT routinely copy full sprint histories, old worker conversations,
  unrelated findings, entire governance docs, giant prior reports, stale
  reasoning, or large chat transcripts.
- Reference authoritative repo artifacts (`docs/`, `reports/`, `registry/`,
  `tests/`, `core/`) instead of copying them.
- Hard budget: `core/context_budget.build_work_packet()` raises if a packet
  exceeds `DEFAULT_PACKET_BUDGET_CHARS` (12,000). Context is a budget.

## 7. Premium Context Protection

Before large Sol/Opus dispatches, consider whether a cheaper available worker
can narrow the problem first:

```
CHEAPER WORKER → investigate → locate files → reproduce → identify tests
→ identify constraints → create concise evidence/context packet

then: PREMIUM WORKER → high-value reasoning / implementation / review
```

NOT mechanically forced — direct premium dispatch wins when clearly more
efficient (`premium_prep_recommendation()` returns a hint, never a mandate).

## 8. Session + Cache Optimization

Make the S048 ~21M cacheWrite churn lesson durable (`core/session_policy.py`):

| Reuse session when | Fresh session when |
|--------------------|--------------------|
| next work genuinely related | work unrelated |
| cached context remains useful | context bloated |
| context remains clean | context stale |
| reuse avoids cache reconstruction | contamination risk |
| independence not required | independent review required |
| | compact fresh brief more efficient |

Optimize for **USEFUL RELEVANT CACHED CONTEXT**, not maximum session age.
Independent review NEVER reuses the implementer's working context.

## 9. Quiet MAIN / Executive Reporting Mode

DeepSeek MAIN does NOT narrate: polling, queue checks, dependency reasoning,
worker monitoring, routine provider checks, command narration, internal
planning, obvious next steps, repeated state.

Roshan receives reports ONLY for:
- meaningful completion
- meaningful provider exhaustion
- capacity becoming available where execution changes
- genuine blocker
- decision required
- governance/safety issue
- material failure
- material scope/state change
- approximately hourly unattended update when useful

Default output format:

```
COMPLETED
- material outcome

CAPACITY
- meaningful change only

NEXT
- one concise sentence if useful

DECISION
- only if required
```

If nothing important happened: **DO NOT REPORT.** Continue working.
(`core/reporting_policy.py` implements classification.)

## 10. Worker Output Economy

Worker completions focus on:
- result
- files changed/inspected
- tests/evidence
- blockers
- decisions required

Avoid long introductions, restating task briefs, narrating obvious work,
speculative essays, repetitive completion reports, copying evidence already
stored on disk. Engineering detail lives in CODE / TESTS / EVIDENCE ARTIFACTS.
Do NOT reduce required evidence quality — detailed evidence remains detailed on
disk; executive reporting remains concise.

## 11. Capacity-Aware Dispatch

Before material dispatch, consider (where information is available — never
invent unobservable metrics):
- actual worker/model · provider · task type · worker competence
- current provider availability · remaining subscription capacity
- reset timing where known · expected context size · cache/session opportunity
- expected output size · independence requirement
- probability of success · probability of rework
- cheaper-worker preparation opportunity

Gracefully degrade when capacity/token information is unavailable (all CWO
fields None-safe; `WorkforceResolver` without identity/capacity layers behaves
exactly as before).

## 12. Cross-Family Review

Codex/Claude diversity used intentionally:
- Codex implementation → Claude independent review
- Claude architecture/reasoning → Codex verification/implementation

Independent duplication must be justified by risk, architecture, governance,
uncertainty, or verification value — never automatic.

## 13. Telemetry (minimal)

Captured where the architecture permits (None when unavailable — never
fabricated):
- actual worker/model · provider · task classification
- fresh/reused session · input tokens · cached input · output tokens
- elapsed duration · completion status · review result · rework/failure
- provider exhaustion/reset state

Implemented in `core/workforce_metrics.py` (CWO fields on `DispatchMetrics`)
and `core/capacity_ledger.py` (reset timing). No analytics subsystem.

## 14. Implementation Surfaces

| Surface | Change |
|---------|--------|
| `registry/workforce_identity.yml` | NEW — canonical worker identity + alias map |
| `registry/provider_resolution.yml` | EXTEND — `codex-fast` logical provider (Luna → `lisa-codex-fast` → `openai/gpt-5.4-mini`, distinct from Sol's `openai/gpt-5.5`) |
| `core/workforce_identity.py` | NEW — identity resolver (normalise/resolve/capacity/DeepSeek-Pro guard) |
| `core/context_budget.py` | NEW — bounded work-packet builder + premium-prep hint |
| `core/session_policy.py` | NEW — session reuse/fresh decision policy |
| `core/reporting_policy.py` | NEW — executive reporting classification + worker output economy |
| `core/capacity_ledger.py` | EXTEND — reset-time observation + capacity-near-reset (tz-safe) |
| `core/workforce_resolver.py` | EXTEND — identity/capacity layers, capacity-aware ordering, assignment fields |
| `core/workforce_metrics.py` | EXTEND — CWO telemetry fields |
| `core/dispatcher.py` | EXTEND — telemetry wiring from ExecutionResult |
| `core/router.py` | EXTEND — default resolver CWO-aware |
| `tests/test_cwo_acceptance.py` | NEW — 39 tests for the 12 acceptance criteria (incl. F-1/F-3 regressions) |
| `docs/LISAOS/CWO-001-CLOUD-WORKFORCE-OPTIMIZATION.md` | NEW — this policy |

## 15. Acceptance (12 criteria)

1. actual model identities resolve correctly ✅ `WorkforceIdentityRegistry.resolve`
2. legacy aliases remain safe ✅ alias map + tests
3. subscription vs metered distinguishable ✅ `worker.is_subscription/is_metered` + ledger cost_class
4. worker context packets bounded/relevant ✅ `build_work_packet` hard budget
5. related-session reuse preferred ✅ `reuse_session(related=True, clean=True)` → REUSE
6. unrelated/independent work forces fresh ✅ `independence_required=True` → FRESH
7. premium dispatch can use prepared compact context ✅ `premium_prep_recommendation`
8. MAIN suppresses routine narration ✅ `classify_event` suppressed classes
9. material events surface ✅ `classify_event` reportable classes
10. unavailable telemetry doesn't break dispatch ✅ None-safe; legacy resolver unchanged
11. DeepSeek Pro not accidentally available ✅ `is_deepseek_pro` guard + registry absence
12. WBS repository untouched ✅ no WBS paths; WBS git state unmodified by this work

## 17. Review Record (2026-08-09)

- **Opus review #1** (`lisa-claude-premium`): VERDICT **PASS WITH CONDITIONS** — F-1 (MEDIUM: capacity_class/health_state transposed), F-2 (MEDIUM: Codex fast tier collapsed onto Sol's model), F-3 (LOW: tz-naive TypeError). Scope check: LisaOS-only, WBS untouched, no DeepSeek Pro, no local workers, fail-closed preserved, no fabricated telemetry. 12 criteria substantively met.
- **Corrections**: F-1 unpack order fixed + `test_capacity_fields_not_transposed`; F-2 `codex-fast` logical provider added (Luna → gpt-5.4-mini) + fixture updated; F-3 tz-naive → UTC + `(ValueError, TypeError)` caught + `test_capacity_near_reset_tz_naive_degrades`.
- **Opus re-verification**: VERDICT **PASS** — all three conditions confirmed fixed on disk; acceptance 39/39; full suite 922 passed + 26 subtests, 0 regressions. No new issues.

## 16. Out of Scope (per mission)

- DeepSeek Pro onboarding · local-model support beyond clean future extensibility
- unrelated LisaOS architecture redesign · WBS repository changes
- analytics subsystem beyond minimal telemetry
