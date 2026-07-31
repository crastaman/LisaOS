# Lisa OS Constitution v2 — Revision Evidence Index

## Purpose

This documentation-only index makes the revision bases cited by the
Constitution v2 proposal metadata inspectable without treating a later summary
as missing historical evidence.

It changes no constitutional rule, enforcement classification, implementation,
or test. Where an original artifact is unavailable, the index records that
absence and does not reconstruct it.

## Revision chain

| Revision | Immutable proposal or inspectable state | Review/remediation evidence | Availability and limits |
|---|---|---|---|
| r2 | No immutable r2 commit or tag was found. The first committed Constitution v2 set is r3 at `f06e26d0a9ffb404db2c1b042aaa8cd453bb5a11`; its metadata contains retrospective per-file descriptions of r2. | No standalone r2 author self-audit artifact was found in the repository, visible Git history, reflogs, stashes, unreachable objects, or scoped local session search. | **Original artifact unavailable.** The r2 B/A item lists in later metadata are historical author summaries, not independently inspectable original evidence. They are preserved but not upgraded into proof. |
| r3 | Commit `f06e26d0a9ffb404db2c1b042aaa8cd453bb5a11`, subject `docs(constitution): freeze v2 r3 proposed baseline for independent review`. No r3 proposal tag exists. | No standalone Claude Fable 5 advisory-review output was found in the repository or scoped recovery sources. The r4 packet records its advisory classification retrospectively. | The r3 tree and r3→r4 diff are inspectable. The original advisory review is unavailable and is not reconstructed. |
| r4 | Commit `e695cfa99c512c1a724ecc1acda7eb7064de41d6`; annotated tag `CONSTITUTION-V2-R4-PROPOSED`, tag object `0b16828e43d657355f75bddec0dc42a9b89b794f`. | `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R4_INDEPENDENT_REVIEW_PACKET.md`, committed separately at `25ec6beec2e26b883724a9b68b67bea88d892daf`. | The packet is supporting evidence added after the frozen r4 proposal. It expressly distinguishes retrospective provenance from contemporaneous evidence and records unavailable earlier-review evidence. |
| r5 | Commit `247d3eb76d6f2ac08e5307134b80e5458b4b00d3`; annotated tag `CONSTITUTION-V2-R5-PROPOSED`, tag object `e7564cd5d6028d3f7b59069ae22a804f5d9069bc`. | `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R5_INDEPENDENT_REVIEW.md`. Recovery provenance and hashes are in `V2_R6_REMEDIATION_EVIDENCE.md` §13. | The review was recovered verbatim from the original Codex session output. It is not reconstructed. Its own six-condition result is advisory because condition 3 failed. |
| r6 | Commit `d5be4e916577dfc8715bb6ca9a09445ef72e7626`; annotated tag `CONSTITUTION-V2-R6-PROPOSED`, tag object `9a5e07edb7fcec849345d8dd427fdc1f25deb9e1`. | `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R6_REMEDIATION_EVIDENCE.md`; the r5 review above is its source finding artifact. | The remediation packet is part of the immutable r6 tree. Codex/OpenAI authored r6 and is permanently disqualified from independently reviewing it. r6 remains proposed and unratified. |
| LCR-01 — Constitutional Audit Chain Completion | Post-r6 documentation-only candidate; not staged, committed, or tagged. | This index; the recovered r5 review; the LCR-01 addendum in `V2_R6_REMEDIATION_EVIDENCE.md` §13; metadata links in all eight proposal files. | No constitutional semantics, implementation, or tests changed. The immutable r4/r5/r6 tags are not moved by this candidate. |

## Finding chain for r6

| r5 review finding | r6 disposition | Inspectable location |
|---|---|---|
| ADV-01 | Mechanically remediated | Recovered r5 review §6; r6 remediation evidence §§5, 9 |
| ADV-02 | Mechanically remediated | Recovered r5 review §6; r6 remediation evidence §§5, 9 |
| ADV-03 | Mechanically remediated | Recovered r5 review §6; r6 remediation evidence §§5, 9 |
| ADV-04 | Accepted residual risk (R5-1); not mechanically closed; contradictory absolute wording handled by ADV-06 | Recovered r5 review §§6–7; r6 remediation evidence §§5, 10, 13 |
| ADV-05 | Disclosure remediated; underlying R5-2 route remains accepted | Recovered r5 review §§6–7; r6 remediation evidence §§5, 9–10 |
| ADV-06 | Contradictory absolute wording removed/qualified | Recovered r5 review §6; r6 remediation evidence §§5, 9 |
| ADV-07 | Non-blocking future identity-validation enhancement | Recovered r5 review §§6, 12 |
| ADV-08 | Non-blocking historical test-count correction | Recovered r5 review §§4, 6, 12 |

## Historical-evidence rules

1. A Git commit or annotated tag identifies an immutable tree; a later review
   packet does not become part of that earlier tree.
2. A recovered artifact is identified as recovered and carries source
   provenance. It is not described as contemporaneously committed.
3. A missing original artifact remains missing. Later metadata may describe
   the historical decision, but that description is not the original evidence.
4. **Historical S044** identifies the r2 author self-audit described in
   proposal metadata. **LCR-01** identifies the post-r6 “Constitutional Audit
   Chain Completion” assignment. They are distinct assignments and this index
   does not conflate them.
5. No artifact in this index is a ratification record.
