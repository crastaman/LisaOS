# L001.5 Registry Governance Review

**Job ID:** L001.5-REGISTRY-GOVERNANCE-REVIEW  
**Repository:** `~/Lisa`  
**Scope:** Governance refinement of the L001 registry foundation.  
**Mode:** Documentation and registry metadata only. No runtime behaviour changes.

## Executive Summary

L001.5 reviewed the initial LisaOS registry foundation and strengthened it for long-term governance, extensibility, and enterprise readiness.

The sprint did not redesign the architecture and did not add runtime features. It added metadata, lifecycle, ownership, policy, dependency, and runtime abstraction fields so future LisaOS components can depend on stable registry structures.

Primary outcome:

- The registry model now has a canonical versioned metadata header.
- Every registry object has `status`, `owner`, and `policy_profile`.
- Agents support `depends_on` where architecturally justified.
- Agents and runtimes support `runtime_profile` abstraction to reduce provider coupling.
- Future resolver, validation, scheduling, cloud worker, and policy-injection work can proceed without immediate schema redesign.

## Architecture Assessment

The L001 registry foundation was structurally sound but too minimal for future implementation dependencies.

Before L001.5, the registries defined useful content but lacked:

- registry-level version metadata
- object lifecycle state
- canonical ownership metadata
- policy profile hooks
- dependency expression
- runtime abstraction beyond concrete runtime IDs

These omissions would have forced early schema changes once resolver work, enterprise deployment, project policy injection, or cloud worker execution began.

L001.5 addresses those concerns while preserving the original registry objects and behaviour.

## Registry Improvements

### Registry metadata

Each registry now includes:

```yaml
registry:
  name:
  version: 1.0.0
  schema:
  last_updated:
  owner: LisaOS
  status: active
```

This establishes the registry as a versioned canonical artifact.

### Status lifecycle

Every registry object now includes:

```yaml
status:
```

Allowed lifecycle values:

- `active`
- `experimental`
- `deprecated`
- `disabled`

Current production-ready registry objects default to `active`. The future GLM builder runtime placeholder is marked `experimental` because it is not active for production use.

### Canonical owner

Every registry object now includes:

```yaml
owner: LisaOS
```

Allowed future values:

- `LisaOS`
- `WBS`
- `BAR`
- `Realign`
- `Shared`

Current L001 entries default to `LisaOS` because they belong to the operating-system foundation.

### Policy profiles

Every registry object now includes:

```yaml
policy_profile:
```

Initial policy profile values include:

- `repository-boundary`
- `documentation-standard`
- `security-standard`
- `runtime-standard`

Policy profiles prepare the registry for future project policy injection without redesigning the object model.

### Dependencies

Agents now support:

```yaml
depends_on:
```

Dependencies were added only where architecturally justified:

- `router` depends on `planner`
- `memory` depends on `planner`
- `security` depends on `planner`
- `release` depends on `planner`
- `builder-template` depends on `planner`
- `architecture-guardian-template` depends on `planner`
- `documentation-review-template` depends on `planner`
- `ui-audit-template` depends on `planner`
- `wordpress-plugin-template` depends on `builder-template` and `architecture-guardian-template`
- `release-manager-template` depends on `planner` and `release`
- `security-review-template` depends on `architecture-guardian-template`

This does not enforce orchestration yet. It documents dependency intent for future resolver work.

### Runtime abstraction

Existing runtime IDs were preserved.

A new metadata field was added:

```yaml
runtime_profile:
```

Initial runtime profiles include:

- `governance-runtime`
- `planning-runtime`
- `review-runtime`
- `implementation-runtime`

This allows future components to route to abstract runtime roles while retaining current runtime placeholders.

## Future Risks

### Schema drift

Without a formal validator, future registry edits may accidentally omit required keys or introduce inconsistent terminology.

### Policy profile ambiguity

Policy profiles are named but not yet semantically defined. L002 should define what each profile requires and how project policy injection extends it.

### Dependency enforcement

Agent dependencies are declarative only. Future resolver work must decide whether dependencies are advisory, required, inherited, or execution-ordered.

### Runtime-provider coupling

Concrete runtime IDs remain in the registry for traceability. Future orchestration should prefer `runtime_profile` selection and only resolve to concrete runtimes at execution time.

### Multi-project ownership

The owner model supports multiple projects, but there are not yet project-specific policy packages for WBS, BAR, Realign, or future applications.

### Enterprise deployment

The registries are now metadata-ready, but enterprise deployment will require validation, audit logs, role-based permissions, secrets isolation, and environment-specific overlays.

## Recommendations Deferred to L002

L002 should remain read-only and resolver-design focused.

Recommended L002 scope:

1. Create formal schema documentation for all registries.
2. Add a read-only registry validation script.
3. Validate required fields, allowed lifecycle values, owner values, and policy profile values.
4. Validate cross-registry references:
   - job default agents exist
   - agent capabilities exist
   - runtime IDs exist
   - dependency targets exist
5. Define resolver logic for:
   - job → agent
   - agent → capabilities
   - agent → runtime profile
   - runtime profile → runtime candidate
6. Define project policy injection semantics.
7. Define future scheduling hooks without implementing scheduling.
8. Keep runtime behaviour unchanged until governance review approves enforcement.

## Decision Log

| Decision | Outcome | Reason |
|---|---|---|
| Add registry-level metadata | Accepted | Enables versioning, ownership, lifecycle, and schema identification. |
| Start versions at `1.0.0` | Accepted | L001 is the first canonical registry model. |
| Add object `status` | Accepted | Enables lifecycle governance without deleting objects. |
| Add object `owner` | Accepted | Supports multi-project and shared ownership models. |
| Default current owners to `LisaOS` | Accepted | Current entries are operating-system foundation entries. |
| Add `policy_profile` | Accepted | Supports future policy injection without schema redesign. |
| Add `depends_on` for agents | Accepted | Documents dependency intent for resolver work. |
| Preserve current runtime IDs | Accepted | Avoids redesign and keeps L001 compatibility. |
| Add `runtime_profile` | Accepted | Reduces future provider coupling while preserving concrete runtime placeholders. |
| Do not implement resolver behaviour | Accepted | L001.5 is governance refinement only. |
| Defer schema validation script to L002 | Accepted | Keeps this sprint focused on model refinement and documentation. |
