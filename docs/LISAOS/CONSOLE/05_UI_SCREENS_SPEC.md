# UI / Screens Specification

**Status:** IMPLEMENTED (Phase C4) — `console/app.py`, `console/templates/`,
`console/static/style.css`. 53/53 new tests passing. See
`docs/LISAOS/CONSOLE/screenshots/` for real screenshots and this doc's
route inventory (pulled directly from `app.url_map`, not transcribed).

Server-rendered Flask + Jinja2, no JS framework, no build step, no CDN
assets, no emojis, no websocket.

## Route inventory (verified against `app.url_map`)

| Route | Methods | Endpoint | Purpose |
|---|---|---|---|
| `/` | GET | `dashboard` | System overview, pending decisions, recent briefs, worker health, notification status |
| `/bundles` | GET | `bundles_list` | All Decision Bundles |
| `/bundles/<bundle_id>` | GET | `bundle_detail` | Evidence references, recommendation, risk summary, audit references, raw JSON |
| `/briefs` | GET | `briefs_list` | All Executive Briefs |
| `/brief/<brief_id>` | GET | `brief_detail` | **Singular** — matches `advisors.notify.build_payload()`'s `f"{base_url}/brief/{brief_id}"` deep-link format from Phase C3 exactly |
| `/approvals` | GET | `approvals_list` | **Pending decisions only** — bundles with `decision: null` |
| `/approvals/<bundle_id>` | GET | `approval_detail` | Brief + raw bundle + the Approve/Reject form |
| `/approvals/<bundle_id>/decide` | **POST** | `approval_decide` | The only POST route in the entire app |
| `/workers` | GET | `workers` | Read-only `registry/employees.yml` mirror + real participation counts |
| `/audit` | GET | `audit` | Append-only timeline tail |
| `/static/<path:filename>` | GET | `static` | Flask's built-in static handler (`style.css`) |

**`test_console_routes.py::TestNoExecutionCapableRoutes`** asserts this
structurally: no route rule contains "run", "execute", "retry", "force",
or "dispatch", and exactly one POST route exists in the whole app.

## Screen-by-screen

1. **Dashboard** (`/`) — bundle counts by decision state, brief counts by
   status, worker registration/activity counts, notification sent/
   failed/suppressed counts (from `audit.jsonl`), last 5 briefs.
2. **Decision Bundles** (`/bundles`, `/bundles/<id>`) — list + detail.
   Detail shows evidence source files + matched line counts, the linked
   brief's recommendation if one exists, risk summary (from the brief's
   `key_risks`), participating workers, `gaps`, and the full bundle as
   collapsible-scroll raw JSON.
3. **Executive Briefs** (`/briefs`, `/brief/<id>`) — headline,
   recommendation, confidence, key risks, suggested actions, missing
   information, escalation recommendation, degraded-mode status, and
   notification-sent status for that brief.
4. **Approvals** (`/approvals`, `/approvals/<id>`, `POST .../decide`) —
   pending only; the only screen with a real action. A required rationale
   textarea and two buttons, Approve and Reject — nothing else.
5. **Workers** (`/workers`) — id, department, seniority, capabilities,
   preferred model, recent assignment count. No control actions: `console/
   data.py::list_workers()` has no write path, and the route has no POST
   method.
6. **Audit** (`/audit`) — tails `reports/console/audit.jsonl` directly,
   newest first: `bundle_created`, `brief_generated`/
   `brief_generation_failed`, `ntfy_sent`/`ntfy_failed`/
   `ntfy_duplicate_suppressed`, `decision_recorded`, `access_granted`/
   `access_denied`.

## Design constraints (verified, not just followed)

- No emojis anywhere in templates or copy.
- No client-side framework or JS beyond the browser's native HTML form
  submission — `console/templates/` contains zero `<script>` tags.
- Plain CSS (`console/static/style.css`), system font stack, no external
  CDN assets — nothing in any template references an external origin.
- `/workers` and `/audit` (and every bundle/brief detail view) are
  strictly read-only: no edit forms, no delete buttons.
- The only two buttons that do anything anywhere in the Console are
  **Approve** and **Reject**, both on `/approvals/<bundle_id>` — proven
  by `test_only_one_post_route_exists_and_it_is_decide`.
