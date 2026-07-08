---
schema: lisaos.gpt_context.v1
last_updated: 2026-07-08
owner: LisaOS
status: active
---

# Glossary

- **LisaOS** — the workforce/automation operating system in `~/Lisa`.
- **Job Packet** — the unit of work LisaOS schedules and executes,
  shaped by `jobs/schema.yml`.
- **Dispatcher** — `core/dispatcher.py`; the sole execution authority in
  LisaOS (`governance/GOVERNANCE.md`, rule 12).
- **Workforce Resolver** — `core/workforce_resolver.py`; matches a job to
  a capable, seniority-ordered employee/role from `registry/employees.yml`.
- **Governance Gate** — a pass/fail/warn check run before or around
  dispatch (`core/anti_regression.py`, `core/governance_guard.py`).
- **Decision Bundle** — the complete evidence LisaOS exports for one job
  that needs a human decision. See
  `docs/LISAOS/CONSOLE/01_DECISION_BUNDLE_SPEC.md`.
- **Executive Brief** — the GPT Advisor's compressed output for one
  Decision Bundle: headline, summary, recommendation, confidence, risk
  flags, open questions.
- **GPT Advisor** — the advisory-only summarization pipeline in
  `advisors/`. Never executes anything.
- **Lisa Console** — the private web app (`console/`) where Roshan reviews
  briefs and records Approve/Reject decisions.
- **Safe Action** — an action the Console is permitted to take: writing a
  bundle's `decision` field, or an audit-log line. Nothing else.
- **ntfy** — the push-notification relay (ntfy.sh) used to alert Roshan
  that a decision is pending.
- **Tailnet** — the private Tailscale network the Console is exposed on;
  never the public internet.
- **Artifact Lifecycle** — the state machine (`DRAFT → PENDING_VALIDATION
  → VALIDATED → PUBLISHED → ARCHIVED → DELETED`) defined in
  `docs/LISAOS/LISAOS_ARTIFACT_LIFECYCLE.md`, reused by Decision Bundles.
- **WBS / HEB** — a primary LisaOS project (separate repository); see
  `05_WBS_CONTEXT.md`.
- **BAR** — a primary LisaOS project; see `02_BAR_TECH_CONTEXT.md`.
