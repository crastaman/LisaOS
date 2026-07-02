# Runtime Resolver

The resolver directory documents how a future LisaOS resolver should interpret job packets and registries.

No resolver logic is implemented in L003.

## Future resolution order

1. Read a job packet from `jobs/schema.yml` shape.
2. Match `job_type` to `registry/jobs.yml`.
3. Determine the default or preferred agent.
4. Merge job-required capabilities with registry-required capabilities.
5. Respect prohibited capabilities from the job and selected agent.
6. Read the selected agent's `runtime_profile`.
7. Find runtime candidates in `registry/runtimes.yml` by `runtime_profile`.
8. Apply fallback runtime order from `registry/agents.yml`.
9. Require validation when either the job or job type requires it.
10. Require approval when either the job or job type requires it.

## Resolver boundaries

A future resolver must remain model-agnostic and policy-aware. It should produce a decision packet, not execute work directly.

## Deferred

- runtime scoring
- provider availability checks
- queue processing
- autonomous dispatch
- OpenClaw integration
- scheduling
