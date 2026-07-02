# L001 Registry Foundation

**Sprint:** L001  
**Repository:** `~/Lisa`  
**Scope:** Foundational LisaOS registry files only.

## Purpose

L001 begins LisaOS implementation by establishing the first canonical registry foundation.

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

## Registry philosophy

LisaOS registries should be:

- canonical inside `~/Lisa`
- explicit enough for humans and agents to inspect
- safe by default
- capability-aware
- model-agnostic
- repository-boundary aware
- suitable for future automation without requiring immediate runtime integration

The registries define intent before enforcement. Future sprints can add resolvers, validators, health checks, routing, and adapters.

## Registry responsibilities

### `registry/agents.yml`

Defines the initial LisaOS system agents and reusable templates.

System agents represent OS-owned responsibilities such as planning, routing, memory, security, and release coordination.

Templates represent reusable agent patterns that applications instantiate through project policy injection.

### `registry/capabilities.yml`

Defines OS-level capabilities as primitives.

Capabilities are not templates. They describe what classes of action are possible, their risk level, and whether human approval is required.

### `registry/runtimes.yml`

Defines runtime placeholders only.

This registry names model/provider roles without including API keys, credentials, secrets, or provider configuration.

### `registry/jobs.yml`

Defines initial job types and default routing expectations.

Job types connect work categories to default agents, capability requirements, validation expectations, approval requirements, and output artifacts.

## Connection to the Kernel

The LisaOS Kernel defines the operating model for governance, orchestration, routing, capabilities, runtime selection, memory, and workflow execution.

L001 turns the Kernel concepts into the first registry layer:

- Kernel agent model → `registry/agents.yml`
- Kernel capability model → `registry/capabilities.yml`
- Kernel runtime model → `registry/runtimes.yml`
- Kernel job/workflow model → `registry/jobs.yml`

These files are the foundation for future resolver and orchestration work, but they do not yet enforce behaviour.

## Next sprint recommendation

Recommended next sprint:

**L002 — Registry Validation and Resolver Design**

Suggested scope:

1. Add schema documentation for each registry.
2. Add a read-only validation script for YAML shape and required keys.
3. Define resolver rules for selecting agents, runtimes, and capabilities.
4. Add governance checks for repository, branch, target path, and output verification.
5. Keep runtime behaviour unchanged until the resolver is reviewed and approved.
