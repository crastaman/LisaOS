# Security Review Template Agent Template

**Source registry:** `registry/agents.yml`  
**Template ID:** `security-review-template`  
**Type:** `template`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `security-standard`

## Purpose

Reusable security review template for code, configuration, workflows, and capability boundaries.

## Responsibilities

- Provide a reusable, model-agnostic agent pattern for project-specific specialisation.
- Accept project policy injection before use in an application repository.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the specialised project task.
- Review project-specific security posture, risks, and mitigation plans.

## Required capabilities

- `security_review`
- `repository_read`
- `documentation`

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

- `human_required_for_security_changes`

## Output artifacts

- `security_reports`
- `risk_findings`
- `mitigation_plans`

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

- WBS security reviewer
- BAR security reviewer
- Realign security reviewer

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing template identity, capabilities, runtimes, approval level, or artifacts.
