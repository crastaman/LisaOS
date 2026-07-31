# Constitutional Proposal Area

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> This area's rules take effect only upon recorded human ratification of
> Constitution v2 (`../00_LISA_CONSTITUTION_V2.md`, Art. IX.3).

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r8 |
| Revision evidence index (r8) | `docs/LISAOS/CONSTITUTION/REVIEWS/V2_REVISION_EVIDENCE_INDEX.md` maps every cited r2–r8 revision basis to an immutable object and repository evidence artifact, or records the original artifact as unavailable without reconstruction. It records LCR-01 at commit `91e291f3556a834f1d6520fb336ee0f78112152a`, frozen as `CONSTITUTION-V2-R7-PROPOSED` (annotated tag object `0a074479fd71493c0ddb6771e8c5f4c7f17c8e40`), and identifies the exact recovered independent-review artifacts and their provenance. The r4, r5, and r6 proposal tags remained unmoved. This row records no ratification and changes no constitutional semantics. |
| Revision basis (r8) | r8 — documentation-only correction following the final independent review of `CONSTITUTION-V2-R7-PROPOSED` (verdict **B — REMEDIATION REQUIRED BEFORE HUMAN RATIFICATION**). It corrects proposal self-identification and evidence-state accuracy; records the immutable LCR-01/r7 identity; preserves the exact recovered r6, LCR-01 delta, and r7 final review outputs with provenance; and applies only the permitted factual documentation corrections for NB1, r5 advisory status, and ADV-04 post-freeze provenance. It introduces no constitutional semantic, governance, implementation, architecture, test, threat-model, or residual-risk change. Frozen predecessor: `CONSTITUTION-V2-R7-PROPOSED`, commit `91e291f3556a834f1d6520fb336ee0f78112152a`, annotated tag object `0a074479fd71493c0ddb6771e8c5f4c7f17c8e40`, preserved unchanged. The proposal remains **PROPOSED — PENDING HUMAN RATIFICATION**. |
| Prior revision basis (r6) | r6 — remediation authored by **Codex / OpenAI** following the independent Codex r5 verdict **C. REMEDIATION REQUIRED BEFORE RATIFICATION**. Frozen predecessor: `CONSTITUTION-V2-R5-PROPOSED`, commit `247d3eb76d6f2ac08e5307134b80e5458b4b00d3`, preserved unchanged. r6 remediates **ADV-01** with one strict string-and-membership provenance validator at construction and every run; **ADV-02** with complete `ExecutionResult` validation and normalized failure evidence; **ADV-03** with strict JSON-safe evidence, flush/fsync append, evidence-before-completion ordering, and an explicit systemic halt on sink failure; **ADV-05** with explicit disclosure of process-wide re-marking of the shared simulated executor; and **ADV-06** by removing absolute silent-laundering claims. Surviving accepted residuals: `functools.wraps` may accidentally copy a valid declaration, and `mark_executor` may deliberately mark or re-mark a callable; strict vocabulary validation does not prove semantic truth. Contemporaneous authoring evidence: `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R6_REMEDIATION_EVIDENCE.md`. Because Codex authored r6, Codex is permanently disqualified from independently reviewing r6. **At the r6 freeze, r6 had not yet been independently reviewed or ratified; its later independent review and verdict C are preserved and indexed separately.** |
| Prior revision basis (r5) | r5 — version tracking only; no rule in this file changed at r5. The r5 set commits the enforcement implementation and its tests alongside the constitutional text, and corrects the T15 residual-risk wording. **The recovered r5 review is an independent review with substantial historical and technical evidentiary value, but it did not satisfy the constitutional independent-review gate because condition 3 failed; for ratification it is advisory.** |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report — `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md` (Phase 0 architecture sprint; originated as a project-conversation artifact and was **not** committed when this document set was drafted — prepared as a verbatim preserved historical-evidence transcription on 2026-07-30 and included in the immutable r4 proposal baseline (`e695cfa9`), carried forward unchanged into r5; no formal acceptance record exists) |

---

## Purpose

This directory is the **only** place where proposed amendments to canonical
P0 artifacts (the Constitution, identity and human-authority declarations,
amendment and supremacy rules) may be drafted. It is ordinary writable space
(class P4): any actor — Lisa or a worker — may draft here under a normal task
grant.

## Rules

1. **Nothing in this directory has any force, ever.** A proposal is text, not
   authority.
2. **Only Roshan ratifies, and only through the ratification record.** A
   proposal becomes canon only through the named human ratification record
   described in Constitution Art. IX.3 and
   `../04_AUDIT_AND_EVIDENCE.md` §1.5, which identifies the exact ratified
   text by commit, digest, or equivalent immutable reference. Moving or copying
   a file into the canonical directory does **not** ratify it, and completing a
   metadata block has **no constitutional effect**.
3. **Drafting grants nothing.** Writing, reviewing, or iterating on a
   proposal confers no authority over its subject matter.
4. **No actor may simulate ratification.** Lisa and workers may not create,
   assert, simulate, or infer a ratification, and may not fill in a
   ratification metadata block (threat T10).
5. **Proposals are evidenced.** A proposal drafted under a task grant appears
   in the evidence ledger like any other governed output.

## Genesis exception (transitional, non-precedential)

The initial v2 document set was drafted directly in the canonical
`docs/LISAOS/CONSTITUTION/` directory because it predates the operation of this
proposal workflow (Constitution Art. IX.7). That exception covers the
pre-ratification genesis set **only**. After ratification, every P0 amendment
must originate here, and **no future proposal may rely on the genesis
exception.**

## Conventions

- One proposal per file: `PROPOSAL_<YYYY-MM-DD>_<short-kebab-topic>.md`.
- Each proposal states: the canonical artifact and clause it would amend, the
  proposed text, the rationale, and the evidence motivating the change.
- Rejected or superseded proposals stay in place, marked
  `REJECTED` / `SUPERSEDED` — the drafting history is part of the audit
  trail.
