---
schema: lisaos.gpt_context.v1
last_updated: 2026-07-08
owner: LisaOS
status: active
---

# LisaOS Context

## Current state (as of 2026-07-08)

LisaOS 3.0 "Workforce Intelligence" core (Phases 0–3) is **closed and in
maintenance mode**, approved complete by Roshan on 2026-07-08, in `~/Lisa`
on branch `fix/provider-resolution`. 220/220 tests passing at closure. Full
record: `docs/LISAOS/V3/LISAOS_3.0_CLOSURE_REPORT.md` and
`docs/LISAOS/V3/32_CTO_FINAL_REVIEW.md`.

Further core development is frozen except for (1) bug fixes, (2)
regressions, (3) concrete WBS-driven needs. Primary project attention has
returned to WBS. A number of gaps were explicitly deferred at closure, not
forgotten — do not treat a mention of one of these as a bug report unless
it's blocking something concrete: dynamic main/MAIN-001, sprint metrics
ledger, o-series import, the learning loop, local Ollama activation,
legacy `cost_tier` retirement, and a corrupt native DeepSeek credential.

## What LisaOS is

An adaptive engineering organization model: jobs are decomposed and staffed
against a registry of roles/employees/capabilities
(`registry/employees.yml`, `registry/capabilities.yml`), scheduled by a
ready-frontier dependency graph (`core/dependency_graph.py`), and executed
by `core/dispatcher.py` — the **sole execution authority** in the system
(`governance/GOVERNANCE.md`, rule 12). Evidence of what happened is recorded
as append-only JSONL under `reports/lisa/`.

## Lisa Console's relationship to this

Lisa Console v1 (this pack exists to support it) is a **separate, additive
track** — it does not reopen the V3 core freeze. It only reads existing
evidence/registries and adds new, clearly-scoped modules
(`advisors/`, `console/`, `docs/LISAOS/CONSOLE/`) alongside the frozen
core. See `docs/LISAOS/CONSOLE/00_ARCHITECTURE.md`.
