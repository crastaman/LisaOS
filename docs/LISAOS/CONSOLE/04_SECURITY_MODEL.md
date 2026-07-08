# Security Model

**Status:** IMPLEMENTED (auth: Phase C4 — `console/auth.py`; hardening
and deployment readiness: Phase C5 — `console/config_check.py`,
`tests/test_console_security.py`, `tests/test_console_config.py`, this
doc, `09_DEPLOYMENT_GUIDE.md`). See `11_C5_SECURITY_REPORT.md` for the
formal Phase C5 security report and residual risk assessment.

**Known limitation, stated plainly**: no Tailscale installation exists
in the environment this phase was implemented in, so "validate against a
real tailnet" could not be performed end-to-end here — there is no
tailnet to test against. Everything at the application layer (header
parsing, allowlist matching, fail-closed behavior, audit logging) is
implemented and tested. The live `tailscale serve` deployment itself,
and a real cross-device request against it, require the actual Lisa
node and are a manual verification step for Roshan — see
`09_DEPLOYMENT_GUIDE.md`'s checklist.

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

**The critical deployment invariant**: this entire model trusts the
`Tailscale-User-Login` header completely. That trust is only valid
because `tailscale serve` strips any client-supplied version of that
header and injects its own, verified from the WireGuard peer identity —
a client cannot forge it *through* `tailscale serve`. If the Flask
process were ever bound to `0.0.0.0` instead of `127.0.0.1`, or run
without `tailscale serve` in front of it, **any client could set this
header to anything and grant themselves access** — the app-layer check
would still run, but the identity it's checking would no longer be
trustworthy. `09_DEPLOYMENT_GUIDE.md` states this as a hard requirement,
not a preference: bind `127.0.0.1` only, always.

**Hardening additions (Phase C5)**:
- Oversized header values are truncated before touching the allowlist
  comparison or the audit log — an attacker sending a huge
  `Tailscale-User-Login` value is denied outright (never matched) and
  cannot bloat `audit.jsonl` or, downstream, a bundle's `decision.by`
  field. `MAX_IDENTITY_LENGTH = 320` in `console/auth.py`.
  (`tests/test_console_security.py::TestMalformedHeaders`)
- Empty, whitespace-only, and unicode header values are all denied
  cleanly (no crash, no bypass).
  (`tests/test_console_security.py::TestMalformedHeaders`)
- Every identity value is written to the audit log via `json.dumps()`,
  which escapes quotes/backslashes/control characters automatically —
  no header value can corrupt the JSONL audit format.
  (`test_identity_value_safely_json_encoded_in_audit`)
- "Replay" (resubmitting a captured, identical `POST .../decide`
  request) is harmless by construction: the already-decided guard
  (Phase C4) rejects the second attempt outright, and
  `tests/test_console_security.py::TestReplay
  .test_replaying_the_same_decide_request_is_harmless` proves exactly
  one `decision_recorded` audit line results from two identical
  requests. There is no session token or nonce to replay in the first
  place — the only state that matters is the bundle's own
  `decision: null` check.

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

**Audit integrity model (Phase C5 review)**: every write site
(`console/auth.py`, `console/actions.py`, `core/decision_bundle_exporter
.py`, `advisors/gpt_advisor.py`, `advisors/notify.py` — five modules)
opens `audit.jsonl` exclusively in append (`"a"`) mode; there is no code
path anywhere in the repo that truncates or rewrites it, verified both
structurally (`test_every_source_module_opens_audit_in_append_mode_only`
greps every write site) and behaviorally
(`test_audit_file_only_ever_grows`, `test_earlier_audit_lines_never_change`
— repeated operations only ever extend the file; a prior line is
bit-for-bit identical after five more requests). This is a **filesystem-
permissions-and-code-review integrity model**, not a cryptographic one —
there is no hash chaining or signing, so a party with direct filesystem
write access (root, or Roshan's own shell) could still hand-edit the
file undetected. That is an accepted, proportionate limitation for a
single-operator local tool, not a hidden gap: cryptographic tamper-
evidence would be meaningful for a multi-party audit trail, not a
personal one where the operator and the trust boundary are the same
person.

## Threat model summary

| Threat | Mitigation | Status |
|---|---|---|
| Request from off-tailnet | `tailscale serve`, no `funnel` | **App-layer: N/A (network-layer control).** Config documented in `09_DEPLOYMENT_GUIDE.md`; live verification is a manual step (no tailnet in the dev environment) |
| Console bound to `0.0.0.0` or run without `tailscale serve` in front | Documented as the critical deployment invariant (see above) — the header check is only as trustworthy as the network path in front of it | **Documented; enforced by deployment procedure, not by app code** (an app-layer bind-address enforcement was considered and rejected as redundant — see `11_C5_SECURITY_REPORT.md`) |
| Request from another tailnet device | `Tailscale-User-Login` checked against the `LISA_CONSOLE_OWNER_IDENTITY` allowlist, else 403 | **Implemented, tested** |
| Oversized/malformed/empty/unicode header values | Truncated before comparison/audit; denied cleanly, no crash | **Implemented, tested** (Phase C5) |
| Replay of a captured request | Already-decided guard makes a repeated `decide` POST a no-op; GETs are naturally idempotent | **Implemented, tested** (Phase C5) |
| Secret leakage via logs/bundles/briefs/ntfy | Secrets confined to `.env`; never interpolated into any written artifact | **Implemented, tested** (Phase C2/C3, re-verified at Console integration level in Phase C5) |
| Console used to execute arbitrary action | Structurally impossible — Console can only write `decision` + audit log; zero core/engines imports, verified by grep | **Implemented, tested** |
| GPT output used to bypass governance | GPT recommendation is display-only; only Approve/Reject are wired to any effect, and Approve still only satisfies the existing governance gate, not a new one | **Implemented** |
| Double-decision race | Check-then-write guard on `decision: null`, not OS-level file locking (proportionate for a single-operator local tool — a known, documented limitation, not hidden) | **Implemented, tested** |
| Read outside allowed dirs | No generic file browser exists — every read is a named function against a fixed file set, not a path parameter | **Implemented by construction** |
| Audit log tampering | Append-only by construction (grepped + behaviorally tested); no cryptographic tamper-evidence (accepted limitation, see above) | **Implemented, tested; residual risk documented** |
| Silent misconfiguration (e.g. forgot to set the allowlist) | `bin/console-preflight` / `console.config_check.check_config()` surfaces it explicitly before deployment, distinguishing hard errors from graceful-degradation warnings | **Implemented, tested** (Phase C5) |
