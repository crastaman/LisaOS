# LisaOS Jobs

The `jobs/` directory contains the lightweight job packet schema and examples for future LisaOS execution workflows.

L003 does not create a job queue, scheduler, worker, autonomous runner, or OpenClaw integration.

## Files

- `jobs/schema.yml` — model-agnostic job packet schema.
- `jobs/examples/wbs-qa-pilot.yml` — example-only future WBS QA job packet.

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

## Status values

Initial packet status values are documentation-only and should align with future workflow design:

- `draft`
- `queued`
- `assigned`
- `active`
- `blocked`
- `completed`
- `failed`
- `cancelled`

## Boundary rule

A job packet must include `target_repository` and `repository_boundary_check` before future execution can be considered safe.
