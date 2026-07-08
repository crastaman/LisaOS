# Decision Consumption Model

**Status:** Phase C5 — documentation only. No consumption code exists or
is being added by this phase; this doc exists specifically because the
Phase C5 requirements ask how "Lisa executes" is preserved once a
decision is recorded, and the honest answer needs to be written down
rather than assumed.

## The three-part philosophy, mapped to real modules

```
Lisa works.       -> core/dispatcher.py + core/workforce_resolver.py (unchanged, pre-existing)
GPT compresses.    -> advisors/gpt_advisor.py (Phase C2) -- advisory only
Roshan decides.    -> console/actions.py::record_decision() (Phase C4) -- the ONLY way `decision` is ever written
Lisa executes.     -> core/dispatcher.py + core/workforce_resolver.py (the SAME pre-existing path -- see below)
```

The interesting question this phase asks: between "Roshan decides" and
"Lisa executes," what actually happens? Who reads `decision.choice ==
"approve"` and turns it into real work?

## Current state, stated honestly

**Nothing consumes a recorded decision automatically today.** This is
not an oversight — it's a direct consequence of a fact established back
in Phase C1: LisaOS job packets (`jobs/schema.yml`) are documentation-
only, and a Decision Bundle is typically built **from already-recorded
evidence** (`reports/lisa/workforce_evidence.jsonl`) rather than as a
pre-execution gate for work that hasn't happened yet. In the current
system, by the time a bundle exists, the underlying LisaOS-dispatched
work (if any) has usually already run — the bundle is Roshan's
after-the-fact review artifact, and its `proposed_actions` describe
candidate *next* steps (e.g. "merge the fix," "deploy to production"),
which are frequently **not** LisaOS-dispatcher jobs at all — they're
real-world follow-ups (a git merge, a production deploy) that happen
outside LisaOS entirely, exactly as they would if the Console didn't
exist.

So today, "Lisa executes" after an Approve decision means: **Roshan (or
whatever process would normally do that follow-up step) does it,
exactly as before** — the Console recorded a rationale-backed decision;
it did not, and structurally could not, trigger anything.

## The intended future model — and the invariant that survives it

If a `proposed_action` genuinely is LisaOS-dispatcher-executable work
(a new job worth delegating to the workforce), the correct way to act on
an approved decision is:

1. A human (today), or a future scheduler/poller (not yet built, not
   part of this phase or any phase C0–C5), reads `reports/console/
   bundles/*/bundle.json` and finds bundles where `decision.choice ==
   "approve"`.
2. That reader — **never `console/`** — invokes the existing, already-
   governed execution path directly: `core/dispatcher.py` ->
   `core/workforce_resolver.py`, the same path every other delegated
   LisaOS job already goes through, with the same capability matching,
   fail-closed model resolution, and evidence recording
   (`governance/GOVERNANCE.md`, rule 12). A recorded decision does not
   invent a new execution mechanism — it authorizes use of the one that
   already exists.
3. The dispatcher runs the job exactly as it would for any other
   delegated work, producing its own `workforce_evidence.jsonl` records
   — which could, in turn, feed a *new* Decision Bundle for the next
   round of review, if warranted.

**The invariant that must survive this, forever, even after such a
consumer is eventually built**: the consumer is architecturally
*outside* `console/`. Nothing in `console/app.py`'s routes, nothing in
`console/actions.py`, nothing triggered by a page load or a form
submission ever calls `core.dispatcher` or `core.workforce_resolver`.
This is not a policy Console follows — it's a fact about which modules
`console/` imports, and that fact is independently verified by every
phase's grep-for-`core`/`engines`-imports check
(`test_no_route_rule_contains_a_forbidden_action_word`, and the
equivalent zero-import proofs in `advisors/`). Adding a future decision-
consuming scheduler would mean writing an **entirely new, separate
module** (e.g. a hypothetical `core/decision_consumer.py`) that itself
goes through the dispatcher the same way every other governed caller
does — it would require zero changes to `console/`, because `console/`'s
job already ends the moment `decision` is written.

## Why this is the correct design, not a limitation to fix later

Collapsing "Roshan decides" and "Lisa executes" into one system (i.e.
having the Console itself call the dispatcher the moment a decision is
recorded) would reintroduce exactly the risk this whole project exists
to avoid: a web form with a direct path to real execution. Keeping
consumption **out-of-band and pull-based** — something else reads the
decision later, on its own schedule, through its own governed path —
means the Console's blast radius stays fixed at "one JSON field and an
audit log entry," regardless of how sophisticated a future consumer
becomes. That is what "the Console must remain incapable of execution
even after deployment" means concretely: not a promise, a module
boundary.
