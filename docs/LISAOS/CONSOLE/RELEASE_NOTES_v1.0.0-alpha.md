# Lisa Console v1.0.0-alpha — Release Notes

**Tag:** `v1.0.0-alpha`
**Date:** 2026-07-08

## What this is

A minimal private web app connecting Roshan, a GPT Advisor, and LisaOS:

```
Lisa works.
GPT compresses.
Roshan decides.
```

Lisa exports a self-contained Decision Bundle for a completed unit of
work; a GPT Advisor compresses it into a short Executive Brief; Roshan
reviews both in a private, Tailscale-only Console and records an
Approve/Reject decision with a required rationale. That's the entire
system — nothing in it can execute anything.

## What's new in this release

- **Decision Bundles** (`core/decision_bundle_exporter.py`) —
  self-contained, immutable, schema-versioned exports built from real
  LisaOS evidence (`reports/lisa/workforce_evidence.jsonl`), with an
  honest `gaps` field disclosing what couldn't be automatically
  populated.
- **GPT Advisor** (`advisors/`) — reads a Decision Bundle plus a
  version-controlled Context Pack (`docs/GPT_CONTEXT/`) and produces an
  Executive Brief: recommendation, confidence, key risks, suggested
  actions, missing information, escalation level. Fully degrades (never
  blocks, never crashes) if OpenAI is unavailable or unconfigured.
- **ntfy notifications** (`advisors/notify.py`) — a strict 7-field
  payload allowlist, bounded retry, duplicate suppression.
- **The Console** (`console/`) — 6 screens (Dashboard, Decision Bundles,
  Executive Briefs, Approvals, Workers, Audit), Tailscale-identity auth
  with an explicit allowlist, and exactly one action anywhere in the
  app: Approve or Reject, both requiring a written rationale.
- **Hardening** — negative-path tested (malformed/oversized/unicode
  headers, replay, audit integrity), configuration preflight
  (`bin/console-preflight`), a full deployment guide.
- **Approval handoff design** — a fully specified (not yet built)
  filesystem-artifact model for how an approved decision eventually
  reaches the dispatcher, with immutable provenance hashing and a
  6-state lifecycle (`pending → claimed → executing → completed/failed`,
  `pending → cancelled`).

## Why "alpha"

- The Approval Watcher (the component that would actually detect
  approvals and hand them to the dispatcher) is design-only — nothing
  consumes a decision automatically yet. Every Approve/Reject today is a
  durable, rationale-backed record; acting on it is still a manual step.
- Dispatcher intake (reading an Execution Request and feeding it into
  `core/dispatcher.py`) is future work, not part of this release.
- No live Tailscale deployment has been exercised — the auth logic is
  fully implemented and tested at the application layer, but real
  cross-device tailnet behavior hasn't been observed yet (no Tailscale
  installation existed where this was built).
- Operational usage experience doesn't exist yet — this is tested
  software, not yet battle-tested software.

None of these are correctness gaps in what's shipped; they're honest
boundaries on what "v1" actually covers.

## Upgrading / deploying

See `09_DEPLOYMENT_GUIDE.md` for the full guide. Quick start:

```
python3 -m venv .venv
.venv/bin/pip install -r console/requirements.txt
cp .env.example .env   # fill in LISA_CONSOLE_OWNER_IDENTITY at minimum
PYTHONPATH="$HOME/Lisa" python3 bin/console-preflight
```

## Breaking changes

None — this is the first release.

## Known issues

See `12_FINAL_IMPLEMENTATION_REPORT.md`'s "Known limitations" section
and `11_C5_SECURITY_REPORT.md`'s residual risk table.
