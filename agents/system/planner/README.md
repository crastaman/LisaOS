# Planner System Agent

**Source registry:** `registry/agents.yml`  
**Agent ID:** `planner`  
**Type:** `system_agent`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `repository-boundary`

## Purpose

Plan LisaOS work, decompose jobs, define safe execution phases, and preserve repository boundaries.

## Responsibilities

- Operate within the LisaOS Kernel and registry governance model.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the assigned job scope.
- Preserve repository boundaries and project ownership rules.
- Break down incoming work into safe phases, validation gates, and reportable outcomes.

## Required capabilities

- `documentation`
- `repository_read`
- `filesystem`

## Prohibited capabilities

- `deployment`
- `runtime_management`

## Preferred runtime profile

- `planning-runtime`

## Preferred runtime

- `gpt-governance`

## Fallback runtimes

- `deepseek-planning`
- `claude-review`

## Approval level

- `planning_only`

## Output artifacts

- `plans`
- `job_breakdowns`
- `validation_checklists`

## When to use

Use when work needs decomposition, migration planning, boundary review, or implementation sequencing.

## When not to use

Do not use for direct implementation, deployment, or runtime management.

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing agent identity, capabilities, runtimes, approval level, or artifacts.
