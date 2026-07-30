# Worker Permission Contracts and Role Compatibility

> **STATUS: PROPOSED — PENDING HUMAN RATIFICATION**
>
> No constitutional force until recorded human ratification of Constitution v2
> (Art. IX.3). Revising this document does not ratify it.

| Field | Value |
|---|---|
| Status | PROPOSED — PENDING HUMAN RATIFICATION |
| Version | 2.0.0-proposed-r3 |
| Revision basis | r3 — enforcement-honesty remediation of the Claude Fable 5 advisory audit (BF-2: §3B no-downgrade protection is registry-contingent, not structural). That audit was **advisory** and does **not** satisfy the independent constitutional gate. Prior: r2 — remediation of author self-audit S044 (B1 transitional artifact access, B2 prohibition sources, A5 SoD labels, A6 superset staffing, A7 no silent downgrade, A9 probation evaluability) |
| Architecture phase | Phase 1 — Constitutional Governance Layer |
| Authority required for ratification | Roshan Crasta (human authority source) |
| Ratified by | *(pending)* |
| Ratification date | *(pending)* |
| Supersedes | None (new document) |
| Related evidence baseline | Phase 0 Reconnaissance Report (accepted 2026-07-30); full review of `registry/employees.yml`, `registry/agents.yml`, and the `WorkPackage` / `Employee` / `WorkAssignment` models in `core/workforce_resolver.py` (2026-07-30) |

---

## 1. The contract formula

A worker's effective permission at any moment is:

```
effective permission = capability ∩ live task grant ∩ artifact-class access − prohibitions
```

- **Capability** is descriptive: what the employee *can* do, declared in the
  canonical workforce registry. Capability alone permits nothing.
- The **live task grant** (WorkAssignment) is what the worker *may* do right
  now — one work package, nothing else.
- **Artifact-class access** limits which protected classes
  (`03_PROTECTED_ARTIFACTS.md`) the assignment may touch. No canonical
  registry declares this today; until one does, it is supplied by the
  transitional rule in §1.1.
- **Prohibitions** are absolute and non-overridable by any task grant. Their
  instrument sources are defined in §2A.

### 1.1 Transitional artifact-class access rule (expires automatically)

No canonical registry currently declares per-role artifact-class access.
Verified 2026-07-30: `registry/employees.yml` declares task capabilities only
and carries no artifact-access or prohibition field. Without a transitional
rule, default-deny would make every worker's permission set empty and no
governed work could proceed.

Until a canonical permission or system-role registry becomes operative, a
worker's artifact-class access is **derived, never granted wholesale**, from
the conjunction of:

1. the **active assignment** — only artifacts within the assigned work
   package's stated scope;
2. the **task scope** as described in that work package;
3. the worker's **declared capabilities** — a worker with no implementation
   capability derives no code-write access, and so on;
4. the **protected-artifact classification** of each target
   (`03_PROTECTED_ARTIFACTS.md`).

Derived access is bounded absolutely. Under this rule:

- **P0 canonical artifacts are never writable.** Proposed amendments only, and
  only in the proposal area (Constitution Art. IX.6–7).
- **P1 artifacts are not writable.** A P1 change requires an explicit episodic
  human grant plus independent review, and is never derived from an ordinary
  assignment.
- **P2 evidence is append-only through the owning component.** No worker
  writes a ledger directly.
- **Human-only acts are never derived** (Constitution Art. VIII.1), including
  release authorization.
- **Unclassified targets default to human-only pending classification**
  (Constitution Art. VIII.2).

This rule is deliberately narrow. It grants no repository-wide access, and the
absence of an explicit prohibition never widens it. Where the assignment does
not clearly place a target inside scope, access is denied and the worker
escalates (`01_AUTHORITY_MODEL.md` §6.2).

**Automatic expiry.** This rule ceases to have effect the moment a canonical
permission or system-role registry declaring per-role artifact access becomes
operative. It lapses by its own terms; no amendment or further act is needed
to retire it.

*Enforcement status: norm-only.* Nothing computes or restricts artifact-class
access. `WorkPackage` carries only `id`, `description`,
`required_capabilities`, `risk`, `mode`, and `depends_on` (verified
2026-07-30), so the substrate has no representation of artifact classes at
all. This clause defines an obligation on actors, not a runtime control.

## 2. Contract schema

Each employee's permission contract declares the following. Every field has a
defined instrument or constitutional source; none floats free.

| Field | Meaning | Instrument / constitutional source | Enforcement |
|---|---|---|---|
| `provides` | Capabilities the employee offers | Canonical workforce registry (`registry/employees.yml` → `capabilities`) | **Enforced** — capability-superset matching in the resolver/policy engine |
| `may_touch` | Artifact classes writable under an assignment | §1.1 transitional rule, until a canonical permission registry exists | **Norm-only** — no registry field, no runtime check |
| `prohibited` | Absolute prohibitions no task grant can override | §2A (constitutional, policy, canonical registry, or expressly adopted legacy) | **Norm-only** — constitutional prohibitions bind regardless of registry support |
| `escalation_duty` | When the worker must stop and escalate | Constitution Art. IV.3; `01_AUTHORITY_MODEL.md` §6.2 | **Norm-only** |
| `review_class` | Independent review required before acceptance | `04_AUDIT_AND_EVIDENCE.md` §5 | **Norm-only** |

## 2A. Where absolute prohibitions legally exist

The `prohibited` term has four possible sources, in precedence order. **A
prohibition is effective only if some authorized instrument adopts it.**

1. **Constitutional prohibitions.** Human-only powers (Art. VIII.1), the
   unclassified-action default (Art. VIII.2), the P0/P1 write rules, the
   non-transitivity of grants, and the separation-of-duties rules in §3.
   **These bind regardless of any missing registry field** — they need no
   registry support to be effective.
2. **Policy-level prohibitions.** Operational governance and security policy
   (`governance/GOVERNANCE.md`, `governance/SECURITY.md`,
   `lisaos/policies/governance.yml`) as P1 instruments subordinate to the
   Constitution.
3. **Canonical registry prohibitions** — once a canonical permission or
   system-role registry supports a prohibition field. **No such field exists
   today** (verified 2026-07-30: `registry/employees.yml` has none).
4. **Transitional legacy prohibitions, only where expressly adopted.**
   `registry/agents.yml` contains `prohibited_capabilities`, but that file is a
   transitional input and is **not** a constitutional or canonical authority
   source (§4). Its contents do **not** become authoritative merely by
   existing. A legacy prohibition binds only when a current authorized
   instrument — this Constitution, a policy, or an explicit grant — expressly
   adopts it; the adopting instrument, not the legacy file, is then its
   source.

Consequence: no constitutionally significant prohibition was lost by declining
to ratify the legacy registry, because every such prohibition is asserted at
level 1 or 2. What is currently unavailable is *per-role, machine-checkable*
prohibition — a registry capability, not a constitutional one.

*Enforcement status: norm-only at all four levels.* No mechanism evaluates any
prohibition. The nearest mechanical relatives are the probation restriction
and capability-superset matching (§3.5), which are **staffing filters, not
prohibitions** — they constrain who is assigned, not what an assigned worker
may then do.

## 3. Role compatibility and incompatibility

Separation-of-duties rules, per work package. These are constitutional
prohibitions (§2A level 1) and bind despite the absence of registry fields.
Each carries its verified enforcement status.

1. **Author ≠ reviewer.** The identity that produced an artifact may not
   review it. For P1 and security-class work the reviewer must additionally be
   of a different model family where technically available
   (`04_AUDIT_AND_EVIDENCE.md` §4).
   *Norm-only.* The registry expresses the intent as advisory hints —
   `cto-reviewer` carries `avoid_tasks: [authoring the artefact it reviews]`,
   `qa-engineer` carries `avoid_tasks: [authoring the implementation it
   tests]` — and these load into the `Employee` model, but no mechanism
   consults them when staffing.
2. **Planner ≠ implementer** on the same package. *Norm-only.*
3. **Security and architecture reviewers hold no repository-write authority.**
   *Norm-only.* Reviewer roles such as `cto-reviewer` declare only
   `[review, irreversible-judgement, security-review]`, but **capability
   absence in a registry is a staffing-match property, not a runtime write
   prohibition** — a staffed reviewer is not mechanically prevented from
   writing anything.
4. **Guard maintainer ≠ governed worker in the same sprint.** Whoever changes
   P1 governance-enforcing code cannot simultaneously be staffed on work that
   code is judging. *Norm-only.*
5. **Probation incompatibility.** *Partially enforced* — see §3.5.
6. **No self-staffing.** Workers never choose their own staffing; only
   governed dispatch staffs work. *Enforced.* The resolver and policy engine
   select the employee, and `core/dispatcher.py` exposes no code path by which
   a worker (or the orchestrator) stages its own package.

### 3.5 Probation incompatibility — what is evaluable today

**Mechanically enforced part:** a probation-flagged provider may staff **only**
`risk: low` work. Verified in `core/policy_engine.py` and
`core/workforce_resolver.py`: a probation provider is skipped whenever
`work_package.risk != "low"`.

**Norm-only extension:** probation models must additionally never staff work
touching P1 or P2 artifacts, or security-class work, regardless of risk label.
`WorkPackage` carries only `id`, `description`, `required_capabilities`,
`risk`, `mode`, and `depends_on` (verified 2026-07-30) — **no artifact-class or
work-class field exists**, so the runtime cannot evaluate this extension.
Classification is therefore supplied by the dispatching context: when
composing a package that touches P1/P2 or security-class work, the orchestrator
must set a non-low `risk`, which brings the package inside the enforced rule
above. Where the orchestrator cannot establish the classification, the package
is not dispatched on a probation-eligible chain and the question escalates.

This clause claims no runtime evaluation of fields the substrate does not
possess.

## 3A. Superset staffing confers no additional authority

The resolver selects an employee whose declared capabilities are a **superset**
of the package's required capabilities, choosing the lowest-seniority capable
candidate for cost discipline. A staffed worker therefore routinely holds
general capabilities exceeding what the active package requires.

- Staffing compatibility is **not** permission to use every capability the
  worker holds.
- Active authority remains limited to the assignment and its task grant (§1).
- Unused capabilities confer no authority, create no permission, and are never
  evidence that an action was in scope.

*Enforcement status: norm-only at runtime.* The intersection in §1 is a norm;
the superset match is what the substrate actually computes (verified in
`core/workforce_resolver.py` and `core/policy_engine.py`). This materially
raises the scope-creep risk recorded as threat T2.

## 3B. No silent downgrade of judgement-critical work

Architecture, security review, irreversible judgement, and constitutionally
protected review must not silently downgrade to a weaker role, model, or
authority class.

- Any permitted fallback must be explicit, recorded, and compatible with the
  required authority and independence class
  (`04_AUDIT_AND_EVIDENCE.md` §3–§4).
- Where no acceptable substitute exists, the package **halts and surfaces the
  reason** rather than proceeding on a lesser substitute (Constitution
  Art. VII.2(b)).
- A fallback that would defeat reviewer independence is not an acceptable
  substitute even when technically available.

*Enforcement status: partially enforced — registry-contingent.* The canonical
registry encodes this intent and today the behaviour holds, but **not** because
an empty fallback chain is structurally sufficient. Verified 2026-07-30 in
`core/workforce_resolver.py`: the resolver iterates *capable candidates* in the
outer loop (lowest-seniority first, via `candidates_for()`), and each
candidate's own model chain in the inner loop. Exhausting one candidate's chain
causes **escalation to the next capable candidate**, not a halt. The resolver
halts and surfaces only when every capable candidate is exhausted.

Current halt-and-surface behaviour for irreversible judgement is therefore a
**joint property** of four things, all of which must hold:

- resolver mechanics (candidate-outer / chain-inner, fail-closed on
  exhaustion);
- capability allocation — `irreversible-judgement` is currently carried only by
  `chief-architect` and `cto-reviewer`;
- candidate ordering — both are `principal`, so no lower-ranked worker is
  reachable ahead of them;
- current registry contents — both carry `fallback_models: []`.

An empty fallback chain **alone does not prevent** the resolver from selecting
another capable candidate. Granting `irreversible-judgement` to any
lower-seniority or weaker-model employee — an unauthorized or merely careless
edit to `registry/employees.yml` — would restore silent judgement downgrade
without any code change and without tripping any runtime check. That registry
mutation risk is threat **T3** (`05_THREAT_MODEL.md`), and the protection
consequently rests on the **norm-only P1 registry governance** of
`03_PROTECTED_ARTIFACTS.md` §1.

What is additionally **not** enforced: nothing checks that a permitted fallback
or candidate substitution preserves the required independence class, and
`failure_policy: halt-and-surface` is loaded into the `Employee` model without
any mechanism acting on it.

## 4. Registries: canonical vs transitional

This Constitution does **not** ratify `registry/agents.yml`. Phase 0
reconnaissance established it is superseded and awaiting retirement.

- **Future canonical system-role registry.** The standing-grant instrument
  for role definitions, prohibitions, and approval requirements is a future
  canonical system-role (authority-role) registry. The useful concepts in the
  legacy file — prohibited capabilities, approval levels — are carried
  forward into this contract schema and that future registry, not inherited
  by ratifying the legacy file. Designing that registry is outside this
  phase's scope.
- **Current canonical instruments (P1):** `registry/employees.yml`,
  `registry/provider_resolution.yml`, `registry/workforce_modes.yml` — the
  operative workforce, provider, and mode registries of the Gen 3 substrate.
- **Transitional inputs only:** `registry/agents.yml`, `registry/runtimes.yml`
  (and other superseded surfaces). Readable for continuity; constitutionally
  granting nothing; retirable without constitutional amendment. Their
  prohibitions bind only when expressly adopted (§2A level 4).

## 5. Contract change rules

Because registries are standing-grant instruments, editing a canonical
registry is an authority change, not configuration: it requires an explicit
episodic human grant plus independent review (P1 rule), and is never bundled
into ordinary feature work. "Hiring a model = editing this file" therefore
becomes a human-granted act. *Enforcement status: norm-only — the files are
ordinarily writable (threat T3).*
