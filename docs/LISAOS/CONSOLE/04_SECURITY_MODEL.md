# Security Model

**Status:** IMPLEMENTED (auth: Phase C4 — `console/auth.py`; deployment
hardening: Phase C5, not yet started)

## Authentication / session model

No password, no login form, no session cookie. Deployment (Phase C5,
not yet implemented) will use `tailscale serve https / http://127.0.0.1:
<port>` with Tailscale identity headers enabled, so every request Flask
receives carries `Tailscale-User-Login`. `console/auth.py::init_app()`
registers a `before_request` hook (`check_access()`) that checks that
header against an **explicit allowlist** —
`LISA_CONSOLE_OWNER_IDENTITY`, parsed as a comma-separated set via
`allowed_identities()` (supports more than one approved identity, per
the Phase C4 explicit requirement) — and aborts 403 otherwise. An unset
or empty allowlist means the set is empty, so **every** request is
denied until it's configured: fail closed, never fail open. Because
`tailscale serve` (never `funnel`) will be used, no public listener will
ever exist — this satisfies "no public internet exposure" without any
password/session code to maintain. **Every access attempt, granted or
denied, is audited** (`access_granted`/`access_denied` events) —
verified by `test_console_auth.py::TestCheckAccess
.test_every_request_is_audited_including_repeated_ones`.

## Boundaries

- **Read scope**: Console reads only `reports/console/**` (its own
  bundles/briefs/notifications/audit), `registry/employees.yml`, and
  `reports/lisa/workforce_evidence.jsonl` (for worker participation
  counts). No generic filesystem browser exists — there is no `/reports`
  or `/docs` route; every read in `console/data.py` goes through a named
  function reading a specific, fixed set of files. Never WBS paths
  (`docs/LISAOS/REPOSITORY_BOUNDARIES.md`).
- **Write scope**: Console writes only a bundle's `decision` field (via
  `console/actions.py::record_decision()`) and its own audit log
  (`console/auth.py`, `console/actions.py`). It never edits registries,
  other bundle fields, briefs, or any core module's output.
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

`reports/console/audit.jsonl`, following the exact append-only JSONL
convention already used for `governance_violations.jsonl` /
`governance_acknowledgements.jsonl`. Implemented across three phases —
one line per:

- `bundle_created` (Phase C1, `core/decision_bundle_exporter.py`)
- `brief_generated` / `brief_generation_failed` (Phase C2,
  `advisors/gpt_advisor.py`)
- `ntfy_sent` / `ntfy_failed` / `ntfy_duplicate_suppressed` (Phase C3,
  `advisors/notify.py`)
- `access_granted` / `access_denied` (Phase C4, `console/auth.py`) —
  every access attempt, covering "was this page ever looked at" as a
  side effect of auditing all access, not as a separate event type
- `decision_recorded` (Phase C4, `console/actions.py`) — actor identity,
  `bundle_id`, choice, note, timestamp

The `/audit` screen tails this file directly — no separate database,
matching the JSONL-first convention already established in the repo.

## Threat model summary

| Threat | Mitigation | Status |
|---|---|---|
| Request from off-tailnet | `tailscale serve`, no `funnel` | Phase C5 (deployment, not yet done) |
| Request from another tailnet device | `Tailscale-User-Login` checked against the `LISA_CONSOLE_OWNER_IDENTITY` allowlist, else 403 | **Implemented, tested** |
| Secret leakage via logs/bundles/briefs/ntfy | Secrets confined to `.env`; never interpolated into any written artifact | **Implemented, tested** (Phase C2/C3) |
| Console used to execute arbitrary action | Structurally impossible — Console can only write `decision` + audit log; zero core/engines imports, verified by grep | **Implemented, tested** |
| GPT output used to bypass governance | GPT recommendation is display-only; only Approve/Reject are wired to any effect, and Approve still only satisfies the existing governance gate, not a new one | **Implemented** |
| Double-decision race | Check-then-write guard on `decision: null`, not OS-level file locking (proportionate for a single-operator local tool — a known, documented limitation, not hidden) | **Implemented, tested** |
| Read outside allowed dirs | No generic file browser exists — every read is a named function against a fixed file set, not a path parameter | **Implemented by construction** |
