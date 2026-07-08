# GPT Context Pack

**Status:** ACTIVE (Phase C0 scaffolding)
**Owner:** LisaOS
**Date:** 2026-07-08
**Repository:** `~/Lisa` (LisaOS only)
**Consumed by:** `advisors/gpt_advisor.py` (Phase C2, not yet implemented)

## What this is

The OpenAI API has no access to ChatGPT conversational memory. Every call the
GPT Advisor makes is stateless. This directory is the version-controlled
substitute: everything the Advisor is allowed to know about Roshan, BAR,
LisaOS, WBS, and how decisions should be made lives here, in plain text, in
git. If it is not written in this pack, the Advisor does not know it — do not
assume it can infer context from a prior conversation, because there is no
prior conversation from its point of view.

The GPT Advisor pipeline (see
[`docs/LISAOS/CONSOLE/02_GPT_ADVISOR_SPEC.md`](../LISAOS/CONSOLE/02_GPT_ADVISOR_SPEC.md))
always loads the **entire** pack, concatenated in file order, plus one full
Decision Bundle. Roshan and Lisa never hand-pick which context files apply to
a given decision — GPT reads everything and decides what is relevant, exactly
as GPT reads the whole bundle rather than a curated subset of it.

## Files

| # | File | Purpose |
|---|---|---|
| 01 | [`01_SYSTEM_ROLE.md`](01_SYSTEM_ROLE.md) | What the GPT Advisor is/isn't; output contract |
| 02 | [`02_BAR_TECH_CONTEXT.md`](02_BAR_TECH_CONTEXT.md) | BAR Technologies project context |
| 03 | [`03_ROSHAN_PREFERENCES.md`](03_ROSHAN_PREFERENCES.md) | How Roshan wants work approached and reported |
| 04 | [`04_LISAOS_CONTEXT.md`](04_LISAOS_CONTEXT.md) | LisaOS state: what's frozen, what's active |
| 05 | [`05_WBS_CONTEXT.md`](05_WBS_CONTEXT.md) | WBS/HEB project context |
| 06 | [`06_DECISION_PRINCIPLES.md`](06_DECISION_PRINCIPLES.md) | How to reason about a recommendation |
| 07 | [`07_CURRENT_PRIORITIES.md`](07_CURRENT_PRIORITIES.md) | What matters right now (time-sensitive) |
| 08 | [`08_GLOSSARY.md`](08_GLOSSARY.md) | Terms used across bundles and briefs |
| 09 | [`09_ARCHITECTURAL_CONSTRAINTS.md`](09_ARCHITECTURAL_CONSTRAINTS.md) | Constitutional layer — binding, overrides all else on conflict |

## Maintenance rule

`07_CURRENT_PRIORITIES.md` decays fast and must be kept current — a stale
priorities file actively misleads the Advisor rather than just being
unhelpful. Every edit to any file in this pack must be logged in
[`CHANGELOG.md`](CHANGELOG.md).
