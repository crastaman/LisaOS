# L001 Registry Foundation

**Sprint:** L001  
**Governance refinement:** L001.5  
**Repository:** `~/Lisa`  
**Scope:** Foundational LisaOS registry files only.

## Purpose

L001 began LisaOS implementation by establishing the first canonical registry foundation.

The goal is to make LisaOS concepts explicit and machine-readable before deeper runtime, routing, agent, or workflow implementation begins.

This sprint creates initial registries for:

- agents
- capabilities
- runtimes
- job types

No runtime behaviour is changed. No OpenClaw behaviour is changed. No WBS files are modified.

## Files created

```text
registry/agents.yml
registry/capabilities.yml
registry/runtimes.yml
registry/jobs.yml
docs/LISAOS/L001_REGISTRY_FOUNDATION.md
```

## L001.5 governance refinement

L001.5 strengthened the registry model without redesigning the architecture or changing runtime behaviour.

The registry foundation now includes:

- registry-level metadata:
  - `name`
  - `version`
  - `schema`
  - `last_updated`
  - `owner`
  - `status`
- object-level lifecycle status:
  - `active`
  - `experimental`
  - `deprecated`
  - `disabled`
- object-level canonical ownership through `owner`
- object-level `policy_profile`
- agent dependency support through `depends_on`
- runtime abstraction support through `runtime_profile`

Current registry version begins at `1.0.0`.

## Registry philosophy

LisaOS registries should be:

- canonical inside `~/Lisa`
- explicit enough for humans and agents to inspect
- safe by default
- capability-aware
- model-agnostic
- repository-boundary aware
- policy-injection ready
- extensible without schema redesign for normal growth
- suitable for future automation without requiring immediate runtime integration

The registries define intent before enforcement. Future sprints can add resolvers, validators, health checks, routing, scheduling, and adapters.

## Registry responsibilities

### `registry/agents.yml`

Defines the initial LisaOS system agents and reusable templates.

System agents represent OS-owned responsibilities such as planning, routing, memory, security, and release coordination.

Templates represent reusable agent patterns that applications instantiate through project policy injection.

The registry now also records lifecycle status, canonical owner, policy profile, dependency relationships, and runtime profile abstraction.

### `registry/capabilities.yml`

Defines OS-level capabilities as primitives.

Capabilities are not templates. They describe what classes of action are possible, their risk level, whether human approval is required, lifecycle status, owner, and policy profile.

### `registry/runtimes.yml`

Defines runtime placeholders only.

This registry names model/provider roles without including API keys, credentials, secrets, or provider configuration.

L001.5 adds `runtime_profile` so future routing can target abstract profiles such as `planning-runtime`, `review-runtime`, `implementation-runtime`, and `governance-runtime` without hard-coding vendor-specific runtime IDs.

### `registry/jobs.yml`

Defines initial job types and default routing expectations.

Job types connect work categories to default agents, capability requirements, validation expectations, approval requirements, output artifacts, lifecycle status, owner, and policy profile.

## Connection to the Kernel

The LisaOS Kernel defines the operating model for governance, orchestration, routing, capabilities, runtime selection, memory, and workflow execution.

L001 turns the Kernel concepts into the first registry layer:

- Kernel agent model → `registry/agents.yml`
- Kernel capability model → `registry/capabilities.yml`
- Kernel runtime model → `registry/runtimes.yml`
- Kernel job/workflow model → `registry/jobs.yml`

L001.5 strengthens this layer so future Kernel implementation work can depend on stable registry metadata and governance fields.

These files are the foundation for future resolver and orchestration work, but they do not yet enforce behaviour.

## Next sprint recommendation

Recommended next sprint:

**L002 — Registry Validation and Resolver Design**

Suggested scope:

1. Add schema documentation for each registry.
2. Add a read-only validation script for YAML shape and required keys.
3. Define resolver rules for selecting agents, runtimes, and capabilities.
4. Add governance checks for repository, branch, target path, and output verification.
5. Define policy profile semantics and project policy injection rules.
6. Keep runtime behaviour unchanged until the resolver is reviewed and approved.
