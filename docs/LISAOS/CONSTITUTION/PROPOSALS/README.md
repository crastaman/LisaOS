# Constitutional Proposal Area

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> This area's rules take effect only upon recorded human ratification of
> Constitution v2 (`../00_LISA_CONSTITUTION_V2.md`, Art. IX.3).

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r6 (tracks the constitutional set it accompanies; this file is **class P4**, not a member of the ratified constitutional set `00`–`06`) |
| Revision evidence index (LCR-01) | `docs/LISAOS/CONSTITUTION/REVIEWS/V2_REVISION_EVIDENCE_INDEX.md` maps every cited r2–r6 revision basis to an immutable object and repository evidence artifact, or records the original artifact as unavailable without reconstruction. The original r5 review is preserved verbatim at `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R5_INDEPENDENT_REVIEW.md`; recovery provenance and ADV-04 disposition are recorded in `V2_R6_REMEDIATION_EVIDENCE.md` §13. This LCR-01 documentation-only row postdates the immutable r6 tag and changes no constitutional semantics. |
| Revision basis | r6 — remediation authored by **Codex / OpenAI** following the independent Codex r5 verdict **C. REMEDIATION REQUIRED BEFORE RATIFICATION**. Frozen predecessor: `CONSTITUTION-V2-R5-PROPOSED`, commit `247d3eb76d6f2ac08e5307134b80e5458b4b00d3`, preserved unchanged. r6 remediates **ADV-01** with one strict string-and-membership provenance validator at construction and every run; **ADV-02** with complete `ExecutionResult` validation and normalized failure evidence; **ADV-03** with strict JSON-safe evidence, flush/fsync append, evidence-before-completion ordering, and an explicit systemic halt on sink failure; **ADV-05** with explicit disclosure of process-wide re-marking of the shared simulated executor; and **ADV-06** by removing absolute silent-laundering claims. Surviving accepted residuals: `functools.wraps` may accidentally copy a valid declaration, and `mark_executor` may deliberately mark or re-mark a callable; strict vocabulary validation does not prove semantic truth. Contemporaneous authoring evidence: `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R6_REMEDIATION_EVIDENCE.md`. Because Codex authored r6, Codex is permanently disqualified from independently reviewing r6. **r6 has not been independently reviewed or ratified.** |
| Prior revision basis (r5) | r5 — version tracking only; no rule in this file changed at r5. The r5 set commits the enforcement implementation and its tests alongside the constitutional text, and corrects the T15 residual-risk wording. **r5 has not been independently reviewed.** |
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
