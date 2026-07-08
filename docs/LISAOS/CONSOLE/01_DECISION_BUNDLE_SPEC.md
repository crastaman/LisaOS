# Decision Bundle Specification

**Status:** IMPLEMENTED (Phase C1) — `core/decision_bundle_exporter.py`,
`bin/export-decision-bundle`, `tests/test_decision_bundle_exporter.py`
(15/15 passing). See `docs/LISAOS/CONSOLE/examples/sample_bundle.json`
for a complete worked example.

## Real-data grounding (read this first)

The original design assumed a live `job_id` flowing through materialized
job packets. Phase C1 grounding confirmed `jobs/schema.yml` is
**documentation-only** — no job packet is ever written to disk anywhere
in LisaOS today (`jobs/README.md` states this explicitly). The only real,
currently-populated identifier for a unit of work is **`work_package_id`**
in `reports/lisa/workforce_evidence.jsonl`.

Consequence: every bundle's `job_id` field is populated from a
`work_package_id` match, and `job_id_source` / `job_id_source_note`
record that mapping explicitly rather than pretending a live job-packet
system exists. Fields with no automatic source today (`job_type`,
`target_repository`, `requested_by`, `objective`, `status_at_export`,
`proposed_actions`) are optional caller-supplied parameters — the schema
still supports them (per the approved requirements), they're honestly
`null`/empty when nothing supplies them. Every such gap is also recorded
in the bundle's own `gaps` array, so a reader (Roshan or, later, GPT)
never has to guess why a field is empty.

## Format

JSON, schema `lisaos.console.decision_bundle.v1`. One directory per
bundle at `reports/console/bundles/<bundle_id>/`:

```
reports/console/bundles/<bundle_id>/
  bundle.json          # the bundle itself
  raw/
    workforce_evidence.jsonl   # copy of the matched evidence subset only
```

### Top-level fields

| Field | Populated by | Notes |
|---|---|---|
| `bundle_id` | exporter | `db-<UTC date>-<8 hex>`, generated per export, globally unique |
| `schema` | exporter | `lisaos.console.decision_bundle.v1` |
| `created_at` | exporter | ISO 8601 UTC |
| `job_id` | caller (matched against real evidence) | see grounding note above |
| `job_id_source` / `job_id_source_note` | exporter | provenance of the `job_id` mapping |
| `job_type`, `target_repository`, `requested_by`, `objective` | caller, optional | no automatic source exists yet |
| `status_at_export` | caller, optional | one of `completed`/`blocked`/`failed`/`null`; not derivable automatically |
| `approval_required` | caller, default `true` | no automatic approval-workflow logic in C1 |
| `participating_workers` | exporter, derived | deduplicated `{employee, department, physical_model, resolved_runtime, provider_id}` from matched evidence |
| `evidence.workforce_evidence` | exporter, derived | every `workforce_evidence.jsonl` record where `work_package_id == job_id` |
| `evidence.provider_resolution_evidence` | always `[]` in C1 | no `work_package_id`/`job_id` field exists in `provider_resolution_evidence.jsonl` to correlate against — see `gaps` |
| `evidence.reports`, `evidence.output_artifacts`, `evidence.test_results`, `evidence.policy_gate_report` | always empty/`null` in C1 | reserved fields; no persisted per-job source exists yet |
| `proposed_actions` | caller, optional | `[{action_id, description, risk_tier, reversible}]` |
| `risk_assessment` | always `null`/`[]` in C1 | reserved for the GPT Advisor (Phase C2) |
| `advisory` | always `null` in C1 | reserved for GPT Advisor Executive Brief linkage (Phase C2) |
| `governance_status` | exporter, derived | see below — repo-wide, not job-specific |
| `audit_references` | exporter, derived | source file paths + matched line counts, for traceability |
| `gaps` | exporter, derived | plain-language list of every field this export could not automatically populate, and why |
| `decision` | always `null` at export | written later by the Console's Safe Action Model (Phase C4) — never by the exporter |

### `governance_status` scope

`core/decision_bundle_exporter.py` reuses `core.governance_guard`'s real
`GovernanceViolation` model and `unacknowledged()` function directly
(no reimplementation). However, `GovernanceViolation` records are keyed
by subagent name/session, **not** by `work_package_id` — there is no data
model linking a specific governance violation to a specific job today.
`governance_status` therefore reports the **repository-wide** count of
unacknowledged violations at export time, with an explicit `scope_note`
field so this is never misread as "this job has no governance issues."

## Export trigger

`core/decision_bundle_exporter.py` exposes:

- `build_bundle(job_id, **kwargs) -> dict` — pure construction (reads
  evidence files, never writes).
- `write_bundle(bundle, bundles_dir=None) -> Path` — atomic, immutable
  write.
- `export_bundle(job_id, **kwargs) -> Path` — both steps in one call;
  what the CLI calls.

**On-demand only in Phase C1** via `bin/export-decision-bundle <job_id>
[options]`. There is no automatic trigger yet — an "automatically export
whenever a job reaches a terminal approval-required state" hook (as
originally envisioned) requires a live job-state machine that does not
exist in LisaOS today; wiring that in is deferred to whichever phase
introduces real job packets, not assumed here.

Every export is read-only with respect to all existing LisaOS state
(evidence logs, registries, `core.governance_guard`'s read helpers). The
only write is the new bundle directory itself.

## Immutability

Enforced in code, not just by convention: `write_bundle()` raises
`DecisionBundleError` if `reports/console/bundles/<bundle_id>/` already
exists. Because `bundle_id` includes a random 8-hex-character suffix,
collisions are effectively impossible; the refuse-to-overwrite check
exists specifically so immutability is a guarantee, not a hope.
`bundle.json` is written via a `.tmp` file + `os.replace()`, so a
concurrent reader (a future Console process) can never observe a
half-written file.

## Storage location and retention strategy

- **Location**: `reports/console/bundles/<bundle_id>/`, inside the
  already-gitignored `reports/` tree (matches the existing
  `reports/lisa/` convention — evidence/audit data is never committed).
- **Retention in Phase C1**: none. No automatic deletion or archival.
  Bundles persist indefinitely until a future archival mechanism is
  built — deferred deliberately rather than over-built now, since this
  is a local, single-user tool and silently deleting evidence data would
  be a worse failure mode than accumulating it. Disk usage should be
  monitored manually until an archival phase is scoped.
- **Future** (not yet implemented): the `DRAFT → PENDING_VALIDATION →
  PUBLISHED → ARCHIVED` lifecycle from
  `docs/LISAOS/LISAOS_ARTIFACT_LIFECYCLE.md` remains the intended model
  for later phases, once the Console (Phase C4) writes `decision` and a
  retention window can be defined against real usage patterns. No Python
  implementation of that state machine exists anywhere in `core/` today
  (confirmed) — Phase C1 does not add one.

## Schema versioning

Literal string `lisaos.console.decision_bundle.v1` on every bundle,
matching the `registry/*.yml` schema-versioning convention already used
in this repo. Backward-compatible additions (a new optional field) do
not require a version bump. Anything that changes or removes an existing
field's meaning bumps to `v2`. A reader (GPT Advisor, Console) that
encounters an unrecognized schema string should fail closed / degrade
rather than assume compatibility.

## CLI

```
bin/export-decision-bundle <job_id> \
  [--job-type TYPE] [--target-repository PATH] [--requested-by NAME] \
  [--objective TEXT] [--status-at-export {completed,blocked,failed}] \
  [--no-approval-required]
```

`job_id` must match a real `work_package_id` in
`reports/lisa/workforce_evidence.jsonl` to surface evidence. An unmatched
`job_id` still produces a valid, schema-conformant bundle with empty
evidence and a note in `gaps` — this is not an error, since exporting
ahead of evidence existing is a legitimate use.

Exit codes: `0` success, `2` usage/construction error
(`DecisionBundleError`).
