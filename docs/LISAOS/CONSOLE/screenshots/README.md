# Screenshots

Real screenshots of the running Flask app (Phase C4), captured with
Playwright driving a headless Chromium against
`console.app.create_app()` bound to `127.0.0.1:8420`, with every request
carrying a `Tailscale-User-Login` header (simulating what `tailscale
serve` injects in production — Phase C5). Not mockups.

Demo data was generated through the real code paths
(`core.decision_bundle_exporter`, `advisors.gpt_advisor`,
`console.actions.record_decision`) — four Decision Bundles in different
states (pending with an "ok" brief, pending with a degraded brief,
approved, rejected) plus the real `registry/employees.yml` and
`reports/lisa/workforce_evidence.jsonl` for the Workers screen.

| File | Screen |
|---|---|
| `dashboard.png` | `/` — system overview, recent briefs, worker health, notification status |
| `bundles_list.png` | `/bundles` |
| `bundle_detail.png` | `/bundles/<id>` — evidence, recommendation, risk summary, audit references, raw JSON |
| `briefs_list.png` | `/briefs` |
| `brief_detail.png` | `/brief/<id>` (singular — matches the ntfy deep-link format from Phase C3) |
| `approvals_list.png` | `/approvals` — pending only |
| `approval_detail.png` | `/approvals/<id>` — the only screen with the Approve/Reject form |
| `workers.png` | `/workers` — read-only registry mirror + real participation counts |
| `audit.png` | `/audit` |
| `access_denied_403.png` | a request with no `Tailscale-User-Login` header |
