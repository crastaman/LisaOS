# Decision Consumption Model

**Status:** Phase C5 — documentation only. No consumption code exists or
is being added by this phase. This doc exists because the Phase C5
requirements ask, explicitly, how "Lisa executes" is preserved once a
decision is recorded — the honest current answer, plus a fully specified
design for the handoff step, needs to be written down rather than
assumed or left as a placeholder.

**CTO review note (2026-07-08):** this design was reviewed and accepted
as the canonical governance handoff model for Console v1, on the
condition that the Execution Request schema carry immutable provenance
and dispatcher-claim fields, and that its lifecycle be expanded beyond a
simple pending/completed/failed split. Both refinements are incorporated
below. Per the review conditions: this remains documentation only — no
Approval Watcher or dispatcher intake code is introduced by this
refinement, and none should be inferred from the detail added here.

## The complete lifecycle

```
Lisa creates Decision Bundle
  -> GPT creates Executive Brief
    -> Roshan approves/rejects
      -> Decision recorded
        -> [Approval Watcher detects it, writes an Execution Request]   <-- the "?" this doc specifies
          -> Lisa (dispatcher) executes
```

| Stage | Component | Status |
|---|---|---|
| Lisa creates Decision Bundle | `core/decision_bundle_exporter.py` | **Implemented** (Phase C1) |
| GPT creates Executive Brief | `advisors/gpt_advisor.py` | **Implemented** (Phase C2) |
| Roshan approves/rejects | `console/actions.py::record_decision()` | **Implemented** (Phase C4) |
| Decision recorded | `bundle.json`'s `decision` field | **Implemented** (Phase C4) |
| Approval detected, Execution Request written | a new, separate component — **designed here, not built** | **Design only** (Phase C5) |
| Lisa executes | `core/dispatcher.py` + `core/workforce_resolver.py` | **Pre-existing, unchanged** |

## Why the "?" step is a separate component, not a Console feature

Collapsing "Roshan decides" and "Lisa executes" into one system — having
the Console itself call the dispatcher the moment a decision is recorded
— would reintroduce exactly the risk this whole project exists to avoid:
a web form with a direct path to real execution. The design below keeps
consumption **out-of-band, pull-based, and filesystem-mediated**, per
this phase's explicit instruction to prefer filesystem artifacts over
direct invocation. That preference isn't just a style choice here: a
filesystem artifact is inspectable, diffable, and re-playable by a human
before anything executes, where a direct function call is none of those
things.

## Component: the Approval Watcher (design, not yet built)

A new, small, separate module — nominally `core/approval_watcher.py`
(or a `bin/` script; exact location is an implementation-time decision,
not fixed by this doc) — with exactly one job: detect newly-approved
bundles and hand them off, on disk, to the execution side.

### Who detects approvals

The Approval Watcher. It is invoked **on demand or on a schedule**
(cron, launchd, or a manual `bin/`-style command — not a long-running
daemon triggered by Console activity, since nothing in Console ever
calls out to anything). Each run:

1. Lists `reports/console/bundles/*/bundle.json`.
2. Filters to bundles where `decision.choice == "approve"`.
3. Filters out any bundle that already has a corresponding Execution
   Request (idempotency — see "Retry behavior" below).
4. For each remaining bundle, writes one Execution Request.

The Watcher **only ever reads** `reports/console/bundles/` and **only
ever writes** into the new execution-request directory below — it has
no import of `console/` (it doesn't need Console running at all; it
reads the same files a browser would render) and, critically, **no
import of `core.dispatcher` or `core.workforce_resolver` either**. It
cannot execute anything, by the same "verify by grep" standard applied
to every module in this project.

### Who creates execution jobs

Still the Approval Watcher — but "creates" here means **writes a
filesystem artifact describing a candidate job**, not "runs a job."

New artifact type, schema `lisaos.execution_request.v1`, one file per
request, living at a fixed path for its entire lifetime (see "Lifecycle"
below for why this design supersedes an earlier directory-per-state
sketch):

```
reports/lisa/execution_requests/<request_id>.json
```

```json
{
  "request_id": "er-2026-07-08-a1b2c3d4",
  "schema": "lisaos.execution_request.v1",
  "bundle_id": "db-2026-07-08-...",
  "bundle_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "job_id": "impl-booking-email-fix",
  "created_at": "2026-07-08T...",
  "decision": {"choice": "approve", "by": "roshan@example.ts.net", "at": "...", "note": "..."},
  "proposed_actions": [ /* copied verbatim from the bundle */ ],
  "status": "pending",
  "consumed_by": null,
  "consumed_at": null
}
```

- **`bundle_sha256`** — a SHA-256 hash of the source `bundle.json`'s
  exact bytes at the moment the Execution Request was created. This is
  immutable provenance: a Decision Bundle is itself immutable once
  exported (Phase C1), but its `decision` field is written *after*
  export by a separate call (`console/actions.py::record_decision()`);
  hashing the bundle at request-creation time gives whatever eventually
  reads this request a way to verify it is still acting on the exact
  bundle content Roshan actually saw and approved, not a
  since-mutated or misidentified one. (A dispatcher-side consumer, not
  built by this phase, would be expected to recompute the hash of the
  current `bundle.json` and refuse to proceed if it doesn't match —
  the check itself is future work, but the field that makes the check
  possible belongs in the schema from the start.)
- **`consumed_by` / `consumed_at`** — null until a dispatcher-side
  component claims this request (see "Lifecycle" below); populated
  exactly once, at the `pending → claimed` transition, and never
  cleared except by the explicit manual reset described in "Retry
  behavior."

Deliberately mirrors `core/decision_bundle_exporter.py`'s own
conventions otherwise: `reports/lisa/` (not `reports/console/`, since
this now belongs to the execution side, not Console's private storage),
a versioned schema string, and an atomic tmp-then-rename write for every
transition (never a partial write observable mid-transition).

**Where authority transfers**: precisely at the *initial* write (the
`pending` state). Before it, the only durable fact is "Roshan approved
something" (a Console-owned artifact, `bundle.json`). After it, there is
a **Lisa-owned** artifact, in `reports/lisa/` — the same tree
`workforce_evidence.jsonl` and the governance logs already live in —
describing a candidate for execution, complete with the provenance hash
needed to verify it's still trustworthy by the time anything acts on it.
The Watcher does not execute the request itself; it only makes the
request legible to whatever *does* have execution authority. A second,
distinct transfer of *responsibility* (not authority — authority was
never anywhere but the dispatcher) happens at `claimed`, described next.

## Lifecycle

Expanded, on CTO review, beyond a simple pending/completed/failed split
— `status` is the single authoritative field (not a directory the file
lives in, correcting the earlier sketch above); every transition is an
atomic rewrite of the same file, the same pattern
`console/actions.py::record_decision()` already uses for a bundle's
`decision` field:

```
pending -> claimed -> executing -> completed
pending -> claimed -> executing -> failed
pending -> cancelled
```

| Status | Meaning | Who sets it |
|---|---|---|
| `pending` | An Execution Request exists but no dispatcher-side component has accepted responsibility for it yet. | Approval Watcher, at creation |
| `claimed` | A dispatcher-side component has accepted responsibility — `consumed_by`/`consumed_at` are populated at this transition. Nothing has started running yet. | The (not-yet-built) dispatcher intake adapter |
| `executing` | Execution has actually started. | Same adapter, immediately before invoking the dispatcher |
| `completed` | Execution finished successfully. | Same adapter, after the dispatcher returns success |
| `failed` | Execution was attempted and failed. | Same adapter, after the dispatcher returns/raises failure |
| `cancelled` | Execution was deliberately withdrawn before completion — e.g. Roshan changes their mind after approving but before anything picked the request up. | A human, or a future Console-adjacent-but-still-not-Console tool — **not** part of this phase either |

The `pending → claimed` transition is the second half of the authority
story: `pending` says "this candidate exists"; `claimed` says "a
specific, identified dispatcher-side component (`consumed_by`) is now
accountable for it as of `consumed_at`." Two independent dispatcher-side
components racing to claim the same request is a real concern this
schema makes checkable (whoever writes `claimed` first wins; a second
writer sees `consumed_by` already set and must not overwrite it) — the
concrete locking mechanism is dispatcher-side implementation detail, not
fixed by this doc, but the schema fields that make the check possible
are specified now rather than retrofitted later.

### Where execution authority actually lives

Exclusively `core/dispatcher.py` → `core/workforce_resolver.py` —
**unchanged by this design**. The only new work at that end (also not
built by this phase) is a thin, optional intake adapter that can read an
Execution Request file and construct the `WorkPackage` the dispatcher
already knows how to consume — e.g. a `bin/lisa-dispatch
--from-execution-request <path>` flag, run manually by Roshan or by a
separate scheduled invocation. That adapter is dispatcher-side code,
reviewed and tested the same way any dispatcher change would be — it is
explicitly **not** part of `console/`, not part of the Approval Watcher,
and not part of this phase's deliverables. Whether it's built at all is
a future, separately-approved decision; today, a human reading the
Execution Request and acting on it manually is a completely sufficient
consumer.

### Audit implications

Two separate, append-only trails, owned by two separate trust domains —
deliberately not merged into one file:

- `reports/console/audit.jsonl` (existing, Phase C1–C5) records what
  **Console** did: `decision_recorded` already captures the
  approve/reject event itself. Nothing about this design changes that.
- A new `reports/lisa/execution_requests.jsonl` (design only, matching
  the existing `workforce_evidence.jsonl` JSONL-append convention)
  records what the **execution side** did, one line per status
  transition: `execution_request_created` (`pending`),
  `execution_request_claimed` (`claimed`, includes `consumed_by`),
  `execution_started` (`executing`), `execution_completed`,
  `execution_failed`, `execution_cancelled` — each with `request_id`,
  `bundle_id`, `bundle_sha256`, and a timestamp. This keeps the
  Console's audit trail exactly as scoped as it is today (it has no way
  to know or claim what happened after a decision, because nothing in
  Console does anything after a decision) while still giving the
  execution side its own honest, fully-transitioned record, in the same
  evidence-based style as everything else in this repo.

### Failure handling

- **Watcher fails mid-write**: atomic tmp-then-rename (same pattern as
  `bundle.json`) means a crash never leaves a half-written Execution
  Request — the next run either sees a complete file at `status:
  "pending"` or no file at all, never something in between.
- **Watcher can't determine an unambiguous job from a bundle** (e.g. a
  bundle with no LisaOS-executable `proposed_actions`, only real-world
  follow-ups like "merge the fix"): it writes no Execution Request at
  all for that bundle. Not every approval needs one — that's expected,
  not an error.
- **A dispatcher-side component claims a request but crashes before
  executing**: the request is left at `status: "claimed"` with a
  `consumed_by`/`consumed_at` pointing at the component that claimed
  it — visibly stuck, not silently lost. Recovering a stuck `claimed`
  request (e.g. after a crashed process) is, like retry, a deliberate
  manual decision (§ Retry behavior), not an automatic timeout — this
  phase does not specify a lease/heartbeat mechanism, since none of this
  is being built yet.
- **Dispatch itself fails** (the adapter feeds an Execution Request in
  and the dispatcher's existing fail-closed model resolution, capability
  matching, etc. rejects or fails it): `status` transitions to `"failed"`
  in place, with the failure reason recorded alongside it — never
  silently dropped, never left ambiguous between "not yet tried" and
  "tried and failed." This reuses whatever failure/evidence semantics
  `core/dispatcher.py` already has; nothing new is invented there.
- **Roshan changes their mind after approving, before anything claims
  the request**: `status` transitions to `"cancelled"` — a deliberate,
  attributed withdrawal, distinct from `"failed"` (which means execution
  was actually attempted).
- **Approval sits with no Watcher run at all** (e.g. cron isn't set up
  yet): nothing is lost. The approval is a durable fact in `bundle.json`
  regardless of whether anything has consumed it — this is the entire
  point of a pull-based, filesystem-mediated handoff instead of a
  fire-and-forget event. Roshan can always run the Watcher manually and
  get the same result as if it had run on schedule.

### Retry behavior

**Deliberately manual, not automatic.** This is a considered choice, not
an oversight: `governance/GOVERNANCE.md` rule 5 ("no automation without
clear rollback") and this project's repeated preference for fail-closed,
operator-attributed action over silent automation both argue against an
auto-retry loop here. More concretely: a `proposed_action` may be a
real-world, **non-idempotent** action ("deploy to production") —
silently retrying a failed execution automatically risks a duplicate
real-world side effect far worse than a duplicate notification (which is
exactly why `advisors/notify.py`'s bounded auto-retry is *not* the
pattern reused here). Instead:

- The Watcher's own approval→request step **is** naturally idempotent
  and safe to re-run anytime (step 3 above) — running it twice never
  creates two Execution Requests for the same bundle.
- A **failed** or **cancelled** Execution Request is retried only by a
  deliberate, attributed human action: resetting `status` back to
  `"pending"` and clearing `consumed_by`/`consumed_at` back to `null`,
  the same "explicit, attributed operator acknowledgement" pattern
  `core/governance_guard.py` already uses for overriding a stopped
  state. No code path does this automatically.
- A stuck **`claimed`** request (§ Failure handling) is recovered the
  same way — a human resets it to `pending` and clears the claim fields
  — never an automatic timeout-and-reclaim.

## The invariant that survives all of this, forever

Nothing above changes what's already independently verified: zero
imports of `core.dispatcher` / `core.workforce_resolver` / `engines/*`
anywhere in `console/` (checked by grep every phase), and no route,
button, or code path in `console/app.py` or `console/actions.py` that
can trigger anything beyond writing `decision` and an audit line. The
Approval Watcher and any future dispatcher-side intake adapter are, by
design, modules that do not exist inside `console/` and would require
zero changes to it. **The Console's job ends the moment `decision` is
written** — that boundary is what "the Console must remain permanently
incapable of execution" means concretely, and it holds regardless of
how sophisticated everything on the other side of the filesystem
handoff eventually becomes.
