# Substrate Binding — Constitution ↔ Gen 3 Components

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> No constitutional force until recorded human ratification of Constitution v2
> (Art. IX.3). Revising this document does not ratify it.

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r3 |
| Revision basis | r3 — enforcement-honesty remediation of the Claude Fable 5 advisory audit (BF-1 PolicyEngine approval metadata; BF-2 registry-contingent no-downgrade; M2 caller-dependent guard invocation). That audit was **advisory** and does **not** satisfy the independent constitutional gate. Prior: r2 — remediation of author self-audit S044 (B3 fail-closed semantics alignment; enforcement rows added for the r2 clauses) |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report (accepted 2026-07-30); code verification of `core/dispatcher.py`, `core/workforce_resolver.py`, `core/policy_engine.py`, `core/governance_guard.py`, `core/openclaw_bridge.py`, `registry/employees.yml`, and a call-site search for `lisaos/policies/governance.yml` (2026-07-30) |

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
| `core/dispatcher.py` | Coordination/execution separation (the orchestrator never executes — no code path exists for it to take a package); **per-package fail-closed failure** per Art. VII.2(b), where an unstaffable package fails with recorded evidence without halting independently authorized siblings; refuses to run at all without an explicit executor, so simulation cannot be selected by omission |
| `core/workforce_resolver.py` | Gatekeeper and scrivener of task grants: selects an eligible employee and materializes the WorkAssignment; narrows, rejects, fails closed; never widens (see `01_AUTHORITY_MODEL.md` §3). Staffs a **capability superset** of the package, which is why `02` §3A exists |
| `core/policy_engine.py` | **Staffing enforcement only**: mode eligibility, capacity-ledger health, provider availability, probation restriction. It performs **no approval validation** — verified 2026-07-30. It also does **not** populate approval metadata: its `WorkAssignment` is built without `operator_approval_required` or `fallback_level`, so both take dataclass defaults (`False` / `None`) even on non-low-risk fallback staffing. A substrate gap, not an exemption — an absent flag is not approval |
| `core/governance_guard.py` | Court of first instance for bypass (T1): scans for ungoverned production-shaped work, records violations, and — **once `require_clean()` is called** — fails closed per Art. VII.2(a) until a named operator acknowledges. The raise is mechanical; the invocation is not: verified 2026-07-30, no production entry point calls it (the only call sites are tests), so sprint-entry application is caller-dependent |
| `core/openclaw_bridge.py` | Attribution authority: deterministic `employee → agent → physical model` identity chain, fail-closed; the chain that makes evidence meaningful |
| Canonical registries (`employees.yml`, `provider_resolution.yml`, `workforce_modes.yml`) | Standing-grant instruments (hence P1). Legacy `agents.yml` / `runtimes.yml` are transitional inputs only, and their prohibitions bind only where expressly adopted (`02` §2A level 4) |
| Evidence ledgers (`reports/lisa/*.jsonl`) | The audit substrate: sole admissible proof that authority existed for an act (P2) |

## 3. Clause-by-clause enforcement status (verified)

| Constitutional rule | Status | Verified basis |
|---|---|---|
| Orchestrator never executes governed work | **Enforced** (within the governed path) | `core/dispatcher.py`: no code path for main to take a package |
| Fail-closed staffing; no silent fallback; probation restricted to `risk: low` | **Enforced** | Resolver/policy engine raise `WorkforceResolutionError`; probation skipped whenever `risk != "low"` |
| Explicit recorded fallback | **Partial — path-dependent** | `fallback_from` / `fallback_reason` are populated on both staffing paths. `fallback_level` is populated **only** by `core/workforce_resolver.py`; `core/policy_engine.py` leaves it at its `None` default (verified 2026-07-30) |
| No silent downgrade of judgement-critical work (`02` §3B) | **Partial — registry-contingent** | Not structural. Verified 2026-07-30: the resolver escalates to the *next capable candidate* when a candidate's chain is exhausted, so `fallback_models: []` alone prevents nothing. Halt-and-surface holds today only because `irreversible-judgement` is carried solely by `chief-architect` / `cto-reviewer`, both `principal`, both with empty chains. A registry edit granting that capability to a weaker worker would silently restore downgrade (threat T3). Nothing checks that a substitution preserves the independence class, and `failure_policy` is loaded without being acted on |
| Deterministic identity/attribution chain | **Enforced** | Bridge `agent_for_logical()` + `validate_identity_map()`; fails closed |
| Evidence on every governed execution | **Enforced** (governed path only) | Dispatcher + `record_assignment_evidence()` |
| Execution mode distinguishable; simulation never presented as real (`04` §1.6) | **Partial** | `execution_evidence_source` carries `"SIMULATED-NOT-EXECUTED"`; real-only fields stay empty under simulation; `mismatch` flags divergence; `Dispatcher.__init__` raises without an explicit executor. The broader mode vocabulary has no canonical encoding |
| **Art. VII.2(a)** graph/sprint-entry halt | **Partial** | `governance_guard.require_clean()` refuses entry until violations are acknowledged — real once invoked, but doubly qualified: invocation is caller-dependent (no production call site; verified 2026-07-30), and detection is gated by the name-prefix heuristic |
| **Art. VII.2(b)** per-package fail-closed failure, siblings continue | **Enforced** | `core/dispatcher.py`: an unstaffable package is marked FAILED with evidence and "never silently vanishes and never blocks the rest of the graph from proceeding" |
| **Art. VII.2(d)** systemic halt | **Norm-only** | No mechanism escalates a package-level failure to a systemic halt, and none detects governance-layer unreliability |
| **Art. VII.3–5** safe suspension, classes, clearing authority | **Norm-only** | No suspension mechanism or class field exists; the guard's entry halt plus human acknowledgement is the nearest analogue (threat T12) |
| Detection of work outside the governed path (T1/T6) | **Partial** | Guard name-prefix heuristic; non-matching names evade (guard's own docstring) |
| Violation acknowledgement attributed + fail-closed | **Partial** | `require_clean()` raises until acknowledged; code requires only a non-empty operator string — "operator is human, never Lisa" is norm-only |
| Human approval before restricted action classes | **Norm-only** | Verified 2026-07-30: no code reads `lisaos/policies/governance.yml`; PolicyEngine has no approval concept and does not set `operator_approval_required` at all. On the `WorkforceResolver` path the flag is set but only *flags* the need, without checking satisfaction. No approval validator exists on either path |
| Episodic approval expiry / single-use default (`01` §4.3) | **Norm-only** | No approval instrument or expiry field exists in the substrate |
| Ratification only via named human record (Art. IX.3–5) | **Norm-only** | No ratification ledger or validator exists; nearest pattern is `record_acknowledgement`, which requires a named operator but cannot verify humanness (threat T10) |
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

## 4. Future enforcement candidates (flagged, not designed)

The norm-only rows above are candidates for future mechanical enforcement.
Ranked by the threat register (`05_THREAT_MODEL.md`), the sharpest gaps are:
ratification integrity (T10), approval validation (T9), scope conformance under
superset staffing (T2), registry/P1 write protection (T3), and ledger
immutability (T4). Two structural additions would carry several of these at
once — an append-only human-act ledger with a named-operator contract (serving
T9, T10, and suspension clearing), and an artifact-class field on the work
package (serving T2, the transitional access rule, and the probation
extension).

Designing any of this — like workforce evolution, delegation optimisation,
engineering memory, and migration — is explicitly outside Phase 1's scope.
