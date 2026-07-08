# advisors/

GPT Advisor package for Lisa Console. Advisory-only by construction — this
package must never import `core/dispatcher.py` or any `engines/*` module.
See `docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md` and
`docs/LISAOS/CONSOLE/02_GPT_ADVISOR_SPEC.md`.

## Status

Phase C0 scaffolding only. No runtime behavior yet.

## Planned modules (not yet implemented)

- `context_pack.py` (Phase C2) — loads `docs/GPT_CONTEXT/*.md`, cached,
  mtime-invalidated.
- `gpt_advisor.py` (Phase C2) — Context Pack + Decision Bundle → Executive
  Brief via the OpenAI API, with degraded-mode fallback.
- `notify.py` (Phase C3) — Executive Brief → ntfy push notification.
