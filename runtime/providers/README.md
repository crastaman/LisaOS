# Runtime Providers

This directory documents the provider abstraction boundary for future LisaOS runtime execution.

L003 does not add provider integrations, credentials, API calls, GLM integration, or model selection logic.

## Provider principle

LisaOS should route through runtime profiles before selecting a concrete provider runtime.

Examples of runtime profiles from `registry/runtimes.yml`:

- `planning-runtime`
- `governance-runtime`
- `review-runtime`
- `implementation-runtime`

## Provider boundary

Provider-specific details must remain behind adapters and must not leak into agent templates or job packets.

Future provider integrations should document:

- runtime ID
- provider name
- supported runtime profile
- supported capabilities
- cost tier
- health status source
- fallback behaviour
- approval requirements for restricted actions
