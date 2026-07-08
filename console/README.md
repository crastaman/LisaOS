# console/

Lisa Console v1 Flask app (Phase C4). Server-side rendered only (Flask +
Jinja2), no SPA framework, no websocket, no client-side state beyond a
plain HTML form. See `docs/LISAOS/CONSOLE/05_UI_SCREENS_SPEC.md` for the
route inventory and `00_ARCHITECTURE.md` for the Safe Action Model this
app is built against.

## Observational and advisory only

- No import of `core.dispatcher`, `core.workforce_resolver`, or any
  `engines/*` module anywhere in this package (verified by grep).
- The only write path besides the audit log is `console/actions.py
  ::record_decision()` -- it writes exactly one field (`decision`) on an
  already-exported bundle. Nothing in this app can execute, schedule, or
  dispatch anything.
- No "Run", "Execute", "Retry", or "Force" route or button exists
  anywhere in `console/app.py` or `console/templates/`. The only two
  actions are Approve and Reject, both on the same form.

## Modules

- `auth.py` -- Tailscale-identity check (`Tailscale-User-Login` header
  against an explicit `LISA_CONSOLE_OWNER_IDENTITY` allowlist), audits
  every access attempt.
- `data.py` -- read-only access to bundles, briefs, notification
  markers, the audit log, and `registry/employees.yml`.
- `actions.py` -- the Safe Action Model: `record_decision()`.
- `app.py` -- the Flask app factory and all routes.
- `templates/`, `static/style.css` -- server-rendered HTML, minimal CSS.

## Running locally

Needs a project-local virtualenv (`console/requirements.txt`) -- Flask is
not, and should not become, a LisaOS core dependency:

```
python3 -m venv .venv
.venv/bin/pip install -r console/requirements.txt
PYTHONPATH="$HOME/Lisa" .venv/bin/python3 -c \
  "from console.app import create_app; create_app().run(host='127.0.0.1', port=8420)"
```

Deployment behind `tailscale serve` (never `funnel`) is Phase C5, not
implemented here.
