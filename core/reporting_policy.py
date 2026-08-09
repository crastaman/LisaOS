"""LisaOS Executive Reporting Policy (CWO-001).

Quiet MAIN / Executive Reporting Mode as durable behavior. DeepSeek MAIN must
NOT continuously narrate polling, queue checks, dependency reasoning, worker
monitoring, routine provider checks, command narration, internal planning,
obvious next steps, or repeated state.

Roshan receives reports ONLY for:
  * meaningful completion
  * meaningful provider exhaustion
  * capacity becoming available where execution changes
  * genuine blocker
  * decision required
  * governance/safety issue
  * material failure
  * material scope/state change
  * approximately hourly unattended update when useful

Default executive output format:

    COMPLETED
    - material outcome
    CAPACITY
    - meaningful change only
    NEXT
    - one concise sentence if useful
    DECISION
    - only if required

If nothing important happened: DO NOT REPORT. Continue working.

Worker output economy: worker completions should focus on result / files
changed-inspected / tests-evidence / blockers / decisions-required, NOT long
introductions, restated briefs, narrated obvious work, speculative essays, or
repetitive reports. Engineering detail lives in code/tests/evidence artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Event classes.
COMPLETION = "completion"
EXHAUSTION = "provider_exhaustion"
CAPACITY_AVAILABLE = "capacity_available"
BLOCKER = "blocker"
DECISION_REQUIRED = "decision_required"
GOVERNANCE = "governance"
FAILURE = "material_failure"
SCOPE_CHANGE = "material_scope_change"
HOURLY_UPDATE = "hourly_update"

# Routinely-suppressed narration classes (internal orchestration).
SUPPRESSED_CLASSES = (
    "polling",
    "queue_check",
    "dependency_reasoning",
    "worker_monitoring",
    "routine_provider_check",
    "command_narration",
    "internal_planning",
    "obvious_next_step",
    "repeated_state",
)

# Reportable classes.
REPORTABLE_CLASSES = (
    COMPLETION,
    EXHAUSTION,
    CAPACITY_AVAILABLE,
    BLOCKER,
    DECISION_REQUIRED,
    GOVERNANCE,
    FAILURE,
    SCOPE_CHANGE,
    HOURLY_UPDATE,
)


@dataclass
class ReportEvent:
    """One event to classify for MAIN executive reporting."""

    event_class: str
    detail: str = ""
    material: bool = True          # False => suppressed even if class matches
    payload: dict[str, Any] = field(default_factory=dict)


def classify_event(event_class: str, *, material: bool = True) -> bool:
    """Return True if the event should be reported to Roshan.

    Routine narration (polling, queue checks, dependency reasoning, worker
    monitoring, routine provider checks, command narration, internal planning,
    obvious next steps, repeated state) is suppressed. Material events of
    reportable classes surface.
    """
    if not material:
        return False
    return event_class in REPORTABLE_CLASSES


def suppress_if_nothing(events: list[ReportEvent]) -> bool:
    """Return True if NOTHING material happened -- DO NOT REPORT.

    If no reportable event exists in the batch, MAIN stays quiet and keeps
    working.
    """
    return not any(classify_event(e.event_class, material=e.material) for e in events)


def executive_summary(
    *,
    completed: list[str] | None = None,
    capacity: list[str] | None = None,
    next_step: str = "",
    decision: str = "",
) -> str:
    """Render the executive output format.

    COMPLETED / CAPACITY / NEXT / DECISION. Empty sections are omitted.
    """
    parts: list[str] = []
    if completed:
        parts.append("COMPLETED\n" + "\n".join(f"- {c}" for c in completed))
    if capacity:
        parts.append("CAPACITY\n" + "\n".join(f"- {c}" for c in capacity))
    if next_step:
        parts.append("NEXT\n" + f"- {next_step}")
    if decision:
        parts.append("DECISION\n" + f"- {decision}")
    return "\n\n".join(parts)


def worker_report_minimal(
    *,
    result: str,
    files_changed: list[str] | None = None,
    files_inspected: list[str] | None = None,
    tests_evidence: list[str] | None = None,
    blockers: list[str] | None = None,
    decisions_required: list[str] | None = None,
) -> str:
    """Worker output economy: result / files / tests-evidence / blockers /
    decisions. No introductions, no restated briefs, no narration."""
    parts: list[str] = [f"RESULT: {result}"]
    if files_changed:
        parts.append("FILES CHANGED\n" + "\n".join(f"- {f}" for f in files_changed))
    if files_inspected:
        parts.append("FILES INSPECTED\n" + "\n".join(f"- {f}" for f in files_inspected))
    if tests_evidence:
        parts.append("TESTS / EVIDENCE\n" + "\n".join(f"- {t}" for t in tests_evidence))
    if blockers:
        parts.append("BLOCKERS\n" + "\n".join(f"- {b}" for b in blockers))
    if decisions_required:
        parts.append("DECISIONS REQUIRED\n" + "\n".join(f"- {d}" for d in decisions_required))
    return "\n".join(parts)


__all__ = [
    "classify_event",
    "suppress_if_nothing",
    "executive_summary",
    "worker_report_minimal",
    "ReportEvent",
    "COMPLETION",
    "EXHAUSTION",
    "CAPACITY_AVAILABLE",
    "BLOCKER",
    "DECISION_REQUIRED",
    "GOVERNANCE",
    "FAILURE",
    "SCOPE_CHANGE",
    "HOURLY_UPDATE",
    "REPORTABLE_CLASSES",
    "SUPPRESSED_CLASSES",
]
