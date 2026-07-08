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

## Phase C1 — Decision Bundle Exporter (IMPLEMENTED, stopped for review)

Implemented: `core/decision_bundle_exporter.py`, `bin/export-decision-bundle`
CLI, `tests/test_decision_bundle_exporter.py` (15/15 passing). Landed on
`feature/lisa-console` (branched off the Phase C0 commit on
`fix/provider-resolution`), not on the shared branch, to keep Console
history separable from unrelated in-progress work already sitting there.

Real-data grounding surfaced during implementation: LisaOS job packets
are documentation-only (no live job-packet store exists anywhere in the
repo). The exporter keys on the real, running identifier —
`work_package_id` in `reports/lisa/workforce_evidence.jsonl` — and is
explicit in every bundle's `job_id_source_note` and `gaps` fields about
what it could and couldn't automatically populate. See
`01_DECISION_BUNDLE_SPEC.md` for the full, revised spec and
`examples/sample_bundle.json` for a worked example.

Deliver: implementation report, test results, one sample bundle artifact.
Stop for review. **Awaiting explicit approval before Phase C2.**

## Phase C2 — GPT Advisor (IMPLEMENTED, stopped for review)

Implemented: `advisors/context_pack.py`, `advisors/openai_client.py`
(stdlib `urllib`, no new dependency), `advisors/gpt_advisor.py`,
`tests/test_context_pack.py`, `tests/test_openai_client.py`,
`tests/test_gpt_advisor.py` (34/34 passing). Landed on `feature/lisa-console`.

Verified, not just documented: zero `core`/`engines` imports anywhere in
`advisors/` (grepped); the bundle read path is proven read-only by a test
that `chmod`s the bundle file/directory read-only before generating a
brief from it; the API key never reaches a log, exception, bundle, or
brief (asserted in tests). Executive Brief field names were revised from
the C0-era draft (`risk_flags`/`open_questions`) to match this phase's
explicit requirements (`key_risks`/`missing_information`/
`suggested_actions`/`escalation_recommendation`) — see
`02_GPT_ADVISOR_SPEC.md`.

Deliver: implementation report, one sample brief, failure-path
validation (API-down case). Stop for review. **Awaiting explicit approval
before Phase C3.**

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
