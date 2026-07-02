# Wordpress Plugin Template Agent Template

**Source registry:** `registry/agents.yml`  
**Template ID:** `wordpress-plugin-template`  
**Type:** `template`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `repository-boundary`

## Purpose

Reusable WordPress plugin engineering template for project-specific plugin implementations.

## Responsibilities

- Provide a reusable, model-agnostic agent pattern for project-specific specialisation.
- Accept project policy injection before use in an application repository.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the specialised project task.
- Support project-specific WordPress plugin implementation and review.

## Required capabilities

- `php`
- `javascript`
- `wordpress`
- `git`
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

- `plugin_patches`
- `test_results`
- `migration_notes`

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

- WBS WordPress plugin agent
- BAR WordPress integration agent
- Realign WordPress extension agent

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing template identity, capabilities, runtimes, approval level, or artifacts.
