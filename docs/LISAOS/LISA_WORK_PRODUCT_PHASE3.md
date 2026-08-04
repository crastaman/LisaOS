# LISA_WORK_PRODUCT_PHASE3 — Workforce Evidence Pipeline

**Phase:** 3 (LISA-I005) · **Baseline:** `LISA-I004-PHASE2-COMPLETE`
**Module:** `core/work_product.py` · **Tests:** `tests/test_work_product.py`

Answers the question LisaOS previously could not: **"what exactly did this worker
produce?"** — from deterministic evidence, not conversation history.

---

## Pipeline position

```
Mission → Classification → Planning → Validation → Dispatcher
        → Workforce Resolver → OpenClaw Bridge → Worker
        → Structured Work Product → Evidence Store → Human
```

Capture is an **executor wrapper** (`work_product_recording_executor`), the same
pattern as `ledger_recording_executor`. Consequences, all deliberate:

* no change to `core/dispatcher.py` or `core/openclaw_bridge.py`;
* **no parallel execution path** — the dispatcher remains the sole execution
  authority and capture is a passive observer around it;
* provenance is **inherited** from the inner executor, never invented;
* the inner `ExecutionResult` is returned **unmodified** — capture can neither
  pass nor fail a package, and a capture failure never breaks a dispatch batch.

Stack (innermost first): `real/simulated → capacity ledger → work-product capture`.

---

## The trust boundary

The only entity that knows what engineering happened is the worker, and the
worker is untrusted — the same problem Phase 2 solved for plans. A Work Product
is therefore split:

| Half | Source | Trust | Contents |
|---|---|---|---|
| **observed** | LisaOS, from git | authoritative | repo, branch, base/head commit, files changed, patch + sha256 |
| **declared** | the worker | untrusted, optional | summary, tests, risks, warnings, deferred |
| **discrepancies** | reconciliation | derived | where the two disagree |

**Observation wins. Disagreement is recorded, never resolved away.** A worker
cannot write into the observed half, and `declared` accepts only the keys in
`DECLARED_KEYS` — an attempt to declare `status` or `files_changed` is rejected,
so a worker cannot overwrite what LisaOS observes for itself.

Declarations are read from `work_products/declared/<package_id>.json`. Absence is
a recorded fact, not an error: the observed half stands alone.

---

## Attribution hazard (found in review)

A diff against the base commit cannot tell *who* changed a file or *when*. In a
repository that was already dirty before dispatch, that pre-existing work would
be credited to the worker. Capture therefore records the working-tree state
**before** execution and excludes those paths from `attributed_files_changed`.

* `files_changed` — the full, raw diff vs base (nothing is hidden)
* `attributed_files_changed` — what this execution is actually credited with
* `pre_existing_dirty` — what was already dirty, plus a discrepancy note
* `changed` — derived from **attributed** changes only

Untracked files cannot appear in a git diff; they are listed separately and
`patch_covers_untracked` is `false`. Stated, not hidden.

---

## Validation (fail closed)

`validate_work_product()` accumulates **every** violation and rejects the whole
artifact; nothing partial is ever stored or handed to review.

| Rule | Rejects |
|---|---|
| V1 | unknown `schema_version` |
| V2 | missing `package_id` / `work_product_id` |
| V3 | status outside `completed` / `failed` / `no_execution` |
| V4 | missing worker identity; missing `agent_id` when provenance is `worker-real` |
| V5 | malformed `observed`; `available=false` with no `capture_error` |
| V6 | malformed `files_changed`; `changed` contradicting attributed changes |
| V7 | changed files with no patch; unresolvable patch reference; **sha256 or size mismatch** |
| V8 | malformed test evidence (see below) |
| V9 | missing `created_at` |
| V10/V11 | unknown top-level keys; unpermitted declared keys |
| V12 | malformed `discrepancies` |

**Test evidence** (V8) requires `command`, `result ∈ {pass,fail,error,skipped}`,
non-negative `duration_seconds`, integer `passed`/`failed`/`skipped`, and an
`environment`; a declared `pass` carrying failures is rejected as incoherent.

---

## Storage and discovery

Under the existing `reports/lisa/orchestration/` tree — **no parallel ledger**:

```
work_products/<package>__<run>.json     the artifact
work_products/<package>__<run>.patch    the patch (sha256 + size in the artifact)
work_products/index.jsonl               append-only discovery index
work_products/declared/<package>.json   worker declaration (input)
```

`find_work_products(package_id=…, job_id=…, sprint=…, employee=…, agent_id=…)`
queries the index; all axes AND together. `bin/lisa` passes its intake
`request_id` as `--job-id` and a lexical `--sprint` hint, so evidence links back
to the mission that produced it. A corrupt index line never hides the rest.

The patch is stored beside the artifact rather than inside it, so artifacts stay
small and greppable while the diff stays byte-exact and hash-verified.

---

## Review handoff

`build_review_bundle(work_product)` assembles work product + patch text +
declared risks/tests/deferred + discrepancies into one structure, so a reviewer
never re-derives the implementation from conversation history or OpenClaw logs.
It **validates first** — an invalid Work Product cannot reach review — and large
patches are truncated with `patch_truncated: true`.

It performs **no interpretation**. Capture first, interpret later; summarisation
belongs to a later phase.

---

## CLI

```
lisa-dispatch run goal.json [--repo PATH] [--job-id ID] [--sprint ID]
                            [--no-work-product]
```

Capture is **on by default** (`--repo` defaults to the current directory) so
every executed package yields evidence.

---

## Honest limitations

* Attribution is **temporal, not causal**: a change made by anything else while a
  package runs is attributed to that package. Isolated per-worker checkouts would
  be needed for a stronger guarantee.
* Untracked files are listed but not in the patch.
* `declared` is only as truthful as the worker; LisaOS validates its *shape* and
  flags contradictions, it cannot verify that a declared test actually ran.
* Nothing yet writes declarations — wiring the declaration contract into worker
  briefs is Phase 4 work; today the observed half stands alone and the absence
  is recorded.
