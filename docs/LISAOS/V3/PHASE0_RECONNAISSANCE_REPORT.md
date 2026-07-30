# Phase 0 Reconnaissance Report — Preserved Historical Artifact

> **PROVENANCE HEADER — NOT PART OF THE ORIGINAL REPORT**
>
> Everything below the horizontal rule that closes this header is a **faithful,
> verbatim transcription** of the Lisa OS Phase 0 Reconnaissance Report exactly
> as produced during the Phase 0 architecture sprint.
>
> **Origin.** The report was produced in the project conversation and existed
> **only** there. It was never written to a file and never committed to this
> repository.
>
> **Why it is being preserved now.** Constitution v2 evidence validation
> identified that this artifact — cited as the "Related evidence baseline"
> (*"Phase 0 Reconnaissance Report (accepted 2026-07-30)"*) in the metadata
> block of every document in `docs/LISAOS/CONSTITUTION/` — had never been
> committed and therefore could not be produced for an independent reviewer.
> The independent constitutional review conducted by OpenAI Codex failed
> condition 3 of the six-condition validity test in
> `04_AUDIT_AND_EVIDENCE.md` §3 ("Evidence baseline access") on exactly this
> ground. This file exists to close that evidentiary gap by preserving the
> historical artifact itself.
>
> **Fidelity statement.** **No substantive content below this header has been
> altered.** Nothing was rewritten, improved, summarized, modernized, or
> reinterpreted. Obsolete observations, historical statements that no longer
> match the current implementation, grammar, wording, terminology, section
> numbering, and figures are all preserved as written. Statements below are
> accurate **as of the Phase 0 sprint** and are **not** reconciled with any
> later revision of the codebase or the Constitution.
>
> **Formatting accommodations (presentation only, no character of content
> changed).** Three, disclosed in full:
> 1. The report title and the nine numbered section titles are rendered as
>    Markdown headings. Their text is unchanged. This is required because
>    lines such as `1. Repository map` would otherwise be parsed as ordered
>    list items and **renumbered by the renderer**, which would violate the
>    instruction not to renumber sections.
> 2. The box-drawing repository-map table is enclosed in a fenced code block so
>    its original alignment survives rendering. Its characters are unchanged.
> 3. The ASCII resolution-chain diagram in §2 is enclosed in a fenced code block
>    for the same reason. Its characters are unchanged.
>
> No other change of any kind was made.
>
> | Field | Value |
> |---|---|
> | Artifact | Lisa OS Phase 0 Reconnaissance Report |
> | Original medium | Project conversation (uncommitted) |
> | Sprint | Architecture Sprint, Phase 0 |
> | Baseline acceptance date as cited by Constitution v2 | 2026-07-30 |
> | Transcribed to repository | 2026-07-30 |
> | Transcription type | Verbatim historical preservation |
> | Artifact class | P4 — reports & docs (`03_PROTECTED_ARTIFACTS.md` §1) |
> | Status | Historical evidence. Not a current architectural statement. |

---

# Lisa OS — Reconnaissance Report (Architecture Sprint, Phase 0)

Method: read-only survey of ~/Lisa on branch feature/lisa-console. Nothing was modified, deleted, or created. Full test suite executed once as evidence (read-only side effects only): 442/442 tests pass via python -m unittest discover (pytest is not installed).

---

## 1. Repository map

~280 tracked/untracked project files (plus a .venv). Top-level layout:

```
┌──────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┬──────────────────┐
│                   Area                   │                                                                                         Contents                                                                                          │      Status      │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ core/                                    │ The implemented LisaOS 3.0 engine: provider_resolver, workforce_resolver, dependency_graph, dispatcher, policy_engine, workforce_modes, capacity_ledger, anti_regression,                 │ Live, tested     │
│                                          │ governance_guard, openclaw_bridge, decision_bundle_exporter + legacy lisa_core/planner/router/aggregator                                                                                  │                  │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ registry/                                │ employees.yml, provider_resolution.yml, workforce_modes.yml (current) + agents.yml, runtimes.yml, capabilities.yml, jobs.yml (legacy, marked superseded) + agents.json (a third,          │ Mixed            │
│                                          │ WBS-report-oriented agent map)                                                                                                                                                            │ generations      │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ engines/                                 │ claude.py, codex.py, gpt.py, openclaw.py — subprocess-based Engine classes for the Gen-1 router                                                                                           │ Legacy           │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ console/, advisors/                      │ Lisa Console v1 (Flask, observational/advisory-only, approve/reject only) + GPT advisor                                                                                                   │ Merged to main   │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ bin/                                     │ 12 entry points: lisa-dispatch, lisa-workforce, lisa-resolve, lisa-governance-check, console-preflight, export-decision-bundle, etc.                                                      │ Live             │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ tests/                                   │ 22 test modules, 442 tests, all green                                                                                                                                                     │ Live             │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ docs/LISAOS/                             │ Canonical docs + L-series + V3/ (34 docs) + CONSOLE/ (19 docs) + 8 untracked S024 docs                                                                                                    │ See §3           │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ docs/ARCHITECTURE/, docs/ADR/            │ Gen-1 "Lisa Core v1" architecture + only 2 ADRs (engine abstraction, capability routing)                                                                                                  │ Legacy           │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ lisaos/                                  │ Docs-era scaffolding: policies (governance.yml, routing.yml), runtime role registry, sprint state (sprints/current.yml, showing WBS sprint S005), packet rules, Lisa identity/soul/tools  │ Partially        │
│                                          │                                                                                                                                                                                           │ superseded       │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ governance/, identity/, bootstrap/,      │ Governance rules (13), Lisa identity, bootstrap prompt, Lisa Workflow + WBS playbooks                                                                                                     │ Live governance  │
│ workflows/                               │                                                                                                                                                                                           │                  │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ jobs/, skills/, capabilities/, agents/   │ Job specs as markdown, Gen-1 skill YAMLs, capability descriptions, agent template READMEs                                                                                                 │ Docs-only        │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ reports/                                 │ Audit trail: forensic audits, phase reports, CTO reviews, workforce_evidence.jsonl (55 records), console audit log                                                                        │ Evidence         │
├──────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────┤
│ memory/, knowledge/*, configs/, src/,    │ Empty scaffolding directories                                                                                                                                                             │ Unbuilt          │
│ logs/, prompts/                          │                                                                                                                                                                                           │                  │
└──────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┴──────────────────┘
```

Branch state (important): main already contains the Console v1 merge (8c47142). The current branch feature/lisa-console is 3 ahead / 3 behind main — its 3 unique commits are the OpenClaw execution bridge + governance hardening + deterministic execution identity (1fc4014, e0aba10, 6fbb6dd), which are not on main. The branch name no longer matches its content.

## 2. Architecture map

The repo contains three architectural generations coexisting, plus one adjacent subsystem:

Gen 1 — "Lisa Core v1" (docs/ARCHITECTURE, ADR-0001/2, core/lisa_core.py, engines/, skills/*.yaml): skill → planner → choose_engine → subprocess engine. Explicitly marked "LEGACY ROUTING LAYER (superseded)" in core/router.py:19.

Gen 2 — "LisaOS v2/v3 Foundation" (MANIFEST, KERNEL, L001–L007, registry/agents.yml+runtimes.yml, lisaos/ policies): a documentation-defined kernel — job queue, scheduler, context loader, capability security, runtime selection policy. Largely never implemented as code: jobs/queue.yml/active.yml/completed.yml from KERNEL §3.1 do not exist; job packets are "documentation-only today" (stated plainly in core/decision_bundle_exporter.py:18-24).

Gen 3 — "LisaOS 3.0 Workforce Intelligence" (the live system). Resolution chain, implemented and enforced in code:

```
Goal → DependencyGraph → ready frontier → PolicyEngine (mode + capacity-ledger filters)
     → WorkforceResolver (capability → lowest-seniority employee → preferred/fallback model)
     → ProviderResolver (logical → physical model+runtime, credential-checked, fail-closed)
     → OpenClawBridge (physical model → dedicated 1:1 OpenClaw agent identity, live-discovered)
     → evidence record (reports/lisa/workforce_evidence.jsonl)
```

Key invariants, all structurally enforced and test-covered: fail-closed (never a silent DeepSeek fallback), main never executes worker packages (the L2/L3 "firewall"), subscription-before-API admission, GLM probation → low-risk only, explicit recorded fallbacks, 17 anti-regression gates.

Adjacent — Lisa Console v1: Flask, Tailscale-identity auth, strictly observational; the only write is approve/reject on an exported decision bundle. Verified to import no dispatch code.

The stack runs on top of OpenClaw as the execution platform (Lisa = orchestration, OpenClaw = runtimes/agents), with the bridge as the only governance-authoritative dispatch path.

## 3. Documentation inventory

Authoritative (per docs/LISAOS/README.md + V3 closure):
- FOUNDATION_V3_COMPLETE.md, ECOSYSTEM.md, MANIFEST.md, KERNEL.md, KERNEL_DECISIONS.md, KERNEL_REVIEW.md, REPOSITORY_BOUNDARIES.md, L004, L005_L007 review
- docs/LISAOS/V3/ (00–33 + phase reports + closure) — the design and record of the implemented system; status "CORE COMPLETE — MAINTENANCE MODE" (2026-07-08)
- docs/LISAOS/CONSOLE/ — complete Console v1 spec set
- governance/GOVERNANCE.md (13 rules), workflows/LISA_WORKFLOW.md

Candidate artefacts (untracked, the "not clean" state): the 8 S024 AI-Workforce docs dated 2026-07-06 (ARCHITECTURAL_CRITIQUE, AI_WORKFORCE_FRAMEWORK, MODEL_ASSIGNMENT_MATRIX, CAPACITY_MANAGEMENT_STRATEGY, COST_OPTIMISATION_REPORT, PARALLEL_EXECUTION_FRAMEWORK, DISPATCHER_ARCHITECTURE, DAILY_OPERATING_FRAMEWORK) plus the README section indexing them and GUIDES/GLM_USAGE_POLICY.md. These are load-bearing but uncommitted: the committed V3 docs explicitly cite them ("Builds on: S024 architecture", V3/00 cites COST_OPTIMISATION_REPORT.md). The critique's diagnosis (two-currency economics, roles-baked-into-providers, DeepSeek monoculture) is the direct intellectual parent of the shipped code.

Uncommitted registry change: registry/agents.yml — mostly a YAML reformat, but with two semantic edits: fixes dangling fallback glm-builder-future → glm-builder-trial (only the latter exists in runtimes.yml) and adds a new wbs-builder-glm trial agent — into the superseded legacy registry.

Duplicates/conflicts:
1. Three agent/routing registries: registry/employees.yml (current), registry/agents.yml+runtimes.yml (superseded but still being edited), registry/agents.json + lisaos/runtime/registry.yml (Gen-1/2 remnants, mutually inconsistent runtime names: kimi, qwen, ollama appear only there).
2. KERNEL.md vs reality: describes a file-based job queue, lisa-job-create.sh, and AGENTS.md/CAPABILITIES.md context loading — none exist. KERNEL is not marked superseded, yet V3 supersedes its scheduler/routing sections.
3. L005 runtime-selection policy vs V3: cost-tier Rule 3 was formally rejected by the S024 critique and replaced, but LISAOS_RUNTIME_SELECTION_POLICY.md carries no superseded banner (unlike runtimes.yml, which does this correctly).
4. Test-count drift: closure report baselines "220/220"; the suite is now 442 (console + bridge tests added after closure).

Missing documents referenced as canonical: docs/LISAOS/AGENTS.md and docs/LISAOS/CAPABILITIES.md — listed as "planned" in the README start-here list and referenced by KERNEL's context loader; never written.

## 4. Current governance summary

- Human authority: Roshan holds vision, ethics, approvals; lisaos/policies/governance.yml lists 9 change classes requiring GPT-or-Roshan approval (architecture, schema, payments, destructive ops…) vs auto-allowed routine work.
- Rules 12–13 (post-hardening): all delegated production work MUST flow through core/dispatcher.py → core/workforce_resolver.py; the bridge is the sole authoritative attribution source; manual TUI dispatch is non-authoritative. Bypass = governance violation requiring attributed operator acknowledgement via bin/lisa-governance-check.
- Enforcement reality: governance_guard.py detects but cannot prevent bypasses (native subagent spawns happen outside its process boundary) — detection + fail-closed acknowledgement gating is the compensating control.
- Maintenance-mode freeze (closure report): LisaOS development frozen except bug fixes, regressions, and WBS-driven need; archived roadmap items are explicitly not to be resurrected speculatively.
- Repository boundary discipline: LisaOS work in ~/Lisa, WBS in ~/Projects/WBS/healing-events-booking; wbs-prefixed OpenClaw agents are excluded from LisaOS dispatch by the bridge.
- Console governance: approve/reject only; every access audited; Tailscale identity allowlist.

## 5. Current delegation model

Employee-before-model, capability-before-provider (§2 chain). Specifics:
- Staffing: capability-superset match → lowest-seniority capable employee (cost discipline); seniority ranks microtask(1)→principal(6). ~15 roles across departments (office-of-cto, etc.); chief-architect/cto-reviewer pin to Opus with no fallback (halt-and-surface — judgement is never downgraded).
- Modes: 9 workforce modes as data (economy/balanced/premium/overnight/…) re-binding eligibility and cost policy; an empty allowed_employees list fails closed by design.
- Economics: two-currency model — perishable subscription capacity (Claude/Codex OAuth) spent first; elastic API spend (DeepSeek/Qwen-DeepInfra) fills the rest; Haiku added as subscription-cheap microtask worker.
- Execution: the bridge maps resolved physical model → the dedicated 1:1 OpenClaw agent identity (lisa-claude-opus, lisa-deepseek, lisa-qwen…), discovered live — because OpenClaw rejects --model overrides. Fails closed if no non-WBS agent matches.
- Known residual gap (CTO review, 2026-07-09): Qwen→DeepSeek substitution persists only on the legacy manual main-TUI path; the bridge fixes it. Codex ≡ openai/gpt-5.5 by registry definition — a modelling/labelling issue, not a routing defect.

## 6. Current strengths

1. The scheduling layer is real, not aspirational — implemented, 442 green tests, evidence-bearing (55 workforce-evidence records), with proof-of-work tests run against the shipped registries.
2. Fail-closed discipline is pervasive and consistent across resolver, ledger, graph, modes, and bridge — the DeepSeek-monoculture root cause is structurally eliminated on the governed path.
3. Registry-as-data: hiring a model = editing YAML; verified no orchestration-code coupling.
4. Exceptional audit culture: forensic audits, adversarial CTO reviews that verify prior audits against the OpenClaw SQLite ground truth, honest defect reports (e.g., the Phase 1–3 "simulated executor" admission).
5. Anti-regression gates codify past failures (F1–F8 + phase-specific) as executable checks.
6. Clean safety separation in the Console (advisory-only, verified no dispatch imports).
7. Artifact-first communication, fresh-session isolation, and repository boundaries — the substrate the S024 critique itself flagged as worth preserving.

## 7. Current weaknesses

1. Three routing generations coexist; the superseded agents.yml is still receiving semantic edits (uncommitted wbs-builder-glm), so the legacy layer is not actually frozen.
2. Documentation drift at the canonical tier: KERNEL.md and L005 describe rejected/unbuilt mechanisms without superseded banners; the README start-here list points at two documents that don't exist.
3. Load-bearing docs are untracked: the committed V3 record cites S024 documents that exist only in the working tree — a git clean would sever the design lineage.
4. Branch/merge incoherence: main has the Console but lacks the execution bridge and governance hardening (the 3 commits unique to feature/lisa-console); commit 5b46800 records "decision not to merge yet" while main's 8c47142 says "Merge Lisa Console v1 into main".
5. Governance is detective, not preventive, for the highest-risk bypass (native subagent spawns); the legacy TUI path still silently substitutes DeepSeek (Defect B, unfixed by design on that path).
6. No temporal quota introspection yet — the capacity ledger records observed exhaustion but cannot see actual window/weekly reset clocks (records "unknown" honestly).
7. No learning loop (L5), no dynamic main runtime (MAIN-001), no sprint metrics ledger — all consciously archived, but they were the "keep the workforce busy" payoff of the design.
8. Dead scaffolding (memory/, knowledge/*, configs/, src/, logs/) and stale state (lisaos/sprints/current.yml frozen at WBS S005); no pytest/CI harness — tests run only via ad-hoc unittest discovery.

## 8. Missing architectural components

- Job/packet materialization: no queue, no packet files; decision bundles substitute work_package_id for a job ID and say so explicitly.
- AGENTS.md / CAPABILITIES.md (canonical catalogue referenced by KERNEL's context loader).
- Memory system (directory exists, empty; "durable memory" currently = git-tracked docs only).
- Quota Monitor with real reset timestamps (CAPACITY_MANAGEMENT_STRATEGY's GREEN/AMBER/RED model — only the ledger half exists).
- Learning loop (V3 L5), dynamic main runtime, sprint scorecards — designed, archived, unbuilt.
- Legacy retirement plan execution (runtimes.yml/router marked "scheduled for retirement in a later phase" — no phase defined).
- ADR trail for Gen 3: only two Gen-1 ADRs exist; every V3 decision lives in reports/design docs rather than ADRs.
- CI / test-runner definition (no pytest, no CI config, no documented test entry point).

## 9. Questions requiring clarification

1. The untracked S024 docs — commit as-is (they're already cited by committed docs), or are they still under review? This is the main "repository not clean" decision.
2. The uncommitted registry/agents.yml change — is the wbs-builder-glm trial agent still wanted, given (a) the registry is superseded, (b) GLM policy restricts it to scout tasks, and (c) WBS agents are excluded from LisaOS dispatch by the bridge?
3. Branch disposition — should feature/lisa-console's three bridge/hardening commits be merged to main (main currently lacks the authoritative execution path that governance rules 12–13 mandate)? And which record stands: "not to merge yet" (5b46800) or the actual Console merge on main?
4. Sprint mandate vs freeze — the closure report freezes LisaOS work except bug/regression/WBS-need. Under which category does this architecture sprint operate, and does it license reopening archived items (learning loop, MAIN-001, legacy retirement)?
5. Canonical doc policy — should KERNEL.md/L005 be brought in line with implemented reality (or banner-marked superseded), and are AGENTS.md/CAPABILITIES.md still planned?
6. Codex identity — keep codex ≡ openai/gpt-5.5 (accepting the label collapse) or model Codex as a distinct provider?
7. Agent-registry convergence — is employees.yml intended to become the sole agent/role registry, retiring agents.yml, agents.json, and lisaos/runtime/registry.yml?
8. Empty scaffolding (memory/, knowledge/, src/, configs/) — reserved for future architecture, or candidates for removal in a later cleanup phase?
