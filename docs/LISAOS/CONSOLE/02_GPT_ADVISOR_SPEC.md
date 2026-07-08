# GPT Advisor Specification

**Status:** IMPLEMENTED (Phase C2) — `advisors/context_pack.py`,
`advisors/openai_client.py`, `advisors/gpt_advisor.py`,
`tests/test_context_pack.py`, `tests/test_openai_client.py`,
`tests/test_gpt_advisor.py` (34/34 passing). See
`docs/LISAOS/CONSOLE/examples/sample_brief_degraded.json` (real, generated
by the actual fail-closed path in this environment) and
`sample_brief_ok.json` (illustrative — no API credential exists in this
environment to produce a real success case).

## Advisory-only, verified not just asserted

Every module in `advisors/` has **zero imports of `core/` or `engines/`** —
confirmed by grep, not just claimed in a docstring. There is no code path
from this package into `core.dispatcher`, `core.workforce_resolver`, or
any `engines/*` module. Concretely:

- `advisors/context_pack.py` only opens files under `docs/GPT_CONTEXT/`.
- `advisors/openai_client.py` makes exactly one kind of outbound call
  (OpenAI Chat Completions) and touches no other system.
- `advisors/gpt_advisor.py` reads a bundle with plain `json.load()` and
  never opens it for writing. Its only write is a new file under
  `reports/console/briefs/`. It never writes a `decision` — that remains
  exclusively the Console's Safe Action Model (Phase C4).

`tests/test_gpt_advisor.py::TestGenerateBriefForBundleId
.test_reads_bundle_read_only_never_writes_to_it` makes this a proven
property, not a convention: it `chmod`s the bundle file and its directory
read-only before calling `generate_brief_for_bundle_id()` — if the module
ever attempted to open the bundle for writing, the test would fail with a
`PermissionError`.

## GPT Context Pack loader (`advisors/context_pack.py`)

Loads `docs/GPT_CONTEXT/NN_*.md` — matched by the regex `^(\d{2})_.*\.md$`,
i.e. `01_SYSTEM_ROLE.md` through `09_ARCHITECTURAL_CONSTRAINTS.md` today,
sorted numerically. **`README.md` and `CHANGELOG.md` are deliberately
excluded** — they're meta-documents (an index and a revision log), not
context content. (This is a small, deliberate deviation from the original
Phase C0 design note that said "plus README.md" — the real implementation
treats only numbered files as context.)

Cached in memory per directory, keyed by a signature of every numbered
file's mtime + size — cheap to check (a `stat()` per file, no content
read) on every call, and only re-reads file content when something
actually changed. `ContextPackError` is raised (not silently swallowed)
if the directory is missing or contains no numbered files — a missing
context pack is a configuration error, not something degraded mode should
paper over.

## OpenAI API integration layer (`advisors/openai_client.py`)

**Stdlib only** (`urllib.request`) — no external dependency. This repo
pins no Python dependencies at all; `tests/smoke_deepinfra.py` uses the
identical pattern against a different OpenAI-compatible endpoint, so this
follows established convention.

`call_chat_completion(system_prompt, user_prompt, model=None, ...)` calls
`POST https://api.openai.com/v1/chat/completions` with
`response_format: {"type": "json_object"}` and `temperature: 0`, and
returns the parsed JSON content dict.

**Security**:
- API key read once, from `LISA_CONSOLE_OPENAI_API_KEY` only — never a
  function parameter with a hardcoded fallback.
- **Fails closed before any network call** if the key is missing/empty
  (`AdvisorCredentialsError`), proven in
  `tests/test_openai_client.py::TestCredentialsFailClosed
  .test_missing_key_raises_before_any_network_call`, which asserts
  `urlopen` is never called.
- The key is used solely to build the `Authorization: Bearer ...` header.
  It is never interpolated into a log line, an exception message, a
  bundle, or a brief — verified in
  `test_key_never_appears_in_request_url_only_header`.
- HTTP error bodies are captured (truncated to 500 chars) for diagnostics,
  but request headers (including the key) are never echoed back.

**Failure categorization** — every category below maps directly to an
Executive Brief `degraded_category`:

| HTTP/transport condition | Category |
|---|---|
| `429` | `rate_limited` |
| `5xx` | `unavailable` |
| `400` with `context_length` in the error body | `context_overflow` |
| any other `4xx` | `invalid_response` |
| `URLError`/`TimeoutError` mentioning a timeout | `timeout` |
| any other `URLError` (connection refused, DNS, etc.) | `unavailable` |
| response body isn't valid JSON, missing `choices[0].message.content`, or content isn't a JSON object | `invalid_response` |

Model selection: `LISA_CONSOLE_OPENAI_MODEL` env var, falling back to
`advisors.openai_client.DEFAULT_MODEL`. A configuration value, not a
hardcoded architectural dependency — no branching logic anywhere checks
"is this model X" (Role Abstraction Principle,
`docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md`).

## Context assembly (`advisors/gpt_advisor.py`)

- **System message** = the full concatenated Context Pack text (which
  already begins with `01_SYSTEM_ROLE.md`'s instructions).
- **User message** = the full Decision Bundle, pretty-printed JSON,
  followed by explicit output-format instructions describing every
  required Executive Brief field, its type, and its allowed enum values.

Both are always the *whole* pack and the *whole* bundle — never a
curated subset — matching the "Lisa exports the whole bundle, GPT decides
relevance" principle from the original design brief.

## Executive Brief output contract

Schema `lisaos.console.executive_brief.v1`. Field names were revised in
Phase C2 to match the explicit requirements this phase was approved
against (superseding the C0-era `risk_flags`/`open_questions` naming):

| Field | Type | Notes |
|---|---|---|
| `brief_id` | string | `eb-<UTC date>-<8 hex>` |
| `schema` | string | `lisaos.console.executive_brief.v1` |
| `bundle_id`, `bundle_schema` | string | traceability back to the source bundle |
| `created_at` | string | ISO 8601 UTC |
| `status` | `"ok"` \| `"degraded"` | see degraded mode below |
| `model` | string \| null | the OpenAI model used, or `null` in a credentials-failure degraded brief |
| `headline` | string \| null | ≤140 chars |
| `summary` | string \| null | ≤6 sentences, grounded strictly in the bundle |
| `recommendation` | `"approve"` \| `"reject"` \| `"approve_with_changes"` \| `"needs_more_info"` \| null | **advisory only** — see constraints below |
| `confidence` | `"low"` \| `"medium"` \| `"high"` \| null | |
| `key_risks` | array of strings | |
| `suggested_actions` | array of strings | GPT's own suggestions — distinct from the bundle's `proposed_actions` |
| `missing_information` | array of strings | |
| `escalation_recommendation` | `{"level": "none"\|"recommended"\|"urgent", "reason": string\|null}` | |
| `degraded_category` | string \| null | `credentials`\|`unavailable`\|`timeout`\|`rate_limited`\|`invalid_response`\|`context_overflow`\|`partial_summary`, or `null` when `status == "ok"` |
| `degraded_reason` | string \| null | human-readable explanation |

### Explicit constraints on `recommendation` (enforced by construction, not just documented)

The Advisor **may recommend only**. It cannot approve, reject, execute,
mutate bundle state, write a decision, or invoke any Lisa runtime
function — there is no code path in `advisors/` capable of any of those.
`recommendation` is a text label the Console (Phase C4) may display; only
Roshan's Approve/Reject click in the Console can ever populate a bundle's
`decision` field (Safe Action Model, `00_ARCHITECTURE.md`).

## Brief persistence

`reports/console/briefs/<brief_id>.json`, written via `.tmp` +
`os.replace()` (same atomic pattern as bundles). Briefs are **not**
immutability-enforced like bundles: a retry after a degraded brief simply
produces a new `brief_id` rather than needing to overwrite anything, so
there's no scenario where overwrite protection is needed.

## Failure handling and degraded mode

Every required failure mode produces a **valid, schema-conformant,
persisted brief** with `status: "degraded"` — `generate_brief()` never
raises for an OpenAI-side failure:

- **Credentials unavailable** → fails closed before any network call →
  `degraded_category: "credentials"`.
- **API unavailable** (5xx, connection refused, DNS failure) →
  `"unavailable"`.
- **Timeout** → `"timeout"`.
- **Rate limiting** (429) → `"rate_limited"`.
- **Invalid responses** (malformed JSON, missing fields the transport
  layer can detect, non-object content) → `"invalid_response"`.
- **Context overflow** (400 with a context-length error) →
  `"context_overflow"`.
- **Partial summaries** (the API call succeeds and returns valid JSON,
  but `recommendation` or `confidence` — the two fields load-bearing
  enough that a Console display would be misleading without them — are
  missing or fail enum validation) → `"partial_summary"`. Non-critical
  fields (`key_risks`, `suggested_actions`, `missing_information`,
  `escalation_recommendation`) degrade individually to safe empty
  defaults *without* forcing the whole brief into degraded status, so a
  single malformed array doesn't discard an otherwise-usable
  recommendation.

**Degraded-mode guarantee, concretely**: a degraded brief still has
`bundle_id`/`bundle_schema` set, is still written to
`reports/console/briefs/`, and the bundle it was generated from is never
touched. Nothing in this module can make a bundle invalid, block Console
usage (once Phase C4 exists), or block a future Approve/Reject decision —
those all depend only on the bundle, which the Advisor never mutates.

## Trigger

Two entry points: `generate_and_write_brief(bundle, ...)` for an
already-loaded bundle dict, and `generate_brief_for_bundle_id(bundle_id,
...)` which reads `reports/console/bundles/<bundle_id>/bundle.json`
read-only. No automatic trigger exists yet in Phase C2 — matching Phase
C1's on-demand-only stance, since there is still no live job-state
machine to hook an automatic "bundle reached DRAFT" event off of. A CLI
wrapper was not part of this phase's approved deliverables and was not
added, to stay within scope.
