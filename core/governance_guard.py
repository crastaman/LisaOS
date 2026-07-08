"""LisaOS Governance Guard (post-closure hardening patch).

Detects delegated work that executed OUTSIDE the governed LisaOS path
(core/dispatcher.py -> core/workforce_resolver.py) -- most concretely, a
Claude Code native subagent spawned directly. A raw subagent spawn has no
capability match, no fail-closed model resolution, no employee-affinity
enforcement, and produces no workforce_evidence.jsonl record, because it
never calls into WorkforceResolver.resolve() at all.

This module cannot PREVENT a native subagent spawn -- that mechanism lives
in the Claude Code harness, outside this repo's process boundary and outside
Lisa's control. What it CAN do, and does:

  * scan Claude Code's own per-project subagent transcripts for invocations
    that look like delegated production work (name matches a
    production-shaped prefix -- see PRODUCTION_NAME_PREFIXES);
  * cross-reference them against real governed evidence
    (reports/lisa/workforce_evidence.jsonl);
  * record anything unmatched as a GovernanceViolation
    (reports/lisa/governance_violations.jsonl);
  * fail closed -- require_clean() raises GovernanceGuardError -- until an
    explicit, attributed operator acknowledgement
    (reports/lisa/governance_acknowledgements.jsonl) covers every open
    violation.

LIMITATION (stated plainly, not hidden): the production-name-prefix match is
a best-effort heuristic, not a proof. A subagent named outside
PRODUCTION_NAME_PREFIXES evades detection. This closes the gap "as far as
currently possible" from within Lisa's own process -- it does not make
bypass structurally impossible. See
docs/LISAOS/V3/33_WORKFORCE_GOVERNANCE_HARDENING.md.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
CLAUDE_PROJECTS_ROOT = Path(
    os.environ.get("CLAUDE_PROJECTS_ROOT", Path.home() / ".claude" / "projects")
)
WORKFORCE_EVIDENCE_LOG = LISA_BASE / "reports" / "lisa" / "workforce_evidence.jsonl"
VIOLATIONS_LOG = LISA_BASE / "reports" / "lisa" / "governance_violations.jsonl"
ACKNOWLEDGEMENTS_LOG = LISA_BASE / "reports" / "lisa" / "governance_acknowledgements.jsonl"

# Subagent names that LOOK like delegated production/implementation work, as
# opposed to read-only research/exploration (which never needs
# WorkforceResolver staffing and is out of scope for this guard).
PRODUCTION_NAME_PREFIXES: tuple[str, ...] = ("impl-", "build-", "fix-", "upgrade-")


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

@dataclass
class SubagentInvocation:
    """One Claude Code subagent transcript found under a project directory."""

    name: str
    session_id: str
    project_dir: str
    transcript_path: str


@dataclass
class GovernanceViolation:
    """A production-shaped subagent invocation with no governed evidence."""

    violation_id: str
    subagent_name: str
    session_id: str
    transcript_path: str
    reason: str
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


class GovernanceGuardError(Exception):
    """Raised when unacknowledged governance violations block a governed run."""


def violation_id(subagent_name: str, transcript_path: str) -> str:
    return hashlib.sha256(f"{subagent_name}:{transcript_path}".encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Scanning (read-only; never mutates harness state)
# --------------------------------------------------------------------------- #

def find_subagent_invocations(project_dirs: Iterable[Path]) -> list[SubagentInvocation]:
    """Enumerate Claude Code subagent transcripts under the given project dirs.

    Each `<project-dir>/<session-id>/subagents/<name>...` file is one spawned
    subagent. Read-only.
    """
    out: list[SubagentInvocation] = []
    for project_dir in project_dirs:
        project_dir = Path(project_dir)
        if not project_dir.is_dir():
            continue
        for subagents_dir in sorted(project_dir.glob("*/subagents")):
            session_id = subagents_dir.parent.name
            for f in sorted(subagents_dir.iterdir()):
                if not f.is_file():
                    continue
                out.append(SubagentInvocation(
                    name=f.stem,
                    session_id=session_id,
                    project_dir=str(project_dir),
                    transcript_path=str(f),
                ))
    return out


def _looks_like_production(name: str) -> bool:
    lname = name.lower()
    return any(lname.startswith(p) for p in PRODUCTION_NAME_PREFIXES)


def _governed_identifiers(evidence_path: Path) -> set[str]:
    """Every work_package_id / employee id ever recorded as governed evidence."""
    ids: set[str] = set()
    if not evidence_path.is_file():
        return ids
    for line in evidence_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("work_package_id"):
            ids.add(str(rec["work_package_id"]).lower())
        if rec.get("employee"):
            ids.add(str(rec["employee"]).lower())
    return ids


def detect_bypass_violations(
    invocations: Iterable[SubagentInvocation],
    *,
    evidence_path: Path | None = None,
) -> list[GovernanceViolation]:
    """Production-shaped subagent invocations with no matching governed evidence."""
    governed = _governed_identifiers(evidence_path or WORKFORCE_EVIDENCE_LOG)
    violations: list[GovernanceViolation] = []
    for inv in invocations:
        if not _looks_like_production(inv.name):
            continue
        if inv.name.lower() in governed:
            continue
        violations.append(GovernanceViolation(
            violation_id=violation_id(inv.name, inv.transcript_path),
            subagent_name=inv.name,
            session_id=inv.session_id,
            transcript_path=inv.transcript_path,
            reason=(f"subagent {inv.name!r} looks like delegated production work "
                    f"but has no corresponding core.workforce_resolver evidence "
                    f"record -- it did not go through the LisaOS dispatcher"),
        ))
    return violations


# --------------------------------------------------------------------------- #
# Persistence: violations + acknowledgements
# --------------------------------------------------------------------------- #

def record_violations(
    violations: Iterable[GovernanceViolation], *, path: Path | None = None,
) -> Path:
    target = path or VIOLATIONS_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        for v in violations:
            fh.write(json.dumps(v.to_dict()) + "\n")
    return target


def _acknowledged_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        for vid in rec.get("violation_ids", []):
            ids.add(vid)
    return ids


def record_acknowledgement(
    violation_ids: Iterable[str], *, operator: str, reason: str, path: Path | None = None,
) -> Path:
    """Append an explicit, attributed acknowledgement covering the given violations.

    This does NOT retroactively make the bypassed work governed -- it records
    that a named human operator has reviewed and accepted the deviation, per
    the "operator acknowledgement required before continuing" invariant.
    """
    if not operator:
        raise ValueError("record_acknowledgement requires a non-empty operator")
    target = path or ACKNOWLEDGEMENTS_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "violation_ids": list(violation_ids),
        "operator": operator,
        "reason": reason,
        "acknowledged_at": datetime.now(timezone.utc).isoformat(),
    }
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return target


def unacknowledged(
    violations: Iterable[GovernanceViolation], *, ack_path: Path | None = None,
) -> list[GovernanceViolation]:
    acked = _acknowledged_ids(ack_path or ACKNOWLEDGEMENTS_LOG)
    return [v for v in violations if v.violation_id not in acked]


# --------------------------------------------------------------------------- #
# Fail-closed entry point
# --------------------------------------------------------------------------- #

def require_clean(
    project_dirs: Iterable[Path],
    *,
    evidence_path: Path | None = None,
    ack_path: Path | None = None,
    violations_path: Path | None = None,
) -> list[GovernanceViolation]:
    """Scan, record, and fail closed if any violation is unacknowledged.

    Call this before a governed sprint starts. Returns the (possibly empty)
    list of all detected violations on success; raises GovernanceGuardError
    -- never silently continues -- if any remain unacknowledged.
    """
    invocations = find_subagent_invocations(project_dirs)
    violations = detect_bypass_violations(invocations, evidence_path=evidence_path)
    if violations:
        record_violations(violations, path=violations_path)
    pending = unacknowledged(violations, ack_path=ack_path)
    if pending:
        names = ", ".join(f"{v.subagent_name!r} ({v.violation_id})" for v in pending)
        raise GovernanceGuardError(
            f"{len(pending)} unacknowledged governance violation(s): {names}. "
            f"Run `bin/lisa-governance-check acknowledge <id> <operator> <reason>` "
            f"before continuing."
        )
    return violations
