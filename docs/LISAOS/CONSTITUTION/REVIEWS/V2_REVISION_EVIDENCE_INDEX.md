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
| r6 | Commit `d5be4e916577dfc8715bb6ca9a09445ef72e7626`; annotated tag `CONSTITUTION-V2-R6-PROPOSED`, tag object `9a5e07edb7fcec849345d8dd427fdc1f25deb9e1`. | `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R6_REMEDIATION_EVIDENCE.md`; recovered original review `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R6_INDEPENDENT_REVIEW.md`; the r5 review above is its source finding artifact. | The remediation packet is part of the immutable r6 tree. The later-recovered r6 review is not part of the r6 or r7 frozen trees; its recovery provenance is recorded below. Codex/OpenAI authored r6 and remains permanently disqualified from independently reviewing it. r6 remains proposed and unratified. |
| LCR-01 — Constitutional Audit Chain Completion | Documentation-only change committed at `91e291f3556a834f1d6520fb336ee0f78112152a` and frozen as `CONSTITUTION-V2-R7-PROPOSED`, annotated tag object `0a074479fd71493c0ddb6771e8c5f4c7f17c8e40`. The r4, r5, and r6 annotated proposal tags remained unmoved. | This index; the recovered r5 review; the LCR-01 addendum in `V2_R6_REMEDIATION_EVIDENCE.md` §13; metadata links in all eight proposal files; recovered original delta review `LCR_01_TARGETED_INDEPENDENT_DELTA_REVIEW.md`. | No constitutional semantics, governance behavior, implementation, or tests changed. The delta review returned **A — APPROVE FOR COMMIT** and stated that its prior r6 verdict C was satisfied by LCR-01. |
| r7 | Commit `91e291f3556a834f1d6520fb336ee0f78112152a`; annotated tag `CONSTITUTION-V2-R7-PROPOSED`, tag object `0a074479fd71493c0ddb6771e8c5f4c7f17c8e40`. | Recovered original final review `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R7_FINAL_INDEPENDENT_RATIFICATION_REVIEW.md`; LCR-01 evidence above. | The final review returned **B — REMEDIATION REQUIRED BEFORE HUMAN RATIFICATION** for three documentation-only self-description/evidence-state defects. It approved the constitutional substance, implementation, tests, threat model, and accepted residual risks. r7 remains proposed and unratified. |
| r8 committed candidate | Candidate commit `c0c2b13f2d148b50e1df27f7329d96a237233351`; parent `91e291f3556a834f1d6520fb336ee0f78112152a`; subject `docs(constitution): prepare v2 r8 ratification candidate`. `CONSTITUTION-V2-R8-PROPOSED` does not yet exist, and no r8 tag object is claimed. The r4–r7 annotated proposal tags remain unchanged. | Exact staged-delta review `docs/LISAOS/CONSTITUTION/REVIEWS/V2_R8_TARGETED_INDEPENDENT_STAGED_DELTA_REVIEW.md`, verdict **A — APPROVE R8 CANDIDATE FOR COMMIT**; this index; uniform r8 proposal metadata; the three earlier recovered reviews; later audit-chain annotations in `V2_R6_REMEDIATION_EVIDENCE.md`; the permitted NB1 factual-locus correction. | The r8 documentation candidate is committed and remains unratified. The next authorized action is to freeze the evidence-closure commit under the annotated `CONSTITUTION-V2-R8-PROPOSED` tag. This row neither invents nor predicts a tag object SHA. |

### r8 freeze sequencing note

The evidence-closure commit, rather than
`c0c2b13f2d148b50e1df27f7329d96a237233351`, will be the commit frozen by
`CONSTITUTION-V2-R8-PROPOSED` because it includes the exact independent review
of the staged r8 delta and the accurate committed-candidate evidence state. No
further content commit should intervene between that evidence-closure commit
and the later authorized annotated-tag operation.

## Recovered independent-review provenance

The following original Claude Opus 5 assistant outputs were recovered from
`~/.claude/projects/-Users-lisa-Lisa/d55a656e-22e6-4166-9dd1-f3fb05125549.jsonl`
(session id `d55a656e-22e6-4166-9dd1-f3fb05125549`). Each repository artifact
is the exact text payload plus one repository-standard final line feed. None
is reconstructed from a prompt, summary, terminal excerpt, or memory.

| Review artifact | Message id | Source record UUID | Emitted at | Raw payload SHA-256 | Repository artifact SHA-256 | Normalization |
|---|---|---|---|---|---|---|
| `V2_R6_INDEPENDENT_REVIEW.md` | `msg_011CdZnN5xXXyYSvGTDEzE5W` | `02ca052f-ee87-4d69-9b7c-b3faa6681d19` | `2026-07-31T08:02:51.320Z` | `6374fc2126533e3958f899f8689a8f2682e6f4ad25aaf3b1b65164ac06735c0e` | `4e9baef2cc5a3208dd8ca164826fec88fe35d55a9fee2cf2f1638a61cbe595e5` | Original payload had no final LF; exactly one LF added |
| `LCR_01_TARGETED_INDEPENDENT_DELTA_REVIEW.md` | `msg_011CdZpQB1RWML1Kvfe7txv6` | `0cd1864f-8481-4826-8837-80583ab2dd1a` | `2026-07-31T08:27:58.102Z` | `cb9747a2c1e82b5ca9964955ff6534f4e2c42ac9f9f6f73ec0081c6d0e5f62cf` | `6af443d18a5404d0b8273b5f2ab4476ab3ba0b65afee0f274fc842358f6b216f` | Original payload had no final LF; exactly one LF added |
| `V2_R7_FINAL_INDEPENDENT_RATIFICATION_REVIEW.md` | `msg_011CdZuRAYW9FvGMUZ8qGKdJ` | `d80981c1-7699-4eda-9a69-13995e51a0ae` | `2026-07-31T09:34:09.151Z` | `13cf8c081aabe765ffadaf9659a2c86628eacf5ab27fad6b145197db75161f79` | `792d35a8833bc3fc311960b72928a125df2d9a8485fb027d06d05efcb2dcd15a` | Original payload had no final LF; exactly one LF added |
| `V2_R8_TARGETED_INDEPENDENT_STAGED_DELTA_REVIEW.md` | `msg_011CdZyDSbHVGe4sX2LbXToe` | `7f113a02-9acd-42b7-a1be-1f10a78c32fc` | `2026-07-31T10:23:34.367Z` | `7506073fce612d444e4a67679063c5f9f42df103b1c21277a58f9eb6ad01a3ea` | `edbf9e48a2bdadfd41ad59162a43ef32d6dc6db4b09264758356f7153b17f948` | Original payload had no final LF; exactly one LF added |

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
