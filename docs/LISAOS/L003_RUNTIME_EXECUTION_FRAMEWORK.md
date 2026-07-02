# L003 Runtime Execution Framework

**Job ID:** L003-LISAOS-RUNTIME-EXECUTION-FRAMEWORK  
**Repository:** `~/Lisa`  
**Scope:** Minimal runtime and execution framework documentation.  
**Runtime behaviour:** Unchanged.

## Purpose

L003 creates the lightweight LisaOS runtime and execution framework needed to route future jobs consistently.

The sprint defines documentation and schema surfaces only. It does not build autonomous orchestration, Telegram integration, scheduler behaviour, memory engine behaviour, cloud features, GLM integration, provider calls, or OpenClaw runtime changes.

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

## Files created

```text
runtime/README.md
runtime/resolver/README.md
runtime/providers/README.md
runtime/health/README.md
runtime/adapters/README.md
jobs/README.md
jobs/schema.yml
jobs/examples/wbs-qa-pilot.yml
workflows/lisaos/execution-flow.md
docs/LISAOS/L003_RUNTIME_EXECUTION_FRAMEWORK.md
```

## Relationship to L001 registry foundation

L003 depends on the registry foundation created in L001 and refined in L001.5:

- `registry/jobs.yml` defines job types and default agents.
- `registry/agents.yml` defines agents, runtime profiles, fallback runtimes, approval levels, and output artifacts.
- `registry/capabilities.yml` defines capability names, risks, and approval implications.
- `registry/runtimes.yml` defines runtime IDs and runtime profile metadata.

## Relationship to L002 agent framework

L003 references the L002 agent framework under `agents/`.

Before future execution can use an agent, the corresponding README should exist under:

- `agents/system/<agent-id>/README.md`
- `agents/templates/<template-id>/README.md`

L003 validation verifies these folders exist before relying on them.

## Job packet schema

`jobs/schema.yml` defines a model-agnostic packet shape with:

- `job_id`
- `target_repository`
- `job_type`
- `priority`
- `requested_by`
- `objective`
- `context_files`
- `required_capabilities`
- `prohibited_capabilities`
- `preferred_agent`
- `validation_required`
- `approval_required`
- `output_artifacts`
- `repository_boundary_check`
- `status`

## Example packet

`jobs/examples/wbs-qa-pilot.yml` is an example-only future WBS QA job packet.

It does not run tests, browser automation, provider calls, scheduling, or runtime selection. It does not modify WBS.

## Limitations

L003 does not include:

- autonomous orchestration
- runtime resolver implementation
- runtime scoring
- provider adapters
- provider credentials
- GLM integration
- Telegram integration
- scheduler integration
- memory engine implementation
- cloud workers
- OpenClaw runtime behaviour changes
- WBS modifications

## Next sprint recommendation

Recommended next sprint:

**L004 — Registry and Job Validation Tools**

Suggested scope:

1. Add read-only validation scripts for registry and job packet shape.
2. Validate cross-registry references.
3. Validate agent README coverage.
4. Validate repository boundary metadata.
5. Produce validation reports without dispatching jobs.
6. Keep runtime execution disabled until explicitly approved.
