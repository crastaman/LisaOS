# LisaOS QA Standards

**Part of:** [L004 Release, QA, and Engineering Playbooks](../../docs/LISAOS/L004_RELEASE_QA_PLAYBOOKS.md)

---

## 1. Core Principles

1. **LocalWP runtime QA is mandatory before any commit** for WordPress/plugin changes. Unit tests are not sufficient — real database, real plugin activation, real POST data.
2. **Evidence is mandatory.** No test is complete without captured output. Every SQL query, WP-CLI command, screen scrape, and error log message must be recorded.
3. **Idempotency is always tested.** Run each migration, backfill, or data transformation twice. Confirm zero new artefacts on the second run.
4. **Duplicate detection is always tested.** Confirm that unique constraints (application-layer or DB-layer) prevent duplicate user-to-entity links and duplicate entity-to-type records.
5. **Regression matrix covers all previously verified paths.** Legacy read paths must still return correct data after new fields/tables are introduced.
6. **Separate QA agent from engineering agent.** The agent that wrote the code must not be the same agent that runs QA. This catches blind spots.
7. **Dedicated discardable databases.** Never test on the development database. Create a fresh database per test scenario.

---

## 2. QA Environment Requirements

- **WordPress:** LocalWP site with a real MySQL/MariaDB database (not SQLite).
- **Plugin:** The development plugin directory must be symlinked into the LocalWP `wp-content/plugins/` directory (or copied).
- **WP-CLI:** Must be available and configured for the test site.
- **Databases:** Dedicated databases for each test scenario (fresh install, upgrade, backfill). Drop after completion.
- **Error logging:** WP_DEBUG and WP_DEBUG_LOG enabled. Capture `wp-content/debug.log`.
- **No production data exposure.** Use dummy users, dummy posts, dummy meta values.

---

## 3. Architecture Compliance Review

Every QA pass must verify that the implementation matches the architecture specification:

- Entity types are correct (e.g. `practitioner` vs `facilitator` vs `customer`).
- Table names follow the established convention (`wp_heb_*`).
- Column names, data types, and indexes match the spec.
- Migration numbers follow the established sequence.
- No new capabilities, roles, or AJAX handlers unless explicitly called for.

---

## 4. Regression Matrix

The regression matrix is built incrementally. Each sprint adds its test scenarios to the matrix.

| Scenario | What It Verifies | Example (S015) |
|----------|-----------------|-----------------|
| Fresh install | Plugin activates, tables created, default state correct | S015: identity links table created, CPT registered |
| Upgrade | Existing data preserved, new fields populated, migration idempotent | S015: practitioner links backfilled, duplicates zero |
| Backfill — CPT available | New posts created, meta transferred, identity links created | S015: facilitator profiles created from usermeta |
| Backfill — CPT unavailable | Safe abort, flag NOT set | S015: `skipped_cpt_not_registered` |
| Entity validation | Invalid inputs rejected with correct error codes | S015: 9 identity link validation cases |
| Idempotency | Second run produces zero new records | S015: links diff=0, posts diff=0 |
| Duplicate prevention | Unique constraints enforced at application layer | S015: duplicate user+type and entity+type rejected |
| Reactivation | Plugin deactivation/reactivation safe | S015: links diff=0 |
| Legacy read path | Old code still returns correct values | S015: `HEB_Facilitators::get_practitioner_id_for_user()` |
| Security | No leaked caps, no new auth holes, no new endpoints | S015: no new roles, no new AJAX handlers |

---

## 5. Evidence Capture

Every QA test run captures:

### Mandatory

| Artefact | Format | Tool |
|----------|--------|------|
| Git status | Plain text | `git status --short --branch` |
| Database schema | `SHOW CREATE TABLE` output | WP-CLI `eval` or `db query` |
| Column definitions | `information_schema.COLUMNS` query | WP-CLI `eval` |
| Index definitions | `SHOW INDEX FROM` output | WP-CLI `eval` |
| Row counts | Grouped by entity_type where applicable | WP-CLI `eval` |
| Duplicate counts | GROUP BY + HAVING > 1 | WP-CLI `eval` |
| Idempotency diff | Before/after diff on re-run | WP-CLI `eval` (two calls) |
| Error log tail | Last 50 lines of debug.log | `tail` |
| WP-CLI output | Full stdout + stderr | Tee to log file |

### When Applicable

| Artefact | When |
|----------|------|
| Screenshot | UI changes, admin pages, error modals |
| PHP error trace | Any WP_Error or exception |
| POST/GET response | AJAX handler testing |
| HTTP response code | Endpoint testing |

---

## 6. QA Result Statuses

| Status | Meaning | Gate Action |
|--------|---------|-------------|
| **PASS** | All tests pass. No observations. | Clear for next stage. |
| **PASS WITH OBSERVATIONS** | All tests pass, but non-blocking issues noted (e.g. known technical debt, documented limitations). | Clear for next stage. Observations should be tracked. |
| **REQUIRES FIXES** | Some tests fail or produce unexpected results. Defects found. | Must fix before proceeding. Not necessarily release-blocking. |
| **BLOCK RELEASE** | A fundamental defect prevents release. | Release blocked until fixed and re-verified. Do not push. |

### Example Verdicts

- `PASS` — All 7 test categories green. Idempotent. No duplicates. Evidence captured. No observations.
- `PASS WITH OBSERVATIONS` — All tests green. CPT uses capability_type `post` (accepted debt, documented). No portal consumer code yet.
- `REQUIRES FIXES` — Migration fails on upgrade path. CPT missing index. Identity link validation returns 500 on duplicate.
- `BLOCK RELEASE` — CPT slug exceeds WordPress 20-character max. Schema version mismatch causes data loss. Migration not idempotent.

---

## 7. Result Artefact

QA results are stored as JSON at `reports/wbs/qa-<tag>-results.json`:

```json
{
  "tag": "s015-phase-a0",
  "date": "2026-07-02",
  "agent": "openclaw-qa",
  "status": "PASS",
  "tests": [
    { "id": 1, "name": "Fresh Install", "result": "PASS", "evidence": "..." },
    { "id": 2, "name": "Existing Upgrade", "result": "PASS", "evidence": "..." },
    { "id": 4, "name": "Facilitator Backfill", "result": "PASS", "evidence": "..." },
    { "id": 5, "name": "Identity Link Validation", "result": "PASS", "evidence": "..." },
    { "id": 6, "name": "Regression", "result": "PASS" },
    { "id": 7, "name": "Security", "result": "PASS" }
  ],
  "observations": [],
  "recommendation": "PASS"
}
```

---

## Related

- [L004 Release, QA, and Engineering Playbooks](../../docs/LISAOS/L004_RELEASE_QA_PLAYBOOKS.md)
- [Release Pipeline](../release-pipeline.md)
- [Runtime Verification Playbook](playbooks/runtime-verification-playbook.md)
- [WordPress Constraints](../wordpress-constraints.md)
