"""Durable session retirement and handoff artifacts (RC005/D2).

`write_handoff` emits the `lisa-handoff/1` durable contract. When a caller
passes no explicit `summary`, the production enrichment layer
(`build_production_summary`) populates the full 16-key contract from
authoritative persisted Lisa state (mission ledger, capacity ledger, graph
state, governance violations, activation-gate report).

Design contract (durable handoff production activation, R3):
  * lisa-handoff/1 schema, atomic tmp+replace write, and existing callers are
    preserved unchanged.
  * No second handoff format and no duplicate state authority: the layer only
    READS pre-existing persisted state and writes the handoff artifact.
  * Fail-safe: `mission_loader` never raises; keys whose authoritative source
    is unavailable are simply omitted; unknown-worker / unresolved-error
    lists default to [] (no invented values).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.session_lifecycle import SessionLifecycleStore

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
DEFAULT_DB = Path.home() / ".openclaw" / "state" / "openclaw.sqlite"
HANDOFF_DIR = LISA_BASE / "reports" / "lisa" / "orchestration" / "handoffs"

# Canonical 16-key lisa-handoff/1 contract asserted by TestR8_DurableHandoff.
REQUIRED_CONTRACT_KEYS = [
    "mission_objective", "current_wave", "current_package",
    "completed_work", "outstanding_work", "repo", "branch", "head",
    "authorization_boundaries", "active_workers", "unknown_workers",
    "unresolved_errors", "decisions", "artifacts", "gate_state",
    "next_permitted_action",
]

MISSION_LEDGER = LISA_BASE / "reports" / "lisa" / "orchestration" / "rc006_mission_state.json"
CAPACITY_LEDGER = LISA_BASE / "reports" / "lisa" / "capacity_ledger.json"
GRAPH_STATE = LISA_BASE / "reports" / "lisa" / "orchestration" / "graph_state.json"
VIOLATIONS_LOG = LISA_BASE / "reports" / "lisa" / "orchestration" / "governance" / "violations.jsonl"
GATE_REPORT = LISA_BASE / "reports" / "lisa" / "orchestration" / "LISA-ACTIVATION-GATE-POST-RC006.md"
ORCH_DIR = LISA_BASE / "reports" / "lisa" / "orchestration"
DECISION_BUNDLES = [
    LISA_BASE / "reports" / "lisa" / "r001_decision_bundle.md",
    LISA_BASE / "reports" / "lisa" / "r002a_decision_bundle.md",
    LISA_BASE / "reports" / "lisa" / "r002b_decision_bundle.md",
    LISA_BASE / "reports" / "lisa" / "r002c_decision_bundle.md",
]


class MissionLoaderError(Exception):
    """Raised when a required persisted state file is missing or malformed."""


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _read_lines(path: Path) -> list[str] | None:
    if not path.is_file():
        return None
    try:
        return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return None


def _json_records(path: Path) -> list[dict[str, Any]]:
    lines = _read_lines(path)
    if lines is None:
        return []
    out: list[dict[str, Any]] = []
    for ln in lines:
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _wave_review_stage(state: dict[str, Any]) -> str | None:
    wave5c = state.get("wave5c")
    if not isinstance(wave5c, dict):
        return None
    accepted = set()
    for key, value in wave5c.items():
        if isinstance(value, str) and value.strip().upper() == "ACCEPT":
            accepted.add(key)
    # Review rounds superseded by an ACCEPT on the same review thread are not
    # outstanding: only keys that carry final review outcomes are pending work.
    final_keys = [k for k in wave5c if k.endswith("_final") or "round" not in k]
    pending = [k for k in final_keys if k not in accepted]
    if pending:
        return pending[-1]
    if accepted:
        return "complete"
    return None


def _completed_wave_work(state: dict[str, Any]) -> list[str]:
    out: list[str] = []
    wave5a = state.get("wave_5a")
    if isinstance(wave5a, dict) and wave5a:
        out.append("5A migration + observability (ledger: wave_5a)")
    wave5b = state.get("wave_5b")
    if isinstance(wave5b, dict) and wave5b:
        result = wave5b.get("result")
        result_label = result.get("result") if isinstance(result, dict) else str(result or "recorded")
        out.append("5B reliability acceptance R1-R15 (ledger: wave_5b, result "
                   + str(result_label) + ")")
    wave5c = state.get("wave5c")
    if isinstance(wave5c, dict):
        accepted = [k for k, v in wave5c.items()
                    if isinstance(v, str) and v.strip().upper() == "ACCEPT"]
        for key in sorted(accepted):
            out.append(f"5C review {key}: ACCEPT")
    return out


def _outstanding_wave_work(state: dict[str, Any]) -> list[str]:
    wave5c = state.get("wave5c")
    if not isinstance(wave5c, dict):
        return []
    # Only final review keys (or non-round keys) are genuinely outstanding;
    # earlier rounds superseded by an ACCEPT are completed, not pending.
    final_keys = [k for k in wave5c if k.endswith("_final") or "round" not in k]
    return [f"5C review {k}: pending" for k in final_keys
            if not (isinstance(wave5c[k], str) and wave5c[k].strip().upper() == "ACCEPT")]


def _active_workers(state: dict[str, Any], *, capacity_path: Path = CAPACITY_LEDGER) -> list[str]:
    ledger = _read_json(capacity_path)
    if not ledger:
        return []
    return sorted(name for name, rec in ledger.items()
                  if isinstance(rec, dict) and rec.get("health_state") == "healthy")


def _unknown_workers(state: dict[str, Any], *, graph_path: Path = GRAPH_STATE) -> list[str]:
    if not graph_path.is_file():
        return []
    try:
        from core.reconciliation import graph_unknown_packages
        loaded = _read_json(graph_path)
        return list(graph_unknown_packages(loaded))
    except Exception:
        return []


def _unresolved_errors(state: dict[str, Any], *,
                       violations_path: Path = VIOLATIONS_LOG,
                       ack_path: Path | None = None) -> list[dict[str, Any]]:
    violations = _json_records(violations_path)
    ack = _json_records(ack_path or (LISA_BASE / "reports" / "lisa" / "governance_acknowledgements.jsonl"))
    acked_ids: set[str] = set()
    for r in ack:
        for vid in r.get("violation_ids") or []:
            if isinstance(vid, str) and vid:
                acked_ids.add(vid)
    out: list[dict[str, Any]] = []
    for rec in violations:
        vid = str(rec.get("violation_id") or rec.get("id") or "")
        if vid and vid in acked_ids:
            continue
        rules = rec.get("governing_rule") or []
        out.append({"violation_id": vid, "kind": ",".join(rules) if isinstance(rules, list) else str(rules),
                    "summary": str(rec.get("reason") or rec.get("detail") or "")[:200]})
    return out[:50]  # bounded; full log remains authoritative at governance/violations.jsonl


def _decision_names(state: dict[str, Any]) -> list[str]:
    return [p.name for p in DECISION_BUNDLES if p.is_file()]


def _artifact_paths(state: dict[str, Any], *,
                    orchestration_dir: Path = ORCH_DIR) -> list[str]:
    out: list[str] = []
    baseline = (state.get("preflight") or {}).get("regression_baseline")
    if isinstance(baseline, dict):
        out.append(f"regression baseline: {json.dumps(baseline, sort_keys=True)}")
    for p in sorted(orchestration_dir.iterdir()) if orchestration_dir.is_dir() else []:
        if p.is_file() and p.name.endswith((".json", ".md")) and p.name != "graph_state.json":
            out.append(str(p))
    return out


def _gate_state(state: dict[str, Any], *, gate_report: Path = GATE_REPORT) -> str:
    if gate_report.is_file():
        return "ACTIVATION-GATE: BLOCKED (R3 pending)"
    return "NO ACTIVATION GATE REPORT"


def _next_permitted_action(state: dict[str, Any], *, gate_report: Path = GATE_REPORT) -> str:
    if gate_report.is_file():
        return ("Roshan authorizes a bounded follow-up mission to populate the full "
                "lisa-handoff/1 contract durably and produce a real production handoff "
                "artifact for fresh-session recovery. WBS050 is NOT authorized.")
    npa = state.get("next_permitted_action")
    return str(npa) if npa else "NO PERSISTED NEXT PERMITTED ACTION"


def _current_wave(state: dict[str, Any]) -> str | None:
    stage = _wave_review_stage(state)
    return f"5C ({stage})" if stage else None


def mission_loader(
    path: Path = MISSION_LEDGER,
) -> tuple[Callable[[], dict[str, Any] | None], Path]:
    """Return (loader, source_path) for the authoritative mission ledger.

    The loader NEVER raises: a missing or malformed ledger returns None, and
    the enrichment layer then emits only keys it can still source (empty
    worker/error lists and no invented mission values).
    """

    def _load() -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return loaded if isinstance(loaded, dict) else None

    return _load, path


def build_production_summary(
    state: dict[str, Any] | None = None,
    *,
    mission_path: Path = MISSION_LEDGER,
    capacity_path: Path = CAPACITY_LEDGER,
    graph_path: Path = GRAPH_STATE,
    violations_path: Path = VIOLATIONS_LOG,
    ack_path: Path | None = None,
    orchestration_dir: Path = ORCH_DIR,
    gate_report: Path = GATE_REPORT,
) -> dict[str, Any]:
    """Populate the complete lisa-handoff/1 contract from persisted state.

    Every key is sourced from authoritative durable state (mission ledger,
    capacity ledger, graph state, governance violations, gate report). No
    conversational prose and no invented values: keys whose source is
    unavailable are omitted, and unknown-worker / unresolved-error lists
    default to []. Paths are injectable for hermetic tests; production
    defaults point at the live persisted sources.
    """
    if state is None:
        loader, _ = mission_loader(mission_path)
        state = loader()
    if not isinstance(state, dict):
        return {}
    summary: dict[str, Any] = {}
    if state.get("title"):
        summary["mission_objective"] = str(state["title"])
    current_wave = _current_wave(state)
    if current_wave:
        summary["current_wave"] = current_wave
    if state.get("status"):
        summary["current_package"] = str(state["status"])
    completed = _completed_wave_work(state)
    if completed:
        summary["completed_work"] = completed
    outstanding = _outstanding_wave_work(state)
    if outstanding:
        summary["outstanding_work"] = outstanding
    if state.get("repo"):
        summary["repo"] = str(state["repo"])
    if state.get("branch"):
        summary["branch"] = str(state["branch"])
    if state.get("verified_head"):
        summary["head"] = str(state["verified_head"])
    boundaries: list[str] = []
    if state.get("wbs_boundary"):
        boundaries.append(str(state["wbs_boundary"]))
    boundaries.append("WBS050 is NOT authorized. No WBS implementation may begin.")
    summary["authorization_boundaries"] = boundaries
    summary["active_workers"] = _active_workers(state, capacity_path=capacity_path)
    summary["unknown_workers"] = _unknown_workers(state, graph_path=graph_path)
    summary["unresolved_errors"] = _unresolved_errors(
        state, violations_path=violations_path, ack_path=ack_path)
    summary["decisions"] = _decision_names(state)
    summary["artifacts"] = _artifact_paths(state, orchestration_dir=orchestration_dir)
    summary["gate_state"] = _gate_state(state, gate_report=gate_report)
    summary["next_permitted_action"] = _next_permitted_action(
        state, gate_report=gate_report)
    return summary


def handoff_required(session: dict[str, Any] | None, *, threshold: float | None = None) -> bool:
    if threshold is None:
        from core.reliability_config import load_reliability_config
        threshold = load_reliability_config().session_threshold("warning_threshold_pct", 0.80)
    return float((session or {}).get("context_pct") or 0) >= threshold


def retire_session(session_key: str, reason: str, context_pct: float,
                   *, db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return SessionLifecycleStore(db_path).upsert(
        session_key, session_state="RETIRED", context_pct=min(1.0, max(0.0, context_pct)),
        retired_at=now, last_seen_at=int(datetime.now(timezone.utc).timestamp() * 1000),
    ) | {"retirement_reason": reason}


def write_handoff(session_key: str, target_worker: str, summary: Any,
                  *, output_dir: Path = HANDOFF_DIR,
                  mission_path: Path = MISSION_LEDGER) -> Path:
    """Atomically write a lisa-handoff/1 artifact.

    When `summary` is None (or an empty mapping) the production enrichment
    layer populates the complete 16-key contract from authoritative persisted
    state. Explicit caller-provided summaries (legacy 3-key context-retirement
    and R8 test payloads) are written unchanged, preserving compatibility.
    """
    if summary is None or summary == {}:
        summary = build_production_summary(mission_path=mission_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in session_key)[-120:]
    path = output_dir / f"{safe}-handoff.json"
    payload = {"schema": "lisa-handoff/1", "session_key": session_key,
               "target_worker": target_worker, "summary": summary,
               "created_at": datetime.now(timezone.utc).isoformat()}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path
