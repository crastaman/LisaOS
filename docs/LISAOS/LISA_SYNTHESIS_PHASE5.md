# LISA_SYNTHESIS_PHASE5 — Deterministic Evidence Synthesis

**Phase:** 5 (LISA-I007) · **Baseline:** `LISA-I006-PHASE4-COMPLETE`
**Module:** `core/synthesizer.py` · **CLI:** `bin/lisa-report` · **Tests:** `tests/test_synthesizer.py`

Converts validated review bundles into human-readable engineering reports.

**This is not an LLM and not a summariser.** It contains no model call, no
heuristic and no judgement of engineering quality. It assembles evidence that
already exists and labels where every statement came from.

---

## Position

```
… Worker → Observed Work Product → Worker Declaration → Validation
   → Review Bundle → Deterministic Synthesizer → Operator Report
```

The review bundle is the **single source of truth**. The synthesizer has no
code path to OpenClaw conversations, model transcripts, chat/prompt history or
raw worker output, and imports nothing that does. It is read-only: inputs are
deep-copied, so a report can neither mutate nor alias live evidence.

---

## Four structural prohibitions

| Never | Instead |
|---|---|
| **infers** | every statement is copied or counted out of the bundle |
| **invents** | absent evidence produces a `MISSING` statement |
| **suppresses** | every discrepancy in the bundle reaches the report |
| **repairs** | contradictions print as `CONFLICT` with both sides intact |

---

## Evidence labels (architectural — never merged)

| Label | Meaning |
|---|---|
| `OBSERVED` | LisaOS derived it; authoritative |
| `DECLARED` | the worker claimed it; untrusted |
| `VERIFIED` | a claim LisaOS independently confirmed (e.g. patch sha256) |
| `UNVERIFIED` | a claim LisaOS has no means to confirm (e.g. declared tests) |
| `CONFLICT` | observation and declaration disagree |
| `MISSING` | the evidence does not exist |

Every statement carries exactly one label plus a `source` — a dotted path into
the bundle — so any line of a report can be checked against its evidence. A
statement without a traceable source raises rather than rendering.

---

## Report schema (`lisa-synthesis-report/1`)

```
schema_version, package_id, work_product_id,
execution: {status, worker, context},
section_order: [...12 keys...],
sections: { <key>: { statements: [{label, text, source}], ...structured data } }
```

Twelve sections, fixed order: executive summary · work completed · observed
changes · worker declarations · validation outcome · structured discrepancies ·
tests observed · tests declared · risks · deferred work · review outcome ·
outstanding uncertainties.

`render_report()` produces plain text; `report_to_json()` produces stable
sorted-key JSON for diffing and archival.

### "Tests observed" is always MISSING

LisaOS observes no test execution. That section always reports the absence
explicitly rather than quietly reusing the worker's declared tests — which is
precisely the substitution this architecture exists to prevent. Declared tests
are labelled `UNVERIFIED`, never `VERIFIED`.

---

## Review outcome

A classification of the **evidence state**, by published rules — not an
approval and not a quality judgement (approvals are out of scope):

```
EXECUTION_FAILED     if execution status is not 'completed'
CONFLICTS_PRESENT    if any discrepancy has severity 'conflict'
EVIDENCE_INCOMPLETE  if no valid worker declaration exists
EVIDENCE_COMPLETE    otherwise
```

The rules are printed with the outcome so a reader can re-derive it.

---

## Determinism guarantees

Identical bundles produce **byte-identical** reports. There is deliberately no
`generated_at`, no uuid, no run counter and no other hidden state — the report
is a pure function of the bundle. Any collection derived from a set is sorted
before output. A test asserts the report contains no timestamp-shaped key,
because a timestamp here would silently destroy the guarantee the phase exists
to provide.

---

## CLI

```
lisa-report <package_id> [--job-id ID] [--sprint ID] [--store PATH] [--json] [--all]
lisa-report --artifact <work-product.json> [--json]
```

Exit codes: `0` report produced · `2` usage · `3` no matching work product ·
`4` evidence failed validation (**fail closed — no report is produced**).

---

## Honest limitations

* A report is only as good as its evidence: the synthesizer faithfully renders
  a thin declaration as a thin report.
* `UNVERIFIED` is a large category — every declared test, risk and assumption
  sits there, and nothing in LisaOS can promote them.
* The disposition is mechanical; `EVIDENCE_COMPLETE` means the evidence is
  present and coherent, **not** that the work is good.
* Rendering is plain text only; no HTML/markdown renderer is provided.
