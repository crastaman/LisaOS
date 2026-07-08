"""LisaOS Decision Bundle Exporter (Lisa Console v1, Phase C1).

Assembles a self-contained "Decision Bundle" for one unit of work, so that a
human (Roshan) or an advisory-only GPT process can review everything LisaOS
knows about it without any further context retrieval. See
docs/LISAOS/CONSOLE/01_DECISION_BUNDLE_SPEC.md for the full specification.

Strictly read-only with respect to all existing LisaOS state: it reads
reports/lisa/*.jsonl evidence logs and calls into core.governance_guard's
read-only helpers. It never imports core.dispatcher, core.workforce_resolver,
or any engines/* module, and never mutates anything outside its own bundle
output directory (reports/console/bundles/<bundle_id>/). Exporting a bundle
can never trigger execution -- there is no code path here that dispatches,
schedules, or invokes a job.

Real-data caveat (see docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md and
docs/LISAOS/CONSOLE/01_DECISION_BUNDLE_SPEC.md for the full explanation):
LisaOS job packets (jobs/schema.yml) are documentation-only today -- no job
packet is ever materialized as a file. The only real, currently-populated
identifier for a unit of work is `work_package_id` in
reports/lisa/workforce_evidence.jsonl. Every bundle's `job_id` field is
populated from a work_package_id match, and `job_id_source` records that
mapping explicitly rather than pretending a live job-packet system exists.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.governance_guard import GovernanceViolation, unacknowledged

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
WORKFORCE_EVIDENCE_LOG = LISA_BASE / "reports" / "lisa" / "workforce_evidence.jsonl"
VIOLATIONS_LOG = LISA_BASE / "reports" / "lisa" / "governance_violations.jsonl"
ACKNOWLEDGEMENTS_LOG = LISA_BASE / "reports" / "lisa" / "governance_acknowledgements.jsonl"
BUNDLES_DIR = LISA_BASE / "reports" / "console" / "bundles"
AUDIT_LOG = LISA_BASE / "reports" / "console" / "audit.jsonl"

SCHEMA = "lisaos.console.decision_bundle.v1"

_VALID_STATUS_AT_EXPORT = {None, "completed", "blocked", "failed"}


class DecisionBundleError(Exception):
    """Raised when a Decision Bundle cannot be built or written safely."""


@dataclass
class ProposedAction:
    action_id: str
    description: str
    risk_tier: str = "medium"
    reversible: bool = True

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "risk_tier": self.risk_tier,
            "reversible": self.reversible,
        }


# --------------------------------------------------------------------------- #
# Small read-only helpers
# --------------------------------------------------------------------------- #

def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_bundle_id() -> str:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"db-{date}-{uuid.uuid4().hex[:8]}"


def _match_workforce_evidence(job_id: str, evidence_path: Path) -> list[dict]:
    """Every workforce_evidence.jsonl record whose work_package_id == job_id."""
    return [r for r in _read_jsonl(evidence_path) if r.get("work_package_id") == job_id]


def _participating_workers(matched: list[dict]) -> list[dict]:
    """Deduplicated worker/employee assignments drawn from matched evidence."""
    seen: set[tuple] = set()
    workers: list[dict] = []
    for rec in matched:
        key = (rec.get("employee"), rec.get("department"))
        if key in seen:
            continue
        seen.add(key)
        workers.append({
            "employee": rec.get("employee"),
            "department": rec.get("department"),
            "physical_model": rec.get("physical_model"),
            "resolved_runtime": rec.get("resolved_runtime"),
            "provider_id": rec.get("provider_id"),
        })
    return workers


def _governance_status(violations_path: Path, ack_path: Path) -> dict:
    """Repo-wide unacknowledged governance violation status at export time.

    Not job-specific: LisaOS's governance violation records
    (core.governance_guard.GovernanceViolation) are keyed by subagent
    name/session, not by work_package_id -- there is no data model linking a
    violation to a specific unit of work today. See scope_note.
    """
    raw = _read_jsonl(violations_path)
    violations = [GovernanceViolation(**rec) for rec in raw]
    pending = unacknowledged(violations, ack_path=ack_path)
    return {
        "unacknowledged_violation_count": len(pending),
        "unacknowledged_violation_ids": [v.violation_id for v in pending],
        "scope_note": (
            "Governance violations are tracked repository-wide, not correlated "
            "to a specific job_id/work_package_id in the current LisaOS data "
            "model. This reflects overall unacknowledged governance state at "
            "export time, not violations specific to this job."
        ),
    }


# --------------------------------------------------------------------------- #
# Bundle construction (pure w.r.t. its inputs; reads evidence files)
# --------------------------------------------------------------------------- #

def build_bundle(
    job_id: str,
    *,
    job_type: str | None = None,
    target_repository: str | None = None,
    requested_by: str | None = None,
    objective: str | None = None,
    status_at_export: str | None = None,
    approval_required: bool = True,
    proposed_actions: list[ProposedAction] | None = None,
    evidence_path: Path | None = None,
    violations_path: Path | None = None,
    ack_path: Path | None = None,
    bundle_id: str | None = None,
) -> dict[str, Any]:
    """Assemble (but do not write) a Decision Bundle dict for one job_id.

    job_id must match a real `work_package_id` in workforce_evidence.jsonl to
    surface any evidence -- see module docstring. An unmatched job_id still
    produces a valid, schema-conformant bundle with empty evidence and a
    `gaps` entry noting nothing was found; it is not an error, since a human
    may be exporting ahead of evidence existing.
    """
    if not job_id:
        raise DecisionBundleError("job_id is required and must be non-empty")
    if status_at_export not in _VALID_STATUS_AT_EXPORT:
        raise DecisionBundleError(
            f"status_at_export must be one of {sorted(s for s in _VALID_STATUS_AT_EXPORT if s)} "
            f"or None, got {status_at_export!r}"
        )

    evidence_path = evidence_path or WORKFORCE_EVIDENCE_LOG
    violations_path = violations_path or VIOLATIONS_LOG
    ack_path = ack_path or ACKNOWLEDGEMENTS_LOG
    proposed_actions = proposed_actions or []

    matched = _match_workforce_evidence(job_id, evidence_path)

    gaps: list[str] = []
    if not matched:
        gaps.append(
            f"No workforce_evidence.jsonl records found for job_id={job_id!r} "
            f"(matched against work_package_id) -- bundle contains no "
            f"execution evidence."
        )
    if status_at_export is None:
        gaps.append(
            "status_at_export: not supplied -- no live job-state machine "
            "exists in LisaOS today; supply explicitly if known from "
            "external context."
        )
    gaps.append(
        "evidence.provider_resolution_evidence: not populated -- "
        "provider_resolution_evidence.jsonl has no work_package_id/job_id "
        "correlation field in the current data model."
    )
    gaps.append(
        "evidence.reports / output_artifacts / test_results / "
        "policy_gate_report: reserved fields -- no persisted, per-job "
        "source exists yet for any of these."
    )
    gaps.append(
        "risk_assessment / advisory: reserved for the GPT Advisor "
        "(Phase C2) -- not populated by the exporter."
    )

    bundle: dict[str, Any] = {
        "bundle_id": bundle_id or _generate_bundle_id(),
        "schema": SCHEMA,
        "created_at": _now_iso(),
        "job_id": job_id,
        "job_id_source": "work_package_id",
        "job_id_source_note": (
            "LisaOS job packets (jobs/schema.yml) are documentation-only "
            "today -- no live job-packet store exists. job_id is populated "
            "from the real, running identifier (workforce_evidence.jsonl's "
            "work_package_id) and will be revisited if/when job packets "
            "become live."
        ),
        "job_type": job_type,
        "target_repository": target_repository,
        "requested_by": requested_by,
        "objective": objective,
        "status_at_export": status_at_export,
        "approval_required": approval_required,
        "participating_workers": _participating_workers(matched),
        "evidence": {
            "workforce_evidence": matched,
            "provider_resolution_evidence": [],
            "reports": [],
            "output_artifacts": [],
            "test_results": {},
            "policy_gate_report": None,
        },
        "proposed_actions": [a.to_dict() for a in proposed_actions],
        "risk_assessment": {
            "overall_risk": None,
            "risk_flags": [],
        },
        "advisory": {
            "recommendation": None,
            "confidence": None,
            "brief_id": None,
        },
        "governance_status": _governance_status(violations_path, ack_path),
        "audit_references": {
            "source_files": [
                {"path": str(evidence_path), "matched_lines": len(matched)},
                {"path": str(violations_path), "matched_lines": None},
                {"path": str(ack_path), "matched_lines": None},
            ],
            "raw_copy": "raw/workforce_evidence.jsonl",
        },
        "gaps": gaps,
        "decision": None,
    }
    return bundle


# --------------------------------------------------------------------------- #
# Write path (the only place this module touches disk for output)
# --------------------------------------------------------------------------- #

def _append_audit(record: dict[str, Any], audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def write_bundle(
    bundle: dict[str, Any], *, bundles_dir: Path | None = None, audit_path: Path | None = None,
) -> Path:
    """Write a built bundle atomically and immutably.

    Refuses to overwrite an existing bundle directory -- once exported, a
    bundle_id is final. Writes bundle.json via a .tmp + os.replace so a
    concurrent reader never observes a half-written file, and copies the
    matched workforce_evidence subset into raw/ for self-contained review.
    Appends one "bundle_created" line to the Console audit log (Phase C4
    addition -- the Audit screen needs a real event for every bundle, not
    just ntfy events).
    """
    bundle_id = bundle.get("bundle_id")
    if not bundle_id:
        raise DecisionBundleError("bundle has no bundle_id -- build_bundle() first")

    target_dir = (bundles_dir or BUNDLES_DIR) / bundle_id
    if target_dir.exists():
        raise DecisionBundleError(
            f"bundle directory already exists (bundles are immutable once "
            f"exported): {target_dir}"
        )
    target_dir.mkdir(parents=True)
    raw_dir = target_dir / "raw"
    raw_dir.mkdir()

    tmp_path = target_dir / "bundle.json.tmp"
    final_path = target_dir / "bundle.json"
    tmp_path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, final_path)

    matched = bundle.get("evidence", {}).get("workforce_evidence", [])
    raw_evidence_path = raw_dir / "workforce_evidence.jsonl"
    with raw_evidence_path.open("w", encoding="utf-8") as fh:
        for rec in matched:
            fh.write(json.dumps(rec) + "\n")

    _append_audit(
        {
            "event": "bundle_created",
            "bundle_id": bundle_id,
            "job_id": bundle.get("job_id"),
            "at": _now_iso(),
            "status_at_export": bundle.get("status_at_export"),
            "approval_required": bundle.get("approval_required"),
        },
        audit_path or AUDIT_LOG,
    )

    return final_path


def export_bundle(
    job_id: str,
    *,
    bundles_dir: Path | None = None,
    audit_path: Path | None = None,
    **build_kwargs: Any,
) -> Path:
    """Build and write a Decision Bundle for job_id in one call. See CLI:
    bin/export-decision-bundle.
    """
    bundle = build_bundle(job_id, **build_kwargs)
    return write_bundle(bundle, bundles_dir=bundles_dir, audit_path=audit_path)
