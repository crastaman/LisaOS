# LISA_GOVERNANCE_DETECTION_PHASE6 — Governance Detection Backstop

**Phase:** 6 (LISA-I008) · **Baseline:** `LISA-I007-PHASE5-COMPLETE`
**Module:** `core/governance_detector.py` · **CLI:** `bin/lisa-governance`
**Tests:** `tests/test_governance_detector.py`

Phases 1–5 built an authoritative governed path. LisaOS could execute governed
work correctly but could not **see** governed work that bypassed it. That
blindness is what let S046 fail silently.

**Principle: governed work must always produce evidence.** Governed-shaped
activity with no corresponding LisaOS evidence is a governance violation.

---

## How detection works

| Stage | Source |
|---|---|
| observed activity | OpenClaw `task_runs` (read-only) — the same ground truth the bridge already reconciles against |
| governed shape | `core/task_classifier.py` — the **same deterministic rules** that route work at intake. No language model. |
| correlation | `run_id` present in `workforce_evidence.jsonl` or the work-product index |

Present ⇒ governed and evidenced. Absent ⇒ the work happened outside LisaOS.

Reusing the intake classifier means a rule that governs at the front door
governs at the backstop, by construction — the two can never drift apart.

---

## The detection asymmetry (the false-positive control)

Intake and detection deliberately fail in **opposite** directions:

* **Intake**: ambiguity → `GOVERNED`. Being wrong merely over-governs safe work.
* **Detection**: ambiguity → **no violation**. Being wrong blocks real
  engineering and accuses an operator of a bypass.

So detection requires a **positive** signal — at least one explicit `G` rule —
and never fires on `DEFAULT_GOVERNED_AMBIGUOUS`. Conversation, architectural
discussion, explanation, status questions and read-only research match no `G`
rule and are never flagged. `cron` runtimes are excluded by default: scheduled
operational jobs are not governed engineering, and sweeping them in would
generate the recurring noise that teaches operators to ignore a detector.

**Severity** is `critical` when a change-making rule matched (`G1_REPO_WRITE`,
`G2_EXECUTION_MUTATION`) and `warning` otherwise — so a bypassed audit and a
bypassed implementation are not presented as equally urgent.

---

## GovernanceViolation schema (`lisa-governance-violation/1`)

```json
{"violation_id": "...", "timestamp": "<from the observed run>",
 "reason": "...", "governing_rule": ["G1_REPO_WRITE"],
 "observed_activity": {"run_id","agent_id","runtime","status","task","observed_at","source"},
 "missing_evidence": ["workforce_evidence","work_product"],
 "severity": "critical|warning", "acknowledged": false, "acknowledged_by": null}
```

`violation_id` is `sha256("openclaw-run:<run_id>")[:16]` — deterministic, so
re-scanning never produces duplicate or drifting violations. Every timestamp
comes from the **observed activity**, never the wall clock, so reports are
byte-identical across runs (the Phase 5 discipline, for the same reason).

---

## Behaviour on detection

`require_clean_execution()` **raises** rather than continuing. `bin/lisa` calls
it before both governed dispatch paths (`--goal` and `--plan --dispatch`) and
exits **9** with `GOVERNANCE_BLOCKED`, recording the block in the intake ledger.
Violations are appended to an append-only ledger; nothing is repaired,
re-routed or dispatched.

**Acknowledgement is an attributed human decision.** It does not make bypassed
work governed retroactively and creates no evidence for it — it records that a
named operator reviewed and accepted the deviation. The acknowledgement ledger
of `core/governance_guard.py` is **reused, not duplicated**, so an operator has
one place to review deviations across both bypass surfaces.

```
bin/lisa-governance report          # deterministic report (exit 9 if pending)
bin/lisa-governance check           # fail closed
bin/lisa-governance acknowledge <id> --operator NAME --reason TEXT
bin/lisa-governance acknowledge-all --operator NAME --reason TEXT
```

`LISA_GOVERNANCE_DB` overrides the observation source (tests point it at a
nonexistent path to stay isolated from real machine state).

---

## Honest limitations

* **A detector that cannot see cannot protect.** If the OpenClaw database is
  absent or unreadable, detection yields nothing and the gate stays open. This
  is a backstop; the primary control remains the structural fact that `lisa` is
  the only governed door.
* **Keyword rules cannot parse negation.** A brief saying "do **not** implement"
  contains "implement" and matches `G1`. Read-only review briefs therefore
  sometimes classify as `critical`. Deterministic matching cannot fix this;
  treating severity as a hint rather than a verdict is the mitigation.
* **Correlation is by `run_id` only.** Work performed with no `task_runs` row
  at all (a human editing files directly) is invisible to this detector.
* Detection reads the whole `task_runs` history by default, so adopting the
  backstop surfaces historical bypasses immediately — see below.

---

## Adoption note

At implementation time a scan of the real machine reported **36 violations
across 37 observed executions** — including every manual `openclaw agent`
worker dispatch used to build Phases 1–6 themselves. These are genuine: that
work bypassed LisaOS intake. They are left **unacknowledged deliberately**;
acknowledging them is an attributed operator decision, not one LisaOS or an
assistant may take on the operator's behalf. Until acknowledged, governed
dispatch through `bin/lisa` is blocked — which is the backstop working as
designed.
