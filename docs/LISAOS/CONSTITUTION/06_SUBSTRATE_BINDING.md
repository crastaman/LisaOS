# Substrate Binding — Constitution ↔ Gen 3 Components

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> No constitutional force until recorded human ratification of Constitution v2
> (Art. IX.3). Revising this document does not ratify it.

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r4 |
| Revision basis | r4 — remediation of the **independent Codex constitutional review** (OpenAI/GPT-5) as reconciled by the subsequent independent assessment: B1 ratification instrument specification, B2 execution-outcome evidence, B3 executor provenance and attribution truth, B4 identity and simulation classifications, B5 amendment precedence, plus the confirmed non-blocking findings (guard clearance, candidate substitution, incorporation boundary, planner/P4 coherence, approval authority, legacy entrypoints, threat-model completeness). The Codex review was **advisory** — it failed the six-condition test on evidence-baseline access only — and does **not** satisfy the independent constitutional gate. Prior: r3 — enforcement-honesty remediation of the Claude Fable 5 advisory audit (BF-1 PolicyEngine approval metadata; BF-2 registry-contingent no-downgrade; M2 caller-dependent guard invocation). That audit was **advisory** and does **not** satisfy the independent constitutional gate. Prior: r2 — remediation of author self-audit S044 (B3 fail-closed semantics alignment; enforcement rows added for the r2 clauses) |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report — `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md` (Phase 0 architecture sprint; originated as a project-conversation artifact and was **not** committed when this document set was drafted — prepared as a verbatim preserved historical-evidence transcription on 2026-07-30 and included in this immutable r4 proposal baseline; no formal acceptance record exists); code verification of `core/dispatcher.py`, `core/workforce_resolver.py`, `core/policy_engine.py`, `core/governance_guard.py`, `core/openclaw_bridge.py`, `registry/employees.yml`, and a call-site search for `lisaos/policies/governance.yml` (2026-07-30) |

---

## 1. Character of the binding

The Constitution is the **normative layer**; the Gen 3 components are
**governance/enforcement actors** that apply instrument rules. No component
holds authority; each executes rules on behalf of the authority chain. This
document is **descriptive**: it maps clauses to the components that enforce
them today and honestly marks what is unenforced. It designs no
implementation.

## 2. Component roles

| Component | Constitutional function |
|---|---|
| `core/dispatcher.py` | Coordination/execution separation: it has no code path to take a package for itself, and since r4 it refuses an executor that does not **declare** its provenance, records that declaration, and derives worker/main attribution from it rather than assuming. It cannot verify the declaration (threat T15). Also: **per-package fail-closed failure** per Art. VII.2(b), where an unstaffable package fails with recorded evidence without halting independently authorized siblings; refuses to run at all without an explicit executor, so simulation cannot be selected by omission |
| `core/workforce_resolver.py` | Gatekeeper and scrivener of task grants: selects an eligible employee and materializes the WorkAssignment; narrows, rejects, fails closed; never widens (see `01_AUTHORITY_MODEL.md` §3). Staffs a **capability superset** of the package, which is why `02` §3A exists |
| `core/policy_engine.py` | **Staffing enforcement only**: mode eligibility, capacity-ledger health, provider availability, probation restriction. It performs **no approval validation** — verified 2026-07-30. It also does **not** populate approval metadata: its `WorkAssignment` is built without `operator_approval_required` or `fallback_level`, so both take dataclass defaults (`False` / `None`) even on non-low-risk fallback staffing. A substrate gap, not an exemption — an absent flag is not approval |
| `core/governance_guard.py` | Court of first instance for bypass (T1): scans for ungoverned production-shaped work, records violations, and — **once `require_clean()` is called** — fails closed per Art. VII.2(a) until a named operator acknowledges. The raise is mechanical; the invocation is not: verified 2026-07-30, no production entry point calls it (the only call sites are tests), so sprint-entry application is caller-dependent |
| `core/openclaw_bridge.py` | Attribution authority: deterministic `employee → agent → physical model` identity chain, fail-closed; the chain that makes evidence meaningful |
| Canonical registries (`employees.yml`, `provider_resolution.yml`, `workforce_modes.yml`) | Standing-grant instruments (hence P1). Legacy `agents.yml` / `runtimes.yml` are transitional inputs only, and their prohibitions bind only where expressly adopted (`02` §2A level 4) |
| Evidence ledgers (`reports/lisa/*.jsonl`) | The audit substrate: sole admissible proof that authority existed for an act (P2) |

## 3. Clause-by-clause enforcement status (verified)

| Constitutional rule | Status | Verified basis |
|---|---|---|
| Orchestrator never executes governed work | **Partial — declaration-based** (r4, B3) | Two separable claims. (a) *The dispatcher cannot execute*: **enforced** — `core/dispatcher.py` has no code path by which it takes a package itself; it always submits to the supplied executor. (b) *What runs is a worker*: **not proven**. The executor is caller-supplied and nothing inspects it. Since r4 it must **declare** `worker-real` / `worker-simulated` / `main-inline`; undeclared executors are refused, the declaration is recorded as `execution_provenance`, and `by_main` is derived from it rather than hardcoded `False`. A deliberately mismarked in-process callable is still undetected (threat T15) |
| Fail-closed staffing; no silent fallback; probation restricted to `risk: low` | **Enforced** | Resolver/policy engine raise `WorkforceResolutionError`; probation skipped whenever `risk != "low"` |
| Explicit recorded fallback | **Partial — path-dependent, and model-chain only** | Two limits. (a) `fallback_from` / `fallback_reason` are populated on both staffing paths, but `fallback_level` **only** by `core/workforce_resolver.py`; `core/policy_engine.py` leaves it at its `None` default. (b) r4, finding N2: fallback metadata describes movement **within one employee's model chain only**. Escalation from one capable employee to another — the outer candidate loop — is recorded as an ordinary assignment with **no substitution marker at all**. "Explicit recorded fallback" must be read as "explicit recorded *model* fallback" |
| No silent downgrade of judgement-critical work (`02` §3B) | **Partial — registry-contingent** | Not structural. Verified 2026-07-30: the resolver escalates to the *next capable candidate* when a candidate's chain is exhausted, so `fallback_models: []` alone prevents nothing. Halt-and-surface holds today only because `irreversible-judgement` is carried solely by `chief-architect` / `cto-reviewer`, both `principal`, both with empty chains. A registry edit granting that capability to a weaker worker would silently restore downgrade (threat T3). Nothing checks that a substitution preserves the independence class, and `failure_policy` is loaded without being acted on |
| Deterministic identity **selection** | **Enforced** | `core/openclaw_bridge.py` `agent_for_logical()` is called on the dispatch path and fails closed twice — `fail-closed-no-identity-agent` when a logical identity has no agent binding, `fail-closed-identity-agent-unavailable` when the bound agent is missing. No physical-model reverse-matching, so `codex` and `gpt` cannot collapse onto one agent |
| Live agent/model identity **integrity** | **Partial — post-execution detection** (r4, B4a/B4b) | Corrected at r4: `validate_identity_map()` is **not** on the dispatch path — its only non-test caller is the separate `bin/lisa-identity-check` command, so map validation is an out-of-band procedural preflight, not a runtime gate. At runtime the bridge confirms the bound agent exists but does not preflight that its live model matches the registry; drift is computed **after** execution from `executionTrace`, and `mismatch` deliberately does not mark the package failed (`core/openclaw_bridge.py`). `core/anti_regression.py` turns it into a gate failure at report level, after the fact |
| Evidence on every governed execution | **Enforced** (governed path only) | Dispatcher + `record_assignment_evidence()`. Scope caveat: "governed path" excludes the legacy entrypoints below |
| Evidence records the **outcome** (`04` §1.1) | **Enforced** (r4, B2) | `execution_success` / `execution_error` are copied from the `ExecutionResult` onto the `WorkAssignment` and serialized. Before r4 they existed only in the in-memory `DispatchReport`, so a failed execution was indistinguishable from a successful one in the ledger |
| Execution attribution is sourced, not assumed (`04` §1.7) | **Partial — declaration-based** (r4, B3) | Undeclared executors are refused; `execution_provenance` is recorded; `by_main` is derived. Declaration ≠ proof (T15) |
| Execution mode distinguishable; simulation never presented as real (`04` §1.6) | **Partial** | `execution_evidence_source` carries `"SIMULATED-NOT-EXECUTED"`, stamped by `simulated_executor` itself since r4 so labelling is no longer caller-dependent; real-only fields stay empty under simulation; `mismatch` flags divergence; `Dispatcher.__init__` raises without an explicit executor. The broader mode vocabulary has no canonical encoding |
| Staffing requires a named capability | **Enforced** (r4, authority-leak 3) | `candidates_for([])` returns no candidates, so a package declaring no required capabilities fails closed. Before r4 `set().issubset(...)` matched every employee and the seniority sort then staffed the **lowest-ranked** one |
| **Art. VII.2(a)** graph/sprint-entry halt | **Partial** | `governance_guard.require_clean()` refuses entry until violations are acknowledged — real once invoked, but doubly qualified: invocation is caller-dependent (no production call site; verified 2026-07-30), and detection is gated by the name-prefix heuristic |
| **Art. VII.2(b)** per-package fail-closed failure, siblings continue | **Enforced** | `core/dispatcher.py`: an unstaffable package is marked FAILED with evidence and "never silently vanishes and never blocks the rest of the graph from proceeding" |
| **Art. VII.2(d)** systemic halt | **Norm-only** | No mechanism escalates a package-level failure to a systemic halt, and none detects governance-layer unreliability |
| **Art. VII.3–5** safe suspension, classes, clearing authority | **Norm-only** | No suspension mechanism or class field exists; the guard's entry halt plus human acknowledgement is the nearest analogue (threat T12) |
| Detection of work outside the governed path (T1/T6) | **Partial, with structural blind spots** | Three separate limits, all verified: (a) the name-prefix heuristic — non-matching names evade (guard's own docstring); (b) clearing is by **name match against the whole ledger**, including permanent employee ids, so a matched name is a standing whitelist rather than proof this invocation was governed (r4, N1 / threat T17); (c) the guard scans only Claude Code subagent transcripts, so the legacy entrypoints in §3A are **structurally invisible** to it (threat T16) |
| Violation acknowledgement attributed + fail-closed | **Partial** | `require_clean()` raises until acknowledged; code requires only a non-empty operator string — "operator is human, never Lisa" is norm-only |
| Human approval before restricted action classes | **Norm-only** | Verified 2026-07-30: no code reads `lisaos/policies/governance.yml`; PolicyEngine has no approval concept and does not set `operator_approval_required` at all. On the `WorkforceResolver` path the flag is set but only *flags* the need, without checking satisfaction. No approval validator exists on either path |
| Episodic approval expiry / single-use default (`01` §4.3) | **Norm-only** | No approval instrument or expiry field exists in the substrate |
| Ratification only via named human record (Art. IX.3–5) | **Norm-only — now fully specified** (r4, B1) | The instrument now has an address and a schema: `reports/lisa/ratification_records.jsonl`, P2 append-only, ten required fields (`04` §1.5). That closes the "instrument with no destination" defect. Enforcement is unchanged and unchangeable from inside the system: no validator exists, no code reads the ledger, and no artifact here can prove the ratifier was human — any validator would be P1 code editable by the actors it constrains (Art. IX.9, threat T3). Human audit is the only control; **T10 remains High** |
| Instrument precedence, non-orderable conflicts fail closed (Art. II.5) | **Norm-only** | No precedence engine exists |
| Bounded orchestration grant (`01` §3A) | **Partial** | The execution prohibition is enforced by the dispatcher; goal scope, spend ceilings, and artifact scope are unchecked (threat T11) |
| Transitional artifact-class access (`02` §1.1) | **Norm-only** | `WorkPackage` carries only `id`, `description`, `required_capabilities`, `risk`, `mode`, `depends_on` — no artifact-class representation exists |
| Prohibitions (`02` §2A, all four levels) | **Norm-only** | No prohibition field in any canonical registry; no evaluator |
| P0/P1 write protection | **Norm-only** | Files ordinarily writable |
| P2 append-only ledgers; correction by superseding record | **Partial** | Components only append; out-of-band edits unprevented |
| Consultation vs authority escalation (`01` §6) | **Norm-only** | `escalates_to` loads into `Employee` but nothing routes escalations or distinguishes consultation from delegation (threat T13) |
| Reviewer independence (six conditions) | **Norm-only** | No mechanism exists |
| Task-grant scope conformance; superset staffing confers nothing | **Norm-only** | Assignments recorded; conformance unchecked; superset match is what the resolver actually computes |
| Release grants (Art. VIII.3) | **Norm-only** | New instrument; no release automation is currently governed by it |

## 3A. Ungoverned surfaces in this repository (named, not implied)

Every "Enforced" row above is scoped to the **governed path**: work entering
through `core/dispatcher.py`. Two currently-executable entrypoints do not enter
it, and this document set previously left that unsaid. They are named here so
no reader infers that the governed path is the only path (r4; threat T16).

| Surface | What it does | Governance |
|---|---|---|
| `bin/lisa` | Loads `registry/agents.json` and spawns `claude -p <prompt>` by subprocess | **None.** No dispatcher, no resolver, no staffing, no `WorkAssignment`, no evidence record |
| `bin/lisa-core` → `core/lisa_core.py` | Runs skills through the legacy `choose_engine()` / `engine.run()` path | **None.** `core/router.py` self-labels this layer "LEGACY … SUPERSEDED … Do not build new routing on this path" |

Neither produces a subagent transcript, so `core/governance_guard.py`
**cannot** detect either — the guard's blind spot here is structural, not a
heuristic gap. Work performed through these surfaces is ungoverned in the
constitutional sense (`04` §1.2: no evidence = ungoverned). Retiring, gating,
or routing them through governed dispatch is future work and is **not**
claimed to be done.

Registry note (r4, Gen 3 alignment): `registry/agents.yml` carries
`status: active` in its own header while `02_PERMISSION_CONTRACTS.md` §4
classifies it transitional, superseded, and unratified. The constitutional
classification governs; the registry header is stale metadata in a file this
Constitution does not ratify. It is recorded here rather than edited, because
canonical registries are P1 and this remediation holds no P1 grant.

## 4. Future enforcement candidates (flagged, not designed)

The norm-only rows above are candidates for future mechanical enforcement.
Ranked by the threat register (`05_THREAT_MODEL.md`), the sharpest gaps are:
**retiring or governing the legacy entrypoints in §3A (T16)** — the only gap
where ungoverned execution is currently reachable by a single command —
followed by ratification integrity (T10), approval validation (T9), scope
conformance under superset staffing (T2), registry/P1 write protection (T3),
ledger immutability (T4), binding guard clearance to the invocation rather
than to a name (T17), and recording cross-employee candidate substitution
(`02_PERMISSION_CONTRACTS.md` §3B, "explicit, recorded" fallback). Two structural additions would carry several of these at
once — an append-only human-act ledger with a named-operator contract (serving
T9, T10, and suspension clearing), and an artifact-class field on the work
package (serving T2, the transitional access rule, and the probation
extension).

Designing any of this — like workforce evolution, delegation optimisation,
engineering memory, and migration — is explicitly outside Phase 1's scope.
