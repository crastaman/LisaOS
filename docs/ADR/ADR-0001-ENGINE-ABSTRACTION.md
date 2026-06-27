# ADR-0001 — Engine Abstraction

## Status

Accepted

## Context

Lisa Core must remain independent of any specific AI model.

Claude Code, Codex, GPT, OpenClaw and future engines are execution engines.

Lisa Core coordinates them.

## Decision

Lisa will communicate with AI systems through an Engine interface.

Skills describe intent.

The Router selects the appropriate engine.

Supported engines:

- ClaudeEngine
- CodexEngine
- GPTEngine
- OpenClawEngine

## Consequences

Benefits:

- Vendor independence
- Extensible architecture
- Skills become reusable
- Engines become replaceable

Tradeoffs:

- Slightly higher architectural complexity
- Requires routing logic
