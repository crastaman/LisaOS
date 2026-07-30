# Audit, Evidence, and Independent Review

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> No constitutional force until recorded human ratification of Constitution v2
> (Art. IX.3). Revising this document does not ratify it.

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r3 |
| Revision basis | r3 — enforcement-honesty remediation of the Claude Fable 5 advisory audit (BF-1 approval metadata path-dependence; M1 execution-evidence literals; M2 procedural governance-guard invocation). That audit was **advisory** and does **not** satisfy the independent constitutional gate. Prior: r2 — remediation of author self-audit S044 (B4 ratification record, A2 correction path, A3 approval expiry, A4 execution-mode evidence) |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report (accepted 2026-07-30); code verification of `core/governance_guard.py`, the `WorkAssignment` evidence model and `Dispatcher.__init__` executor contract in `core/dispatcher.py` (2026-07-30) |

---

## 1. Evidence obligations

1. Every governed action yields an **append-only, attributed evidence
   record**: actor identity, the grant/assignment it acted under, artifact
   classes touched, and outcome.
   - The existing `WorkAssignment` evidence schema already carries actor,
     staffing, and routing attribution (mechanically enforced on the governed
     path). The grant-reference and artifact-class fields are **normative
     additions**; changing the schema itself is later work, outside this
     phase's scope.
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

Required contents:

- ratifier identity (a named human);
- constitutional version and immutable document-set identifier;
- date and time;
- an explicit ratification statement;
- reason or decision basis;
- evidence identifier;
- an immutable reference to the exact ratified text — repository state,
  commit, digest, or equivalent.

Absent a valid record, the document set remains proposed and non-operative no
matter what any metadata block says. Lisa and workers may not create, assert,
simulate, or infer ratification (threat T10).

*Enforcement status: norm-only.* No mechanism validates a ratification record,
and no ratification ledger exists yet. The nearest existing pattern is the
attributed acknowledgement path in `core/governance_guard.py`, which requires a
named operator but cannot verify that the operator is human.

### 1.6 Execution mode must be distinguishable

Evidence must record **how** a result was produced. Recognised modes:

real execution · dry run · simulation · replay · mocked validation ·
static analysis · human observation

Simulated, mocked, replayed, or statically-derived evidence may support design
or logic validation, but **may never be represented as proof of real
execution**, and never satisfies a requirement for real-execution evidence.

*Enforcement status: partially enforced — the strongest of the evidence
controls.* Verified in code: `WorkAssignment.execution_evidence_source` records
the mode. Values **actually emitted at runtime** include
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
