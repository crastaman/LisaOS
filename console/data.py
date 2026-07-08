"""Read-only data access for Lisa Console (Phase C4).

Every function in this module only ever reads from disk -- bundles,
briefs, notification markers, the audit log, and registry/employees.yml.
Nothing here writes anything; writes live exclusively in
core.decision_bundle_exporter (bundle creation, Phase C1),
advisors.gpt_advisor (brief generation, Phase C2), advisors.notify
(notifications, Phase C3), and console.actions (decisions, Phase C4).

No LisaOS runtime imports (core/, engines/) -- path constants are
redeclared locally rather than imported, matching the same convention
already used independently in core/decision_bundle_exporter.py,
advisors/gpt_advisor.py, and advisors/notify.py (each of which also
redeclares LISA_BASE rather than importing it from a shared module).
Reading registry/employees.yml is plain YAML parsing, not an import of
any workforce-resolution code.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
BUNDLES_DIR = LISA_BASE / "reports" / "console" / "bundles"
BRIEFS_DIR = LISA_BASE / "reports" / "console" / "briefs"
NOTIFICATIONS_DIR = LISA_BASE / "reports" / "console" / "notifications"
AUDIT_LOG = LISA_BASE / "reports" / "console" / "audit.jsonl"
EMPLOYEES_REGISTRY = LISA_BASE / "registry" / "employees.yml"
WORKFORCE_EVIDENCE_LOG = LISA_BASE / "reports" / "lisa" / "workforce_evidence.jsonl"


# --------------------------------------------------------------------------- #
# Bundles
# --------------------------------------------------------------------------- #

def list_bundles(bundles_dir: Path | None = None) -> list[dict[str, Any]]:
    """All bundles, newest created_at first."""
    bundles_dir = bundles_dir or BUNDLES_DIR
    if not bundles_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for entry in bundles_dir.iterdir():
        bundle_path = entry / "bundle.json"
        if bundle_path.is_file():
            try:
                out.append(json.loads(bundle_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
    out.sort(key=lambda b: b.get("created_at") or "", reverse=True)
    return out


def load_bundle(bundle_id: str, *, bundles_dir: Path | None = None) -> dict[str, Any] | None:
    bundle_path = (bundles_dir or BUNDLES_DIR) / bundle_id / "bundle.json"
    if not bundle_path.is_file():
        return None
    return json.loads(bundle_path.read_text(encoding="utf-8"))


def list_pending_approvals(bundles_dir: Path | None = None) -> list[dict[str, Any]]:
    return [b for b in list_bundles(bundles_dir) if b.get("decision") is None]


# --------------------------------------------------------------------------- #
# Briefs
# --------------------------------------------------------------------------- #

def list_briefs(briefs_dir: Path | None = None) -> list[dict[str, Any]]:
    """All briefs, newest created_at first."""
    briefs_dir = briefs_dir or BRIEFS_DIR
    if not briefs_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for entry in briefs_dir.iterdir():
        if entry.suffix == ".json" and not entry.name.endswith(".json.tmp"):
            try:
                out.append(json.loads(entry.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
    out.sort(key=lambda b: b.get("created_at") or "", reverse=True)
    return out


def load_brief(brief_id: str, *, briefs_dir: Path | None = None) -> dict[str, Any] | None:
    brief_path = (briefs_dir or BRIEFS_DIR) / f"{brief_id}.json"
    if not brief_path.is_file():
        return None
    return json.loads(brief_path.read_text(encoding="utf-8"))


def briefs_for_bundle(bundle_id: str, briefs_dir: Path | None = None) -> list[dict[str, Any]]:
    """All briefs generated for a given bundle_id, newest first -- there can
    be more than one (e.g. a degraded attempt followed by a later retry).
    """
    return [b for b in list_briefs(briefs_dir) if b.get("bundle_id") == bundle_id]


def latest_brief_for_bundle(bundle_id: str, briefs_dir: Path | None = None) -> dict[str, Any] | None:
    matches = briefs_for_bundle(bundle_id, briefs_dir)
    return matches[0] if matches else None


# --------------------------------------------------------------------------- #
# Notification status
# --------------------------------------------------------------------------- #

def notification_status_for_brief(
    brief_id: str, notifications_dir: Path | None = None,
) -> dict[str, Any] | None:
    marker_path = (notifications_dir or NOTIFICATIONS_DIR) / f"{brief_id}.json"
    if not marker_path.is_file():
        return None
    return json.loads(marker_path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Workers (read-only registry mirror + recent participation)
# --------------------------------------------------------------------------- #

def list_workers(
    *, registry_path: Path | None = None, evidence_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Read-only mirror of registry/employees.yml, annotated with recent
    participation counts from workforce_evidence.jsonl. No control actions
    -- this function has no write capability and nothing in console/
    calls anything that could assign or dispatch work to a worker.
    """
    registry_path = registry_path or EMPLOYEES_REGISTRY
    if not registry_path.is_file():
        return []
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    employees = registry.get("employees", {})

    participation = _participation_counts(evidence_path or WORKFORCE_EVIDENCE_LOG)

    workers = []
    for employee_id, spec in employees.items():
        workers.append({
            "id": employee_id,
            "department": spec.get("department"),
            "seniority": spec.get("seniority"),
            "responsibilities": spec.get("responsibilities"),
            "capabilities": spec.get("capabilities", []),
            "preferred_model": spec.get("preferred_model"),
            "recent_assignments": participation.get(employee_id, 0),
        })
    workers.sort(key=lambda w: (-w["recent_assignments"], w["id"]))
    return workers


def _participation_counts(evidence_path: Path) -> dict[str, int]:
    if not evidence_path.is_file():
        return {}
    counts: dict[str, int] = {}
    for line in evidence_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        employee = rec.get("employee")
        if employee:
            counts[employee] = counts.get(employee, 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #

def tail_audit(*, audit_path: Path | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Most-recent-first audit entries, capped at `limit`."""
    audit_path = audit_path or AUDIT_LOG
    if not audit_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    records.reverse()
    return records[:limit]


# --------------------------------------------------------------------------- #
# Dashboard summary
# --------------------------------------------------------------------------- #

def dashboard_summary(
    *,
    bundles_dir: Path | None = None,
    briefs_dir: Path | None = None,
    audit_path: Path | None = None,
    registry_path: Path | None = None,
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    bundles = list_bundles(bundles_dir)
    briefs = list_briefs(briefs_dir)
    audit = tail_audit(audit_path=audit_path, limit=10_000)

    pending = [b for b in bundles if b.get("decision") is None]
    approved = [b for b in bundles if (b.get("decision") or {}).get("choice") == "approve"]
    rejected = [b for b in bundles if (b.get("decision") or {}).get("choice") == "reject"]

    ok_briefs = [b for b in briefs if b.get("status") == "ok"]
    degraded_briefs = [b for b in briefs if b.get("status") == "degraded"]

    ntfy_sent = sum(1 for a in audit if a.get("event") == "ntfy_sent")
    ntfy_failed = sum(1 for a in audit if a.get("event") == "ntfy_failed")
    ntfy_suppressed = sum(1 for a in audit if a.get("event") == "ntfy_duplicate_suppressed")

    workers = list_workers(registry_path=registry_path, evidence_path=evidence_path)
    active_workers = sum(1 for w in workers if w["recent_assignments"] > 0)

    return {
        "bundle_count": len(bundles),
        "pending_count": len(pending),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "brief_count": len(briefs),
        "brief_ok_count": len(ok_briefs),
        "brief_degraded_count": len(degraded_briefs),
        "notification_sent": ntfy_sent,
        "notification_failed": ntfy_failed,
        "notification_suppressed": ntfy_suppressed,
        "worker_count": len(workers),
        "worker_active_count": active_workers,
        "recent_briefs": briefs[:5],
    }
