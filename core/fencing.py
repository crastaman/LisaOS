"""Duplicate-execution fencing for RC005 Wave 2 (C2)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "blocked", "timed_out"})
ACKNOWLEDGED_STATES = frozenset({"ACKNOWLEDGED", "DISPATCH_UNKNOWN"})


def normalized_brief(brief: str | None) -> str:
    return " ".join(str(brief or "").split())


def brief_hash(brief: str | None) -> str:
    return hashlib.sha256(normalized_brief(brief).encode("utf-8")).hexdigest()


def fencing_key(*, goal: str | None, package_id: str, task_family: str | None,
                session_key: str | None, brief_digest: str) -> str:
    value = [goal or "", package_id, task_family or "", session_key or "", brief_digest]
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FenceDecision:
    allowed: bool
    reason: str
    key: str


def check_dispatch_fence(
    *, record: dict[str, Any] | None, goal: str | None, package_id: str,
    task_family: str | None, session_key: str | None, brief_digest: str,
    reconciliation: dict[str, Any] | None = None,
) -> FenceDecision:
    key = fencing_key(goal=goal, package_id=package_id, task_family=task_family,
                      session_key=session_key, brief_digest=brief_digest)
    if not record:
        return FenceDecision(True, "no_prior_execution", key)
    status = str(record.get("status") or "not_started").lower()
    same_brief = record.get("brief_hash") == brief_digest
    same_family = (record.get("task_family") or "") == (task_family or "")
    same_session = bool(session_key and record.get("session_key") == session_key)
    acknowledged = str(record.get("dispatch_state") or "") in ACKNOWLEDGED_STATES
    recon = reconciliation or {}
    authorized = recon.get("decision") in {"RESUME", "RETRY"} and bool(recon.get("evidence"))
    if status not in TERMINAL_STATUSES and acknowledged and same_brief and same_family:
        if same_session and not authorized:
            return FenceDecision(False, "duplicate_nonterminal_dispatch", key)
        if same_session and recon.get("decision") == "RETRY":
            return FenceDecision(False, "retry_must_use_fresh_session", key)
    return FenceDecision(True, "reconciliation_or_fresh_dispatch", key)
