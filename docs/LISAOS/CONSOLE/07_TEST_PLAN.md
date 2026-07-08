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
| `tests/test_gpt_advisor.py` | C2 | Context Pack loading/caching, prompt composition, structured-output parsing, degraded-mode fallback (OpenAI call mocked) |
| `tests/test_notify.py` | C3 | Payload construction, priority logic, delivery-failure audit logging (HTTP mocked) |
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
tests`) must stay green — currently 220/220 — plus all new Console tests,
before any Console phase is considered done.
