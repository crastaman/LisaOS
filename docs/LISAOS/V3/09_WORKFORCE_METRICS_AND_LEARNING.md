# Workforce Metrics & Learning Plan

**Status:** DESIGN FOR APPROVAL. No implementation.
**Date:** 2026-07-07

LisaOS must *learn from every sprint* and tune routing over time. This defines the metrics, where they come from (evidence, not assumption), and the learning loop that turns them into better routing.

---

## 1. Data sources (all inspectable — evidence before assumption)

| Source | Provides |
|---|---|
| `reports/lisa/provider_resolution_evidence.jsonl` (exists) | per-resolution: intended/resolved/actual model, availability, auth, fallback, drift |
| OpenClaw state `~/.openclaw/state/openclaw.sqlite` (`subagent_runs`, `task_runs`, `flow_runs`) | actual model run, timing, status per subagent |
| `openclaw models status` | auth expiry, provider health at sprint start |
| Sprint ledger (new, proposed `reports/lisa/sprint_metrics.jsonl`) | per-sprint rollup of the metrics below |

The learning store never invents numbers; every metric traces to one of these.

## 2. The metric set

### Delegation & utilisation (the core problem)
| Metric | Definition | Target |
|---|---|---|
| **Delegation ratio** | packets delegated ÷ delegable packets | ≥0.8 (Balanced) |
| **Worker utilisation** | mean % capable employees busy on ready frontier | ≥60% |
| **Idle time** | employee-minutes idle while ready work existed | → 0 |
| **Parallel efficiency** | serial-sum(packet times) ÷ wall-clock | ≥ target per mode (>2× baseline) |
| **Scheduling failures** | ticks with idle-capable-employee + unassigned-frontier | → 0 |
| **"Main did it itself"** | delegable packets executed by the main runtime | → 0 |

### Cost & capacity (`06`)
| Metric | Definition | Target |
|---|---|---|
| Subscription utilisation | subscription packets ÷ subscription-eligible | ≥90% |
| API spend / sprint | £ elastic | ↓ per unit work |
| Opus guard ratio | Opus packets ÷ total | ≤10%, all irreversible |
| GLM utilisation | GLM packets ÷ total | >0 rising |
| Wasted-quota events | idle subscription while paying API | → 0 |

### Quality & reliability
| Metric | Definition | Target |
|---|---|---|
| Review loop count | rework cycles per packet | ↓ |
| Defect rate | packets failing QA ÷ total | ↓ |
| Retry rate | retries ÷ packets | ↓ |
| Escalation rate | packets escalated a rung ÷ total | stable/↓ |
| Fallback rate | resolutions using a fallback ÷ total | ↓ (high = config/health problem) |
| Model drift | `actual_model ≠ resolved_model` events | 0 (fail-closed guarantee) |

### Scores (learned, per model & per employee)
- **Model performance score** — per (model, capability): success rate, mean latency, retry/defect contribution, cost. Updated each sprint.
- **Employee performance score** — per role: delegation success, escalation frequency, defect rate.

## 3. The learning loop

```
after each sprint:
    rollup = aggregate(evidence_jsonl, openclaw_sqlite, sprint_events)
    append rollup -> sprint_metrics.jsonl
    for (model, capability) in rollup:
        model_score[model,cap] = ema(model_score[model,cap], observed)   # exponential moving avg
    for employee in rollup:
        emp_score[employee] = ema(emp_score[employee], observed)
    propose_tuning(rollup)     # -> suggestions, NOT auto-applied to prod routing
```

**Tuning outputs (suggestions, gated):**
- Promote a probationary model to `preferred` for a role (score cleared threshold).
- Demote a model with high defect/retry contribution to fallback-only.
- Raise/lower a provider's concurrency cap based on observed throttling.
- Flag a chronically idle employee (over-hired role) or a chronically overloaded one (needs a second candidate).

### Governance of learning
- Learning **proposes**; a human (or CTO Reviewer in an approved mode) **confirms** changes to `preferred` bindings. No silent self-rewiring of production routing — consistent with "fail closed, evidence before assumption".
- All score changes are logged with the evidence that drove them.

## 4. Probation mechanic (ties to `01`/`05`)

A newly hired model starts at neutral score, `probation: true`. For its first N sprints (default 3) it is eligible only for low-risk packets. If its model performance score clears threshold and defect contribution is below cap, the learning loop *proposes* promotion to `preferred`. This is how "adding a model = hiring an employee, then it earns trust" is made concrete.

## 5. Reporting

- **Per-sprint scorecard** appended to the sprint ledger and surfaced in the morning brief (`reports/nightly/morning-brief.md` already exists as the delivery channel).
- **Trend view** — delegation ratio, utilisation, subscription %, API £ over the last K sprints — is the operator's single glance at whether 3.0 is working.
- **Regression alarms** — delegation ratio dropping or scheduling failures rising triggers a surfaced warning (the "Lisa is slow" early-warning).

## 6. Definition of "learning is working"

Over successive sprints: delegation ratio ↑ and stabilises high; scheduling failures → 0; subscription utilisation ↑; API £/unit-work ↓; defect/retry ↓. If these trends hold, the workforce is self-tuning as designed. If delegation ratio regresses, the metric surfaces it before the operator has to notice slowness manually.
