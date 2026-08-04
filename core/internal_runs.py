"""LisaOS internal runtime provenance (LISA-I010, DEFECT-1 repair).

WHY THIS EXISTS
---------------
LisaOS makes OpenClaw calls of two structurally different kinds:

  * WORK PACKAGE EXECUTION -- a worker running a dispatched package. It must
    produce workforce evidence and a Work Product.
  * INTERNAL CONTROL-PLANE CALLS -- the Phase 2 planner proposer, which runs
    BEFORE a work-package graph exists. It can never produce a Work Product,
    because there is no package to produce one for.

The Phase 6 governance detector correlated every `task_runs` row against
work-product evidence, so the planner's own call looked exactly like an
ungoverned bypass. LISA-I009 proved the consequence: every `--plan` invocation
manufactured a violation that blocked its own dispatch. LisaOS blocked itself.

THE CONTRACT (evidence-based, never prompt-based)
-------------------------------------------------
An internal call records a machine-readable provenance row keyed by the run id
OpenClaw itself returns. The detector then requires that claim to be
CORROBORATED before honouring it:

    internal_planner      => an intake record with that request_id
                             AND a planning artifact for that request_id
    work_package_worker   => workforce evidence AND a Work Product

A row that merely CLAIMS to be internal, with no correlated intake record and
no planning artifact, is still a violation. This is the whole point: the
exemption is earned by evidence that only the real pipeline can produce, not
granted by an agent name, a model, or any wording in a prompt.

Deliberately NOT implemented, because each would be a hole:
  * exempting an agent id (`lisa-claude-sonnet` also runs real work packages);
  * exempting a model or provider;
  * matching prompt text such as "internal planner" or "planning only".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LISA_BASE = Path(__file__).resolve().parent.parent
ORCHESTRATION_DIR = LISA_BASE / "reports" / "lisa" / "orchestration"
INTERNAL_RUNS_LOG = ORCHESTRATION_DIR / "internal_runs.jsonl"
INTAKE_LOG = ORCHESTRATION_DIR / "intake.jsonl"
PLANS_DIR = ORCHESTRATION_DIR / "plans"

PROVENANCE_SCHEMA_VERSION = "lisa-internal-run/1"

# Run kinds. Extend only when a genuinely new control-plane call type exists.
RUN_KIND_INTERNAL_PLANNER = "internal_planner"
RUN_KIND_WORK_PACKAGE_WORKER = "work_package_worker"

# What each kind must be able to show. Used by the detector to decide WHICH
# evidence to demand, rather than demanding work products from everything.
EVIDENCE_EXPECTATIONS: dict[str, dict[str, Any]] = {
    RUN_KIND_INTERNAL_PLANNER: {
        "stage": "planning",
        "evidence_expected": "planning_artifact",
        "work_product_expected": False,
    },
    RUN_KIND_WORK_PACKAGE_WORKER: {
        "stage": "execution",
        "evidence_expected": "work_product",
        "work_product_expected": True,
    },
}


def record_internal_run(
    run_id: str,
    *,
    run_kind: str = RUN_KIND_INTERNAL_PLANNER,
    request_id: str | None,
    path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Append one provenance row for an internal control-plane call.

    Returns the record, or None when it cannot be written. Failure is
    deliberately non-fatal but also NOT concealed in its effect: an unrecorded
    internal run simply fails to correlate later and is reported as a
    violation. That is the safe direction -- provenance is something a run must
    EARN, so losing it must never silently grant an exemption.
    """
    if not run_id:
        return None
    expectations = EVIDENCE_EXPECTATIONS.get(run_kind)
    if expectations is None:
        raise ValueError(
            f"unknown run_kind {run_kind!r}; expected one of "
            f"{sorted(EVIDENCE_EXPECTATIONS)}")

    record = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "run_id": str(run_id),
        "run_kind": run_kind,
        "request_id": request_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **expectations,
    }
    target = Path(path) if path is not None else INTERNAL_RUNS_LOG
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        return None
    return record


def load_internal_runs(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """run_id -> provenance record. A corrupt line never hides the rest."""
    target = Path(path) if path is not None else INTERNAL_RUNS_LOG
    out: dict[str, dict[str, Any]] = {}
    if not target.is_file():
        return out
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("run_id"):
            out[str(record["run_id"])] = record
    return out


def _intake_request_ids(path: str | Path | None = None) -> set[str]:
    target = Path(path) if path is not None else INTAKE_LOG
    ids: set[str] = set()
    if not target.is_file():
        return ids
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("request_id"):
            ids.add(str(record["request_id"]))
    return ids


def verify_internal_run(
    record: dict[str, Any],
    *,
    intake_path: str | Path | None = None,
    plans_dir: str | Path | None = None,
) -> tuple[bool, list[str]]:
    """Is this provenance claim corroborated by evidence only LisaOS can make?

    Returns (ok, missing). A claim is honoured ONLY when every piece of
    evidence its run_kind promises actually exists.
    """
    missing: list[str] = []
    run_kind = record.get("run_kind")
    if run_kind not in EVIDENCE_EXPECTATIONS:
        return False, [f"unknown run_kind {run_kind!r}"]

    request_id = record.get("request_id")
    if not request_id:
        return False, ["provenance record carries no request_id"]

    if str(request_id) not in _intake_request_ids(intake_path):
        missing.append("intake_record")

    if run_kind == RUN_KIND_INTERNAL_PLANNER:
        plans = Path(plans_dir) if plans_dir is not None else PLANS_DIR
        if not (plans / f"{request_id}.json").is_file():
            missing.append("planning_artifact")

    return (not missing), missing
