# UI / Screens Specification

**Status:** DESIGN APPROVED — not yet implemented (Phase C4)

Server-rendered Flask + Jinja2, no JS framework, no build step, no CDN
assets, no emojis.

| Route | Purpose | Actionable? |
|---|---|---|
| `/` | Dashboard: counts of jobs by status, pending approvals, latest briefs | No |
| `/jobs` | Table from job packets, filterable by status | No |
| `/jobs/<job_id>` | One job's detail, links to its bundle(s)/brief(s) | No |
| `/workers` | Read-only mirror of `registry/employees.yml` | No |
| `/approvals` | Bundles with `decision: null`; headline/recommendation/confidence per row | Links only |
| `/approvals/<bundle_id>` | Full Executive Brief + raw bundle (collapsible JSON) | **Yes — Approve / Reject** |
| `/brief/<brief_id>` | ntfy deep-link target; same content as approval detail | **Yes — Approve / Reject** |
| `/reports` | Read-only browser scoped strictly to `reports/` and `docs/LISAOS/` | No |
| `/audit` | Tails the Console's own audit JSONL, newest first | No |

## Design constraints

- No emojis anywhere in templates or copy.
- No client-side framework; at most a few lines of vanilla JS for a
  confirm-dialog on Approve/Reject.
- Plain CSS, system font stack, no external CDN assets.
- `/reports` and `/workers` are explicitly read-only in v1 — no edit
  forms, no delete buttons, no arbitrary filesystem access outside their
  scoped roots.
- The only two buttons that do anything anywhere in the Console are
  **Approve** and **Reject**, both on `/approvals/<bundle_id>` and
  `/brief/<brief_id>` (same underlying template).
