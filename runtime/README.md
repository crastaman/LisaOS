# LisaOS Runtime Framework

**Sprint:** L003-LISAOS-RUNTIME-EXECUTION-FRAMEWORK  
**Status:** Documentation-only foundation  
**Runtime behaviour:** Unchanged

The runtime framework defines the minimal path future LisaOS jobs should follow when moving from a job packet to a validated and approved result.

It does not implement autonomous orchestration, provider execution, scheduling, Telegram integration, memory engine behaviour, cloud workers, or GLM integration.

## Minimal execution path

```text
Job
↓
Job Type
↓
Default Agent
↓
Required Capabilities
↓
Runtime Profile
↓
Fallback Runtime
↓
Validation
↓
Approval
```

## Framework areas

- `runtime/resolver/` — future resolution rules and decision order.
- `runtime/providers/` — future provider abstraction documentation.
- `runtime/health/` — future runtime health and availability checks.
- `runtime/adapters/` — future adapter boundary documentation.

## Canonical registries

The framework depends on existing registry metadata:

- `registry/jobs.yml` for job type defaults.
- `registry/agents.yml` for agents, runtime profiles, fallback runtimes, approval level, and artifacts.
- `registry/capabilities.yml` for capability names and risk metadata.
- `registry/runtimes.yml` for runtime candidates and runtime profiles.

## Non-goals

L003 does not execute jobs, select models, call providers, modify OpenClaw, or change application repositories.
