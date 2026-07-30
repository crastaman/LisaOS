# Lisa OS Constitution v2 r4 — Independent Review Packet

## 1. Purpose and classification

This is a **supporting review-evidence packet** for an independent
pre-ratification review of the Lisa OS Constitution v2 r4 proposal.

Classification and limits:

- It is **not** part of the constitutional P0 document set.
- It **does not amend** the frozen r4 proposal.
- It **does not ratify** the proposal, and cannot.
- The constitutional review target remains commit
  `e695cfa99c512c1a724ecc1acda7eb7064de41d6`.
- This packet exists to give a reviewer the assignment, evidence baseline,
  accepted prior state, provenance disclosures, and review authority needed to
  evaluate the six validity conditions in
  `docs/LISAOS/CONSTITUTION/04_AUDIT_AND_EVIDENCE.md` §3.

This packet was authored after the frozen proposal. Nothing in it may be read
as constitutional text, and nothing in it changes the meaning of the proposal.

---

## 2. Independent review assignment

Review the immutable Lisa OS Constitution v2 r4 proposal for:

- constitutional coherence;
- authority and amendment consistency;
- evidence and audit sufficiency;
- permission and protected-artifact consistency;
- threat-model completeness;
- substrate-binding truthfulness;
- enforcement claims versus verified implementation;
- internal contradictions, ambiguity, circularity, and unverifiable claims;
- readiness for human ratification.

**The reviewer has explicit authority to:**

- approve for human ratification;
- reject;
- return blocking findings;
- classify the result as advisory if independence conditions are not met.

**The reviewer is not instructed to defend, justify, preserve, or rubber-stamp
the proposal.** Rejection is a normal, recordable outcome, not an escalation.

The review must be performed as a **separate assignment**, not as a
continuation or sub-step of the authoring work.

---

## 3. Immutable artifact under review

| Field | Value |
|---|---|
| Commit | `e695cfa99c512c1a724ecc1acda7eb7064de41d6` |
| Tag | `CONSTITUTION-V2-R4-PROPOSED` (annotated) |
| Commit subject | `docs(constitution): freeze v2 r4 proposed baseline` |

The reviewer must inspect **only the repository tree at that commit** when
judging the constitutional text.

- Current working-tree changes are **out of scope** as proposal text.
- Later commits are **out of scope** unless explicitly cited as supporting
  review evidence.
- Supporting evidence added after the frozen proposal — including this packet —
  **must not be mistaken for part of the proposal text**.

### Tag dereferencing note

`CONSTITUTION-V2-R4-PROPOSED` is an **annotated** tag, so a bare
`git rev-parse CONSTITUTION-V2-R4-PROPOSED` returns the *tag object* SHA
(`0b16828e43d657355f75bddec0dc42a9b89b794f`), not the commit. This is normal
Git behaviour and is **not** a mismatch. Dereference explicitly:

```
git rev-parse "CONSTITUTION-V2-R4-PROPOSED^{commit}"
git rev-list -n1 CONSTITUTION-V2-R4-PROPOSED
```

Both return `e695cfa99c512c1a724ecc1acda7eb7064de41d6`.

### Constitutional P0 set (the text under review)

- `docs/LISAOS/CONSTITUTION/00_LISA_CONSTITUTION_V2.md`
- `docs/LISAOS/CONSTITUTION/01_AUTHORITY_MODEL.md`
- `docs/LISAOS/CONSTITUTION/02_PERMISSION_CONTRACTS.md`
- `docs/LISAOS/CONSTITUTION/03_PROTECTED_ARTIFACTS.md`
- `docs/LISAOS/CONSTITUTION/04_AUDIT_AND_EVIDENCE.md`
- `docs/LISAOS/CONSTITUTION/05_THREAT_MODEL.md`
- `docs/LISAOS/CONSTITUTION/06_SUBSTRATE_BINDING.md`

### Excluded from the ratified P0 text

- `docs/LISAOS/CONSTITUTION/PROPOSALS/README.md` — class P4 procedural index
- `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md` — class P4 historical evidence
- **this review packet**

---

## 4. Accepted prior state

| Field | Value |
|---|---|
| Commit | `f06e26d0a9ffb404db2c1b042aaa8cd453bb5a11` |
| Description | Lisa OS Constitution v2 **r3** proposed baseline for independent review |

This is the **direct parent** of the r4 proposal commit and is the accepted
prior proposal state against which r4 changes should be assessed.

Verification:

```
git rev-parse e695cfa99c512c1a724ecc1acda7eb7064de41d6^
```

Expected output:

```
f06e26d0a9ffb404db2c1b042aaa8cd453bb5a11
```

Useful diff for scoping the r3 → r4 delta:

```
git diff f06e26d0 e695cfa9 -- docs/LISAOS/CONSTITUTION/
```

---

## 5. Authoring and remediation provenance

Recorded honestly, from repository history and project-conversation evidence:

- **r4 was authored and remediated through Claude/Anthropic sessions** under
  direct human authorization from Roshan Crasta.
- **Claude participated materially in drafting and remediation and is therefore
  disqualified from serving as the independent reviewer of r4** (condition 2).
- Earlier **Codex/OpenAI** reviews were **advisory** because they failed the
  six-condition validity test — specifically condition 3, evidence-baseline
  access: the cited Phase 0 report did not exist in the repository at the time.
- Earlier **Claude Fable 5** review was advisory on condition 6 (model family).
- **No contemporaneous canonical authoring-grant record was committed when the
  drafting work occurred.** No `WorkAssignment` was materialized, and no
  workforce evidence record exists for the authoring or remediation sessions.
- **No formal acceptance record exists** for the historical Phase 0
  reconnaissance report. The "accepted 2026-07-30" phrasing used in earlier
  revisions was unsupportable and was corrected in r4.
- The historical Phase 0 reconnaissance report was **later preserved verbatim**
  in `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md`. It originated as a
  project-conversation artifact and was not committed when the Constitution set
  was originally drafted.

**Any description of authoring instructions or remediation history in this
packet is a retrospective provenance record derived from repository history and
project-conversation evidence — not a contemporaneous ledger entry.** No absent
record is claimed to have existed.

---

## 6. Evidence baseline available to the reviewer

**Evidence must be evaluated at the relevant commit or historical state.**
Current uncommitted implementation changes are **not** proof of what existed in
the frozen r4 proposal baseline. Where the constitutional text says a claim was
"verified 2026-07-30," the reviewer should **independently inspect the cited
code and history** rather than treating the statement as self-proving. Missing,
untracked, or inaccessible evidence must be **reported as a finding**, never
inferred.

Availability was checked before listing. Status is given per path.

### Tracked at the r4 baseline (`e695cfa9`) — inspectable by the reviewer

| Path | Status | What it supports |
|---|---|---|
| `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md` | tracked @ r4 | The cited evidence baseline. Repository map, three-generation architecture, governance summary, delegation model, known weaknesses. Supports `01`, `02`, `05`, `06` |
| `core/dispatcher.py` | tracked @ r4 · **modified in working tree** | Coordination/execution separation; per-package fail-closed; executor contract. Basis for `06` orchestrator and evidence rows |
| `core/governance_guard.py` | tracked @ r4 | Bypass detection, name-prefix heuristic, ledger-wide name clearing, `require_clean()`. Basis for `04` §2.2/§2.2A, `05` T1/T17 |
| `core/openclaw_bridge.py` | tracked @ r4 · **modified in working tree** | `agent_for_logical()` selection, fail-closed identity, post-execution drift detection, simulation labelling. Basis for `06` identity rows, `05` T14 |
| `core/policy_engine.py` | tracked @ r4 | Alternative staffing path; absence of approval metadata. Basis for `01` §4.3, `05` T9, `06` PolicyEngine row |
| `core/workforce_resolver.py` | tracked @ r4 · **modified in working tree** | `WorkAssignment` schema, `candidates_for()`, fallback metadata, evidence writer. Basis for `04` §1.1, `02` §3B, `06` fallback rows |
| `registry/agents.yml` | tracked @ r4 · **modified in working tree** | Legacy/transitional registry; `status: active` header vs `02` §4 transitional classification |
| `registry/employees.yml` | tracked @ r4 | Capability allocation, seniority ranks, `irreversible-judgement` holders, empty fallback chains. Basis for the registry-contingency claim in `02` §3B / `06` |
| `registry/provider_resolution.yml` | tracked @ r4 | Logical→physical provider mapping, agent bindings, probation flags |
| `lisaos/policies/governance.yml` | tracked @ r4 | Approval classes incl. `requires_gpt_or_roshan_approval`. Basis for `01` §4.3 approver clause and `05` T9 |
| `tests/test_dispatcher.py` | tracked @ r4 · **modified in working tree** | Dispatcher behaviour incl. executor contract |
| `tests/test_governance_guard.py` | tracked @ r4 | Guard scan/acknowledge/`require_clean` behaviour; validates name-only matching (T17) |
| `tests/test_anti_regression.py` | tracked @ r4 | Anti-regression gates; fail-closed evidence-source prefix family |
| Git history (`f06e26d0`, `e695cfa9`, and ancestors) | available | r3→r4 delta, freeze provenance, absence of authoring-grant records |

### NOT available at the r4 baseline — must be treated as evidence gaps

| Path | Actual status | Consequence |
|---|---|---|
| `tests/test_r4_remediation.py` | **untracked; absent at `e695cfa9`** | The tests that pin the r4 B2/B3/leak-3 behaviour are **not in the baseline**. A reviewer at the target commit cannot use them as evidence |
| `reports/lisa/provider_resolution_evidence.jsonl` | **untracked**; present in working tree only | Not admissible as baseline evidence. Listed here only because it was proposed as optional |

### MATERIAL DISCLOSURE — enforcement claims not supported by code at the baseline

Verified directly against the target commit, and reported here because §6
requires evidence gaps to be surfaced rather than inferred:

**Several "Enforced" claims added in r4 describe code that does not exist in the
r4 baseline tree.** The implementing changes were made in the working tree and
were **not** included in the freeze commit.

| r4 constitutional claim | Location | Code at `e695cfa9` |
|---|---|---|
| Evidence records the **outcome** — **Enforced** (`execution_success` / `execution_error`) | `04` §1.1, `06` §3 | `execution_success` appears **0 times** in `core/workforce_resolver.py` |
| Undeclared executors are **refused**; provenance declared and recorded | `04` §1.7, `06` §2–§3, `05` T15 | `mark_executor` / `EXECUTOR_PROVENANCE_ATTR` appear **0 times** in `core/dispatcher.py` |
| Staffing requires a named capability — **Enforced** | `06` §3 | `if not required_capabilities` appears **0 times** in `core/workforce_resolver.py` |

All three exist only in uncommitted working-tree modifications to
`core/dispatcher.py`, `core/workforce_resolver.py`, `core/openclaw_bridge.py`,
and `core/capacity_ledger.py`.

**The reviewer should treat this as a finding to evaluate, not as settled.** It
bears directly on §7 condition 3 and on the substrate-binding truthfulness
question in §2 of this assignment. The reviewer is free to conclude that the
frozen text overstates enforcement relative to its own tree, and to weight that
however the six-condition test and their own judgement require. Nothing in this
packet should be read as arguing for a particular disposition.

Reproduce with:

```
git show e695cfa9:core/workforce_resolver.py | grep -c execution_success
git show e695cfa9:core/dispatcher.py         | grep -c mark_executor
```

---

## 7. Six-condition validity declaration

The reviewer must complete this table **before** substantive review
(`04_AUDIT_AND_EVIDENCE.md` §3).

| Condition | Requirement | Reviewer declaration | Evidence / reason |
|---|---|---|---|
| 1 | Separate assignment | PASS / FAIL | |
| 2 | No authorship participation | PASS / FAIL | |
| 3 | Evidence baseline access | PASS / FAIL | |
| 4 | Authority to disagree or reject | PASS / FAIL | |
| 5 | No instruction to defend | PASS / FAIL | |
| 6 | Independence disclosure | PASS / FAIL | |

Rules:

- **If any condition fails, the reviewer must stop** the validity assessment
  and classify the result as:

  ```
  ADVISORY — INDEPENDENCE TEST FAILED
  ```

- A failed validity test **does not satisfy the constitutional
  independent-review gate**, regardless of the quality of the substantive
  review that follows.
- The reviewer **must disclose provider, model, and model-family identity**
  where known.
- **Different model-family independence is mandatory where technically
  available** for P1 and security-class work, per `04_AUDIT_AND_EVIDENCE.md`
  §4. Any Claude/Anthropic-family reviewer fails condition 2 for this proposal
  on authorship grounds (§5 above).

---

## 8. Required review method

1. Verify the immutable target and parent commit.
2. Verify the tag resolves to the target commit (see the dereferencing note in
   §3).
3. Inspect **all seven** P0 constitutional files at the target commit.
4. Inspect the preserved reconnaissance report and the cited implementation
   evidence.
5. Compare r4 against r3 (`git diff f06e26d0 e695cfa9 -- docs/LISAOS/CONSTITUTION/`).
6. Test cross-document references and precedence rules — including Article II.5
   rank ordering, temporal supersession, and the amendment-chain gate.
7. Separate findings into:
   - constitutional defects;
   - enforcement gaps **already disclosed** by the text;
   - **inaccurate** enforcement claims;
   - missing evidence;
   - non-blocking observations;
   - future implementation work.
8. **Do not treat a disclosed norm-only or partial control as a defect** merely
   because it is not fully enforced — unless:
   - the classification is inaccurate;
   - the Constitution **depends** on enforcement it does not possess;
   - the residual risk is internally contradictory or unacceptable under its
     own rules.
9. Report exact file, section, and supporting evidence for **every** finding.
10. **Make no edits during the review.**

---

## 9. Required review output

### A. Independence validity result

```
PASS — SIX-CONDITION VALID
```
or
```
ADVISORY — INDEPENDENCE TEST FAILED
```

Include the completed six-condition table and reviewer identity/model
disclosure.

### B. Executive verdict

Exactly one of:

- `APPROVE FOR HUMAN RATIFICATION`
- `RETURN WITH BLOCKING FINDINGS`
- `ADVISORY ONLY — NO CONSTITUTIONAL GATE SATISFIED`

### C. Blocking findings

Each with: ID · severity · constitutional location · evidence · reasoning ·
required remediation.

### D. Major non-blocking findings

### E. Minor findings and editorial observations

### F. Evidence-access gaps

### G. Cross-document consistency results

### H. Enforcement-truthfulness results

### I. Ratification readiness statement

The reviewer must state **explicitly** whether the exact immutable P0 set at
`e695cfa99c512c1a724ecc1acda7eb7064de41d6` is ready for human ratification.

---

## 10. Ratification boundary

- **This review cannot ratify the Constitution.**
- **Only Roshan Crasta**, as the human authority source, may ratify it.
- Ratification requires a valid record conforming to
  `04_AUDIT_AND_EVIDENCE.md` §1.5 — canonical ledger
  `reports/lisa/ratification_records.jsonl`, ten required fields, with
  `text_reference` naming the exact ratified commit.
- **No ratification record should be created** until a six-condition-valid
  independent review has completed without blocking findings **and** Roshan has
  made an explicit human decision.

---

## 11. Known limitation of this packet

This packet improves access to the assignment, evidence baseline, accepted
prior state, and provenance disclosures.

**It does not retroactively create a contemporaneous authoring grant or evidence
ledger entry that never existed.** No `WorkAssignment` was materialized for the
authoring or remediation work, and no workforce evidence record exists for it.
That absence is a historical fact, disclosed here rather than repaired.

**The independent reviewer must decide** whether this honest retrospective
packet is sufficient to satisfy Condition 3 under the text of
`04_AUDIT_AND_EVIDENCE.md` §3.3 ("Evidence baseline access. The reviewer can see
the assignment, its evidence records, and the accepted prior state").

Condition 3 names three things. This packet supplies the **assignment** (§2) and
the **accepted prior state** (§4). It does **not** supply contemporaneous
**evidence records** for the authoring work, because none exist.

**The reviewer must not assume sufficiency merely because the packet exists.**
