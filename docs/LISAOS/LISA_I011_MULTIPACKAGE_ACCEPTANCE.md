# LISA-I011 — Multi-Package Failure Acceptance

**Baseline:** `LISA-I010-PROVENANCE-COMPLETE` · **Date:** 2026-08-05
**Verdict:** pipeline behaves correctly under multi-package load with partial
failure. **Two findings**; one acceptance criterion **not met**.

No architecture was built or changed in this sprint.

---

## Mission and generated dependency graph

One command, one request id `e8ff3bac`:

```
bin/lisa "LISA-I011 multi-package acceptance …" --plan --dispatch      → exit 2
```

Exit 2 is the documented partial-failure code (per-package fail-closed), not a
pipeline failure.

```
  note-a ─┐
  note-b ─┼──> summary          (dependency chain)
  note-c  │                     (independent, parallel)
  fail-control                  (independent, fails closed at staffing)
```

| package | caps | mode | depends_on |
|---|---|---|---|
| `i011.note-a` | documentation | economy | — |
| `i011.note-b` | documentation | economy | — |
| `i011.note-c` | documentation | economy | — |
| `i011.summary` | documentation | economy | note-a, note-b |
| `i011.fail-control` | **architecture** | economy | — |

---

## Parallel execution evidence

| metric | value |
|---|---|
| wall clock | **46.44 s** |
| serial sum | **101.32 s** |
| speedup | **2.18×** |
| peak concurrent workers | **3** |
| main-executed packages | **0** |

Tick 0 shows `ready=4, in_flight=3, queue=1`: four packages were on the ready
frontier, three were admitted, and the fourth was held by the per-provider cap
(`max_per_provider=3`, all four eligible workers being `claude-haiku`). This is
the cap being respected, not starvation. `summary` stayed blocked until both
dependencies completed, then ran alone (19.0 s).

---

## Failure-path evidence — natural, not simulated

`i011.fail-control` failed **closed at staffing**, before any spend:

```
available: false
auth_result: "no_capable_employee"
reason: "no employee provides ['architecture'] within mode 'economy''s allowed roster"
```

The failure is genuine policy enforcement: `architecture` is held only by
`chief-architect`, which `economy` mode's roster excludes. Nothing in LisaOS
was edited to induce it. Plan validation correctly *passed* the package (P7
checks capability coverage, P9 checks the mode is known) and the workforce
resolver correctly *refused* to staff it.

**Isolation confirmed:** `completed=4, failed=1, blocked=0`. The failure
neither blocked nor corrupted any sibling; `summary` still ran.

---

## Successful-path evidence

All four completed packages produced their files
(`note-a.md`, `note-b.md`, `note-c.md`, `summary.md`), each staffed to
`operations-microtask-agent` → `claude-haiku` → agent `lisa-haiku`, all with
`execution_success=true`, `mismatch=false`, provenance `worker-real`.

## Evidence & declaration completeness matrix

| package | work product | status | declaration | valid | review bundle | synthesis |
|---|---|---|---|---|---|---|
| note-a | ✅ | completed | ✅ | ✅ | ✅ | EVIDENCE_COMPLETE |
| note-b | ✅ | completed | ✅ | ✅ | ✅ | EVIDENCE_COMPLETE |
| note-c | ✅ | completed | ✅ | ✅ | ✅ | EVIDENCE_COMPLETE |
| summary | ✅ | completed | ✅ | ✅ | ✅ | EVIDENCE_COMPLETE |
| **fail-control** | ❌ **none** | — | — | — | ❌ | ❌ **see DEFECT-3** |

All work products share the single request id `e8ff3bac`.
Ledger chronology (one request): `PLAN_READY → GOVERNANCE_CHECK_STARTED →
GOVERNANCE_CHECK_PASSED → DISPATCH_STARTED → DISPATCHED → DISPATCH_COMPLETED`.
Final governance scan: **clean**, 46 observed, 0 unacknowledged.

---

## DEFECT-3 — a package that fails at staffing produces no Work Product

**Observed:** `i011.fail-control` has a `workforce_evidence` record but **no
Work Product**, therefore no review bundle and no synthesis. The sprint
requires preserved evidence, review bundle and synthesis for the failing
package; only the first exists.

**Root cause:** work-product capture is an *executor wrapper*
(`work_product_recording_executor`). A package that fails in
`WorkforceResolver.resolve()` never reaches the executor, so the wrapper never
runs. Staffing failures are evidenced only in the dispatcher's own
`workforce_evidence.jsonl`.

**Consequence:** the operator-facing report layer is blind to unstaffable work.
`bin/lisa-report` can say nothing about a package that never ran, and a partial
failure is visible only by reading the raw dispatch JSON or evidence ledger.

**Recommended correction (NOT applied — out of scope):** emit a Work Product
with `status="no_execution"` for staffing failures. The status already exists
in the schema (`STATUS_NO_EXECUTION`) and is unused, which suggests the gap was
anticipated but never wired. This is a reporting-completeness gap, not a
governance hole: the failure was correctly refused, evidenced and surfaced.

---

## FINDING-4 — the declaration contract is not overridable by package text
### (acceptance criterion NOT met)

`i011.note-c` was a deliberate control: its description, carried faithfully by
the planner, said *"Do not write any declaration file for this package beyond
the note-c.md file itself."* **The worker wrote a valid declaration anyway.**

So the `EVIDENCE_INCOMPLETE` path was **not exercised live** in this run, and
the "one package with a missing declaration, reported honestly" criterion is
**not met**.

This is reported as a finding rather than retried, because the behaviour is
arguably *correct and desirable*: the contract is injected by LisaOS at the
capture boundary, and a work package cannot instruct a worker to skip producing
evidence. A package-level opt-out would be an evidence-suppression channel.

`EVIDENCE_INCOMPLETE` remains covered by hermetic unit tests
(`tests/test_synthesizer.py`); what is unproven is that it can arise from a
*live* worker. Provoking it would need a worker that genuinely fails to comply
— which cannot be arranged deterministically without editing LisaOS.

---

## Tests

| suite | result |
|---|---|
| focused (dispatcher, dependency graph, governance, evidence, synthesis, provenance) | OK |
| full regression | **849 passed**, 39 skipped |
| live OpenClaw calls during tests | **0** |

---

## Independent architectural review

* **Dispatcher remained the sole execution authority** — `main_completed=0`,
  `worker_completed=4`; every execution carried `worker-real` provenance.
* **Planner remained proposal-only** — it emitted a plan; validation accepted
  it; the planner never dispatched.
* **Synthesizer remained read-only** — reports were generated from bundles
  only; no evidence was mutated.
* **Governance remained deterministic and clean** — no violation from the
  planner run (provenance correlated), none from the four worker runs
  (work-product correlated), and the failed package produced no ungoverned
  activity because it never executed.
* **Evidence remained authoritative** — declarations were validated, not
  trusted; nothing was fabricated for the failed package.
* **Failed work never bypassed governance**, and successful work remained
  reviewable.
* **No parallel execution path appeared**; no manual intervention, no
  acknowledgement, no recovery command, no `--goal` fallback.
