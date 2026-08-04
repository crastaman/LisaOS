# LISA_DECLARATION_CONTRACT_PHASE4 — Worker Declaration Contract

**Phase:** 4 (LISA-I006) · **Baseline:** `LISA-I005-PHASE3-COMPLETE`
**Module:** `core/work_product.py` · **Tests:** `tests/test_work_product.py`

Phase 3 made LisaOS's *observed* evidence authoritative. Phase 4 activates the
complementary *declared* evidence: what the worker believes it produced.

**Declarations are evidence, not truth.**

---

## Flow

```
… Dispatcher → Workforce Resolver → OpenClaw Bridge → Worker
   → Observed Work Product → Worker Declaration → Reconciliation
   → Validated Review Bundle
```

The contract reaches workers from the **capture wrapper** — the only place that
sees every WorkPackage on its way to execution without touching the planner,
dispatcher or bridge (all out of scope). `augment_brief()` appends the contract
to a **copy** of the package, so the dependency graph's own objects are never
mutated and scheduling, retries and evidence still see the original brief. If
augmentation fails for any reason the original brief is dispatched unchanged —
a brief that cannot be augmented must still execute.

Disable per-dispatch with `work_product_recording_executor(..., declare=False)`.

---

## Declaration schema (`lisa-worker-declaration/1`)

Written by the worker to `work_products/declared/<package_id>.json`.

| Field | Type | Required |
|---|---|---|
| `summary` | string | **yes** |
| `tests` | list of test-evidence objects | no |
| `risks` / `warnings` / `deferred` / `assumptions` | list of strings | no |
| `notes` | string | no |
| `schema_version` | string | no (validated when present) |

Test evidence: `command`, `result ∈ {pass,fail,error,skipped}`,
`duration_seconds`, `passed`, `failed`, `skipped`, `environment`.

### Forbidden — LisaOS-owned observations

A worker may declare only what LisaOS cannot observe. These are **rejected**,
and the rejection names the reason:

`files_changed` · `patch` / `patch_path` / `patch_sha256` · commit hashes
(`commit`, `base_commit`, `head_commit`) · `repo` / `repository` / `branch` /
`changed` · `status` / `execution_status` / `success` · `runtime` / `model` /
`provider` / `agent_id` / `worker` / `employee` / `run_id` / `provenance` /
`tokens` · timestamps · `work_product_id` / `package_id` / `observed` /
`discrepancies` / `context`.

They are enumerated explicitly rather than left to the unknown-key rule, so a
rename of a permitted key can never silently open a hole for one of them.

The contract text handed to workers is **generated from these constants**, so
the contract a worker is given and the contract LisaOS enforces cannot drift.

---

## Validation (fail closed)

`validate_declaration()` returns **every** violation; a declaration is never
silently repaired or partially accepted.

| Rule | Rejects |
|---|---|
| D0 | not a JSON object |
| D1 | forbidden (observed) fields |
| D2 | unknown keys |
| D3 | missing/blank required `summary` |
| D4 | unknown `schema_version` |
| D5 | malformed `tests` |
| D6 | malformed string lists / `notes` |

A rejected declaration is **not stored** as `declared` — but its rejection is
recorded, because a worker that reports badly is itself a fact a reviewer needs.
Every Work Product carries:

```json
"declaration": {"present": true, "valid": false, "errors": ["D1: …"],
                "schema_version": "lisa-worker-declaration/1"}
```

Work Product rule **V13** enforces that outcome, including the invariant that
`declared` content may only be present when `declaration.valid` is true.

---

## Reconciliation

Deterministic; observation always authoritative; nothing discarded. Produces
**structured** discrepancies (`code`, `severity`, `detail`, plus context):

| Code | Severity | Meaning |
|---|---|---|
| `DECLARATION_INVALID` | conflict | declaration violated the contract |
| `DECLARATION_MISSING` | warning | no declaration written |
| `SUMMARY_WITHOUT_CHANGE` | warning | summary but no attributed change |
| `CHANGE_WITHOUT_TESTS` | warning | files changed, no test evidence |
| `DECLARED_TEST_FAILURES` | warning | worker declared failing tests |
| `WORK_DEFERRED` | info | worker declared deferred work |
| `PRE_EXISTING_DIRT` | info | repo already dirty before execution |
| `UNTRACKED_NOT_IN_PATCH` | info | untracked files absent from the patch |

`SUMMARY_WITHOUT_CHANGE` is deliberately a **warning, not a conflict**:
read-only packages (audits, reviews, analysis) legitimately summarise work
without changing anything, and since a worker cannot declare `files_changed`,
structure alone cannot distinguish the two. `conflict` is reserved for
unambiguous contract violations so the severity keeps its meaning.

Plain-string discrepancies from Phase 3 artifacts remain readable.

---

## Review bundle

Reviewers receive all four required views, and never need to rediscover the
implementation:

* **observed** evidence — `change` (repo, branch, base/head commit, files,
  patch text + sha256, attribution, pre-existing dirt)
* **declared** evidence — summary, tests, risks, warnings, deferred (verbatim)
* **discrepancies** — structured, with severity
* **validation outcome** — `declaration.present / valid / errors`

`build_review_bundle()` still validates first (an invalid Work Product cannot
reach review) and still performs **no interpretation**.

---

## Honest limitations

* A declaration is only as truthful as the worker. LisaOS validates its *shape*
  and flags contradictions with observation; it cannot verify that a declared
  test actually ran.
* Nothing enforces that a worker writes a declaration — absence is recorded as
  `DECLARATION_MISSING`, not punished. Making declarations mandatory for
  engineering packages is a policy decision, not implemented here.
* The contract lengthens every brief by a fixed block.
* Declarations are keyed by `package_id` alone, so a re-run of the same package
  reads a stale declaration unless the worker overwrites it.
