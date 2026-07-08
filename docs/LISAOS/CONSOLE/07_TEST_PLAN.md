# Test Plan

**Status:** COMPLETE for C1–C5. 395/395 passing under `.venv`.

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
| `tests/test_console_security.py` (**implemented, 14/14 passing, skipped on bare system Python**) | C5 | Malformed/oversized/unicode headers, replay proof, audit-append-only (structural + behavioral), secret-never-in-audit at Console integration level |
| `tests/test_console_config.py` (**implemented, 11/11 passing**) | C5 | `console/config_check.py`: hard errors vs. graceful-degradation warnings, registry validation, storage writability |

Flask is a `console/`-scoped dependency (`console/requirements.txt`),
deliberately not installed for the system Python LisaOS core has always
run tests under. `test_console_auth.py`, `test_console_routes.py`, and
`test_console_security.py` guard their Flask imports and skip (not
fail) when Flask isn't importable, so the standing bare-`python3`
regression command stays green; `test_console_data.py`,
`test_console_actions.py`, and `test_console_config.py` need no guard
since none of `console/data.py`, `console/actions.py`, or
`console/config_check.py` imports Flask at all. Run the full suite for
real with:
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
- Malformed/oversized/whitespace/unicode identity headers denied
  cleanly, no crash, no audit-log bloat. **Implemented, Phase C5.**
- Replay of a captured request is harmless (idempotency guard).
  **Implemented, Phase C5.**
- Audit log is append-only (structural + behavioral proof).
  **Implemented, Phase C5.**
- Live Tailscale `serve` deployment verification (real off-tailnet
  request rejected at the network layer, not just the app layer) —
  **cannot be certified from this environment** (no tailnet available);
  mandatory manual step in `09_DEPLOYMENT_GUIDE.md`'s checklist. See
  `11_C5_SECURITY_REPORT.md` §1.

## Regression gate

Two commands, both must stay green:

- `PYTHONPATH="$HOME/Lisa" python3 -m unittest discover -s tests` (bare
  system Python, no Flask) — 395/395 as of Phase C5, with 39 Console
  tests explicitly skipped (Flask not installed) rather than failing.
- `PYTHONPATH="$HOME/Lisa" .venv/bin/python3 -m unittest discover -s
  tests` (project-local venv, Flask + PyYAML installed) — 395/395, all
  executed, none skipped.

(220/220 at the 2026-07-08 LisaOS 3.0 closure → 243/243 pre-Console →
258/258 after C1 → 292/292 after C2 → 314/314 after C3 → 370/370 after
C4 → 395/395 after C5.)
