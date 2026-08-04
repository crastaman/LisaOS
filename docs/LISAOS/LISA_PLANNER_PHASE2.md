# LISA_PLANNER_PHASE2 — Natural Language Mission Planner

**Phase 2 — Natural Language Mission Planner**
Module: `core/planner.py` (Phase 2 section) | Entry: `bin/lisa --plan`

---

## Core Principle: THE LLM PROPOSES, LISA DECIDES

The LLM proposer is outside Lisa's trust boundary.  Nothing it returns may
reach the dispatcher without passing every validation gate in `validate_plan()`.
The proposer is treated as an untrusted, non-deterministic data source; the
schema, validation rules, and rejection behaviour are all deterministic.

**Honest limitation:** The LLM proposer is not deterministic.  Two calls with
the same mission may return different plans.  The schema, validation, and
rejection behaviour *are* deterministic — a plan either satisfies all 12 rules
or it does not, with no partial acceptance.

---

## Pipeline

```
mission
  → task_classifier (GOVERNED)
  → PROPOSER  [untrusted LLM — outside trust boundary]
      ↓ raw text
  → parse_plan_text()   [tolerant JSON extractor]
      ↓ list
  → validate_plan()     [deterministic governance gate — all 12 rules]
      ↓ normalized package list
  → write bare-JSON artifact  (reports/lisa/orchestration/plans/<id>.json)
  → (optionally) existing dispatcher  (bin/lisa-dispatch)
```

If `validate_plan()` rejects the plan, **no artifact is written** and **no
dispatch is attempted** — fail closed.

---

## Validation Rules (P1 – P12)

All errors are collected before raising; `PlanValidationError.errors` contains
every violation found, never just the first.

| # | Rule |
|---|------|
| P1 | Top level is a `list`; length ≥ 1 and ≤ `MAX_PACKAGES` (20). |
| P2 | Every element is a `dict`. |
| P3 | `id`: present, `str`, matches `^[a-z0-9][a-z0-9._-]*$`, ≤ 64 chars, unique within the plan. |
| P4 | `description`: present, `str`, 20 ≤ len ≤ 2000 chars (bounded execution context). |
| P5 | `required_capabilities`: present, non-empty `list[str]`. |
| P6 | Every capability ∈ `known_capabilities()` — **rejects hallucinated capabilities**. |
| P7 | **Staffability**: `EmployeeRegistry().candidates_for(caps)` is non-empty for each package — a plan Lisa cannot staff is invalid. |
| P8 | `risk` (default `"normal"`) ∈ `VALID_RISK` (`"low"`, `"normal"`, `"critical"`). |
| P9 | `mode` (default `"balanced"`) resolves via `WorkforceModeRegistry().get()` without raising. |
| P10 | `depends_on` (default `[]`) is a `list[str]`. |
| P11 | No unknown keys — only `id`, `description`, `required_capabilities`, `risk`, `mode`, `depends_on`. |
| P12 | Graph integrity: `DependencyGraph.from_packages(...)` must not raise `GraphError` (no duplicate id, self-dependency, unknown dependency, or cycle). **Reuses DependencyGraph — no reimplementation of cycle detection.** |

On success, packages are normalized: defaults filled, key order enforced as
`id, description, required_capabilities, risk, mode, depends_on`.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | OK — plan written (plan-only mode) or dispatch succeeded. |
| 2 | `AMBIGUOUS_FLAGS` — `--goal` and `--plan` given together. |
| 4 | `PLANNING_REQUIRED` — GOVERNED mission, neither `--goal` nor `--plan` given. |
| 7 | `PLAN_REJECTED` — proposer output failed validation (≥1 rule violated). |
| 8 | `PLAN_PROPOSER_FAILED` — proposer transport or subprocess error. |

Exit codes 5 (BLOCKED), 6 (VALIDATION_FAILED), and dispatch exit codes are
unchanged from Phase 1.

---

## Artifact Layout

### Goal artifact (bare JSON array — required by bin/lisa-dispatch)

```
reports/lisa/orchestration/plans/<request_id>.json
```

Content: a bare JSON array of normalized work-package dicts.  Override with
`--plan-out PATH`.  This is the same format `bin/lisa --goal` and
`bin/lisa-dispatch` already consume — no wrapper object.

### Sidecar metadata (never pollutes the goal artifact)

```
reports/lisa/orchestration/plans/<request_id>.meta.json
```

Content:
```json
{
  "request_id": "<uuid>",
  "mission": "<original mission string>",
  "proposer_id": "openclaw:claude-sonnet",
  "created_at": "<ISO-8601 UTC>",
  "package_ids": ["pkg-a", "pkg-b"]
}
```

---

## Intake Records

New status values appended to the intake JSONL ledger:

| Status | When |
|--------|------|
| `PLAN_READY` | Plan validated and artifact written. |
| `PLAN_REJECTED` | `validate_plan()` raised `PlanValidationError`. `validation_errors` field carries the full error list. |
| `PLAN_PROPOSER_FAILED` | Proposer raised an exception. |
| `AMBIGUOUS_FLAGS` | Both `--goal` and `--plan` were given. |

---

## Test Seam

`LISA_PROPOSER_CMD` overrides the proposer **only when `LISA_TEST_MODE=1` is
also set**.  The command is called with the full prompt on stdin and must write
the plan text to stdout.  Setting `LISA_PROPOSER_CMD` without `LISA_TEST_MODE=1`
is ignored with a warning on stderr (same pattern as `LISA_DISPATCH_CMD`).

---

## Key Modules

| Module | Role |
|--------|------|
| `core/planner.py` | `known_capabilities()`, `build_prompt()`, `parse_plan_text()`, `validate_plan()`, `plan_mission()`, `build_openclaw_proposer()` |
| `core/workforce_resolver.py` | `EmployeeRegistry`, `WorkPackage`, `VALID_RISK` (P7, P8) |
| `core/workforce_modes.py` | `WorkforceModeRegistry` (P9) |
| `core/dependency_graph.py` | `DependencyGraph` (P12 — reused, not reimplemented) |
| `core/openclaw_bridge.py` | `agent_for_logical()` — used by `build_openclaw_proposer()` |

`bin/lisa` accesses openclaw only through `core.planner` — it does not import
`core.openclaw_bridge` directly.

---

## Honest Limitations

1. **Non-deterministic proposer**: the LLM may return different decompositions
   for the same mission.  Validation is deterministic; acceptance is not.
2. **P7 staffability** checks the registry at plan time, not at dispatch time.
   An employee's availability is checked by the WorkforceResolver at dispatch.
3. **No multi-turn planning**: each call to `plan_mission()` is a single,
   stateless proposer call.  The proposer has no memory of prior plans.
4. **Single proposer model**: `build_openclaw_proposer()` defaults to
   `claude-sonnet`.  The model is chosen by the agent's own OpenClaw binding;
   Lisa cannot override it per the agent-model contract.
