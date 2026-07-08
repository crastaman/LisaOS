# ntfy Notification Specification

**Status:** DESIGN APPROVED — not yet implemented (Phase C3)

## Hosting

Public ntfy.sh, one dedicated topic
(`https://ntfy.sh/<long-random-token>`, generated once, stored in
`LISA_CONSOLE_NTFY_TOPIC`, never committed), optionally with an
`LISA_CONSOLE_NTFY_TOKEN` access token on top, since ntfy.sh is public
infrastructure.

## Payload

Minimal — a pointer only, never bundle data:

- **Title**: `[LisaOS] <headline>` (or `<job_type> needs a decision` if
  the GPT summary failed)
- **Body**: `<recommendation> (<confidence>) — tap to review`
- **Click action**: `https://<tailscale-magicdns-name>/brief/<brief_id>`
  — only resolvable/reachable on the tailnet, so the URL is inert
  off-network and nothing sensitive needs to be in the ntfy payload
  itself.
- **Priority**: high when `risk_flags` is non-empty or `recommendation ==
  reject`, default otherwise.
- **Tags**: e.g. `robot` for automatic, `warning` for high-risk.

## Delivery

Sent by `advisors/notify.py`, the last pipeline step. Single attempt, no
retry storm. Delivery failure is audit-logged (`04_SECURITY_MODEL.md`)
but never blocks bundle/brief availability in the Console — Roshan can
always reach pending approvals by opening the Console directly.

## Future option (not v1)

Self-hosted ntfy on the tailnet is a documented, swappable alternative if
ntfy.sh's public-infrastructure exposure of headline/summary text becomes
unacceptable. Switching does not require any change to the Decision
Bundle or Executive Brief formats — only to `advisors/notify.py`'s target
URL.
