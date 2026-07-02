# Security System Agent

**Source registry:** `registry/agents.yml`  
**Agent ID:** `security`  
**Type:** `system_agent`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `security-standard`

## Purpose

Review permissions, capability boundaries, repository safety, and security-sensitive workflows.

## Responsibilities

- Operate within the LisaOS Kernel and registry governance model.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the assigned job scope.
- Preserve repository boundaries and project ownership rules.
- Identify security, permission, and capability risks before implementation proceeds.

## Required capabilities

- `security_review`
- `documentation`
- `repository_read`

## Prohibited capabilities

- `deployment`

## Preferred runtime profile

- `review-runtime`

## Preferred runtime

- `claude-review`

## Fallback runtimes

- `gpt-governance`
- `deepseek-planning`

## Approval level

- `human_required_for_changes`

## Output artifacts

- `security_reviews`
- `risk_registers`
- `approval_requirements`

## When to use

Use when a job has security, permission, deployment, secret, or restricted-capability implications.

## When not to use

Do not use to deploy fixes directly or override human approval for restricted actions.

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing agent identity, capabilities, runtimes, approval level, or artifacts.
