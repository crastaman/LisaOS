# Lisa Console — Changelog

## 2026-07-08 — Design approved; Phase C0 scaffolding

- Architecture design approved by Roshan (8-deliverable design review:
  Architecture, Decision Bundle Spec, GPT Advisor Spec, ntfy Spec,
  Security Model, UI/Screens Spec, Implementation Plan, Test Plan).
- Design baseline updated before implementation start: GPT Context Pack
  renumbered `01_SYSTEM_ROLE.md`–`09_ARCHITECTURAL_CONSTRAINTS.md`;
  `09_ARCHITECTURAL_CONSTRAINTS.md` added as the constitutional layer;
  Role Abstraction Principle (Planner/Builder/Reviewer/Auditor/CTO/
  Operator as platform roles, not model assignments) documented; Phase
  C0–C5 Definition of Done extended with architectural-constraints and
  role-abstraction checks.
- Phase C0 scaffolding created: `docs/GPT_CONTEXT/`, this doc set
  (`docs/LISAOS/CONSOLE/`), `advisors/` package skeleton (no runtime
  behavior), `reports/console/` directories, `.env.example` additions.
  No executable Console code yet — that begins Phase C1.

## 2026-07-08 — Phase C1: Decision Bundle Exporter

- Implemented `core/decision_bundle_exporter.py`, `bin/export-decision-bundle`,
  `tests/test_decision_bundle_exporter.py` (15/15 passing), on new branch
  `feature/lisa-console`.
- Real-data grounding: LisaOS job packets are documentation-only — no
  live job-packet store exists. The exporter keys bundles on the real,
  running `work_package_id` identifier from `workforce_evidence.jsonl`
  and records the mapping explicitly (`job_id_source_note`), plus a
  `gaps` array on every bundle listing what could not be automatically
  populated and why.
- `01_DECISION_BUNDLE_SPEC.md` rewritten to match the real, implemented
  schema. Added `docs/LISAOS/CONSOLE/examples/sample_bundle.json`
  (synthetic worked example).
- No changes to `core/dispatcher.py`, `core/workforce_resolver.py`,
  `engines/*`, or any `registry/*.yml` schema. Full existing test suite
  unaffected. Phase C2 (GPT Advisor) is NOT authorized.
