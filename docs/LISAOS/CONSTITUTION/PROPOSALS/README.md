# Constitutional Proposal Area

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> This area's rules take effect only upon recorded human ratification of
> Constitution v2 (`../00_LISA_CONSTITUTION_V2.md`, Art. IX.3).

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r4 (tracks the constitutional set it accompanies; this file is **class P4**, not a member of the ratified constitutional set `00`–`06`) |
| Revision basis | r4 — version tracking only; no rule in this file changed at r4. The r4 set remediates the independent Codex constitutional review as reconciled by the subsequent independent assessment. That review was **advisory** and does **not** satisfy the independent constitutional gate. |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report — `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md` (Phase 0 architecture sprint; originated as a project-conversation artifact and was **not** committed when this document set was drafted — prepared as a verbatim preserved historical-evidence transcription on 2026-07-30 and included in this immutable r4 proposal baseline; no formal acceptance record exists) |

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
