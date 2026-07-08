# Deployment Guide

**Status:** Phase C5. Written from `console/` and `advisors/`'s actual
implemented configuration surface — every env var and command below is
real, not aspirational. The one thing this guide **cannot** certify from
this environment: no Tailscale installation exists where this was
written, so the `tailscale serve` steps are correct per Tailscale's
documented behavior but have not been executed and observed here. Treat
the "Live verification" checkboxes in the checklist at the end as
mandatory, not optional.

## 1. Prerequisites on the Lisa node

- Python 3.10+ (this repo is developed against 3.14).
- A project-local virtualenv for Console — **never install Flask into
  the system Python**:
  ```
  cd ~/Lisa
  python3 -m venv .venv
  .venv/bin/pip install -r console/requirements.txt
  ```
- Tailscale installed and this machine already joined to your tailnet
  (`tailscale status` should show it). Console does not manage Tailscale
  enrollment — that's a one-time `tailscale up` done outside this repo.

## 2. Environment variables

All in `.env` (never committed — `.env.example` is the template).
Reference: `.env.example` in the repo root.

| Variable | Required | Purpose |
|---|---|---|
| `LISA_CONSOLE_OWNER_IDENTITY` | **Yes** | Comma-separated allowlist of `Tailscale-User-Login` values. Empty/unset = everyone denied. |
| `LISA_CONSOLE_OPENAI_API_KEY` | No (degrades) | Direct OpenAI API key for the GPT Advisor. Missing → every brief is `degraded`/`credentials`; bundles remain fully usable. |
| `LISA_CONSOLE_OPENAI_MODEL` | No | Defaults to `advisors.openai_client.DEFAULT_MODEL`. |
| `LISA_CONSOLE_NTFY_TOPIC` | No (degrades) | ntfy.sh topic (long random string). Missing → notifications fail closed with `not_configured`, no network attempt. |
| `LISA_CONSOLE_NTFY_TOKEN` | No | ntfy access token, sent only as an `Authorization` header. |
| `LISA_CONSOLE_NTFY_SERVER` | No | Defaults to `https://ntfy.sh`. Point at a self-hosted instance to migrate — the entire provider abstraction is this one variable. |
| `LISA_CONSOLE_BASE_URL` | No (cosmetic) | Your Tailscale MagicDNS URL, e.g. `https://lisa.<tailnet>.ts.net`. Missing → ntfy notifications omit the deep link. |

**Before starting the Console, always run**:
```
PYTHONPATH="$HOME/Lisa" python3 bin/console-preflight
```
Exit code `0` = clean, `1` = warnings only (still safe to run), `2` =
errors (fix before starting — almost always a missing
`LISA_CONSOLE_OWNER_IDENTITY`). This command needs no virtualenv (no
Flask dependency) — it can be run immediately after cloning.

## 3. Starting the Console

Local-only, bound to loopback — **never** `0.0.0.0` (see
`04_SECURITY_MODEL.md`'s critical deployment invariant):

```
cd ~/Lisa
PYTHONPATH="$HOME/Lisa" .venv/bin/python3 -c "
from console.app import create_app
create_app().run(host='127.0.0.1', port=8420)
"
```

This is Flask's development server — fine for a single-operator local
tool reached only over the tailnet, but if you want a slightly more
robust process (auto-restart on crash), see §6 (process management).

## 4. `tailscale serve` configuration

`tailscale serve` is what makes the `Tailscale-User-Login` header
trustworthy — it strips any client-supplied value and injects its own,
verified from the WireGuard peer identity. **Never use `tailscale
funnel`** (that exposes to the public internet, which contradicts every
design decision in this project).

```
tailscale serve --bg --https=443 http://127.0.0.1:8420
```

- `--bg` runs it in the background as a long-lived service.
- `--https=443` terminates TLS at the tailnet edge; your tailnet peers
  reach it at `https://<this-node's-MagicDNS-name>/`.
- Identity headers are enabled by default for `tailscale serve` — no
  extra flag needed; confirm with `tailscale serve status`.

Set `LISA_CONSOLE_BASE_URL` to that MagicDNS URL once you know it (`
tailscale status` or `tailscale serve status` shows it), then restart
the Console process so ntfy deep links resolve correctly.

To stop: `tailscale serve --https=443 off`.

## 5. ntfy configuration

1. Pick a long, random, hard-to-guess topic name (it's public
   infrastructure by default — treat the topic name itself as a secret).
   Generate one, e.g.: `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`
2. Set `LISA_CONSOLE_NTFY_TOPIC` to that value.
3. Optionally set up ntfy access-token auth for extra protection against
   topic guessing (see ntfy.sh's own docs for generating a token), and
   set `LISA_CONSOLE_NTFY_TOKEN`.
4. Subscribe to that topic in the ntfy mobile/desktop app.
5. Leave `LISA_CONSOLE_NTFY_SERVER` unset to use the public `https://
   ntfy.sh` relay, or point it at a self-hosted instance on your tailnet
   if you'd rather nothing (even headline text) leave the tailnet — see
   `03_NTFY_NOTIFICATION_SPEC.md`'s provider-abstraction note.

## 6. OpenAI configuration

1. Get an API key from platform.openai.com.
2. Set `LISA_CONSOLE_OPENAI_API_KEY` — **environment variable only,
   never in a committed file**.
3. Optionally set `LISA_CONSOLE_OPENAI_MODEL` to override the default.
4. No key at all is a fully supported, tested configuration — the
   Console runs in permanent degraded-brief mode and remains completely
   usable (Phase C2's core design goal).

## 7. Process management

Not yet automated (no launchd plist has been written in this repo). For
now, running it under a terminal multiplexer (`tmux`/`screen`) or a
simple wrapper script that restarts on exit is sufficient for a
single-operator tool. A proper `launchd` plist (macOS-native, matching
the Darwin host) is a reasonable follow-up, not blocking this phase.

## 8. Backup strategy

Everything Console writes lives under `reports/console/` (bundles,
briefs, notification markers, `audit.jsonl`) — this directory is
gitignored (matches the existing `reports/lisa/` convention: evidence
data is never committed) and is the **only** durable state Console owns.
Back it up like any other local data directory you care about:

```
tar czf lisa-console-backup-$(date +%Y%m%d).tar.gz -C ~/Lisa reports/console
```

Run this on whatever cadence matches how much you'd mind losing —
decisions and their rationale are the highest-value data in that tree.
There is no database to dump; it's all JSON/JSONL files.

## 9. Upgrade strategy

```
cd ~/Lisa
git pull                                    # or merge feature/lisa-console
.venv/bin/pip install -r console/requirements.txt   # pick up any new/bumped deps
PYTHONPATH="$HOME/Lisa" python3 bin/console-preflight  # confirm config still valid
# restart the Console process
```

Decision Bundles and Executive Briefs are schema-versioned
(`lisaos.console.decision_bundle.v1`, `lisaos.console.executive_brief
.v1`) — an upgrade that changes either schema bumps the version string;
older files on disk keep their old version string and this Console does
not attempt in-place migration. If a future version needs to read older
files, that reader must branch on the schema string rather than assume
compatibility (the same rule stated in `01_DECISION_BUNDLE_SPEC.md`'s
"Schema versioning" section).

## 10. Rollback strategy

Code rollback is ordinary git: `git checkout <previous-commit>` (or
`git revert`) and restart the process. Because bundles/briefs are
immutable-once-written (bundles) or additive (a new brief_id per
attempt, never an overwrite), rolling back the code never corrupts or
loses existing data — an older Console binary reading newer-schema data
it doesn't recognize is the only edge case, and the schema-versioning
discipline above (fail closed / degrade on an unrecognized schema string
rather than assume compatibility) is what protects against silently
misreading it.

To fully remove Console without touching LisaOS core: `rm -rf .venv`
(the virtualenv, entirely outside git) and `git checkout
fix/provider-resolution` (abandoning the `feature/lisa-console` branch,
which has touched nothing outside `console/`, `advisors/`, `core/
decision_bundle_exporter.py`'s audit addition, and
`docs/GPT_CONTEXT/`+`docs/LISAOS/CONSOLE/`).

## 11. Production deployment checklist

- [ ] `.venv/` created, `console/requirements.txt` installed
- [ ] `.env` populated (never committed) — at minimum
      `LISA_CONSOLE_OWNER_IDENTITY`
- [ ] `PYTHONPATH="$HOME/Lisa" python3 bin/console-preflight` exits `0`
      or `1` (not `2`)
- [ ] Console process started, bound to `127.0.0.1` only — **verify
      with `lsof -i :8420` or equivalent that nothing is listening on a
      non-loopback address**
- [ ] `tailscale serve --bg --https=443 http://127.0.0.1:8420` running
      — confirm with `tailscale serve status`
- [ ] **Live verification (manual, cannot be certified from this
      environment)**: from a second device on the same tailnet, confirm
      the Console loads at the MagicDNS URL and the correct identity is
      recognized
- [ ] **Live verification (manual)**: from a device *not* on the
      tailnet, confirm the URL is unreachable at all (DNS/connection
      failure, not a 403 — the network layer should refuse it before the
      app layer ever sees the request)
- [ ] `LISA_CONSOLE_BASE_URL` set to the real MagicDNS URL, Console
      restarted
- [ ] ntfy topic configured and subscribed to on your phone; send a
      real test notification (e.g. by generating one real Decision
      Bundle + brief + `send_notification()` call) and confirm it
      arrives
- [ ] Backup cadence decided and, ideally, automated (§8)
