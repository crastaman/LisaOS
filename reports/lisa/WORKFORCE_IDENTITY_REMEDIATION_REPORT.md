# LisaOS Workforce Identity Remediation — Implementation Report

**Implementer:** Sonnet, per the Workforce Identity Remediation handoff (Opus)
**Date:** 2026-07-11
**Architecture adopted:** `Employee (LisaOS policy) → OpenClaw Agent (identity) → Physical Model`. Persona-only execution identity is now prohibited.
**Scope:** LisaOS + OpenClaw agent provisioning. No orchestration redesign, no DB migration, no workforce-policy change.

---

## 1. Headline result

Execution identity is now deterministic and structurally unambiguous. **Every logical workforce identity has exactly one dedicated OpenClaw agent**, dispatch selects it by an explicit 1:1 map (no physical-model reverse match), and the identity chain is enforced by a gate and auditable by a CLI. **All 5 required identities executed for real on their correct dedicated agents**, independently verified in `task_runs`. Suite: 430 → **442 tests, all green**.

The codex/gpt collision is resolved at the root: `codex`→`lisa-codex` and `gpt`→`lisa-gpt` now run on the *same physical model* (`openai/gpt-5.5`) as *distinct agents* — attribution stays intact because `task_runs.agent_id` differs.

---

## 2. Required changes — delivered

### (1) Missing identity agents provisioned
Created via the Phase 4b flow (`openclaw agents add`), one dedicated agent per logical identity:

| Provisioned | Model | | Already existed |
|---|---|---|---|
| `lisa-deepseek` | custom-api-deepseek-com/deepseek-reasoner | | `lisa-claude-opus` |
| `lisa-codex` | openai/gpt-5.5 | | `lisa-claude-sonnet` |
| `lisa-gpt` | openai/gpt-5.5 | | `lisa-qwen` |
| `lisa-haiku` | anthropic/claude-haiku-4-5 | | |
| `lisa-glm` | zai/glm-5.2 | | |
| `lisa-glm-turbo` | zai/glm-5-turbo | | |

All 9 logical providers now have a 1:1 dedicated agent (haiku/glm models are outside the OpenClaw default-catalog but provisioned cleanly — the catalog is a hint, not an allowlist).

**Naming decision (flagged):** the handoff listed `lisa-opus`/`lisa-sonnet`, but dedicated agents already existed as `lisa-claude-opus`/`lisa-claude-sonnet`. Creating new `lisa-opus`/`lisa-sonnet` would produce **two** agents per identity — violating "one identity → one agent." Per "smallest change set," I mapped `claude-opus`→`lisa-claude-opus` and `claude-sonnet`→`lisa-claude-sonnet` (the existing agents) rather than duplicating. Same identity guarantee, no duplication.

### (2) Reverse physical-model matching replaced with a deterministic map
- `registry/provider_resolution.yml`: each of the 9 providers gains an explicit `agent:` binding (the 1:1 map, co-located with `physical_model`).
- `core/openclaw_bridge.py`: new `agent_for_logical(resolved_logical, resolver)` reads that binding. `_execute` now selects the agent by **logical identity**, not physical model. The prohibited `_select_agent`/`agent_for_physical_model` reverse match is retained **for validation only** (drift check) and no longer participates in dispatch.
- Fail-closed: an identity with no `agent` binding → `fail-closed-no-identity-agent`; a bound agent that isn't a live non-WBS agent → `fail-closed-identity-agent-unavailable`. Never falls through to a shared agent.

### (3) Single source of truth / drift detection
- `validate_identity_map(resolver)` cross-checks the registry against **live OpenClaw** (`agents list`): every logical provider must have an `agent` that (a) exists, (b) is not shared/general or `wbs-*`, and (c) whose pinned model matches the registry `physical_model` (openclaw.json is authoritative). Any divergence is a reported problem.
- Exposed via `bin/lisa-identity-check drift`. (Kept `provider_resolution.yml` rather than deleting it — the resolver and 200+ tests depend on it; the drift check is the smaller, safer of the handoff's two options.)

### (4) Bridge-only dispatch enforcement
- `bin/lisa-identity-check bypass` scans `~/.openclaw/state/openclaw.sqlite` (read-only) for the S036a failure mode: a task that declared a worker persona ("You are … Qwen/Codex/…") but executed on a **shared/general agent** (`main`/…). Each is reported as a `VIOLATION` with the broken chain, and the CLI exits non-zero. Direct manual-TUI subagent spawning that breaks identity is now surfaced, never silent. (This complements the existing `governance_guard`, which covered Claude Code subagents but not the OpenClaw main-TUI path.)

### (5) Attribution guard (in-band gate)
- `core/anti_regression.py`: new `check_identity_chain(assignment, identity_map)` — the executing agent must be the dedicated agent for the package's `resolved_logical`. A package that ran on a *different* agent (esp. `main`) is a hard FAIL, even when the model is right. Wired into `run_dispatch_gates`/`run_policy_gates` (identity map built from the resolver). Gate index F8.

---

## 3. Structural guarantees now enforced

| Must be impossible | Mechanism |
|---|---|
| Codex/GPT/DeepSeek executing via a shared agent (`main`) | dispatch selects `lisa-<identity>` only; `check_identity_chain` FAILs otherwise; `lisa-identity-check bypass` flags any manual occurrence |
| Workforce identity inferred from physical model | selection keys on `resolved_logical`, never physical model |
| Reverse model lookup (dispatch) | removed from `_execute`; retained only for drift validation |
| Two identities collapsing onto one agent | 1:1 registry binding; `codex`≠`gpt` proven live (distinct agents, same model) |
| Silent execution substitution | `mismatch` (R1) + `check_no_execution_mismatch` (F7) + `check_identity_chain` (F8), all gate-enforced |

---

## 4. Verification tests (real, DB-verified)

Dispatched all 5 required identities through `bin/lisa-dispatch` (REAL mode). `graph: 5 completed, 0 failed`, all `mismatch=False`:

| Requested identity | Selected agent | Executed model | Runtime label | task_runs status (independent query) |
|---|---|---|---|---|
| claude-opus | **lisa-claude-opus** | anthropic/claude-opus-4-8 | claude-cli | succeeded |
| claude-sonnet | **lisa-claude-sonnet** | anthropic/claude-sonnet-4-6 | claude-cli | succeeded |
| deepseek | **lisa-deepseek** | custom-api-deepseek-com/deepseek-reasoner | openclaw | succeeded |
| codex | **lisa-codex** | openai/gpt-5.5 | codex | succeeded |
| gpt | **lisa-gpt** | openai/gpt-5.5 | openclaw | succeeded |

Independent `sqlite3` query of `task_runs` confirmed each `run_id → agent_id` (all `lisa-*`, all `succeeded`). `codex` and `gpt` ran on the same model as **different agents** — the collision is structurally gone.

`bin/lisa-identity-check bypass` over the probe window: **no violations** (all via `lisa-*` agents). Over the S036a window (2026-07-09): correctly **flags** the historical `qwen-deepinfra → main → deepseek-reasoner` and `claude-opus → main → sonnet` chain breaks — proving the guard catches the exact original failure.

**Honest note on exit code:** the probe returned exit 3 due to a **pre-existing, unrelated** `no_worker_starvation` gate (`deepseek-probe` waited 15s under the deliberately low `--max-per-provider 2`). All identity/attribution gates (F7, F8) passed. This is a scheduling artefact of the probe parameters, not an identity failure.

---

## 5. Tests

```
$ PYTHONPATH="$HOME/Lisa" python3 -m unittest discover -s tests
Ran 442 tests in 1.5s — OK (skipped=39)
```
430 pre-existing (fixtures updated for the deterministic path; none weakened) + **12 new**: deterministic map + collision-distinctness, `validate_identity_map` drift/missing/shared-agent cases, two new fail-closed paths (unmapped identity, identity-agent-unavailable), `check_identity_chain` PASS/FAIL cases, and a `run_dispatch_gates` integration test proving a broken chain fails the report.

---

## 6. Files changed

| File | Change |
|---|---|
| `registry/provider_resolution.yml` | `agent:` binding added to all 9 providers (the 1:1 map) |
| `core/openclaw_bridge.py` | `agent_for_logical()` (deterministic selection), `validate_identity_map()` (drift), `_execute` rewired off reverse match, new fail-closed reasons, docstring |
| `core/anti_regression.py` | `check_identity_chain()` gate (F8) + wired into `run_dispatch_gates` |
| `bin/lisa-identity-check` | **New.** `drift` + `bypass` read-only audits |
| `tests/test_openclaw_bridge.py` | fixtures updated for identity dispatch; new deterministic-selection + drift tests |
| `tests/test_anti_regression.py` | `check_identity_chain` unit + integration tests |

**OpenClaw side:** 6 new agents provisioned (config-managed by the CLI; `openclaw.json` is the source of truth). No LisaOS code writes to OpenClaw state; `openclaw.sqlite` opened `mode=ro` throughout.

**Not touched:** workforce-policy layer (employees, capabilities, seniority, cost, scheduler), dispatcher scheduling loop, OpenClaw itself. No new orchestration layer.

---

## 7. Rollback

- Deprovision agents: `openclaw agents delete lisa-{deepseek,codex,gpt,haiku,glm,glm-turbo}`.
- `git checkout registry/provider_resolution.yml core/openclaw_bridge.py core/anti_regression.py tests/test_openclaw_bridge.py tests/test_anti_regression.py`; delete `bin/lisa-identity-check`.
- Re-run suite → pre-sprint baseline green. No DB/state to unwind (read-only throughout).

---

## 8. Outcome

S036a-style attribution divergence is now structurally impossible for bridge-dispatched work: `Policy Layer → Agent Identity → Physical Execution`, with the agent identity bound to the model at the OpenClaw layer and enforced by gate + audit. The one residual is inherent and already governed: an operator can still hand-spawn a persona through `main` outside the bridge — that path is now *detected and flagged* by `lisa-identity-check bypass` and prohibited by governance rule 13, but (as the architecture review noted) native isolation removes the mechanism, not the human ability to bypass it.
