# Dual-Write Playbook

**Part of:** [L004 Release, QA, and Engineering Playbooks](../../../docs/LISAOS/L004_RELEASE_QA_PLAYBOOKS.md)

Use this playbook when introducing a new storage mechanism (table, field, post type) that must co-exist with a legacy read/write path during a transition period.

---

## When to Use

- A new database table stores data that was previously stored in post meta.
- A new post type holds data that was previously stored in user meta.
- A new table field duplicates information from an existing column.
- The old code path must continue to work while the new code path is verified.
- The transition period is temporary (one sprint) or permanent (dual-read for backward compatibility).

---

## Pre-Flight Checks

- [ ] The legacy read path is identified and its callers are documented.
- [ ] The new write path is defined: which method(s) perform the dual write.
- [ ] Error handling for dual-write failure is agreed: fail open or fail closed?
- [ ] The legacy path remains the source of truth for readers, or both paths are authoritative?
- [ ] Edge cases enumerated: unlink, re-link, duplicate detection, inactive statuses.

---

## Implementation Rules

1. **Write to the new path in the same method that writes to the old path.** Example: `HEB_Practitioner::save_meta()` updates `_heb_practitioner_user_id` (old) AND calls `HEB_Identity_Links::create_link()` (new) in the same code block.
2. **Fail closed on the dual write.** If the new write fails (returns `WP_Error`), log the error but do NOT roll back the old write. The dual write is a secondary index — the primary write still completes.
3. **Check for existing link before creating.** If the new path already has an entry for this user+type, update it rather than creating a duplicate.
4. **Handle unlink (user_id = 0).** When the old path clears the association, the dual-write must also remove the new path's record.
5. **Handle re-link (different entity, same user).** When the old path changes the target, delete the old link and create a new one in the new path.

### Pseudocode

```php
public static function save_meta( $entity_id, array $data ) {
    $user_id = absint( $data[ self::META_USER_ID ] );
    
    // 1. Write to legacy path (always)
    update_post_meta( $entity_id, self::META_USER_ID, $user_id );
    
    // 2. Dual-write to new path
    if ( $user_id > 0 ) {
        $existing_link = HEB_Identity_Links::get_link_for_user( $user_id, 'practitioner' );
        if ( ! $existing_link ) {
            $result = HEB_Identity_Links::create_link( $user_id, 'practitioner', $entity_id, 'active' );
            if ( is_wp_error( $result ) ) {
                error_log( '[DualWrite] create failed: ' . $result->get_error_message() );
            }
        } elseif ( (int) $existing_link->wp_user_id !== $user_id ) {
            HEB_Identity_Links::delete_link( (int) $existing_link->id );
            $result = HEB_Identity_Links::create_link( $user_id, 'practitioner', $entity_id, 'active' );
            if ( is_wp_error( $result ) ) {
                error_log( '[DualWrite] re-link failed: ' . $result->get_error_message() );
            }
        }
    } else {
        // Unlink: remove from new path
        $existing_link = HEB_Identity_Links::get_link_for_user( $user_id, 'practitioner' );
        if ( $existing_link ) {
            HEB_Identity_Links::delete_link( $existing_link->id );
        }
    }
}
```

---

## Validation Steps

1. **Write test:** Create a new entity (e.g. practitioner), associate with a user. Verify legacy meta written AND new table row created.
2. **Re-link test:** Change the user association. Verify old link removed, new link created. No orphan records.
3. **Unlink test:** Clear the user association. Verify legacy meta set to 0 AND new table row removed.
4. **Duplicate prevention:** Attempt to associate the same user with a second entity of the same type. Verify the new path returns a conflict error.
5. **Read path test:** Call the legacy read function. Verify it returns the correct entity ID (from legacy meta, not the new table).
6. **Error handling test:** Simulate a failure in the new write path (e.g. invalid entity ID). Verify legacy write still completes. Verify error is logged.

---

## Evidence Required

- [ ] Row count in new table before/after write.
- [ ] Row count in new table before/after re-link.
- [ ] Row count in new table before/after unlink.
- [ ] Legacy meta value before/after write.
- [ ] Duplicate prevention: attempt 2 links for same user+type, confirm conflict error.
- [ ] Legacy read path returns correct value after dual write.
- [ ] Error log entries for any simulated failure cases.

---

## Rollback Considerations

- **The legacy path is always authoritative** until the transition period ends. Rollback means removing the dual-write code; the legacy path continues working.
- If the new table has rows that reference stale data (e.g. a deleted practitioner), a cleanup migration may be needed on rollback.
- Do NOT delete source records during dual-write. The new path is a secondary index, not a primary store.

---

## Common Failure Modes

| Failure | Symptom | Fix |
|---------|---------|-----|
| New path not created on write | Dual-write code not reached | Check the guard conditions: is the entity type valid? Is user_id > 0? |
| Orphan rows on unlink | Dual-write doesn't handle user_id=0 | Add the `else { delete_link() }` branch for the unlink case. |
| Duplicate rows on re-link | Code creates a new row instead of deleting + re-creating | Check for existing link before create; update or delete-then-create. |
| Conflict error on first write | Unique constraint on user+type but old path allows it | Decide: can one user have two practitioners? If not, the new path correctly enforces this. If yes, the constraint is wrong. |
| Legacy read returns stale data | Reader doesn't use new table | That's expected during transition. The new table is not the source of truth yet. |

---

## Related

- [Migration Playbook](migration-playbook.md)
- [Backfill Playbook](backfill-playbook.md)
- [Runtime Verification Playbook](runtime-verification-playbook.md)
- [WordPress Constraints](../wordpress-constraints.md)
