# Employee Capability Matrix

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

Each employee is a **role** bound to a preferred model family + exact model + fallbacks, with capability requirements, a utilisation target, and a failure policy. Models are from the verified inventory (`03`). This is the proposed content of a new `registry/employees.yml` — it **replaces** the thin `runtimes.yml` placeholders (`gpt-governance`, `deepseek-planning`, …) that were never bound to physical models.

Legend — **Class**: Sub = subscription, API = elastic API, Local = on-device. **Speed/Ctx/Reliability**: L/M/H relative. **Util %**: target share of that employee's department load.

> **Trust guards (corrections applied — see CHANGELOG):**
> - **GLM is PROBATIONARY, not trusted.** Where a role lists a GLM model it is a *probation candidate* (`probation: true`), eligible for low-risk packets only, never the confirmed `preferred` until it passes reliability validation. **If GLM fails validation it is retired** and the role falls back to the next model. No critical work routes to GLM pre-validation.
> - **Codex is hired only after identity validation.** Roles listing Codex (`openai/gpt-5.5` via codex runtime) require Phase-0 runtime evidence that `codex` really is OpenAI, not the mis-named Alibaba-Qwen provider (`15`). Until then those roles use their non-Codex option.
> - **Local AI is NOT in the active workforce.** No employee below depends on a local model. Local is future capacity only (`10`); any prior "local fallback" is removed from active bindings.

---

## 1. Office of the CTO

### CHIEF-ARCHITECT
| Field | Value |
|---|---|
| Department | Office of the CTO |
| Responsibilities | System architecture, irreversible design decisions, cross-cutting technical direction |
| Preferred family / model | Anthropic Opus / `anthropic/claude-opus-4-8` |
| Fallback models | `anthropic/claude-opus-4-7`, `anthropic/claude-opus-4-6` |
| Required capabilities | `architecture`, `irreversible-judgement`, `deep-reasoning`, `long-context` |
| Best tasks | Architecture sprints, kernel decisions, trade-off adjudication |
| Avoid | Bulk implementation, mechanical edits, microtasks (quota waste) |
| Class / Cost | Sub / high (scarce) | 
| Speed / Ctx / Reliability | L / H / H |
| Ideal util % | ≤10% (scarce, on-demand) |
| Failure policy | No lateral fallback for judgement; if Opus unavailable → **halt & surface**, do not downgrade architecture to a cheaper model |

### CTO-REVIEWER
| Field | Value |
|---|---|
| Department | Office of the CTO |
| Responsibilities | Final approval gate; reviews irreversible/architectural output before acceptance |
| Preferred family / model | Anthropic Opus / `anthropic/claude-opus-4-8` |
| Fallback models | `anthropic/claude-opus-4-7` |
| Required capabilities | `review`, `irreversible-judgement`, `security-review` |
| Best tasks | Sign-off on CTO review, release gates, security-sensitive changes |
| Avoid | Authoring the thing it reviews (separation of duties) |
| Class / Cost | Sub / high |
| Speed / Ctx / Reliability | L / H / H |
| Ideal util % | ≤10% |
| Failure policy | If Opus unavailable → block acceptance; never auto-approve on a lesser model |

## 2. Engineering

### SENIOR-SW-ENGINEER
| Field | Value |
|---|---|
| Responsibilities | Complex coding, refactoring, design-level implementation, code review |
| Preferred family / model | Anthropic Sonnet / `anthropic/claude-sonnet-4-6` |
| Fallback models | `openai/gpt-5.5` (codex runtime), `custom-api-deepseek-com/deepseek-reasoner` |
| Required capabilities | `code-implementation`, `refactor`, `review`, `long-context` |
| Best tasks | Non-trivial features, architecture-conformant implementation, reviews |
| Avoid | Trivial edits (delegate down), architecture ownership (escalate up) |
| Class / Cost | Sub / medium |
| Speed / Ctx / Reliability | M / H / H |
| Ideal util % | 25% |
| Failure policy | 2 retries → escalate to Chief Architect; fallback Codex then DeepSeek, recorded |

### SW-ENGINEER
| Field | Value |
|---|---|
| Responsibilities | Standard feature work, well-specified implementation |
| Preferred family / model | OpenAI Codex / `openai/gpt-5.5` (runtime: codex) |
| Fallback models | `anthropic/claude-sonnet-4-6`, `custom-api-deepseek-com/deepseek-reasoner` |
| Required capabilities | `code-implementation`, `code-execution`, `test-authoring` |
| Best tasks | Specified features, patch validation, sandboxed changes |
| Avoid | Ambiguous/architectural work |
| Class / Cost | Sub / medium |
| Speed / Ctx / Reliability | M / M / H |
| Ideal util % | 30% |
| Failure policy | 2 retries → escalate to Senior SW Eng |

### IMPLEMENTATION-ENGINEER
| Field | Value |
|---|---|
| Responsibilities | High-volume, well-bounded mechanical implementation |
| Preferred family / model | DeepSeek / `custom-api-deepseek-com/deepseek-reasoner` |
| Fallback models | `deepinfra/Qwen/Qwen3.6-35B-A3B`, `zai/glm-5.2` |
| Required capabilities | `code-implementation`, `bulk-mechanical` |
| Best tasks | Boilerplate, repetitive edits, scaffolding, bulk transforms |
| Avoid | Design decisions, security-sensitive code |
| Class / Cost | API / low |
| Speed / Ctx / Reliability | H / M / M |
| Ideal util % | 35% |
| Failure policy | 2 retries → escalate to SW Eng; fallback Qwen-DeepInfra then GLM |

## 3. Quality

### QA-ENGINEER
| Field | Value |
|---|---|
| Responsibilities | Test authoring, acceptance validation, regression checks |
| Preferred family / model | Anthropic Sonnet / `anthropic/claude-sonnet-4-6` |
| Fallback models | `openai/gpt-5.5` (codex), `deepinfra/Qwen/Qwen3.6-35B-A3B` |
| Required capabilities | `test-authoring`, `code-execution`, `review` |
| Best tasks | Writing/running tests, validating acceptance criteria, coverage |
| Avoid | Authoring the implementation it tests |
| Class / Cost | Sub / medium |
| Speed / Ctx / Reliability | M / H / H |
| Ideal util % | 15% |
| Failure policy | Flaky test → Debugging Specialist |

### DEBUGGING-SPECIALIST
| Field | Value |
|---|---|
| Responsibilities | Root-cause analysis, failure reproduction, fixes |
| Preferred family / model | OpenAI Codex / `openai/gpt-5.5` (codex); deep bugs → `openai/o3` |
| Fallback models | `anthropic/claude-sonnet-4-6`, `custom-api-deepseek-com/deepseek-reasoner` |
| Required capabilities | `code-execution`, `deep-reasoning`, `code-implementation` |
| Best tasks | Stack traces, flaky tests, regressions, perf issues |
| Avoid | Greenfield feature work |
| Class / Cost | Sub / medium–high |
| Speed / Ctx / Reliability | M / M / H |
| Ideal util % | on-demand |
| Failure policy | 3 retries → escalate to Senior SW Eng + Chief Architect |

## 4. Research & Docs

### RESEARCH-ENGINEER
| Field | Value |
|---|---|
| Responsibilities | Investigation, options analysis, synthesis, benchmarking |
| Preferred family / model | OpenAI o-series / `openai/o3` (deep research: `openai/o3-deep-research`) |
| Fallback models | `openai/gpt-5.5`, `deepinfra/Qwen/Qwen3.6-35B-A3B` |
| Required capabilities | `research`, `deep-reasoning`, `long-context` |
| Best tasks | Trade studies, literature/codebase investigation, comparisons |
| Avoid | Long-running main; production code |
| Class / Cost | Sub / medium |
| Speed / Ctx / Reliability | L / H / H |
| Ideal util % | on-demand |
| Failure policy | Fallback to GPT burst then Qwen |

### DOCUMENTATION-ENGINEER
| Field | Value |
|---|---|
| Responsibilities | Docs, reports, changelogs, guides, dashboards |
| Preferred family / model | Qwen-DeepInfra / `deepinfra/Qwen/Qwen3.6-35B-A3B` (large-ctx mechanical) |
| Fallback models | `zai/glm-5.2`, `anthropic/claude-haiku-4-5` |
| Required capabilities | `documentation`, `long-context`, `bulk-mechanical` |
| Best tasks | README/report generation, doc refactors, large-context summarisation |
| Avoid | Architecture narrative requiring judgement (escalate) |
| Class / Cost | API / low |
| Speed / Ctx / Reliability | H / H / M |
| Ideal util % | 20% |
| Failure policy | Fallback GLM then Haiku |

## 5. Operations

### OPS-ENGINEER
| Field | Value |
|---|---|
| Responsibilities | Runtime ops, nightly jobs, health checks, config hygiene |
| Preferred family / model | Anthropic Haiku / `anthropic/claude-haiku-4-5` (subscription) |
| Probation candidate | GLM / `zai/glm-5-turbo` — *may become preferred only after reliability validation* |
| Fallback models | `anthropic/claude-haiku-4-5` (local Ollama: **future only, not active**) |
| Required capabilities | `microtask`, `bulk-mechanical`, `documentation` |
| Best tasks | Log parsing, morning brief, status rollups, config checks |
| Avoid | Anything irreversible |
| Class / Cost | Sub / low |
| Speed / Ctx / Reliability | H / M / M |
| Ideal util % | 15% |
| Failure policy | Fallback within subscription (Haiku); GLM only if validated; **no local dependency** |

### MICROTASK-AGENT
| Field | Value |
|---|---|
| Responsibilities | Cheapest-possible small units: routing hints, summaries, extraction |
| Preferred family / model | Anthropic Haiku / `anthropic/claude-haiku-4-5` |
| Probation candidate | `zai/glm-5-turbo` (validate first) |
| Fallback models | Haiku only for now (GLM once validated; local `qwen2.5:3b` is **future capacity, not active**) |
| Required capabilities | `microtask` |
| Best tasks | 1-shot summaries, label extraction, dashboard cell updates |
| Avoid | Multi-step reasoning |
| Class / Cost | Sub / near-zero |
| Speed / Ctx / Reliability | H / L / M |
| Ideal util % | fill idle |
| Failure policy | Fallback within subscription; GLM-turbo only if validated; **no local dependency**; never escalates above SW Eng |

### RELEASE-MANAGER
| Field | Value |
|---|---|
| Responsibilities | Release readiness, changelog assembly, gate coordination |
| Preferred family / model | OpenAI GPT burst / `openai/gpt-5.5` (short bursts only) |
| Fallback models | `anthropic/claude-sonnet-4-6` |
| Required capabilities | `documentation`, `review`, `repository_operations` |
| Best tasks | Release checklists, changelog synthesis, gate orchestration |
| Avoid | Long-running sessions (GPT limit risk) |
| Class / Cost | Sub / low |
| Speed / Ctx / Reliability | M / M / H |
| Ideal util % | on-demand |
| Failure policy | Fallback Sonnet |

## 6. Platform (deterministic org citizens — not LLM capacity)

### PROVIDER-MANAGER
Owns `registry/provider_resolution.yml` + `core/provider_resolver.py`. Resolves logical→physical, checks availability, fails closed. **This is code, not a model.** Health/credential authority for the whole org.

### DISPATCHER-MANAGER
Owns the scheduler: builds the ready frontier, assigns packets to employees, enforces the "keep workforce busy" invariant, records utilisation. **Routes workers — the main runtime does not.** GPT burst may assist with graph decomposition, but the *routing decision* is deterministic.

### CONTEXT-MANAGER
Owns context budgeting/compaction across employees (builds on `LISAOS_CONTEXT_MANAGEMENT.md`). Preferred assist model for summarisation: Qwen-DeepInfra or Haiku (cheap, large-ctx). Prevents context bloat that slows the main runtime.

---

## 7. Summary table

| Employee | Dept | Preferred model | Class | Ideal util % | Escalates to |
|---|---|---|---|---|---|
| Chief Architect | CTO | claude-opus-4-8 | Sub | ≤10% | — |
| CTO Reviewer | CTO | claude-opus-4-8 | Sub | ≤10% | — |
| Senior SW Eng | Eng | claude-sonnet-4-6 | Sub | 25% | Chief Architect |
| SW Eng | Eng | gpt-5.5 (codex) † | Sub | 30% | Senior SW Eng |
| Implementation Eng | Eng | deepseek-reasoner | API | 35% | SW Eng |
| QA Engineer | Quality | claude-sonnet-4-6 | Sub | 15% | Debugging Specialist |
| Debugging Specialist | Quality | gpt-5.5 (codex) † / o3 | Sub | on-demand | Senior SW Eng |
| Research Engineer | R&D | o3 / o3-deep-research | Sub | on-demand | — |
| Documentation Eng | R&D | Qwen-DeepInfra | API | 20% | — |
| Ops Engineer | Ops | claude-haiku-4-5 (GLM ‡) | Sub | 15% | — |
| Microtask Agent | Ops | claude-haiku-4-5 | Sub | fill idle | SW Eng |
| Release Manager | Ops | gpt-5.5 burst | Sub | on-demand | — |
| Provider Manager | Platform | *(code)* | — | — | — |
| Dispatcher Manager | Platform | *(code)* | — | — | — |
| Context Manager | Platform | *(code + cheap assist)* | — | — | — |

The preferred-model column is the **Balanced mode** default. Other modes re-bind these (see `08`).

† **Codex hire is gated** on Phase-0 runtime-evidence identity validation (`15`); until confirmed OpenAI, these roles use Sonnet/DeepSeek.
‡ **GLM is a probation candidate**, not the confirmed preferred; validate before reliance, retire on failure. Local AI is absent from this table by design (future capacity, `10`).
