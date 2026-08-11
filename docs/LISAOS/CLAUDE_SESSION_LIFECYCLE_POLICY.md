# CLAUDE SESSION LIFECYCLE POLICY v1

**Status:** ACTIVE · **Owner:** LisaOS · **Date:** 2026-08-11
**Repository:** `~/Lisa` (branch `feature/lisa-console`)
**Applies to:** all Claude workforce dispatch (Opus/Sonnet/Haiku), MAIN orchestration, worker briefs, auto-resume, recovery
**Supersedes / tightens:** CWO-001 §8 session+cache optimisation (this policy is the normative rule; CWO-001 §8 remains the general cache-economy principle)

---

## 1. Evidence Basis

This policy converts the findings of the Claude historical context-bloat audit
into durable workflow rules. The audit remains historical evidence; this
document is the normative rule.

- **Evidence:** WBS048 `reports/s048-framework/evidence/CLAUDE-CONTEXT-BLOAT-AUDIT-2026-08-11.md`
- **Measured findings that drove the policy:**
  - Sonnet session `3884735d` chained 6 unrelated atomic tasks (P5-D-02, P5-D-03, P7-C-01, P5-D-06 ×3), 89 assistant calls, peak ~163,208 active tokens, ~7.04M cacheRead, 1 compaction — approximately 70–80% of the observed 8%→93% Claude usage spike was attributed to this misrouted/chained workload.
  - Opus session `a0dbbeae` reached ~287,964 active tokens — unrelated WBS048 reviews, CWO work and DeepSeek reviews chained; cacheRead/write ratio looked excellent while useful context discipline was poor.
  - Haiku session `a4e37de4` reached ~198,257 active tokens across multiple days and unrelated task families.
  - Retained tool results reached ~44k–89k bytes and were re-read by every subsequent turn.
  - **General finding:** a high cacheRead ratio does NOT by itself mean efficient Claude execution. Warm-session reuse is beneficial within coherent work; cross-task/cross-family session reuse creates context bloat and quota waste. **The correct unit of continuity is the TASK FAMILY.**

## 2. Canonical Session Principle

> **ONE ATOMIC TASK FAMILY = ONE CLAUDE SESSION**

A task family consists of:

- one atomic task;
- continuation of that exact task;
- rework/fix rounds for that task;
- verification follow-up directly associated with that task.

**Permitted reuse example:** `P5-D-06 → P5-D-06 R1 → P5-D-06 R2` (same family, provided context remains healthy).

**Prohibited reuse example:** `P5-D-02 → P5-D-03 → P7-C-01 → P5-D-06` — these are separate task families and require separate Claude sessions.

Do NOT assume adjacent task IDs mean the same family.

## 3. Hard Session Boundaries

A fresh Claude session MUST be created when ANY of these change:

- atomic task family;
- sprint/workstream;
- repository/project;
- worker identity;
- implementation → independent review;
- independent review → implementation;
- review family;
- provider/model identity;
- materially unrelated task domain.

A fresh session must ALSO be required after:

- Claude session-limit failure;
- known context contamination;
- invalid/mismatched session identity;
- recovery where session provenance cannot be trusted.

Claude sessions MUST NOT span:

- WBS046 → WBS047 → WBS048;
- WBS → LisaOS;
- implementation → independent review;
- WBS review → LisaOS/CWO review;
- WBS review → DeepSeek evaluation;
- or equivalent unrelated work families.

## 4. Session Identity

Session identity is derived from:

```
repository/project + sprint/workstream + employee + role + atomic_task_family
```

Examples:

- `wbs/wbs048/sonnet/implementation/p4-b-01`
- `wbs/wbs048/opus/review/p4-b`

Implementation: `core/session_policy.py` — `SessionKey` / `session_key_for()`. The key is compact, deterministic, and fail-safe (unknown components resolve to `unknown`). The key requirement: unrelated work cannot silently inherit a previous Claude session.

OpenClaw session-key integration: when a WorkPackage carries the identity tuple (`project`, `sprint`, `employee`, `role`, `task_family`), the dispatcher bridge (`core/openclaw_bridge.py`) derives the OpenClaw session key from `session_key_for()` instead of the legacy fresh-random key. Identity-absent legacy packages keep the legacy fresh-random key unchanged.

## 4a. MANDATORY WORKDIR INVARIANT (operational finding, 2026-08-11)

**Finding:** the clean benchmark exposed that fresh worker sessions may start in worker scaffolding rather than the target repository — fresh Opus sessions land in `~/.openclaw/workspace-lisa-claude-opus` (an empty scaffolding dir with no repo files). A review brief without an explicit workdir came back BLOCKED; the same brief with a `## WORKING DIRECTORY (MANDATORY)` block passed immediately.

**Invariant (durable, workforce-wide — not only Opus):**

1. **Every implementation/review brief MUST carry an explicit authoritative repository/workdir** (absolute path + `cd` instruction).
2. **Before worker execution, verify:** expected repository **==** actual target repository. Do NOT rely on warm-session memory to locate the repo.
3. **If the repository/workdir is absent or invalid: FAIL CLOSED** → `WORKDIR_MISSING` / `WORKDIR_MISMATCH` → **do not execute**.
4. Applies workforce-wide where appropriate (implementation AND review; all workers).

Implementation: `core/session_policy.py` — `WorkdirCheck` / `check_workdir()` (pure, fail-closed); `core/workforce_resolver.py` — `WorkPackage.repository`; `core/openclaw_bridge.py` — real executor verifies `check_workdir(expected=work_package.repository, actual=os.getcwd())` BEFORE dispatch and returns `fail-closed-workdir_missing` / `fail-closed-workdir_mismatch` ExecutionResults.

Expected identity tuple for identity-bearing WorkPackages now includes `repository`:

```
project / sprint / employee / role / task_family / repository
```

## 5. Context State Classification

Where telemetry permits, classify active Claude session context (`core/session_policy.py` `context_state()`):

| State | Threshold | Behaviour |
|-------|-----------|-----------|
| HEALTHY | < 80k | reuse permitted (boundaries permitting) |
| WARNING | 80–100k | reassess |
| WARNING (prefer fresh) | 100–120k | fresh session preferred unless same-family continuity materially benefits execution |
| RESET_REQUIRED | > 120k | do not start new work in that session |

These are operational thresholds, not mathematical absolutes. **TASK-FAMILY BOUNDARIES ARE AUTHORITATIVE** — a 40k session from the wrong task family must NOT be reused merely because it is below threshold.

If reliable active-context telemetry is unavailable: fail toward session isolation rather than indefinite reuse.

## 6. Compaction Policy

Compaction is NOT a substitute for proper session boundaries.

Allow compaction ONLY when:

- the worker remains on the same atomic task family;
- continuity is genuinely useful;
- context is approaching the operational threshold;
- starting fresh would materially lose useful working state.

If the task family changes: NEW SESSION. Do not compact an old unrelated session merely so it can continue serving new work. After a session-limit failure: invalidate that session for future unrelated dispatch.

## 7. Large Tool Output Policy

Prevent large tool outputs from remaining unnecessarily in Claude conversation context:

- test-suite output; PHPUnit output; shell logs; grep/search dumps; large diffs; generated reports; worker transcripts; large JSON; diagnostic output.

Preferred behaviour:

1. preserve the full output in an evidence/artifact file when needed;
2. provide Claude with a concise summary + result/status + relevant exceptions/failures + artifact path.

Operational target:

- normal retained tool result: ≤ ~20k;
- > ~30k: externalize/truncate unless full inline content is genuinely necessary.

Do NOT silently discard evidence — externalization must preserve access to the complete result. Do not implement arbitrary truncation that could hide test failures or review findings.

Implementation: `core/context_budget.py` — `externalize_large_output(content, artifact_dir=..., artifact_name=...)` writes the full output to `reports/artifacts/<name>-<ts>.txt` and returns a summary + path. On artifact-write failure it returns the full content unchanged (evidence never silently dropped).

## 8. Worker-Specific Rules

### Sonnet
- Default: one atomic task family per session.
- Permitted: same-task continuation/rework/verification.
- Prohibited: chaining unrelated implementation tasks simply to keep cache warm.
- Context guidance: < 80k HEALTHY; 80–100k WARNING/reassess; 100–120k prefer fresh; > 120k no new work. Task-family change requires fresh regardless of token count.
- After approximately 4–6 tool-heavy turns, reassess context even if exact token telemetry is unavailable.

### Opus
- Opus is primarily an independent high-reasoning/review lane.
- One coherent review family per session; never inherit implementation session history; fresh context for independent review.
- Never mix WBS review + LisaOS/CWO review + DeepSeek review.
- Normally no more than ~4 closely related review targets per review session; context threshold overrides target count. Four tiny related reviews may be acceptable; two very large reviews may require separation. Do NOT treat "4" as an unconditional allowance.
- Review independence is more important than cache warmth.

### Haiku
- Default: one task per session.
- Permitted: at most two genuinely tiny, closely related operations when context remains small.
- Do not maintain multi-day Haiku sessions.
- Do not carry planning/governance history into later mechanical tasks merely to preserve cache.

## 9. Routing Guard Integration

Preserve and integrate with the existing employee→runtime-agent routing safeguard (`bin/dispatch-guard.sh`).

Canonical mappings (unchanged):

| Employee | Runtime agent | Model |
|----------|---------------|-------|
| Sol | `lisa-codex-premium` | `openai/gpt-5.6-sol` |
| Terra | `lisa-codex-balanced` | `openai/gpt-5.6-terra` |
| Luna | `lisa-codex-fast` | `openai/gpt-5.6-luna` |
| Opus | `lisa-claude-premium` | `anthropic/claude-opus-4-8` |
| Sonnet | `lisa-claude-balanced` | `anthropic/claude-sonnet-4-6` |
| Haiku | `lisa-claude-fast` | `anthropic/claude-haiku-4-5` |
| Pro | `lisa-deepseek-pro` | `custom-api-deepseek-com/deepseek-v4-pro` |

Before Claude session selection occurs, worker identity must already have passed routing validation. A session belonging to Sonnet must never be reused for Terra. A session belonging to Opus must never be reused for Sonnet. Equivalent cross-worker/provider mismatches must fail closed. This policy does NOT weaken the routing guard added after the Terra→Sonnet incident.

## 10. Recovery / Compact / Auto-Resume

Session identity must survive or be safely reconstructed across: MAIN compact, MAIN recovery, auto-resume, gateway restart, OpenClaw restart where applicable.

If Lisa cannot prove that a recovered Claude session still belongs to the exact project + sprint + worker + role + task family, use a fresh Claude session. Fail safe toward fresh context.

Auto-resume must NOT attach a new task to whatever Claude session happened to be warm previously. The session key (project/sprint/employee/role/task_family) is the single source of truth; absence of a provable key ⇒ fresh session.

## 11. Telemetry

For each Claude session/dispatch, capture where available (existing evidence/logging architecture; None when unavailable — never fabricated):

- employee; provider/model; project/repository; sprint/workstream; role; atomic task family;
- Claude session ID; NEW or REUSED; reason for reuse/new session;
- approximate starting active context; approximate peak active context;
- cacheRead; cacheWrite/cacheCreation; output tokens;
- compaction occurrence; reset reason; task outcome.

Implementation: `core/workforce_metrics.py` — `DispatchMetrics.session_fresh_reused` (fresh/reused counts) and `session_reuse_reasons` (Lifecycle v1 reason counts); token totals already captured None-safe.

## 12. Efficiency Metrics

Do not optimize purely for cache-hit percentage — high cacheRead can coexist with severe context bloat. Where practical, future analysis should be able to calculate:

- completed/accepted tasks per Claude session;
- cacheRead per accepted task;
- context growth per atomic task;
- output tokens relative to active context;
- review findings per review session;
- failed/retried work per session.

Store sufficient raw evidence for later calculation. No analytics subsystem.

## 13. Traceability

- Evidence: WBS048 `reports/s048-framework/evidence/CLAUDE-CONTEXT-BLOAT-AUDIT-2026-08-11.md`
- Implementation: `core/session_policy.py`, `core/context_budget.py`, `core/workforce_metrics.py`, `core/openclaw_bridge.py`, `core/workforce_resolver.py`
- Tests: `tests/test_session_lifecycle.py`
- ADR: NOT required — this is a workflow/governance policy within existing architecture (no new architectural decision; it tightens CWO-001 §8 with task-family identity + enforcement).

## 14. MANDATORY WORKDIR — Brief Template Requirement

Every implementation/review brief MUST contain the following block (exact wording):

```
## WORKING DIRECTORY (MANDATORY)

All work MUST happen against the authoritative repository at:

    <ABSOLUTE REPO PATH>

Run `cd <ABSOLUTE REPO PATH>` FIRST. If your default working directory is not
this repository, `cd` into it before any verification or modification step.
```

The dispatcher must verify (before execution) that the worker's runtime workdir equals the declared repository. If the brief omits the block, or the worker's actual workdir differs: FAIL CLOSED (`WORKDIR_MISSING` / `WORKDIR_MISMATCH`), no execution.
