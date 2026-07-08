# Deployment Checklist — Lisa Console v1.0.0-alpha

Standalone quick-reference for closeout. Full context, commands, and
reasoning for each item: `09_DEPLOYMENT_GUIDE.md`.

## Before starting

- [ ] `.venv/` created, `console/requirements.txt` installed (Flask is
      `console/`-scoped — never install it into the system Python)
- [ ] `.env` populated (never committed) — at minimum
      `LISA_CONSOLE_OWNER_IDENTITY`
- [ ] `PYTHONPATH="$HOME/Lisa" python3 bin/console-preflight` exits `0`
      or `1` (not `2`)

## Starting the Console

- [ ] Process started, bound to `127.0.0.1` **only** — verify with
      `lsof -i :8420` (or equivalent) that nothing listens on a
      non-loopback address. This is the single most important item on
      this checklist — the entire auth model depends on it (see
      `04_SECURITY_MODEL.md`'s critical deployment invariant).

## Tailscale

- [ ] `tailscale serve --bg --https=443 http://127.0.0.1:8420` running —
      confirm with `tailscale serve status`
- [ ] **Never** `tailscale funnel` for this app
- [ ] `LISA_CONSOLE_BASE_URL` set to the real MagicDNS URL once known,
      Console restarted

## Live verification (manual — cannot be certified from a dev sandbox)

- [ ] From a **second device on the tailnet**: Console loads, correct
      identity recognized
- [ ] From a device **not** on the tailnet: URL is unreachable at the
      network layer (DNS/connection failure — not a 403)

## ntfy

- [ ] Topic generated (long random string), subscribed to on your phone
- [ ] Real test notification sent and received

## Ongoing

- [ ] Backup cadence decided for `reports/console/` (the only durable
      state Console owns)
- [ ] Upgrade procedure understood: `git pull` / merge → reinstall
      requirements → `console-preflight` → restart
- [ ] Rollback procedure understood: plain `git checkout`/`revert`, safe
      because bundles are immutable and schema-versioned
