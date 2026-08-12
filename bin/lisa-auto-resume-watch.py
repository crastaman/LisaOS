#!/usr/bin/env python3
"""lisa-auto-resume-watch — deterministic auto-resume watcher (command payload).

Designed as the --command for an OpenClaw cron job. Runs headless: loads
persisted graph state, decides whether to re-dispatch, and re-dispatches
only when worker state has changed (HWM advanced or non-terminal packages
remain).

NEVER invokes MAIN/LLM. NEVER narrates polling output. Preserves exactly-once
semantics: a DONE mission is never re-dispatched.

Exit codes:
    0   DONE (no work needed, or dispatch completed successfully)
    3   WAKE_MAIN (escalation — cron failure alert will notify MAIN)
    2   dispatch error (cron records as error run)
"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.auto_resume import (
    resume_if_needed,
    graph_state_path_for_goal,
    DECISION_CONTINUE,
    DECISION_WAKE_MAIN,
    DECISION_DONE,
    OPENCLAW_DB,
)

def _dispatch_bin() -> str:
    return str(Path(__file__).resolve().parent / "lisa-dispatch")


def _run_dispatch(goal_path: str) -> int:
    """Run lisa-dispatch as a subprocess with --auto-resume. Returns exit code."""
    # Default ON: deployed cron must explicitly opt out, never silently omit it.
    if os.environ.get("LISA_DELIVERY_PREFLIGHT", "true").lower() not in {"0", "false", "no"}:
        preflight = [sys.executable, str(Path(__file__).resolve().parent / "lisa-cron-preflight"),
                     "--job-id", os.environ.get("LISA_CRON_JOB_ID", "auto-resume-watch")]
        channel = os.environ.get("LISA_DELIVERY_CHANNEL")
        if channel:
            preflight += ["--channel", channel]
        if os.environ.get("LISA_DELIVERY_BEST_EFFORT", "").lower() in {"1", "true", "yes"}:
            preflight.append("--best-effort")
        if os.environ.get("LISA_CRON_DB"):
            preflight += ["--db", os.environ["LISA_CRON_DB"]]
        checked = subprocess.run(preflight, capture_output=True, text=True)
        if checked.returncode != 0:
            print("delivery preflight failed; dispatch skipped; tokens_burned=0", file=sys.stderr)
            return checked.returncode
    cmd = [sys.executable, _dispatch_bin(), "run", goal_path, "--auto-resume"]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=600,  # 10-minute hard cap
    )
    # Only print on non-zero exit (error path) so cron surface is silent on success.
    if result.returncode != 0:
        print(result.stderr[:2000], file=sys.stderr)
    return result.returncode


def _find_active_goal() -> str | None:
    """Return the explicitly configured mission goal path."""
    configured = os.environ.get("LISA_MISSION_GOAL")
    if configured and Path(configured).is_file():
        return configured
    return None


def main() -> int:
    if not os.environ.get("LISA_MISSION_GOAL"):
        print("WAKE_MAIN: LISA_MISSION_GOAL is required for mission-scoped auto-resume.",
              file=sys.stderr)
        return 3
    goal_path = _find_active_goal()
    if goal_path is None:
        print("WAKE_MAIN: configured LISA_MISSION_GOAL is missing or unreadable.",
              file=sys.stderr)
        return 3

    graph_state_path = graph_state_path_for_goal(goal_path)
    decision = resume_if_needed(goal_path, graph_state_path=graph_state_path,
                                enforce_staleness=True, event_db_path=OPENCLAW_DB)
    from core.auto_resume import load_graph_state
    from core.reconciliation import pending_reconciliation_queue
    state = load_graph_state(graph_state_path)
    unknown_count = len(pending_reconciliation_queue(state))

    if decision == DECISION_DONE:
        # Mission complete. Silent success.
        return 0

    if decision == DECISION_WAKE_MAIN:
        # Escalation needed — non-zero exit so cron records it as an error
        # and MAIN can pick it up via failure notification.
        failed = [pid for pid, s in (state or {}).get("packages", {}).items()
                  if s in ("failed", "timed_out")]
        print(f"WAKE_MAIN: {len(failed)} failed package(s); UNKNOWN={unknown_count}.",
              file=sys.stderr)
        return 3

    # DECISION_CONTINUE — re-dispatch
    print(f"auto-resume: UNKNOWN={unknown_count}", file=sys.stderr)
    rc = _run_dispatch(goal_path)
    return rc


if __name__ == "__main__":
    sys.exit(main())
