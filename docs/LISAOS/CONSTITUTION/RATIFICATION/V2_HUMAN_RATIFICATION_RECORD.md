# Lisa OS Constitution v2 — Human Ratification Record

> **STATUS: EXECUTED — RATIFIED BY THE HUMAN AUTHORITY**
>
> This document is prepared for execution by the human authority. It is **not**
> itself a ratification and confers no constitutional force.
>
> Two things remain, and only Roshan Crasta may perform them:
>
> 1. complete §7 (the ratification statement, in his own words) and §9 (signature);
> 2. append the canonical ledger record in §8 to
>    `reports/lisa/ratification_records.jsonl`.
>
> Until the ledger record in §8 exists, Constitution v2 remains
> **PROPOSED — PENDING HUMAN RATIFICATION** and the pre-existing governance
> surfaces remain operative (Art. IX.3–4).

---

## 1. Why this document is unexecuted

Article IX.5 provides:

> **No actor may ratify.** Lisa and workers may not create, assert, simulate, or
> infer ratification, and may not complete a ratification metadata block.
> Attempting to do so is an attempt to forge authority (threat T10).

Every part of this record that states a *verified fact* was prepared by the
independent reviewer. Every part that constitutes the *act of ratifying* is left
blank. Article IX.9 states that no artifact inside this system can prove a
ratification record was written by the human rather than fabricated by an actor;
the only real protection is that the human writes it. That protection is
preserved here deliberately.

## 2. Ratification authority

| Field | Value |
|---|---|
| Sole authority source | **Roshan Crasta** (Art. II.1) |
| Power exercised | Ratification of a canonical P0 artifact — human-only and non-delegable (Art. VIII.1) |
| Delegability | None. No actor, including Lisa, may exercise or simulate this power (Art. IX.5) |
| Instrument of effect | A named human record appended to `reports/lisa/ratification_records.jsonl` (Art. IX.3) |
| Effect of this markdown file | **None.** Metadata and narrative are a mirror, not an instrument (Art. IX.4) |

## 3. Subject of ratification

| Field | Value |
|---|---|
| Constitutional version | `2.0.0` (proposal revision `2.0.0-proposed-r8`) |
| Proposal tag | `CONSTITUTION-V2-R8-PROPOSED` |
| Annotated tag object | `93abdc72b0c0e3707e3e9917f02d421e57eae1e7` |
| Constitutional commit | `0fcc68a5531b6c811b7eeb279f1ce9035f4e7365` |
| Immediate parent | `c0c2b13f2d148b50e1df27f7329d96a237233351` |

**Ratified constitutional set — these seven documents and nothing else** (Art. V, Art. I.1A):

```text
docs/LISAOS/CONSTITUTION/00_LISA_CONSTITUTION_V2.md
docs/LISAOS/CONSTITUTION/01_AUTHORITY_MODEL.md
docs/LISAOS/CONSTITUTION/02_PERMISSION_CONTRACTS.md
docs/LISAOS/CONSTITUTION/03_PROTECTED_ARTIFACTS.md
docs/LISAOS/CONSTITUTION/04_AUDIT_AND_EVIDENCE.md
docs/LISAOS/CONSTITUTION/05_THREAT_MODEL.md
docs/LISAOS/CONSTITUTION/06_SUBSTRATE_BINDING.md
```

**Expressly outside the ratified set.** `PROPOSALS/README.md` is class P4
supporting documentation (`04` §1.5). `identity/IDENTITY.md` and
`lisaos/agents/lisa/SOUL.md` are P0-protected but are **descriptive subordinate
instruments, never ratified constitutional text** (Art. I.1A). `REVIEWS/`,
`RATIFICATION/`, and `HISTORY.md` are evidence and supporting records, not
constitutional text.

## 4. Verification basis

Independently established by the reviewer prior to execution:

| Basis | Result |
|---|---|
| Constitutional review chain | r4 → r5 → r6 → r7 → r8, each against a frozen tag |
| r6 independent review | Verdict **C — REMEDIATION REQUIRED**; 23 enforcement claims verified in code; 34 adversarial probes, none falsifying a claim |
| Test suite at r6 | 477 total, 438 passed, 39 skipped, 0 failures, 0 errors — independently reproduced |
| r5 review recovery | Preserved verbatim; repository SHA-256 `f1f8532c…d30a03` verified byte-for-byte against the original output plus one trailing LF |
| r7 final review | Verdict **B**; three documentation self-description defects identified |
| r8 staged-delta review | Verdict **A — APPROVE R8 CANDIDATE FOR COMMIT**; all three r7 blockers resolved |
| Freeze continuity | **PASS** — 12 mechanical checks; candidate-to-freeze delta is exactly two `REVIEWS/` paths |
| Audit chain | Every cited revision basis r2–r8 is inspectable or expressly recorded unavailable without reconstruction |

**Disclosed limitations, carried into this record rather than omitted:**

- The independent reviewer for r6–r8 is Claude Opus 5 (Anthropic). Family
  independence holds against the r6/r7/r8 author (Codex/OpenAI) but **not**
  against inherited r2/r3 Claude-family text (`04` §4).
- The same reviewer executed the r8 commit and freeze under explicit
  authorization. No constitutional content was authored by it.
- Raw-payload hashes, message IDs, and timestamps in the recovered-review
  provenance tables were **not** independently verified; session-transcript
  reads were declined. Repository hashes, LF normalization, and content fidelity
  were verified.
- The r5 review is **advisory**: it failed six-condition condition 3 and
  satisfies no constitutional independent-review requirement.
- Accepted residual risks **R5-1** (`functools.wraps` provenance inheritance)
  and **R5-2** (process-wide re-marking of the shared `simulated_executor`)
  remain open, disclosed, and adversarially reproduced. Ratification adopts them
  as accepted risks.
- Ratification integrity itself is **norm-only**; threat **T10 remains High**
  (Art. IX.9).

## 5. Freeze continuity verification

| Check | Result |
|---|---|
| Tag annotated, not lightweight | PASS |
| `rev-parse` tag → `93abdc72b0c0e3707e3e9917f02d421e57eae1e7` | PASS |
| `rev-parse` tag`^{}` → `0fcc68a5531b6c811b7eeb279f1ce9035f4e7365` | PASS |
| Single parent `c0c2b13f…` | PASS |
| Candidate→freeze delta is exactly two `REVIEWS/` paths | PASS |
| Zero changes to `00`–`06` or `PROPOSALS/README.md` | PASS |
| Version `2.0.0-proposed-r8` and pending status in all eight documents | PASS |
| Predecessor tags r4–r7 unchanged | PASS |
| No commit between evidence closure and tag target | PASS |
| No merge, no push, no ratification evidenced | PASS |

**Result: PASS — FREEZE CONTINUITY VERIFIED.** The independently approved
candidate became the immutable proposal without an intervening content change.

## 6. Effective governance statement — takes effect only on execution

Upon the ledger record in §8 being appended by the ratifier, and not before:

1. Constitution v2, as frozen at commit `0fcc68a5531b6c811b7eeb279f1ce9035f4e7365`,
   becomes the **governing constitutional authority** of Lisa OS.
2. Article II.5 instrument precedence becomes operative (Art. IX.8).
3. `identity/IDENTITY.md`, `lisaos/agents/lisa/SOUL.md`,
   `governance/GOVERNANCE.md`, `governance/SECURITY.md`, and
   `lisaos/policies/governance.yml` survive as **subordinate instruments**.
   None is repealed; the Constitution supersedes their uncoordinated precedence
   only (Art. II.5, `00` metadata).
4. The Article IX.6 amendment path becomes the sole route to constitutional
   change: draft in `PROPOSALS/` → independent review → recorded human
   ratification. The Article IX.7 genesis exception is spent and
   **non-precedential**; no future proposal may rely on it.
5. Enforcement states remain exactly as classified in `06_SUBSTRATE_BINDING.md`.
   Ratification confers normative force; it does **not** convert any norm-only
   control into a mechanical one.

## 7. Ratification statement — COMPLETED BY THE RATIFIER

`04` §1.5 requires "an explicit ratification statement **in the ratifier's own
words**." It is left blank deliberately; no actor may supply it.

```text
RATIFIER:            Roshan Crasta

RATIFICATION
STATEMENT:           I have reviewed Constitution v2 and the supporting ratification materials. I understand the authority boundaries, protected artifacts, audit requirements, and amendment process, and I approve this Constitution as the governing framework for Lisa OS.

DECISION BASIS:      Independent architectural and constitutional review of Constitution v2 revision r8, including verification of the proposal tag, immutable commit, authority model, permission contracts, protected artifacts, audit requirements, threat model, substrate binding, amendment process, and ratification instrument.

DATE AND TIME
(ISO-8601 + tz):     2026-08-01T11:22:38+04:00
```

## 8. Canonical ledger record — the operative instrument

**This, not the markdown above, is what ratifies.** Append one line to
`reports/lisa/ratification_records.jsonl` (append-only, class P2; corrections
only by superseding record). All ten fields are mandatory — a record missing any
field "is not a ratification record and has no effect" (`04` §1.5).

This is the exact line appended to the ledger. No field is a placeholder.

```json
{"record_type":"ratification","ratifier":"Roshan Crasta","constitutional_version":"2.0.0","document_set_id":"0fcc68a5531b6c811b7eeb279f1ce9035f4e7365","text_reference":{"kind":"git-commit","value":"0fcc68a5531b6c811b7eeb279f1ce9035f4e7365","documents":["docs/LISAOS/CONSTITUTION/00_LISA_CONSTITUTION_V2.md","docs/LISAOS/CONSTITUTION/01_AUTHORITY_MODEL.md","docs/LISAOS/CONSTITUTION/02_PERMISSION_CONTRACTS.md","docs/LISAOS/CONSTITUTION/03_PROTECTED_ARTIFACTS.md","docs/LISAOS/CONSTITUTION/04_AUDIT_AND_EVIDENCE.md","docs/LISAOS/CONSTITUTION/05_THREAT_MODEL.md","docs/LISAOS/CONSTITUTION/06_SUBSTRATE_BINDING.md"]},"ratified_at":"2026-08-01T11:22:38+04:00","statement":"I have reviewed Constitution v2 and the supporting ratification materials. I understand the authority boundaries, protected artifacts, audit requirements, and amendment process, and I approve this Constitution as the governing framework for Lisa OS.","basis":"Independent architectural and constitutional review of Constitution v2 revision r8, including verification of the proposal tag, immutable commit, authority model, permission contracts, protected artifacts, audit requirements, threat model, substrate binding, amendment process, and ratification instrument.","evidence_id":"LISA-CONSTITUTION-V2-RATIFICATION-20260801-2E376D59","supersedes":null}
```

Notes on two fields the schema calls out specifically:

- `ratified_at` is the timestamp Article II.5 temporal supersession orders by.
- `basis` must state **which independent review it relies on**. The r8
  staged-delta review (verdict A) and the freeze continuity check (PASS) are
  preserved in `docs/LISAOS/CONSTITUTION/REVIEWS/`. The r5 review is advisory
  only and cannot carry this field alone.

## 9. Signature block — SIGNED

```text
I, the undersigned sole authority source of Lisa OS, having read the ratified
constitutional set at the commit identified in §3, and having accepted the
residual risks disclosed in §4, ratify Constitution v2 as the governing
constitutional authority of Lisa OS.


SIGNED:      Roshan Crasta

NAME:        Roshan Crasta

DATE:        2026-08-01T11:22:38+04:00

LEDGER
EVIDENCE ID: LISA-CONSTITUTION-V2-RATIFICATION-20260801-2E376D59
```

## 10. Execution checklist

- [ ] §7 completed in the ratifier's own words
- [ ] §8 ledger line completed and appended to `reports/lisa/ratification_records.jsonl`
- [ ] §9 signed
- [ ] This document's status banner updated from **UNEXECUTED INSTRUMENT** to **EXECUTED**
- [ ] `HISTORY.md` ratification entry and status updated
- [ ] `ADR-000` status updated from `Proposed` to `Accepted`
- [ ] `MILESTONES.md` human-ratification milestone checked
- [ ] `docs/LISAOS/README.md` constitutional section updated from proposed to ratified

Each item is a one-line edit. None may be performed before the ledger record
exists.

---

*Prepared by the independent reviewer as an unexecuted instrument. This
preparation is a specification act, not an enforcement or ratification one
(Art. IX.3, IX.5, IX.9).*
