# ADR-0002 — Capability-Based Routing

## Status

Accepted

## Context

Lisa must support multiple execution engines without becoming dependent on one provider.

Available/planned engines:

- Codex: default active engineer for focused repo-aware work
- Claude Code: deep specialist and existing agent ecosystem when available
- Ollama/Qwen: local low-cost/private first-pass analysis
- GPT: architecture and strategic reasoning
- OpenClaw: orchestration/runtime layer

## Decision

Lisa routes work by required capability, not by brand.

Skills should describe what the task needs, such as:

- code_review
- repository_analysis
- architecture
- governance
- implementation
- local_private
- low_cost
- large_context

The router chooses the best available engine.

## Current Policy

Default active engine: Codex

Claude Code is used for deep agent work when available.

Ollama/Qwen will be used for local first-pass analysis after model testing.

## Consequences

Lisa remains flexible, budget-aware, and resilient when one engine is unavailable.
