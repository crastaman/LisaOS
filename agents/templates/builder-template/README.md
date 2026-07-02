# Builder Template Agent Template

**Source registry:** `registry/agents.yml`  
**Template ID:** `builder-template`  
**Type:** `template`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `repository-boundary`

## Purpose

Reusable implementation template for scoped engineering changes with policy injection.

## Responsibilities

- Provide a reusable, model-agnostic agent pattern for project-specific specialisation.
- Accept project policy injection before use in an application repository.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the specialised project task.
- Guide scoped implementation work without bypassing project policy or validation.

## Required capabilities

- `git`
- `terminal`
- `filesystem`
- `repository_read`
- `repository_write`

## Prohibited capabilities

- `deployment`
- `runtime_management`

## Preferred runtime profile

- `implementation-runtime`

## Preferred runtime

- `codex-review`

## Fallback runtimes

- `claude-review`
- `glm-builder-future`

## Approval level

- `project_policy_required`

## Output artifacts

- `patches`
- `implementation_notes`
- `validation_results`

## Project policy injection notes

Before use in an application repository, this template must receive project-specific policy context, including:

- canonical repository path and branch rules
- allowed and prohibited paths
- product ownership boundaries
- validation requirements
- approval requirements
- output artifact locations
- escalation rules for restricted capabilities

Policy injection must specialise the template without changing the canonical LisaOS template definition.

## Example project specialisations

- WBS implementation builder
- BAR application builder
- Realign feature builder

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing template identity, capabilities, runtimes, approval level, or artifacts.
