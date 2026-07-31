# Lisa OS Constitution v2 r5 — Independent Review

## 1. Executive Verdict

**Final verdict: C. REMEDIATION REQUIRED BEFORE RATIFICATION**

The immutable baseline is authentic, internally identifiable, and its full test suite passes. Most norm-only and residual-risk limitations are described candidly.

Ratification is nevertheless blocked by material truthfulness and enforcement-integrity defects:

1. The dispatcher accepts malformed provenance values—including `""` and `"bogus-provenance"`—although the Constitution says only three declared values are allowed.
2. Executor results are not validated. A truthy string such as `success="false"` completes the package and is serialized as a string rather than a Boolean outcome.
3. The claim that every governed execution has evidence is false for malformed executor returns and JSON serialization failures. I reproduced executed work with no evidence record.
4. R5-2—the process-wide re-marking of the shared `simulated_executor` singleton—is technically possible but is not expressly disclosed in any of the eight proposal files.
5. The statement in `05_THREAT_MODEL.md:59-62` that the substrate genuinely prevents “silent attribution laundering” contradicts the admitted `functools.wraps` route.
6. The six-condition independent-review gate fails condition 3 because contemporaneous authoring/remediation evidence records are unavailable.

This review is therefore substantive and independent in authorship/model terms, but advisory under the Constitution’s own six-condition test.

Line references below identify files in commit `247d3eb76d6f2ac08e5307134b80e5458b4b00d3`, not the live working tree.

## 2. Frozen Baseline Verification

| Check | Result |
|---|---|
| Tag type | `tag` — annotated |
| Tag object | `e7564cd5d6028d3f7b59069ae22a804f5d9069bc` — exact match |
| Dereferenced commit | `247d3eb76d6f2ac08e5307134b80e5458b4b00d3` — exact match |
| Target tree | `5628de4fff0ff4dcf74633a9bd0bc3d73f8dea29` |
| Parent | One parent: `25ec6beec2e26b883724a9b68b67bea88d892daf` |
| Merge status | Not a merge |
| r4 tag type | Annotated tag |
| r4 dereferenced commit | `e695cfa99c512c1a724ecc1acda7eb7064de41d6` — exact match |
| r4 ancestry | r4 is an ancestor of r5 |
| r4 preservation | r4 tag still resolves to its original immutable commit |
| Temporary review tree | Exported with `git archive` to `/private/tmp/lisa-r5-review.kdeOfw`; removed after review |
| Repository changes made | None |

The r5 commit changes exactly:

- Four implementation files: `core/capacity_ledger.py`, `core/dispatcher.py`, `core/openclaw_bridge.py`, `core/workforce_resolver.py`.
- Eight proposal documents.
- `tests/test_dispatcher.py`.
- New `tests/test_r4_remediation.py`.

That matches the stated r5 remediation scope.

The live working tree contained two modified and nine untracked files. None was used as constitutional or implementation evidence. A final `git status --short` showed the same pre-existing set, confirming that this review made no repository changes.

## 3. Review Independence

Git metadata identifies Lisa as author and Claude Opus 5 as co-author. This review was performed by Codex/OpenAI GPT-5 family. I did not author the proposal, implementation, remediation, or tests.

I independently inspected Git objects, the exported tagged tree, implementation control flow, tests, and adversarial behavior. I did not use prior Claude summaries as proof. The r4 review packet was consulted only to evaluate whether the six-condition evidence-access requirement could be met; its implementation conclusions were not adopted as evidence.

The review was not instructed to defend or preserve the proposal, and rejection was explicitly permitted.

The constitutional gate nevertheless fails on missing authoring/remediation evidence records; see section 10.

## 4. Constitutional Metadata Verification

All eight files contain:

- Version `2.0.0-proposed-r5`.
- Status `PROPOSED — PENDING HUMAN RATIFICATION`.
- `Ratified by: (pending)`.
- `Ratification date: (pending)`.

Each says r5 has not been independently reviewed. None asserts completed ratification or approval.

The revision basis is substantially accurate:

- r4 lacks `execution_success`, `execution_provenance`, and `tests/test_r4_remediation.py`.
- r5 contains the implementation and tests in its own tree.
- The Phase 0 report first appears at r4 and is unchanged between r4 and r5.
- r4 remains a historical immutable tag rather than being rewritten.

One non-constitutional metadata error exists: the r5 commit message says “460 pass, 39 skipped.” The actual result is **460 total, 421 passed, 39 skipped**. This does not change the successful suite outcome, but the commit-message count is inaccurate.

## 5. Claim Inventory

Classification legend: A = code-enforced; B = process/review; C = declared but not technically enforced; D = accepted residual risk; E = historical; F = unsupported/overstated.

Exact repetitions across documents are consolidated, but every distinct normative enforcement proposition is represented.

| ID | Constitutional claim | Location | Classification | Code evidence | Test evidence | Verdict |
|---|---|---|---|---|---|---|
| M01 | Execution outcome is carried on `WorkAssignment` | `04:24-38`; `06:54` | A | `workforce_resolver.py:188-204`; `dispatcher.py:454-459` | `test_r4_remediation.py:163-201` | TRUE |
| M02 | `execution_success` and `execution_error` are serialized | `04:29-35`; `06:54` | A | `WorkAssignment.to_dict`; `record_assignment_evidence` at `workforce_resolver.py:462-468` | `test_r4_remediation.py:173-190` | TRUE for valid values |
| M03 | Executor provenance is carried in evidence | `04:36-38,150-185`; `06:55` | A | `WorkAssignment.execution_provenance`; `dispatcher.py:460-464` | `test_r4_remediation.py:98-104` | TRUE for accepted callables |
| M04 | Undeclared executor refused at construction | Metadata revision basis; `04:156-174`; `05:T15` | A | `Dispatcher.__init__`, `dispatcher.py:238-265` | `test_r4_remediation.py:53-67` | TRUE narrowly |
| M05 | Provenance is revalidated every `run()` | Metadata revision basis; `05:T15` | A | `dispatcher.py:292-314` | `test_r4_remediation.py:106-136` | PARTIAL: presence is re-read, validity is not checked |
| M06 | Worker/main attribution is derived from provenance | `01:128-146`; `04:150-174`; `06:47,55` | A | `dispatcher.py:313-315,469-487` | `test_r4_remediation.py:74-96` | TRUE for valid values |
| M07 | `simulated_executor` applies its own label | `04:117-148`; `05:T14`; `06:56` | A | `dispatcher.py:152-174` | `test_r4_remediation.py:208-222`; `test_openclaw_bridge.py:625-630` | TRUE |
| M08 | Empty required capabilities fail closed | `06:57`; repeated revision basis | A | `candidates_for`, `workforce_resolver.py:321-342` | `test_r4_remediation.py:239-255` | TRUE |
| M09 | Staffing fails closed for unknown capability/no worker/no model | `01:57-77`; `02:96-103`; `06:48` | A | `workforce_resolver.py:370-455`; `policy_engine.py:73-114,200-217` | `test_workforce_resolver.py:271-306`; `test_dispatcher.py:140-171` | TRUE |
| M10 | Identity selection is deterministic and fail-closed | `06:39,51-52`; `05:T14/T16 context` | A | `agent_for_logical`; `build_real_executor`, `openclaw_bridge.py:381-416` | `test_openclaw_bridge.py:165-217,262-293`; `test_anti_regression.py:167-197` | TRUE for registry selection |
| M11 | Evidence is recorded on every governed execution | `00:205-206`; `04:24-26`; `06:53` | F | Evidence is written only after a valid return is reconciled: `dispatcher.py:424-464` | Existing tests cover valid returns and raised exceptions, not malformed returns/serialization | FALSE |
| M12 | One package’s staffing/executor exception does not halt safe siblings | `00:228-231`; `06:35,59` | A | `dispatcher.py:337-356,424-487` | `test_dispatcher.py:141-155,328-361` | TRUE for staffing errors and raised executor exceptions |
| M13 | Evidence survives JSONL serialization and reload | `04:29-38`; `06:54-55` | A | Dataclass → `asdict` → `json.dumps` | Raw persistence asserted at `test_r4_remediation.py:173-190`; JSON parsing at `test_dispatcher.py:236-258`; manual reload confirmed | TRUE for JSON-valid values; coverage partial |
| M14 | Constitutional evidence references resolve at or before r5 as claimed | Metadata `Related evidence baseline`; `06:18` | E | Git object/path audit | No automated reference audit | TRUE with disclosed absent runtime ledgers |
| N01 | Proposal has no force until human ratification | All eight headers; `00:289-337` | B | No ratification validator exists | None | NOT TECHNICALLY ENFORCED, accurately labeled |
| N02 | Roshan is sole authority source | `00:64-81`; `01:22-41` | C | No authority-source evaluator | None | NOT TECHNICALLY ENFORCED |
| N03 | Instrument precedence and non-orderable conflicts fail closed | `00:82-136`; `06:67` | C | No precedence engine | None | NOT TECHNICALLY ENFORCED |
| N04 | Authority defaults to deny and cannot be inferred | `00:160-178`; `01:213-232` | C | Staffing has limited fail-closed filters; no general permission engine | Staffing tests only | NOT TECHNICALLY ENFORCED generally |
| N05 | Lisa has only bounded orchestration authority | `01:79-146`; `06:68` | C | Dispatcher separation only; goal/spend/artifact scope unchecked | Provenance/dispatcher tests | PARTIAL |
| N06 | Dispatcher itself has no package-execution branch | `01:133-135`; `06:35,47` | A | All execution goes through `pool.submit(executor, ...)` | Dispatcher suites | TRUE |
| N07 | A valid executor must use one of three provenance values | `04:156-163`; `05:T15` | F | `_VALID_PROVENANCE` is checked only by `mark_executor`; dispatcher checks only `is None` | Only helper rejection tested | FALSE |
| N08 | Wrappers inherit provenance and cannot invent it | `04:163`; `05:T15` | F | `ledger_recording_executor` inherits correctly, but arbitrary wrappers can be marked or mutate the attribute | `test_r4_remediation.py:140-153` covers only ledger wrapper | FALSE as a general claim |
| N09 | Simulation cannot be selected by executor omission | `04:143-144`; `05:T14`; `06:35,56` | A | `Dispatcher.__init__` raises on `None` | `test_dispatcher.py:364-397` | TRUE |
| N10 | Evidence mode vocabulary distinguishes every listed mode | `00:209-213`; `04:106-148` | C | Only simulation, real-response, and fail-closed literals have encodings | Simulation/bridge tests | PARTIAL, accurately labeled |
| N11 | Outcome evidence is semantically truthful | `04:24-35`; Article X | F | `ExecutionResult.success` has no runtime type validation | No malformed-success test | FALSE |
| N12 | Grant and artifact-class references are in every evidence record | `04:24-42` | C | Fields do not exist | None | NOT TECHNICALLY ENFORCED, accurately disclosed |
| N13 | P2 ledgers are append-only | `03:24-30,82-110`; `04:50-51`; `06:72` | B | Components use append mode; filesystem edits remain possible | Guard append test `test_governance_guard.py:167-175` | PARTIAL |
| N14 | Erroneous evidence is corrected only by superseding record | `03:82-110` | B | No general correction validator | Acknowledgement path is only analogue | NOT TECHNICALLY ENFORCED generally |
| N15 | Human acts require named human operator and reason | `00:207-208`; `04:46-49,217-226` | B | Guard requires non-empty operator but cannot verify humanness | `test_governance_guard.py:149-165` | PARTIAL |
| N16 | Ratification ledger/schema is authoritative | `00:294-337`; `04:53-104`; `06:66` | B | No reader, validator, or committed ledger | None | NOT TECHNICALLY ENFORCED, accurately labeled |
| N17 | Governance guard fails closed once invoked | `04:189-201`; `06:38,58` | A | `governance_guard.require_clean` | `test_governance_guard.py:121-161` | TRUE after invocation |
| N18 | Sprint entry always invokes the guard | `04:191-201`; `06:58` | C | No production caller; separate anti-regression injection only | Guard unit tests | NOT TECHNICALLY ENFORCED |
| N19 | Guard evidence is bound to the specific invocation | `04:202-216`; `05:T17` | D | Name-only, ledger-wide match | `test_governance_guard.py:90-114` | FALSE as proof; accurately disclosed |
| N20 | Capability-superset matching and seniority ordering | `02:98,193-209`; `06:36` | A | `candidates_for`, `workforce_resolver.py:321-342` | `test_workforce_resolver.py:233-264` | TRUE |
| N21 | Superset capabilities confer no extra authority | `02:193-209`; `06:75` | C | Runtime does not constrain post-assignment actions | None | NOT TECHNICALLY ENFORCED |
| N22 | Probation capacity is restricted to low-risk work | `02:172-190`; `06:48` | A | Resolver/policy filters | `test_workforce_resolver.py:348-375`; policy tests | TRUE for `risk`; artifact/security extension not enforced |
| N23 | Unavailable/disabled capacity is excluded | `06:48`; staffing description | A | `CapacityLedger.is_usable`; `PolicyEngine.resolve` | `test_policy_engine.py:117-192`; `test_anti_regression.py:503-558` | TRUE |
| N24 | Fallback is explicit and recorded | `02:211-263`; `06:49-50` | A | Model-chain fallback fields populated; employee substitution not marked | Workforce fallback tests | PARTIAL, accurately disclosed |
| N25 | Judgement-critical work cannot silently downgrade | `02:211-263`; `06:50` | D | Holds only under current registry allocation | Registry and workforce tests | PARTIAL, accurately disclosed |
| N26 | Workers cannot self-staff | `02:167-170` | A | Resolver/policy select worker; no dispatcher self-staff branch | Staffing and dispatcher tests | TRUE within governed path |
| N27 | Artifact-class access and P0/P1 write protection | `00:180-201`; `02:41-89`; `03:22-45,112-124` | C | No artifact-class field or filesystem guard | None | NOT TECHNICALLY ENFORCED |
| N28 | Absolute prohibitions are runtime-enforced | `02:104-139`; `06:70` | C | No canonical prohibition field/evaluator | None | NOT TECHNICALLY ENFORCED |
| N29 | Separation of author/reviewer/planner/security roles | `01:43-55`; `02:141-171` | C | Registry hints load but are unused for SoD | No enforcement tests | NOT TECHNICALLY ENFORCED |
| N30 | Approval presence, expiry, and satisfaction are enforced | `01:148-203`; `04:222-226,270-283`; `06:64-65` | C | Resolver sometimes flags; PolicyEngine does not; nothing validates approval | Workforce approval-flag tests only | NOT TECHNICALLY ENFORCED |
| N31 | Grants are expiring, revocable, non-transitive, non-retroactive | `01:211-232` | C | No grant lifecycle mechanism | None | NOT TECHNICALLY ENFORCED |
| N32 | Consultation never transfers authority; escalation follows the upward chain | `01:234-279`; `06:73` | C | Fields load but no routing/enforcement | None | NOT TECHNICALLY ENFORCED |
| N33 | High-risk and production-release authority is human-only | `00:264-287`; `01:281-289`; `06:76` | C | No approval/release validator | None | NOT TECHNICALLY ENFORCED |
| N34 | Proposal area and genesis rules control future constitutional drafting | `00:316-323`; `03:47-78`; proposal README `22-56` | B | Process rule only | None | NOT TECHNICALLY ENFORCED |
| N35 | Independent review requires six conditions and model-family separation | `04:228-260` | B | No runtime validator | None | NOT TECHNICALLY ENFORCED |
| N36 | Systemic halt and safe-suspension classes operate mechanically | `00:217-262`; `06:60-61` | C | No suspension mechanism/class field | None | NOT TECHNICALLY ENFORCED |
| T01 | Direct bypass is partially detected | `05:39` | D | Guard heuristic; legacy paths invisible | Guard tests | PARTIAL, honestly disclosed |
| T02 | Scope creep remains uncontrolled | `05:40` | D | No scope representation | None | TRUE residual |
| T03 | Registry self-elevation remains possible | `05:41` | D | Files ordinarily writable | None | TRUE residual |
| T04 | Ledger tampering remains possible | `05:42` | D | No filesystem immutability | Append tests only | TRUE residual |
| T05 | Reviewer capture/family correlation remains possible | `05:43` | D | No review validator | None | TRUE residual |
| T06 | Private chained delegation is only heuristically detectable | `05:44` | D | Guard heuristic only | Guard tests | PARTIAL |
| T07 | Instruction smuggling remains unsolved | `05:45` | D | No technical control | None | TRUE residual |
| T08 | Stale authority is only partly controlled | `05:46` | D | Per-run assignments; approval expiry unchecked | None | PARTIAL |
| T09 | Approval fabrication remains possible | `05:47` | D | No validator; path-dependent flag | Staffing tests | TRUE residual |
| T10 | Ratification can be forged in-system | `05:48` | D | No authentication/validator | None | TRUE residual |
| T11 | Unbounded orchestration remains partly unchecked | `05:49` | D | Dispatcher separation only | Provenance tests | PARTIAL |
| T12 | Suspension self-clearing is norm-only | `05:50` | D | No mechanism | None | TRUE residual |
| T13 | Consultation can be mistaken for authority | `05:51` | D | No mechanism | None | TRUE residual |
| T14 | Simulation presentation risk is reduced but not eliminated | `05:52` | D | Explicit simulation label and no omission default | Simulation tests | PARTIAL, reasonable |
| T15 | Attribution falsification remains possible | `05:53`; `04:170-185` | D/F | Declaration mechanism plus reproduced bypasses | Positive provenance tests; negative gaps | PARTIAL disclosure; contradictory summary |
| T16 | Legacy entrypoints bypass all governance | `05:54`; `06:78-95` | D | `bin/lisa`; `bin/lisa-core` → legacy router | No end-to-end governance test | TRUE residual, honestly disclosed |
| T17 | Stale/colliding identifiers clear the guard | `05:55`; `04:202-216` | D | Ledger-wide name match | Guard tests | TRUE residual |

## 6. Adversarial and Bypass Findings

### ADV-01 — Invalid provenance values bypass enforcement

- Severity: High
- Claim affected: only `worker-real`, `worker-simulated`, or `main-inline` may be accepted.
- Proof: setting `__lisa_execution_provenance__` directly to `"bogus-provenance"` or `""` passed both construction and `run()`.
- Observed evidence: the invalid value was serialized. `"bogus-provenance"` was treated as main execution because it was not in `_WORKER_PROVENANCE`.
- Cause: `mark_executor` validates the vocabulary, but `Dispatcher` only rejects `None`.
- Disclosed: No.
- Blocking: Yes—enforcement and attribution integrity.

### ADV-02 — Non-Boolean success corrupts outcome truth

- Severity: High
- Claim affected: evidence records a truthful execution outcome.
- Proof: `ExecutionResult(success="false", ...)` marked the package complete because the string is truthy.
- Evidence record: `"execution_success": "false"`—a string, not Boolean `false`.
- Graph result: completed `1`, failed `0`.
- Disclosed: No.
- Blocking: Yes—evidence integrity.

### ADV-03 — Governed execution can occur without evidence

- Severity: High
- Claim affected: evidence on every governed execution.
- Reproduction 1: executor returned `None` for one package while a sibling ran normally. Both executor calls occurred; dispatcher raised `AttributeError`; no evidence file was produced.
- Reproduction 2: executor returned a nominal `ExecutionResult` containing non-JSON-serializable token metadata. Execution completed, but evidence serialization raised `TypeError`; the JSONL file existed with zero bytes.
- Cause: result reconciliation and serialization are outside a fail-closed conversion boundary.
- Disclosed: Systemic halt is documented as norm-only, but `06:53` still calls evidence-on-every-execution “Enforced.”
- Blocking: Yes—constitutional truthfulness and evidence integrity.

### ADV-04 — R5-1 remains open

- Severity: Medium, accepted only if accurately described.
- Proof: a `functools.wraps(marked_real)` replacement wrapper inherited `worker-real`, never invoked the wrapped function, and was counted as worker execution.
- Disclosed: Yes, at `04:176-185` and `05:T15`.
- Blocking: The risk itself need not block, but contradictory absolute wording does.

### ADV-05 — R5-2 remains open but is not expressly disclosed

- Severity: High for disclosure; Medium as an underlying accepted risk.
- Proof: `mark_executor(simulated_executor, MAIN_INLINE)` changed the shared function process-wide; subsequent dispatch recorded `main-inline`. The simulation label remained, but every caller sharing that function observed the re-mark.
- Disclosed: Only generically as deliberate mis-marking. No proposal file mentions the shared singleton, process-wide blast radius, re-marking, or R5-2. A repository-wide search found no such wording.
- Blocking: Yes—residual-risk honesty.

### ADV-06 — “Silent laundering prevented” contradicts R5-1

- Severity: High.
- Claim affected: honest summary at `05:59-62`.
- Proof: the summary says silent attribution laundering is genuinely prevented, while `05:T15` and `04:176-185` admit an accidental `functools.wraps` laundering route.
- Disclosed: The route is disclosed elsewhere, creating an internal contradiction.
- Blocking: Yes—constitutional coherence and truthfulness.

### ADV-07 — Identity duplicate-binding validation gap

- Severity: Low.
- Claim affected: live identity-map integrity.
- Proof: `validate_identity_map` checks existence, shared/general names, and model drift, but does not check whether two logical providers bind to the same dedicated agent.
- Current tree: all nine configured agent bindings are unique; codex and gpt bind to distinct agents.
- Disclosed: Covered by the document’s `Partial` classification for live identity integrity.
- Blocking: No.

### ADV-08 — Test-count metadata is inaccurate

- Severity: Low.
- Proof: commit message says “460 pass, 39 skipped”; runner says “Ran 460 … skipped=39,” meaning 421 passed and 39 skipped.
- Blocking: No; actual suite result is successful and independently reported below.

The adversarial harness was an inline, temporary command beginning exactly:

```text
LISA_HOME=/private/tmp/lisa-r5-review.kdeOfw python3 - <<'PY'
```

It exercised malformed and empty provenance, `functools.wraps` replacement, singleton re-marking, malformed return, non-Boolean success, and serialization failure. It wrote only under `/private/tmp`.

## 7. Residual-Risk Assessment

### R5-1 — `functools.wraps` inheritance

- Technically possible: Yes.
- Independently reproduced: Yes.
- Constitutional description: Accurate in `04:176-185` and `05:T15`.
- Accidental versus deliberate distinction: Clear locally.
- Contradiction: `05:59-62` later says silent laundering is genuinely prevented.
- Ratification classification: Reasonable as an accepted residual only after the contradiction is removed.

### R5-2 — shared simulated-executor re-marking

- Technically possible: Yes.
- Independently reproduced: Yes.
- Constitutional description: Incomplete. The documents disclose deliberate mis-marking generally but do not disclose shared-singleton mutation or process-wide consequences.
- Accidental versus deliberate distinction: General deliberate/accidental distinction exists, but the specific R5-2 route is absent.
- Ratification classification: Potentially reasonable as an accepted residual once expressly documented. It is not presently documented with sufficient specificity.

## 8. Test Results

Exact full-suite command:

```text
LISA_HOME=/private/tmp/lisa-r5-review.kdeOfw python3 -m unittest discover -s tests -p 'test_*.py'
```

Result:

| Metric | Count |
|---|---:|
| Total | 460 |
| Passed | 421 |
| Skipped | 39 |
| Failures | 0 |
| Errors | 0 |

Focused suites:

| Command suffix | Tests | Result |
|---|---:|---|
| `tests.test_r4_remediation` | 18 | PASS |
| `tests.test_dispatcher` | 20 | PASS |
| `tests.test_workforce_resolver` | 36 | PASS |
| `tests.test_policy_engine` | 13 | PASS |
| `tests.test_openclaw_bridge` | 27 | PASS |
| `tests.test_governance_guard` | 13 | PASS |
| `tests.test_anti_regression` | 75 | PASS |

Each used:

```text
LISA_HOME=/private/tmp/lisa-r5-review.kdeOfw python3 -m unittest <module>
```

Environment:

- macOS `26.5.1`, Darwin kernel `25.5.0`, ARM64.
- Python `3.14.6`, `/opt/homebrew/bin/python3`.
- PyYAML `6.0.3`.
- Export directory: `/private/tmp/lisa-r5-review.kdeOfw`.
- No detached worktree or live working-tree imports were used.

All 39 skips were console tests requiring Flask. They are unrelated to the reviewed dispatcher, staffing, provenance, evidence, bridge, guard, and anti-regression claims. Every requested focused suite ran without skips.

Real OpenClaw execution was not attempted; bridge tests are mocked/hermetic. Thus live agent availability and live model coherence were not independently proven—consistent with the Constitution’s `Partial` classification.

## 9. Evidence-Reference Audit

Confirmed inside the frozen tree:

- All cited constitutional documents.
- All cited implementation modules.
- All cited focused test files.
- `docs/LISAOS/V3/PHASE0_RECONNAISSANCE_REPORT.md`.
- Governance, security, identity, SOUL, policy, and registry files.
- Both named legacy entrypoints.
- `bin/lisa-identity-check`.
- r4 immutable commit and tag history.

The Phase 0 report was added at r4 and is byte-unchanged from r4 to r5, supporting the “carried forward unchanged” statement.

The runtime JSONL ledgers are absent from the Git tree:

- `reports/lisa/workforce_evidence.jsonl`
- `reports/lisa/governance_violations.jsonl`
- `reports/lisa/governance_acknowledgements.jsonl`
- `reports/lisa/ratification_records.jsonl`

That absence is not concealed: the documents describe runtime-created ledgers and explicitly say the ratification ledger/validator does not yet exist. These absent paths cannot serve as frozen authoring or review evidence.

## 10. Six-Condition Independent-Review Gate

| Condition | Result | Evidence |
|---|---|---|
| 1. Separate assignment | PASS | The user issued a standalone frozen-baseline review assignment, separate from proposal/remediation work. |
| 2. No authorship participation | PASS | Commit authored by Lisa and co-authored by Claude Opus 5; reviewer is Codex/OpenAI GPT-5 family and did not participate in authorship. |
| 3. Evidence baseline access | FAIL | Frozen code, tests, predecessor, and Phase 0 baseline were accessible, but no contemporaneous `WorkAssignment` or authoring/remediation evidence records exist in the target tree. The r4 review packet itself records this absence at lines 145-147 and 364-376; no r5 ledger cures it. |
| 4. Authority to disagree or reject | PASS | The assignment explicitly permits remediation-required or rejection verdicts. |
| 5. No instruction to defend | PASS | The prompt demands independent falsification and prohibits accepting prior mappings without verification. |
| 6. Independence disclosure | PASS | Reviewer: Codex/OpenAI GPT-5 family. Proposal/remediation authorship includes Claude/Anthropic family. Different-family independence is available and disclosed. |

Because condition 3 fails, this review satisfies no constitutional independent-review requirement under `04:245-248`. Its substantive findings remain usable as advisory evidence, but it cannot itself unlock ratification.

## 11. Ratification Readiness

**C. REMEDIATION REQUIRED BEFORE RATIFICATION**

Reasons:

- Frozen identity: PASS.
- Metadata and non-ratified status: PASS.
- Full and focused tests: PASS, with unrelated Flask skips.
- Material claim-to-code mappings: FAIL for valid provenance vocabulary, outcome integrity, and universal evidence.
- Residual-risk honesty: FAIL for R5-2 specificity and contradictory silent-laundering language.
- Six-condition gate: FAIL on evidence-baseline access.
- Ratification fields: correctly pending.

No ratification, tag, commit, merge, push, or repository edit was performed.

## 12. Required Actions

### Blocking actions before ratification

1. Ensure dispatcher construction and every run reject any provenance outside the three allowed values, or revise the enforcement claims to the weaker behavior actually implemented.
2. Validate executor return shape and require `success` to be a Boolean before using it for graph state or evidence.
3. Resolve the executed-without-evidence paths for malformed returns and serialization failures, or truthfully downgrade “evidence on every governed execution” from enforced.
4. Add an explicit constitutional disclosure of R5-2: the shared `simulated_executor` singleton can be deliberately re-marked process-wide.
5. Remove or qualify the `05:59-62` assertion that silent attribution laundering is prevented.
6. Freeze a new immutable proposal revision containing the remediation and its negative-path tests.
7. Conduct a new review satisfying all six conditions, including accessible authoring/remediation evidence records.

### Non-blocking follow-up

- Add dedicated JSONL round-trip assertions for outcome and provenance types.
- Add negative tests for empty, unknown, non-string, and post-construction provenance mutations.
- Correct future release/test summaries to distinguish total, passed, and skipped counts.
- Consider detecting duplicate logical-provider-to-agent bindings.

### Accepted residual risks

Subject to honest disclosure:

- R5-1 `functools.wraps` metadata inheritance.
- Deliberate executor misdeclaration that no callable inspection can prove false.
- T1–T17 limitations already accurately classified, including legacy ungoverned entrypoints, norm-only ratification integrity, guard name collisions, writable registries, and registry-contingent judgement protection.

### Optional future enhancements

- Canonical encodings for all evidence modes.
- Live OpenClaw identity-map integration testing.
- Mechanical artifact-class, approval, precedence, suspension, and review-condition enforcement.
- Immutable or externally authenticated evidence/ratification storage.
