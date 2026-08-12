"""UNKNOWN reconciliation gate (RC003 Wave 1, package B1).

The gate is the only legal path out of EXECUTION_UNKNOWN. It deliberately
defaults to ESCALATE unless evidence proves either completion/live work
(RESUME) or no live/complete continuation (RETRY).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.execution_state import EXEC_UNKNOWN
from core.reliability_config import ReliabilityConfig, load_reliability_config

RECONCILE_RESUME = "RESUME"
RECONCILE_RETRY = "RETRY"
RECONCILE_ESCALATE = "ESCALATE"
RECONCILE_DECISIONS = frozenset({
    RECONCILE_RESUME,
    RECONCILE_RETRY,
    RECONCILE_ESCALATE,
})


@dataclass(frozen=True)
class ReconciliationEvidence:
    package_id: str
    run_id: str | None = None
    execution_state: str | None = None
    session_live: bool | None = None
    task_run_live: bool | None = None
    task_run_completed: bool | None = None
    artifact_present: bool | None = None
    verified_dead: bool | None = None
    death_evidence_authoritative: bool = False
    retry_count: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "run_id": self.run_id,
            "execution_state": self.execution_state,
            "session_live": self.session_live,
            "task_run_live": self.task_run_live,
            "task_run_completed": self.task_run_completed,
            "artifact_present": self.artifact_present,
            "verified_dead": self.verified_dead,
            "death_evidence_authoritative": self.death_evidence_authoritative,
            "retry_count": self.retry_count,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ReconciliationDecision:
    decision: str
    evidence: ReconciliationEvidence
    decided_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "decided_at": self.decided_at,
            "evidence": self.evidence.to_dict(),
        }


def _with_reason(evidence: ReconciliationEvidence, reason: str) -> ReconciliationEvidence:
    return ReconciliationEvidence(
        package_id=evidence.package_id,
        run_id=evidence.run_id,
        execution_state=evidence.execution_state,
        session_live=evidence.session_live,
        task_run_live=evidence.task_run_live,
        task_run_completed=evidence.task_run_completed,
        artifact_present=evidence.artifact_present,
        verified_dead=evidence.verified_dead,
        death_evidence_authoritative=evidence.death_evidence_authoritative,
        retry_count=evidence.retry_count,
        reasons=[*evidence.reasons, reason],
    )


def decide_reconciliation(
    evidence: ReconciliationEvidence,
    *,
    config: ReliabilityConfig | None = None,
) -> ReconciliationDecision:
    """Return RESUME, RETRY, or ESCALATE for an EXECUTION_UNKNOWN package.

    RETRY requires positive proof of death/no continuation. Ambiguous or
    contradictory evidence escalates; it never retries.
    """
    cfg = config or load_reliability_config()
    if evidence.execution_state != EXEC_UNKNOWN:
        e = _with_reason(evidence, "not EXECUTION_UNKNOWN; no retry gate needed")
        return ReconciliationDecision(RECONCILE_RESUME, e)

    if not cfg.reconciliation_enabled:
        e = _with_reason(evidence, "reconciliation disabled; fail-safe escalation")
        return ReconciliationDecision(RECONCILE_ESCALATE, e)

    if evidence.task_run_completed is True and evidence.artifact_present is True:
        e = _with_reason(evidence, "completed task_run and artifact found")
        return ReconciliationDecision(RECONCILE_RESUME, e)

    if evidence.session_live is True or evidence.task_run_live is True:
        e = _with_reason(evidence, "live execution signal found")
        return ReconciliationDecision(RECONCILE_RESUME, e)

    if evidence.verified_dead is True and evidence.death_evidence_authoritative is True:
        if evidence.retry_count >= cfg.auto_retry_max:
            e = _with_reason(evidence, "retry limit reached")
            return ReconciliationDecision(RECONCILE_ESCALATE, e)
        e = _with_reason(evidence, "verified dead/no continuation; retry allowed")
        return ReconciliationDecision(RECONCILE_RETRY, e)

    if evidence.verified_dead is True:
        e = _with_reason(evidence, "death evidence not authoritative; retry forbidden")
        return ReconciliationDecision(RECONCILE_ESCALATE, e)

    e = _with_reason(evidence, "indeterminate; retry forbidden without proof")
    return ReconciliationDecision(RECONCILE_ESCALATE, e)


def graph_unknown_packages(state: dict[str, Any] | None) -> list[str]:
    """Return package ids whose graph-state value requires reconciliation."""
    if not state:
        return []
    out: list[str] = []
    for pid, raw in (state.get("packages") or {}).items():
        if raw == "execution_unknown":
            out.append(pid)
        elif isinstance(raw, dict) and (
            raw.get("status") in {"execution_unknown", "EXECUTION_UNKNOWN"}
            or (
                raw.get("execution_state") == EXEC_UNKNOWN
                and raw.get("status") not in {"running", "in_progress"}
            )
        ):
            out.append(pid)
    return out


def artifact_present(path: str | Path | None) -> bool | None:
    """Tiny artifact probe used by tests and callers with a declared artifact."""
    if path is None:
        return None
    return Path(path).exists()
