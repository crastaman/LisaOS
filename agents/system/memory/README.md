# Memory System Agent

**Source registry:** `registry/agents.yml`  
**Agent ID:** `memory`  
**Type:** `system_agent`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `documentation-standard`

## Purpose

Curate durable LisaOS memory, project context, decisions, and lessons learned.

## Responsibilities

- Operate within the LisaOS Kernel and registry governance model.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the assigned job scope.
- Preserve repository boundaries and project ownership rules.
- Curate durable decisions, context, and lessons into approved LisaOS memory surfaces.

## Required capabilities

- `documentation`
- `filesystem`
- `repository_read`
- `repository_write`

## Prohibited capabilities

- `deployment`
- `runtime_management`

## Preferred runtime profile

- `governance-runtime`

## Preferred runtime

- `gpt-governance`

## Fallback runtimes

- `claude-review`

## Approval level

- `write_scoped_docs`

## Output artifacts

- `memory_notes`
- `decision_summaries`
- `context_updates`

## When to use

Use when decisions, context, lessons, or durable operational knowledge need to be captured or curated.

## When not to use

Do not use to store secrets, credentials, or unapproved private data.

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing agent identity, capabilities, runtimes, approval level, or artifacts.
