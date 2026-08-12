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


# --------------------------------------------------------------------------- #
# Claude Session Lifecycle Policy v1 (2026-08-11)
#
# Evidence basis:
#   WBS048 reports/s048-framework/evidence/CLAUDE-CONTEXT-BLOAT-AUDIT-2026-08-11.md
#
# Invariant: ONE ATOMIC TASK FAMILY = ONE CLAUDE SESSION.
#
# A task family is one atomic task + its continuation/rework/verification
# rounds. Different atomic tasks (even adjacent IDs) are DIFFERENT families
# and require a fresh session. Implementation and independent review never
# share a session. Sprint/workstream, worker identity, provider/model and
# review family are hard boundaries.
#
# Session identity (compact deterministic key):
#   project / sprint / employee / role / atomic_task_family
# e.g. "wbs/wbs048/sonnet/implementation/p4-b-01"
# --------------------------------------------------------------------------- #

# Context classification thresholds (operational, evidence-based; not
# mathematical absolutes -- task-family boundaries are authoritative).
CTX_HEALTHY = "HEALTHY"
CTX_WARNING = "WARNING"
CTX_RESET = "RESET_REQUIRED"

CTX_HEALTHY_MAX = 80_000          # < 80k  -> HEALTHY
CTX_WARNING_MAX = 100_000         # 80-100k -> WARNING
CTX_PREFER_FRESH = 120_000        # 100-120k -> prefer fresh; compact only if
                                  # same-family continuity genuinely matters
                                  # > 120k -> RESET_REQUIRED before new work

# Large tool-result externalization target (chars/bytes ~ tokens).
TOOL_RESULT_INLINE_MAX = 20_000   # normal retained tool result <= ~20k
TOOL_RESULT_EXTERNALIZE_MIN = 30_000  # > ~30k: externalize/truncate

# --------------------------------------------------------------------------- #
# MANDATORY WORKDIR invariant (Session Policy v1 operational finding, 2026-08-11)
#
# Fresh worker sessions may start in worker scaffolding rather than the target
# repository (observed: fresh Opus sessions land in
# ~/.openclaw/workspace-lisa-claude-opus, an EMPTY scaffolding dir). Warm-session
# memory must never be relied on to locate the repository. Every
# implementation/review brief MUST carry an explicit authoritative repository/
# workdir. Before worker execution, verify expected repository == actual target
# repository. If the repository/workdir is absent or invalid: FAIL CLOSED with
# WORKDIR_MISSING / WORKDIR_MISMATCH -- do not execute.
# --------------------------------------------------------------------------- #

WORKDIR_OK = "OK"
WORKDIR_MISSING = "WORKDIR_MISSING"
WORKDIR_MISMATCH = "WORKDIR_MISMATCH"


@dataclass
class WorkdirCheck:
    """Fail-closed repository/workdir validation for a dispatch.

    expected: the authoritative repository/workdir the brief declares (from the
              dispatch identity tuple).
    actual:   the repository/workdir the worker would execute in (its runtime
              working directory, resolved BEFORE execution).

    result:   OK | WORKDIR_MISSING | WORKDIR_MISMATCH. MISSING when the brief
              carries no authoritative repository (brief defect -- do not
              execute); MISMATCH when expected != actual (worker would operate
              in the wrong tree -- do not execute). Fail closed in both cases.
    """

    expected: str | None
    actual: str | None
    result: str = WORKDIR_MISSING
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.result == WORKDIR_OK

    def __post_init__(self):
        if not self.expected or not str(self.expected).strip():
            self.result = WORKDIR_MISSING
            self.detail = "brief carries no authoritative repository/workdir -- FAIL CLOSED (WORKDIR_MISSING)"
            return
        if not self.actual or not str(self.actual).strip():
            self.result = WORKDIR_MISMATCH
            self.detail = f"worker runtime workdir is empty/unresolved; expected {self.expected!r} -- FAIL CLOSED (WORKDIR_MISMATCH)"
            return
        # Normalize: strip trailing slashes for a tolerant comparison; do not
        # require identical string forms for equivalent paths.
        norm = lambda p: str(p).strip().rstrip("/") or str(p).strip()
        if norm(self.expected) == norm(self.actual):
            self.result = WORKDIR_OK
            self.detail = f"workdir verified: {self.actual}"
        else:
            self.result = WORKDIR_MISMATCH
            self.detail = (
                f"expected workdir {self.expected!r} != actual workdir "
                f"{self.actual!r} -- FAIL CLOSED (WORKDIR_MISMATCH)"
            )


def check_workdir(expected: str | None, actual: str | None) -> WorkdirCheck:
    """Validate the mandatory workdir invariant. Pure and fail-closed."""
    return WorkdirCheck(expected=expected, actual=actual)


# Repository/workdir is part of the dispatch identity tuple (Session Policy v1
# operational finding). When present, the brief must declare it and the bridge
# must verify expected == actual before execution.
WORKDIR_FIELD = "repository"


@dataclass
class SessionKey:
    """Compact deterministic session identity.

    Unrelated work cannot silently inherit a previous Claude session because
    the session key embeds the full identity: project + sprint + employee +
    role + atomic task family. None fields (unavailable identity) resolve to
    "unknown" -- deterministic, never raises, fail-safe toward isolation.
    """

    project: str
    sprint: str
    employee: str
    role: str
    task_family: str

    @property
    def key(self) -> str:
        parts = [
            (self.project or "unknown").strip().lower().replace("/", "-"),
            (self.sprint or "unknown").strip().lower().replace("/", "-"),
            (self.employee or "unknown").strip().lower().replace("/", "-"),
            (self.role or "unknown").strip().lower().replace("/", "-"),
            (self.task_family or "unknown").strip().lower().replace("/", "-"),
        ]
        return "/".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "sprint": self.sprint,
            "employee": self.employee,
            "role": self.role,
            "task_family": self.task_family,
        }


_ROLE_IMPLEMENTATION = "implementation"
_ROLE_REVIEW = "review"


def role_implementation() -> str:
    return _ROLE_IMPLEMENTATION


def role_review() -> str:
    return _ROLE_REVIEW


def is_review_role(role: str | None) -> bool:
    return (role or "").strip().lower() == _ROLE_REVIEW


def session_key_for(
    *,
    project: str | None = None,
    sprint: str | None = None,
    employee: str | None = None,
    role: str | None = None,
    task_family: str | None = None,
) -> str:
    """Build the deterministic session key for an identity tuple.

    Pure and fail-safe: unknown fields resolve to "unknown". Callers use this
    to derive Claude session identity BEFORE dispatch; unrelated work can
    never silently inherit a previous session because any identity-component
    difference produces a different key.

    NOTE: the repository/workdir is deliberately NOT part of the session key
    -- a session is scoped to project/sprint/employee/role/task_family, and
    workdir correctness is enforced separately and fail-closed by
    check_workdir() BEFORE execution (WORKDIR_MISSING / WORKDIR_MISMATCH).
    """
    return SessionKey(
        project=project or "unknown",
        sprint=sprint or "unknown",
        employee=employee or "unknown",
        role=role or "unknown",
        task_family=task_family or "unknown",
    ).key


def context_state(active_context: int | None, *, context_window: int = 200_000,
                  warning_threshold_pct: float | None = None,
                  reset_threshold_pct: float | None = None) -> str:
    """Classify active Claude session context.

    HEALTHY below configured window-relative warning percentage; WARNING
    from warning percentage to the reset percentage; RESET_REQUIRED at the
    configured hard cap. Task-family boundaries are authoritative: a small
    session from the wrong task family must NOT be reused merely because it
    is below threshold (enforced by the key, not by this classifier).

    None telemetry (unknown context) -> WARNING: fail toward session
    isolation rather than indefinite reuse.
    """
    if active_context is None:
        return CTX_WARNING
    if warning_threshold_pct is None or reset_threshold_pct is None:
        from core.reliability_config import load_reliability_config
        config = load_reliability_config()
        warning_threshold_pct = config.session_threshold("warning_threshold_pct", 0.80)
        reset_threshold_pct = config.session_threshold("reset_threshold_pct", 1.0)
    pct = active_context / context_window if context_window > 0 else 1.0
    if pct < warning_threshold_pct:
        return CTX_HEALTHY
    return CTX_RESET if pct >= reset_threshold_pct else CTX_WARNING


def decide_session(
    *,
    active_context: int | None = None,
    context_window: int = 200_000,
    task_family_same: bool = True,
    worker_same: bool = True,
    sprint_same: bool = True,
    role_switch: bool = False,
    review_family_same: bool = True,
    session_limit_failure: bool = False,
    provenance_untrusted: bool = False,
    contamination_risk: bool = False,
) -> SessionDecision:
    """Session Lifecycle v1 decision: REUSE or FRESH.

    Hard boundaries (always FRESH, regardless of token count):
      * different task family
      * different worker
      * different sprint
      * implementation <-> independent review role switch
      * different review family
      * session-limit failure invalidates reuse
      * untrusted recovery provenance
      * contamination risk

    Context thresholds (FRESH when RESET_REQUIRED; WARNING prefers fresh;
    HEALTHY permits reuse only when all boundaries pass).
    """
    if session_limit_failure:
        return SessionDecision(
            FRESH, ["session-limit failure -- session invalidated for reuse"])
    if provenance_untrusted:
        return SessionDecision(
            FRESH, ["recovered session provenance cannot be trusted -- fail safe to fresh"])
    if contamination_risk:
        return SessionDecision(
            FRESH, ["contamination risk -- fresh context required"])
    if not sprint_same:
        return SessionDecision(
            FRESH, ["sprint/workstream changed -- fresh session required"])
    if not worker_same:
        return SessionDecision(
            FRESH, ["worker identity changed -- fresh session required"])
    if role_switch:
        return SessionDecision(
            FRESH, ["implementation <-> independent review switch -- fresh session required"])
    if not task_family_same:
        return SessionDecision(
            FRESH, ["atomic task family changed -- fresh session required"])
    if not review_family_same:
        return SessionDecision(
            FRESH, ["review family changed -- fresh session required"])

    state = context_state(active_context, context_window=context_window)
    if state == CTX_RESET:
        return SessionDecision(
            FRESH, ["context RESET_REQUIRED (>120k) -- do not start new work in this session"])
    if state == CTX_WARNING:
        return SessionDecision(
            FRESH, ["context WARNING (80-120k) -- prefer fresh session for new work"])
    return SessionDecision(
        REUSE, ["same task family + healthy context -- reuse is safe"])


def telemetry_session_fresh_reused(decision: SessionDecision | None) -> str | None:
    """Map a Session Lifecycle v1 decision to telemetry."""
    return telemetry_fresh_reused(decision)


__all__ = [
    "reuse_session",
    "SessionDecision",
    "telemetry_fresh_reused",
    "REUSE",
    "FRESH",
    # --- Session Lifecycle Policy v1 ---
    "SessionKey",
    "session_key_for",
    "context_state",
    "decide_session",
    "role_implementation",
    "role_review",
    "is_review_role",
    "CTX_HEALTHY",
    "CTX_WARNING",
    "CTX_RESET",
    "CTX_HEALTHY_MAX",
    "CTX_WARNING_MAX",
    "CTX_PREFER_FRESH",
    "TOOL_RESULT_INLINE_MAX",
    "TOOL_RESULT_EXTERNALIZE_MIN",
    "telemetry_session_fresh_reused",
    # --- MANDATORY WORKDIR invariant ---
    "WorkdirCheck",
    "check_workdir",
    "WORKDIR_OK",
    "WORKDIR_MISSING",
    "WORKDIR_MISMATCH",
    "WORKDIR_FIELD",
]
