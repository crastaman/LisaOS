"""Four-dimension lifecycle state model + EXECUTION_UNKNOWN (RC003 Wave 1, A1).

This module makes the critical reliability invariant *representable*:

    I1: absence of proof of execution failure must never be treated as proof
        that execution stopped.

Before A1 the system had a single collapsed `status` and a binary
success/failure split, so a transport-ambiguous outcome (600s CLI timeout
after the remote worker started, a lost acknowledgement, a connection closed
mid-run) was recorded as `failed`/`timed_out` — a false claim that execution
stopped. A1 introduces four orthogonal lifecycle dimensions and, critically,
EXECUTION_UNKNOWN: the honest state for "we do not have authoritative proof of
the execution outcome."

Dimensions (RC003 §3 / §9.1):
    DISPATCH   : NOT_SENT -> SENDING -> ACKNOWLEDGED | REJECTED | DISPATCH_UNKNOWN
    EXECUTION  : NOT_STARTED -> RUNNING -> COMPLETED | FAILED | EXECUTION_UNKNOWN
    SESSION    : HEALTHY | CONTEXT_PRESSURE | COMPACTION_REQUIRED | COMPACTING |
                 ACTIVE | EXHAUSTED | THROTTLED | UNAVAILABLE | SESSION_UNKNOWN
    RESULT     : PENDING -> RECEIVED -> INGESTED | DELIVERY_FAILED | RESULT_UNKNOWN
    COMMAND    : OK | FAILED | TIMED_OUT   (cron/CLI outcome — never a worker outcome)

Authority rules (RC003 §3, made binding):
    COMPLETED         requires a worker terminal signal + a result artifact
                      (NOT subprocess exit alone).
    FAILED            requires authoritative termination (worker-reported
                      failure, OR verified process death with no remote
                      continuation).
    EXECUTION_UNKNOWN is the DEFAULT after any dispatch/transport error without
                      authoritative termination. Redispatch from UNKNOWN is
                      forbidden without reconciliation (enforced in
                      core/reconciliation.py).

This module is pure: enums, transition/authority tables, small dataclasses,
and classification helpers. No I/O, no dispatch, no LLM. Safe to unit-test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# --------------------------------------------------------------------------- #
# DISPATCH dimension
# --------------------------------------------------------------------------- #
DISPATCH_NOT_SENT = "NOT_SENT"
DISPATCH_SENDING = "SENDING"
DISPATCH_ACKNOWLEDGED = "ACKNOWLEDGED"
DISPATCH_REJECTED = "REJECTED"
DISPATCH_UNKNOWN = "DISPATCH_UNKNOWN"
DISPATCH_STATES = frozenset({
    DISPATCH_NOT_SENT, DISPATCH_SENDING, DISPATCH_ACKNOWLEDGED,
    DISPATCH_REJECTED, DISPATCH_UNKNOWN,
})

# --------------------------------------------------------------------------- #
# EXECUTION dimension
# --------------------------------------------------------------------------- #
EXEC_NOT_STARTED = "NOT_STARTED"
EXEC_RUNNING = "RUNNING"
EXEC_COMPLETED = "COMPLETED"
EXEC_FAILED = "FAILED"
EXEC_UNKNOWN = "EXECUTION_UNKNOWN"
EXECUTION_STATES = frozenset({
    EXEC_NOT_STARTED, EXEC_RUNNING, EXEC_COMPLETED, EXEC_FAILED, EXEC_UNKNOWN,
})
# Terminal FOR SCHEDULING purposes. EXECUTION_UNKNOWN is deliberately NOT here:
# it is a hold-for-reconciliation state, never a schedulable-or-done terminal.
EXECUTION_TERMINAL = frozenset({EXEC_COMPLETED, EXEC_FAILED})

# --------------------------------------------------------------------------- #
# SESSION dimension (values defined now; wiring is Wave 3 / D1)
# --------------------------------------------------------------------------- #
SESSION_HEALTHY = "HEALTHY"
SESSION_CONTEXT_PRESSURE = "CONTEXT_PRESSURE"
SESSION_COMPACTION_REQUIRED = "COMPACTION_REQUIRED"
SESSION_COMPACTING = "COMPACTING"
SESSION_ACTIVE = "ACTIVE"
SESSION_EXHAUSTED = "EXHAUSTED"
SESSION_THROTTLED = "THROTTLED"
SESSION_UNAVAILABLE = "UNAVAILABLE"
SESSION_UNKNOWN = "SESSION_UNKNOWN"
SESSION_STATES = frozenset({
    SESSION_HEALTHY, SESSION_CONTEXT_PRESSURE, SESSION_COMPACTION_REQUIRED,
    SESSION_COMPACTING, SESSION_ACTIVE, SESSION_EXHAUSTED, SESSION_THROTTLED,
    SESSION_UNAVAILABLE, SESSION_UNKNOWN,
})

# --------------------------------------------------------------------------- #
# RESULT dimension
# --------------------------------------------------------------------------- #
RESULT_PENDING = "PENDING"
RESULT_RECEIVED = "RECEIVED"
RESULT_INGESTED = "INGESTED"
RESULT_DELIVERY_FAILED = "DELIVERY_FAILED"
RESULT_UNKNOWN = "RESULT_UNKNOWN"
RESULT_STATES = frozenset({
    RESULT_PENDING, RESULT_RECEIVED, RESULT_INGESTED,
    RESULT_DELIVERY_FAILED, RESULT_UNKNOWN,
})

# --------------------------------------------------------------------------- #
# COMMAND dimension (cron/CLI subprocess outcome — NEVER a worker outcome)
# --------------------------------------------------------------------------- #
COMMAND_OK = "OK"
COMMAND_FAILED = "FAILED"
COMMAND_TIMED_OUT = "TIMED_OUT"
COMMAND_STATES = frozenset({COMMAND_OK, COMMAND_FAILED, COMMAND_TIMED_OUT})


# --------------------------------------------------------------------------- #
# Bridge evidence-source -> EXECUTION state classification.
#
# The single source of truth shared by core/openclaw_bridge.py (which tags its
# ExecutionResults) and the adversarial tests. Every entry encodes the RC003
# §4.1 authority rule: only pre-dispatch, never-spawned faults are FAILED; any
# fault after the subprocess was invoked (worker may have started remotely) is
# EXECUTION_UNKNOWN.
# --------------------------------------------------------------------------- #

# Pre-dispatch fail-closed: nothing was ever spawned, so there is authoritative
# proof that execution did NOT start. These are genuine command/dispatch
# failures (FAILED), not ambiguity.
PRE_DISPATCH_FAILURE_SOURCES = frozenset({
    "fail-closed-no-resolution",
    "fail-closed-gateway-unreachable",
    "fail-closed-agent-enumeration-error",
    "fail-closed-no-identity-agent",
    "fail-closed-identity-agent-unavailable",
    "fail-closed-workdir_missing",
    "fail-closed-workdir_mismatch",
})

# Post-invocation ambiguity: the CLI subprocess was invoked, so a remote worker
# may have started. Absence of an authoritative terminal signal => UNKNOWN.
POST_INVOCATION_UNKNOWN_SOURCES = frozenset({
    "fail-closed-subprocess-error",     # OSError / TimeoutExpired after invoke
    "real-execution-failed",            # CLI exit != 0 WITHOUT a worker-error payload
    "fail-closed-bad-json-response",    # response lost; run may have started
    "fail-closed-executor-exception",   # bridge outer wrapper caught a post-spawn fault
    "fail-closed-gateway-after-submission",
})


def classify_execution_source(evidence_source: Optional[str]) -> Optional[str]:
    """Map a bridge evidence-source string to an EXECUTION state.

    Returns EXEC_UNKNOWN for post-invocation ambiguity, EXEC_FAILED for
    pre-dispatch failures, and None when the source does not itself determine
    the execution state (e.g. success/completed paths, or hermetic/simulated
    executors) — the caller then derives from `success`.
    """
    if not evidence_source:
        return None
    if evidence_source in POST_INVOCATION_UNKNOWN_SOURCES:
        return EXEC_UNKNOWN
    if evidence_source in PRE_DISPATCH_FAILURE_SOURCES:
        return EXEC_FAILED
    return None


def derive_execution_state(success: bool) -> str:
    """Fallback classification when no explicit execution_state was supplied.

    Preserves the legacy binary contract for hermetic/simulated executors and
    for internal contract violations (malformed results): success -> COMPLETED,
    otherwise FAILED. NEVER yields EXECUTION_UNKNOWN — UNKNOWN is only ever set
    explicitly by a component that observed genuine transport ambiguity.
    """
    return EXEC_COMPLETED if success else EXEC_FAILED


def resolve_execution_state(explicit: Optional[str], success: bool) -> str:
    """Authoritative resolution used by the dispatcher merge.

    An explicit EXECUTION state (set by the real bridge) wins; otherwise derive
    from `success`. This is what keeps the change backward compatible: hermetic
    executors set no explicit state and keep their exact completed/failed
    semantics, while the real bridge can raise EXECUTION_UNKNOWN.
    """
    if explicit in EXECUTION_STATES:
        return explicit  # type: ignore[return-value]
    return derive_execution_state(success)


def requires_reconciliation(execution_state: Optional[str]) -> bool:
    """True iff the execution state is EXECUTION_UNKNOWN (reconcile before any
    redispatch). This is the single predicate the gate and the watcher use."""
    return execution_state == EXEC_UNKNOWN


# --------------------------------------------------------------------------- #
# Legacy status derivation (RC003 §9.1 back-compat rule).
# The 4-dimension columns are authoritative; `status` remains for legacy
# consumers and is derived from the dominant execution dimension.
# --------------------------------------------------------------------------- #
LEGACY_STATUS_COMPLETED = "completed"
LEGACY_STATUS_FAILED = "failed"
LEGACY_STATUS_EXECUTION_UNKNOWN = "execution_unknown"


def derive_legacy_status(execution_state: str) -> str:
    if execution_state == EXEC_COMPLETED:
        return LEGACY_STATUS_COMPLETED
    if execution_state == EXEC_UNKNOWN:
        return LEGACY_STATUS_EXECUTION_UNKNOWN
    return LEGACY_STATUS_FAILED


# --------------------------------------------------------------------------- #
# Terminal evidence record (RC003 §9.1 `terminal_evidence` column, C1 fills it)
# --------------------------------------------------------------------------- #

@dataclass
class TerminalEvidence:
    """The proof (or absence of proof) behind an EXECUTION terminal decision.

    * signal          -- worker terminal signal (CLI status + task_runs status)
    * artifact        -- result artifact presence/reference, or None
    * verified_death  -- True only when process death + no-remote-continuation
                         was positively verified (authoritative FAILED)
    * reconciliation  -- reconciliation decision record, once the gate has run
    """
    signal: Optional[dict[str, Any]] = None
    artifact: Optional[dict[str, Any]] = None
    verified_death: bool = False
    reconciliation: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "artifact": self.artifact,
            "verified_death": self.verified_death,
            "reconciliation": self.reconciliation,
        }


# --------------------------------------------------------------------------- #
# Bundled lifecycle state (all four dimensions + reconciliation flag)
# --------------------------------------------------------------------------- #

@dataclass
class LifecycleState:
    """A snapshot of all four lifecycle dimensions for one task run."""
    dispatch_state: str = DISPATCH_NOT_SENT
    execution_state: str = EXEC_NOT_STARTED
    session_state: str = SESSION_UNKNOWN
    result_state: str = RESULT_PENDING
    command_state: Optional[str] = None
    requires_reconciliation: bool = False
    terminal_evidence: Optional[TerminalEvidence] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_state": self.dispatch_state,
            "execution_state": self.execution_state,
            "session_state": self.session_state,
            "result_state": self.result_state,
            "command_state": self.command_state,
            "requires_reconciliation": self.requires_reconciliation,
            "terminal_evidence": (
                self.terminal_evidence.to_dict() if self.terminal_evidence else None
            ),
        }
