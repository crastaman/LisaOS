# Test Plan

**Status:** IN PROGRESS — expands per phase (C1–C5)

## Convention

One unit-test file per new module, stdlib `unittest`, hermetic tmp dirs,
docstring-linked back to the relevant `docs/LISAOS/CONSOLE/NN_*.md` doc —
matches the existing `tests/` convention exactly (see
`tests/test_dispatcher.py`, `tests/test_governance_guard.py` for the
pattern).

## Planned test files

| File | Phase | Covers |
|---|---|---|
| `tests/test_decision_bundle_exporter.py` (**implemented, 15/15 passing**) | C1 | Bundle construction/validation, evidence matching + dedup, governance status, atomic write, immutability enforcement, end-to-end export |
| `tests/test_context_pack.py` (**implemented, 8/8 passing**) | C2 | Numbered-file discovery/ordering, meta-file exclusion, mtime-based cache invalidation |
| `tests/test_openai_client.py` (**implemented, 13/13 passing**) | C2 | Fail-closed credentials check, HTTP/transport failure categorization, key-never-leaked assertion (`urlopen` mocked) |
| `tests/test_gpt_advisor.py` (**implemented, 13/13 passing**) | C2 | Prompt assembly, all degraded categories, partial-summary critical-vs-noncritical field handling, bundle read-only proof (bundle file chmod'd read-only) |
| `tests/test_notify.py` (**implemented, 22/22 passing**) | C3 | Allowlist payload construction (incl. forbidden-content leak proof), priority logic, retry/backoff, duplicate suppression, not-configured fail-closed, audit logging, HTTP failure categorization |
| `tests/test_console_auth.py` | C4/C5 | Tailscale-header check: missing header → 403, wrong identity → 403, correct identity → 200 |
| `tests/test_console_safe_actions.py` | C4/C5 | Approve/Reject write exactly the documented `decision` shape; compare-and-swap idempotency under a simulated concurrent double-click |

## Live/network smoke test

`tests/smoke_console_e2e.py` (matching the existing `smoke_*.py`
live-network pattern, e.g. `smoke_deepinfra.py`): one real end-to-end run
against real OpenAI + real ntfy.sh. Manual/opt-in only — never part of
the default automated run.

## Security tests

- Request without Tailscale header → 403.
- Request with mismatched identity → 403.
- Attempt to read outside `reports/`/`docs/LISAOS/` via `/reports` →
  403/404.
- Reject requires a non-empty note; empty note is rejected.

## Regression gate

Full suite (`PYTHONPATH="$HOME/Lisa" python3 -m unittest discover -s
tests`) must stay green — 314/314 as of Phase C3 (up from the 220/220
recorded at the 2026-07-08 LisaOS 3.0 closure; the pre-Console baseline
grew to 243 before Console work began, for reasons unrelated to this
project) — plus all new Console tests, before any Console phase is
considered done.
