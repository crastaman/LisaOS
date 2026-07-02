# Runtime Verification Playbook

**Part of:** [L004 Release, QA, and Engineering Playbooks](../../../docs/LISAOS/L004_RELEASE_QA_PLAYBOOKS.md)

Use this playbook when running pre-commit QA in a LocalWP environment against WordPress plugin changes. This is the operational guide for executing the QA pipeline's Stage 3 (OpenClaw Runtime QA).

---

## When to Use

- Before committing any WordPress plugin code change.
- Before pushing any committed code (regression runs).
- After merge conflicts or rebase that might affect plugin behaviour.
- Any time a full end-to-end check is needed in a real WordPress environment.

---

## Pre-Flight Checks

- [ ] LocalWP site is running (`Local` app → "Start Site").
- [ ] WP-CLI is available and points to the LocalWP site root.
- [ ] The development plugin is symlinked into LocalWP's `wp-content/plugins/`.
- [ ] MySQL socket path is known (or the TCP port).
- [ ] Admin credentials for the test site are available (`qaadmin` / `qa-pass-123`).
- [ ] Dedicated test databases will be used (NOT the development database).
- [ ] WP_DEBUG and WP_DEBUG_LOG are enabled in `wp-config.php`.

### Finding the MySQL Socket

```bash
# From the LocalWP site root:
source ../.envrc
echo "$MYSQL_HOME"
# Socket: $MYSQL_HOME/../../mysql/mysqld.sock
# Or TCP port: 127.0.0.1:10004 (varies by site)

# Quick test:
mysql --protocol=socket -uroot -proot -S "$MYSQL_HOME/../../mysql/mysqld.sock" -e "SELECT 1"
```

---

## Test Environment Setup

### 1. Create a Temporary WordPress Root

```bash
WP='/Users/lisa/Local Sites/wbs-development/app/public'
TMP="/tmp/wbs-qa-<tag>-fresh"  # unique per test scenario
rm -rf "$TMP"; mkdir -p "$TMP"

# Symlink everything except wp-config.php
for f in "$WP"/* "$WP"/.[!.]*; do
  base=$(basename "$f")
  [ "$base" = 'wp-config.php' ] && continue
  ln -s "$f" "$TMP/$base" 2>/dev/null || true
done

# Copy and modify wp-config.php
cp "$WP/wp-config.php" "$TMP/wp-config.php"
perl -0pi -e "s/define\(\s*'DB_NAME'\s*,\s*'[^']+'\s*\);/define( 'DB_NAME', '$DB' );/" "$TMP/wp-config.php"
perl -0pi -e "s/define\(\s*'DB_HOST'\s*,\s*'[^']+'\s*\);/define( 'DB_HOST', 'localhost' );/" "$TMP/wp-config.php"
```

### 2. Create Dedicated Databases

```bash
for DB in qa_fresh_<tag> qa_upgrade_<tag> qa_backfill_<tag>; do
  mysql ... -e "CREATE DATABASE \`$DB\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
done
```

### 3. Install WordPress (for fresh databases)

```bash
wp --path="$TMP" core install \
  --url=http://<site>.test \
  --title='QA Tag' \
  --admin_user=qaadmin \
  --admin_password=qa-pass-123 \
  --admin_email=qa@example.test \
  --skip-email >/dev/null 2>&1
```

---

## Running Tests

### Required Test Scenarios

| # | Scenario | Database | What It Verifies |
|:-:|----------|----------|-----------------|
| 1 | Fresh Install + plugin activation | `qa_fresh_<tag>` | Tables created, CPT registered, default state |
| 2 | Upgrade from previous version | `qa_upgrade_<tag>` | Migration runs, data backfilled, idempotent |
| 3 | Backfill — CPT available | `qa_backfill_<tag>` | Posts created, meta transferred, links created |
| 4 | Backfill — CPT unavailable | `qa_backfill_<tag>` | Graceful skip, flag NOT set |
| 5 | Validation gates | Any database | Error codes, duplicate detection, delete |
| 6 | Regression (legacy paths) | Any database | Old reader functions still return correct data |
| 7 | Security (caps, roles, AJAX) | Any database | No new capabilities leaked, no new endpoints |

### Test Execution Pattern

Each test follows this structure:

```bash
wp --path="$TMP" eval '
global $wpdb;

// 1. Capture state before
echo "rows_before=" . $wpdb->get_var("SELECT COUNT(*) FROM ...") . "\n";

// 2. Run the operation
$result = HEB_Migrations::run();
echo "result=" . ($result ? "OK" : "FAIL") . "\n";

// 3. Capture state after
echo "rows_after=" . $wpdb->get_var("SELECT COUNT(*) FROM ...") . "\n";

// 4. Idempotency check (re-run)
$result2 = HEB_Migrations::run();
echo "rows_after2=" . $wpdb->get_var("SELECT COUNT(*) FROM ...") . "\n";

// 5. Duplicate detection
$dupes = $wpdb->get_var("SELECT COUNT(*) FROM (SELECT wp_user_id,entity_type,COUNT(*) c FROM ... GROUP BY wp_user_id,entity_type HAVING c>1) x");
echo "duplicates=" . $dupes . "\n";
' 2>&1 | tee /tmp/qa-<tag>-test-<n>.log
```

---

## Evidence Required

Every test run captures:

- [ ] Git status at start and end (`git status --short --branch`)
- [ ] Database schema (table DDL via `SHOW CREATE TABLE`)
- [ ] Row counts before/after for every affected table
- [ ] Idempotency diff (before → after → after re-run)
- [ ] Duplicate group counts (user+type, entity+type)
- [ ] Error log tail (last 50 lines of `wp-content/debug.log`)
- [ ] Full WP-CLI stdout/stderr per test
- [ ] PHP error output (if any)
- [ ] For failures: error code, WP_Error message, PHP trace

---

## Cleanup

After all tests pass:

```bash
for DB in qa_fresh_<tag> qa_upgrade_<tag> qa_backfill_<tag>; do
  mysql ... -e "DROP DATABASE IF EXISTS \`$DB\`;"
done
rm -rf /tmp/wbs-qa-<tag>-*
```

---

## Common Issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| WP-CLI critical error | PHP warning/error during `eval` | Wrap test code in try/catch. Check `debug.log`. |
| MySQL socket not found | `mysql: command not found` | Source `../.envrc` from the LocalWP site root. Use `$MYSQL_HOME` to find the socket path. |
| Table already exists | `dbDelta()` doesn't report errors | It's expected — `dbDelta()` is additive. Verify schema with `SHOW CREATE TABLE`. |
| WP-CLI uses wrong DB | Re-used temp directory from previous test | Always use fresh temp dirs and fresh databases per test scenario. |
| `post_type_exists()` returns false | CPT not registered in WP-CLI's current request | Some WP-CLI commands bootstrap before `init`. Use a dedicated WP-CLI `eval` call that waits for `init`. |
| Backfill runs twice | Different code path activates backfill on `init` AND on migration | Check callers. The backfill should be triggered from exactly one place. |

---

## Related

- [Release Pipeline](../release-pipeline.md)
- [QA Standards](../qa-standards.md)
- [Migration Playbook](migration-playbook.md)
- [Dual-Write Playbook](dual-write-playbook.md)
- [Backfill Playbook](backfill-playbook.md)
- [WordPress Constraints](../wordpress-constraints.md)
