# CTO Architecture Validation — OpenClaw Multi-Agent vs Subagent Alignment

**Role:** Independent CTO / Architecture Authority · **Mode:** read-only validation (not bug-finding) · **Date:** 2026-07-11
**Grounding:** current `core/openclaw_bridge.py`, live `openclaw agents list`, `task_runs`/`subagent_runs` schema + rows.

---

## Verdict (one line)

**The remediation converged onto native OpenClaw *identity* correctly, and its *dispatch* already uses a native OpenClaw primitive — the top-level agent turn (`openclaw agent`) — which is the RIGHT primitive for Lisa, not a reimplementation of subagents. Subagents would be the *wrong* convergence for Lisa's design, and the proposed "OpenClaw Subagent Session" layer in the target architecture should NOT be adopted.**

---

## The core misconception to retire

The concern assumes two native delegation options, and that Lisa should use `sessions_spawn(agentId=...)`. But those two primitives serve two *different callers*:

| Primitive | Caller it's designed for | Where it lands |
|---|---|---|
| **Subagent** (`sessions_spawn`/`subagents` tool, `agentId=…`) | an **OpenClaw agent (an LLM)** that decides *at runtime* to delegate, and wants results returned to itself as parent | `subagent_runs` (with `controller_session_key` = parent) |
| **Agent turn** (`openclaw agent --agent X`) | an **external programmatic caller** invoking an agent identity directly via the Gateway | `task_runs` (with `agent_id`, `parent_task_id`, `requester_agent_id`) |

**Lisa's coordinator is not an OpenClaw agent. It is deterministic Python (the dispatcher/resolver).** It decides identity *before any agent runs*, from capability + cost + policy. That is exactly the caller the **agent-turn** primitive exists for — and exactly *not* the caller subagents assume.

Using `sessions_spawn` would require Lisa to put a coordinator **agent** (an LLM) in the loop to do the spawning — i.e. re-introduce the very `main`-as-coordinator that caused S036a (an LLM picking models/personas at runtime). The remediation's whole point was to move the coordination brain *out* of an LLM agent and into deterministic code. So the bridge's use of `openclaw agent` is not a failure to converge — **it is the correct convergence for an out-of-band coordinator.**

Empirically confirmed: the 5 identity probes are `task_runs` rows (`agent_id=lisa-*`); the bridge creates **zero** `subagent_runs`. `task_runs` carries lineage (`parent_task_id`, `parent_flow_id`, `requester_agent_id`, `terminal_outcome`), so nothing attribution-critical is lost by not using `subagent_runs`.

---

## A. Architecture Alignment Matrix

| Concern | Native OpenClaw | Current LisaOS | Alignment |
|---|---|---|---|
| **Agent identity** | isolated agent (workspace/model/session/auth boundary) | dedicated `lisa-*` agent per logical identity | **FULLY NATIVE** — adopted, not recreated |
| **Model selection** | per-agent pinned model; `--model` override rejected | select the agent whose pinned model = the identity's model | **FULLY NATIVE** |
| **Task spawning** | (a) subagent under an agent, or (b) top-level agent turn | top-level agent turn (`openclaw agent --agent X`) | **NATIVE** — uses primitive (b), appropriate for an external coordinator |
| **Worker delegation decision** | none — an LLM agent decides ad hoc, or a human routes | deterministic capability→employee→identity in Python | **CUSTOM — no native equivalent** (correctly so) |
| **Routing** | bindings (inbound chat) + agent selection | deterministic logical→agent map + agent selection | **NATIVE selection + custom decision** |
| **Execution attribution (raw)** | `task_runs.agent_id`, `--json` `agentMeta` (provider/model/usage), `executionTrace`, lineage | surfaced from those native fields | **NATIVE data, surfaced** |
| **Intended-vs-actual verification** | none — OpenClaw records what ran, not what *should* have | mismatch (R1/F7) + identity-chain (F8) + reconcile | **CUSTOM — no native equivalent** (Lisa's core value) |
| **Workforce policy / governance / cost / capacity** | none | employees, modes, capacity ledger, approval/escalation | **CUSTOM — permanent** |

---

## B. Duplication Analysis

| Candidate | Verdict |
|---|---|
| Dedicated identity agents vs native agents | **Not duplication** — this IS the native primitive, adopted. |
| Bridge dispatch vs native subagent spawning | **Not duplication** — different native primitive (agent turn), not a hand-rolled spawner. The bridge shells out to the Gateway's own agent RPC. |
| Lisa attribution capture vs native metadata | **Partial, thin overlap** — Lisa reads both the `--json` response and `task_runs`. Each carries something unique (`executionTrace`/drift only in `--json`; durable `terminal_outcome`/status in `task_runs`), so it's two views, not redundancy. |
| `_physical_model_index` / observed-model re-derivation | **Mild redundancy** — now that dispatch is deterministic-by-identity and `agentMeta.model` is authoritative, the reverse index survives only for the drift check + label; the observed-model resolution could lean directly on `agentMeta`. Marginal. |

**No significant functional duplication.** The remediation did not rebuild OpenClaw delegation; it used a native surface and added the decision + verification layers OpenClaw lacks.

---

## C. Unnecessary-Abstraction Analysis

| Layer | Necessary? |
|---|---|
| Deterministic logical→agent map | **Necessary** — it encodes Lisa's *intent*, which OpenClaw has no concept of; it's also what makes drift/identity-chain checkable. |
| Bridge (`build_real_executor`) | **Necessary but can thin** — it is the seam between the Python coordinator and the Gateway; see §9. |
| `openclaw agents list` re-derivation each dispatch | **Keep** — it's the live source of truth (avoids a stale hardcoded map); cheap. |
| Reverse physical-model index | **Trim candidate** — demote to drift-check-only or replace with `agentMeta`-based observed model. |
| Attribution guard + reconcile | **Necessary** — the intent-vs-actual comparison is inherently Lisa's. |

No layer is *unnecessary*; one (reverse index) is a trim candidate.

---

## Answers to the specific questions

**1. Are dedicated `lisa-*` agents the correct implementation of OpenClaw identity boundaries?** **Yes.** A dedicated agent per identity is exactly OpenClaw's identity primitive (isolated workspace/model/session). This is the single most correct part of the remediation.

**2. Should workforce identities be agents, personas, routing policies, or hybrid?** **Hybrid, and the current split is right:** the *execution identity* (Codex/GPT/…) is an **OpenClaw agent**; the *workforce role* (Architect/Builder/Reviewer…) is a **LisaOS policy** above it. Personas-only is the prohibited option (it caused S036a).

**3. Delegate via `sessions_spawn(agentId="lisa-codex")` or custom bridge dispatch?** **Neither framing is right.** The bridge is not "custom dispatch" — it calls the Gateway's native `openclaw agent` turn. And `sessions_spawn` is the wrong native primitive here (it presumes an LLM-agent coordinator). **Keep the top-level agent turn.**

**4. Does the implementation ultimately call native subagent spawning internally?** **No** — it calls `openclaw agent` (→ `task_runs`), not `sessions_spawn` (→ `subagent_runs`). Verified: 0 bridge-created `subagent_runs`.

**5. Should it?** **No.** Switching to subagents would require a coordinator *agent* (LLM) to host the spawns, re-introducing runtime model/persona discretion — the S036a failure mode the remediation eliminated. Top-level turns keep the coordinator deterministic and out-of-band.

**6. Does native OpenClaw already provide executing-agent identity, execution/provider/model metadata, and lineage?** **Yes** — `task_runs.agent_id` + `parent_task_id`/`requester_agent_id`/`terminal_outcome`, and the `--json` `agentMeta` (provider, model, usage) + `executionTrace`. Lisa *surfaces* this; it does not recompute execution truth.

**7. Which parts of Lisa's attribution remain necessary with native metadata?** The **intent** and the **intent-vs-actual comparison**: the deterministic map (defines the expected agent), `check_identity_chain` (F8), `check_no_execution_mismatch` (F7), the evidence log, and `lisa-reconcile`/`lisa-identity-check`. OpenClaw records *what ran*; only Lisa knows *what should have run* and enforces they match.

**8. Which parts are now redundant?** Only the **reverse physical-model index** as an observed-model source (native `agentMeta.model` is authoritative); it survives usefully only for the drift check. Minor.

**9. Can the bridge get thinner by delegating more to OpenClaw?** **Marginally.** Trim the observed-model re-derivation onto `agentMeta`; optionally collapse toward a single post-run read. The big thinning (removing reverse-match selection) already happened. The decision + verification core cannot move to OpenClaw — it has no home there.

**10. What must remain in Lisa permanently?** Workforce policy, role assignment (capability→identity), governance, approval chains, escalation, review policy, release approval, cost/capacity/health policy, and the intended-vs-actual reconciliation + gates. This is Lisa's reason to exist.

**11. Is `Policy → Agent Identity → OpenClaw Subagent Session → Physical Model → Attribution → Reporting` correct?** **No — the "Subagent Session" link is wrong.** Lisa uses top-level **agent turns** (`task_runs`), not subagent sessions (`subagent_runs`). Adopting a subagent-session layer would reintroduce an LLM coordinator. See the corrected target below.

---

## D. Recommended Target Architecture (correcting Q11)

```
LisaOS Workforce Policy            (custom, permanent)
  capability → employee → logical identity; cost/capacity/governance/approval
      │
      ▼  deterministic 1:1 logical → agent (registry `agent:` binding)
OpenClaw Agent Identity            (native — dedicated lisa-* agent)
      │
      ▼  openclaw agent --agent <lisa-*>   ← NATIVE GATEWAY AGENT TURN (not a subagent)
OpenClaw Agent Turn / task_runs    (native execution + attribution + lineage)
      │
      ▼  agent pinned model
Physical Model                     (native)
      │
      ▼  intent (expected agent) vs actual (agent_id / agentMeta / executionTrace)
Attribution Verification           (custom — F7/F8 gates, reconcile, identity-check)
      │
      ▼
Reporting
```

The only change from the proposed chain: **"OpenClaw Subagent Session" → "OpenClaw Agent Turn (task_runs)."** Everything else stands.

---

## E. Migration Recommendations

Small, optional, effort×benefit:

| # | Change | Effort | Benefit |
|---|---|---|---|
| 1 | Source `observed_model` from `agentMeta.model` + the agent's known pinned model; demote `_physical_model_index` to drift-check-only | Low | Low-Med (thins the bridge; removes the last reverse-lookup residue) |
| 2 | Document that `openclaw agent` (agent turn) — not subagents — is the sanctioned dispatch primitive, and why (out-of-band deterministic coordinator) | Low | Med (prevents a future "should we use subagents?" churn) |
| 3 | Leave dispatch mechanism as-is | — | — (it is already native and correct) |

**No structural migration is required.** The architecture is correct as-built.

---

## F. Explicit answers

**Did we implement the right solution?** **Yes.** Identity is fully native (dedicated agents); dispatch uses the correct native primitive for an external coordinator (agent turns, not subagents); the added layers (decision + verification) are the ones OpenClaw genuinely lacks. The remediation converged toward OpenClaw's intended identity model rather than duplicating it.

**Which parts should remain, simplify, or disappear?**
- **Remain (permanent):** dedicated identity agents; deterministic logical→agent map; workforce policy/governance/approval/escalation/review/release; intended-vs-actual gates (F7/F8), reconcile, identity-check.
- **Simplify:** observed-model derivation → lean on native `agentMeta`; demote the reverse index to drift-only.
- **Disappear:** nothing structural. The reverse-match *as a selection mechanism* already disappeared (that was the remediation).

**Did we converge onto OpenClaw, or recreate it?** **Converged.** The one thing that could look like "recreating subagents" — the bridge — is instead using a *different, more appropriate* native primitive, precisely because Lisa's coordinator is deterministic code rather than an LLM agent. Further simplification is possible but marginal; the design is sound and does not warrant a subagent migration.
