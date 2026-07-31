# Substrate Binding — Constitution ↔ Gen 3 Components

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> No constitutional force until recorded human ratification of Constitution v2
> (Art. IX.3). Revising this document does not ratify it.

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r8 |
| Revision evidence index (r8) | `docs/LISAOS/CONSTITUTION/REVIEWS/V2_REVISION_EVIDENCE_INDEX.md` maps every cited r2–r8 revision basis to an immutable object and repository evidence artifact, or records the original artifact as unavailable without reconstruction. It records LCR-01 at commit `91e291f3556a834f1d6520fb336ee0f78112152a`, frozen as `CONSTITUTION-V2-R7-PROPOSED` (annotated tag object `0a074479fd71493c0ddb6771e8c5f4c7f17c8e40`), and identifies the exact recovered independent-review artifacts and their provenance. The r4, r5, and r6 proposal tags remained unmoved. This row records no ratification and changes no constitutional semantics. |
| Revision basis (r8) | r8 — documentation-only correction following the final independent review of `CONSTITUTION-V2-R7-PROPOSED` (verdict **B — REMEDIATION REQUIRED BEFORE HUMAN RATIFICATION**). It corrects proposal self-identification and evidence-state accuracy; records the immutable LCR-01/r7 identity; preserves the exact recovered r6, LCR-01 delta, and r7 final review outputs with provenance; and applies only the permitted factual documentation corrections for NB1, r5 advisory status, and ADV-04 post-freeze provenance. It introduces no constitutional semantic, governance, implementation, architecture, test, threat-model, or residual-risk change. Frozen predecessor: `CONSTITUTION-V2-R7-PROPOSED`, commit `91e291f3556a834f1d6520fb336ee0f78112152a`, annotated tag object `0a074479fd71493c0ddb6771e8c5f4c7f17c8e40`, preserved unchanged. The proposal remains **PROPOSED — PENDING HUMAN RATIFICATION**. |
| Prior revision basis (r6) | r6 — remediation authored by **Codex / OpenAI** following the independent Codex r5 verdict **C. REMEDIATION REQUIRED BEFORE RATIFICATION**. Frozen predecessor: `CONSTITUTION-V2-R5-PROPOSED`, commit `247d3eb76d6f2ac08e5307134b80e5458b4b00d3`, preserved unchanged. r6 remediates **ADV-01** with one strict string-and-membership provenance validator at construction and every run; **ADV-02** with complete `ExecutionResult` validation and normalized failure evidence; **ADV-03** with strict JSON-safe evidence, flush/fsync append, evidence-before-completion ordering, and an explicit systemic halt on sink failure; **ADV-05** with explicit disclosure of process-wide re-marking of the shared simulated executor; and **ADV-06** by removing absolute silent-laundering claims. Surviving accepted residuals: `functools.wraps` may accidentally copy a valid declaration, and `mark_executor` may deliberately mark or re-mark a callable; strict vocabulary validation does not prove semantic truth. Contemporaneous authoring evidence: `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R6_REMEDIATION_EVIDENCE.md`. Because Codex authored r6, Codex is permanently disqualified from independently reviewing r6. **At the r6 freeze, r6 had not yet been independently reviewed or ratified; its later independent review and verdict C are preserved and indexed separately.** |
| Prior revision basis (r5) | r5 — **first proposal revision in which the constitutional enforcement claims, their implementation, and their tests exist in the same commit.** r5 incorporates the dispatcher/evidence enforcement implementation itself: execution outcome (`execution_success` / `execution_error`) and declared executor provenance (`execution_provenance`) are carried into the evidence record and serialized; the dispatcher fails closed on undeclared executor provenance at construction and at every run; an empty-required-capability guard fails closed in `candidates_for()`; and the tests pinning these controls (`tests/test_r4_remediation.py`, updated `tests/test_dispatcher.py`) are included. r5 also corrects the T15 residual-risk wording, which in r4 wrongly stated that accidental attribution laundering was impossible — a `functools.wraps` route remains open and is now recorded rather than denied. r5 **supersedes r4 only as a proposal revision, not as a ratified Constitution**; r4 remains immutably preserved at commit `e695cfa99c512c1a724ecc1acda7eb7064de41d6` (tag `CONSTITUTION-V2-R4-PROPOSED`). **The recovered r5 review is an independent review with substantial historical and technical evidentiary value, but it did not satisfy the constitutional independent-review gate because condition 3 failed; for ratification it is advisory.** Prior: r4 — remediation of the **independent Codex constitutional review** (OpenAI/GPT-5) as reconciled by the subsequent independent assessment: B1 ratification instrument specification, B2 execution-outcome evidence, B3 executor provenance and attribution truth, B4 identity and simulation classifications, B5 amendment precedence, plus the confirmed non-blocking findings (guard clearance, candidate substitution, incorporation boundary, planner/P4 coherence, approval authority, legacy entrypoints, threat-model completeness). The Codex review was **advisory** — it failed the six-condition test on evidence-baseline access only — and does **not** satisfy the independent constitutional gate. Prior: r3 — enforcement-honesty remediation of the Claude Fable 5 advisory audit (BF-1 PolicyEngine approval metadata; BF-2 registry-contingent no-downgrade; M2 caller-dependent guard invocation). That audit was **advisory** and does **not** satisfy the independent constitutional gate. Prior: r2 — remediation of author self-audit S044 (B3 fail-closed semantics alignment; enforcement rows added for the r2 clauses) |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report — `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md` (Phase 0 architecture sprint; originated as a project-conversation artifact and was **not** committed when this document set was drafted — prepared as a verbatim preserved historical-evidence transcription on 2026-07-30 and included in the immutable r4 proposal baseline (`e695cfa9`), carried forward unchanged into r5; no formal acceptance record exists); code verification of `core/dispatcher.py`, `core/workforce_resolver.py`, `core/policy_engine.py`, `core/governance_guard.py`, `core/openclaw_bridge.py`, `registry/employees.yml`, and a call-site search for `lisaos/policies/governance.yml` (2026-07-30) |

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
| `core/dispatcher.py` | Coordination/execution separation: it has no code path to take a package for itself. Since r6, one validator at construction and every run requires executor provenance to be an exact string in the canonical three-value vocabulary; it records the current declaration and derives worker/main attribution from it. It cannot verify the semantic truth of a valid declaration (threat T15). Also: **per-package fail-closed failure** per Art. VII.2(b), where an unstaffable or malformed-result package fails with recorded evidence without halting independently authorized siblings; evidence is appended before successful graph completion; an evidence-sink failure is an explicit systemic halt; and omission of an executor is refused, so simulation cannot be selected by omission |
| `core/workforce_resolver.py` | Gatekeeper and scrivener of task grants: selects an eligible employee and materializes the WorkAssignment; narrows, rejects, fails closed; never widens (see `01_AUTHORITY_MODEL.md` §3). Staffs a **capability superset** of the package, which is why `02` §3A exists |
| `core/policy_engine.py` | **Staffing enforcement only**: mode eligibility, capacity-ledger health, provider availability, probation restriction. It performs **no approval validation** — verified 2026-07-30. It also does **not** populate approval metadata: its `WorkAssignment` is built without `operator_approval_required` or `fallback_level`, so both take dataclass defaults (`False` / `None`) even on non-low-risk fallback staffing. A substrate gap, not an exemption — an absent flag is not approval |
| `core/governance_guard.py` | Court of first instance for bypass (T1): scans for ungoverned production-shaped work, records violations, and — **once `require_clean()` is called** — fails closed per Art. VII.2(a) until a named operator acknowledges. The raise is mechanical; the invocation is not: verified 2026-07-30, no production entry point calls it (the only call sites are tests), so sprint-entry application is caller-dependent |
| `core/openclaw_bridge.py` | Attribution authority: deterministic `employee → agent → physical model` identity chain, fail-closed; the chain that makes evidence meaningful |
| Canonical registries (`employees.yml`, `provider_resolution.yml`, `workforce_modes.yml`) | Standing-grant instruments (hence P1). Legacy `agents.yml` / `runtimes.yml` are transitional inputs only, and their prohibitions bind only where expressly adopted (`02` §2A level 4) |
| Evidence ledgers (`reports/lisa/*.jsonl`) | The audit substrate: sole admissible proof that authority existed for an act (P2) |

## 3. Clause-by-clause enforcement status (verified)

| Constitutional rule | Status | Verified basis |
|---|---|---|
| Orchestrator never executes governed work | **Partial — declaration-based** (r6, ADV-01/05/06) | Two separable claims. (a) *The dispatcher cannot execute*: **enforced** — `core/dispatcher.py` has no code path by which it takes a package itself; it always submits to the supplied executor. (b) *What runs is a worker*: **not proven**. The executor is caller-supplied and nothing inspects it. One validator at construction and every run requires an exact string in `worker-real` / `worker-simulated` / `main-inline`; invalid values are refused, the current declaration is recorded as `execution_provenance`, and `by_main` is derived from it rather than hardcoded `False`. A valid declaration may still be accidentally inherited through `functools.wraps` or deliberately marked/re-marked, including process-wide re-marking of the shared `simulated_executor` object (threat T15) |
| Fail-closed staffing; no silent fallback; probation restricted to `risk: low` | **Enforced** | Resolver/policy engine raise `WorkforceResolutionError`; probation skipped whenever `risk != "low"` |
| Explicit recorded fallback | **Partial — path-dependent, and model-chain only** | Two limits. (a) `fallback_from` / `fallback_reason` are populated on both staffing paths, but `fallback_level` **only** by `core/workforce_resolver.py`; `core/policy_engine.py` leaves it at its `None` default. (b) r4, finding N2: fallback metadata describes movement **within one employee's model chain only**. Escalation from one capable employee to another — the outer candidate loop — is recorded as an ordinary assignment with **no substitution marker at all**. "Explicit recorded fallback" must be read as "explicit recorded *model* fallback" |
| No silent downgrade of judgement-critical work (`02` §3B) | **Partial — registry-contingent** | Not structural. Verified 2026-07-30: the resolver escalates to the *next capable candidate* when a candidate's chain is exhausted, so `fallback_models: []` alone prevents nothing. Halt-and-surface holds today only because `irreversible-judgement` is carried solely by `chief-architect` / `cto-reviewer`, both `principal`, both with empty chains. A registry edit granting that capability to a weaker worker would silently restore downgrade (threat T3). Nothing checks that a substitution preserves the independence class, and `failure_policy` is loaded without being acted on |
| Deterministic identity **selection** | **Enforced** | `core/openclaw_bridge.py` `agent_for_logical()` is called on the dispatch path and fails closed twice — `fail-closed-no-identity-agent` when a logical identity has no agent binding, `fail-closed-identity-agent-unavailable` when the bound agent is missing. No physical-model reverse-matching, so `codex` and `gpt` cannot collapse onto one agent |
| Live agent/model identity **integrity** | **Partial — post-execution detection** (r4, B4a/B4b) | Corrected at r4: `validate_identity_map()` is **not** on the dispatch path — its only non-test caller is the separate `bin/lisa-identity-check` command, so map validation is an out-of-band procedural preflight, not a runtime gate. At runtime the bridge confirms the bound agent exists but does not preflight that its live model matches the registry; drift is computed **after** execution from `executionTrace`, and `mismatch` deliberately does not mark the package failed (`core/openclaw_bridge.py`). `core/anti_regression.py` turns it into a gate failure at report level, after the fact |
| Evidence on every reconciled governed execution | **Enforced within the process/filesystem contract** (r6, ADV-03; governed path only) | Dispatcher normalizes outcomes, builds strict JSON, appends + flushes + `fsync`s, and only then finalizes successful graph state. A sink failure raises `EvidenceSinkError`, fails all non-terminal graph work, and may itself be unevidenced because the sink is unavailable. No claim is made against disk, kernel, filesystem, process, hardware, or out-of-band failure. Scope caveat: the legacy entrypoints below are not governed |
| Evidence records the **outcome** (`04` §1.1) | **Enforced** (r6, ADV-02/03) | `execution_success` / `execution_error` are copied from a validated `ExecutionResult`; malformed returns become normalized failed evidence. Strict JSON conversion occurs before append, and success is not finalized before the append returns |
| Execution attribution is sourced, not assumed (`04` §1.7) | **Partial — declaration-based** (r6, ADV-01/05/06) | Invalid declarations are refused at construction and every run; current `execution_provenance` is recorded; `by_main` is derived. Valid declaration ≠ semantic proof; R5-1 accidental inheritance and R5-2 deliberate shared-object re-marking remain (T15) |
| Execution mode distinguishable; simulation never presented as real (`04` §1.6) | **Partial** | `execution_evidence_source` carries `"SIMULATED-NOT-EXECUTED"`, stamped by `simulated_executor` itself since r4 so labelling is no longer caller-dependent; real-only fields stay empty under simulation; `mismatch` flags divergence; `Dispatcher.__init__` raises without an explicit executor. The broader mode vocabulary has no canonical encoding |
| Staffing requires a named capability | **Enforced** (r4, authority-leak 3) | `candidates_for([])` returns no candidates, so a package declaring no required capabilities fails closed. Before r4 `set().issubset(...)` matched every employee and the seniority sort then staffed the **lowest-ranked** one |
| **Art. VII.2(a)** graph/sprint-entry halt | **Partial** | `governance_guard.require_clean()` refuses entry until violations are acknowledged — real once invoked, but doubly qualified: invocation is caller-dependent (no production call site; verified 2026-07-30), and detection is gated by the name-prefix heuristic |
| **Art. VII.2(b)** per-package fail-closed failure, siblings continue | **Enforced for staffing, executor exception, and malformed-result failures** | `core/dispatcher.py`: the affected package is normalized/marked FAILED with evidence while independently authorized siblings continue. Evidence-sink failure is deliberately excluded because it is systemic under VII.2(d) |
| **Art. VII.2(d)** systemic halt | **Partial** (r6, ADV-03) | Evidence serialization or append failure raises `EvidenceSinkError` and marks all non-terminal graph work failed before any unevidenced success is finalized. Other systemic conditions listed in Art. VII.2(d) remain norm-only |
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
