# Decision Bundle Specification

**Status:** DESIGN APPROVED — not yet implemented (Phase C1)

## Format

JSON, schema `lisaos.console.decision_bundle.v1`. One file per bundle at
`reports/console/bundles/<bundle_id>/bundle.json`, plus a `raw/`
subfolder holding **copies** (not symlinks, for immutability) of the
evidence files it aggregates.

```json
{
  "bundle_id": "db-2026-07-08-0001",
  "schema": "lisaos.console.decision_bundle.v1",
  "created_at": "2026-07-08T00:00:00Z",
  "job_id": "...",
  "job_type": "...",
  "target_repository": "...",
  "requested_by": "...",
  "objective": "...",
  "status_at_export": "completed | blocked | failed",
  "approval_required": true,
  "evidence": {
    "workforce_evidence": [],
    "governance_violations": [],
    "governance_acknowledgements": [],
    "provider_resolution_evidence": [],
    "output_artifacts": [
      {"path": "...", "artifact_lifecycle_state": "...", "checksum": "..."}
    ],
    "test_results": {},
    "policy_gate_report": {}
  },
  "proposed_actions": [
    {"action_id": "...", "description": "...", "risk_tier": "low|medium|high", "reversible": true}
  ],
  "decision": null
}
```

`evidence.*` arrays are the matching lines pulled from the existing
append-only JSONL evidence logs under `reports/lisa/`
(`workforce_evidence.jsonl`, `governance_violations.jsonl`,
`governance_acknowledgements.jsonl`, `provider_resolution_evidence.jsonl`),
filtered by `job_id`.

## Export trigger

New `core/decision_bundle_exporter.py`, called:

1. **Automatically** whenever a job packet transitions into a state with
   `approval_required: true` and `status` in `{completed, blocked,
   failed}` — hooked at the same point `governance_guard` already records
   evidence.
2. **On demand** via `bin/export-decision-bundle <job_id>`.

Lisa always exports the **whole** relevant bundle — every evidence source
tied to that `job_id` — never a partial/selected file. Roshan and GPT
never choose which files go into a bundle.

## Lifecycle

Reuses the existing state machine from
`docs/LISAOS/LISAOS_ARTIFACT_LIFECYCLE.md`:

```
DRAFT (at export)
  -> PENDING_VALIDATION (once GPT Advisor has processed it)
  -> PUBLISHED (once Roshan decides)
  -> ARCHIVED (after a retention window)
```

## Write discipline

Bundle files are written to a `.tmp` path and atomically renamed on
success only — `/approvals` must never show a half-written bundle. The
`decision` field is written exactly once per bundle, guarded by a
compare-and-swap check against `decision: null` (see
`00_ARCHITECTURE.md` § Failure handling).
