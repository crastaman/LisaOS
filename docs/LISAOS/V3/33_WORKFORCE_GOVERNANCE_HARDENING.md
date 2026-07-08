# Workforce Governance Hardening (post-closure patch)

**Status:** Complete. **Date:** 2026-07-08
**Category:** Regression-adjacent governance hardening. **Not Phase 4** — LisaOS
3.0 core (Phases 0–3) remains closed per `LISAOS_3.0_CLOSURE_REPORT.md`; this
patch falls under the closure's permitted "bug fixes, regressions, WBS-driven
improvements" carve-out.
**Files:** `core/workforce_resolver.py` (additive), `core/anti_regression.py`
(additive), `core/governance_guard.py` (new), `bin/lisa-governance-check`
(new), `governance/GOVERNANCE.md` (rule 12 added).

---

## 1. Trigger

A CTO-style incident report described four WBS Upgrade Framework Phase 2
tasks (Safety Constitution, Fingerprint Engine, Backup Manager, Upgrade
Executor) that were planned for Opus/Qwen/DeepSeek/GPT-Governance per role,
but a `/subagents` listing showed all four resolving to `deepseek-reasoner`.

## 2. What was verified before any code changed

The incident, taken literally, **did not match this repository's evidence**:

- `reports/lisa/workforce_evidence.jsonl` (38 real records at review time) —
  `chief-architect` resolved to `claude-opus` 10/10 times; no record of a
  role collapsing onto DeepSeek.
- No file, transcript, or evidence record anywhere under `~/Lisa` or
  `~/.claude` referenced `impl-safety-constitution`,
  `impl-fingerprint-engine`, `impl-backup-manager`, or
  `impl-upgrade-executor`.
- `chief-architect` / `cto-reviewer` are configured `fallback_models: []`,
  `failure_policy: halt-and-surface` — the code path that would need to
  exist to silently downgrade them does not exist
  (`core/workforce_resolver.py`'s `resolve()` raises
  `WorkforceResolutionError` instead).

**The real, confirmed gap:** `core/dispatcher.py` → `core/workforce_resolver.py`
is the only governed delegation path in this repo. Nothing wires Claude
Code's native subagent tool through it. If a subagent is spawned directly —
by name, outside `lisa-dispatch` — it gets none of the affinity enforcement,
fail-closed resolution, or evidence recording that `core/workforce_resolver.py`
guarantees, because it never calls into that module at all. That is a real
architectural hole, independent of whether the specific incident described
actually happened.

## 3. Fix objective

> No delegated production work may execute outside the LisaOS dispatcher /
> WorkforceResolver path.

Codified as rule 12 in `governance/GOVERNANCE.md`.

**Honest limitation, stated up front:** this cannot be enforced by
*prevention* from within this repo. The Claude Code harness that spawns
subagents runs outside `~/Lisa`'s process boundary; no Python code here can
intercept or block that spawn. The only implementable enforcement is
**detect, record, and fail closed on the next governed run until an operator
explicitly acknowledges it** — the same posture this repo already takes
toward capacity exhaustion and probation (Phase 3): governance by structural
fail-closed default, not by physical prevention where physical prevention
isn't reachable.

## 4. What shipped

### 4.1 `WorkAssignment.fallback_level` / `.operator_approval_required`

Two new fields on the Phase 1 `WorkAssignment` dataclass
(`core/workforce_resolver.py`), computed in `WorkforceResolver.resolve()`:

- `fallback_level: int | None` — the accepted model's position in
  `employee.model_chain()` (0 = preferred, 1+ = nth fallback). `None` when
  resolution failed closed (no successful assignment to rank).
- `operator_approval_required: bool` — `True` iff `fallback_level > 0` and
  `work_package.risk != "low"`. Low-risk fallback (e.g. GLM-turbo microtask
  substitution) is routine and does not need a human in the loop; any
  fallback on `normal`/`critical`-risk work is a deviation from the plan and
  is flagged for review.

`chief-architect` / `cto-reviewer` cannot produce `operator_approval_required
= True` from a downgrade, because their empty `fallback_models` chain means
they either land at level 0 or raise — consistent with the pre-existing
`halt-and-surface` invariant, not a new behaviour.

### 4.2 Workforce evidence report format

`core.workforce_resolver.format_assignment_report()` renders one assignment
in the requested standing format:

```
Planned Worker: qwen-deepinfra
Actual Worker: claude-haiku
Reason: preferred qwen-deepinfra unusable; explicit employee fallback -> claude-haiku
Fallback Level: 2
Operator Approval Required: Yes
```

Pure display transform over the recorded `WorkAssignment` — no second source
of truth.

### 4.3 `core/governance_guard.py` — bypass detection

New module, hermetic (no import of `core.dispatcher`, same one-directional
dependency discipline as `core/anti_regression.py`):

- `find_subagent_invocations(project_dirs)` — enumerates Claude Code's own
  `<project>/<session>/subagents/*` transcripts (read-only).
- `detect_bypass_violations(invocations, evidence_path=...)` — flags
  invocations whose name matches a production-shaped prefix
  (`impl-`, `build-`, `fix-`, `upgrade-`) with no corresponding
  `work_package_id`/`employee` in `workforce_evidence.jsonl`.
- `record_violations()` / `record_acknowledgement()` / `unacknowledged()` —
  append-only JSONL under `reports/lisa/` (gitignored, same as
  `workforce_evidence.jsonl`). An acknowledgement requires a non-empty
  `operator` — anonymous acknowledgement is rejected.
- `require_clean(project_dirs, ...)` — scans, records, and raises
  `GovernanceGuardError` if anything remains unacknowledged. Never silently
  continues.

**Stated limitation:** the production-name-prefix match is a best-effort
heuristic, not a proof. A subagent named outside those four prefixes evades
detection. Research/exploration subagents (e.g. `Explore`, general-purpose
search) are deliberately out of scope — they never needed WorkforceResolver
staffing in the first place, and flagging them would just be noise the
operator learns to ignore.

### 4.4 `core/anti_regression.py` — F6

`check_no_unacknowledged_bypass(violations)` — pure function, duck-typed over
anything exposing `.subagent_name` (same pattern as `check_mode_policy_respected`'s
`mode_registry` argument). Wired into `run_pre_sprint_gates()` via a new
`bypass_violations: Iterable[Any] = ()` keyword parameter — defaults to empty
so every existing caller (`bin/lisa-workforce gates`, existing tests) is
unaffected unless it opts in by passing `governance_guard.require_clean()`'s
result.

### 4.5 `bin/lisa-governance-check`

CLI mirroring `bin/lisa-workforce`'s conventions:

```
lisa-governance-check scan [project-dir ...]     # exit 3 if unacknowledged violations found
lisa-governance-check acknowledge <id> <operator> <reason>
```

Live-run against the real `~/.claude/projects` tree at patch time: **8
project dirs, 64 real subagent invocations, 0 production-shaped bypass
violations** — corroborating §2's finding that the specific incident
described did not occur via this mechanism, while leaving the general-purpose
detector in place for future runs.

## 5. Testing

Hermetic, no network/spend, matching the existing suite's fixture style:

- `tests/test_workforce_resolver.py` — 5 new tests (`TestFallbackLevelAndOperatorApproval`):
  preferred-model level 0/no-approval, normal-risk fallback level 2/approval
  required, low-risk fallback/no-approval, chief-architect never above level
  0, failed resolution has `fallback_level=None`.
- `tests/test_anti_regression.py` — 5 new tests: 3 direct
  (`TestNoUnacknowledgedBypass`) + 2 aggregator (`run_pre_sprint_gates`
  passes with no violations / fails with one, unaffected by pre-existing
  stale-alias test).
- `tests/test_governance_guard.py` — new file, 13 tests: scanning (3),
  detection (4: production-shaped+ungoverned, production-shaped+governed by
  `work_package_id`, production-shaped+governed by `employee`,
  non-production-shaped never flagged), acknowledgement + `require_clean`
  (6: passes clean, raises on violation, persists to disk, clears once
  acknowledged, rejects anonymous acknowledgement, append-not-truncate).

**Full suite: 220 pre-existing + 23 new = 243/243 passing.** (Verified by
diffing test counts with the new modules stashed out: baseline 220, +5
`test_workforce_resolver.py`, +5 `test_anti_regression.py`, +13
`test_governance_guard.py` = 243, matching the full `discover` run exactly.)
(`PYTHONPATH="$HOME/Lisa" python3 -m unittest discover -s tests`)

## 6. What did NOT ship (explicit, not hidden)

- **No structural prevention of native subagent spawning.** Stated in §3 —
  not achievable from within this repo's process boundary. If this needs to
  become a hard block rather than detect-and-acknowledge, it requires a
  change at the Claude Code harness level, outside LisaOS's scope.
- **`operator_approval_required` is recorded and reported, not gated.** It
  does not (yet) block a sprint the way `check_no_unacknowledged_bypass`
  does. Per the fix objective's explicit scope ("narrow governance hardening
  patch"), turning it into a blocking gate — requiring an acknowledgement
  record before an assignment with `operator_approval_required=True` is
  accepted — was treated as a follow-on, not bundled in here.
- **The bypass-name heuristic is a fixed 4-prefix allowlist**
  (`impl-`, `build-`, `fix-`, `upgrade-`), not configurable via registry/YAML
  the way `workforce_modes.yml` is. Hardcoded deliberately, to keep this
  patch narrow; if false negatives show up in practice, promoting it to data
  is a small additive follow-on, not a redesign.
