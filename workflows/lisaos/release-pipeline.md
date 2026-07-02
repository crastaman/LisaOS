# LisaOS Release Pipeline

**Part of:** [L004 Release, QA, and Engineering Playbooks](../../docs/LISAOS/L004_RELEASE_QA_PLAYBOOKS.md)

## Pipeline

```text
Architecture Approved
     ↓
1. Engineering
     ↓
2. Self Review
     ↓
3. OpenClaw Runtime QA  ← pre-commit gate
     ↓
4. Commit
     ↓
5. Regression QA  ← post-commit, pre-push gate
     ↓
6. Push / Release Approval
```

---

## Stage 0: Architecture Approved

| Field | Value |
|-------|-------|
| **Owner** | LisaOS Agent (coordinator) |
| **Purpose** | Confirm the architecture proposal is reviewed against platform constraints before engineering begins. |
| **Required artefacts** | Architecture spec or plan document. References checked against [WordPress Constraints](../wordpress-constraints.md) (or equivalent). |
| **Exit criteria** | Architecture spec is approved and logged. No unresolved constraint violations. |
| **Failure handling** | Return to architecture author with specific violation citations. Do not proceed to Engineering. |

---

## Stage 1: Engineering

| Field | Value |
|-------|-------|
| **Owner** | Engineering Agent (Codex or human) |
| **Purpose** | Implement the approved architecture in code. |
| **Required artefacts** | Source changes. Applicable playbook followed (migration, dual-write, backfill, etc.). |
| **Exit criteria** | Code compiles / parses. No WP fatal errors on activation. |
| **Failure handling** | Fix in progress. Do not proceed to Self Review with known parse/activation errors. |

---

## Stage 2: Self Review

| Field | Value |
|-------|-------|
| **Owner** | Engineering Agent |
| **Purpose** | Review own code against the WordPress constraints reference and the applicable playbook checklist. |
| **Required artefacts** | Self-review notes or diff annotations. Constraint checklist marked complete. |
| **Exit criteria** | No obvious constraint violations. Playbook rules followed. |
| **Failure handling** | Fix defects found in self-review. Iterate between Engineering and Self Review as needed. |

---

## Stage 3: OpenClaw Runtime QA (pre-commit gate)

| Field | Value |
|-------|-------|
| **Owner** | QA Agent (OpenClaw, separate from Engineering Agent) |
| **Purpose** | Verify real execution in a LocalWP environment using dedicated/discardable databases. All core tests run before any commit. |
| **Required artefacts** | QA results (JSON with evidence). Error logs. Table schemas. Row counts. Idempotency diffs. Duplicate counts. |
| **Exit criteria** | All core tests PASS or PASS WITH OBSERVATIONS. No REQUIRES FIXES or BLOCK RELEASE results. Evidence captured. |
| **Failure handling** | Log defect. Do NOT commit. Return to Engineering with specific failures and evidence. |

---

## Stage 4: Commit

| Field | Value |
|-------|-------|
| **Owner** | Engineering Agent |
| **Purpose** | Commit changes to the local branch after Runtime QA passes. |
| **Required artefacts** | Commit message following conventional commits format (`type(scope): message`). QA results archived. |
| **Exit criteria** | Commit created. QA result file staged or archived alongside code. |
| **Failure handling** | If commit fails (merge conflict, pre-commit hook), fix and retry. Do not skip back to QA — commit only code that already passed Runtime QA. |

---

## Stage 5: Regression QA (post-commit, pre-push gate)

| Field | Value |
|-------|-------|
| **Owner** | QA Agent (OpenClaw) |
| **Purpose** | Re-run the full QA suite on the committed code to catch regressions from unrelated changes or merge conflicts. |
| **Required artefacts** | Same as Stage 3 (full QA results). Comparison with pre-commit results. |
| **Exit criteria** | All tests still PASS/PASS WITH OBSERVATIONS. No new failures compared to pre-commit run. |
| **Failure handling** | If new failures appear, investigate. May indicate regression from concurrent changes. Do NOT push. Return to Engineering. |

---

## Stage 6: Push / Release Approval

| Field | Value |
|-------|-------|
| **Owner** | LisaOS Agent (coordinator) / Human |
| **Purpose** | Final gate: confirm all stages complete and push to remote. |
| **Required artefacts** | Evidence bundle (QA results, git log, architecture approval reference). |
| **Exit criteria** | Branch pushed. Release decision logged (PASS / PASS WITH OBSERVATIONS). |
| **Failure handling** | BLOCK RELEASE or REQUIRES FIXES → do not push. Notify coordinator with summary. |

---

## Related

- [L004 Release, QA, and Engineering Playbooks](../../docs/LISAOS/L004_RELEASE_QA_PLAYBOOKS.md)
- [QA Standards](../qa-standards.md)
- [Migration Playbook](playbooks/migration-playbook.md)
- [Dual-Write Playbook](playbooks/dual-write-playbook.md)
- [Backfill Playbook](playbooks/backfill-playbook.md)
- [Runtime Verification Playbook](playbooks/runtime-verification-playbook.md)
- [WordPress Constraints](../wordpress-constraints.md)
