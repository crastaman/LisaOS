# Backfill Playbook

**Part of:** [L004 Release, QA, and Engineering Playbooks](../../../docs/LISAOS/L004_RELEASE_QA_PLAYBOOKS.md)

Use this playbook when creating new posts, records, or entities from existing data (user meta, post meta, legacy tables) as part of a migration or data import.

---

## When to Use

- Creating CPT posts from user meta (e.g. facilitator profiles from `heb_display_name`, `heb_bio`, `heb_juice_account`).
- Creating identity links from existing `_heb_practitioner_user_id` post meta.
- Populating a new column from an existing column during a schema migration.
- Any bulk one-time data transformation that creates records from existing data.

---

## Pre-Flight Checks

- [ ] The source data location is confirmed (user meta, post meta, old table).
- [ ] The target post type or table exists and is registered.
- [ ] The backfill logic handles the case where the target post type is NOT registered (graceful skip).
- [ ] A completion flag (option) prevents re-running after success.
- [ ] Deduplication check: are there already rows in the target? If so, the backfill is either complete or needs dedup logic.
- [ ] The backfill is idempotent: running it after completion produces zero new rows.
- [ ] Edge cases enumerated: empty/blank meta values, non-existent CPT, partial failures.

---

## Implementation Rules

1. **Guard with CPT availability check.** If the target post type is not registered (e.g. WP-CLI edge case where `init` hasn't fired), return `status: skipped_cpt_not_registered` and do NOT set the completion flag.
2. **Guard with completion flag.** Check the backfill option at the top. If set, return `status: already_complete` immediately.
3. **Scan users with the required meta key.** Use `get_users( [ 'meta_key' => '...', 'meta_value' => '', 'meta_compare' => '!=' ] )` to find candidates. Empty strings are not candidates.
4. **Skip users with empty display name** (the key meta field). Log the skip.
5. **Use `wp_insert_post()` for creation.** Set `post_title` to the user's display name, `post_name` to the user slug, `post_status` to `publish`.
6. **Transfer meta.** Copy each legacy meta field to the new post's meta using the standard `_heb_facilitator_*` prefix.
7. **Create identity link.** After the post is created, create an identity link for the new entity. If the link fails, log the error and count as `failed`.
8. **Set the completion flag only on full success.** If any candidate fails (post creation error, link creation error), do NOT set the flag. Return `status: incomplete` so the backfill retries on the next request.

### Pseudocode

```php
public static function maybe_backfill_facilitator_profiles() {
    // Early exit: flag already set
    if ( get_option( self::BACKFILL_OPTION ) ) {
        return [ 'status' => 'already_complete', ... ];
    }
    
    // Early exit: CPT not registered
    if ( ! post_type_exists( 'heb_fac_profile' ) ) {
        return [ 'status' => 'skipped_cpt_not_registered', ... ];
        // Do NOT set the completion flag
    }
    
    // Find candidates
    $users = get_users( [
        'meta_key'   => 'heb_display_name',
        'meta_value' => '',
        'meta_compare' => '!=',
    ] );
    
    $succeeded = 0;
    $skipped   = 0;
    $failed    = 0;
    
    foreach ( $users as $user ) {
        $display_name = get_user_meta( $user->ID, 'heb_display_name', true );
        if ( empty( $display_name ) ) {
            $skipped++;
            continue;
        }
        
        // Create post
        $post_id = wp_insert_post( [
            'post_type'   => 'heb_fac_profile',
            'post_title'  => $display_name,
            'post_name'   => $user->user_login,
            'post_status' => 'publish',
        ] );
        
        if ( is_wp_error( $post_id ) ) {
            $failed++;
            continue;
        }
        
        // Transfer meta
        update_post_meta( $post_id, '_heb_facilitator_display_name',  $display_name );
        update_post_meta( $post_id, '_heb_facilitator_bio',           get_user_meta( $user->ID, 'heb_bio', true ) );
        update_post_meta( $post_id, '_heb_facilitator_juice_account', get_user_meta( $user->ID, 'heb_juice_account', true ) );
        
        // Create identity link
        $link = HEB_Identity_Links::create_link( $user->ID, 'facilitator', $post_id, 'active' );
        if ( is_wp_error( $link ) ) {
            $failed++;
            error_log( '[Backfill] link failed for user ' . $user->ID . ': ' . $link->get_error_message() );
            continue;
        }
        
        $succeeded++;
    }
    
    // Only set flag on full success
    if ( $failed === 0 ) {
        update_option( self::BACKFILL_OPTION, current_time( 'mysql' ) );
        return [ 'status' => 'complete', 'candidates' => count($users), 'succeeded' => $succeeded, 'skipped' => $skipped, 'failed' => $failed ];
    }
    
    return [ 'status' => 'incomplete', 'candidates' => count($users), 'succeeded' => $succeeded, 'skipped' => $skipped, 'failed' => $failed ];
}
```

---

## Validation Steps

1. **CPT-unavailable test:** Remove the CPT from globals, call the backfill. Verify `status: skipped_cpt_not_registered`, flag NOT set.
2. **Full successful run:** Seed users with valid meta, call backfill. Verify correct number of posts created, all meta transferred, identity links created.
3. **Skip empty meta:** Include users with empty `heb_display_name`. Verify they are skipped (counted in `$skipped`).
4. **Skip users without meta at all:** Users who never had `heb_display_name` set should not appear as candidates at all.
5. **Idempotency:** Call backfill again after successful run. Verify `status: already_complete`, zero new posts, zero new links.
6. **Partial failure:** Simulate a failure in `wp_insert_post()` (e.g. remove the CPT before the loop). Verify flag NOT set, status `incomplete`.
7. **Source data preserved:** Verify legacy user meta is still intact after backfill.

---

## Evidence Required

- [ ] Candidate user count (users with non-empty source meta).
- [ ] Posts created: count before/after.
- [ ] Identity links created: count before/after (by entity_type).
- [ ] Meta transferred: verify each field on each new post.
- [ ] Skipped count (users with empty display name).
- [ ] Failed count, with error log messages.
- [ ] Completion flag state before/after.
- [ ] Idempotency: before/after diff = 0.
- [ ] Source data: verify legacy meta not deleted.

---

## Rollback Considerations

- **Backfill is additive only.** It creates new posts and links but does NOT delete source data.
- To roll back, delete the created posts and identity links. A rollback migration (`m0027` or similar) can do this.
- Do NOT run the rollback while the corresponding UI or API is consuming the new data.
- Because the completion flag is set only on full success, a partial run (failure mid-way) will retry on the next request. This is intentional — it ensures eventual consistency.

---

## Common Failure Modes

| Failure | Symptom | Fix |
|---------|---------|-----|
| CPT not registered | Backfill returns `skipped_cpt_not_registered` on HTTP requests | Move the backfill call later in the `init` priority or ensure CPT is registered before backfill. |
| Duplicate posts on re-run | Backfill ran before flag was set, then flag was set, then re-run returned `already_complete` | Check flag at top before any work. For defence in depth, check `post_exists()` before `wp_insert_post()`. |
| Post creation fails | `wp_insert_post()` returns `WP_Error` | Log the error, increment `failed`, do NOT set flag. The next request retries. |
| Identity link fails | `create_link()` returns `WP_Error` | Log the error, increment `failed`, do NOT set flag. The post already exists, so the retry should detect the post and skip creation, then create the link. |
| Data inconsistency | Post created but link not created | The post is orphaned. The retry should either skip the post (found via `get_posts` by user slug) and create only the link, or the backfill should check for existing posts per candidate. |
| Empty display name counts as candidate | `get_users()` with `meta_compare=!=` includes empty strings | Add explicit `empty()` check inside the loop. |

---

## Related

- [Migration Playbook](migration-playbook.md)
- [Dual-Write Playbook](dual-write-playbook.md)
- [Runtime Verification Playbook](runtime-verification-playbook.md)
- [WordPress Constraints](../wordpress-constraints.md)
