# ADR-000 — Constitution v2 as the Governing Authority of Lisa OS

| Field | Value |
|---|---|
| **Status** | **Accepted** — ratified 2026-08-01T11:22:38+04:00; ledger `evidence_id` `LISA-CONSTITUTION-V2-RATIFICATION-20260801-2E376D59` |
| Date | 2026-07-31 |
| Deciding authority | Roshan Crasta (sole authority source, Art. II.1) |
| Subject | Lisa OS Constitution v2, `2.0.0-proposed-r8` |
| Proposal tag | `CONSTITUTION-V2-R8-PROPOSED` (`93abdc72b0c0e3707e3e9917f02d421e57eae1e7`) |
| Constitutional commit | `0fcc68a5531b6c811b7eeb279f1ce9035f4e7365` |
| Supersedes | None — root ADR |

> **This ADR records a decision; it does not enact one.** Ratification is
> effective only through the ledger record described below (Art. IX.3). This
> document has no constitutional force (Art. IX.2, IX.4).

**Directory note.** Two ADR locations exist in this repository: `docs/ADR/`
(holding `ADR-0001-ENGINE-ABSTRACTION.md` and `ADR-0002-CAPABILITY-ROUTING.md`)
and this file at `docs/LISAOS/ADR/`, created at the path specified by the
ratification sprint. Consolidating them is future work; it is recorded here
rather than resolved, because reorganising existing engineering records is
outside this documentation-only sprint.

---

## Context

Lisa OS runs a real AI workforce. Before Constitution v2, the substrate enforced
the *mechanics* of governed work — dispatch, staffing, evidence append, bypass
detection — while the *norms* governing authority were spread across
uncoordinated instruments: `identity/IDENTITY.md`, `lisaos/agents/lisa/SOUL.md`,
`governance/GOVERNANCE.md`, `governance/SECURITY.md`, and
`lisaos/policies/governance.yml`. Nothing established which prevailed on
conflict, who could grant authority, or what happened when authority was unclear.

Two structural problems followed. First, an actor could act on capability rather
than on a recorded grant, because no instrument said that capability is not
permission. Second, and more corrosively, governance documents could assert
enforcement the substrate did not perform, with nothing to distinguish a
mechanically enforced rule from an aspiration.

Constitution v2 was drafted to close both: an authority ontology with explicit
precedence and default-deny, and a standing requirement (Article X) that every
constitutional document distinguish **mechanically enforced**, **partially
enforced**, and **norm-only** controls, with the verified clause-by-clause status
maintained in `06_SUBSTRATE_BINDING.md`.

The proposal was taken through five frozen revisions and four independent
reviews. Two returned verdict C and one returned verdict B. Each rejection was
remediated against a frozen tag rather than a moving working tree, and each
predecessor tag was preserved unmoved.

## Decision

**Adopt Lisa OS Constitution v2, as frozen at commit
`0fcc68a5531b6c811b7eeb279f1ce9035f4e7365`, as the governing constitutional
authority of Lisa OS** — effective upon execution of the human ratification
record, and not before.

The decision adopts, specifically:

1. **A single authority source.** Roshan Crasta. No instrument, including the
   Constitution, stands above the source (Art. II.1).
2. **Default-deny.** Authority exists only as a recorded grant. Capability is
   not permission; absence of prohibition is not permission; precedent is not
   permission; success does not launder an ungranted act (Art. IV).
3. **Instrument precedence** with narrowing-only, temporal supersession within a
   valid amendment chain, and fail-closed on non-orderable conflict (Art. II.5).
4. **Fail-closed governance** at four scoped halt levels, where choosing a
   narrower level than the failure warrants is itself a violation (Art. VII).
5. **Human-only powers**, non-delegable to any actor including Lisa (Art. VIII).
6. **Evidence as the completion boundary** on the governed dispatcher path, with
   "no evidence = ungoverned" (Art. VI.1, `04` §1).
7. **Enforcement honesty** as a standing constitutional obligation (Art. X).
8. **The amendment path** as the sole route to constitutional change
   (Art. IX.6).

The decision also **adopts the disclosed residual risks as accepted**, rather
than treating ratification as a claim that they are closed:

- **R5-1** — a `functools.wraps` wrapper that replaces rather than delegates
  inherits a marked executor's valid provenance declaration.
- **R5-2** — `mark_executor` can deliberately re-mark the shared
  `simulated_executor` function object, process-wide for callers holding it.
- **T10** — ratification integrity is norm-only and remains **High**; no
  artifact inside the system can prove a ratification record was written by the
  human (Art. IX.9).
- **T16** — `bin/lisa` and `bin/lisa-core` remain ungoverned and structurally
  invisible to the governance guard.
- **T17** — guard clearance matches by name against the whole ledger, and is a
  standing whitelist rather than proof that a given invocation was governed.
- The `require_clean()` sprint-entry gate has **no production call site**;
  invocation is caller-dependent.

## Consequences

### Positive

- Authority questions have a determinate answer, and unresolved ones fail closed
  rather than resolving in the acting party's favour.
- Governance documents can no longer claim enforcement the substrate lacks
  without contradicting Article X, and `06_SUBSTRATE_BINDING.md` makes the gap
  list explicit and auditable.
- Constitutional change now requires an evidenced, reviewed, human-ratified
  path. Editing a document confers nothing.
- The evidence chain from r2 to r8 is inspectable, with unavailable artifacts
  recorded as unavailable rather than reconstructed.

### Costs and constraints accepted

- **Ratification cannot be mechanically protected.** Any validator would be P1
  code editable by the actors it constrains (threat T3). Periodic human audit of
  the ledger is the only real control.
- **Most controls are norm-only.** Precedence, suspension classes, prohibitions,
  artifact-class access, approval validity, and reviewer independence have no
  mechanism. Ratification confers normative force; it converts nothing into a
  mechanical control.
- **Enforcement is scoped to the governed path.** Every "Enforced" row in
  `06_SUBSTRATE_BINDING.md` applies to work entering through
  `core/dispatcher.py`. Two executable entrypoints bypass it entirely.
- **Reviewer independence is procedural.** No mechanism checks any of the six
  conditions in `04` §3.
- **Family independence was imperfect.** The r6–r8 reviewer is Claude Opus 5;
  inherited r2/r3 text is Claude-family-authored. Disclosed under `04` §3.6
  rather than glossed.

### Operational impact

- The Article IX.7 genesis exception is **spent and non-precedential**. Every
  future P0 amendment must originate in `PROPOSALS/`.
- The subordinate instruments survive; none is repealed. Only their
  uncoordinated precedence is superseded.
- The known conflict between `SOUL.md` (Lisa exists *solely* to accelerate WBS
  development) and `IDENTITY.md` (several broader projects) is recorded as a
  defect to be repaired in those files, not resolved by any actor's judgement
  (Art. I.1A).

## Governance impact

| Area | Before | After ratification |
|---|---|---|
| Authority source | Implicit | Explicit, single, non-delegable |
| Default posture | Undefined | Deny |
| Instrument conflict | Unresolved | Ranked; fail-closed when not orderable |
| Constitutional change | Editing a file | `PROPOSALS/` → independent review → ledger record |
| Enforcement claims | Unmarked | Three declared states, verified per clause |
| Ratification | No instrument | `reports/lisa/ratification_records.jsonl`, ten mandatory fields |
| Residual risk | Undisclosed or denied | Enumerated, classified, adversarially reproduced |

**This ADR is the root ADR.** Every future architectural decision in Lisa OS is
subordinate to the ratified Constitution. An ADR may narrow a constitutional
provision; none may enlarge one (Art. II.5). An ADR that would require a
constitutional change is not an ADR — it is a constitutional amendment proposal
and must take the Article IX.6 path.

## Future amendment process

1. **Draft** in `docs/LISAOS/CONSTITUTION/PROPOSALS/`, where it carries no
   force. Drafting is not ratification (Art. IX.2).
2. **Freeze** the proposal under an annotated tag so review targets an immutable
   tree.
3. **Independent review** satisfying all six conditions of `04` §3 — separate
   assignment, no authorship participation, evidence-baseline access, authority
   to reject, no instruction to defend, independence disclosure. A review failing
   any condition satisfies no review requirement. Family independence is
   mandatory for P1 and security-class work where technically available.
4. **Preserve the review** in `docs/LISAOS/CONSTITUTION/REVIEWS/` with
   provenance and hash, so the basis is inspectable rather than summarized.
5. **Human ratification** by appending a schema-conformant record to
   `reports/lisa/ratification_records.jsonl`. The ratifier writes it; no actor
   may create, assert, simulate, or infer it (Art. IX.5).
6. **Record** the outcome in `HISTORY.md` and the revision evidence index.

A ratified amendment *is* constitutional text from the moment of ratification —
it is not an instrument operating beneath the Constitution (Art. II.5).

## References

- Ratification instrument — `docs/LISAOS/CONSTITUTION/RATIFICATION/V2_HUMAN_RATIFICATION_RECORD.md`
- Constitutional history — `docs/LISAOS/CONSTITUTION/HISTORY.md`
- Revision evidence index — `docs/LISAOS/CONSTITUTION/REVIEWS/V2_REVISION_EVIDENCE_INDEX.md`
- Preserved independent reviews — `docs/LISAOS/CONSTITUTION/REVIEWS/`
- Ratified set — `docs/LISAOS/CONSTITUTION/00_LISA_CONSTITUTION_V2.md` through `06_SUBSTRATE_BINDING.md`
