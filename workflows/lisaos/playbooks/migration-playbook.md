# Migration Playbook

**Part of:** [L004 Release, QA, and Engineering Playbooks](../../../docs/LISAOS/L004_RELEASE_QA_PLAYBOOKS.md)

Use this playbook when implementing any database schema change, version bump, or data transformation that runs on plugin activation or upgrade.

---

## When to Use

- Adding a new database table.
- Adding/modifying columns in an existing table.
- Adding new indexes.
- Backfilling data from legacy meta into new table columns.
- Changing the stored schema version.
- Any migration that must run when a user activates or updates the plugin.

---

## Pre-Flight Checks

- [ ] The sprint/issue specifies which migration number to use (e.g. `m0026`).
- [ ] Migration numbers are sequential and tracked in `HEB_Migrations::run()`.
- [ ] The `heb_db_version` option format is confirmed (e.g. `3.16.0` — three-part semver).
- [ ] The new table name follows the `wp_heb_*` prefix pattern.
- [ ] Column names, types, and indexes match the architecture specification.
- [ ] A dedicated test database is created for upgrade-path testing.
- [ ] The current `heb_db_version` is checked to determine correct migration starting point.

---

## Implementation Rules

1. **One migration method per change.** Each migration is a private static method `m000N()` that takes `$wpdb` as its only parameter.
2. **Guard at the top.** Check if the migration has already run (e.g. `if ( ! $wpdb->query(...) )` — if the table already exists, consider alternate approach).
3. **Use `dbDelta()` for table creation.** It handles `IF NOT EXISTS`, column diffs, and index changes safely. Pass the exact `CREATE TABLE` SQL.
4. **Use `maybe_add_column()` / `maybe_add_index()` for incremental changes.** Avoid raw `ALTER TABLE` that can fail on duplicate column.
5. **Log everything.** Use `error_log()` with the method name and key outcomes.
6. **Idempotent by design.** Running the migration twice must produce the same final state with zero errors on the second run.
7. **Do NOT drop production tables in a migration.** Ever. If a table needs removal, use a separate deprecation plan.

### Numeric Sequence

```php
private static function m0026( $wpdb ) {
    $table_name = $wpdb->prefix . 'heb_identity_links';
    
    $charset_collate = $wpdb->get_charset_collate();
    
    $sql = "CREATE TABLE {$table_name} (
        id bigint unsigned NOT NULL auto_increment,
        ...
        PRIMARY KEY  (id),
        ...
    ) {$charset_collate};";
    
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    dbDelta( $sql );
    
    // Log outcome
    $exists = $wpdb->get_var( "SHOW TABLES LIKE '{$table_name}'" );
    error_log( '[HEB_Migrations] m0026: table ' . ( $exists ? 'created/exists' : 'MISSING' ) );
}
```

---

## Validation Steps

1. **Fresh install:** Create a clean WP install, activate plugin. Verify table exists with all columns and indexes correct.
2. **Upgrade:** Install WP with an older plugin version (or no plugin), manually set `heb_db_version` below the migration version. Activate plugin. Verify migration ran, table created, data backfilled if applicable.
3. **Idempotency:** Re-activate plugin or re-run `HEB_Migrations::run()`. Confirm zero new records/columns/errors.
4. **Duplicate detection:** If the migration creates rows from existing data, verify no duplicate `user_id+type` or `entity+type` rows.
5. **Version check:** Confirm `heb_db_version` is now at the target version (e.g. `3.16.0`).

---

## Evidence Required

- [ ] `SHOW CREATE TABLE` for the new/modified table.
- [ ] `SHOW INDEX FROM` for the new/modified table.
- [ ] Row count before and after upgrade.
- [ ] Row count before and after idempotency re-run.
- [ ] Duplicate group counts (GROUP BY + HAVING > 1).
- [ ] `heb_db_version` before and after.
- [ ] Error log tail for the migration run.
- [ ] If backfilling from user meta: before/after count of users with relevant meta, vs rows created in the new table.

---

## Rollback Considerations

- **Migration is forward-only.** There is no `m0026_down()`. To revert, deploy a new migration that reverses the change.
- If a migration creates a table, the table persists after deactivation. The plugin's `uninstall.php` may clean it up.
- If a migration backfills data, do NOT delete source data. The migration copies; it does not move.
- Test rollback by setting `heb_db_version` back to the previous value and re-running `HEB_Migrations::run()`. The migration should detect the table exists and skip creation, and the backfill should produce zero new rows.

---

## Common Failure Modes

| Failure | Symptom | Fix |
|---------|---------|-----|
| Table already exists | `CREATE TABLE` in `dbDelta()` returns 0 | `dbDelta()` handles this — it's a no-op. Check early-exit logic. |
| Duplicate column | `ALTER TABLE ... ADD COLUMN` fails | Use `maybe_add_column()` instead of raw SQL. |
| `heb_db_version` mismatch | Migration skipped because version compare failed | Confirm the version string format. `version_compare()` treats `3.16.0 > 3.15.0` correctly but `3.16 > 3.9` may not. |
| Migration runs on every page load | Missing version guard — migration runs on every `plugins_loaded` | Guard: `if ( version_compare( $current, $target, '<' ) ) { m0026(...); }`. |
| Backfill creates duplicates | Migration ran twice without duplicate detection | Use `INSERT IGNORE` or check existence before insert. Always test idempotency. |

---

## Related

- [Dual-Write Playbook](dual-write-playbook.md)
- [Backfill Playbook](backfill-playbook.md)
- [Runtime Verification Playbook](runtime-verification-playbook.md)
- [WordPress Constraints](../wordpress-constraints.md)
- [QA Standards](../qa-standards.md)
