# Security Model

**Status:** DESIGN APPROVED — not yet implemented (auth: Phase C4, hardening: Phase C5)

## Authentication / session model

No password, no login form, no session cookie. Deployment uses
`tailscale serve https / http://127.0.0.1:<port>` with Tailscale identity
headers enabled, so every request Flask receives already carries
`Tailscale-User-Login`. A single `before_request` hook checks that header
equals the one configured owner login
(`LISA_CONSOLE_OWNER_IDENTITY` in `.env`) and returns 403 otherwise.
Because `tailscale serve` (never `funnel`) is used, no public listener
ever exists — this satisfies "no public internet exposure" without any
auth code to maintain.

## Boundaries

- **Read scope**: Console may read only `reports/`, `registry/`, `docs/`,
  `jobs/` (packets) — never WBS paths
  (`docs/LISAOS/REPOSITORY_BOUNDARIES.md`).
- **Write scope**: Console writes only a bundle's `decision` field (via
  the Safe Action endpoint) and its own audit log. It never edits
  registries, other job-packet fields, or any core module's output.
- **Secrets**: `LISA_CONSOLE_OPENAI_API_KEY`, `LISA_CONSOLE_NTFY_TOPIC`,
  `LISA_CONSOLE_NTFY_TOKEN` live in `.env` only (extends
  `.env.example`), never logged, never included in bundles, briefs, or
  ntfy payloads.
- **Network egress**: exactly two external calls exist anywhere in the
  system — OpenAI API (bundle text goes here) and ntfy.sh (headline/
  summary text only). Both explicit and auditable; ntfy is swappable to
  self-hosted later without touching the Decision Bundle/Brief formats.
- No Telegram, no other bot/webhook integrations.
- GPT is advisory-only **by construction** — the Advisor module has no
  import path to the dispatcher/engines.

## Audit logging

New `reports/console/audit.jsonl`, following the exact append-only JSONL
convention already used for `governance_violations.jsonl` /
`governance_acknowledgements.jsonl`. One line per:

- bundle exported
- brief generated or failed
- ntfy sent or failed
- approval-detail page view (lightweight — "was this ever looked at")
- every Approve/Reject decision (actor identity, `bundle_id`, choice,
  note, timestamp)

The `/audit` screen tails this file — no separate database, matching the
JSONL-first convention already established in the repo.

## Threat model summary (for Phase C5 hardening)

| Threat | Mitigation |
|---|---|
| Request from off-tailnet | Impossible by construction — `tailscale serve`, no `funnel` |
| Request from another tailnet device | `Tailscale-User-Login` header checked against `LISA_CONSOLE_OWNER_IDENTITY`, else 403 |
| Secret leakage via logs/bundles/briefs/ntfy | Secrets confined to `.env`; never interpolated into any written artifact |
| Console used to execute arbitrary action | Structurally impossible — Console can only write `decision` + audit log; no shell/engine/dispatcher import path |
| GPT output used to bypass governance | GPT recommendation is display-only; only Approve/Reject buttons are wired to any effect, and Approve still only satisfies the existing governance gate, not a new one |
| Double-decision race | Compare-and-swap guard on `decision: null` |
| Read outside allowed dirs (e.g. `/reports` path traversal) | Read scope hard-restricted to `reports/`, `docs/LISAOS/`; reject anything resolving outside |
