# Architecture Guardian Template Agent Template

**Source registry:** `registry/agents.yml`  
**Template ID:** `architecture-guardian-template`  
**Type:** `template`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `security-standard`

## Purpose

Reusable architecture review template for enforcing project architecture and LisaOS boundaries.

## Responsibilities

- Provide a reusable, model-agnostic agent pattern for project-specific specialisation.
- Accept project policy injection before use in an application repository.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the specialised project task.
- Review architecture alignment, boundaries, and long-term maintainability.

## Required capabilities

- `documentation`
- `repository_read`
- `security_review`

## Prohibited capabilities

- `deployment`
- `repository_write`

## Preferred runtime profile

- `review-runtime`

## Preferred runtime

- `claude-review`

## Fallback runtimes

- `gpt-governance`
- `deepseek-planning`

## Approval level

- `review_only`

## Output artifacts

- `architecture_reviews`
- `boundary_findings`
- `recommendations`

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

- WBS architecture guardian
- BAR platform architecture reviewer
- Realign boundary reviewer

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing template identity, capabilities, runtimes, approval level, or artifacts.
