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
| `tests/test_console_auth.py` (**implemented, 8/8 passing**) | C4 | Allowlist parsing, missing/wrong/correct identity → 403/403/200, fail-closed on empty allowlist, every access attempt audited |
| `tests/test_console_data.py` (**implemented, 24/24 passing**) | C4 | Read-only bundle/brief/notification/audit/worker access, newest-first ordering, corrupt-file resilience, dashboard aggregation |
| `tests/test_console_actions.py` (**implemented, 13/13 passing**) | C4 | Approve/Reject write the documented `decision` shape; empty-rationale and missing-actor rejected; already-decided guard leaves the first decision untouched |
| `tests/test_console_routes.py` (**implemented, 17/17 passing, skipped on bare system Python — see below**) | C4 | Full route coverage via Flask's test client: auth gating, empty/populated states, 404s, the decide flow, and a structural proof that no execution-capable route exists |

Flask is a `console/`-scoped dependency (`console/requirements.txt`),
deliberately not installed for the system Python LisaOS core has always
run tests under. `test_console_auth.py` and `test_console_routes.py`
guard their Flask imports and skip (not fail) when Flask isn't
importable, so the standing bare-`python3` regression command stays
green; `test_console_data.py` and `test_console_actions.py` need no
guard since neither `console/data.py` nor `console/actions.py` imports
Flask at all. Run the full suite for real with:
`PYTHONPATH="$HOME/Lisa" .venv/bin/python3 -m unittest discover -s tests`.

## Live/network smoke test

`tests/smoke_console_e2e.py` (matching the existing `smoke_*.py`
live-network pattern, e.g. `smoke_deepinfra.py`): one real end-to-end run
against real OpenAI + real ntfy.sh. Manual/opt-in only — never part of
the default automated run.

## Security tests

- Request without Tailscale header → 403. **Implemented.**
- Request with mismatched identity → 403. **Implemented.**
- Reject (or Approve) requires a non-empty note; empty note is
  rejected. **Implemented.**
- Every access attempt, granted or denied, is audited. **Implemented.**
- No generic file browser exists to path-traverse — Phase C4 dropped
  the `/reports` route from the original C0 draft since it had no real
  requirement behind it once the 6-screen spec was approved.
- Live Tailscale `serve` deployment verification (real off-tailnet
  request rejected at the network layer, not just the app layer) is
  **Phase C5**, not yet done.

## Regression gate

Two commands, both must stay green:

- `PYTHONPATH="$HOME/Lisa" python3 -m unittest discover -s tests` (bare
  system Python, no Flask) — 370/370 as of Phase C4, with 25 Console
  tests explicitly skipped (Flask not installed) rather than failing.
- `PYTHONPATH="$HOME/Lisa" .venv/bin/python3 -m unittest discover -s
  tests` (project-local venv, Flask + PyYAML installed) — 370/370, all
  executed, none skipped.

(220/220 at the 2026-07-08 LisaOS 3.0 closure → 243/243 pre-Console →
258/258 after C1 → 292/292 after C2 → 314/314 after C3 → 370/370 after
C4.)
