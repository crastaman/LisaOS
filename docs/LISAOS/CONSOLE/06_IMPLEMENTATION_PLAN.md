# Sonnet Implementation Plan

**Status:** DESIGN APPROVED. Phase C0 authorized and in progress. **Phases
C1–C5 are NOT authorized** — each requires a separate, explicit
"Approve Phase CN and begin implementation" from Roshan before work
starts, per standing LisaOS convention.

Every phase is additive only (new modules/tests). Nothing in `core/`,
`governance/`, `engines/`, or existing `registry/` schemas is modified by
any Console phase.

## Phase C0 — Scaffolding (in progress)

Create:
- `docs/GPT_CONTEXT/` (9 numbered files + README + CHANGELOG)
- `advisors/` package skeleton (no runtime behavior)
- `reports/console/` directories
- `docs/LISAOS/CONSOLE/` (this doc set)
- `.env.example` additions (no real secrets)

Deliver: directory structure, architecture documentation. No runtime
behavior. Stop for review.

## Phase C1 — Decision Bundle Exporter

Implement: `core/decision_bundle_exporter.py`, bundle schema
serialization, `bin/export-decision-bundle` CLI, tests.

Deliver: implementation report, test results, one sample bundle artifact.
Stop for review.

## Phase C2 — GPT Advisor

Implement: `advisors/context_pack.py`, `advisors/gpt_advisor.py`, OpenAI
API integration, Executive Brief generation, degraded-mode handling.

Deliver: implementation report, one sample brief, failure-path
validation (API-down case). Stop for review.

## Phase C3 — ntfy Notifications

Implement: `advisors/notify.py`, priority handling, single-attempt
delivery (no retry storm), audit logging.

Deliver: implementation report, notification examples, failure-path
validation. Stop for review.

## Phase C4 — Flask Console

Implement: all 9 screens (Dashboard, Jobs, Job detail, Workers,
Approvals, Approval detail, Brief, Reports, Audit), server-side rendered
only.

Deliver: screenshots, implementation report, route inventory. Stop for
review.

## Phase C5 — Hardening

Implement: Tailscale identity verification, authorization middleware,
full audit coverage, negative/security tests.

Deliver: security report, threat model validation (against
`04_SECURITY_MODEL.md`'s threat table), deployment checklist. **Stop for
CTO-role review before merge** (see Role Abstraction Principle,
`docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md`).

## Definition of Done (every phase)

- Acceptance criteria for that phase satisfied.
- Tests passing, including full existing suite (220/220 baseline)
  unchanged.
- Documentation updated (this doc set + `CHANGELOG.md`).
- Governance audit completed — no dispatcher bypass, no boundary
  crossing (`governance/GOVERNANCE.md`).
- **Architectural constraints validated** — no violation of
  `docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md` (GPT stays
  advisory-only, Console stays execution-incapable, dispatcher stays sole
  execution authority).
- **Role abstraction preserved** — no module branches on a hardcoded
  model name as a load-bearing dependency.
- **No new model coupling introduced** — any concrete model choice
  (e.g. which OpenAI model) remains a configuration value, not an
  architectural dependency.
- Human approval received before the next phase begins.
