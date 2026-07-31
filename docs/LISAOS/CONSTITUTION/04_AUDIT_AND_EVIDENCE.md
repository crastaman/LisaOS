# Audit, Evidence, and Independent Review

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> No constitutional force until recorded human ratification of Constitution v2
> (Art. IX.3). Revising this document does not ratify it.

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r6 |
| Revision basis | r6 — remediation authored by **Codex / OpenAI** following the independent Codex r5 verdict **C. REMEDIATION REQUIRED BEFORE RATIFICATION**. Frozen predecessor: `CONSTITUTION-V2-R5-PROPOSED`, commit `247d3eb76d6f2ac08e5307134b80e5458b4b00d3`, preserved unchanged. r6 remediates **ADV-01** with one strict string-and-membership provenance validator at construction and every run; **ADV-02** with complete `ExecutionResult` validation and normalized failure evidence; **ADV-03** with strict JSON-safe evidence, flush/fsync append, evidence-before-completion ordering, and an explicit systemic halt on sink failure; **ADV-05** with explicit disclosure of process-wide re-marking of the shared simulated executor; and **ADV-06** by removing absolute silent-laundering claims. Surviving accepted residuals: `functools.wraps` may accidentally copy a valid declaration, and `mark_executor` may deliberately mark or re-mark a callable; strict vocabulary validation does not prove semantic truth. Contemporaneous authoring evidence: `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R6_REMEDIATION_EVIDENCE.md`. Because Codex authored r6, Codex is permanently disqualified from independently reviewing r6. **r6 has not been independently reviewed or ratified.** |
| Prior revision basis (r5) | r5 — **first proposal revision in which the constitutional enforcement claims, their implementation, and their tests exist in the same commit.** r5 incorporates the dispatcher/evidence enforcement implementation itself: execution outcome (`execution_success` / `execution_error`) and declared executor provenance (`execution_provenance`) are carried into the evidence record and serialized; the dispatcher fails closed on undeclared executor provenance at construction and at every run; an empty-required-capability guard fails closed in `candidates_for()`; and the tests pinning these controls (`tests/test_r4_remediation.py`, updated `tests/test_dispatcher.py`) are included. r5 also corrects the T15 residual-risk wording, which in r4 wrongly stated that accidental attribution laundering was impossible — a `functools.wraps` route remains open and is now recorded rather than denied. r5 **supersedes r4 only as a proposal revision, not as a ratified Constitution**; r4 remains immutably preserved at commit `e695cfa99c512c1a724ecc1acda7eb7064de41d6` (tag `CONSTITUTION-V2-R4-PROPOSED`). **r5 has not been independently reviewed.** Prior: r4 — remediation of the **independent Codex constitutional review** (OpenAI/GPT-5) as reconciled by the subsequent independent assessment: B1 ratification instrument specification, B2 execution-outcome evidence, B3 executor provenance and attribution truth, B4 identity and simulation classifications, B5 amendment precedence, plus the confirmed non-blocking findings (guard clearance, candidate substitution, incorporation boundary, planner/P4 coherence, approval authority, legacy entrypoints, threat-model completeness). The Codex review was **advisory** — it failed the six-condition test on evidence-baseline access only — and does **not** satisfy the independent constitutional gate. Prior: r3 — enforcement-honesty remediation of the Claude Fable 5 advisory audit (BF-1 approval metadata path-dependence; M1 execution-evidence literals; M2 procedural governance-guard invocation). That audit was **advisory** and does **not** satisfy the independent constitutional gate. Prior: r2 — remediation of author self-audit S044 (B4 ratification record, A2 correction path, A3 approval expiry, A4 execution-mode evidence) |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report — `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md` (Phase 0 architecture sprint; originated as a project-conversation artifact and was **not** committed when this document set was drafted — prepared as a verbatim preserved historical-evidence transcription on 2026-07-30 and included in the immutable r4 proposal baseline (`e695cfa9`), carried forward unchanged into r5; no formal acceptance record exists); code verification of `core/governance_guard.py`, the `WorkAssignment` evidence model and `Dispatcher.__init__` executor contract in `core/dispatcher.py` (2026-07-30) |

---

## 1. Evidence obligations

1. Every governed action is required to yield an **append-only, attributed
   evidence record**: actor identity, the grant/assignment it acted under,
   artifact classes touched, and outcome. An evidence-sink failure does not
   make that requirement true by assertion: it prevents successful completion
   and triggers the systemic halt described below.
   - The existing `WorkAssignment` evidence schema carries actor, staffing,
     and routing attribution (mechanically enforced on the governed path).
   - **Outcome is now carried** (r4, finding B2). `execution_success` and
     `execution_error` are populated by the dispatcher from the
     `ExecutionResult` and serialized into the ledger, so a failed execution
     is distinguishable from a successful one in the evidence record itself.
     Before r4 those two values lived only in the in-memory `DispatchReport`,
     which meant the ledger stated this requirement without meeting it.
     `None` on both means *not executed*, which is distinct from *failed*.
   - **Declared executor provenance is now carried** (r4, finding B3).
     `execution_provenance` records which class of executor ran the package.
     See §1.7.
   - The grant-reference and artifact-class fields remain **normative
     additions**; changing the schema for those is later work, outside this
      phase's scope. This carve-out covers those two fields only — it has never
      covered outcome.
   - **The governed dispatcher path now treats evidence as the completion
     boundary** (r6, ADV-02/ADV-03). Executor returns are validated before
     reconciliation. A non-`ExecutionResult`, a non-boolean `success`, or any
     malformed field used by reconciliation becomes a normalized failed
     `WorkAssignment`, which is then evidenced. The assignment is converted to
     a strict JSON-safe schema and serialized before the ledger is opened; the
     serialized line is appended, flushed, and `fsync`ed before successful
     graph completion is recorded. Serialization or append failure raises an
     explicit systemic evidence-sink halt and all non-terminal graph work is
     represented as failed, not successfully complete.
   - This is a **process/filesystem durability contract**, not a metaphysical
     persistence guarantee. Disk, kernel, filesystem, process, hardware, or
     out-of-band failure can still destroy or corrupt evidence. A sink failure
     also means the dispatcher may be unable to record the halt itself in that
     sink; the raised error and in-memory failed graph state are the available
     fail-closed signals.
2. **No evidence = ungoverned.** Work without a ledger record is
   constitutionally identical to a bypass — exactly as the governance guard
   already treats production-shaped subagents with no evidence record.
3. Human acts — episodic approvals, violation acknowledgements, release
   authorizations, suspension clearings, and ratifications — are evidenced
   with named operator and reason. An unevidenced approval is no approval
   (threat T9).
4. Evidence ledgers are P2 artifacts: append-only, corrections by superseding
   record (`03_PROTECTED_ARTIFACTS.md` §2A), no edits or deletes by any actor.

### 1.5 The human ratification record

Ratification of a constitutional document set becomes effective **only**
through a named human ratification record appended to the governance evidence
mechanism. That record — not any document's metadata block — is the sole
source of ratification authority (Constitution Art. IX.3–5).

**Canonical destination** (r4, finding B1): `reports/lisa/ratification_records.jsonl`
— one JSON object per line, append-only, class P2 (`03_PROTECTED_ARTIFACTS.md`
§1). Corrections are made only by appending a superseding record
(`03_PROTECTED_ARTIFACTS.md` §2A); no actor edits or deletes an existing line. This file is the destination Article
IX.3 refers to when it says "the governance evidence mechanism"; before r4 that
phrase named no specific ledger, which left the sole constitutional instrument
without an address.

**Required schema.** Every field is mandatory; a record missing any field is
not a ratification record and has no effect:

| Field | Type | Meaning |
|---|---|---|
| `record_type` | string | Literal `"ratification"` — distinguishes these records from any other appended to the ledger |
| `ratifier` | string | The named human ratifier (the authority source, `01_AUTHORITY_MODEL.md` §1) |
| `constitutional_version` | string | e.g. `2.0.0` — the version being ratified |
| `document_set_id` | string | The immutable document-set identifier (commit SHA, or an aggregate digest over the ratified constitutional set `00`–`06`) |
| `text_reference` | object | `{"kind": "git-commit" \| "digest", "value": "<sha>", "documents": [<P0 paths>]}` — the exact ratified text |
| `ratified_at` | string | ISO-8601 with timezone. This is the timestamp Article II.5 temporal supersession orders by |
| `statement` | string | An explicit ratification statement in the ratifier's own words |
| `basis` | string | Reason or decision basis, including which independent review it relies on |
| `evidence_id` | string | Stable identifier for this record |
| `supersedes` | string \| null | `evidence_id` of a prior record this corrects, or `null` |

Scope note: the document-set identifier and `text_reference.documents` cover
the **ratified constitutional set (`00`–`06`) only** — not the P0-protected
identity declarations, which are never ratified (Art. I.1A).
`PROPOSALS/README.md` is class P4 supporting
documentation and is never part of the ratified text.

Absent a valid record, the document set remains proposed and non-operative no
matter what any metadata block says. Lisa and workers may not create, assert,
simulate, or infer ratification (threat T10).

*Enforcement status: norm-only — specification, not enforcement.* The
destination and schema above are now fully specified, which removes the
"instrument with no address" defect. What has **not** changed: no mechanism
validates a ratification record, no code reads this ledger, and nothing can
establish that a record's `ratifier` was human rather than an actor writing a
string. Any validator would itself be P1 code editable by the actors it
constrains (threat T3), so this gap is not closable from inside the system —
see Constitution Art. IX.9. The nearest existing pattern is the attributed
acknowledgement path in `core/governance_guard.py`, which likewise requires a
named operator and likewise cannot verify humanness. Periodic human audit of
this ledger is the only real control. **Threat T10 remains High.**

### 1.6 Execution mode must be distinguishable

Evidence must record **how** a result was produced. Recognised modes:

real execution · dry run · simulation · replay · mocked validation ·
static analysis · human observation

Simulated, mocked, replayed, or statically-derived evidence may support design
or logic validation, but **may never be represented as proof of real
execution**, and never satisfies a requirement for real-execution evidence.

*Enforcement status: partially enforced — the strongest of the evidence
controls.* Verified in code: `WorkAssignment.execution_evidence_source` records
the mode. **Simulation labelling is no longer caller-dependent** (r4, finding
B4c): `core.dispatcher.simulated_executor` stamps `"SIMULATED-NOT-EXECUTED"`
itself, so every route through the dispatcher API — not only the
`bin/lisa-dispatch --simulate` CLI path via
`core.openclaw_bridge.labelled_simulated_executor` — produces labelled
simulated evidence. Before r4 the bare dispatcher-API executor produced
simulated records with an empty mode field.
Values **actually emitted at runtime** include
`"SIMULATED-NOT-EXECUTED"`, `"openclaw_json_response+task_runs_confirmed"`, and
a family of `"fail-closed-*"` literals written by `core/openclaw_bridge.py` and
`core/dispatcher.py` — for example `"fail-closed-no-identity-agent"`,
`"fail-closed-identity-agent-unavailable"`, `"fail-closed-subprocess-error"`,
`"fail-closed-bad-json-response"`. That list is **illustrative, not
exhaustive**; the authoritative set is whatever those two modules emit. Two
distinctions matter for audit: the string `"fail-closed-no-eligible-agent"`
appears only in an explanatory **comment** on the `WorkAssignment` field and in
a **test fixture** (`tests/test_anti_regression.py`) — it is not an emitted
runtime value; and `core/anti_regression.py` classifies by the
`"fail-closed"` / `"real-execution-failed"` **prefix** family rather than by
any fixed literal. Auditors must not treat comments, fixtures, or conceptual
examples in this document as evidence that a given literal was emitted.
Further verified: `observed_model`, `observed_provider`, and
`execution_run_id` are populated only by a real executor; `mismatch` and
`mismatch_detail` flag divergence between resolved and observed runtime; and
`Dispatcher.__init__` **raises** when no executor is passed, so simulation can
no longer be selected by omission. What remains norm-only: the mode vocabulary
above is broader than the field's current values (dry run, replay, mocked
validation, static analysis, and human observation have no canonical
encoding), and nothing prevents a reader from misreading a simulated record as
a real one. Presenting simulated evidence as real execution is threat T14.

### 1.7 Execution attribution must be sourced, not assumed

Evidence must record **who** performed a governed action on the basis of
something the substrate actually knows, never on the basis of an assumption
baked into the recorder.

*Enforcement status: partially enforced — declaration-based* (r6, ADV-01,
ADV-05, ADV-06). Every executor passed to the dispatcher must carry a
provenance value that is exactly a string and exactly one of `worker-real`,
`worker-simulated`, or `main-inline`. One canonical validator is used by
`mark_executor`, dispatcher construction, and every `run()`. Missing, empty,
unknown, non-string, or post-construction-invalid values fail closed before
execution. The currently validated declaration is recorded as
`WorkAssignment.execution_provenance`, and worker/main attribution in
`DispatchMetrics` is derived from it.

Before r4 the dispatcher accepted any callable and recorded every completion
as `by_main=False` — an assertion of worker execution it had no basis for.
An in-process orchestrator function could perform the work and the delegation
metric would still read 100%.

**What this does not do.** A declaration is not a proof. Strict vocabulary
validation proves only that a recognized string is present; it does not prove
that the callable performs the declared kind of execution. What is removed is
the dispatcher's own hardcoded assumption: an invalid declaration is refused
rather than replaced with an attribution.

Two distinct routes to false attribution remain, and neither is closed in r6:

- **accidental** — a `functools.wraps` wrapper that *replaces* rather than
  *delegates to* a marked executor inherits its declaration, because
  `functools.wraps` copies `__dict__`;
- **deliberate** — `mark_executor` can mark any callable with any valid
  declaration, including deliberately mis-marking a main-process callable.
  It can also re-mark the shared `simulated_executor` function object. Because
  that object is shared, the mutation is process-wide for callers holding that
  same object.

Simulation labelling and provenance attribution are separate dimensions:
`simulated_executor` still stamps `execution_evidence_source` with
`SIMULATED-NOT-EXECUTED`, even if its shared provenance declaration is
deliberately re-marked. Both routes above are threat T15 and accepted residual
risks. A false attribution is therefore not necessarily deliberate, and
evidence bearing `execution_provenance` should be read as *what the executor
declared*, never as proof of what ran. r6 does not claim callable declarations
are inherently trustworthy or that silent attribution laundering is
impossible.

## 2. Audit duties

1. **Periodic human audit** of the ledgers, rather than machine self-audit,
   is the backstop for every norm-only control.
2. Sprint entry must run the governance guard's fail-closed check.
   *Enforcement status: partial — mechanical after invocation, procedural in
   invocation.* Once `require_clean()` is called it is genuinely mechanical: it
   raises `GovernanceGuardError` until every violation is acknowledged, and
   that halt is a graph/sprint-entry halt in the sense of Constitution
   Art. VII.2(a). But verified 2026-07-30 by call-site search, **no production
   entry point invokes it** — `core/dispatcher.py` does not call it, and the
   only call sites in the repository are in `tests/test_governance_guard.py`.
   Invocation therefore depends on caller discipline, and this clause is an
   **operating duty on whoever opens a sprint**, not an automatic gate. This
   matches the `Partial` classification in `06_SUBSTRATE_BINDING.md` §3.
2A. **How the guard clears an invocation, and why that is weak** (r4, finding
   N1). The guard clears a production-shaped subagent invocation when its
   **name** matches any `work_package_id` *or* `employee` id appearing
   anywhere in the entire workforce evidence ledger, with no binding to the
   invocation's own session, transcript, or time
   (`core/governance_guard.py`). Two consequences follow, and auditors must
   assume both:
   - **Employee ids are permanent.** Once `chief-architect` (or any employee
     id) appears in the ledger, *any* subagent invocation with that name is
     cleared forever. This is not merely replayable — it is a standing
     whitelist that grows as the ledger grows.
   - **Evidence is not bound to the act.** A match proves that *something*
     with that name was once governed, never that *this* invocation was.
   A cleared invocation is therefore weak evidence of governance, not proof
   of it. This is threat T17; the control is periodic human audit.
3. Acknowledgement of a violation never retroactively governs the work; it
   records that a named human reviewed and accepted the deviation.
   *Enforcement status: partially enforced — the guard requires a non-empty,
   attributed operator, but cannot verify the operator is human; "the
   operator is human, and is never Lisa" is norm-only.*
4. Episodic approvals must carry the fields listed in
   `01_AUTHORITY_MODEL.md` §4.3, including an expiry or single-use marker. An
   approval with no stated expiry is single-use and lapses with the sprint or
   session in which it was issued; audit should treat any approval reused
   beyond its scope as an unevidenced act (threat T8).

## 3. Independent review — validity test

A review is constitutionally **valid** only when all six conditions hold:

1. **Separate assignment.** The review runs under its own task grant, not as
   a sub-step of the authored work.
2. **No authorship participation.** The reviewer took no part in producing
   the artifact under review.
3. **Evidence baseline access.** The reviewer can see the assignment, its
   evidence records, and the accepted prior state.
4. **Authority to disagree or reject.** Rejection is a normal, recordable
   outcome, not an escalation.
5. **No instruction to defend.** The reviewer received no direction to
   defend, justify, or rubber-stamp the implementation.
6. **Independence disclosure.** Where provider or model-family independence
   is unavailable, that fact is disclosed in the review evidence.

A review failing any condition satisfies no review requirement. Self-review
satisfies nothing, and a review authored by the same actor that produced the
artifact is disclosed as an author self-check, never recorded as an
independent review.

## 4. Model-family independence

Different model family is **mandatory for P1 and security-class work where
technically available**. Identity-level separation can be illusory: at the
time of writing, the `codex` and `gpt` logical identities both resolve to the
same physical model (`openai/gpt-5.5`), so a codex-reviews-gpt pairing is
*not* family independence and must be disclosed under §3.6.

A fallback that would collapse reviewer independence is not an acceptable
substitute even when technically available
(`02_PERMISSION_CONTRACTS.md` §3B).

## 5. Review requirements by class

| Work | Required review |
|---|---|
| P1 changes | Independent review (six-condition valid, family-independent where available) + episodic human grant |
| P3 changes in restricted policy classes | Independent review + the policy-required approval |
| Other governed output | Per the employee contract's `review_class` |

*Enforcement status: reviewer independence is norm-only today — no mechanism
checks any of the six conditions. The policy approval classes in
`lisaos/policies/governance.yml` are likewise norm-only (verified 2026-07-30:
no code reads that file). The substrate can mechanically **flag** one approval
condition, but **only on one staffing path**: `WorkforceResolver.resolve()`
sets `WorkAssignment.operator_approval_required` to `True` (and populates
`fallback_level`) when a fallback model is used on non-low-risk work.
`PolicyEngine.resolve()` builds its `WorkAssignment` without setting either
field, so they fall back to `operator_approval_required = False` and
`fallback_level = None` regardless of whether a fallback was used — a
**substrate gap**, verified 2026-07-30 in `core/policy_engine.py`. Auditors
must therefore treat an absent flag as *no signal*, never as evidence that
approval was unnecessary or given. Even where the flag is set, it signals that
approval is required without verifying that approval was given.*
