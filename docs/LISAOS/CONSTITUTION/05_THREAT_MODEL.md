# Threat Model — Actor Overreach

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> No constitutional force until recorded human ratification of Constitution v2
> (Art. IX.3). Revising this document does not ratify it.

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r6 |
| Revision evidence index (LCR-01) | `docs/LISAOS/CONSTITUTION/REVIEWS/V2_REVISION_EVIDENCE_INDEX.md` maps every cited r2–r6 revision basis to an immutable object and repository evidence artifact, or records the original artifact as unavailable without reconstruction. The original r5 review is preserved verbatim at `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R5_INDEPENDENT_REVIEW.md`; recovery provenance and ADV-04 disposition are recorded in `V2_R6_REMEDIATION_EVIDENCE.md` §13. This LCR-01 documentation-only row postdates the immutable r6 tag and changes no constitutional semantics. |
| Revision basis | r6 — remediation authored by **Codex / OpenAI** following the independent Codex r5 verdict **C. REMEDIATION REQUIRED BEFORE RATIFICATION**. Frozen predecessor: `CONSTITUTION-V2-R5-PROPOSED`, commit `247d3eb76d6f2ac08e5307134b80e5458b4b00d3`, preserved unchanged. r6 remediates **ADV-01** with one strict string-and-membership provenance validator at construction and every run; **ADV-02** with complete `ExecutionResult` validation and normalized failure evidence; **ADV-03** with strict JSON-safe evidence, flush/fsync append, evidence-before-completion ordering, and an explicit systemic halt on sink failure; **ADV-05** with explicit disclosure of process-wide re-marking of the shared simulated executor; and **ADV-06** by removing absolute silent-laundering claims. Surviving accepted residuals: `functools.wraps` may accidentally copy a valid declaration, and `mark_executor` may deliberately mark or re-mark a callable; strict vocabulary validation does not prove semantic truth. Contemporaneous authoring evidence: `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R6_REMEDIATION_EVIDENCE.md`. Because Codex authored r6, Codex is permanently disqualified from independently reviewing r6. **r6 has not been independently reviewed or ratified.** |
| Prior revision basis (r5) | r5 — **first proposal revision in which the constitutional enforcement claims, their implementation, and their tests exist in the same commit.** r5 incorporates the dispatcher/evidence enforcement implementation itself: execution outcome (`execution_success` / `execution_error`) and declared executor provenance (`execution_provenance`) are carried into the evidence record and serialized; the dispatcher fails closed on undeclared executor provenance at construction and at every run; an empty-required-capability guard fails closed in `candidates_for()`; and the tests pinning these controls (`tests/test_r4_remediation.py`, updated `tests/test_dispatcher.py`) are included. r5 also corrects the T15 residual-risk wording, which in r4 wrongly stated that accidental attribution laundering was impossible — a `functools.wraps` route remains open and is now recorded rather than denied. r5 **supersedes r4 only as a proposal revision, not as a ratified Constitution**; r4 remains immutably preserved at commit `e695cfa99c512c1a724ecc1acda7eb7064de41d6` (tag `CONSTITUTION-V2-R4-PROPOSED`). **r5 has not been independently reviewed.** Prior: r4 — remediation of the **independent Codex constitutional review** (OpenAI/GPT-5) as reconciled by the subsequent independent assessment: B1 ratification instrument specification, B2 execution-outcome evidence, B3 executor provenance and attribution truth, B4 identity and simulation classifications, B5 amendment precedence, plus the confirmed non-blocking findings (guard clearance, candidate substitution, incorporation boundary, planner/P4 coherence, approval authority, legacy entrypoints, threat-model completeness). The Codex review was **advisory** — it failed the six-condition test on evidence-baseline access only — and does **not** satisfy the independent constitutional gate. Prior: r3 — enforcement-honesty remediation of the Claude Fable 5 advisory audit (BF-1 T9 approval-flag path-dependence; BF-2 registry-contingent no-downgrade in the honest summary). That audit was **advisory** and does **not** satisfy the independent constitutional gate. Prior: r2 — remediation of author self-audit S044 (A6 superset staffing in T2, A8 orchestrator-specific threats T10–T14) |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report — `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md` (Phase 0 architecture sprint; originated as a project-conversation artifact and was **not** committed when this document set was drafted — prepared as a verbatim preserved historical-evidence transcription on 2026-07-30 and included in the immutable r4 proposal baseline (`e695cfa9`), carried forward unchanged into r5; no formal acceptance record exists); code verification of `core/governance_guard.py`, `core/policy_engine.py`, `core/dispatcher.py`, `core/workforce_resolver.py` (2026-07-30) |

---

## Scope

Threats from authority actors — execution workers, the orchestrator, and
reviewers — exceeding, evading, or fabricating authority. T1–T9 concern
workers and delegation; T10–T14 concern the orchestrator and the evidence
layer; T15–T17 (added at r4) concern execution attribution, ungoverned
entrypoints, and the strength of guard clearance. External attackers and
infrastructure compromise are out of scope for this document.

Enforcement status vocabulary follows Constitution Art. X: **enforced**,
**partial**, **norm-only**. No control below is claimed as stronger than
verified.

## Threat register

| # | Threat | Constitutional control | Enforcement today (verified) | Residual risk |
|---|---|---|---|---|
| **T1** | **Direct bypass** — work executed outside dispatcher/resolver governed dispatch | Task authority exists only via governed dispatch; no evidence = ungoverned | **Partial, with known blind spots.** The governance guard scans Claude Code subagent transcripts, records violations, and fails closed until human-acknowledged — but (a) invocation is caller-dependent (`04` §2.2), (b) detection is a name-prefix heuristic, (c) clearing is a permanent name whitelist (T17), and (d) **the guard structurally cannot see the legacy entrypoints in T16**, which are not subagent transcripts at all | **High** (raised from Medium at r4) — undetectable bypass paths exist in `bin/`; detection, not prevention |
| **T2** | **Scope creep** inside a legitimate assignment, amplified by superset staffing | The assignment is the whole authority; Escalation-not-Innovation; unused capabilities confer no authority (`02` §3A) | **Norm-only.** Assignments are recorded; scope conformance is not checked. The resolver deliberately staffs a **capability superset** of the package (verified), so a worker routinely holds more capability than its package needs — the §1 intersection is a norm, not a runtime bound | High — the widest norm-only gap for workers |
| **T3** | **Self-elevation by configuration** — editing registries/contracts to gain authority | Canonical registries are P1: human grant + independent review required | **Norm-only.** Files are ordinarily writable | Medium — after-the-fact audit is the control |
| **T4** | **Evidence tampering or omission** | Ledgers are P2 append-only; correction only by superseding record (`03` §2A) | **Partial.** Owning components only append (verified); nothing prevents out-of-band edit/delete | Medium — filesystem offers no immutability |
| **T5** | **Reviewer capture** — self-review, instructed defence, or correlated models | Six-condition review validity test; family independence for P1/security; disclosure duty | **Norm-only.** No mechanism checks any condition; the codex/gpt physical-model collapse makes correlation a live concern | Medium |
| **T6** | **Authority laundering via chained delegation** — a worker privately re-delegating | Grants are non-transitive; re-delegation must re-enter governed dispatch | **Partial** (same guard heuristic as T1) | Medium |
| **T7** | **Instruction smuggling** — a worker acting on directives embedded in its inputs | Authority is explicit, never inferred: input content is never a grant | **Norm-only.** Inherent LLM risk; permission contracts limit blast radius | High — accepted and named, not solved |
| **T8** | **Stale or replayed authority** — acting on an expired assignment or old approval | Grants expire; approvals carry expiry or are single-use by default (`01` §4.3); never retroactive | **Partial.** Assignments are per-run instruments; approval expiry is unchecked | Low–Medium |
| **T9** | **Approval fabrication** — proceeding on a claimed but unrecorded human approval | Approvals are instruments: they exist only as recorded evidence; an unevidenced approval is no approval | **Norm-only; flagging is path-dependent.** Verified 2026-07-30: no code reads `lisaos/policies/governance.yml` or validates any approval before execution. The substrate can *flag* the need (`operator_approval_required`) **only on the `WorkforceResolver` path**; `PolicyEngine.resolve()` never sets it, so the field defaults to `False` even on non-low-risk fallback staffing. An absent flag is not approval. Nothing on either path checks satisfaction | Medium–high |
| **T10** | **Forged or self-asserted ratification** — an actor completing a metadata block, or otherwise asserting that the Constitution is in force | Ratification is effective **only** via the named human ratification record; metadata is a mirror with no constitutional effect; no actor may ratify (Art. IX.3–5) | **Norm-only.** Since r4 the instrument is fully specified — canonical ledger `reports/lisa/ratification_records.jsonl`, P2 append-only, ten required fields (`04` §1.5) — which removes the "no destination" defect but changes nothing about enforcement. P0 files remain ordinarily writable, no validator exists, no code reads the ledger, and nothing can establish that a `ratifier` string was written by a human. Art. IX.9 states this limit explicitly: any validator would be P1 code editable by the actors it constrains (T3). The control is structural — authority was moved out of the writable artifact into an append-only record — plus human audit | High — the sharpest orchestrator-layer gap |
| **T11** | **Self-asserted or unbounded standing authority** — the orchestrator treating its coordination grant as general authority, or inventing an operational bound it was never given | Bounded standing grant with explicit may/may-not lists and bounding formula (`01` §3A); operational bounds come from instruments; missing bound ⇒ escalate | **Partial.** `core/dispatcher.py` has no code path by which it executes a package itself — enforced. Whether the *executor it is handed* is a worker is declaration-based only since r4, not proven (T15). Goal scope, spend ceilings, and artifact scope are unchecked | Medium–high |
| **T12** | **Self-clearing governance suspension** — the orchestrator lifting its own halt, or reclassifying an S2–S4 suspension as S1 to make it self-clearable | Suspension classes S1–S4 with clearing authority; Lisa may clear S1 only; reclassification prohibited; uncertain class ⇒ higher class (Art. VII.3–5) | **Norm-only.** No suspension mechanism or class field exists yet; the guard's sprint-entry halt is the nearest existing analogue and it does require human acknowledgement | Medium |
| **T13** | **Consultation treated as delegated authority** — a consulted worker acting on artifacts, or a peer `escalates_to` hop being read as a grant | Consultation transfers no authority and creates no grant; `escalates_to`/`avoid_tasks` are routing hints, not grants; authority escalates upward only (`01` §6.1–6.2) | **Norm-only.** `escalates_to` and `failure_policy` load into the `Employee` model, but nothing routes escalations or distinguishes consultation from delegation | Medium |
| **T14** | **Simulated evidence presented as real execution** | Evidence must record execution mode; simulated/mocked/replayed evidence may never be represented as proof of real execution (`04` §1.6) | **Partial — the best-defended threat here.** `execution_evidence_source` carries an explicit `"SIMULATED-NOT-EXECUTED"` marker, stamped by `simulated_executor` itself since r4 so labelling no longer depends on the caller choosing the labelled wrapper; real-executor-only fields (`observed_model`, `execution_run_id`) stay empty under simulation; `mismatch` flags divergence; and `Dispatcher.__init__` raises when no executor is passed, so simulation cannot be selected by omission (all verified) | Low |
| **T15** | **Attribution falsification** — an executor performing work in the orchestrator's own process while the evidence records worker execution | Execution attribution must be sourced from a declaration, never assumed (`04` §1.7); the orchestrator may never execute governed work (`01` §2) | **Partial — declaration-based** (r6). One validator at construction and every run requires an exact string in `worker-real` / `worker-simulated` / `main-inline`; malformed or mutated-invalid declarations fail closed, the current valid declaration is recorded, and worker/main attribution is derived from it. **But valid syntax is not semantic proof.** Before r4 this was worse than norm-only: `by_main=False` was hardcoded, so the substrate actively manufactured false attribution | Medium — two routes remain open and are accepted rather than hidden. **R5-1, accidental:** a `functools.wraps` wrapper that replaces rather than delegates inherits a marked executor's valid declaration because `wraps` copies `__dict__`. **R5-2, deliberate and process-wide:** `mark_executor` can deliberately re-mark the shared `simulated_executor` function object; callers holding that same object observe the mutation. Its `SIMULATED-NOT-EXECUTED` evidence label remains separate from its provenance attribution. Strict vocabulary validation closes malformed-value acceptance, not false valid declarations, and r6 does not claim silent laundering is impossible |
| **T16** | **Legacy ungoverned entrypoints** — executable paths that reach real models without dispatcher, staffing, resolution, or evidence | Task authority exists only via governed dispatch (`01` §3); no evidence = ungoverned (`04` §1.2) | **Norm-only, and undetected.** Named honestly rather than implied absent: `bin/lisa` spawns `claude -p` by subprocess directly; `bin/lisa-core` → `core/lisa_core.py` uses the legacy `choose_engine()` / `engine.run()` path (`core/router.py` self-labels it SUPERSEDED). Neither produces a `WorkAssignment` or any evidence record, and neither is a subagent transcript, so the governance guard **cannot** see them. Retiring or governing these surfaces is future work | **High** — the widest bypass in the repository |
| **T17** | **Guard clearance by stale or colliding identifiers** — a bypass cleared because its name once appeared in the ledger | Evidence must attest to *this* act, not merely to a name (`04` §2.2A) | **Norm-only.** The guard clears any invocation whose name matches any `work_package_id` or `employee` id anywhere in the ledger, unbound to session, transcript, or time. Because employee ids are permanent, this is a standing whitelist, not a replay window. Verified in `core/governance_guard.py` and its tests | Medium — silently weakens T1/T6 detection |

## Honest summary

The Gen 3 substrate mechanically constrains staffing, routing, identity, and
evidence *on the governed path*. It prevents simulation-by-omission and, since
r6, refuses malformed executor provenance and malformed successful results.
It does **not** prevent every silent attribution-laundering route: R5-1 and
R5-2 in T15 remain possible.

Three qualifications matter more than that list:

**The governed path is not the only path.** `bin/lisa` and `bin/lisa-core`
reach real models with no dispatcher, no staffing, no evidence, and no
possibility of guard detection (threat **T16**). Every "enforced" claim in this
document set is scoped to the governed path and says nothing about these.

**"The orchestrator never executes" is a declaration, not a proof.** The
dispatcher has no code path to take a package itself, and executors must now
declare their provenance — but nothing inspects a callable to confirm the
declaration is true (threat **T15**).

**Silent downgrade of judgement roles is registry-contingent.** The resolver
escalates to the next capable candidate when a candidate's model chain is
exhausted, so an empty `fallback_models` list alone does not force a halt.
Today's halt-and-surface behaviour holds only because `irreversible-judgement`
is allocated exclusively to two `principal` employees that both carry empty
chains. A registry edit (threat **T3**) could restore silent downgrade with no
code change.

Everything else — scope conformance, registry protection, ledger immutability,
reviewer independence, input-directive resistance, approval validation,
ratification integrity, suspension discipline, and the consultation/delegation
boundary — is today constrained by norms, evidence, and human audit, **not** by
prevention.

The highest-severity residual gaps are **T16** (legacy ungoverned
entrypoints), **T10** (ratification integrity), **T1** (direct bypass, raised
to High at r4 because T16 and T17 are undetectable by the guard), **T7**
(instruction smuggling), and **T2** (scope creep under superset staffing).
Closing any of them mechanically is future enforcement work, explicitly out of
this phase's scope; candidates are flagged in `06_SUBSTRATE_BINDING.md` §4.

T16 deserves the top slot on honesty grounds: it is the only threat here where
a real, currently-executable command in `bin/` reaches a real model with no
governance whatsoever and no possibility of detection. Every other gap in this
register concerns the strength of a control on the governed path; T16 concerns
work that never enters it.
