# Documentation Review Template Agent Template

**Source registry:** `registry/agents.yml`  
**Template ID:** `documentation-review-template`  
**Type:** `template`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `documentation-standard`

## Purpose

Reusable documentation consistency, reference, and governance review template.

## Responsibilities

- Provide a reusable, model-agnostic agent pattern for project-specific specialisation.
- Accept project policy injection before use in an application repository.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the specialised project task.
- Review documentation consistency, references, completeness, and canonical ownership.

## Required capabilities

- `documentation`
- `repository_read`
- `filesystem`

## Prohibited capabilities

- `deployment`
- `runtime_management`

## Preferred runtime profile

- `review-runtime`

## Preferred runtime

- `claude-review`

## Fallback runtimes

- `gpt-governance`
- `deepseek-planning`

## Approval level

- `write_scoped_docs`

## Output artifacts

- `documentation_reviews`
- `reference_maps`
- `doc_patches`

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

- WBS documentation consistency reviewer
- BAR documentation reviewer
- LisaOS docs reviewer

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing template identity, capabilities, runtimes, approval level, or artifacts.
