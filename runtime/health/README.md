# Runtime Health

This directory documents future runtime health checks.

L003 does not implement health checks, provider pings, monitoring, alerts, or availability scoring.

## Future health dimensions

A future health layer may track:

- provider availability
- runtime availability
- latency class
- error rate
- cost tier
- capability support
- policy restrictions
- maintenance status

## Health output principle

Health checks should provide advisory metadata to the resolver. They should not bypass policy, approval, validation, or repository-boundary rules.
