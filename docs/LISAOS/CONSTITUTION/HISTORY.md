# Lisa OS Constitution v2 — Constitutional History

> This is a historical record, not constitutional text. It has no constitutional
> force and ratifies nothing (Art. IX.2, IX.4).

Every immutable identity below was independently verified against the
repository. Where an original artifact is unavailable, that absence is recorded
rather than reconstructed.

---

## Timeline

### Conception — Phase 1 Constitutional Governance Layer

Lisa OS operated a real AI workforce — dispatcher, workforce resolver, policy
engine, governance guard, execution bridge, registries, evidence ledger — that
enforced the *mechanics* of governed work but supplied no *norms*. Constitution
v2 was conceived to answer who holds authority, how it is granted, what is
protected, and what happens when certainty runs out.

The v2 document set was drafted directly in the canonical directory under the
**Article IX.7 genesis exception**, because it predates the operation of its own
proposal workflow. That exception is transitional, non-precedential, and now
spent.

| Revision | Character |
|---|---|
| r2 | Remediation of author self-audit **S044** (blockers B1–B8, corrections A1–A9). No immutable r2 commit or tag exists; the original self-audit artifact is unavailable and is not reconstructed. |
| r3 | Set-wide revision incorporating the Claude Fable 5 advisory audit (2026-07-30) and the BF-1/BF-2/M1/M2 corrections. First committed set, at `f06e26d0a9ffb404db2c1b042aaa8cd453bb5a11`. No r3 tag. The original advisory review is unavailable. Advisory only — did **not** satisfy the independent review gate. |

### r4 — first independent constitutional review

| Field | Value |
|---|---|
| Commit | `e695cfa99c512c1a724ecc1acda7eb7064de41d6` |
| Tag object | `0b16828e43d657355f75bddec0dc42a9b89b794f` |

Remediation of the independent Codex review (OpenAI/GPT-5): B1 ratification
instrument specification, B2 execution-outcome evidence, B3 executor provenance
and attribution truth, B4 identity and simulation classifications, B5 amendment
precedence. The review was **advisory** — it failed the six-condition test on
evidence-baseline access — and did not satisfy the constitutional gate. The
review packet was committed separately at `25ec6beec2e26b883724a9b68b67bea88d892daf`.

### r5 — claims, implementation, and tests in one commit

| Field | Value |
|---|---|
| Commit | `247d3eb76d6f2ac08e5307134b80e5458b4b00d3` |
| Tag object | `e7564cd5d6028d3f7b59069ae22a804f5d9069bc` |

The first revision in which the constitutional enforcement claims, their
implementation, and their tests existed in the same commit. r5 also corrected
the T15 residual-risk wording, which at r4 had wrongly stated that accidental
attribution laundering was impossible.

The r5 independent review returned **C — REMEDIATION REQUIRED BEFORE
RATIFICATION** with eight findings, ADV-01 through ADV-08. It existed only in a
session archive at the time and was recovered later (see r8). Its own
six-condition result is **advisory**: condition 3 failed.

### r6 — evidence integrity remediation

| Field | Value |
|---|---|
| Commit | `d5be4e916577dfc8715bb6ca9a09445ef72e7626` |
| Tag object | `9a5e07edb7fcec849345d8dd427fdc1f25deb9e1` |

Remediated ADV-01 (strict provenance validation at construction and every run),
ADV-02 (complete `ExecutionResult` validation, exact-Boolean `success`),
ADV-03 (JSON-safe evidence, flush/fsync append, evidence-before-completion
ordering, systemic `EvidenceSinkError` halt), ADV-05 (disclosure of process-wide
re-marking), and ADV-06 (removal of absolute silent-laundering claims).
ADV-04 was accepted as residual risk R5-1; ADV-07 and ADV-08 were non-blocking.

The independent r6 review returned **C — REMEDIATION REQUIRED BEFORE
RATIFICATION**. It verified 23 mechanically enforced claims, ran 34 adversarial
probes without falsifying any claim, and independently reproduced the test suite
at 477 total / 438 passed / 39 skipped / 0 failures / 0 errors. Its single
blocking finding was evidentiary, not technical: the r5 review that r6 cited as
its basis existed nowhere in the repository, and ADV-04 was unaccounted for.

### LCR-01 — Constitutional Audit Chain Completion

Documentation-only. Recovered the original r5 review verbatim, completed the
revision evidence chain, recorded the ADV-04 disposition, bound the r6
remediation packet to its immutable identity, and distinguished historical S044
from LCR-01. The independent delta review returned **A — APPROVE FOR COMMIT**
and recorded that the prior r6 verdict C was satisfied.

### r7 — audit-chain freeze

| Field | Value |
|---|---|
| Commit | `91e291f3556a834f1d6520fb336ee0f78112152a` |
| Tag object | `0a074479fd71493c0ddb6771e8c5f4c7f17c8e40` |

The final independent ratification review returned **B — REMEDIATION REQUIRED
BEFORE HUMAN RATIFICATION**. It approved the constitutional substance,
implementation, tests, threat model, and accepted residual risks, but found three
documentation defects in the freeze's own self-description: the proposal did not
identify itself as r7 (all eight documents still declared `2.0.0-proposed-r6`),
the revision-evidence index declared itself uncommitted inside the commit that
contained it, and the r6 packet banner described committed additions as
working-copy-only.

### r8 — self-identification and evidence-state remediation

| Field | Value |
|---|---|
| Candidate commit | `c0c2b13f2d148b50e1df27f7329d96a237233351` |
| Evidence-closure commit | `0fcc68a5531b6c811b7eeb279f1ce9035f4e7365` |
| Tag object | `93abdc72b0c0e3707e3e9917f02d421e57eae1e7` |

All three r7 blockers resolved: uniform `2.0.0-proposed-r8` across all eight
documents with a uniform r8 revision-basis row; the evidence index bound to the
real LCR-01 commit and r7 tag object; the r6 packet banner recording the r7
identity and distinguishing later annotations from contemporaneous evidence.
Three permitted factual corrections were applied (the NB1 evidence-literal locus,
the r5 advisory qualification, and historical framing of the r6 review status).

The independent staged-delta review returned **A — APPROVE R8 CANDIDATE FOR
COMMIT**. The three prior reviews were recovered and preserved verbatim in
`REVIEWS/`, each with provenance and repository SHA-256.

### Proposal freeze

The evidence-closure commit `0fcc68a5531b6c811b7eeb279f1ce9035f4e7365` was
frozen under annotated tag `CONSTITUTION-V2-R8-PROPOSED`, tag object
`93abdc72b0c0e3707e3e9917f02d421e57eae1e7`. Tags r4–r7 remained unmoved. Nothing
was pushed, merged, or ratified.

### Freeze continuity verification

Twelve mechanical checks confirmed the independently approved candidate became
the immutable proposal without an intervening content change. The
candidate-to-freeze delta is exactly two `REVIEWS/` paths; zero changes to
`00`–`06` or `PROPOSALS/README.md`.

**Result: PASS — FREEZE CONTINUITY VERIFIED.**

### Human ratification

**PERFORMED.**

| Field | Value |
|---|---|
| Ratifier | Roshan Crasta |
| Ratified at | `2026-08-01T11:22:38+04:00` |
| Ledger `evidence_id` | `LISA-CONSTITUTION-V2-RATIFICATION-20260801-2E376D59` |
| Ratified commit | `0fcc68a5531b6c811b7eeb279f1ce9035f4e7365` |
| Proposal tag | `CONSTITUTION-V2-R8-PROPOSED` (tag object `93abdc72b0c0e3707e3e9917f02d421e57eae1e7`) |
| Ledger | `reports/lisa/ratification_records.jsonl` |

Constitution v2 became the governing constitutional authority of Lisa OS at the
moment that ledger record was appended (Art. IX.3).

---

## Current Governing Constitution

**Version:**
Lisa OS Constitution v2 — proposal revision `2.0.0-proposed-r8`

**Frozen at:**
`CONSTITUTION-V2-R8-PROPOSED` → commit `0fcc68a5531b6c811b7eeb279f1ce9035f4e7365`

**Effective:**
1 August 2026

**Status:**
**RATIFIED**

**Ratified by:** Roshan Crasta · **Ratified at:** `2026-08-01T11:22:38+04:00`
· **Ledger evidence_id:** `LISA-CONSTITUTION-V2-RATIFICATION-20260801-2E376D59`

> The pre-existing governance surfaces (`governance/GOVERNANCE.md`,
> `governance/SECURITY.md`, `lisaos/policies/governance.yml`,
> `identity/IDENTITY.md`, `lisaos/agents/lisa/SOUL.md`) survive as subordinate
> instruments. None is repealed; only their uncoordinated precedence is
> superseded (Art. II.5).
