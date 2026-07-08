# Phase C5 Security Report

**Status:** Final deliverable for Phase C5. Prepared for CTO-role review
before `feature/lisa-console` merges (Role Abstraction Principle,
`docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md`).
**Scope:** `console/`, plus the audit-logging additions to
`core/decision_bundle_exporter.py` and `advisors/gpt_advisor.py` made in
this phase.
**Evidence basis:** every claim below cites a real test or a real grep
result, not an assertion. Full suite: **395/395 passing** (`.venv`, all
executed; bare system Python, 39 of those skipped — Flask genuinely not
installed there by design, see `07_TEST_PLAN.md`).

## 1. Stated limitation (read first)

No Tailscale installation exists in the environment this phase was
implemented in. Everything in §2–§5 below that can be verified by code,
grep, or a hermetic test has been verified. **Live cross-device tailnet
behavior — a real second device sending a real Tailscale-injected
header, and a real off-tailnet request being unreachable at the network
layer — has not been observed and cannot be certified from here.**
`09_DEPLOYMENT_GUIDE.md`'s checklist marks these as mandatory manual
verification steps on the real Lisa node. This report does not claim
more than what was actually tested.

## 2. Authorization middleware validation

| Property | Evidence |
|---|---|
| Missing identity header → 403, audited | `test_console_auth.py::test_missing_header_denied_and_audited` |
| Invalid/wrong identity → 403, audited | `test_console_auth.py::test_wrong_identity_denied_and_audited` |
| Empty allowlist → 403 even with a valid-looking header (fail closed) | `test_console_auth.py::test_empty_allowlist_fails_closed_even_with_a_header` |
| Correct identity → 200, audited | `test_console_auth.py::test_correct_identity_granted_and_audited` |
| Multiple approved identities (comma-separated allowlist) | `test_console_auth.py::TestAllowedIdentities` (3 tests) |
| Every route requires identity, no exceptions | `test_console_routes.py::TestAuthGating.test_every_screen_requires_identity` (parametrized over all 6 screens) |
| The one POST route is also gated | `test_console_routes.py::test_decide_route_requires_identity_too` |

## 3. Negative-path testing (this phase's core deliverable)

| Case | Result | Evidence |
|---|---|---|
| Header present but empty string | Denied | `test_console_security.py::test_header_present_but_empty_denied` |
| Header whitespace-only | Denied | `test_header_whitespace_only_denied` |
| Header oversized (10,000+ chars) | Denied, not matched, **and truncated before audit write** (fixed this phase — see §6) | `test_oversized_header_denied_not_matched`, `test_oversized_header_truncated_before_audit_write` |
| Header exactly at the length boundary | Still matches correctly if legitimately allow-listed | `test_header_exactly_at_limit_can_still_match` |
| Unicode identity | Denied cleanly, no crash | `test_unicode_identity_handled_without_crashing` |
| Header containing quotes/backslashes | Safely JSON-encoded in the audit log, no format corruption | `test_identity_value_safely_json_encoded_in_audit` |
| Replay: identical `POST .../decide` submitted twice | Second attempt rejected (400); exactly one `decision_recorded` audit line results | `test_console_security.py::test_replaying_the_same_decide_request_is_harmless` |
| Repeated GETs | Naturally idempotent, no state change | `test_repeated_get_requests_are_naturally_idempotent` |
| Unauthorized access attempts | 403 + audited, every time, including repeats | `test_console_auth.py::test_every_request_is_audited_including_repeated_ones` |

There is no session token or nonce anywhere in this system to replay in
the traditional sense — the only mutable state a request can affect is a
bundle's `decision` field, and that field's own idempotency guard
(Phase C4's already-decided check) is what makes replay harmless.

## 4. Audit coverage and integrity review

**Coverage** — every write-capable module appends to
`reports/console/audit.jsonl`:

| Event | Module | Phase |
|---|---|---|
| `bundle_created` | `core/decision_bundle_exporter.py` | C1 (audit added C4) |
| `brief_generated` / `brief_generation_failed` | `advisors/gpt_advisor.py` | C2 (audit added C4) |
| `ntfy_sent` / `ntfy_failed` / `ntfy_duplicate_suppressed` | `advisors/notify.py` | C3 |
| `access_granted` / `access_denied` | `console/auth.py` | C4 |
| `decision_recorded` | `console/actions.py` | C4 |

**Integrity** — reviewed this phase, both structurally and behaviorally:

- Every one of the five write sites above opens `audit.jsonl` in append
  (`"a"`) mode only — confirmed by grepping each file's actual
  `audit_path.open(...)` call site, not a blanket text search (an
  earlier, naively broad version of this check produced a false
  positive against an unrelated file write; fixed before landing — see
  `test_every_source_module_opens_audit_in_append_mode_only`).
- The file only ever grows under repeated operations; a line written
  early in a session is byte-for-byte identical after many more
  operations (`test_audit_file_only_ever_grows`,
  `test_earlier_audit_lines_never_change`).
- **No cryptographic tamper-evidence exists** (no hash chaining, no
  signing). A party with direct filesystem write access could still
  hand-edit the file undetected. This is an accepted, explicitly
  documented residual risk (§7), proportionate to a single-operator
  local tool where the operator and the trust boundary are the same
  person — not a gap discovered late and hand-waved away.

## 5. Configuration validation

`console/config_check.py` / `bin/console-preflight` — 11 tests
(`test_console_config.py`), runs with no Flask dependency:

- Missing/empty `LISA_CONSOLE_OWNER_IDENTITY` → hard error (this is the
  one setting whose absence silently looks like "the Console is broken"
  rather than "unconfigured," since it fails closed with no visible
  symptom otherwise).
- Missing `LISA_CONSOLE_OPENAI_API_KEY` / `LISA_CONSOLE_NTFY_TOPIC` /
  `LISA_CONSOLE_BASE_URL` → warnings only, correctly reflecting that
  these degrade gracefully (Phase C2/C3 design) rather than break
  anything.
- Missing or malformed `registry/employees.yml` → error / warning as
  appropriate.
- `reports/console/` unwritable → error.

## 6. Findings from this phase (fixed, not just noted)

1. **Log-bloat via oversized identity header.** Before this phase, an
   attacker sending a very large `Tailscale-User-Login` value would be
   correctly denied, but the full value would still be written to
   `audit.jsonl` verbatim on every attempt — a cheap way to grow that
   file arbitrarily. Fixed: `console/auth.py::MAX_IDENTITY_LENGTH = 320`
   truncates before both the allowlist comparison and the audit write.
2. **Template crash on a bundle missing `audit_references`.** A
   negative-path test using a minimal (but schema-plausible) bundle
   fixture triggered a real `jinja2.exceptions.UndefinedError` — a 500,
   not a graceful degrade — in `bundle_detail.html`. Every bundle
   `core.decision_bundle_exporter.build_bundle()` produces does include
   this field unconditionally, so this wasn't reachable through the
   exporter today, but a future schema version, a hand-edited file, or a
   partially-written bundle from some other source could hit it. Fixed
   with a defensive `{% if bundle.audit_references %}` guard.
3. **`test_every_source_module_opens_audit_in_append_mode_only`'s first
   draft was itself too broad** (banned all `"w"`-mode opens anywhere in
   five files, which flagged `core/decision_bundle_exporter.py`'s
   unrelated `raw/workforce_evidence.jsonl` copy write). Corrected to
   check specifically the `audit_path.open(...)` call sites before this
   report was written — noted here because a security test that's wrong
   in the "too strict" direction is still worth catching and recording
   the correction for, not just quietly fixing.

## 7. Residual risk assessment

| Risk | Severity | Why it's accepted |
|---|---|---|
| No cryptographic audit-log tamper-evidence | Low, for this deployment | Single-operator tool; the operator and the trust boundary are the same person. Would become relevant if Console ever supported multiple distinct operators. |
| Check-then-write (not OS-level file lock) on the decision field | Low | Single-operator, browser-driven tool; a true race requires two simultaneous submissions from the same operator, which the UI doesn't encourage and which the guard still resolves safely (second write is rejected, not corrupted). |
| Live Tailscale behavior unverified from this environment | **Medium until manually verified** | No tailnet available here. Mitigated by: (a) the header-trust mechanism is Tailscale's own documented, widely-relied-upon behavior, not a novel assumption; (b) `09_DEPLOYMENT_GUIDE.md`'s checklist makes live verification a mandatory, explicit step before calling deployment complete. |
| Flask dev server used to serve the app (§`console/README.md`) | Low, contained | Acceptable for a single-operator tool reached only over the tailnet; not internet-facing. A `waitress`/production-server swap was scoped in the original C0 design as a future option, not required for this phase. |
| `LISA_CONSOLE_NTFY_TOPIC` transits headline text through a public third party (ntfy.sh) by default | Low, by design and disclosed | Documented since Phase C0/C3; the payload allowlist (`advisors/notify.py`) already minimizes what crosses that boundary, and self-hosting is a one-variable config change (`LISA_CONSOLE_NTFY_SERVER`) if this risk should be eliminated entirely. |
| No automated decision-consumption pipeline exists yet (design fully specified in `10_DECISION_CONSUMPTION_MODEL.md`: an Approval Watcher writes filesystem Execution Requests; the existing dispatcher, unchanged, is the only thing with execution authority) | None (not a risk) | Explicitly out of scope for C0–C5 — the absence of a consumer is what keeps Console's execution-incapability trivially true today. Not a gap to close, a property to preserve. The design deliberately keeps any future consumer outside `console/` and filesystem-mediated (never direct invocation), so building it later requires zero changes to anything in this phase. |

## 8. Summary

Every requirement in this phase's negative-path list (missing header,
invalid identity, empty allowlist, malformed headers, replay attempts,
unauthorized access, audit integrity, secret handling) has a
corresponding passing test, cited above by name. Two real defects were
found and fixed during this work (§6), not just documented as known
issues. The one item that cannot be certified from this environment —
live tailnet behavior — is stated plainly rather than implied to be
covered, with a concrete manual-verification checklist
(`09_DEPLOYMENT_GUIDE.md`) so it doesn't get silently skipped at actual
deployment time.

**Recommendation:** ready for CTO-role review. Not ready to claim "fully
verified against a live tailnet" until the manual checklist steps in
`09_DEPLOYMENT_GUIDE.md` are actually run on the real Lisa node.
