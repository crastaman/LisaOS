# WordPress Constraints Reference

**Part of:** [L004 Release, QA, and Engineering Playbooks](../../docs/LISAOS/L004_RELEASE_QA_PLAYBOOKS.md)

This document records WordPress-specific constraints that every engineer and reviewer must check before writing or approving WBS (or any WordPress plugin) code.

---

## CPT Slug Length

```
register_post_type( 'slug_here', ... )
```

- **Max slug length: 20 characters.** `register_post_type()` returns `WP_Error` with code `post_type_length_invalid` for longer slugs.
- **Always count your slug before coding.** `echo strlen('my_custom_post_type_slug');`
- The slug is the first argument to `register_post_type()`. The `$args` array does not affect this constraint.
- **This includes hyphens and underscores.** `'healing-events-booking-x'` is 24 chars — also invalid.

**S015 Lesson:** `heb_facilitator_profile` (23 chars) failed silently. The error surfaced only in debug mode. Always count.

### Checking

```php
$slug = 'your_post_type_slug';
if ( strlen( $slug ) > 20 ) {
    wp_die( 'Post type slug too long: ' . $slug . ' (' . strlen( $slug ) . ' chars)' );
}
```

---

## Migration Ordering and Versioning

- Schema version is stored as `heb_db_version` option.
- Format: three-part semver (e.g. `3.16.0`). Do NOT use `3.16` — `version_compare()` treats `3.16` < `3.9` differently than string comparison.
- Migrations run in numeric order (`m0001`, `m0002`, ..., `m0026`, ...). Each migration method checks if its work is already done before proceeding.
- Guard with `version_compare( $current, $target, '<' )` — this ensures migrations run only once per version.

```php
if ( version_compare( $current_db_version, '3.16.0', '<' ) ) {
    self::m0026( $wpdb );
    update_option( 'heb_db_version', '3.16.0' );
}
```

---

## CPT Registration Timing

- CPT registration must happen on the `init` action hook. Not earlier.
- `register_post_type()` called before `init` produces a `_doing_it_wrong()` notice and does NOT register the post type.
- Code that depends on a registered CPT (backfills, queries) must execute on or after `init`, priority > the CPT registration priority.
- In WP-CLI, `init` fires as expected, but the execution context differs from HTTP (no admin, no theme, no current user).

```php
add_action( 'init', [ __CLASS__, 'register_facilitator_profile_post_type' ] );
```

---

## Activation Hooks

- `register_activation_hook()` fires on admin-side plugin activation.
- **It does NOT re-fire on plugin updates.** For update migrations, hook into `plugins_loaded` (priority 1) and compare `heb_db_version` against `HEB_VERSION`.
- In WP-CLI, `wp plugin activate` triggers the activation hook. `wp plugin update` does NOT. The `plugins_loaded` guard handles this.
- Activation hooks execute before `init`. Any code that needs registered post types during activation will fail.

---

## Idempotent Migrations

- Every migration must be safe to run multiple times.
- Table creation: `dbDelta()` handles `IF NOT EXISTS`.
- Column addition: use `maybe_add_column()`, not raw `ALTER TABLE ... ADD`.
- Data backfill: check if records already exist before inserting. Use `INSERT IGNORE` or `SELECT COUNT(*)` guards.
- The `heb_db_version` guard ensures migration methods are called only once, but the methods themselves must still tolerate being called with already- applied state.

---

## Schema Versioning

| Field | Pattern | Example |
|-------|---------|---------|
| Option name | `heb_db_version` | `3.16.0` |
| Format | `MAJOR.MINOR.PATCH` | `3.16.0` |
| Storage | `get_option()` / `update_option()` | autoload = yes |
| Comparison | `version_compare()` | `version_compare('3.15.0', '3.16.0', '<')` |
| Increment | PATCH for bugfixes, MINOR for features, MAJOR for breaking | S015: `3.15.0` → `3.16.0` |

---

## AJAX, Nonce, and Capability Checks

- WBS does not add new AJAX handlers in the current pattern. If adding one:
  - Use `wp_ajax_*` and `wp_ajax_nopriv_*` hooks.
  - Verify nonce with `check_ajax_referer()`.
  - Check capabilities with `current_user_can()`.
  - Exit with `wp_die()` or `wp_send_json_*()`.
- Do NOT expose write endpoints without authentication.

---

## REST API Exposure

- Default CPTs and tables are NOT exposed via REST unless `show_in_rest => true` is set in `register_post_type()`.
- If REST exposure is needed, add it explicitly with `'show_in_rest' => true, 'rest_base' => 'safe-base-name'`.
- Non-REST endpoints use admin-ajax or admin-post patterns behind capability checks.

---

## Frontend-Only Portal Constraint

- WBS uses a React frontend that communicates via REST/GraphQL (or admin-ajax with nonces).
- No new admin pages are added in the current pattern.
- The portal is the consumer; the plugin provides data infrastructure only.
- Any new public-facing endpoint must check for authentication and capability.

---

## WP User Identity vs WBS Business Identity

This is the most important conceptual constraint for WBS.

| Concept | Example | WP User | WBS Entity |
|---------|---------|:-------:|:----------:|
| Subscriber | `john@example.com` | ✅ `user_id` | ❌ |
| Practitioner | Dr. Jane Smith | ✅ `user_id` | ✅ `heb_practitioner` post ID |
| Facilitator | Yoga Class Leader | ✅ `user_id` | ✅ `heb_fac_profile` post ID |
| Customer | Booking client | ✅ `user_id` | ✅ booking record |
| Student | Course enrollee | ✅ `user_id` | ✅ enrolment record |

**Rules:**
- A WP user may be zero, one, or multiple business identities.
- A practitioner is NOT a facilitator. They are different entity types with different business logic.
- A facilitator is NOT a practitioner. Facilitators lead events; practitioners run appointments.
- Identity links (`wp_heb_identity_links`) bridge WP users to business entities.
- Roles (`heb_facilitator`) are WP-level capabilities, not WBS entity types.

---

## Facilitator Is Not Practitioner

- **Practitioners** (HEB post type `heb_practitioner`) run one-on-one appointments, have availability profiles, work periods, and service associations.
- **Facilitators** (HEB post type `heb_fac_profile`) lead group events and courses, have facilitator profiles with display name, bio, and juice account.
- They share no database tables, no CPT, and no business logic.
- An identity link's `entity_type` distinguishes them: `'practitioner'` vs `'facilitator'`.
- A WP user can be both a practitioner and a facilitator — they would have two identity links with different entity_types.

---

## WBS Identities Are Not Necessarily WP Roles

| WBS Identity | WP Role? | Notes |
|-------------|:--------:|-------|
| Subscriber | ✅ `subscriber` | Built-in WP role |
| Administrator | ✅ `administrator` | Built-in WP role |
| Practitioner | ❌ | Business entity — associates with a WP user via user ID meta |
| Facilitator | ❌ | Business entity — relates to `heb_facilitator` role historically, but the role is coincidental |
| Customer | ❌ | A booking participant, not a WP concept |
| Student | ❌ | A course enrollee, not a WP concept |
| Manager | ❌ | A business role mapped to WP administrator or custom role |

Do NOT assume that adding a WP role means creating a WBS entity, and do NOT assume that creating a WBS entity means the WP user should be assigned a role.

---

## Related

- [L004 Release, QA, and Engineering Playbooks](../../docs/LISAOS/L004_RELEASE_QA_PLAYBOOKS.md)
- [Development Setup](../../docs/DEVELOPER_SETUP.md) (if exists)
- [Migration Playbook](playbooks/migration-playbook.md)
- [Dual-Write Playbook](playbooks/dual-write-playbook.md)
- [Backfill Playbook](playbooks/backfill-playbook.md)
