---
schema: lisaos.gpt_context.v1
last_updated: 2026-07-08
owner: LisaOS
status: placeholder
---

# WBS / HEB Context

## Current state of this file

`identity/IDENTITY.md` lists **WBS / HEB** as a primary project, and it is
the stated primary project focus following the 2026-07-08 LisaOS 3.0
freeze. `~/Lisa/knowledge/WBS/` exists as the designated knowledge-base
location for WBS content but currently contains no populated files. WBS
product work itself lives in a separate repository
(`~/Projects/WBS/healing-events-booking`, per
`docs/LISAOS/REPOSITORY_BOUNDARIES.md`) — LisaOS/Console must never write
there.

## Rule for the Advisor

Do not assume any specific WBS/HEB product facts beyond "WBS/HEB is a live,
currently-prioritized project." If a WBS-tagged Decision Bundle needs
product context this file doesn't have, say so in `open_questions` rather
than guessing.

## Rule for maintainers

Populate this file from `~/Lisa/knowledge/WBS/` once it has content, and
log the change in `CHANGELOG.md`.
