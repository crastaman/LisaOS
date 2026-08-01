# LisaOS Documentation

LisaOS is the AI operating system, governance platform, orchestration layer, and reusable engineering platform for the BAR Technologies ecosystem.

## Recommended starting point

Start here:

1. [FOUNDATION_V3_COMPLETE.md](FOUNDATION_V3_COMPLETE.md) — Foundation v3 milestone declaration and core engineering principles.
2. [ECOSYSTEM.md](ECOSYSTEM.md) — BAR Technologies ecosystem architecture and repository ownership.
3. [MANIFEST.md](MANIFEST.md) — LisaOS purpose, scope, and canonical platform definition.
4. [KERNEL.md](KERNEL.md) — LisaOS Kernel architecture and operating model.
5. AGENTS.md — planned canonical agent and template catalogue.
6. CAPABILITIES.md — planned capability registry documentation.

Every architect, engineer, and AI agent should understand the ecosystem before reading the Manifest or Kernel.

## Current canonical documents

- [FOUNDATION_V3_COMPLETE.md](FOUNDATION_V3_COMPLETE.md)
- [ECOSYSTEM.md](ECOSYSTEM.md)
- [MANIFEST.md](MANIFEST.md)
- [KERNEL.md](KERNEL.md)
- [KERNEL_DECISIONS.md](KERNEL_DECISIONS.md)
- [KERNEL_REVIEW.md](KERNEL_REVIEW.md)
- [REPOSITORY_BOUNDARIES.md](REPOSITORY_BOUNDARIES.md)
- [L004_RELEASE_QA_PLAYBOOKS.md](L004_RELEASE_QA_PLAYBOOKS.md)
- [L005_L007_DESIGN_REVIEW.md](L005_L007_DESIGN_REVIEW.md)

## Constitutional governance layer — RATIFIED

The Phase 1 constitutional architecture document set (seven documents,
`CONSTITUTION/00`–`06`), at revision `2.0.0-proposed-r8`, frozen under annotated
tag `CONSTITUTION-V2-R8-PROPOSED` (commit `0fcc68a5531b6c811b7eeb279f1ce9035f4e7365`).
**Constitution v2 is ratified and is the governing constitutional authority of
Lisa OS.** Ratified by Roshan Crasta at `2026-08-01T11:22:38+04:00`, effective
1 August 2026, through the named human ratification record
`LISA-CONSTITUTION-V2-RATIFICATION-20260801-2E376D59` in `reports/lisa/ratification_records.jsonl` (Art. IX.3). The
pre-existing governance surfaces (`governance/GOVERNANCE.md`,
`governance/SECURITY.md`, `lisaos/policies/governance.yml`) survive as
subordinate instruments; none is repealed.

Independent review is no longer outstanding. The proposal has been through five
frozen revisions and four independent reviews (r5, r6, LCR-01, r7, r8), the last
returning **A — APPROVE R8 CANDIDATE FOR COMMIT**, followed by a freeze
continuity check returning **PASS**. All four reviews are preserved verbatim in
`CONSTITUTION/REVIEWS/`. **The ratification record is recorded in the ledger.**

### Ratification, history, and decision records

- [CONSTITUTION/RATIFICATION/V2_HUMAN_RATIFICATION_RECORD.md](CONSTITUTION/RATIFICATION/V2_HUMAN_RATIFICATION_RECORD.md) — the ratification instrument, prepared and **unexecuted**; carries the verification basis and the exact canonical ledger record for Roshan to complete and append.
- [CONSTITUTION/HISTORY.md](CONSTITUTION/HISTORY.md) — the constitutional timeline from conception through r8, the proposal freeze, and freeze continuity verification.
- [ADR/ADR-000-CONSTITUTION-RATIFICATION.md](ADR/ADR-000-CONSTITUTION-RATIFICATION.md) — root ADR: context, decision, consequences, governance impact, and the future amendment process. All future ADRs are subordinate to it.
- [CONSTITUTION/REVIEWS/V2_REVISION_EVIDENCE_INDEX.md](CONSTITUTION/REVIEWS/V2_REVISION_EVIDENCE_INDEX.md) — maps every cited r2–r8 revision basis to an immutable object, or records the original artifact as unavailable without reconstruction.
- [MILESTONES.md](MILESTONES.md) — governance complete pending ratification; implementation phase next.

- [CONSTITUTION/00_LISA_CONSTITUTION_V2.md](CONSTITUTION/00_LISA_CONSTITUTION_V2.md) — the proposed Constitution: authority ontology, roles, human-only powers, fail-closed and safe suspension, amendment procedure.
- [CONSTITUTION/01_AUTHORITY_MODEL.md](CONSTITUTION/01_AUTHORITY_MODEL.md) — source / instruments / actors; grant forms and properties; governed-dispatch origin of task authority; escalation protocol.
- [CONSTITUTION/02_PERMISSION_CONTRACTS.md](CONSTITUTION/02_PERMISSION_CONTRACTS.md) — worker permission contracts; role compatibility rules; canonical vs transitional registries.
- [CONSTITUTION/03_PROTECTED_ARTIFACTS.md](CONSTITUTION/03_PROTECTED_ARTIFACTS.md) — protected artifact classes P0–P4 and the amendment proposal area.
- [CONSTITUTION/04_AUDIT_AND_EVIDENCE.md](CONSTITUTION/04_AUDIT_AND_EVIDENCE.md) — evidence obligations and the six-condition independent-review validity test.
- [CONSTITUTION/05_THREAT_MODEL.md](CONSTITUTION/05_THREAT_MODEL.md) — actor-overreach threats T1–T17 (worker, orchestrator, evidence layer, and — from r4 — execution attribution, ungoverned entrypoints, and guard clearance) with verified enforcement status.
- [CONSTITUTION/06_SUBSTRATE_BINDING.md](CONSTITUTION/06_SUBSTRATE_BINDING.md) — clause-by-clause mapping onto the Gen 3 substrate (enforced / partial / norm-only).
- [CONSTITUTION/PROPOSALS/README.md](CONSTITUTION/PROPOSALS/README.md) — the P0 amendment proposal area and its rules.

## AI Workforce architecture (S024)

The AI Engineering Organisation design sprint. Start with the critique — it diagnoses why the workforce behaves like "one engineer + many DeepSeek helpers" and drives the other seven documents.

- [ARCHITECTURAL_CRITIQUE.md](ARCHITECTURAL_CRITIQUE.md) — first-principles critique, root-cause analysis, and the 12–24 month executive recommendation. **Read first.**
- [AI_WORKFORCE_FRAMEWORK.md](AI_WORKFORCE_FRAMEWORK.md) — organisation structure: durable roles, elastic worker instances.
- [MODEL_ASSIGNMENT_MATRIX.md](MODEL_ASSIGNMENT_MATRIX.md) — per-provider responsibilities, best/worst workloads, value, and cost.
- [CAPACITY_MANAGEMENT_STRATEGY.md](CAPACITY_MANAGEMENT_STRATEGY.md) — quota-aware scheduling; behaviour when Claude/Codex hit their limits.
- [COST_OPTIMISATION_REPORT.md](COST_OPTIMISATION_REPORT.md) — the two-currency cost model (perishable premium capacity + elastic API spend).
- [PARALLEL_EXECUTION_FRAMEWORK.md](PARALLEL_EXECUTION_FRAMEWORK.md) — decomposition-first parallel sprint framework.
- [DISPATCHER_ARCHITECTURE.md](DISPATCHER_ARCHITECTURE.md) — the Lisa Dispatcher fleet-scheduler design.
- [DAILY_OPERATING_FRAMEWORK.md](DAILY_OPERATING_FRAMEWORK.md) — the optimal engineering day and portfolio-scale operation.
  - [Release Pipeline](../../workflows/lisaos/release-pipeline.md)
  - [QA Standards](../../workflows/lisaos/qa-standards.md)
  - [WordPress Constraints](../../workflows/lisaos/wordpress-constraints.md)
  - [Migration Playbook](../../workflows/lisaos/playbooks/migration-playbook.md)
  - [Dual-Write Playbook](../../workflows/lisaos/playbooks/dual-write-playbook.md)
  - [Backfill Playbook](../../workflows/lisaos/playbooks/backfill-playbook.md)
  - [Runtime Verification Playbook](../../workflows/lisaos/playbooks/runtime-verification-playbook.md)

## Repository boundary

Canonical LisaOS documentation belongs in this repository:

```text
~/Lisa
```

Application-specific documentation belongs in each application repository. For WBS, the canonical application repository is:

```text
~/Projects/WBS/healing-events-booking
```

Cross-repository references should use pointers instead of duplicating canonical architecture.
