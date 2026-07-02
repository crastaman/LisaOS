# Runtime Adapters

This directory documents the future adapter boundary between LisaOS runtime decisions and concrete execution systems.

L003 does not implement adapters or call external runtimes.

## Adapter role

A future adapter may translate a resolved execution packet into a provider-specific invocation while preserving:

- job objective
- repository boundary
- selected agent
- required capabilities
- prohibited capabilities
- validation requirements
- approval requirements
- output artifact expectations

## Adapter constraints

Adapters must not own routing policy. They should receive already-resolved, policy-checked execution packets.
