# L004 Release, QA, and Engineering Playbooks

**Job ID:** L004-LISAOS-RELEASE-QA-PLAYBOOKS  
**Repository:** `~/Lisa`  
**Scope:** Documentation and workflow standardisation only.  
**Runtime behaviour:** Unchanged. No WBS files modified. No automation built.

---

## 1. Purpose

S015 Phase A0 (Identity & Access Foundation) on WBS revealed several operational gaps that delayed release confidence:

- Architecture was engineered and QA'd concurrently, meaning some structural defects (e.g. CPT slug length) were found late.
- Self-review by the same agent that wrote the code missed constraint violations that a human peer would catch.
- LocalWP environment tests were run ad-hoc rather than from a standard checklist.
- Evidence capture was retroactive instead of mandatory per-test.
- There was no formal release pipeline — commit, push, and merge happened without a gate between them.

L004 documents the standard release pipeline, QA standards, and reusable playbooks so that every future WBS sprint (and any future LisaOS-managed project) follows the same proven sequence.

---

## 2. Lessons from S015 Phase A0

| Lesson | Impact | Mitigation in L004 |
|--------|--------|--------------------|
| Architecture approval and engineering overlapped | CPT slug length defect (23 chars, WP max 20) found during QA instead of architecture review | Architecture approval is now a dedicated pipeline stage with mandatory constraint review |
| Self-review is not sufficient | Same agent missed the CPT slug violation; only caught during systematic testing | Self-review is a separate stage, but OpenClaw Runtime QA is a mandatory separate pass |
| No LocalWP QA before commit | PHP errors discovered only after full upgrade-path testing | LocalWP runtime verification is a gated pre-commit step |
| Ad-hoc evidence capture | Retroactive log collection missed some error output | Per-test evidence capture is a hard requirement in every playbook |
| No regression gate before push | Confident release required a full re-run after unrelated file changes | Regression QA is a dedicated pipeline stage after commit, before push |
| WordPress-specific constraints not documented | Each new engineer re-discovers WP limits | A central constraints reference doc prevents repeat violations |

---

## 3. LisaOS Release Pipeline

The full pipeline is defined in [`workflows/lisaos/release-pipeline.md`](../../workflows/lisaos/release-pipeline.md).

High-level flow:

```text
Architecture Approved
     ↓
Engineering
     ↓
Self Review
     ↓
OpenClaw Runtime QA  ← pre-commit gate
     ↓
Commit
     ↓
Regression QA  ← post-commit, pre-push gate
     ↓
Push / Release Approval
```

Each stage has an owner, purpose, required artefacts, exit criteria, and failure handling. See the pipeline document for full details.

---

## 4. QA Standards

QA standards are defined in [`workflows/lisaos/qa-standards.md`](../../workflows/lisaos/qa-standards.md).

Key principles:

- **LocalWP runtime QA is mandatory before any commit** for WordPress/plugin changes.
- **Evidence is mandatory** — every test produces SQL output, WP-CLI output, error logs, or screenshots.
- **Idempotency is always tested** — run the migration/backfill twice, confirm zero new artefacts on re-run.
- **Duplicate detection is always tested** — confirm unique constraints hold at the application layer.
- **Regression matrix covers all previously verified paths** — legacy read paths must still work.
- **Four QA result statuses** — PASS, PASS WITH OBSERVATIONS, REQUIRES FIXES, BLOCK RELEASE.

---

## 5. Engineering Playbooks

Reusable playbooks for common WBS engineering patterns:

| Playbook | When to Use | File |
|----------|------------|------|
| **Migration Playbook** | Any schema change, version bump, or data transformation on plugin activation/upgrade | [`playbooks/migration-playbook.md`](../../workflows/lisaos/playbooks/migration-playbook.md) |
| **Dual-Write Playbook** | Writing to a new table while preserving a legacy read path | [`playbooks/dual-write-playbook.md`](../../workflows/lisaos/playbooks/dual-write-playbook.md) |
| **Backfill Playbook** | Creating posts/records from existing metadata for a new entity type | [`playbooks/backfill-playbook.md`](../../workflows/lisaos/playbooks/backfill-playbook.md) |
| **Runtime Verification Playbook** | Pre-commit QA in LocalWP using dedicated databases | [`playbooks/runtime-verification-playbook.md`](../../workflows/lisaos/playbooks/runtime-verification-playbook.md) |
| **WordPress Constraints Reference** | Common WP limits every engineer must check before coding | [`../../workflows/lisaos/wordpress-constraints.md`](../../workflows/lisaos/wordpress-constraints.md) |

---

## 6. Common WordPress Constraints

Refer to [`workflows/lisaos/wordpress-constraints.md`](../../workflows/lisaos/wordpress-constraints.md) for the definitive reference.

Critical constraints from S015:

- **CPT slug max length: 20 characters.** `register_post_type()` returns `WP_Error` with code `post_type_length_invalid` for longer slugs. Always count your slug before coding.
- **Migration ordering matters.** Version strings are compared with `version_compare()`. Schema changes must be ordered and idempotent.
- **CPT registration must happen on `init`, not earlier.** Any code that depends on a registered post type must wait until `init` has fired.
- **Activation hooks in WP-CLI may differ from HTTP.** Some `init`-dependent operations complete differently under `wp plugin activate` vs browser activation.
- **User IDs and business entity IDs are distinct.** A WP user is not a practitioner, not a facilitator, not a customer. Identity links tables bridge the gap.

---

## 7. Required Evidence

Every QA pass must capture the following (stored in `reports/wbs/qa-<tag>-results.json` with supporting logs):

- **Git state** (`git status --short --branch`) before and after
- **Database schema** (table columns, indexes, via `DESCRIBE` / `SHOW CREATE TABLE`)
- **Record counts** (total rows per affected table, grouped by entity type)
- **Duplicate counts** (rows with same `wp_user_id+entity_type` or `entity_type+entity_id`)
- **Idempotency diff** (before/after counts after a second run)
- **Error logs** (`wp-content/debug.log`, PHP error output)
- **Standard output** from WP-CLI `eval` / `db query` calls
- **Failure statuses** (error codes, WP_Error messages, exception traces)

For UI changes, include screenshots.

---

## 8. Release Status Definitions

| Status | Meaning | Gate |
|--------|---------|------|
| **PASS** | All tests pass. No observations. | Cleared for release. |
| **PASS WITH OBSERVATIONS** | All tests pass, but non-blocking observations are noted (e.g. known debt). | Cleared for release with caveats documented. |
| **REQUIRES FIXES** | Some tests fail or produce unexpected results. Defects found, but not necessarily release-blocking. | Must fix before release decision. |
| **BLOCK RELEASE** | A fundamental defect prevents release (e.g. broken schema, data loss risk, WP constraint violation). | Release blocked until defect is fixed and re-verified. |

---

## 9. How This Applies to Future WBS Sprints

Starting from S016 and all subsequent WBS sprints:

1. **Architecture** must pass through the architecture review stage (pipeline gate) before any code is written.
2. **Engineering** follows the applicable playbook (migration, dual-write, backfill, etc.) from the start.
3. **Self-review** uses the WordPress constraints reference as a checklist.
4. **Runtime QA** follows the runtime verification playbook on LocalWP with a disposable database.
5. **Evidence** is captured per-test, per-playbook.
6. **Regression** is run after commit, before push, using the same playbook structure.
7. **Release decision** uses the four-status QA result and the release pipeline exit criteria.

The same pipeline applies to non-WBS LisaOS-managed projects, substituting the WordPress constraints reference with the equivalent platform constraints for that project.

---

## 10. Next Recommendation

After L004:

1. Stage L005 — **PR Review Checklist** — formalise the PR review gate for other agents to follow.
2. Stage L006 — **Evidence Capture Automation** — define a standard JSON schema for QA results (`reports/schema.yml`) so results are machine-parseable.
3. Stage L007 — **Cron-Based Regression Suite** — define a cron playbook that runs the full regression suite on `main` weekly and alerts on new failures.

## Related

- [Release Pipeline](../../workflows/lisaos/release-pipeline.md)
- [QA Standards](../../workflows/lisaos/qa-standards.md)
- [L003 Runtime Execution Framework](L003_RUNTIME_EXECUTION_FRAMEWORK.md)
- [KERNEL.md](KERNEL.md)
