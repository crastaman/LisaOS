# L002 Agent Framework

**Job ID:** L002-LISAOS-AGENT-FRAMEWORK  
**Repository:** `~/Lisa`  
**Scope:** Lightweight LisaOS agent framework based on the L001 registry foundation.

## Purpose

L002 creates the folder and documentation structure required for LisaOS system agents and reusable agent templates.

This sprint is intentionally small. It does not implement autonomous orchestration, runtime resolver logic, Telegram integration, scheduling, memory engine behaviour, cloud workers, or production execution.

The framework makes the registry visible as a navigable agent library while keeping `registry/agents.yml` canonical.

## Structure created

```text
agents/
agents/README.md
agents/system/
agents/system/<system-agent-id>/README.md
agents/templates/
agents/templates/<template-id>/README.md
skills/
prompts/
workflows/lisaos/
docs/LISAOS/L002_AGENT_FRAMEWORK.md
```

## System agents vs templates

### System agents

System agents are LisaOS-owned operating-system agents.

They support platform responsibilities such as planning, routing, memory, security, and release coordination.

Current system agents:

- `planner`
- `router`
- `memory`
- `security`
- `release`

### Templates

Templates are reusable agent patterns.

They are not product-specific until a project injects policy, repository boundaries, validation requirements, ownership, and escalation rules.

Current templates:

- `builder-template`
- `architecture-guardian-template`
- `documentation-review-template`
- `ui-audit-template`
- `wordpress-plugin-template`
- `release-manager-template`
- `security-review-template`

## Relationship to `registry/agents.yml`

`registry/agents.yml` remains the canonical source of truth for:

- agent IDs
- agent type
- lifecycle status
- canonical owner
- policy profile
- dependencies
- required capabilities
- prohibited capabilities
- preferred runtime
- runtime profile
- fallback runtimes
- approval level
- output artifacts

The agent READMEs are registry-derived documentation surfaces. They make the registry easier to inspect, but they do not replace the registry.

## Relationship to policy injection

Templates are designed for future project policy injection.

Policy injection should provide:

- target repository
- product owner
- allowed paths
- prohibited paths
- validation requirements
- approval requirements
- output artifact expectations
- escalation rules
- project-specific terminology

Policy injection specialises a template for a project without changing the canonical LisaOS template.

## Limitations

L002 does not include:

- autonomous orchestration
- runtime resolver logic
- model selection logic
- Telegram integration
- scheduler integration
- memory engine implementation
- cloud worker execution
- generated prompts
- executable skills
- production deployment behaviour

The `skills/`, `prompts/`, and `workflows/lisaos/` directories are created as foundation points only.

## Next sprint recommendation

Recommended next sprint:

**L003 — Runtime and Execution Framework**

Suggested scope:

1. Define runtime execution contracts without enabling autonomous execution.
2. Document runtime profile resolution rules.
3. Define agent invocation packet shape.
4. Define validation and approval checkpoints.
5. Keep provider credentials, secrets, deployment, scheduling, Telegram, and cloud workers out of scope until explicitly approved.
