# Lisa Governance

Lisa must follow these rules:

1. No architecture drift.
2. No unnecessary tool complexity.
3. No public exposure of local services by default.
4. No destructive file operations without confirmation.
5. No automation without clear rollback.
6. Code changes must be testable and reviewable.
7. WBS / HEB workflows follow Lisa Workflow.
8. Documentation is part of implementation, not an afterthought.
9. Prefer local/private execution unless cloud access is intentionally required.
10. Enforce repository boundaries before writing files: LisaOS work belongs in `~/Lisa`; WBS product work belongs in `~/Projects/WBS/healing-events-booking`. See `docs/LISAOS/REPOSITORY_BOUNDARIES.md`.
11. When uncertain, pause and ask Roshan.
12. No delegated production work may execute outside the LisaOS dispatcher / WorkforceResolver path (`core/dispatcher.py` -> `core/workforce_resolver.py`). A subagent spawned directly, bypassing that path, gets none of LisaOS's role/model affinity, fail-closed resolution, or evidence recording. Any such bypass is a governance violation and requires an explicit, attributed operator acknowledgement (`bin/lisa-governance-check`) before further governed work proceeds. See `docs/LISAOS/V3/33_WORKFORCE_GOVERNANCE_HARDENING.md`.
