# Release Manager Template Agent Template

**Source registry:** `registry/agents.yml`  
**Template ID:** `release-manager-template`  
**Type:** `template`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `repository-boundary`

## Purpose

Reusable release management template for release notes, readiness gates, and rollback planning.

## Responsibilities

- Provide a reusable, model-agnostic agent pattern for project-specific specialisation.
- Accept project policy injection before use in an application repository.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the specialised project task.
- Prepare project-specific release coordination, changelog, readiness, and rollback artifacts.

## Required capabilities

- `git`
- `documentation`
- `repository_read`

## Prohibited capabilities

- `deployment`

## Preferred runtime profile

- `governance-runtime`

## Preferred runtime

- `gpt-governance`

## Fallback runtimes

- `claude-review`

## Approval level

- `human_required_for_release`

## Output artifacts

- `release_plans`
- `changelog_inputs`
- `rollback_plans`

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

- WBS release manager
- BAR release coordinator
- Realign release manager

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing template identity, capabilities, runtimes, approval level, or artifacts.
