# advisors/

GPT Advisor package for Lisa Console. Advisory-only by construction — this
package must never import `core/dispatcher.py` or any `engines/*` module.
See `docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md` and
`docs/LISAOS/CONSOLE/02_GPT_ADVISOR_SPEC.md`.

## Status

Phase C3 implemented. Zero imports of `core/` or `engines/` anywhere in
this package (verified by grep, not just asserted).

## Modules

- `context_pack.py` — loads `docs/GPT_CONTEXT/NN_*.md`, cached,
  mtime-invalidated.
- `openai_client.py` — stdlib-only (`urllib`) OpenAI Chat Completions
  call. Fails closed if `LISA_CONSOLE_OPENAI_API_KEY` is unset.
- `gpt_advisor.py` — Context Pack + full Decision Bundle → Executive
  Brief, with full degraded-mode coverage. Reads bundles read-only, never
  mutates one, never writes a `decision`.
- `notify.py` — Executive Brief → ntfy push notification, via a strict
  payload allowlist (nothing but `brief_id`/`headline`/
  `recommendation_summary`/`confidence`/`priority`/`timestamp`/
  `console_deep_link` ever reaches the wire). Retry with backoff,
  duplicate suppression, audit logging. Fully decoupled from
  `gpt_advisor.py` — neither module imports the other.

## Planned (not yet implemented)

- Phase C4 (Flask Console) is a separate top-level `console/` package,
  not part of `advisors/`.
