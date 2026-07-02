# LisaOS Agent Framework

**Source registry:** `registry/agents.yml`  
**Framework sprint:** L002-LISAOS-AGENT-FRAMEWORK

The LisaOS agent framework provides the lightweight folder structure for system agents and reusable templates.

It is intentionally documentation-first. It does not implement autonomous orchestration, runtime resolver logic, scheduling, Telegram integration, memory engine behaviour, or cloud execution.

## System agents

System agents are owned by LisaOS and support core operating-system responsibilities.

- [`planner`](system/planner/README.md) — Plan LisaOS work, decompose jobs, define safe execution phases, and preserve repository boundaries.
- [`router`](system/router/README.md) — Route jobs to appropriate agents, templates, runtimes, and capability sets.
- [`memory`](system/memory/README.md) — Curate durable LisaOS memory, project context, decisions, and lessons learned.
- [`security`](system/security/README.md) — Review permissions, capability boundaries, repository safety, and security-sensitive workflows.
- [`release`](system/release/README.md) — Coordinate LisaOS release readiness, documentation gates, changelog inputs, and cross-repository release boundaries.

## Templates

Templates are reusable agent patterns. They become project-specific only after policy injection.

- [`builder-template`](templates/builder-template/README.md) — Reusable implementation template for scoped engineering changes with policy injection.
- [`architecture-guardian-template`](templates/architecture-guardian-template/README.md) — Reusable architecture review template for enforcing project architecture and LisaOS boundaries.
- [`documentation-review-template`](templates/documentation-review-template/README.md) — Reusable documentation consistency, reference, and governance review template.
- [`ui-audit-template`](templates/ui-audit-template/README.md) — Reusable user-interface audit template for accessibility, visual consistency, and frontend risk review.
- [`wordpress-plugin-template`](templates/wordpress-plugin-template/README.md) — Reusable WordPress plugin engineering template for project-specific plugin implementations.
- [`release-manager-template`](templates/release-manager-template/README.md) — Reusable release management template for release notes, readiness gates, and rollback planning.
- [`security-review-template`](templates/security-review-template/README.md) — Reusable security review template for code, configuration, workflows, and capability boundaries.

## Ownership

Canonical agent definitions live in `registry/agents.yml`.

The files under `agents/system/` and `agents/templates/` are registry-derived documentation surfaces. They explain how each agent or template should be used but do not replace the registry.

## Registry-derived content rule

Do not edit generated or registry-derived agent content without updating `registry/agents.yml` first.

If an agent's capabilities, runtime profile, fallback runtimes, approval level, ownership, status, policy profile, or output artifacts change, update the registry and then refresh the corresponding README.

## Model-agnostic principle

LisaOS agents must remain model-agnostic.

Agents may reference preferred runtime profiles and fallback runtime IDs, but no agent should depend permanently on a single vendor or model. Future resolver work should select concrete runtimes from registry metadata at execution time.
