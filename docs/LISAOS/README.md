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
