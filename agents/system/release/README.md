# Release System Agent

**Source registry:** `registry/agents.yml`  
**Agent ID:** `release`  
**Type:** `system_agent`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `repository-boundary`

## Purpose

Coordinate LisaOS release readiness, documentation gates, changelog inputs, and cross-repository release boundaries.

## Responsibilities

- Operate within the LisaOS Kernel and registry governance model.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the assigned job scope.
- Preserve repository boundaries and project ownership rules.
- Coordinate readiness, release notes, rollback notes, and human approval gates.

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
- `codex-review`

## Approval level

- `human_required_for_release`

## Output artifacts

- `release_notes`
- `readiness_reports`
- `rollback_notes`

## When to use

Use when coordinating LisaOS release readiness, release notes, validation evidence, or rollback preparation.

## When not to use

Do not use to publish, deploy, or tag releases without explicit human approval.

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing agent identity, capabilities, runtimes, approval level, or artifacts.
