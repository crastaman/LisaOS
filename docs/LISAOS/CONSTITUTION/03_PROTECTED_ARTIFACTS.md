# Protected Artifact Classes

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> No constitutional force until recorded human ratification of Constitution v2
> (Art. IX.3). Revising this document does not ratify it.

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r5 |
| Revision basis | r5 — **first proposal revision in which the constitutional enforcement claims, their implementation, and their tests exist in the same commit.** r5 incorporates the dispatcher/evidence enforcement implementation itself: execution outcome (`execution_success` / `execution_error`) and declared executor provenance (`execution_provenance`) are carried into the evidence record and serialized; the dispatcher fails closed on undeclared executor provenance at construction and at every run; an empty-required-capability guard fails closed in `candidates_for()`; and the tests pinning these controls (`tests/test_r4_remediation.py`, updated `tests/test_dispatcher.py`) are included. r5 also corrects the T15 residual-risk wording, which in r4 wrongly stated that accidental attribution laundering was impossible — a `functools.wraps` route remains open and is now recorded rather than denied. r5 **supersedes r4 only as a proposal revision, not as a ratified Constitution**; r4 remains immutably preserved at commit `e695cfa99c512c1a724ecc1acda7eb7064de41d6` (tag `CONSTITUTION-V2-R4-PROPOSED`). **r5 has not been independently reviewed.** Prior: r4 — remediation of the **independent Codex constitutional review** (OpenAI/GPT-5) as reconciled by the subsequent independent assessment: B1 ratification instrument specification, B2 execution-outcome evidence, B3 executor provenance and attribution truth, B4 identity and simulation classifications, B5 amendment precedence, plus the confirmed non-blocking findings (guard clearance, candidate substitution, incorporation boundary, planner/P4 coherence, approval authority, legacy entrypoints, threat-model completeness). The Codex review was **advisory** — it failed the six-condition test on evidence-baseline access only — and does **not** satisfy the independent constitutional gate. Prior: r3 — set-wide version harmonization only; no clause in this document was changed at r3. The r3 set incorporates the post-remediation advisory constitutional audit and the BF-1/BF-2 enforcement-honesty and M1/M2 factual corrections, which landed in `01`, `02`, `04`, `05`, `06`. That audit was **advisory** and does **not** satisfy the independent constitutional gate. Prior: r2 — remediation of author self-audit S044 (B4 ratification recording, A1 genesis clause, A2 evidence correction path) |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report — `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md` (Phase 0 architecture sprint; originated as a project-conversation artifact and was **not** committed when this document set was drafted — prepared as a verbatim preserved historical-evidence transcription on 2026-07-30 and included in the immutable r4 proposal baseline (`e695cfa9`), carried forward unchanged into r5; no formal acceptance record exists); `core/governance_guard.py` acknowledgement path verification (2026-07-30) |

---

## 1. Classes and change rules

| Class | Contents | Current file mapping | Change rule |
|---|---|---|---|
| **P0 — Constitutional & identity authority** | The Constitution; constitutional amendments; identity and human-authority declarations; amendment and supremacy rules | **Ratified constitutional text:** `docs/LISAOS/CONSTITUTION/00–06_*.md` (once ratified). **P0-protected but not ratified constitutional text:** `identity/IDENTITY.md`; `lisaos/agents/lisa/SOUL.md` | Modification of any P0 artifact is **human-only**. *Ratification* applies to the constitutional set only, and is effective only through the human ratification record (Constitution Art. IX.3). The two identity files are protected at P0 and are incorporated descriptively (Art. I.1A); they are not part of the ratified text and no ratification record covers them — r4, finding N4. Drafting proposed amendments is permitted **only** in the proposal area (§2). |
| **P1 — Governance & enforcement** | Operational governance policies; security policy; canonical workforce, provider and runtime registries; governance-enforcing code; dispatch and evidence schemas | `governance/GOVERNANCE.md`; `governance/SECURITY.md`; `lisaos/policies/governance.yml`; `registry/employees.yml`, `registry/provider_resolution.yml`, `registry/workforce_modes.yml`; `core/governance_guard.py`, `core/workforce_resolver.py`, `core/provider_resolver.py`, `core/policy_engine.py`, `core/dispatcher.py`, `core/openclaw_bridge.py`; the `WorkAssignment` / evidence-record schemas | Explicit episodic human grant **plus** independent review (family-independent where technically available). Never bundled into ordinary feature work. Not writable under the transitional access rule (`02_PERMISSION_CONTRACTS.md` §1.1). |
| **P2 — Evidence records** | The append-only governance ledgers | `reports/lisa/workforce_evidence.jsonl`, `reports/lisa/governance_violations.jsonl`, `reports/lisa/governance_acknowledgements.jsonl`, `reports/lisa/ratification_records.jsonl` (the canonical ratification ledger, Constitution Art. IX.3 / `04` §1.5 — added at r4) | Append-only, by the owning component. No actor edits or deletes; correction is a superseding appended record (§2A). Subject to periodic human audit. The ratification ledger has **no owning component**: it is written by a human act and read by human audit only — no code appends to or validates it (Art. IX.9). |
| **P3 — Production code** | Governed project code | Per project | Permission contracts + policy approval classes. |
| **P4 — Reports & docs** | Non-constitutional documentation and reports; the proposal area | Everything else; `docs/LISAOS/CONSTITUTION/PROPOSALS/` | Standard permission contracts. |

Notes:

- **Pre-ratification status of this document set.** Until the human
  ratification record exists, the files in
  `docs/LISAOS/CONSTITUTION/` are *proposed* P0 artifacts: they are handled
  with P0 care, but they carry no authority and are not yet canon. Revising
  them does not ratify them.
- Legacy registries (`registry/agents.yml`, `registry/runtimes.yml`) are
  transitional inputs, not P1 canon; they may be retired without amendment,
  and their prohibitions bind only where expressly adopted
  (`02_PERMISSION_CONTRACTS.md` §2A).
- Classification of a new artifact follows the fail-closed rule: if it
  plausibly belongs to a higher class, treat it as that class pending human
  classification (Constitution Art. VIII.2).

## 2. The proposal area

`docs/LISAOS/CONSTITUTION/PROPOSALS/` is ordinary writable space (class P4) in
which any actor — workers and the planner included — may draft proposed P0
amendments.

*Drafting note* (r4, finding N5): "protected artifact" in the actor limits at
`01_AUTHORITY_MODEL.md` §2 means classes **P0–P3**. P4 appears in the class
table in §1 for completeness of the classification, but it carries standard
permission contracts, and drafting here is expressly permitted to every actor.
Read literally against the old wording, the planner's "may never write
protected artifacts" would have barred the planner from the one place the
Constitution invites all actors to draft.

Rules:

1. Nothing in the proposal area has any force, ever.
2. A proposal becomes canon only through the human ratification record
   (Constitution Art. IX.3), which identifies the exact ratified text. Moving
   or copying a file into the canonical directory does **not** ratify it, and
   completing a metadata block has no constitutional effect.
3. Drafting, reviewing, or iterating on a proposal confers no authority over
   the subject matter of the proposal.
4. Proposals are evidenced: a proposal drafted under a task grant appears in
   the evidence ledger like any other governed output.

**Genesis exception (transitional, non-precedential).** The initial v2 document
set was drafted directly in this canonical directory because it predates the
operation of its own proposal workflow (Constitution Art. IX.7). The exception
covers that pre-ratification genesis set only. After ratification, every P0
amendment must originate in `PROPOSALS/`, and no future proposal may rely on
this exception.

See `PROPOSALS/README.md` for drafting conventions.

## 2A. Correcting erroneous evidence (P2)

Evidence is append-only, so an error is corrected by superseding it — never by
rewriting history.

A correction record must:

- **never** delete or rewrite the original record;
- be appended as a new, superseding record;
- reference the original evidence identifier;
- identify the correcting authority — the human authority, or the owning
  component acting under an explicit human instruction;
- state the reason and the corrected interpretation;
- preserve the full history, including the superseded record.

**Who may append.** Ordinary governed records are appended by the owning
component only. **Human corrections and human acts** — approvals,
acknowledgements, ratifications, suspension clearings — are appended by the
human authority, or by a component acting on an explicit, attributed human
instruction. The existing acknowledgement path in `core/governance_guard.py`
(`record_acknowledgement`, which refuses an empty operator) is the pattern to
follow. No worker appends a correction, and no actor may append a correction
on the human authority's behalf.

*Enforcement status: partially enforced.* Owning components only ever append
(verified in code), and `record_acknowledgement` requires a non-empty named
operator — but it cannot verify that the operator is human, and nothing
prevents an out-of-band file edit. Append-only is therefore a discipline plus
audit, not an immutability guarantee (threat T4).

## 3. Enforcement status

Write protection for P0 and P1 is **norm-only** today: the files are
ordinarily writable and no mechanism prevents an actor from editing them. This
is why ratification authority was moved out of the metadata block and into the
append-only human ratification record (Constitution Art. IX.3–5): a norm-only
protected file must not be the instrument that confers supreme authority.
Validation of that record is itself **norm-only** — no ratification ledger or
validator exists yet.

P2 append-only behaviour is **partially enforced**: the owning components only
ever append (verified in code), but nothing prevents an out-of-band edit or
delete.

These gaps are threats T3, T4, and T10 in `05_THREAT_MODEL.md`; the audit
duties in `04_AUDIT_AND_EVIDENCE.md` are the compensating control. This
document must not be read as claiming mechanical protection exists.
