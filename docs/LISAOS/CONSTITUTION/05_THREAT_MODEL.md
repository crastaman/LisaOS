# Threat Model — Actor Overreach

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> No constitutional force until recorded human ratification of Constitution v2
> (Art. IX.3). Revising this document does not ratify it.

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r3 |
| Revision basis | r3 — enforcement-honesty remediation of the Claude Fable 5 advisory audit (BF-1 T9 approval-flag path-dependence; BF-2 registry-contingent no-downgrade in the honest summary). That audit was **advisory** and does **not** satisfy the independent constitutional gate. Prior: r2 — remediation of author self-audit S044 (A6 superset staffing in T2, A8 orchestrator-specific threats T10–T14) |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report (accepted 2026-07-30); code verification of `core/governance_guard.py`, `core/policy_engine.py`, `core/dispatcher.py`, `core/workforce_resolver.py` (2026-07-30) |

---

## Scope

Threats from authority actors — execution workers, the orchestrator, and
reviewers — exceeding, evading, or fabricating authority. T1–T9 concern
workers and delegation; T10–T14 concern the orchestrator and the evidence
layer specifically. External attackers and infrastructure compromise are out
of scope for this document.

Enforcement status vocabulary follows Constitution Art. X: **enforced**,
**partial**, **norm-only**. No control below is claimed as stronger than
verified.

## Threat register

| # | Threat | Constitutional control | Enforcement today (verified) | Residual risk |
|---|---|---|---|---|
| **T1** | **Direct bypass** — work executed outside dispatcher/resolver governed dispatch | Task authority exists only via governed dispatch; no evidence = ungoverned | **Partial.** Governance guard scans subagent transcripts, records violations, fails closed until human-acknowledged — but matching is a name-prefix heuristic; non-matching names evade (stated in the guard's own docstring) | Medium — detection, not prevention; heuristic gap acknowledged |
| **T2** | **Scope creep** inside a legitimate assignment, amplified by superset staffing | The assignment is the whole authority; Escalation-not-Innovation; unused capabilities confer no authority (`02` §3A) | **Norm-only.** Assignments are recorded; scope conformance is not checked. The resolver deliberately staffs a **capability superset** of the package (verified), so a worker routinely holds more capability than its package needs — the §1 intersection is a norm, not a runtime bound | High — the widest norm-only gap for workers |
| **T3** | **Self-elevation by configuration** — editing registries/contracts to gain authority | Canonical registries are P1: human grant + independent review required | **Norm-only.** Files are ordinarily writable | Medium — after-the-fact audit is the control |
| **T4** | **Evidence tampering or omission** | Ledgers are P2 append-only; correction only by superseding record (`03` §2A) | **Partial.** Owning components only append (verified); nothing prevents out-of-band edit/delete | Medium — filesystem offers no immutability |
| **T5** | **Reviewer capture** — self-review, instructed defence, or correlated models | Six-condition review validity test; family independence for P1/security; disclosure duty | **Norm-only.** No mechanism checks any condition; the codex/gpt physical-model collapse makes correlation a live concern | Medium |
| **T6** | **Authority laundering via chained delegation** — a worker privately re-delegating | Grants are non-transitive; re-delegation must re-enter governed dispatch | **Partial** (same guard heuristic as T1) | Medium |
| **T7** | **Instruction smuggling** — a worker acting on directives embedded in its inputs | Authority is explicit, never inferred: input content is never a grant | **Norm-only.** Inherent LLM risk; permission contracts limit blast radius | High — accepted and named, not solved |
| **T8** | **Stale or replayed authority** — acting on an expired assignment or old approval | Grants expire; approvals carry expiry or are single-use by default (`01` §4.3); never retroactive | **Partial.** Assignments are per-run instruments; approval expiry is unchecked | Low–Medium |
| **T9** | **Approval fabrication** — proceeding on a claimed but unrecorded human approval | Approvals are instruments: they exist only as recorded evidence; an unevidenced approval is no approval | **Norm-only; flagging is path-dependent.** Verified 2026-07-30: no code reads `lisaos/policies/governance.yml` or validates any approval before execution. The substrate can *flag* the need (`operator_approval_required`) **only on the `WorkforceResolver` path**; `PolicyEngine.resolve()` never sets it, so the field defaults to `False` even on non-low-risk fallback staffing. An absent flag is not approval. Nothing on either path checks satisfaction | Medium–high |
| **T10** | **Forged or self-asserted ratification** — an actor completing a metadata block, or otherwise asserting that the Constitution is in force | Ratification is effective **only** via the named human ratification record; metadata is a mirror with no constitutional effect; no actor may ratify (Art. IX.3–5) | **Norm-only.** P0 files are ordinarily writable and no ratification validator exists. The control is structural: authority was moved out of the writable artifact into the evidence record | High — the sharpest orchestrator-layer gap |
| **T11** | **Self-asserted or unbounded standing authority** — the orchestrator treating its coordination grant as general authority, or inventing an operational bound it was never given | Bounded standing grant with explicit may/may-not lists and bounding formula (`01` §3A); operational bounds come from instruments; missing bound ⇒ escalate | **Partial.** One component is genuinely enforced: `core/dispatcher.py` has no code path by which the orchestrator can execute a package. Goal scope, spend ceilings, and artifact scope are unchecked | Medium–high |
| **T12** | **Self-clearing governance suspension** — the orchestrator lifting its own halt, or reclassifying an S2–S4 suspension as S1 to make it self-clearable | Suspension classes S1–S4 with clearing authority; Lisa may clear S1 only; reclassification prohibited; uncertain class ⇒ higher class (Art. VII.3–5) | **Norm-only.** No suspension mechanism or class field exists yet; the guard's sprint-entry halt is the nearest existing analogue and it does require human acknowledgement | Medium |
| **T13** | **Consultation treated as delegated authority** — a consulted worker acting on artifacts, or a peer `escalates_to` hop being read as a grant | Consultation transfers no authority and creates no grant; `escalates_to`/`avoid_tasks` are routing hints, not grants; authority escalates upward only (`01` §6.1–6.2) | **Norm-only.** `escalates_to` and `failure_policy` load into the `Employee` model, but nothing routes escalations or distinguishes consultation from delegation | Medium |
| **T14** | **Simulated evidence presented as real execution** | Evidence must record execution mode; simulated/mocked/replayed evidence may never be represented as proof of real execution (`04` §1.6) | **Partial — the best-defended threat here.** `execution_evidence_source` carries an explicit `"SIMULATED-NOT-EXECUTED"` marker; real-executor-only fields (`observed_model`, `execution_run_id`) stay empty under simulation; `mismatch` flags divergence; and `Dispatcher.__init__` raises when no executor is passed, so simulation cannot be selected by omission (all verified) | Low–Medium |

## Honest summary

The Gen 3 substrate mechanically constrains staffing, routing, identity, and
evidence *on the governed path*, and it genuinely prevents two specific
overreaches: the orchestrator executing work itself, and simulation-by-omission.

A third — silent downgrade of judgement roles — is **registry-contingent, not
structural**. The resolver escalates to the next capable candidate when a
candidate's model chain is exhausted, so an empty `fallback_models` list alone
does not force a halt. Today's halt-and-surface behaviour holds only because
`irreversible-judgement` is allocated exclusively to two `principal` employees
that both carry empty chains. A registry edit (threat **T3**) could restore
silent downgrade with no code change, which makes this protection dependent on
norm-only P1 registry governance.

Everything else — scope conformance, registry protection, ledger immutability,
reviewer independence, input-directive resistance, approval validation,
ratification integrity, suspension discipline, and the consultation/delegation
boundary — is today constrained by norms, evidence, and human audit, **not** by
prevention.

The three highest-severity residual gaps are T10 (ratification integrity),
T7 (instruction smuggling), and T2 (scope creep under superset staffing).
Closing any of them mechanically is future enforcement work, explicitly out of
this phase's scope; candidates are flagged in `06_SUBSTRATE_BINDING.md` §4.
