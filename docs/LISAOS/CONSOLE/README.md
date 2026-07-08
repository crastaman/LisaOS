# Lisa Console v1

**Status:** DESIGN APPROVED — Phase C0 (scaffolding) in progress
**Owner:** LisaOS
**Date:** 2026-07-08 (design) / 2026-07-08 (Phase C0)
**Repository:** `~/Lisa` (LisaOS only)
**Relationship to core:** Additive. Does not reopen or modify the LisaOS 3.0
core freeze (`docs/LISAOS/V3/LISAOS_3.0_CLOSURE_REPORT.md`).

## What this is

A minimal private web app connecting Roshan, a GPT Advisor, and LisaOS:

```
Lisa works.
GPT compresses.
Roshan decides.
```

Lisa keeps executing exactly as it does today. A new GPT Advisor compresses
job evidence into a short Executive Brief. Roshan is the only actor who can
ever trigger an action, from one private page reachable only over
Tailscale, notified via ntfy. See
[`09_ARCHITECTURAL_CONSTRAINTS.md`](../../GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md)
for the binding constraints this design must never violate.

## Deliverable map

| # | Document | Covers |
|---|---|---|
| 00 | [`00_ARCHITECTURE.md`](00_ARCHITECTURE.md) | Overall architecture, data flow, Safe Action Model, deployment, failure handling |
| 01 | [`01_DECISION_BUNDLE_SPEC.md`](01_DECISION_BUNDLE_SPEC.md) | Decision Bundle format, export trigger, lifecycle |
| 02 | [`02_GPT_ADVISOR_SPEC.md`](02_GPT_ADVISOR_SPEC.md) | Context Pack consumption, summary pipeline, output contract, degraded mode |
| 03 | [`03_NTFY_NOTIFICATION_SPEC.md`](03_NTFY_NOTIFICATION_SPEC.md) | ntfy payload, priority, delivery failure handling |
| 04 | [`04_SECURITY_MODEL.md`](04_SECURITY_MODEL.md) | Auth/session model, read/write boundaries, secrets, audit logging |
| 05 | [`05_UI_SCREENS_SPEC.md`](05_UI_SCREENS_SPEC.md) | The 9 Console screens |
| 06 | [`06_IMPLEMENTATION_PLAN.md`](06_IMPLEMENTATION_PLAN.md) | Phased Sonnet implementation plan (C0–C6), Definition of Done |
| 07 | [`07_TEST_PLAN.md`](07_TEST_PLAN.md) | Unit/security/idempotency test coverage |

Related: [`docs/GPT_CONTEXT/`](../../GPT_CONTEXT/README.md) — the
version-controlled context pack the GPT Advisor reads.

## Governing constraints (non-negotiable)

- GPT remains advisory only; it has no code path to execute anything.
- Console can never execute an action directly — it may only write a
  bundle's `decision` field and its own audit log.
- The dispatcher (`core/dispatcher.py`) remains the sole execution
  authority.
- No public internet exposure — Tailscale `serve` only, never `funnel`.
- No Telegram. No emojis. No complex UI.

See [`CHANGELOG.md`](CHANGELOG.md) for revision history.
