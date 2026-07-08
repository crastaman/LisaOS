# GPT Advisor Specification

**Status:** DESIGN APPROVED — not yet implemented (Phase C2)

## Package

New top-level package `advisors/` (parallel to `agents/`).

## Context Pack

`advisors/context_pack.py` loads every file in `docs/GPT_CONTEXT/`
(`01_SYSTEM_ROLE.md` through `09_ARCHITECTURAL_CONSTRAINTS.md`, plus
`README.md`) in numeric order, cached in memory, re-read if any file's
mtime changes. See `docs/GPT_CONTEXT/README.md` for the full file list and
the hard rule: this pack is the entire substitute for ChatGPT
conversational memory. If it isn't written there, the Advisor cannot know
it.

## Pipeline

1. Load the Context Pack (all files, always — never a subset).
2. Load one Decision Bundle in full (never a subset).
3. Compose one prompt: system role (`01_SYSTEM_ROLE.md`) + context pack
   body + bundle JSON (pretty-printed) + explicit structured-output
   schema.
4. Call the OpenAI API directly (`LISA_CONSOLE_OPENAI_API_KEY` env var
   only, never committed — see `.env.example`) with structured output,
   requesting:

```json
{
  "brief_id": "...",
  "bundle_id": "...",
  "headline": "<=140 chars",
  "summary": "<=6 sentences",
  "recommendation": "approve | reject | approve_with_changes | needs_more_info",
  "confidence": "low | medium | high",
  "risk_flags": ["..."],
  "open_questions": ["..."]
}
```

5. Write to `reports/console/briefs/<brief_id>.json`, linked to
   `bundle_id`.

## Constraints

- Advisory data only. The `advisors/` package has **no import path** to
  `core/dispatcher.py` or `engines/*` — it is structurally incapable of
  executing anything, not just instructed not to. See
  `docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md`.
- No hardcoded model coupling: the specific OpenAI model called is a
  configuration value (role: CTO/Auditor per the Role Abstraction
  Principle), swappable without touching this spec, the Decision Bundle
  format, or the Executive Brief format.

## Degraded mode

On any API failure, timeout, or malformed response: the brief is marked
`status: "failed"`. The Console still shows the raw, unsummarized bundle.
ntfy still fires, with a degraded-mode note ("GPT summary unavailable —
raw bundle ready for review"). GPT being unavailable never blocks
Roshan's ability to see and decide.

## Trigger

Invoked immediately after a bundle reaches `DRAFT` — either the same
export step, or a lightweight watcher (implementation detail decided in
Phase C2).
