"""LisaOS Session + Cache Policy (CWO-001).

Makes the S048 ~21M cacheWrite churn lesson durable: reuse sessions when the
next work is genuinely related and cached context remains useful/clean; start
fresh when work is unrelated, context is bloated/stale, contamination risk
exists, or independent review is required.

Optimize for USEFUL RELEVANT CACHED CONTEXT, not maximum session age.

Design guarantees:
  * EXPLICIT DECISION. reuse_session() returns a structured decision with
    reasons -- never a silent default.
  * INDEPENDENCE FIRST. independent review ALWAYS forces fresh context
    (review independence is non-negotiable; a session containing the
    implementer's working context is never reused for the review of that
    work).
  * CLEANLINESS. context_ok (clean/useful) is a required input; stale or
    bloated context forces fresh.
  * NO CONTAMINATION. contamination_risk forces fresh.
  * FAIL OPEN ON TELEMETRY. Pure decision logic, no I/O, no spend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REUSE = "reuse"
FRESH = "fresh"


@dataclass
class SessionDecision:
    """Structured session reuse decision."""

    decision: str                    # REUSE | FRESH
    reasons: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def should_reuse(self) -> bool:
        return self.decision == REUSE


def reuse_session(
    *,
    related: bool,
    cached_context_useful: bool,
    context_clean: bool,
    independence_required: bool = False,
    contamination_risk: bool = False,
    compact_fresh_more_efficient: bool = False,
) -> SessionDecision:
    """Decide whether to reuse a worker session or start fresh.

    Mission rules:
      REUSE when: next work genuinely related AND cached context remains
        useful AND context remains clean AND reuse avoids unnecessary cache
        reconstruction AND independence is not required.
      FRESH when: work unrelated OR context bloated/stale OR contamination
        risk OR independent review required OR a compact fresh brief is more
        efficient.

    Independence_required dominates: an independent review NEVER reuses the
    session containing the work under review.
    """
    reasons: list[str] = []

    if independence_required:
        reasons.append("independent review required -- review independence "
                       "never reuses the implementer's working context")
        return SessionDecision(FRESH, reasons)

    if contamination_risk:
        reasons.append("contamination risk -- fresh context required")
        return SessionDecision(FRESH, reasons)

    if compact_fresh_more_efficient:
        reasons.append("a compact fresh brief is more efficient than the "
                       "existing cached context")
        return SessionDecision(FRESH, reasons)

    if not related:
        reasons.append("next work is unrelated to the session's cached context")
        return SessionDecision(FRESH, reasons)

    if not cached_context_useful:
        reasons.append("cached context is no longer useful for the next work")
        return SessionDecision(FRESH, reasons)

    if not context_clean:
        reasons.append("cached context is bloated or stale -- fresh context "
                       "required")
        return SessionDecision(FRESH, reasons)

    reasons.append("related work + useful clean cached context -- reuse "
                   "avoids unnecessary cache reconstruction")
    return SessionDecision(REUSE, reasons)


def telemetry_fresh_reused(decision: SessionDecision) -> str | None:
    """Map a decision to the telemetry value: 'fresh' | 'reused' | None.

    None when the decision is unavailable (fail open on telemetry -- dispatch
    must never break because session telemetry is missing).
    """
    if decision is None:
        return None
    return "reused" if decision.should_reuse else "fresh"


__all__ = [
    "reuse_session",
    "SessionDecision",
    "telemetry_fresh_reused",
    "REUSE",
    "FRESH",
]
