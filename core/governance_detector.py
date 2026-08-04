"""LisaOS governance detection backstop (Phase 6 -- LISA-I008).

Phases 1-5 built an authoritative governed path. This module closes the last
structural gap: LisaOS could execute governed work correctly, but could not
SEE governed work that bypassed it. That blindness is what let S046 fail
silently -- a full production-readiness audit ran inside a chat session with
zero LisaOS evidence, and nothing noticed.

THE PRINCIPLE
-------------
Governed work must always produce evidence. Governed-shaped activity with no
corresponding LisaOS evidence is a governance violation.

WHAT IT DOES, AND DOES NOT DO
-----------------------------
It DETECTS and BLOCKS. It does not orchestrate, re-route, repair or decide how
work should proceed -- those are operator decisions, and automating them here
would recreate the very ungoverned authority this module exists to expose.

HOW DETECTION WORKS
-------------------
  observed activity   OpenClaw `task_runs` (read-only), the same ground truth
                      core/openclaw_bridge.py already reconciles against.
  governed shape      core/task_classifier.py -- the SAME deterministic rules
                      that route work at intake. No language model is involved,
                      and a rule that governs at the front door governs at the
                      backstop, by construction.
  correlation         run_id present in workforce evidence or the work-product
                      index. Present => governed and evidenced. Absent => the
                      work happened outside LisaOS.

THE DETECTION ASYMMETRY (the key false-positive control)
--------------------------------------------------------
Intake and detection fail in OPPOSITE directions, deliberately:

  * At intake, ambiguity resolves to GOVERNED. The cost of being wrong is
    merely that safe work gets governed.
  * At detection, ambiguity resolves to NO VIOLATION. The cost of being wrong
    is that real engineering is blocked and an operator is accused of a bypass.

So detection requires a POSITIVE governed signal -- at least one explicit G
rule -- and never fires on `DEFAULT_GOVERNED_AMBIGUOUS`. Conversation,
architectural discussion, explanation, status questions and read-only research
do not match a G rule and are therefore never flagged.

DETERMINISM
-----------
Violation ids are derived from the observed run id, and every timestamp comes
from the observed activity rather than the wall clock. Scanning the same
evidence twice produces byte-identical violations and reports -- the same
discipline as the Phase 5 synthesizer, for the same reason: a report that
changes when nothing changed cannot be trusted or diffed.

ACKNOWLEDGEMENT
---------------
The acknowledgement ledger of `core/governance_guard.py` is REUSED, not
duplicated. That module detects a different bypass surface (Claude Code
subagent transcripts); both write to one ledger, so an operator has a single
place to review and accept deviations.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from core.governance_guard import (
    ACKNOWLEDGEMENTS_LOG, _acknowledged_ids, record_acknowledgement,
)
from core.synthesizer import (
    LABEL_MISSING, LABEL_OBSERVED, statement,
)
from core.task_classifier import classify

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

DETECTOR_SCHEMA_VERSION = "lisa-governance-violation/1"
REPORT_SCHEMA_VERSION = "lisa-governance-report/1"

LISA_BASE = Path(__file__).resolve().parent.parent
ORCHESTRATION_DIR = LISA_BASE / "reports" / "lisa" / "orchestration"
WORKFORCE_EVIDENCE = LISA_BASE / "reports" / "lisa" / "workforce_evidence.jsonl"
WORK_PRODUCT_INDEX = ORCHESTRATION_DIR / "work_products" / "index.jsonl"
DETECTOR_VIOLATIONS_LOG = ORCHESTRATION_DIR / "governance" / "violations.jsonl"

DEFAULT_OPENCLAW_DB = Path.home() / ".openclaw" / "state" / "openclaw.sqlite"

# Runtimes examined by default. `cron` is excluded: scheduled operational jobs
# are not governed engineering, and sweeping them in would generate exactly the
# recurring false positives that teach operators to ignore the detector.
DEFAULT_RUNTIMES = ("cli", "tui")

SEVERITY_CRITICAL = "critical"  # matched a change-making rule (G1/G2)
SEVERITY_WARNING = "warning"    # governed-shaped, but no change-making signal

# Rules that indicate work which MAKES changes, rather than merely reviewing.
_CHANGE_MAKING_RULES = ("G1_REPO_WRITE", "G2_EXECUTION_MUTATION")

# Never a positive detection signal: this is the intake safe-default, not
# evidence that the activity was governed engineering.
_AMBIGUOUS_RULE = "DEFAULT_GOVERNED_AMBIGUOUS"


class GovernanceDetectionError(Exception):
    """Unacknowledged violations block governed execution. Never silent."""

    def __init__(self, message: str, violations: list["GovernanceViolation"] | None = None):
        super().__init__(message)
        self.violations = list(violations or [])


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

@dataclass
class ObservedActivity:
    """One execution observed outside LisaOS. Purely factual."""

    run_id: str
    agent_id: str | None
    runtime: str | None
    status: str | None
    task: str
    observed_at: str
    source: str = "openclaw.task_runs"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GovernanceViolation:
    """Governed-shaped activity with no corresponding LisaOS evidence."""

    violation_id: str
    timestamp: str                      # from the OBSERVED activity, never now()
    reason: str
    governing_rule: list[str]
    observed_activity: dict[str, Any]
    missing_evidence: list[str]
    severity: str
    acknowledged: bool = False
    acknowledged_by: str | None = None
    schema_version: str = DETECTOR_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def violation_id_for(run_id: str) -> str:
    """Deterministic id: the same run always yields the same violation id, so
    re-scanning cannot produce duplicate or drifting violations."""
    return hashlib.sha256(f"openclaw-run:{run_id}".encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Observation (read-only)
# --------------------------------------------------------------------------- #

def _epoch_ms_to_iso(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return "unknown"


def load_observed_activity(
    db_path: str | Path | None = None,
    *,
    runtimes: Iterable[str] = DEFAULT_RUNTIMES,
    since_ms: int | None = None,
    limit: int = 5000,
) -> list[ObservedActivity]:
    """Read OpenClaw `task_runs`. Read-only, and never raises on an absent or
    unreadable database.

    Honest limitation, stated rather than hidden: if the observation source is
    missing, detection yields NOTHING. This is a backstop, not a substitute for
    the structural authority of the `lisa` entrypoint -- a detector that cannot
    see cannot protect, and pretending otherwise would be worse than the gap.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_OPENCLAW_DB
    if not path.is_file():
        return []
    wanted = tuple(runtimes)
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT run_id, agent_id, runtime, status, task, created_at "
                "FROM task_runs ORDER BY created_at ASC LIMIT ?", (limit,),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []

    out: list[ObservedActivity] = []
    for row in rows:
        if wanted and row["runtime"] not in wanted:
            continue
        if since_ms is not None:
            try:
                if int(row["created_at"]) < since_ms:
                    continue
            except (TypeError, ValueError):
                pass
        out.append(ObservedActivity(
            run_id=str(row["run_id"]),
            agent_id=row["agent_id"],
            runtime=row["runtime"],
            status=row["status"],
            task=row["task"] or "",
            observed_at=_epoch_ms_to_iso(row["created_at"]),
        ))
    return out


def evidence_run_ids(
    *,
    workforce_evidence: str | Path | None = None,
    work_product_index: str | Path | None = None,
) -> set[str]:
    """Every run id LisaOS has evidence for. A corrupt line never hides the rest."""
    ids: set[str] = set()
    sources = (
        (Path(workforce_evidence) if workforce_evidence is not None else WORKFORCE_EVIDENCE,
         ("execution_run_id", "run_id")),
        (Path(work_product_index) if work_product_index is not None else WORK_PRODUCT_INDEX,
         ("run_id",)),
    )
    for path, keys in sources:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            for key in keys:
                value = record.get(key)
                if value:
                    ids.add(str(value))
    return ids


# --------------------------------------------------------------------------- #
# Governed-shape detection (deterministic; no language model)
# --------------------------------------------------------------------------- #

def governed_signal(task_text: str) -> tuple[bool, list[str], str]:
    """Does this activity look like governed engineering?

    Returns (is_governed, matched_rules, reason). Reuses the intake classifier
    but applies the detection asymmetry: an explicit G rule is REQUIRED, and the
    ambiguous safe-default never counts. This is what keeps conversation,
    explanation, status questions and read-only research out of the ledger.
    """
    result = classify(task_text)
    if result.classification != "GOVERNED":
        return False, [], f"classified {result.classification}, not governed engineering"

    explicit = [r for r in result.matched_rules if r.startswith("G")]
    if not explicit:
        return False, [], (
            "only the ambiguous safe-default matched; detection requires an "
            "explicit governed signal")
    return True, explicit, f"matched governed rule(s): {', '.join(explicit)}"


def severity_for(rules: Iterable[str]) -> str:
    """critical when the work makes changes; warning when it only reviews."""
    return (SEVERITY_CRITICAL if any(r in _CHANGE_MAKING_RULES for r in rules)
            else SEVERITY_WARNING)


def detect_violations(
    activities: Iterable[ObservedActivity],
    *,
    evidence_ids: set[str] | None = None,
    acknowledged: set[str] | None = None,
) -> list[GovernanceViolation]:
    """Correlate observed activity against LisaOS evidence.

    Deterministic: same inputs, same violations, same order (evidence order).
    """
    evidence = evidence_ids if evidence_ids is not None else set()
    acked = acknowledged or set()
    violations: list[GovernanceViolation] = []

    for activity in activities:
        if activity.run_id in evidence:
            continue  # governed AND evidenced -- the happy path
        is_governed, rules, reason = governed_signal(activity.task)
        if not is_governed:
            continue  # not governed engineering -- never flagged

        missing = ["workforce_evidence", "work_product"]
        vid = violation_id_for(activity.run_id)
        violations.append(GovernanceViolation(
            violation_id=vid,
            timestamp=activity.observed_at,
            reason=(
                f"governed engineering ran on agent {activity.agent_id!r} "
                f"(run {activity.run_id}) with no LisaOS evidence: it did not "
                f"enter through the `lisa` entrypoint and was never dispatched "
                f"by the LisaOS dispatcher"),
            governing_rule=rules,
            observed_activity=activity.to_dict(),
            missing_evidence=missing,
            severity=severity_for(rules),
            acknowledged=vid in acked,
            acknowledged_by=None,
        ))
    return violations


# --------------------------------------------------------------------------- #
# Persistence (violations ledger; acknowledgements are SHARED with governance_guard)
# --------------------------------------------------------------------------- #

def record_violations(
    violations: Iterable[GovernanceViolation], *, path: str | Path | None = None,
) -> Path:
    """Append violations to the ledger. Append-only: evidence is never rewritten."""
    target = Path(path) if path is not None else DETECTOR_VIOLATIONS_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        for violation in violations:
            fh.write(json.dumps(violation.to_dict()) + "\n")
    return target


def acknowledged_ids(path: str | Path | None = None) -> set[str]:
    """Ids acknowledged in the SHARED acknowledgement ledger."""
    return _acknowledged_ids(Path(path) if path is not None else ACKNOWLEDGEMENTS_LOG)


def acknowledge(
    violation_ids: Iterable[str], *, operator: str, reason: str,
    path: str | Path | None = None,
) -> Path:
    """Record an attributed operator acknowledgement.

    This does NOT make the bypassed work governed retroactively, and does not
    create evidence for it. It records that a named human reviewed and accepted
    the deviation, which is the only thing that may unblock governed execution.
    """
    return record_acknowledgement(
        violation_ids, operator=operator, reason=reason,
        path=Path(path) if path is not None else None,
    )


def unacknowledged(
    violations: Iterable[GovernanceViolation], *, ack_path: str | Path | None = None,
) -> list[GovernanceViolation]:
    acked = acknowledged_ids(ack_path)
    return [v for v in violations if v.violation_id not in acked]


# --------------------------------------------------------------------------- #
# Scanning + fail-closed gate
# --------------------------------------------------------------------------- #

def scan(
    *,
    db_path: str | Path | None = None,
    workforce_evidence: str | Path | None = None,
    work_product_index: str | Path | None = None,
    ack_path: str | Path | None = None,
    runtimes: Iterable[str] = DEFAULT_RUNTIMES,
    since_ms: int | None = None,
) -> list[GovernanceViolation]:
    """Full detection pass. Read-only; records nothing."""
    activities = load_observed_activity(db_path, runtimes=runtimes, since_ms=since_ms)
    evidence = evidence_run_ids(
        workforce_evidence=workforce_evidence, work_product_index=work_product_index)
    return detect_violations(
        activities, evidence_ids=evidence, acknowledged=acknowledged_ids(ack_path))


def require_clean_execution(
    *,
    db_path: str | Path | None = None,
    workforce_evidence: str | Path | None = None,
    work_product_index: str | Path | None = None,
    ack_path: str | Path | None = None,
    violations_path: str | Path | None = None,
    runtimes: Iterable[str] = DEFAULT_RUNTIMES,
    record: bool = True,
) -> list[GovernanceViolation]:
    """Gate governed execution. Raises rather than continuing silently.

    Returns all detected violations when none are outstanding; raises
    GovernanceDetectionError when any remain unacknowledged.
    """
    violations = scan(
        db_path=db_path, workforce_evidence=workforce_evidence,
        work_product_index=work_product_index, ack_path=ack_path, runtimes=runtimes,
    )
    pending = [v for v in violations if not v.acknowledged]
    if violations and record:
        record_violations(violations, path=violations_path)
    if pending:
        raise GovernanceDetectionError(
            f"{len(pending)} unacknowledged governance violation(s) detected; "
            f"governed execution is blocked. Review with `bin/lisa-governance "
            f"report` and acknowledge with `bin/lisa-governance acknowledge "
            f"<id> <operator> <reason>`.",
            pending,
        )
    return violations


# --------------------------------------------------------------------------- #
# Deterministic reporting
# --------------------------------------------------------------------------- #

def build_governance_report(
    violations: Iterable[GovernanceViolation],
    *,
    scanned: int | None = None,
) -> dict[str, Any]:
    """A traceable, deterministic governance report.

    Statements reuse the synthesizer's labelled/traceable form, so governance
    output reads the same way as engineering reports. No wall-clock value is
    included: identical evidence yields an identical report.
    """
    violations = list(violations)
    critical = [v for v in violations if v.severity == SEVERITY_CRITICAL]
    pending = [v for v in violations if not v.acknowledged]

    summary = [
        statement(LABEL_OBSERVED,
                  f"{len(violations)} governance violation(s) detected"
                  + (f" across {scanned} observed execution(s)." if scanned is not None
                     else "."),
                  "openclaw.task_runs + LisaOS evidence"),
    ]
    if violations:
        summary.append(statement(
            LABEL_MISSING,
            f"{len(critical)} of these ran change-making work with no LisaOS evidence.",
            "violation.severity"))
        summary.append(statement(
            LABEL_OBSERVED,
            f"{len(pending)} violation(s) are unacknowledged and currently block "
            "governed execution.",
            "violation.acknowledged"))
    else:
        summary.append(statement(
            LABEL_OBSERVED,
            "All observed governed activity correlates with LisaOS evidence.",
            "openclaw.task_runs + LisaOS evidence"))

    entries = []
    for violation in violations:
        activity = violation.observed_activity
        entries.append({
            "violation_id": violation.violation_id,
            "severity": violation.severity,
            "acknowledged": violation.acknowledged,
            "detected_rule": list(violation.governing_rule),
            "evidence_found": ["openclaw.task_runs"],
            "evidence_missing": list(violation.missing_evidence),
            "classification": (
                "GOVERNED_WORK_WITHOUT_EVIDENCE"),
            "recommended_operator_action": (
                "Review the run, then either acknowledge the deviation with an "
                "attributed reason, or re-run the work through `lisa \"<mission>\"` "
                "so it produces evidence. LisaOS will not re-route it for you."),
            "statements": [
                statement(LABEL_OBSERVED,
                          f"run {activity.get('run_id')} on agent "
                          f"{activity.get('agent_id')} ({activity.get('runtime')}) "
                          f"at {violation.timestamp}, status "
                          f"{activity.get('status')}.",
                          "openclaw.task_runs"),
                statement(LABEL_OBSERVED,
                          f"task text matched {', '.join(violation.governing_rule)}.",
                          "core.task_classifier"),
                statement(LABEL_MISSING,
                          f"no correlating {' or '.join(violation.missing_evidence)} "
                          f"record exists for this run id.",
                          "reports/lisa evidence ledgers"),
            ],
            "observed_activity": dict(activity),
        })

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": {"statements": summary},
        "counts": {
            "violations": len(violations),
            "critical": len(critical),
            "unacknowledged": len(pending),
            "scanned": scanned,
        },
        "violations": entries,
    }


def render_governance_report(report: dict[str, Any]) -> str:
    """Deterministic plain-text rendering."""
    if not isinstance(report, dict) or "violations" not in report:
        raise GovernanceDetectionError(
            "render_governance_report requires a report from build_governance_report()")
    lines = [
        "=" * 78,
        "LisaOS Governance Detection Report",
        "=" * 78,
    ]
    for item in report["summary"]["statements"]:
        lines.append(f"  [{item['label']:<10}] {item['text']}")
        lines.append(f"               ↳ source: {item['source']}")
    lines.append("")

    if not report["violations"]:
        lines.append("No governance violations detected.")
        lines.append("=" * 78)
        return "\n".join(lines)

    for entry in report["violations"]:
        ack = "ACKNOWLEDGED" if entry["acknowledged"] else "UNACKNOWLEDGED"
        lines.append("-" * 78)
        lines.append(f"violation {entry['violation_id']}  "
                     f"[{entry['severity'].upper()}] [{ack}]")
        lines.append(f"classification : {entry['classification']}")
        lines.append(f"detected rule  : {', '.join(entry['detected_rule'])}")
        lines.append(f"evidence found : {', '.join(entry['evidence_found'])}")
        lines.append(f"evidence missing: {', '.join(entry['evidence_missing'])}")
        for item in entry["statements"]:
            lines.append(f"  [{item['label']:<10}] {item['text']}")
            lines.append(f"               ↳ source: {item['source']}")
        lines.append(f"  action: {entry['recommended_operator_action']}")
        lines.append("")

    lines.append("=" * 78)
    lines.append("Detection is deterministic and evidence-backed. LisaOS reports and")
    lines.append("blocks; it does not decide how the work should proceed.")
    lines.append("=" * 78)
    return "\n".join(lines)


def report_to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
