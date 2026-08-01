# Lisa OS — Milestones

> Programme tracker. Not constitutional text; has no constitutional force.

## Governance Phase — complete pending ratification

| | Milestone | Evidence |
|---|---|---|
| ✅ | **Constitutional Architecture** | Seven-document set `00`–`06`: authority ontology, roles by authority class, permission contracts, protected artifacts, audit and evidence, threat model, substrate binding |
| ✅ | **Constitutional Governance** | Default-deny, instrument precedence, four fail-closed halt levels, human-only powers, Article IX amendment path |
| ✅ | **Independent Review Framework** | Six-condition validity test; five frozen revisions and four independent reviews (r5 C, r6 C, LCR-01 A, r7 B, r8 A), each against an immutable tag |
| ✅ | **Evidence Preservation** | Revision evidence index r2–r8; four independent reviews recovered verbatim with provenance and SHA-256; unavailable artifacts recorded as unavailable, never reconstructed |
| ✅ | **Proposal Freeze** | `CONSTITUTION-V2-R8-PROPOSED` → `93abdc72b0c0e3707e3e9917f02d421e57eae1e7` → commit `0fcc68a5531b6c811b7eeb279f1ce9035f4e7365`; freeze continuity **PASS**, r4–r7 tags unmoved |
| ✅ | **Human Ratification** | Ratified by Roshan Crasta at `2026-08-01T11:22:38+04:00`; ledger record `LISA-CONSTITUTION-V2-RATIFICATION-20260801-2E376D59` appended to `reports/lisa/ratification_records.jsonl` (Art. IX.3) |

**Governance is complete. Constitution v2 is ratified and governing.**
Article II.5 instrument precedence is operative; the Article IX.7 genesis
exception is spent; every future P0 amendment must originate in `PROPOSALS/`
and take the Article IX.6 path.

---

## Implementation Phase — begins next

| | Milestone | Notes |
|---|---|---|
| ⬜ | **Runtime Foundation** | Substrate the governed path depends on |
| ⬜ | **Dispatcher** | Ready-frontier scheduler exists and is constitutionally pinned. Remaining: retire or govern the ungoverned entrypoints `bin/lisa` and `bin/lisa-core` (threat T16 — the sharpest current gap, ungoverned execution reachable by one command) |
| ⬜ | **Workforce Manager** | Record cross-employee candidate substitution; close the `PolicyEngine` approval-metadata gap so an absent flag is never read as approval |
| ⬜ | **Context Manager** | — |
| ⬜ | **Checkpoint / Resume** | — |
| ⬜ | **Agent Runtime** | Bind provenance to something the substrate observes rather than to a callable attribute, closing residual risks R5-1 and R5-2 |
| ⬜ | **Constitutional Enforcement** | Convert norm-only controls to mechanical ones, ranked by threat: T16 legacy entrypoints, T10 ratification integrity, T9 approval validation, T2 scope conformance, T3 registry/P1 write protection, T4 ledger immutability, T17 binding guard clearance to the invocation. Two structural additions carry several at once: an append-only human-act ledger with a named-operator contract, and an artifact-class field on the work package. A production call site for `require_clean()` is the cheapest first win |
| ⬜ | **Autonomous Engineering** | — |
| ⬜ | **WBS Integration** | — |

---

## Standing constraints on the Implementation Phase

Carried from the constitutional record; these bind implementation work
regardless of milestone order.

- **Ratification confers normative force only.** It converts no norm-only
  control into a mechanical one. The verified clause-by-clause status lives in
  `06_SUBSTRATE_BINDING.md` and must be kept true as implementation proceeds
  (Art. X).
- **Enforcement is scoped to the governed path.** Every "Enforced" claim applies
  to work entering through `core/dispatcher.py`. Widening a claim requires
  widening the substrate first, then the document — never the reverse.
- **Accepted residual risks stay disclosed until mechanically closed.** R5-1,
  R5-2, T10, T16, T17 are accepted, not solved. Removing a disclosure without
  closing the underlying route is an Article X violation.
- **Escalation, not innovation.** At any boundary, ambiguity, or obstacle, the
  sanctioned move is evidenced escalation. Improvised workarounds are violations
  regardless of outcome (Art. IV.3).
- **P1 work needs independent, family-independent review** plus an episodic
  human grant (`04` §5).
