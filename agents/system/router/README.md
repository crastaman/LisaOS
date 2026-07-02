# Router System Agent

**Source registry:** `registry/agents.yml`  
**Agent ID:** `router`  
**Type:** `system_agent`  
**Owner:** `LisaOS`  
**Status:** `active`  
**Policy profile:** `runtime-standard`

## Purpose

Route jobs to appropriate agents, templates, runtimes, and capability sets.

## Responsibilities

- Operate within the LisaOS Kernel and registry governance model.
- Use only declared capabilities and respect prohibited capabilities.
- Produce the declared output artifacts for the assigned job scope.
- Preserve repository boundaries and project ownership rules.
- Map jobs to agents, templates, runtime profiles, and capability requirements.

## Required capabilities

- `documentation`
- `repository_read`
- `runtime_management`

## Prohibited capabilities

- `deployment`

## Preferred runtime profile

- `governance-runtime`

## Preferred runtime

- `gpt-governance`

## Fallback runtimes

- `deepseek-planning`

## Approval level

- `governance_review`

## Output artifacts

- `routing_decisions`
- `agent_assignments`
- `capability_requests`

## When to use

Use when a job needs classification, agent selection, capability mapping, or runtime-profile recommendation.

## When not to use

Do not use to execute work directly or bypass approval gates.

## Registry maintenance note

This README is derived from `registry/agents.yml`. Update the registry first when changing agent identity, capabilities, runtimes, approval level, or artifacts.
