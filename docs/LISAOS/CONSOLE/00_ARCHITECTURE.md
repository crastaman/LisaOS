# Lisa Console v1 — Architecture

**Status:** DESIGN APPROVED
**Date:** 2026-07-08
**Repository:** `~/Lisa` (LisaOS only)

## Problem

Roshan currently has to manually inspect LisaOS's JSONL evidence logs, job
packets, and report directories to know what happened and decide what's
next. There is no single place aggregating jobs/workers/approvals/reports,
nothing distills a completed job's evidence into an executive-readable
recommendation, and nothing pushes a notification when a decision is
actually needed.

## Philosophy → components

- **Lisa works** → existing dispatcher/workforce_resolver/engines
  (unchanged) produce evidence; a new exporter turns that evidence into a
  Decision Bundle (`01_DECISION_BUNDLE_SPEC.md`).
- **GPT compresses** → a new GPT Advisor turns a Decision Bundle plus the
  version-controlled Context Pack (`docs/GPT_CONTEXT/`) into a short
  Executive Brief with a recommendation (`02_GPT_ADVISOR_SPEC.md`). GPT
  never executes anything — it has no code path that can, per
  `docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md`.
- **Roshan decides** → the Console plus an ntfy notification
  (`03_NTFY_NOTIFICATION_SPEC.md`) is the only channel that can ever write
  a decision; nothing auto-executes on GPT's say-so.

## Scope discipline

Purely additive alongside frozen LisaOS 3.0 core (Phases 0–3 untouched).
Console only *reads* existing artifacts (job packets, registries, reports,
governance JSONL logs) and adds new, clearly scoped modules next to them
(`advisors/`, `console/`, this doc set) — nothing here modifies core
dispatcher/engine/governance behavior. Console never touches WBS paths
(`docs/LISAOS/REPOSITORY_BOUNDARIES.md`).

## Role abstraction

This architecture is written against platform **roles**
(Planner/Builder/Reviewer/Auditor/CTO/Operator), not specific models. See
`docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md` for the full principle
and the current example role→model mapping. Concretely: nothing in
`advisors/` or `console/` may hardcode a specific model name as a
load-bearing dependency; which OpenAI model the GPT Advisor calls is a
configuration value, not an architectural coupling.

## Data flow

```
Job packet reaches a terminal state with approval_required: true
  -> Decision Bundle Exporter (core/decision_bundle_exporter.py, Phase C1)
  -> Decision Bundle written (DRAFT)
  -> GPT Advisor reads Context Pack + full bundle (Phase C2)
  -> Executive Brief written
  -> ntfy push: headline + recommendation + confidence (Phase C3)
  -> Roshan opens Console over Tailscale (Phase C4)
  -> Approve or Reject (Safe Action Model, below)
  -> decision written into bundle; governance gate satisfied
  -> (only now) dispatcher proceeds with the already-existing execution path,
     unchanged
```

## Safe Action Model

The Console can only ever **write a decision**, never execute a job action
directly.

- **Approve** writes `decision: {"choice": "approve", "by": "roshan",
  "at": ..., "note": "..."}` into the bundle, moves it `DRAFT` →
  `PUBLISHED` in the artifact lifecycle, and appends an audit line. This
  satisfies the existing governance-gate approval requirement that
  dispatch already checks — it extends the `record_acknowledgement()`
  pattern in `core/governance_guard.py` to accept a `bundle_id`. Console
  does not bypass or duplicate that gate.
- Actual execution stays entirely the dispatcher/workforce pipeline's job,
  run exactly as today. Console never shells out, never calls engines
  directly, and never touches the filesystem outside `reports/console/`
  and its own audit log.
- **Reject** writes the same shape with `choice: "reject"` and a
  **required, non-empty** note. The job packet is marked `cancelled`; no
  execution ever follows a rejected bundle.
- GPT's `approve_with_changes` / `needs_more_info` labels are
  **display-only** on the brief. The only two buttons Roshan can actually
  click are **Approve** and **Reject** — a deliberately small action
  surface, no footgun buttons.
- Every decision requires the Tailscale-identity header to match the one
  configured owner identity (`04_SECURITY_MODEL.md`).

## Deployment model

- Console runs as a local process bound to `127.0.0.1:8420`, served by
  `waitress` (single worker — a single-user local tool, not a production
  service; Flask's dev server is not used).
- `tailscale serve https / http://127.0.0.1:8420` publishes it **only** to
  the tailnet, at a stable MagicDNS name — the ntfy deep-link target.
- **No `tailscale funnel`** (public internet exposure) — explicitly
  excluded. This design is the one explicit approval for Tailscale
  exposure that `governance/SECURITY.md`'s default-off policy requires,
  scoped strictly to `serve`.
- Process management: macOS launchd plist, starts Console on login,
  restarts on crash.

## Failure handling

- OpenAI unreachable/timeout → brief marked failed; Console still fully
  usable off the raw bundle; ntfy still notifies (degraded message).
- ntfy unreachable → audit-logged, single attempt, no retry storm; Roshan
  can still reach pending approvals by opening the Console directly.
- Tailscale identity header missing/mismatched → 403, audit-logged as
  access-denied, not silent.
- Bundle export fails mid-write → written to `.tmp`, atomically renamed
  only on success — `/approvals` never shows a half-written bundle.
- Concurrent Approve/Reject race → compare-and-swap guarded: only the
  first write against `decision: null` succeeds; second attempt rejected
  with "already decided."
- Console process crash → launchd restarts it; no in-memory state to
  lose, everything is file-backed.

## Deliberately out of scope for v1

- Editing jobs/workers from the Console (read-only mirror only).
- Multi-user support (single owner identity only).
- Bundle diffing/history UI beyond the flat audit tail.
- Self-hosted ntfy (documented as a swappable future option,
  `04_SECURITY_MODEL.md`).
- Mobile-specific UI — Tailscale + phone browser is sufficient for the
  ntfy deep-link.
